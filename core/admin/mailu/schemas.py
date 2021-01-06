import marshmallow
import flask_marshmallow

from . import models


ma = flask_marshmallow.Marshmallow()


class BaseSchema(ma.SQLAlchemyAutoSchema):

    SKIP_IF = {
        'comment': {'', None}
    }

    @marshmallow.post_dump
    def remove_skip_values(self, data, many, **kwargs):
        print(repr(data), self.context)
        return {
            key: value for key, value in data.items()
            if key not in self.SKIP_IF or value not in self.SKIP_IF[key]
        }

class BaseMeta:
    exclude = ['created_at', 'updated_at']


class DomainSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = models.Domain

    # _dict_hide = {'users', 'managers', 'aliases'}
    # _dict_show = {'dkim_key'}
    # _dict_extra = {'dns':{'dkim_publickey', 'dns_mx', 'dns_spf', 'dns_dkim', 'dns_dmarc'}}
    # _dict_secret = {'dkim_key'}
    # _dict_types = {
    #     'dkim_key': (bytes, type(None)),
    #     'dkim_publickey': False,
    #     'dns_mx': False,
    #     'dns_spf': False,
    #     'dns_dkim': False,
    #     'dns_dmarc': False,
    # }
    # _dict_output = {'dkim_key': lambda key: key.decode('utf-8').strip().split('\n')[1:-1]}
    # @staticmethod
    # def _dict_input(data):
    #     if 'dkim_key' in data:
    #         key = data['dkim_key']
    #         if key is not None:
    #             if type(key) is list:
    #                 key = ''.join(key)
    #             if type(key) is str:
    #                 key = ''.join(key.strip().split()) # removes all whitespace
    #                 if key == 'generate':
    #                     data['dkim_key'] = dkim.gen_key()
    #                 elif key:
    #                     m = re.match('^-----BEGIN (RSA )?PRIVATE KEY-----', key)
    #                     if m is not None:
    #                         key = key[m.end():]
    #                     m = re.search('-----END (RSA )?PRIVATE KEY-----$', key)
    #                     if m is not None:
    #                         key = key[:m.start()]
    #                     key = '\n'.join(wrap(key, 64))
    #                     key = f'-----BEGIN PRIVATE KEY-----\n{key}\n-----END PRIVATE KEY-----\n'.encode('ascii')
    #                     try:
    #                         dkim.strip_key(key)
    #                     except:
    #                         raise ValueError('invalid dkim key')
    #                     else:
    #                       data['dkim_key'] = key
    #                 else:
    #                     data['dkim_key'] = None

    # name = db.Column(IdnaDomain, primary_key=True, nullable=False)
    # managers = db.relationship('User', secondary=managers,
    #     backref=db.backref('manager_of'), lazy='dynamic')
    # max_users = db.Column(db.Integer, nullable=False, default=-1)
    # max_aliases = db.Column(db.Integer, nullable=False, default=-1)
    # max_quota_bytes = db.Column(db.BigInteger(), nullable=False, default=0)
    # signup_enabled = db.Column(db.Boolean(), nullable=False, default=False)


class UserSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = models.User

    # _dict_hide = {'domain_name', 'domain', 'localpart', 'quota_bytes_used'}
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

    # domain = db.relationship(Domain,
    #     backref=db.backref('users', cascade='all, delete-orphan'))
    # password = db.Column(db.String(255), nullable=False)
    # quota_bytes = db.Column(db.BigInteger(), nullable=False, default=10**9)
    # quota_bytes_used = db.Column(db.BigInteger(), nullable=False, default=0)
    # global_admin = db.Column(db.Boolean(), nullable=False, default=False)
    # enabled = db.Column(db.Boolean(), nullable=False, default=True)

    # # Features
    # enable_imap = db.Column(db.Boolean(), nullable=False, default=True)
    # enable_pop = db.Column(db.Boolean(), nullable=False, default=True)

    # # Filters
    # forward_enabled = db.Column(db.Boolean(), nullable=False, default=False)
    # forward_destination = db.Column(CommaSeparatedList(), nullable=True, default=[])
    # forward_keep = db.Column(db.Boolean(), nullable=False, default=True)
    # reply_enabled = db.Column(db.Boolean(), nullable=False, default=False)
    # reply_subject = db.Column(db.String(255), nullable=True, default=None)
    # reply_body = db.Column(db.Text(), nullable=True, default=None)
    # reply_startdate = db.Column(db.Date, nullable=False,
    #     default=date(1900, 1, 1))
    # reply_enddate = db.Column(db.Date, nullable=False,
    #     default=date(2999, 12, 31))

    # # Settings
    # displayed_name = db.Column(db.String(160), nullable=False, default='')
    # spam_enabled = db.Column(db.Boolean(), nullable=False, default=True)
    # spam_threshold = db.Column(db.Integer(), nullable=False, default=80)

class AliasSchema(BaseSchema):
    class Meta(BaseMeta):
        model = models.Alias
        exclude = BaseMeta.exclude + ['localpart']
        # TODO look for good way to exclude secrets, unverbose and defaults

    # _dict_hide = {'domain_name', 'domain', 'localpart'}
    # @staticmethod
    # def _dict_input(data):
    #     Email._dict_input(data)
    #     # handle comma delimited string for backwards compability
    #     dst = data.get('destination')
    #     if type(dst) is str:
    #         data['destination'] = list([adr.strip() for adr in dst.split(',')])


class TokenSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
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


class FetchSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = models.Fetch

    # _dict_recurse = True
    # _dict_hide = {'user_email', 'user', 'last_check', 'error'}
    # _dict_mandatory = {'protocol', 'host', 'port', 'username', 'password'}
    # _dict_secret = {'password'}

    # id = db.Column(db.Integer(), primary_key=True)
    # user_email = db.Column(db.String(255), db.ForeignKey(User.email),
    #     nullable=False)
    # user = db.relationship(User,
    #     backref=db.backref('fetches', cascade='all, delete-orphan'))
    # protocol = db.Column(db.Enum('imap', 'pop3'), nullable=False)
    # host = db.Column(db.String(255), nullable=False)
    # port = db.Column(db.Integer(), nullable=False)
    # tls = db.Column(db.Boolean(), nullable=False, default=False)
    # username = db.Column(db.String(255), nullable=False)
    # password = db.Column(db.String(255), nullable=False)
    # keep = db.Column(db.Boolean(), nullable=False, default=False)
    # last_check = db.Column(db.DateTime, nullable=True)
    # error = db.Column(db.String(1023), nullable=True)


class ConfigSchema(ma.SQLAlchemySchema):
    class Meta:
        model = models.Config
#    created_at = ma.auto_field(dump_only=True)
#    updated_at = ma.auto_field(dump_only=True)
    comment = ma.auto_field()
    name = ma.auto_field(required=True)
    value = ma.auto_field(required=True)

class RelaySchema(BaseSchema):
    class Meta(BaseMeta):
        model = models.Relay
#    created_at = ma.auto_field(dump_only=True)
#    updated_at = ma.auto_field(dump_only=True)
#    comment = ma.auto_field()
#    name = ma.auto_field(required=True)
#    smtp = ma.auto_field(required=True)

schemas = {
    'domains': DomainSchema,
    'relays': RelaySchema,
    'users': UserSchema,
    'aliases': AliasSchema,
#    'config': ConfigSchema,
}
