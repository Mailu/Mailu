"""
Mailu marshmallow schema
"""

from textwrap import wrap

import re
import yaml

from marshmallow import post_dump, fields, Schema
from flask_marshmallow import Marshmallow
from OpenSSL import crypto

from . import models, dkim


ma = Marshmallow()
# TODO:
# how to mark keys as "required" while unserializing (in certain use cases/API)?
# - fields withoud default => required
# - fields which are the primary key => unchangeable when updating


### yaml render module ###

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
    def _update_dict(dict1, dict2):
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
        cls._update_dict(kwargs, cls._load_defaults)
        return yaml.load(*args, **kwargs)

    _dump_defaults = {
        'Dumper': SpacedDumper,
        'default_flow_style': False,
        'allow_unicode': True,
    }
    @classmethod
    def dumps(cls, *args, **kwargs):
        """ dump yaml data to string
        """
        cls._update_dict(kwargs, cls._dump_defaults)
        return yaml.dump(*args, **kwargs)


### field definitions ###

class LazyString(fields.String):
    """ Field that serializes a "false" value to the empty string
    """

    def _serialize(self, value, attr, obj, **kwargs):
        """ serialize None to the empty string
        """
        return value if value else ''


class CommaSeparatedList(fields.Raw):
    """ Field that deserializes a string containing comma-separated values to
        a list of strings
    """
    # TODO: implement this


class DkimKey(fields.String):
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
            raise TypeError(f'invalid type: {type(value).__name__!r}')

        # clean value (remove whitespace and header/footer)
        value = self._clean_re.sub('', value.strip())

        # map empty string/list to None
        if not value:
            return None

        # handle special value 'generate'
        elif value == 'generate':
            return dkim.gen_key()

        # wrap value into valid pem layout and check validity
        value = (
            '-----BEGIN PRIVATE KEY-----\n' +
            '\n'.join(wrap(value, 64)) +
            '\n-----END PRIVATE KEY-----\n'
        ).encode('ascii')
        try:
            crypto.load_privatekey(crypto.FILETYPE_PEM, value)
        except crypto.Error as exc:
            raise ValueError('invalid dkim key') from exc
        else:
            return value


### schema definitions ###

class BaseSchema(ma.SQLAlchemyAutoSchema):
    """ Marshmallow base schema with custom exclude logic
        and option to hide sqla defaults
    """

    class Meta:
        """ Schema config """
        model = None

    def __init__(self, *args, **kwargs):

        # get and remove config from kwargs
        context = kwargs.get('context', {})

        # compile excludes
        exclude = set(kwargs.get('exclude', []))

        # always exclude
        exclude.update({'created_at', 'updated_at'})

        # add include_by_context
        if context is not None:
            for ctx, what in getattr(self.Meta, 'include_by_context', {}).items():
                if not context.get(ctx):
                    exclude |= set(what)

        # update excludes
        kwargs['exclude'] = exclude

        # exclude_by_value
        self._exclude_by_value = getattr(self.Meta, 'exclude_by_value', {})

        # exclude default values
        if not context.get('full'):
            for column in self.Meta.model.__table__.columns:
                if column.name not in exclude:
                    self._exclude_by_value.setdefault(column.name, []).append(
                        None if column.default is None else column.default.arg
                    )

        # hide by context
        self._hide_by_context = set()
        if context is not None:
            for ctx, what in getattr(self.Meta, 'hide_by_context', {}).items():
                if not context.get(ctx):
                    self._hide_by_context |= set(what)

        # init SQLAlchemyAutoSchema
        super().__init__(*args, **kwargs)

    @post_dump
    def _remove_skip_values(self, data, many, **kwargs): # pylint: disable=unused-argument

        if not self._exclude_by_value and not self._hide_by_context:
            return data

        full = self.context.get('full')
        return {
            key: '<hidden>' if key in self._hide_by_context else value
            for key, value in data.items()
            if full or key not in self._exclude_by_value or value not in self._exclude_by_value[key]
        }

    # TODO: remove LazyString and fix model definition (comment should not be nullable)
    comment = LazyString()

class DomainSchema(BaseSchema):
    """ Marshmallow schema for Domain model """
    class Meta:
        """ Schema config """
        model = models.Domain
        include_relationships = True
        #include_fk = True
        exclude = ['users', 'managers', 'aliases']

        include_by_context = {
            'dns': {'dkim_publickey', 'dns_mx', 'dns_spf', 'dns_dkim', 'dns_dmarc'},
        }
        hide_by_context = {
            'secrets': {'dkim_key'},
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

    dkim_key = DkimKey()
    dkim_publickey = fields.String(dump_only=True)
    dns_mx = fields.String(dump_only=True)
    dns_spf = fields.String(dump_only=True)
    dns_dkim = fields.String(dump_only=True)
    dns_dmarc = fields.String(dump_only=True)

    # _dict_types = {
    #     'dkim_key': (bytes, type(None)),
    #     'dkim_publickey': False,
    #     'dns_mx': False,
    #     'dns_spf': False,
    #     'dns_dkim': False,
    #     'dns_dmarc': False,
    # }


class TokenSchema(BaseSchema):
    """ Marshmallow schema for Token model """
    class Meta:
        """ Schema config """
        model = models.Token

    # _dict_recurse = True
    # _dict_hide = {'user', 'user_email'}
    # _dict_mandatory = {'password'}

    # id = db.Column(db.Integer(), primary_key=True)
    # user_email = db.Column(db.String(255), db.ForeignKey(User.email),
    #     nullable=False)
    # user = db.relationship(User,
    #     backref=db.backref('tokens', cascade='all, delete-orphan'))
    # password = db.Column(db.String(255), nullable=False)
    # ip = db.Column(db.String(255))


class FetchSchema(BaseSchema):
    """ Marshmallow schema for Fetch model """
    class Meta:
        """ Schema config """
        model = models.Fetch
        include_by_context = {
            'full': {'last_check', 'error'},
        }
        hide_by_context = {
            'secrets': {'password'},
        }

# TODO: What about mandatory keys?
    # _dict_mandatory = {'protocol', 'host', 'port', 'username', 'password'}


class UserSchema(BaseSchema):
    """ Marshmallow schema for User model """
    class Meta:
        """ Schema config """
        model = models.User
        include_relationships = True
        exclude = ['localpart', 'domain', 'quota_bytes_used']

        exclude_by_value = {
            'forward_destination': [[]],
            'tokens': [[]],
            'reply_enddate': ['2999-12-31'],
            'reply_startdate': ['1900-01-01'],
        }

    tokens = fields.Nested(TokenSchema, many=True)
    fetches = fields.Nested(FetchSchema, many=True)

# TODO: deserialize password/password_hash! What about mandatory keys?
    # _dict_mandatory = {'localpart', 'domain', 'password'}
    # @classmethod
    # def _dict_input(cls, data):
    #     Email._dict_input(data)
    #     # handle password
    #     if 'password' in data:
    #         if 'password_hash' in data or 'hash_scheme' in data:
    #             raise ValueError('ambigous key password and password_hash/hash_scheme')
    #         # check (hashed) password
    #         password = data['password']
    #         if password.startswith('{') and '}' in password:
    #             scheme = password[1:password.index('}')]
    #             if scheme not in cls.scheme_dict:
    #                 raise ValueError(f'invalid password scheme {scheme!r}')
    #         else:
    #             raise ValueError(f'invalid hashed password {password!r}')
    #     elif 'password_hash' in data and 'hash_scheme' in data:
    #         if data['hash_scheme'] not in cls.scheme_dict:
    #             raise ValueError(f'invalid password scheme {scheme!r}')
    #         data['password'] = '{'+data['hash_scheme']+'}'+ data['password_hash']
    #         del data['hash_scheme']
    #         del data['password_hash']


class AliasSchema(BaseSchema):
    """ Marshmallow schema for Alias model """
    class Meta:
        """ Schema config """
        model = models.Alias
        exclude  = ['localpart']

        exclude_by_value = {
            'destination': [[]],
        }

# TODO: deserialize destination!
    # @staticmethod
    # def _dict_input(data):
    #     Email._dict_input(data)
    #     # handle comma delimited string for backwards compability
    #     dst = data.get('destination')
    #     if type(dst) is str:
    #         data['destination'] = list([adr.strip() for adr in dst.split(',')])


class ConfigSchema(BaseSchema):
    """ Marshmallow schema for Config model """
    class Meta:
        """ Schema config """
        model = models.Config


class RelaySchema(BaseSchema):
    """ Marshmallow schema for Relay model """
    class Meta:
        """ Schema config """
        model = models.Relay


class MailuSchema(Schema):
    """ Marshmallow schema for Mailu config """
    class Meta:
        """ Schema config """
        render_module = RenderYAML
    domains = fields.Nested(DomainSchema, many=True)
    relays = fields.Nested(RelaySchema, many=True)
    users = fields.Nested(UserSchema, many=True)
    aliases = fields.Nested(AliasSchema, many=True)
    config = fields.Nested(ConfigSchema, many=True)


### config class ###

class MailuConfig:
    """ Class which joins whole Mailu config for dumping
    """

    _models = {
        'domains': models.Domain,
        'relays': models.Relay,
        'users': models.User,
        'aliases': models.Alias,
#       'config': models.Config,
    }

    def __init__(self, sections):
        if sections:
            for section in sections:
                if section not in self._models:
                    raise ValueError(f'Unknown section: {section!r}')
            self._sections = set(sections)
        else:
            self._sections = set(self._models.keys())

    def __getattr__(self, section):
        if section in self._sections:
            return self._models[section].query.all()
        else:
            raise AttributeError
