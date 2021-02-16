""" Mailu marshmallow fields and schema
"""

from copy import deepcopy
from textwrap import wrap

import re
import json
import yaml

import sqlalchemy

from marshmallow import pre_load, post_load, post_dump, fields, Schema
from marshmallow.utils import ensure_text_type
from marshmallow.exceptions import ValidationError
from marshmallow_sqlalchemy import SQLAlchemyAutoSchemaOpts
from marshmallow_sqlalchemy.fields import RelatedList

from flask_marshmallow import Marshmallow

from OpenSSL import crypto

try:
    from pygments import highlight
    from pygments.token import Token
    from pygments.lexers import get_lexer_by_name
    from pygments.lexers.data import YamlLexer
    from pygments.formatters import get_formatter_by_name
except ModuleNotFoundError:
    canColorize = False
else:
    canColorize = True

from . import models, dkim


ma = Marshmallow()

# TODO: how and where to mark keys as "required" while deserializing in api?
# - when modifying, nothing is required (only the primary key, but this key is in the uri)
#   - the primary key from post data must not differ from the key in the uri
# - when creating all fields without default or auto-increment are required
# TODO: validate everything!


### class for hidden values ###

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

HIDDEN = _Hidden()


### map model to schema ###

_model2schema = {}

def get_schema(model=None):
    """ return schema class for model or instance of model """
    if model is None:
        return _model2schema.values()
    else:
        return _model2schema.get(model) or _model2schema.get(model.__class__)

def mapped(cls):
    """ register schema in model2schema map """
    _model2schema[cls.Meta.model] = cls
    return cls


### helper functions ###

def get_fieldspec(exc):
    """ walk traceback to extract spec of invalid field from marshmallow """
    path = []
    tbck = exc.__traceback__
    while tbck:
        if tbck.tb_frame.f_code.co_name == '_serialize':
            if 'attr' in tbck.tb_frame.f_locals:
                path.append(tbck.tb_frame.f_locals['attr'])
        elif tbck.tb_frame.f_code.co_name == '_init_fields':
            path = '.'.join(path)
            spec = ', '.join([f'{path}.{key}' for key in tbck.tb_frame.f_locals['invalid_fields']])
            return spec
        tbck = tbck.tb_next
    return None

def colorize(data, lexer='yaml', formatter='terminal', color=None, strip=False):
    """ add ANSI color to data """
    if color is None:
        # autodetect colorize
        color = canColorize
    if not color:
        # no color wanted
        return data
    if not canColorize:
        # want color, but not supported
        raise ValueError('Please install pygments to colorize output')

    scheme = {
        Token:                  ('',        ''),
        Token.Name.Tag:         ('cyan',    'brightcyan'),
        Token.Literal.Scalar:   ('green',   'green'),
        Token.Literal.String:   ('green',   'green'),
        Token.Keyword.Constant: ('magenta', 'brightmagenta'),
        Token.Literal.Number:   ('magenta', 'brightmagenta'),
        Token.Error:            ('red',     'brightred'),
        Token.Name:             ('red',     'brightred'),
        Token.Operator:         ('red',     'brightred'),
    }

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

    res = highlight(
        data,
        MyYamlLexer() if lexer == 'yaml' else get_lexer_by_name(lexer),
        get_formatter_by_name(formatter, colorscheme=scheme)
    )

    return res.rstrip('\n') if strip else res


### render modules ###

# allow yaml to represent hidden attributes
yaml.add_representer(
    _Hidden,
    lambda cls, data: cls.represent_data(str(data))
)

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
        """ add default kv's to kwargs if missing
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

class JSONEncoder(json.JSONEncoder):
    """ JSONEncoder supporting serialization of HIDDEN """
    def default(self, o):
        """ serialize HIDDEN """
        if isinstance(o, _Hidden):
            return str(o)
        return json.JSONEncoder.default(self, o)

class RenderJSON:
    """ Marshmallow JSON Render Module
    """

    @staticmethod
    def _augment(kwargs, defaults):
        """ add default kv's to kwargs if missing
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


### custom fields ###

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

    def _deserialize(self, value, attr, data, **kwargs):
        """ deserialize comma separated string to list of strings
        """

        # empty
        if not value:
            return []

        # split string
        if isinstance(value, str):
            return list([item.strip() for item in value.split(',') if item.strip()])
        else:
            return value


class DkimKeyField(fields.String):
    """ Serialize a dkim key to a list of strings (lines) and
        Deserialize a string or list of strings to a valid dkim key
    """

    default_error_messages = {
        "invalid": "Not a valid string or list.",
        "invalid_utf8": "Not a valid utf-8 string or list.",
    }

    _clean_re = re.compile(
        r'(^-----BEGIN (RSA )?PRIVATE KEY-----|-----END (RSA )?PRIVATE KEY-----$|\s+)',
        flags=re.UNICODE
    )

    def _serialize(self, value, attr, obj, **kwargs):
        """ serialize dkim key to a list of strings (lines)
        """

        # map empty string and None to None
        if not value:
            return None

        # return list of key lines without header/footer
        return value.decode('utf-8').strip().split('\n')[1:-1]

    def _deserialize(self, value, attr, data, **kwargs):
        """ deserialize a string or list of strings to dkim key data
            with verification
        """

        # convert list to str
        if isinstance(value, list):
            try:
                value = ''.join([ensure_text_type(item) for item in value])
            except UnicodeDecodeError as exc:
                raise self.make_error("invalid_utf8") from exc

        # only text is allowed
        else:
            if not isinstance(value, (str, bytes)):
                raise self.make_error("invalid")
            try:
                value = ensure_text_type(value)
            except UnicodeDecodeError as exc:
                raise self.make_error("invalid_utf8") from exc

        # clean value (remove whitespace and header/footer)
        value = self._clean_re.sub('', value.strip())

        # map empty string/list to None
        if not value:
            return None

        # handle special value 'generate'
        elif value == 'generate':
            return dkim.gen_key()

        # remember some keydata for error message
        keydata = f'{value[:25]}...{value[-10:]}' if len(value) > 40 else value

        # wrap value into valid pem layout and check validity
        value = (
            '-----BEGIN PRIVATE KEY-----\n' +
            '\n'.join(wrap(value, 64)) +
            '\n-----END PRIVATE KEY-----\n'
        ).encode('ascii')
        try:
            crypto.load_privatekey(crypto.FILETYPE_PEM, value)
        except crypto.Error as exc:
            raise ValidationError(f'invalid dkim key {keydata!r}') from exc
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

class BaseOpts(SQLAlchemyAutoSchemaOpts):
    """ Option class with sqla session
    """
    def __init__(self, meta, ordered=False):
        if not hasattr(meta, 'sqla_session'):
            meta.sqla_session = models.db.session
        if not hasattr(meta, 'sibling'):
            meta.sibling = False
        super(BaseOpts, self).__init__(meta, ordered=ordered)

class BaseSchema(ma.SQLAlchemyAutoSchema):
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

        # get context
        context = kwargs.get('context', {})
        flags = {key for key, value in context.items() if value is True}

        # compile excludes
        exclude = set(kwargs.get('exclude', []))

        # always exclude
        exclude.update({'created_at', 'updated_at'})

        # add include_by_context
        if context is not None:
            for need, what in getattr(self.Meta, 'include_by_context', {}).items():
                if not flags & set(need):
                    exclude |= set(what)

        # update excludes
        kwargs['exclude'] = exclude

        # init SQLAlchemyAutoSchema
        super().__init__(*args, **kwargs)

        # exclude_by_value
        self._exclude_by_value = getattr(self.Meta, 'exclude_by_value', {})

        # exclude default values
        if not context.get('full'):
            for column in self.opts.model.__table__.columns:
                if column.name not in exclude:
                    self._exclude_by_value.setdefault(column.name, []).append(
                        None if column.default is None else column.default.arg
                    )

        # hide by context
        self._hide_by_context = set()
        if context is not None:
            for need, what in getattr(self.Meta, 'hide_by_context', {}).items():
                if not flags & set(need):
                    self._hide_by_context |= set(what)

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

        # order dump_fields
        for field in order:
            if field in self.dump_fields:
                self.dump_fields[field] = self.dump_fields.pop(field)

        # move pre_load hook "_track_import" to the front
        hooks = self._hooks[('pre_load', False)]
        hooks.remove('_track_import')
        hooks.insert(0, '_track_import')
        # move pre_load hook "_add_instance" to the end
        hooks.remove('_add_required')
        hooks.append('_add_required')

        # move post_load hook "_add_instance" to the end
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

    def _call_and_store(self, *args, **kwargs):
        """ track curent parent field for pruning """
        self.context['parent_field'] = kwargs['field_name']
        return super()._call_and_store(*args, **kwargs)

    # this is only needed to work around the declared attr "email" primary key in model
    def get_instance(self, data):
        """ lookup item by defined primary key instead of key(s) from model """
        if self.transient:
            return None
        if keys := getattr(self.Meta, 'primary_keys', None):
            filters = {key: data.get(key) for key in keys}
            if None not in filters.values():
                return self.session.query(self.opts.model).filter_by(**filters).first()
        return super().get_instance(data)

    @pre_load(pass_many=True)
    def _patch_input(self, items, many, **kwargs): # pylint: disable=unused-argument
        """ - flush sqla session before serializing a section when requested
              (make sure all objects that could be referred to later are created)
            - when in update mode: patch input data before deserialization
              - handle "prune" and "delete" items
              - replace values in keys starting with '-' with default
        """

        # flush sqla session
        if not self.Meta.sibling:
            self.opts.sqla_session.flush()

        # stop early when not updating
        if not self.context.get('update'):
            return items

        # patch "delete", "prune" and "default"
        want_prune = []
        def patch(count, data, prune):

            # don't allow __delete__ coming from input
            if '__delete__' in data:
                raise ValidationError('Unknown field.', f'{count}.__delete__')

            # handle "prune list" and "delete item" (-pkey: none and -pkey: id)
            for key in data:
                if key.startswith('-'):
                    if key[1:] == self._primary:
                        # delete or prune
                        if data[key] is None:
                            # prune
                            prune.append(True)
                            return None
                        # mark item for deletion
                        return {key[1:]: data[key], '__delete__': True}

            # handle "set to default value" (-key: none)
            def set_default(key, value):
                if not key.startswith('-'):
                    return (key, value)
                key = key[1:]
                if not key in self.opts.model.__table__.columns:
                    return (key, None)
                if value is not None:
                    raise ValidationError(
                        'When resetting to default value must be null.',
                        f'{count}.{key}'
                    )
                value = self.opts.model.__table__.columns[key].default
                if value is None:
                    raise ValidationError(
                        'Field has no default value.',
                        f'{count}.{key}'
                    )
                return (key, value.arg)

            return dict([set_default(key, value) for key, value in data.items()])

        # convert items to "delete" and filter "prune" item
        items = [
            item for item in [
                patch(count, item, want_prune) for count, item in enumerate(items)
            ] if item
        ]

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
            existing = {item[self._primary] for item in items if self._primary in item}
            for item in getattr(self.context['parent'], self.context['parent_field']):
                key = getattr(item, self._primary)
                if key not in existing:
                    if add_items:
                        items.append({self._primary: key})
                    else:
                        items.append({self._primary: key, '__delete__': True})

        return items

    @pre_load
    def _track_import(self, data, many, **kwargs): # pylint: disable=unused-argument
        """ call callback function to track import
        """
        # callback
        if callback := self.context.get('callback'):
            callback(self, data)

        return data

    @pre_load
    def _add_required(self, data, many, **kwargs): # pylint: disable=unused-argument
        """ when updating:
            allow modification of existing items having required attributes
            by loading existing value from db
        """

        if not self.opts.load_instance or not self.context.get('update'):
            return data

        # stabilize import of auto-increment primary keys (not required),
        # by matching import data to existing items and setting primary key
        if not self._primary in data:
            for item in getattr(self.context['parent'], self.context['parent_field']):
                existing = self.dump(item, many=False)
                this = existing.pop(self._primary)
                if data == existing:
                    instance = item
                    data[self._primary] = this
                    break

        # try to load instance
        instance = self.instance or self.get_instance(data)
        if instance is None:

            if '__delete__' in data:
                # deletion of non-existent item requested
                raise ValidationError(
                    f'item to delete not found: {data[self._primary]!r}',
                    field_name=f'?.{self._primary}',
                )

        else:

            if self.context.get('update'):
                # remember instance as parent for pruning siblings
                if not self.Meta.sibling:
                    self.context['parent'] = instance
                # delete instance when marked
                if '__delete__' in data:
                    self.opts.sqla_session.delete(instance)
                # delete item from lists or prune lists
                # currently: domain.alternatives, user.forward_destination,
                # user.manager_of, aliases.destination
                for key, value in data.items():
                    if not isinstance(self.fields[key], fields.Nested) and isinstance(value, list):
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
                                        f'item to delete not found: {item[1:]!r}',
                                        field_name=f'?.{key}',
                                    ) from exc
                        # deduplicate and sort list
                        data[key] = sorted(new_value)
                        # log backref modification not catched by hook
                        if isinstance(self.fields[key], RelatedList):
                            if callback := self.context.get('callback'):
                                callback(self, instance, {
                                    'key': key,
                                    'target': str(instance),
                                    'before': [str(v) for v in getattr(instance, key)],
                                    'after': data[key],
                                })



            # add attributes required for validation from db
            # TODO: this will cause validation errors if value from database does not validate
            # but there should not be an invalid value in the database
            for attr_name, field_obj in self.load_fields.items():
                if field_obj.required and attr_name not in data:
                    data[attr_name] = getattr(instance, attr_name)

        return data

    @post_load(pass_original=True)
    def _add_instance(self, item, original, many, **kwargs): # pylint: disable=unused-argument
        """ add new instances to sqla session """

        if item in self.opts.sqla_session:
            # item was modified
            if 'hash_password' in original:
                # stabilize import of passwords to be hashed,
                # by not re-hashing an unchanged password
                if attr := getattr(sqlalchemy.inspect(item).attrs, 'password', None):
                    if attr.history.has_changes() and attr.history.deleted:
                        try:
                            # reset password hash, if password was not changed
                            inst = type(item)(password=attr.history.deleted[-1])
                            if inst.check_password(original['password']):
                                item.password = inst.password
                        except ValueError:
                            # hash in db is invalid
                            pass
                        else:
                            del inst
        else:
            # new item
            self.opts.sqla_session.add(item)
        return item

    @post_dump
    def _hide_values(self, data, many, **kwargs): # pylint: disable=unused-argument
        """ hide secrets and order output """

        # stop early when not excluding/hiding
        if not self._exclude_by_value and not self._hide_by_context:
            return data

        # exclude or hide values
        full = self.context.get('full')
        return type(data)([
            (key, HIDDEN if key in self._hide_by_context else value)
            for key, value in data.items()
            if full or key not in self._exclude_by_value or value not in self._exclude_by_value[key]
        ])

    # this field is used to mark items for deletion
    mark_delete = fields.Boolean(data_key='__delete__', load_only=True)

    # TODO: remove LazyStringField (when model was changed - IMHO comment should not be nullable)
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
    hash_password = fields.Boolean(load_only=True, missing=False)


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
        exclude = ['_email', 'domain', 'localpart', 'domain_name', 'quota_bytes_used']

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
    hash_password = fields.Boolean(load_only=True, missing=False)


@mapped
class AliasSchema(BaseSchema):
    """ Marshmallow schema for Alias model """
    class Meta:
        """ Schema config """
        model = models.Alias
        load_instance = True
        exclude = ['_email', 'domain', 'localpart', 'domain_name']

        primary_keys = ['email']
        exclude_by_value = {
            'destination': [[]],
        }

    email = fields.String(required=True)
    destination = CommaSeparatedListField()


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


class MailuSchema(Schema):
    """ Marshmallow schema for complete Mailu config """
    class Meta:
        """ Schema config """
        render_module = RenderYAML

        order = ['domain', 'user', 'alias', 'relay'] # 'config'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # order dump_fields
        for field in self.Meta.order:
            if field in self.dump_fields:
                self.dump_fields[field] = self.dump_fields.pop(field)

    def _call_and_store(self, *args, **kwargs):
        """ track current parent and field for pruning """
        self.context.update({
            'parent': self.context.get('config'),
            'parent_field': kwargs['field_name'],
        })
        return super()._call_and_store(*args, **kwargs)

    @pre_load
    def _clear_config(self, data, many, **kwargs): # pylint: disable=unused-argument
        """ create config object in context if missing
            and clear it if requested
        """
        if 'config' not in self.context:
            self.context['config'] = models.MailuConfig()
        if self.context.get('clear'):
            self.context['config'].clear(
                models = {field.nested.opts.model for field in self.fields.values()}
            )
        return data

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
