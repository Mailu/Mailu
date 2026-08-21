""" Mailu marshmallow fields and schema
"""

from copy import deepcopy
from collections import Counter
from datetime import timezone

import inspect
import json
import logging
import yaml

import sqlalchemy

from marshmallow import missing, pre_load, post_load, post_dump, fields, Schema
from marshmallow.utils import ensure_text_type
from marshmallow.exceptions import ValidationError
from marshmallow_sqlalchemy import SQLAlchemyAutoSchemaOpts
from marshmallow_sqlalchemy.fields import RelatedList

from flask_marshmallow import Marshmallow

from cryptography.hazmat.primitives import serialization

from pygments import highlight
from pygments.token import Token
from pygments.lexers import get_lexer_by_name
from pygments.lexers.data import YamlLexer
from pygments.formatters import get_formatter_by_name

from mailu import models, dkim


ma = Marshmallow()


### import logging and schema colorization ###

_model2schema = {}

def get_schema(cls=None):
    """ return schema class for model """
    if cls is None:
        return _model2schema.values()
    return _model2schema.get(cls)

def mapped(cls):
    """ register schema in model2schema map """
    _model2schema[cls.Meta.model] = cls
    return cls

class Logger:
    """ helps with counting and colorizing
        imported and exported data
    """

    class MyYamlLexer(YamlLexer):
        """ colorize yaml constants and integers """
        def get_tokens(self, text, unfiltered=False):
            for typ, value in super().get_tokens(text, unfiltered):
                if typ is Token.Literal.Scalar.Plain:
                    if value in {'true', 'false', 'null'}:
                        typ = Token.Keyword.Constant
                    elif value == HIDDEN:
                        typ = Token.Error
                    else:
                        try:
                            int(value, 10)
                        except ValueError:
                            try:
                                float(value)
                            except ValueError:
                                pass
                            else:
                                typ = Token.Literal.Number.Float
                        else:
                            typ = Token.Literal.Number.Integer
                yield typ, value

    def __init__(self, want_color=None, can_color=False, debug=False, secrets=False):

        self.lexer = 'yaml'
        self.formatter = 'terminal'
        self.strip = False
        self.verbose = 0
        self.quiet = False
        self.secrets = secrets
        self.debug = debug
        self.print = print

        self.color = want_color or can_color

        self._counter = Counter()
        self._schemas = {}

        # log contexts
        self._diff_context = {
            'full': True,
            'secrets': secrets,
        }
        log_context = {
            'secrets': secrets,
        }

        # register listeners
        for schema in get_schema():
            model = schema.Meta.model
            self._schemas[model] = schema(context=log_context)
            sqlalchemy.event.listen(model, 'after_insert', self._listen_insert)
            sqlalchemy.event.listen(model, 'after_update', self._listen_update)
            sqlalchemy.event.listen(model, 'after_delete', self._listen_delete)

        # special listener for dkim_key changes
        # TODO: _listen_dkim can be removed when dkim keys are stored in database
        self._dedupe_dkim = set()
        sqlalchemy.event.listen(models.db.session, 'after_flush', self._listen_dkim)

        # register debug logger for sqlalchemy
        if self.debug:
            logging.basicConfig()
            logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    def _log(self, action, target, message=None):
        if message is None:
            try:
                message = self._schemas[target.__class__].dump(target)
            except KeyError:
                message = target
        if not isinstance(message, str):
            message = repr(message)
        self.print(f'{action} {target.__table__}: {self.colorize(message)}')

    def _listen_insert(self, mapper, connection, target): # pylint: disable=unused-argument
        """ callback method to track import """
        self._counter.update([('Created', target.__table__.name)])
        if self.verbose:
            self._log('Created', target)

    def _listen_update(self, mapper, connection, target): # pylint: disable=unused-argument
        """ callback method to track import """

        changes = {}
        inspection = sqlalchemy.inspect(target)
        for attr in sqlalchemy.orm.class_mapper(target.__class__).column_attrs:
            history = getattr(inspection.attrs, attr.key).history
            if history.has_changes() and history.deleted:
                before = history.deleted[-1]
                after = getattr(target, attr.key)
                # we don't have ordered lists
                if isinstance(before, list):
                    before = set(before)
                if isinstance(after, list):
                    after = set(after)
                # TODO: this can be removed when comment is not nullable in model
                if attr.key == 'comment' and not before and not after:
                    pass
                # only remember changed keys
                elif before != after:
                    if self.verbose:
                        changes[str(attr.key)] = (before, after)
                    else:
                        break

        if self.verbose:
            # use schema to log changed attributes
            schema = get_schema(target.__class__)
            only = set(changes.keys()) & set(schema().fields.keys())
            if only:
                for key, value in schema(
                    only=only,
                    context=self._diff_context
                ).dump(target).items():
                    before, after = changes[key]
                    if value == HIDDEN:
                        before = HIDDEN if before else before
                        after = HIDDEN if after else after
                    else:
                        # also hide this
                        after = value
                    self._log('Modified', target, f'{str(target)!r} {key}: {before!r} -> {after!r}')

        if changes:
            self._counter.update([('Modified', target.__table__.name)])

    def _listen_delete(self, mapper, connection, target): # pylint: disable=unused-argument
        """ callback method to track import """
        self._counter.update([('Deleted', target.__table__.name)])
        if self.verbose:
            self._log('Deleted', target)

    # TODO: _listen_dkim can be removed when dkim keys are stored in database
    def _listen_dkim(self, session, flush_context): # pylint: disable=unused-argument
        """ callback method to track import """
        for target in session.identity_map.values():
            # look at Domains originally loaded from db
            if not isinstance(target, models.Domain) or not target._sa_instance_state.load_path:
                continue
            before = target._dkim_key_on_disk
            after = target._dkim_key
            # "de-dupe" messages; this event is fired at every flush
            if before == after or (target, before, after) in self._dedupe_dkim:
                continue
            self._dedupe_dkim.add((target, before, after))
            self._counter.update([('Modified', target.__table__.name)])
            if self.verbose:
                if self.secrets:
                    before = before.decode('ascii', 'ignore')
                    after = after.decode('ascii', 'ignore')
                else:
                    before = HIDDEN if before else ''
                    after = HIDDEN if after else ''
                self._log('Modified', target, f'{str(target)!r} dkim_key: {before!r} -> {after!r}')

    def track_serialize(self, obj, item, backref=None):
        """ callback method to track import """
        # called for backref modification?
        if backref is not None:
            self._log(
                'Modified', item, '{target!r} {key}: {before!r} -> {after!r}'.format_map(backref))
            return
        # show input data?
        if self.verbose < 2:
            return
        # hide secrets in data
        if not self.secrets:
            item = self._schemas[obj.opts.model].hide(item)
            if 'hash_password' in item:
                item['password'] = HIDDEN
            if 'fetches' in item:
                for fetch in item['fetches']:
                    fetch['password'] = HIDDEN
        self._log('Handling', obj.opts.model, item)

    def changes(self, *messages, **kwargs):
        """ show changes gathered in counter """
        if self.quiet:
            return
        if self._counter:
            changes = []
            last = None
            for (action, what), count in sorted(self._counter.items()):
                if action != last:
                    if last:
                        changes.append('/')
                    changes.append(f'{action}:')
                    last = action
                changes.append(f'{what}({count})')
        else:
            changes = ['No changes.']
        self.print(*messages, *changes, **kwargs)

    def _format_errors(self, store, path=None):

        res = []
        if path is None:
            path = []
        for key in sorted(store):
            location = path + [str(key)]
            value = store[key]
            if isinstance(value, dict):
                res.extend(self._format_errors(value, location))
            else:
                for message in value:
                    res.append((".".join(location), message))

        if path:
            return res

        maxlen = max(len(loc) for loc, msg in res)
        res = [f'     - {loc.ljust(maxlen)} : {msg}' for loc, msg in res]
        errors = f'{len(res)} error{["s",""][len(res)==1]}'
        res.insert(0, f'[ValidationError] {errors} occurred during input validation')

        return '\n'.join(res)

    def _is_validation_error(self, exc):
        """ walk traceback to extract invalid field from marshmallow """
        path = []
        trace = exc.__traceback__
        while trace:
            if trace.tb_frame.f_code.co_name == '_serialize':
                if 'attr' in trace.tb_frame.f_locals:
                    path.append(trace.tb_frame.f_locals['attr'])
            elif trace.tb_frame.f_code.co_name == '_init_fields':
                spec = ', '.join(
                    '.'.join(path + [key])
                    for key in trace.tb_frame.f_locals['invalid_fields'])
                return f'Invalid filter: {spec}'
            trace = trace.tb_next
        return None

    def format_exception(self, exc):
        """ format ValidationErrors and other exceptions when not debugging """
        if isinstance(exc, ValidationError):
            return self._format_errors(exc.messages)
        if isinstance(exc, ValueError):
            if msg := self._is_validation_error(exc):
                return msg
        if self.debug:
            return None
        msg = ' '.join(str(exc).split())
        return f'[{exc.__class__.__name__}] {msg}'

    colorscheme = {
        Token:                  ('',        ''),
        Token.Name.Tag:         ('cyan',    'cyan'),
        Token.Literal.Scalar:   ('green',   'green'),
        Token.Literal.String:   ('green',   'green'),
        Token.Name.Constant:    ('green',   'green'), # multiline strings
        Token.Keyword.Constant: ('magenta', 'magenta'),
        Token.Literal.Number:   ('magenta', 'magenta'),
        Token.Error:            ('red',     'red'),
        Token.Name:             ('red',     'red'),
        Token.Operator:         ('red',     'red'),
    }

    def colorize(self, data, lexer=None, formatter=None, color=None, strip=None):
        """ add ANSI color to data """

        if color is False or not self.color:
            return data

        lexer = lexer or self.lexer
        lexer = Logger.MyYamlLexer() if lexer == 'yaml' else get_lexer_by_name(lexer)
        formatter = get_formatter_by_name(formatter or self.formatter, colorscheme=self.colorscheme)
        if strip is None:
            strip = self.strip

        res = highlight(data, lexer, formatter)
        if strip:
            return res.rstrip('\n')
        return res


### marshmallow render modules ###

# hidden attributes
class _Hidden:
    def __bool__(self):
        return False
    def __copy__(self):
        return self
    def __deepcopy__(self, _):
        return self
    def __eq__(self, other):
        return str(other) == '<hidden>'
    def __repr__(self):
        return '<hidden>'
    __str__ = __repr__

yaml.add_representer(
    _Hidden,
    lambda dumper, data: dumper.represent_data(str(data))
)

HIDDEN = _Hidden()

# multiline attributes
class _Multiline(str):
    pass

yaml.add_representer(
    _Multiline,
    lambda dumper, data: dumper.represent_scalar(u'tag:yaml.org,2002:str', data, style='|')

)

# yaml render module
class RenderYAML:
    """ Marshmallow YAML Render Module
    """

    class SpacedDumper(yaml.Dumper):
        """ YAML Dumper to add a newline between main sections
            and double the indent used
        """

        def write_line_break(self, data=None):
            super().write_line_break(data)
            if len(self.indents) == 1:
                super().write_line_break()

        def increase_indent(self, flow=False, indentless=False):
            return super().increase_indent(flow, False)

    @staticmethod
    def _augment(kwargs, defaults):
        """ add defaults to kwargs if missing
        """
        for key, value in defaults.items():
            if key not in kwargs:
                kwargs[key] = value

    _load_defaults = {}
    @classmethod
    def loads(cls, *args, **kwargs):
        """ load yaml data from string
        """
        cls._augment(kwargs, cls._load_defaults)
        return yaml.safe_load(*args, **kwargs)

    _dump_defaults = {
        'Dumper': SpacedDumper,
        'default_flow_style': False,
        'allow_unicode': True,
        'sort_keys': False,
    }
    @classmethod
    def dumps(cls, *args, **kwargs):
        """ dump data to yaml string
        """
        cls._augment(kwargs, cls._dump_defaults)
        return yaml.dump(*args, **kwargs)

# json encoder
class JSONEncoder(json.JSONEncoder):
    """ JSONEncoder supporting serialization of HIDDEN """
    def default(self, o):
        """ serialize HIDDEN """
        if isinstance(o, _Hidden):
            return str(o)
        return json.JSONEncoder.default(self, o)

# json render module
class RenderJSON:
    """ Marshmallow JSON Render Module
    """

    @staticmethod
    def _augment(kwargs, defaults):
        """ add defaults to kwargs if missing
        """
        for key, value in defaults.items():
            if key not in kwargs:
                kwargs[key] = value

    _load_defaults = {}
    @classmethod
    def loads(cls, *args, **kwargs):
        """ load json data from string
        """
        cls._augment(kwargs, cls._load_defaults)
        return json.loads(*args, **kwargs)

    _dump_defaults = {
        'separators': (',',':'),
        'cls': JSONEncoder,
    }
    @classmethod
    def dumps(cls, *args, **kwargs):
        """ dump data to json string
        """
        cls._augment(kwargs, cls._dump_defaults)
        return json.dumps(*args, **kwargs)


### marshmallow: custom fields ###

def _rfc3339(datetime):
    """ dump datetime according to rfc3339 """
    if datetime.tzinfo is None:
        datetime = datetime.astimezone(timezone.utc)
    res = datetime.isoformat()
    if res.endswith('+00:00'):
        return f'{res[:-6]}Z'
    return res

fields.DateTime.SERIALIZATION_FUNCS['rfc3339'] = _rfc3339
fields.DateTime.DESERIALIZATION_FUNCS['rfc3339'] = fields.DateTime.DESERIALIZATION_FUNCS['iso']
fields.DateTime.DEFAULT_FORMAT = 'rfc3339'

class LazyStringField(fields.String):
    """ Field that serializes a "false" value to the empty string
    """

    def _serialize(self, value, attr, obj, **kwargs):
        """ serialize None to the empty string
        """
        return value if value else ''

class CommaSeparatedListField(fields.Raw):
    """ Deserialize a string containing comma-separated values to
        a list of strings
    """

    default_error_messages = {
        "invalid": "Not a valid string or list.",
        "invalid_utf8": "Not a valid utf-8 string or list.",
    }

    def _deserialize(self, value, attr, data, **kwargs):
        """ deserialize comma separated string to list of strings
        """

        # empty
        if not value:
            return []

        # handle list
        if isinstance(value, list):
            try:
                value = [ensure_text_type(item) for item in value]
            except UnicodeDecodeError as exc:
                raise self.make_error("invalid_utf8") from exc

        # handle text
        else:
            if not isinstance(value, (str, bytes)):
                raise self.make_error("invalid")
            try:
                value = ensure_text_type(value)
            except UnicodeDecodeError as exc:
                raise self.make_error("invalid_utf8") from exc
            else:
                value = filter(bool, (item.strip() for item in value.split(',')))

        return list(value)


class DkimKeyField(fields.String):
    """ Serialize a dkim key to a multiline string and
        deserialize a dkim key data as string or list of strings
        to a valid dkim key
    """

    default_error_messages = {
        "invalid": "Not a valid string or list.",
        "invalid_utf8": "Not a valid utf-8 string or list.",
    }

    def _serialize(self, value, attr, obj, **kwargs):
        """ serialize dkim key as multiline string
        """

        # map empty string and None to None
        if not value:
            return ''

        # return multiline string
        return _Multiline(value.decode('utf-8'))

    def _wrap_key(self, begin, data, end):
        """ generator to wrap key into RFC 7468 format """
        yield begin
        pos = 0
        while pos < len(data):
            yield data[pos:pos+64]
            pos += 64
        yield end
        yield ''

    def _deserialize(self, value, attr, data, **kwargs):
        """ deserialize a string or list of strings to dkim key data
            with verification
        """

        # convert list to str
        if isinstance(value, list):
            try:
                value = ''.join(ensure_text_type(item) for item in value).strip()
            except UnicodeDecodeError as exc:
                raise self.make_error("invalid_utf8") from exc

        # only text is allowed
        else:
            if not isinstance(value, (str, bytes)):
                raise self.make_error("invalid")
            try:
                value = ensure_text_type(value).strip()
            except UnicodeDecodeError as exc:
                raise self.make_error("invalid_utf8") from exc

        # generate new key?
        if value.lower() == '-generate-':
            return dkim.gen_key()

        # no key or key is <hidden>?
        if not value or str(value) == '<hidden>':
            return None

        # remember part of value for ValidationError
        bad_key = value

        # strip header and footer, clean whitespace and wrap to 64 characters
        try:
            if value.startswith('-----BEGIN '):
                end = value.index('-----', 11) + 5
                header = value[:end]
                value = value[end:]
            else:
                header = '-----BEGIN PRIVATE KEY-----'

            if (pos := value.find('-----END ')) >= 0:
                end = value.index('-----', pos+9) + 5
                footer = value[pos:end]
                value = value[:pos]
            else:
                footer = '-----END PRIVATE KEY-----'
        except ValueError as exc:
            raise ValidationError(f'invalid dkim key {bad_key!r}') from exc

        # remove whitespace from key data
        value = ''.join(value.split())

        # remember part of value for ValidationError
        bad_key = f'{value[:25]}...{value[-10:]}' if len(value) > 40 else value

        # wrap key according to RFC 7468
        value = ('\n'.join(self._wrap_key(header, value, footer))).encode('ascii')

        # check key validity
        try:
            serialization.load_pem_private_key(value, password=None)
        except (UnicodeEncodeError, ValueError) as exc:
            raise ValidationError(f'invalid dkim key {bad_key!r}') from exc
        else:
            return value

class PasswordField(fields.Str):
    """ Serialize a hashed password hash by stripping the obsolete {SCHEME}
        Deserialize a plain password or hashed password into a hashed password
    """

    _hashes = {'PBKDF2', 'BLF-CRYPT', 'SHA512-CRYPT', 'SHA256-CRYPT', 'MD5-CRYPT', 'CRYPT'}

    def _serialize(self, value, attr, obj, **kwargs):
        """ strip obsolete {password-hash} when serializing """
        # strip scheme spec if in database - it's obsolete
        if value.startswith('{') and (end := value.find('}', 1)) >= 0:
            if value[1:end] in self._hashes:
                return value[end+1:]
        return value

    def _deserialize(self, value, attr, data, **kwargs):
        """ hashes plain password or checks hashed password
            also strips obsolete {password-hash} when deserializing
        """

        # when hashing is requested: use model instance to hash plain password
        if data.get('hash_password'):
            # hash password using model instance
            inst = self.metadata['model']()
            inst.set_password(value)
            value = inst.password
            del inst

        # strip scheme spec when specified - it's obsolete
        if value.startswith('{') and (end := value.find('}', 1)) >= 0:
            if value[1:end] in self._hashes:
                value = value[end+1:]

        # check if algorithm is supported
        inst = self.metadata['model'](password=value)
        try:
            # just check against empty string to see if hash is valid
            inst.check_password('')
        except ValueError as exc:
            # ValueError: hash could not be identified
            raise ValidationError(f'invalid password hash {value!r}') from exc
        del inst

        return value


### base schema ###

class Storage:
    """ Storage class to save information in context
    """

    context = {}

    def store(self, key, value):
        """ store value under key """
        key = f'{self.__class__.__name__}.{key}'
        self.context.setdefault('_track', {})[key] = value

    def recall(self, key):
        """ recall value from key """
        key = f'{self.__class__.__name__}.{key}'
        return self.context['_track'][key]

class BaseOpts(SQLAlchemyAutoSchemaOpts):
    """ Option class with sqla session
    """
    def __init__(self, meta, ordered=False):
        if not hasattr(meta, 'sqla_session'):
            meta.sqla_session = models.db.session
        if not hasattr(meta, 'sibling'):
            meta.sibling = False
        super(BaseOpts, self).__init__(meta, ordered=ordered)

class BaseSchema(ma.SQLAlchemyAutoSchema, Storage):
    """ Marshmallow base schema with custom exclude logic
        and option to hide sqla defaults
    """

    OPTIONS_CLASS = BaseOpts

    class Meta:
        """ Schema config """
        include_by_context = {}
        exclude_by_value = {}
        hide_by_context = {}
        order = []
        sibling = False

    def __init__(self, *args, **kwargs):

        # prepare only to auto-include explicitly specified attributes
        only = set(kwargs.get('only') or [])

        # get context
        context = kwargs.get('context', {})
        flags = {key for key, value in context.items() if value is True}

        # compile excludes
        exclude = set(kwargs.get('exclude', []))

        # always exclude
        exclude.update({'created_at', 'updated_at'} - only)

        # add include_by_context
        if context is not None:
            for need, what in getattr(self.Meta, 'include_by_context', {}).items():
                if not flags & set(need):
                    exclude |= what - only

        # update excludes
        kwargs['exclude'] = exclude

        # init SQLAlchemyAutoSchema
        super().__init__(*args, **kwargs)

        # exclude_by_value
        self._exclude_by_value = {
            key: values for key, values in getattr(self.Meta, 'exclude_by_value', {}).items()
            if key not in only
        }

        # exclude default values
        if not context.get('full'):
            for column in self.opts.model.__table__.columns:
                if column.name not in exclude and column.name not in only:
                    self._exclude_by_value.setdefault(column.name, []).append(
                        None if column.default is None else column.default.arg
                    )

        # hide by context
        self._hide_by_context = set()
        if context is not None:
            for need, what in getattr(self.Meta, 'hide_by_context', {}).items():
                if not flags & set(need):
                    self._hide_by_context |= what - only

        # remember primary keys
        self._primary = str(self.opts.model.__table__.primary_key.columns.values()[0].name)

        # determine attribute order
        if hasattr(self.Meta, 'order'):
            # use user-defined order
            order = self.Meta.order
        else:
            # default order is: primary_key + other keys alphabetically
            order = list(sorted(self.fields.keys()))
            if self._primary in order:
                order.remove(self._primary)
                order.insert(0, self._primary)

        # order fieldlists
        for fieldlist in (self.fields, self.load_fields, self.dump_fields):
            for field in order:
                if field in fieldlist:
                    fieldlist[field] = fieldlist.pop(field)

        # move post_load hook "_add_instance" to the end (after load_instance mixin)
        hooks = self._hooks[('post_load', False)]
        hooks.remove('_add_instance')
        hooks.append('_add_instance')

    def hide(self, data):
        """ helper method to hide input data for logging """
        # always returns a copy of data
        return {
            key: HIDDEN if key in self._hide_by_context else deepcopy(value)
            for key, value in data.items()
        }

    def get_parent(self):
        """ helper to determine parent of current object """
        for x in inspect.stack():
            loc = x[0].f_locals
            if 'ret_d' in loc:
                if isinstance(loc['self'], MailuSchema):
                    return self.context.get('config'), loc['attr_name']
                else:
                    return loc['self'].get_instance(loc['ret_d']), loc['attr_name']
        return None, None

    # this is only needed to work around the declared attr "email" primary key in model
    def get_instance(self, data):
        """ lookup item by defined primary key instead of key(s) from model """
        if self.transient:
            return None
        if keys := getattr(self.Meta, 'primary_keys', None):
            filters = {key: data.get(key) for key in keys}
            if None not in filters.values():
                try:
                    res = self.session.query(self.opts.model).filter_by(**filters).first()
                except sqlalchemy.exc.StatementError as exc:
                    raise ValidationError(f'Invalid {keys[0]}: {data.get(keys[0])!r}', data.get(keys[0])) from exc
                else:
                    return res
        res = super().get_instance(data)
        return res

    def _replacement_default(self, name):
        """Return the value a freshly-created model gets for one load field."""
        if name == self._primary:
            raise KeyError(name)

        mapper_property = self.opts.model.__mapper__.attrs.get(name)
        if isinstance(mapper_property, sqlalchemy.orm.RelationshipProperty):
            return [] if mapper_property.uselist else None
        if isinstance(mapper_property, sqlalchemy.orm.ColumnProperty):
            column = mapper_property.columns[0]
            if column.primary_key:
                raise KeyError(name)
            default = column.default
            if default is None:
                return None
            if default.is_scalar:
                return deepcopy(default.arg)
            if default.is_callable:
                return default.arg(None)
            raise KeyError(name)

        descriptor = getattr(self.opts.model, name, None)
        if isinstance(descriptor, property) and descriptor.fset is not None:
            return None
        raise KeyError(name)

    def _prepare_replacement_item(self, data):
        """Reset omitted public fields while retaining the persistent row."""
        if type(data) is not dict:
            return data
        instance = self.get_instance(data)
        if instance is None:
            return data
        for name, field in self.load_fields.items():
            if name in data:
                continue
            if field.required:
                # Required fields without input must still fail normal schema
                # validation. Do not manufacture ``None`` and crash a field
                # serializer before Marshmallow can report the contract error.
                continue
            try:
                value = self._replacement_default(name)
            except KeyError:
                pass
            else:
                data[name] = field._serialize( # pylint: disable=protected-access
                    value,
                    name,
                    instance,
                )
        return data

    @pre_load(pass_many=True)
    def _patch_many(self, items, many, **kwargs): # pylint: disable=unused-argument
        """ - flush sqla session before serializing a section when requested
              (make sure all objects that could be referred to later are created)
            - when in update mode: patch input data before deserialization
              - handle "prune" and "delete" items
              - replace values in keys starting with '-' with default
        """

        # flush sqla session
        if not self.Meta.sibling:
            self.opts.sqla_session.flush()

        # A default full import preserves rows by primary key but otherwise
        # retains replacement semantics. Populate omitted public fields with
        # the values a newly-created row would receive; do not borrow the
        # merge/list-union semantics used by --update.
        if self.context.get('reconcile'):
            originals = items if many else [items]
            self.store('original', deepcopy(originals))
            if many:
                return [
                    self._prepare_replacement_item(item)
                    for item in items
                ]
            return self._prepare_replacement_item(items)

        # stop early when not updating
        if not self.context.get('update'):
            return items

        # patch "delete", "prune" and "default"
        want_prune = []
        def patch(count, data):

            # we only process objects here
            if type(data) is not dict:
                raise ValidationError(f'Invalid item. {self.Meta.model.__tablename__.title()} needs to be an object.', f'{data!r}')

            # don't allow __delete__ coming from input
            if '__delete__' in data:
                raise ValidationError('Unknown field.', f'{count}.__delete__')

            # fail when hash_password is specified without password
            if 'hash_password' in data and not 'password' in data:
                raise ValidationError(
                    'Nothing to hash. Field "password" is missing.',
                    field_name = f'{count}.hash_password',
                )

            # handle "prune list" and "delete item" (-pkey: none and -pkey: id)
            for key in data:
                if key.startswith('-'):
                    if key[1:] == self._primary:
                        # delete or prune
                        if data[key] is None:
                            # prune
                            want_prune.append(True)
                            return None
                        # mark item for deletion
                        return {key[1:]: data[key], '__delete__': count}

            # handle "set to default value" (-key: none)
            def set_default(key, value):
                if not key.startswith('-'):
                    return (key, value)
                key = key[1:]
                if not key in self.opts.model.__table__.columns:
                    return (key, None)
                if value is not None:
                    raise ValidationError(
                        'Value must be "null" when resetting to default.',
                        f'{count}.{key}'
                    )
                value = self.opts.model.__table__.columns[key].default
                if value is None:
                    raise ValidationError(
                        'Field has no default value.',
                        f'{count}.{key}'
                    )
                return (key, value.arg)

            return dict(set_default(key, value) for key, value in data.items())

        # convert items to "delete" and filter "prune" item
        items = [
            item for item in [
                patch(count, item) for count, item in enumerate(items)
            ] if item
        ]

        # remember if prune was requested for _prune_items@post_load
        self.store('prune', bool(want_prune))

        # remember original items to stabilize password-changes in _add_instance@post_load
        self.store('original', items)

        return items

    @pre_load
    def _patch_item(self, data, many, **kwargs): # pylint: disable=unused-argument
        """ - call callback function to track import
            - stabilize import of items with auto-increment primary key
            - delete items
            - delete/prune list attributes
            - add missing required attributes
        """

        # callback
        if callback := self.context.get('callback'):
            callback(self, data)

        # stop early when not updating
        if not self.opts.load_instance or not self.context.get('update'):
            return data

        # stabilize import of auto-increment primary keys (not required),
        # by matching import data to existing items and setting primary key
        if not self._primary in data:
            parent, field = self.get_parent()
            if parent is not None:
                for item in getattr(parent, field):
                    existing = self.dump(item, many=False)
                    this = existing.pop(self._primary)
                    if data == existing:
                        self.instance = item
                        data[self._primary] = this
                        break

        # try to load instance
        instance = self.instance or self.get_instance(data)
        if instance is None:

            if '__delete__' in data:
                # deletion of non-existent item requested
                raise ValidationError(
                    f'Item to delete not found: {data[self._primary]!r}.',
                    field_name = f'{data["__delete__"]}.{self._primary}',
                )

        else:

            if self.context.get('update'):
                # delete instance from session when marked
                if '__delete__' in data:
                    self.opts.sqla_session.delete(instance)
                # delete item from lists or prune lists
                # currently: domain.alternatives, user.forward_destination,
                # user.manager_of, aliases.destination
                for key, value in data.items():
                    if not isinstance(self.fields.get(key), (
                        RelatedList, CommaSeparatedListField, fields.Raw)
                    ) or not isinstance(value, list):
                        continue
                    # deduplicate new value
                    new_value = set(value)
                    # handle list pruning
                    if '-prune-' in value:
                        value.remove('-prune-')
                        new_value.remove('-prune-')
                    else:
                        for old in getattr(instance, key):
                            # using str() is okay for now (see above)
                            new_value.add(str(old))
                    # handle item deletion
                    for item in value:
                        if item.startswith('-'):
                            new_value.remove(item)
                            try:
                                new_value.remove(item[1:])
                            except KeyError as exc:
                                raise ValidationError(
                                    f'Item to delete not found: {item[1:]!r}.',
                                    field_name=f'?.{key}',
                                ) from exc
                    # sort list of new values
                    data[key] = sorted(new_value)
                    # log backref modification not caught by modify hook
                    if isinstance(self.fields[key], RelatedList):
                        if callback := self.context.get('callback'):
                            before = {str(v) for v in getattr(instance, key)}
                            after = set(data[key])
                            if before != after:
                                callback(self, instance, {
                                    'key': key,
                                    'target': str(instance),
                                    'before': before,
                                    'after': after,
                                })

            # add attributes required for validation from db
            for attr_name, field_obj in self.load_fields.items():
                if field_obj.required and attr_name not in data:
                    data[attr_name] = getattr(instance, attr_name)

        return data

    @post_load(pass_many=True)
    def _prune_items(self, items, many, **kwargs): # pylint: disable=unused-argument
        """ handle list pruning """

        # stop early when not updating
        if not self.context.get('update'):
            return items

        # get prune flag from _patch_many@pre_load
        want_prune = self.recall('prune')

        # prune: determine if existing items in db need to be added or marked for deletion
        add_items = False
        del_items = False
        if self.Meta.sibling:
            # parent prunes automatically
            if not want_prune:
                # no prune requested => add old items
                add_items = True
        else:
            # parent does not prune automatically
            if want_prune:
                # prune requested => mark old items for deletion
                del_items = True

        if add_items or del_items:
            parent, field = self.get_parent()
            if parent is not None:
                existing = {item[self._primary] for item in items if self._primary in item}
                for item in getattr(parent, field):
                    key = getattr(item, self._primary)
                    if key not in existing:
                        if add_items:
                            items.append({self._primary: key})
                        else:
                            if self.context.get('update'):
                                self.opts.sqla_session.delete(self.instance or self.get_instance({self._primary: key}))

        return items

    @post_load
    def _add_instance(self, item, many, **kwargs): # pylint: disable=unused-argument
        """ - undo password change in existing instances when plain password did not change
            - add new instances to sqla session
        """

        if not item in self.opts.sqla_session:
            self.opts.sqla_session.add(item)
            return item

        # stop early when neither updating nor reconciling, or when the item
        # has no password attribute
        if (
            not (
                self.context.get('update')
                or self.context.get('reconcile')
            )
            or not hasattr(item, 'password')
        ):
            return item

        # did we hash a new plaintext password?
        original = None
        pkey = getattr(item, self._primary)
        for data in self.recall('original'):
            if 'hash_password' in data and data.get(self._primary) == pkey:
                original = data['password']
                break
        if original is None:
            # password was hashed by us
            return item

        # reset hash if plain password matches hash from db
        if attr := getattr(sqlalchemy.inspect(item).attrs, 'password', None):
            if attr.history.has_changes() and attr.history.deleted:
                try:
                    # reset password hash
                    inst = type(item)(password=attr.history.deleted[-1])
                    if inst.check_password(original):
                        if isinstance(item, models.User):
                            state = sqlalchemy.inspect(item)
                            generation = state.attrs.auth_generation
                            original_generation = (
                                generation.history.deleted[-1]
                                if generation.history.deleted
                                else None
                            )
                            item._preserve_auth_generation = True
                            try:
                                item.password = inst.password
                            finally:
                                del item._preserve_auth_generation
                            if (
                                original_generation is not None
                                and not state.attrs.enabled.history.has_changes()
                            ):
                                item.auth_generation = original_generation
                        else:
                            item.password = inst.password
                except ValueError:
                    # hash in db is invalid
                    pass
                else:
                    del inst

        return item

    @post_dump
    def _hide_values(self, data, many, **kwargs): # pylint: disable=unused-argument
        """ hide secrets """

        # stop early when not excluding/hiding
        if not self._exclude_by_value and not self._hide_by_context:
            return data

        # exclude or hide values
        full = self.context.get('full')
        return type(data)(
            (key, HIDDEN if key in self._hide_by_context else value)
            for key, value in data.items()
            if full or key not in self._exclude_by_value or value not in self._exclude_by_value[key]
        )

    # this field is used to mark items for deletion
    mark_delete = fields.Boolean(data_key='__delete__', load_only=True)

    # TODO: this can be removed when comment is not nullable in model
    comment = LazyStringField()


### schema definitions ###

@mapped
class DomainSchema(BaseSchema):
    """ Marshmallow schema for Domain model """
    class Meta:
        """ Schema config """
        model = models.Domain
        load_instance = True
        include_relationships = True
        exclude = ['users', 'managers', 'aliases']

        # Anonymous Email Service domain flags
        anonmail_enabled = fields.Boolean(load_default=False, dump_default=False)

        include_by_context = {
            ('dns',): {'dkim_publickey', 'dns_mx', 'dns_spf', 'dns_dkim', 'dns_dmarc'},
        }
        hide_by_context = {
            ('secrets',): {'dkim_key'},
        }
        exclude_by_value = {
            'alternatives': [[]],
            'dkim_key': [None],
            'dkim_publickey': [None],
            'dns_mx': [None],
            'dns_spf': [None],
            'dns_dkim': [None],
            'dns_dmarc': [None],
        }

    dkim_key = DkimKeyField(allow_none=True)
    dkim_publickey = fields.String(dump_only=True)
    dns_mx = fields.String(dump_only=True)
    dns_spf = fields.String(dump_only=True)
    dns_dkim = fields.String(dump_only=True)
    dns_dmarc = fields.String(dump_only=True)


@mapped
class TokenSchema(BaseSchema):
    """ Marshmallow schema for Token model """
    class Meta:
        """ Schema config """
        model = models.Token
        load_instance = True

        sibling = True

    password = PasswordField(required=True, metadata={'model': models.User})
    hash_password = fields.Boolean(load_only=True, load_default=False)


@mapped
class FetchSchema(BaseSchema):
    """ Marshmallow schema for Fetch model """
    class Meta:
        """ Schema config """
        model = models.Fetch
        load_instance = True

        sibling = True
        include_by_context = {
            ('full', 'import'): {'last_check', 'error'},
        }
        hide_by_context = {
            ('secrets',): {'password'},
        }


@mapped
class UserSchema(BaseSchema):
    """ Marshmallow schema for User model """
    class Meta:
        """ Schema config """
        model = models.User
        load_instance = True
        include_relationships = True
        exclude = [
            '_email',
            'address_type',
            'domain',
            'localpart',
            'domain_name',
            'quota_bytes_used',
            'auth_generation',
            'scim_resource',
        ]

        primary_keys = ['email']
        exclude_by_value = {
            'forward_destination': [[]],
            'tokens':              [[]],
            'fetches':             [[]],
            'manager_of':          [[]],
            'reply_enddate':       ['2999-12-31'],
            'reply_startdate':     ['1900-01-01'],
        }

    email = fields.String(required=True)
    tokens = fields.Nested(TokenSchema, many=True)
    fetches = fields.Nested(FetchSchema, many=True)

    password = PasswordField(required=True, metadata={'model': models.User})
    hash_password = fields.Boolean(load_only=True, load_default=False)


@mapped
class AliasSchema(BaseSchema):
    """ Marshmallow schema for Alias model """
    class Meta:
        """ Schema config """
        model = models.Alias
        load_instance = True
        exclude = [
            '_email',
            'address_type',
            'domain',
            'localpart',
            'domain_name',
        ]

        primary_keys = ['email']
        exclude_by_value = {
            'destination': [[]],
        }

    email = fields.String(required=True)
    destination = CommaSeparatedListField()

    # Anonymous Email Service metadata
    note = fields.String(allow_none=True)
    hostname = fields.String(allow_none=True)
    # Full config export/import must round-trip owned/anonmail aliases. Keep
    # this relationship read-only for standalone and --update loads; default
    # replacement enables it only after the reconciliation preflight.
    owner_email = fields.String(allow_none=True)
    # No load_default: in merge mode (config-import --update) an omitted field must
    # keep the stored value. On create the model column default (False) applies.
    disabled = fields.Boolean(dump_default=False)

    @pre_load
    def _owner_email_replacement_only(
        self,
        data,
        many,
        **kwargs,
    ): # pylint: disable=unused-argument
        if (
            type(data) is dict
            and 'owner_email' in data
            and not self.context.get('reconcile')
        ):
            raise ValidationError(
                'Unknown field.',
                field_name='owner_email',
            )
        return data


@mapped
class ConfigSchema(BaseSchema):
    """ Marshmallow schema for Config model """
    class Meta:
        """ Schema config """
        model = models.Config
        load_instance = True


@mapped
class RelaySchema(BaseSchema):
    """ Marshmallow schema for Relay model """
    class Meta:
        """ Schema config """
        model = models.Relay
        load_instance = True


@mapped
class MailuSchema(Schema, Storage):
    """ Marshmallow schema for complete Mailu config """
    class Meta:
        """ Schema config """
        model = models.MailuConfig
        render_module = RenderYAML

        order = ['domain', 'user', 'alias', 'relay'] # 'config'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # order fieldlists
        for fieldlist in (self.fields, self.load_fields, self.dump_fields):
            for field in self.Meta.order:
                if field in fieldlist:
                    fieldlist[field] = fieldlist.pop(field)

    @pre_load
    def _clear_config(self, data, many, **kwargs): # pylint: disable=unused-argument
        """ create config object in context if missing
            and reconcile it if replacement was requested
        """
        if 'config' not in self.context:
            self.context['config'] = models.MailuConfig()
        if self.context.get('clear'):
            self.context['reconcile'] = True
            self._reconcile_config(data)
        return data

    def _reconcile_config(self, data):
        """Prune absent rows while retaining rows present by public key."""
        if type(data) is not dict:
            return

        self._preflight_nested_identities(data)
        self._preflight_related_owners(data)
        retained = {}
        routing_addresses = {}
        for section, field in self.fields.items():
            items = data.get(section, [])
            if type(items) is not list:
                raise ValidationError(
                    'Not a valid list.',
                    field_name=section,
                )
            nested = field.schema
            model = nested.opts.model
            identities = set()
            primary_keys = set()
            managed_alias_items = []
            primary_column = (
                model.__table__.primary_key.columns.values()[0]
            )
            bind_processor = primary_column.type.bind_processor(
                models.db.session.get_bind().dialect
            )
            for position, item in enumerate(items):
                if type(item) is not dict:
                    raise ValidationError(
                        'Not a valid mapping.',
                        field_name=f'{section}.{position}',
                    )
                # This relationship was accidentally exposed by the first
                # persistent-identity implementation. It is internal state,
                # not configuration data, and must never be rebound.
                if model is models.User:
                    item.pop('scim_resource', None)
                if nested._primary not in item:
                    raise ValidationError(
                        'Missing data for required field.',
                        field_name=(
                            f'{section}.{position}.{nested._primary}'
                        ),
                    )
                try:
                    primary_key = item[nested._primary]
                    if bind_processor is not None:
                        primary_key = bind_processor(primary_key)
                except (AttributeError, TypeError, ValueError) as exc:
                    raise ValidationError(
                        f'Invalid {nested._primary}: '
                        f'{item[nested._primary]!r}.',
                        field_name=(
                            f'{section}.{position}.{nested._primary}'
                        ),
                    ) from exc
                if primary_key in primary_keys:
                    raise ValidationError(
                        f'Duplicate {nested._primary}: {primary_key!r}.',
                        field_name=(
                            f'{section}.{position}.{nested._primary}'
                        ),
                    )
                primary_keys.add(primary_key)
                if model in (models.User, models.Alias):
                    owner = routing_addresses.get(primary_key)
                    if owner is not None:
                        raise ValidationError(
                            f'Address {primary_key!r} is present in both '
                            f'{owner} and {section}.',
                            field_name=(
                                f'{section}.{position}.{nested._primary}'
                            ),
                        )
                    routing_addresses[primary_key] = section
                instance = nested.get_instance(item)
                if instance is not None:
                    # SQL bind canonicalization can make two spellings the
                    # same public key (notably IDNA U-labels/A-labels). Retain
                    # the existing row without assigning the alternate
                    # spelling back through a persisted primary-key setter.
                    item[nested._primary] = getattr(
                        instance,
                        nested._primary,
                    )
                    identities.add(sqlalchemy.inspect(instance).identity)
                    if (
                        model is models.Alias
                        and instance.scim_resource is not None
                        and instance.scim_resource.deleted_at is None
                    ):
                        self._validate_managed_alias_input(
                            nested,
                            instance,
                            item,
                            position,
                        )
                        managed_alias_items.append(item)
            retained[model] = identities
            if managed_alias_items:
                # The materialized Alias is a projection of normalized SCIM
                # graph state, not an import authority. An unchanged projection
                # establishes retention, then stays out of the generic loader
                # so concurrent pruning cannot reload stale destinations.
                items[:] = [
                    item for item in items
                    if item not in managed_alias_items
                ]

        obsolete = {
            model: [
                item for item in model.query.all()
                if sqlalchemy.inspect(item).identity not in identities
            ]
            for model, identities in retained.items()
        }

        scim_deleted_aliases = set()
        for alias in obsolete.get(models.Alias, []):
            if (
                alias.scim_resource is not None
                and alias.scim_resource.deleted_at is None
            ):
                models.tombstone_scim_resource(alias.scim_resource)
                # Match SCIM Group DELETE: persist the detached tombstone
                # before deleting its formerly managed Alias.
                models.db.session.flush()
                models.db.session.delete(alias)
                scim_deleted_aliases.add(alias)

        retained_users = retained.get(models.User, set())
        retained_aliases = retained.get(models.Alias, set())
        for domain in obsolete.get(models.Domain, []):
            has_retained_user = any(
                sqlalchemy.inspect(user).identity in retained_users
                for user in domain.users
            )
            has_retained_alias = any(
                sqlalchemy.inspect(alias).identity in retained_aliases
                for alias in domain.aliases
            )
            if has_retained_user or has_retained_alias:
                raise ValidationError(
                    f'Domain {domain.name} cannot be removed while retained '
                    'users or aliases reference it.',
                    field_name='domain',
                )

        for items in obsolete.values():
            for item in items:
                if item not in scim_deleted_aliases:
                    models.db.session.delete(item)
        models.db.session.flush()

        # Deleting a User can rematerialize retained Group projections from
        # inside the identity lifecycle hook. Settle those lifecycle-owned
        # writes before the ordinary section loaders issue their own flushes.
        dirty_managed_aliases = [
            alias for alias in models.db.session.dirty
            if (
                isinstance(alias, models.Alias)
                and alias.scim_resource is not None
                and alias.scim_resource.deleted_at is None
            )
        ]
        for alias in dirty_managed_aliases:
            models.permit_scim_managed_alias_edit(alias)
        if dirty_managed_aliases:
            models.db.session.flush()

    def _preflight_nested_identities(self, data):
        """Reject duplicate nested database identities before any mutation."""
        seen = {}
        dialect = models.db.session.get_bind().dialect
        for section, outer_field in self.fields.items():
            outer_items = data.get(section, [])
            if type(outer_items) is not list:
                continue
            outer_schema = outer_field.schema
            for outer_position, outer_item in enumerate(outer_items):
                if type(outer_item) is not dict:
                    continue
                for name, nested_field in outer_schema.load_fields.items():
                    if (
                        not isinstance(nested_field, fields.Nested)
                        or not nested_field.many
                        or name not in outer_item
                    ):
                        continue
                    nested_items = outer_item[name]
                    if type(nested_items) is not list:
                        raise ValidationError(
                            'Not a valid list.',
                            field_name=(
                                f'{section}.{outer_position}.{name}'
                            ),
                        )
                    nested_schema = nested_field.schema
                    primary = nested_schema._primary
                    model = nested_schema.opts.model
                    primary_column = (
                        model.__table__.primary_key.columns.values()[0]
                    )
                    bind_processor = primary_column.type.bind_processor(
                        dialect
                    )
                    model_seen = seen.setdefault(model, set())
                    for nested_position, nested_item in enumerate(
                        nested_items
                    ):
                        if type(nested_item) is not dict:
                            raise ValidationError(
                                'Not a valid mapping.',
                                field_name=(
                                    f'{section}.{outer_position}.{name}.'
                                    f'{nested_position}'
                                ),
                            )
                        if primary not in nested_item:
                            continue
                        value = nested_schema.load_fields[
                            primary
                        ].deserialize(nested_item[primary])
                        if bind_processor is not None:
                            value = bind_processor(value)
                        if value in model_seen:
                            raise ValidationError(
                                f'Duplicate {primary}: {value!r}.',
                                field_name=(
                                    f'{section}.{outer_position}.{name}.'
                                    f'{nested_position}.{primary}'
                                ),
                            )
                        model_seen.add(value)

    def _preflight_related_owners(self, data):
        """Reject duplicate ownership of one-to-many related identities."""
        dialect = models.db.session.get_bind().dialect
        for section, outer_field in self.fields.items():
            outer_items = data.get(section, [])
            if type(outer_items) is not list:
                continue
            outer_schema = outer_field.schema
            outer_model = outer_schema.opts.model
            for name, related_field in outer_schema.load_fields.items():
                if not isinstance(related_field, RelatedList):
                    continue
                relationship = outer_model.__mapper__.relationships.get(name)
                if (
                    relationship is None
                    or relationship.direction
                    is not sqlalchemy.orm.ONETOMANY
                ):
                    continue
                primary_columns = relationship.mapper.primary_key
                if len(primary_columns) != 1:
                    continue
                primary_column = primary_columns[0]
                bind_processor = primary_column.type.bind_processor(dialect)
                python_type = primary_column.type.python_type
                seen = set()
                for outer_position, outer_item in enumerate(outer_items):
                    if type(outer_item) is not dict or name not in outer_item:
                        continue
                    related_items = outer_item[name]
                    if type(related_items) is not list:
                        raise ValidationError(
                            'Not a valid list.',
                            field_name=(
                                f'{section}.{outer_position}.{name}'
                            ),
                        )
                    for related_position, raw_value in enumerate(
                        related_items
                    ):
                        path = (
                            f'{section}.{outer_position}.{name}.'
                            f'{related_position}'
                        )
                        try:
                            related = related_field.inner.deserialize(
                                raw_value
                            )
                            value = getattr(
                                related,
                                primary_column.key,
                            )
                            value = python_type(value)
                            if bind_processor is not None:
                                value = bind_processor(value)
                        except (
                            AttributeError,
                            TypeError,
                            ValueError,
                            ValidationError,
                        ) as exc:
                            raise ValidationError(
                                f'Invalid related identity: {raw_value!r}.',
                                field_name=path,
                            ) from exc
                        if value in seen:
                            raise ValidationError(
                                f'Duplicate related identity: {value!r}.',
                                field_name=path,
                            )
                        seen.add(value)

    @staticmethod
    def _validate_managed_alias_input(schema, alias, item, position):
        """Reject attempts to mutate a retained SCIM-owned Alias."""
        unknown = set(item) - set(schema.fields)
        if unknown:
            name = sorted(unknown)[0]
            raise ValidationError(
                'Unknown field.',
                field_name=f'alias.{position}.{name}',
            )

        prepared = schema._prepare_replacement_item( # pylint: disable=protected-access
            deepcopy(item)
        )
        for name, raw_value in prepared.items():
            field = schema.load_fields.get(name)
            if field is None:
                continue
            if name == schema._primary:
                continue
            value = field.deserialize(
                raw_value,
                attr=name,
                data=prepared,
            )
            current_raw = field.serialize(name, alias)
            current = (
                None
                if current_raw is missing
                else field.deserialize(
                    current_raw,
                    attr=name,
                    data={name: current_raw},
                )
            )
            if name == 'destination':
                value = sorted(set(value))
                current = sorted(set(current))
            if value != current:
                raise ValidationError(
                    f'SCIM-managed Group alias {alias.email} cannot be '
                    f'modified by config import; field {name!r} is '
                    'provider-owned.',
                    field_name=f'alias.{position}.{name}',
                )

    @post_load
    def _make_config(self, data, many, **kwargs): # pylint: disable=unused-argument
        """ update and return config object """
        config = self.context['config']
        for section in self.Meta.order:
            if section in data:
                config.update(data[section], section)

        return config

    domain = fields.Nested(DomainSchema, many=True)
    user = fields.Nested(UserSchema, many=True)
    alias = fields.Nested(AliasSchema, many=True)
    relay = fields.Nested(RelaySchema, many=True)
#    config = fields.Nested(ConfigSchema, many=True)
