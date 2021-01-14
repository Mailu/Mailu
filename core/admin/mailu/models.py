""" Mailu config storage model
"""

import re
import os
import smtplib
import json

from datetime import date
from email.mime import text

import flask_sqlalchemy
import sqlalchemy
import passlib
import idna
import dns

from flask import current_app as app
from sqlalchemy.ext import declarative
from sqlalchemy.inspection import inspect
from werkzeug.utils import cached_property

from . import dkim


db = flask_sqlalchemy.SQLAlchemy()


class IdnaDomain(db.TypeDecorator):
    """ Stores a Unicode string in it's IDNA representation (ASCII only)
    """

    impl = db.String(80)

    def process_bind_param(self, value, dialect):
        """ encode unicode domain name to punycode """
        return idna.encode(value).decode('ascii').lower()

    def process_result_value(self, value, dialect):
        """ decode punycode domain name to unicode """
        return idna.decode(value)

    python_type = str

class IdnaEmail(db.TypeDecorator):
    """ Stores a Unicode string in it's IDNA representation (ASCII only)
    """

    impl = db.String(255)

    def process_bind_param(self, value, dialect):
        """ encode unicode domain part of email address to punycode """
        try:
            localpart, domain_name = value.split('@')
            return '{0}@{1}'.format(
                localpart,
                idna.encode(domain_name).decode('ascii'),
            ).lower()
        except ValueError:
            pass

    def process_result_value(self, value, dialect):
        """ decode punycode domain part of email to unicode """
        localpart, domain_name = value.split('@')
        return '{0}@{1}'.format(
            localpart,
            idna.decode(domain_name),
        )

    python_type = str

class CommaSeparatedList(db.TypeDecorator):
    """ Stores a list as a comma-separated string, compatible with Postfix.
    """

    impl = db.String

    def process_bind_param(self, value, dialect):
        """ join list of items to comma separated string """
        if not isinstance(value, (list, tuple, set)):
            raise TypeError('Must be a list of strings')
        for item in value:
            if ',' in item:
                raise ValueError('Item must not contain a comma')
        return ','.join(sorted(value))

    def process_result_value(self, value, dialect):
        """ split comma separated string to list """
        return list(filter(bool, value.split(','))) if value else []

    python_type = list

class JSONEncoded(db.TypeDecorator):
    """ Represents an immutable structure as a json-encoded string.
    """

    impl = db.String

    def process_bind_param(self, value, dialect):
        """ encode data as json """
        return json.dumps(value) if value else None

    def process_result_value(self, value, dialect):
        """ decode json to data """
        return json.loads(value) if value else None

    python_type = str

class Base(db.Model):
    """ Base class for all models
    """

    __abstract__ = True

    metadata = sqlalchemy.schema.MetaData(
        naming_convention={
            'fk': '%(table_name)s_%(column_0_name)s_fkey',
            'pk': '%(table_name)s_pkey'
        }
    )

    created_at = db.Column(db.Date, nullable=False, default=date.today)
    updated_at = db.Column(db.Date, nullable=True, onupdate=date.today)
    comment = db.Column(db.String(255), nullable=True, default='')

    # @classmethod
    # def from_dict(cls, data, delete=False):

    #     changed = []

    #     pkey = cls._dict_pkey()

    #     # handle "primary key" only
    #     if not isinstance(data, dict):
    #         data = {pkey: data}

    #     # modify input data
    #     if hasattr(cls, '_dict_input'):
    #         try:
    #             cls._dict_input(data)
    #         except Exception as exc:
    #             raise ValueError(f'{exc}', cls, None, data) from exc

    #     # check for primary key (if not recursed)
    #     if not getattr(cls, '_dict_recurse', False):
    #         if not pkey in data:
    #             raise KeyError(f'primary key {cls.__table__}.{pkey} is missing', cls, pkey, data)

    #     # check data keys and values
    #     for key in list(data.keys()):

    #         # check key
    #         if not hasattr(cls, key) and not key in cls.__mapper__.relationships:
    #             raise KeyError(f'unknown key {cls.__table__}.{key}', cls, key, data)

    #         # check value type
    #         value = data[key]
    #         col = cls.__mapper__.columns.get(key)
    #         if col is not None:
    #             if not ((value is None and col.nullable) or (isinstance(value, col.type.python_type))):
    #                 raise TypeError(f'{cls.__table__}.{key} {value!r} has invalid type {type(value).__name__!r}', cls, key, data)
    #         else:
    #             rel = cls.__mapper__.relationships.get(key)
    #             if rel is None:
    #                 itype = getattr(cls, '_dict_types', {}).get(key)
    #                 if itype is not None:
    #                     if itype is False: # ignore value. TODO: emit warning?
    #                         del data[key]
    #                         continue
    #                     elif not isinstance(value, itype):
    #                         raise TypeError(f'{cls.__table__}.{key} {value!r} has invalid type {type(value).__name__!r}', cls, key, data)
    #                 else:
    #                     raise NotImplementedError(f'type not defined for {cls.__table__}.{key}')

    #         # handle relationships
    #         if key in cls.__mapper__.relationships:
    #             rel_model = cls.__mapper__.relationships[key].argument
    #             if not isinstance(rel_model, sqlalchemy.orm.Mapper):
    #                 add = rel_model.from_dict(value, delete)
    #                 assert len(add) == 1
    #                 rel_item, updated = add[0]
    #                 changed.append((rel_item, updated))
    #                 data[key] = rel_item

    #     # create item if necessary
    #     created = False
    #     item = cls.query.get(data[pkey]) if pkey in data else None
    #     if item is None:

    #         # check for mandatory keys
    #         missing = getattr(cls, '_dict_mandatory', set()) - set(data.keys())
    #         if missing:
    #             raise ValueError(f'mandatory key(s) {", ".join(sorted(missing))} for {cls.__table__} missing', cls, missing, data)

    #         # remove mapped relationships from data
    #         mapped = {}
    #         for key in list(data.keys()):
    #             if key in cls.__mapper__.relationships:
    #                 if isinstance(cls.__mapper__.relationships[key].argument, sqlalchemy.orm.Mapper):
    #                     mapped[key] = data[key]
    #                     del data[key]

    #         # create new item
    #         item = cls(**data)
    #         created = True

    #         # and update mapped relationships (below)
    #         data = mapped

    #     # update item
    #     updated = []
    #     for key, value in data.items():

    #         # skip primary key
    #         if key == pkey:
    #             continue

    #         if key in cls.__mapper__.relationships:
    #             # update relationship
    #             rel_model = cls.__mapper__.relationships[key].argument
    #             if isinstance(rel_model, sqlalchemy.orm.Mapper):
    #                 rel_model = rel_model.class_
    #                 # add (and create) referenced items
    #                 cur = getattr(item, key)
    #                 old = sorted(cur, key=id)
    #                 new = []
    #                 for rel_data in value:
    #                     # get or create related item
    #                     add = rel_model.from_dict(rel_data, delete)
    #                     assert len(add) == 1
    #                     rel_item, rel_updated = add[0]
    #                     changed.append((rel_item, rel_updated))
    #                     if rel_item not in cur:
    #                         cur.append(rel_item)
    #                     new.append(rel_item)

    #                 # delete referenced items missing in yaml
    #                 rel_pkey = rel_model._dict_pkey()
    #                 new_data = list([i.to_dict(True, True, None, True, [rel_pkey]) for i in new])
    #                 for rel_item in old:
    #                     if rel_item not in new:
    #                         # check if item with same data exists to stabilze import without primary key
    #                         rel_data = rel_item.to_dict(True, True, None, True, [rel_pkey])
    #                         try:
    #                             same_idx = new_data.index(rel_data)
    #                         except ValueError:
    #                             same = None
    #                         else:
    #                             same = new[same_idx]

    #                         if same is None:
    #                             # delete items missing in new
    #                             if delete:
    #                                 cur.remove(rel_item)
    #                             else:
    #                                 new.append(rel_item)
    #                         else:
    #                             # swap found item with same data with newly created item
    #                             new.append(rel_item)
    #                             new_data.append(rel_data)
    #                             new.remove(same)
    #                             del new_data[same_idx]
    #                             for i, (ch_item, _) in enumerate(changed):
    #                                 if ch_item is same:
    #                                     changed[i] = (rel_item, [])
    #                                     db.session.flush()
    #                                     db.session.delete(ch_item)
    #                                     break

    #                 # remember changes
    #                 new = sorted(new, key=id)
    #                 if new != old:
    #                     updated.append((key, old, new))

    #         else:
    #             # update key
    #             old = getattr(item, key)
    #             if isinstance(old, list):
    #                 # deduplicate list value
    #                 assert isinstance(value, list)
    #                 value = set(value)
    #                 old = set(old)
    #                 if not delete:
    #                     value = old | value
    #             if value != old:
    #                 updated.append((key, old, value))
    #                 setattr(item, key, value)

    #     changed.append((item, created if created else updated))

    #     return changed


# Many-to-many association table for domain managers
managers = db.Table('manager', Base.metadata,
    db.Column('domain_name', IdnaDomain, db.ForeignKey('domain.name')),
    db.Column('user_email', IdnaEmail, db.ForeignKey('user.email'))
)


class Config(Base):
    """ In-database configuration values
    """

    name = db.Column(db.String(255), primary_key=True, nullable=False)
    value = db.Column(JSONEncoded)


# TODO: use sqlalchemy.event.listen() on a store method of object?
@sqlalchemy.event.listens_for(db.session, 'after_commit')
def store_dkim_key(session):
    """ Store DKIM key on commit
    """

    for obj in session.identity_map.values():
        if isinstance(obj, Domain):
            if obj._dkim_key_changed:
                file_path = obj._dkim_file()
                if obj._dkim_key:
                    with open(file_path, 'wb') as handle:
                        handle.write(obj._dkim_key)
                elif os.path.exists(file_path):
                    os.unlink(file_path)

class Domain(Base):
    """ A DNS domain that has mail addresses associated to it.
    """

    __tablename__ = 'domain'

    name = db.Column(IdnaDomain, primary_key=True, nullable=False)
    managers = db.relationship('User', secondary=managers,
        backref=db.backref('manager_of'), lazy='dynamic')
    max_users = db.Column(db.Integer, nullable=False, default=-1)
    max_aliases = db.Column(db.Integer, nullable=False, default=-1)
    max_quota_bytes = db.Column(db.BigInteger, nullable=False, default=0)
    signup_enabled = db.Column(db.Boolean, nullable=False, default=False)

    _dkim_key = None
    _dkim_key_changed = False

    def _dkim_file(self):
        return app.config['DKIM_PATH'].format(
            domain=self.name, selector=app.config['DKIM_SELECTOR'])

    @property
    def dns_mx(self):
        hostname = app.config['HOSTNAMES'].split(',')[0]
        return f'{self.name}. 600 IN MX 10 {hostname}.'

    @property
    def dns_spf(self):
        hostname = app.config['HOSTNAMES'].split(',')[0]
        return f'{self.name}. 600 IN TXT "v=spf1 mx a:{hostname} ~all"'

    @property
    def dns_dkim(self):
        if os.path.exists(self._dkim_file()):
            selector = app.config['DKIM_SELECTOR']
            return (
                f'{selector}._domainkey.{self.name}. 600 IN TXT'
                f'"v=DKIM1; k=rsa; p={self.dkim_publickey}"'
            )

    @property
    def dns_dmarc(self):
        if os.path.exists(self._dkim_file()):
            domain = app.config['DOMAIN']
            rua = app.config['DMARC_RUA']
            rua = f' rua=mailto:{rua}@{domain};' if rua else ''
            ruf = app.config['DMARC_RUF']
            ruf = f' ruf=mailto:{ruf}@{domain};' if ruf else ''
            return f'_dmarc.{self.name}. 600 IN TXT "v=DMARC1; p=reject;{rua}{ruf} adkim=s; aspf=s"'

    @property
    def dkim_key(self):
        if self._dkim_key is None:
            file_path = self._dkim_file()
            if os.path.exists(file_path):
                with open(file_path, 'rb') as handle:
                    self._dkim_key = handle.read()
            else:
                self._dkim_key = b''
        return self._dkim_key if self._dkim_key else None

    @dkim_key.setter
    def dkim_key(self, value):
        old_key = self.dkim_key
        if value is None:
            value = b''
        self._dkim_key_changed = value != old_key
        self._dkim_key = value

    @property
    def dkim_publickey(self):
        dkim_key = self.dkim_key
        if dkim_key:
            return dkim.strip_key(dkim_key).decode('utf8')

    def generate_dkim_key(self):
        self.dkim_key = dkim.gen_key()

    def has_email(self, localpart):
        for email in self.users + self.aliases:
            if email.localpart == localpart:
                return True
        return False

    def check_mx(self):
        try:
            hostnames = app.config['HOSTNAMES'].split(',')
            return any(
                str(rset).split()[-1][:-1] in hostnames
                for rset in dns.resolver.query(self.name, 'MX')
            )
        except Exception:
            return False

    def __str__(self):
        return str(self.name)

    def __eq__(self, other):
        try:
            return self.name == other.name
        except AttributeError:
            return NotImplemented

    def __hash__(self):
        return hash(str(self.name))



class Alternative(Base):
    """ Alternative name for a served domain.
    The name "domain alias" was avoided to prevent some confusion.
    """

    __tablename__ = 'alternative'

    name = db.Column(IdnaDomain, primary_key=True, nullable=False)
    domain_name = db.Column(IdnaDomain, db.ForeignKey(Domain.name))
    domain = db.relationship(Domain,
        backref=db.backref('alternatives', cascade='all, delete-orphan'))

    def __str__(self):
        return str(self.name)


class Relay(Base):
    """ Relayed mail domain.
    The domain is either relayed publicly or through a specified SMTP host.
    """

    __tablename__ = 'relay'

    name = db.Column(IdnaDomain, primary_key=True, nullable=False)
    smtp = db.Column(db.String(80), nullable=True)

    def __str__(self):
        return str(self.name)


class Email(object):
    """ Abstraction for an email address (localpart and domain).
    """

    localpart = db.Column(db.String(80), nullable=False)

    @declarative.declared_attr
    def domain_name(self):
        return db.Column(IdnaDomain, db.ForeignKey(Domain.name),
            nullable=False, default=IdnaDomain)

    # This field is redundant with both localpart and domain name.
    # It is however very useful for quick lookups without joining tables,
    # especially when the mail server is reading the database.
    @declarative.declared_attr
    def email(self):
        updater = lambda context: '{0}@{1}'.format(
            context.current_parameters['localpart'],
            context.current_parameters['domain_name'],
        )
        return db.Column(IdnaEmail,
            primary_key=True, nullable=False,
            default=updater)

    def sendmail(self, subject, body):
        """ Send an email to the address.
        """
        from_address = '{0}@{1}'.format(
            app.config['POSTMASTER'],
            idna.encode(app.config['DOMAIN']).decode('ascii'),
        )
        with smtplib.SMTP(app.config['HOST_AUTHSMTP'], port=10025) as smtp:
            to_address = '{0}@{1}'.format(
                self.localpart,
                idna.encode(self.domain_name).decode('ascii'),
            )
            msg = text.MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = from_address
            msg['To'] = to_address
            smtp.sendmail(from_address, [to_address], msg.as_string())

    @classmethod
    def resolve_domain(cls, email):
        localpart, domain_name = email.split('@', 1) if '@' in email else (None, email)
        alternative = Alternative.query.get(domain_name)
        if alternative:
            domain_name = alternative.domain_name
        return (localpart, domain_name)

    @classmethod
    def resolve_destination(cls, localpart, domain_name, ignore_forward_keep=False):
        localpart_stripped = None
        stripped_alias = None

        if os.environ.get('RECIPIENT_DELIMITER') in localpart:
            localpart_stripped = localpart.rsplit(os.environ.get('RECIPIENT_DELIMITER'), 1)[0]

        user = User.query.get('{}@{}'.format(localpart, domain_name))
        if not user and localpart_stripped:
            user = User.query.get('{}@{}'.format(localpart_stripped, domain_name))
        if user:
            email = '{}@{}'.format(localpart, domain_name)

            if user.forward_enabled:
                destination = user.forward_destination
                if user.forward_keep or ignore_forward_keep:
                    destination.append(email)
            else:
                destination = [email]
            return destination

        pure_alias = Alias.resolve(localpart, domain_name)
        stripped_alias = Alias.resolve(localpart_stripped, domain_name)

        if pure_alias and not pure_alias.wildcard:
            return pure_alias.destination
        elif stripped_alias:
            return stripped_alias.destination
        elif pure_alias:
            return pure_alias.destination

    def __str__(self):
        return str(self.email)


class User(Base, Email):
    """ A user is an email address that has a password to access a mailbox.
    """

    __tablename__ = 'user'

    domain = db.relationship(Domain,
        backref=db.backref('users', cascade='all, delete-orphan'))
    password = db.Column(db.String(255), nullable=False)
    quota_bytes = db.Column(db.BigInteger, nullable=False, default=10**9)
    quota_bytes_used = db.Column(db.BigInteger, nullable=False, default=0)
    global_admin = db.Column(db.Boolean, nullable=False, default=False)
    enabled = db.Column(db.Boolean, nullable=False, default=True)

    # Features
    enable_imap = db.Column(db.Boolean, nullable=False, default=True)
    enable_pop = db.Column(db.Boolean, nullable=False, default=True)

    # Filters
    forward_enabled = db.Column(db.Boolean, nullable=False, default=False)
    forward_destination = db.Column(CommaSeparatedList, nullable=True, default=list)
    forward_keep = db.Column(db.Boolean, nullable=False, default=True)
    reply_enabled = db.Column(db.Boolean, nullable=False, default=False)
    reply_subject = db.Column(db.String(255), nullable=True, default=None)
    reply_body = db.Column(db.Text, nullable=True, default=None)
    reply_startdate = db.Column(db.Date, nullable=False,
        default=date(1900, 1, 1))
    reply_enddate = db.Column(db.Date, nullable=False,
        default=date(2999, 12, 31))

    # Settings
    displayed_name = db.Column(db.String(160), nullable=False, default='')
    spam_enabled = db.Column(db.Boolean, nullable=False, default=True)
    spam_threshold = db.Column(db.Integer, nullable=False, default=80)

    # Flask-login attributes
    is_authenticated = True
    is_active = True
    is_anonymous = False

    def get_id(self):
        return self.email

    @property
    def destination(self):
        if self.forward_enabled:
            result = list(self.forward_destination)
            if self.forward_keep:
                result.append(self.email)
            return ','.join(result)
        else:
            return self.email

    @property
    def reply_active(self):
        now = date.today()
        return (
            self.reply_enabled and
            self.reply_startdate < now and
            self.reply_enddate > now
        )

    scheme_dict = {'PBKDF2': 'pbkdf2_sha512',
                   'BLF-CRYPT': 'bcrypt',
                   'SHA512-CRYPT': 'sha512_crypt',
                   'SHA256-CRYPT': 'sha256_crypt',
                   'MD5-CRYPT': 'md5_crypt',
                   'CRYPT': 'des_crypt'}

    def get_password_context(self):
        return passlib.context.CryptContext(
            schemes=self.scheme_dict.values(),
            default=self.scheme_dict[app.config['PASSWORD_SCHEME']],
        )

    def check_password(self, password):
        context = self.get_password_context()
        reference = re.match('({[^}]+})?(.*)', self.password).group(2)
        result = context.verify(password, reference)
        if result and context.identify(reference) != context.default_scheme():
            self.set_password(password)
            db.session.add(self)
            db.session.commit()
        return result

    def set_password(self, password, hash_scheme=None, raw=False):
        """Set password for user with specified encryption scheme
        @password: plain text password to encrypt (if raw == True the hash itself)
        """
        if hash_scheme is None:
            hash_scheme = app.config['PASSWORD_SCHEME']
        # for the list of hash schemes see https://wiki2.dovecot.org/Authentication/PasswordSchemes
        if raw:
            self.password = '{'+hash_scheme+'}' + password
        else:
            self.password = '{'+hash_scheme+'}' + \
                self.get_password_context().encrypt(password, self.scheme_dict[hash_scheme])

    def get_managed_domains(self):
        if self.global_admin:
            return Domain.query.all()
        else:
            return self.manager_of

    def get_managed_emails(self, include_aliases=True):
        emails = []
        for domain in self.get_managed_domains():
            emails.extend(domain.users)
            if include_aliases:
                emails.extend(domain.aliases)
        return emails

    def send_welcome(self):
        if app.config['WELCOME']:
            self.sendmail(app.config['WELCOME_SUBJECT'],
                app.config['WELCOME_BODY'])

    @classmethod
    def get(cls, email):
        return cls.query.get(email)

    @classmethod
    def login(cls, email, password):
        user = cls.query.get(email)
        return user if (user and user.enabled and user.check_password(password)) else None


class Alias(Base, Email):
    """ An alias is an email address that redirects to some destination.
    """

    __tablename__ = 'alias'

    domain = db.relationship(Domain,
        backref=db.backref('aliases', cascade='all, delete-orphan'))
    wildcard = db.Column(db.Boolean, nullable=False, default=False)
    destination = db.Column(CommaSeparatedList, nullable=False, default=list)

    @classmethod
    def resolve(cls, localpart, domain_name):
        alias_preserve_case = cls.query.filter(
                sqlalchemy.and_(cls.domain_name == domain_name,
                    sqlalchemy.or_(
                        sqlalchemy.and_(
                            cls.wildcard is False,
                            cls.localpart == localpart
                        ), sqlalchemy.and_(
                            cls.wildcard is True,
                            sqlalchemy.bindparam('l', localpart).like(cls.localpart)
                        )
                    )
                )
            ).order_by(cls.wildcard, sqlalchemy.func.char_length(cls.localpart).desc()).first()

        localpart_lower = localpart.lower() if localpart else None
        alias_lower_case = cls.query.filter(
                sqlalchemy.and_(cls.domain_name == domain_name,
                    sqlalchemy.or_(
                        sqlalchemy.and_(
                            cls.wildcard is False,
                            sqlalchemy.func.lower(cls.localpart) == localpart_lower
                        ), sqlalchemy.and_(
                            cls.wildcard is True,
                            sqlalchemy.bindparam('l', localpart_lower).like(sqlalchemy.func.lower(cls.localpart))
                        )
                    )
                )
            ).order_by(cls.wildcard, sqlalchemy.func.char_length(sqlalchemy.func.lower(cls.localpart)).desc()).first()

        if alias_preserve_case and alias_lower_case:
            if alias_preserve_case.wildcard:
                return alias_lower_case
            else:
                return alias_preserve_case
        elif alias_preserve_case and not alias_lower_case:
            return alias_preserve_case
        elif alias_lower_case and not alias_preserve_case:
            return alias_lower_case
        else:
            return None

class Token(Base):
    """ A token is an application password for a given user.
    """

    __tablename__ = 'token'

    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(255), db.ForeignKey(User.email),
        nullable=False)
    user = db.relationship(User,
        backref=db.backref('tokens', cascade='all, delete-orphan'))
    password = db.Column(db.String(255), nullable=False)
    ip = db.Column(db.String(255))

    def check_password(self, password):
        return passlib.hash.sha256_crypt.verify(password, self.password)

    def set_password(self, password):
        self.password = passlib.hash.sha256_crypt.using(rounds=1000).hash(password)

    def __str__(self):
        return self.comment or self.ip


class Fetch(Base):
    """ A fetched account is a remote POP/IMAP account fetched into a local
    account.
    """

    __tablename__ = 'fetch'

    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(255), db.ForeignKey(User.email),
        nullable=False)
    user = db.relationship(User,
        backref=db.backref('fetches', cascade='all, delete-orphan'))
    protocol = db.Column(db.Enum('imap', 'pop3'), nullable=False)
    host = db.Column(db.String(255), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    tls = db.Column(db.Boolean, nullable=False, default=False)
    username = db.Column(db.String(255), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    keep = db.Column(db.Boolean, nullable=False, default=False)
    last_check = db.Column(db.DateTime, nullable=True)
    error = db.Column(db.String(1023), nullable=True)

    def __str__(self):
        return f'{self.protocol}{"s" if self.tls else ""}://{self.username}@{self.host}:{self.port}'


class MailuConfig:
    """ Class which joins whole Mailu config for dumping
        and loading
    """

    # TODO: add sqlalchemy session updating (.add & .del)
    class MailuCollection:
        """ Provides dict- and list-like access to all instances
            of a sqlalchemy model
        """

        def __init__(self, model : db.Model):
            self._model = model

        @cached_property
        def _items(self):
            return {
                inspect(item).identity: item
                for item in self._model.query.all()
            }

        def __len__(self):
            return len(self._items)

        def __iter__(self):
            return iter(self._items.values())

        def __getitem__(self, key):
            return self._items[key]

        def __setitem__(self, key, item):
            if not isinstance(item, self._model):
                raise TypeError(f'expected {self._model.name}')
            if key != inspect(item).identity:
                raise ValueError(f'item identity != key {key!r}')
            self._items[key] = item

        def __delitem__(self, key):
            del self._items[key]

        def append(self, item):
            """ list-like append """
            if not isinstance(item, self._model):
                raise TypeError(f'expected {self._model.name}')
            key = inspect(item).identity
            if key in self._items:
                raise ValueError(f'item {key!r} already present in collection')
            self._items[key] = item

        def extend(self, items):
            """ list-like extend """
            add = {}
            for item in items:
                if not isinstance(item, self._model):
                    raise TypeError(f'expected {self._model.name}')
                key = inspect(item).identity
                if key in self._items:
                    raise ValueError(f'item {key!r} already present in collection')
                add[key] = item
            self._items.update(add)

        def pop(self, *args):
            """ list-like (no args) and dict-like (1 or 2 args) pop """
            if args:
                if len(args) > 2:
                    raise TypeError(f'pop expected at most 2 arguments, got {len(args)}')
                return self._items.pop(*args)
            else:
                return self._items.popitem()[1]

        def popitem(self):
            """ dict-like popitem """
            return self._items.popitem()

        def remove(self, item):
            """ list-like remove """
            if not isinstance(item, self._model):
                raise TypeError(f'expected {self._model.name}')
            key = inspect(item).identity
            if not key in self._items:
                raise ValueError(f'item {key!r} not found in collection')
            del self._items[key]

        def clear(self):
            """ dict-like clear """
            while True:
                try:
                    self.pop()
                except IndexError:
                    break

        def update(self, items):
            """ dict-like update """
            for key, item in items:
                if not isinstance(item, self._model):
                    raise TypeError(f'expected {self._model.name}')
                if key != inspect(item).identity:
                    raise ValueError(f'item identity != key {key!r}')
                if key in self._items:
                    raise ValueError(f'item {key!r} already present in collection')

        def setdefault(self, key, item=None):
            """ dict-like setdefault """
            if key in self._items:
                return self._items[key]
            if item is None:
                return None
            if not isinstance(item, self._model):
                raise TypeError(f'expected {self._model.name}')
            if key != inspect(item).identity:
                raise ValueError(f'item identity != key {key!r}')
            self._items[key] = item
            return item

    domains = MailuCollection(Domain)
    relays = MailuCollection(Relay)
    users = MailuCollection(User)
    aliases = MailuCollection(Alias)
    config = MailuCollection(Config)
