""" Mailu marshmallow fields and schema
"""

import re

from collections import OrderedDict
from textwrap import wrap

import yaml

from marshmallow import pre_load, post_load, post_dump, fields, Schema
from marshmallow.exceptions import ValidationError
from marshmallow_sqlalchemy import SQLAlchemyAutoSchemaOpts
from flask_marshmallow import Marshmallow
from OpenSSL import crypto

from . import models, dkim


ma = Marshmallow()

# TODO: how and where to mark keys as "required" while unserializing (on commandline, in api)?
# - fields without default => required
# - fields which are the primary key => unchangeable when updating


### yaml render module ###

# allow yaml module to dump OrderedDict
yaml.add_representer(
    OrderedDict,
    lambda cls, data: cls.represent_mapping('tag:yaml.org,2002:map', data.items())
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
    def _update_items(dict1, dict2):
        """ sets missing keys in dict1 to values of dict2
        """
        for key, value in dict2.items():
            if key not in dict1:
                dict1[key] = value

    _load_defaults = {}
    @classmethod
    def loads(cls, *args, **kwargs):
        """ load yaml data from string
        """
        cls._update_items(kwargs, cls._load_defaults)
        return yaml.safe_load(*args, **kwargs)

    _dump_defaults = {
        'Dumper': SpacedDumper,
        'default_flow_style': False,
        'allow_unicode': True,
        'sort_keys': False,
    }
    @classmethod
    def dumps(cls, *args, **kwargs):
        """ dump yaml data to string
        """
        cls._update_items(kwargs, cls._dump_defaults)
        return yaml.dump(*args, **kwargs)


### functions ###

def handle_email(data):
    """ merge separate localpart and domain to email
    """

    localpart = 'localpart' in data
    domain = 'domain' in data

    if 'email' in data:
        if localpart or domain:
            raise ValidationError('duplicate email and localpart/domain')
    elif localpart and domain:
        data['email'] = f'{data["localpart"]}@{data["domain"]}'
    elif localpart or domain:
        raise ValidationError('incomplete localpart/domain')

    return data


### field definitions ###

class LazyStringField(fields.String):
    """ Field that serializes a "false" value to the empty string
    """

    def _serialize(self, value, attr, obj, **kwargs):
        """ serialize None to the empty string
        """
        return value if value else ''


class CommaSeparatedListField(fields.Raw):
    """ Field that deserializes a string containing comma-separated values to
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
    """ Field that serializes a dkim key to a list of strings (lines) and
        deserializes a string or list of strings.
    """

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
            value = ''.join(value)

        # only strings are allowed
        if not isinstance(value, str):
            raise ValidationError(f'invalid type {type(value).__name__!r}')

        # clean value (remove whitespace and header/footer)
        value = self._clean_re.sub('', value.strip())

        # map empty string/list to None
        if not value:
            return None

        # handle special value 'generate'
        elif value == 'generate':
            return dkim.gen_key()

        # remember some keydata for error message
        keydata = value
        if len(keydata) > 40:
            keydata = keydata[:25] + '...' + keydata[-10:]

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


### base definitions ###

class BaseOpts(SQLAlchemyAutoSchemaOpts):
    """ Option class with sqla session
    """
    def __init__(self, meta, ordered=False):
        if not hasattr(meta, 'sqla_session'):
            meta.sqla_session = models.db.session
        if not hasattr(meta, 'ordered'):
            meta.ordered = True
        super(BaseOpts, self).__init__(meta, ordered=ordered)

class BaseSchema(ma.SQLAlchemyAutoSchema):
    """ Marshmallow base schema with custom exclude logic
        and option to hide sqla defaults
    """

    OPTIONS_CLASS = BaseOpts

    class Meta:
        """ Schema config """

    def __init__(self, *args, **kwargs):

        # context?
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

        # exclude_by_value
        self._exclude_by_value = getattr(self.Meta, 'exclude_by_value', {})

        # exclude default values
        if not context.get('full'):
            for column in getattr(self.Meta, 'model').__table__.columns:
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

        # init SQLAlchemyAutoSchema
        super().__init__(*args, **kwargs)

        # init order
        if hasattr(self.Meta, 'order'):
            # use user-defined order
            self._order = list(reversed(getattr(self.Meta, 'order')))
        else:
            # default order is: primary_key + other keys alphabetically
            self._order = list(sorted(self.fields.keys()))
            primary = self.opts.model.__table__.primary_key.columns.values()[0].name
            self._order.remove(primary)
            self._order.reverse()
            self._order.append(primary)

    @pre_load
    def _track_import(self, data, many, **kwargs): # pylint: disable=unused-argument
        call = self.context.get('callback')
        if call is not None:
            call(self=self, data=data, many=many, **kwargs)
        return data

    @post_dump
    def _hide_and_order(self, data, many, **kwargs): # pylint: disable=unused-argument

        # order output
        for key in self._order:
            try:
                data.move_to_end(key, False)
            except KeyError:
                pass

        # stop early when not excluding/hiding
        if not self._exclude_by_value and not self._hide_by_context:
            return data

        # exclude items or hide values
        full = self.context.get('full')
        return type(data)([
            (key, '<hidden>' if key in self._hide_by_context else value)
            for key, value in data.items()
            if full or key not in self._exclude_by_value or value not in self._exclude_by_value[key]
        ])

    # TODO: remove LazyStringField and change model (IMHO comment should not be nullable)
    comment = LazyStringField()


### schema definitions ###

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


class TokenSchema(BaseSchema):
    """ Marshmallow schema for Token model """
    class Meta:
        """ Schema config """
        model = models.Token
        load_instance = True


class FetchSchema(BaseSchema):
    """ Marshmallow schema for Fetch model """
    class Meta:
        """ Schema config """
        model = models.Fetch
        load_instance = True
        include_by_context = {
            ('full', 'import'): {'last_check', 'error'},
        }
        hide_by_context = {
            ('secrets',): {'password'},
        }


class UserSchema(BaseSchema):
    """ Marshmallow schema for User model """
    class Meta:
        """ Schema config """
        model = models.User
        load_instance = True
        include_relationships = True
        exclude = ['localpart', 'domain', 'quota_bytes_used']

        exclude_by_value = {
            'forward_destination': [[]],
            'tokens': [[]],
            'fetches': [[]],
            'manager_of': [[]],
            'reply_enddate': ['2999-12-31'],
            'reply_startdate': ['1900-01-01'],
        }

    @pre_load
    def _handle_email_and_password(self, data, many, **kwargs): # pylint: disable=unused-argument
        data = handle_email(data)
        if 'password' in data:
            if 'password_hash' in data or 'hash_scheme' in data:
                raise ValidationError('ambigous key password and password_hash/hash_scheme')
            # check (hashed) password
            password = data['password']
            if password.startswith('{') and '}' in password:
                scheme = password[1:password.index('}')]
                if scheme not in self.Meta.model.scheme_dict:
                    raise ValidationError(f'invalid password scheme {scheme!r}')
            else:
                raise ValidationError(f'invalid hashed password {password!r}')
        elif 'password_hash' in data and 'hash_scheme' in data:
            if data['hash_scheme'] not in self.Meta.model.scheme_dict:
                raise ValidationError(f'invalid password scheme {scheme!r}')
            data['password'] = f'{{{data["hash_scheme"]}}}{data["password_hash"]}'
            del data['hash_scheme']
            del data['password_hash']
        return data

    # TODO: verify password (should this be done in model?)
    # scheme, hashed = re.match('^(?:{([^}]+)})?(.*)$', self.password).groups()
    # if not scheme...
    # ctx = passlib.context.CryptContext(schemes=[scheme], default=scheme)
    # try:
    # ctx.verify('', hashed)
    # =>? ValueError: hash could not be identified

    tokens = fields.Nested(TokenSchema, many=True)
    fetches = fields.Nested(FetchSchema, many=True)


class AliasSchema(BaseSchema):
    """ Marshmallow schema for Alias model """
    class Meta:
        """ Schema config """
        model = models.Alias
        load_instance = True
        exclude  = ['localpart']

        exclude_by_value = {
            'destination': [[]],
        }

    @pre_load
    def _handle_email(self, data, many, **kwargs): # pylint: disable=unused-argument
        return handle_email(data)

    destination = CommaSeparatedListField()


class ConfigSchema(BaseSchema):
    """ Marshmallow schema for Config model """
    class Meta:
        """ Schema config """
        model = models.Config
        load_instance = True


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
        ordered = True
        order = ['config', 'domains', 'users', 'aliases', 'relays']

    @post_dump(pass_many=True)
    def _order(self, data : OrderedDict, many : bool, **kwargs): # pylint: disable=unused-argument
        for key in reversed(self.Meta.order):
            try:
                data.move_to_end(key, False)
            except KeyError:
                pass
        return data

    config = fields.Nested(ConfigSchema, many=True)
    domains = fields.Nested(DomainSchema, many=True)
    users = fields.Nested(UserSchema, many=True)
    aliases = fields.Nested(AliasSchema, many=True)
    relays = fields.Nested(RelaySchema, many=True)
