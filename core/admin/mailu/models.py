from mailu import dkim

from sqlalchemy.ext import declarative
from passlib import context, hash
from datetime import datetime, date
from email.mime import text
from flask import current_app as app
from textwrap import wrap

import flask_sqlalchemy
import sqlalchemy
import re
import time
import os
import glob
import smtplib
import idna
import dns
import json
import itertools


db = flask_sqlalchemy.SQLAlchemy()


class IdnaDomain(db.TypeDecorator):
    """ Stores a Unicode string in it's IDNA representation (ASCII only)
    """

    impl = db.String(80)

    def process_bind_param(self, value, dialect):
        return idna.encode(value).decode("ascii").lower()

    def process_result_value(self, value, dialect):
        return idna.decode(value)

    python_type = str

class IdnaEmail(db.TypeDecorator):
    """ Stores a Unicode string in it's IDNA representation (ASCII only)
    """

    impl = db.String(255)

    def process_bind_param(self, value, dialect):
        try:
            localpart, domain_name = value.split('@')
            return "{0}@{1}".format(
                localpart,
                idna.encode(domain_name).decode('ascii'),
            ).lower()
        except ValueError:
            pass

    def process_result_value(self, value, dialect):
        localpart, domain_name = value.split('@')
        return "{0}@{1}".format(
            localpart,
            idna.decode(domain_name),
        )

    python_type = str

class CommaSeparatedList(db.TypeDecorator):
    """ Stores a list as a comma-separated string, compatible with Postfix.
    """

    impl = db.String

    def process_bind_param(self, value, dialect):
        if type(value) is not list:
            raise TypeError("Should be a list")
        for item in value:
            if "," in item:
                raise ValueError("Item must not contain a comma")
        return ",".join(value)

    def process_result_value(self, value, dialect):
        return list(filter(bool, value.split(","))) if value else []

    python_type = list

class JSONEncoded(db.TypeDecorator):
    """ Represents an immutable structure as a json-encoded string.
    """

    impl = db.String

    def process_bind_param(self, value, dialect):
        return json.dumps(value) if value else None

    def process_result_value(self, value, dialect):
        return json.loads(value) if value else None

    python_type = str

class Base(db.Model):
    """ Base class for all models
    """

    __abstract__ = True

    metadata = sqlalchemy.schema.MetaData(
        naming_convention={
            "fk": "%(table_name)s_%(column_0_name)s_fkey",
            "pk": "%(table_name)s_pkey"
        }
    )

    created_at = db.Column(db.Date, nullable=False, default=date.today)
    updated_at = db.Column(db.Date, nullable=True, onupdate=date.today)
    comment = db.Column(db.String(255), nullable=True)

    @classmethod
    def _dict_pkey(model):
        return model.__mapper__.primary_key[0].name

    def _dict_pval(self):
        return getattr(self, self._dict_pkey())

    def to_dict(self, full=False, include_secrets=False, recursed=False, hide=None):
        """ Return a dictionary representation of this model.
        """

        if recursed and not getattr(self, '_dict_recurse', False):
            return str(self)

        hide = set(hide or []) | {'created_at', 'updated_at'}
        if hasattr(self, '_dict_hide'):
            hide |= self._dict_hide

        secret = set()
        if not include_secrets and hasattr(self, '_dict_secret'):
            secret |= self._dict_secret

        convert = getattr(self, '_dict_output', {})

        res = {}

        for key in itertools.chain(self.__table__.columns.keys(), getattr(self, '_dict_show', [])):
            if key in hide:
                continue
            if key in self.__table__.columns:
                default = self.__table__.columns[key].default
                if isinstance(default, sqlalchemy.sql.schema.ColumnDefault):
                    default = default.arg
            else:
                default = None
            value = getattr(self, key)
            if full or ((default or value) and value != default):
                if key in secret:
                    value = '<hidden>'
                elif value is not None and key in convert:
                    value = convert[key](value)
                res[key] = value

        for key in self.__mapper__.relationships.keys():
            if key in hide:
                continue
            if self.__mapper__.relationships[key].uselist:
                items = getattr(self, key)
                if self.__mapper__.relationships[key].query_class is not None:
                    if hasattr(items, 'all'):
                        items = items.all()
                if full or len(items):
                    if key in secret:
                        res[key] = '<hidden>'
                    else:
                        res[key] = [item.to_dict(full, include_secrets, True) for item in items]
            else:
                value = getattr(self, key)
                if full or value is not None:
                    if key in secret:
                        res[key] = '<hidden>'
                    else:
                        res[key] = value.to_dict(full, include_secrets, True)

        return res

    @classmethod
    def from_dict(model, data, delete=False):

        changed = []

        pkey = model._dict_pkey()

        # handle "primary key" only
        if type(data) is not dict:
            data = {pkey: data}

        # modify input data
        if hasattr(model, '_dict_input'):
            try:
                model._dict_input(data)
            except Exception as reason:
                raise ValueError(f'{reason}', model, None, data)

        # check for primary key (if not recursed)
        if not getattr(model, '_dict_recurse', False):
            if not pkey in data:
                raise KeyError(f'primary key {model.__table__}.{pkey} is missing', model, pkey, data)

        # check data keys and values
        for key, value in data.items():

            # check key
            if not hasattr(model, key):
                raise KeyError(f'unknown key {model.__table__}.{key}', model, key, data)

            # check value type
            col = model.__mapper__.columns.get(key)
            if col is not None:
                if not type(value) is col.type.python_type:
                    raise TypeError(f'{model.__table__}.{key} {value!r} has invalid type {type(value).__name__!r}', model, key, data)
            else:
                rel = model.__mapper__.relationships.get(key)
                if rel is None:
                    itype = getattr(model, '_dict_types', {}).get(key)
                    if itype is not None:
                        if type(value) is not itype:
                            raise TypeError(f'{model.__table__}.{key} {value!r} has invalid type {type(value).__name__!r}', model, key, data)
                    else:
                        raise NotImplementedError(f'type not defined for {model.__table__}.{key}')

            # handle relationships
            if key in model.__mapper__.relationships:
                rel_model = model.__mapper__.relationships[key].argument
                if not isinstance(rel_model, sqlalchemy.orm.Mapper):
                    add = rel_model.from_dict(value, delete)
                    assert len(add) == 1
                    item, updated = add[0]
                    changed.append((item, updated))
                    data[key] = item

        # create or update item?
        item = model.query.get(data[pkey]) if pkey in data else None
        if item is None:
            # create item

            # check for mandatory keys
            missing = getattr(model, '_dict_mandatory', set()) - set(data.keys())
            if missing:
                raise ValueError(f'mandatory key(s) {", ".join(sorted(missing))} for {model.__table__} missing', model, missing, data)

            changed.append((model(**data), True))

        else:
            # update item

            updated = []
            for key, value in data.items():

                # skip primary key
                if key == pkey:
                    continue

                if key in model.__mapper__.relationships:
                    # update relationship
                    rel_model = model.__mapper__.relationships[key].argument
                    if isinstance(rel_model, sqlalchemy.orm.Mapper):
                        rel_model = rel_model.class_
                        # add (and create) referenced items
                        cur = getattr(item, key)
                        old = sorted(cur, key=lambda i:id(i))
                        new = []
                        for rel_data in value:
                            # get or create related item
                            add = rel_model.from_dict(rel_data, delete)
                            assert len(add) == 1
                            rel_item, rel_updated = add[0]
                            changed.append((rel_item, rel_updated))
                            if rel_item not in cur:
                                cur.append(rel_item)
                            new.append(rel_item)

                        # delete referenced items missing in yaml
                        rel_pkey = rel_model._dict_pkey()
                        new_data = list([i.to_dict(True, True, True, [rel_pkey]) for i in new])
                        for rel_item in old:
                            if rel_item not in new:
                                # check if item with same data exists to stabilze import without primary key
                                rel_data = rel_item.to_dict(True, True, True, [rel_pkey])
                                try:
                                    same_idx = new_data.index(rel_data)
                                except ValueError:
                                    same = None
                                else:
                                    same = new[same_idx]

                                if same is None:
                                    # delete items missing in new
                                    if delete:
                                        cur.remove(rel_item)
                                    else:
                                        new.append(rel_item)
                                else:
                                    # swap found item with same data with newly created item
                                    new.append(rel_item)
                                    new_data.append(rel_data)
                                    new.remove(same)
                                    del new_data[same_idx]
                                    for i, (ch_item, ch_update) in enumerate(changed):
                                        if ch_item is same:
                                            changed[i] = (rel_item, [])
                                            db.session.flush()
                                            db.session.delete(ch_item)
                                            break

                        # remember changes
                        new = sorted(new, key=lambda i:id(i))
                        if new != old:
                            updated.append((key, old, new))

                else:
                    # update key
                    old = getattr(item, key)
                    if type(old) is list and not delete:
                        value = old + value
                    if value != old:
                        updated.append((key, old, value))
                        setattr(item, key, value)

            changed.append((item, updated))

        return changed


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


class Domain(Base):
    """ A DNS domain that has mail addresses associated to it.
    """
    __tablename__ = "domain"

    _dict_hide = {'users', 'managers', 'aliases'}
    _dict_show = {'dkim_key'}
    _dict_secret = {'dkim_key'}
    _dict_types = {'dkim_key': bytes}
    _dict_output = {'dkim_key': lambda v: v.decode('utf-8').strip().split('\n')[1:-1]}
    @staticmethod
    def _dict_input(data):
        key = data.get('dkim_key')
        if key is not None:
            key = data['dkim_key']
            if type(key) is list:
                key = ''.join(key)
            if type(key) is str:
                key = ''.join(key.strip().split())
                if key.startswith('-----BEGIN PRIVATE KEY-----'):
                    key = key[25:]
                if key.endswith('-----END PRIVATE KEY-----'):
                    key = key[:-23]
                key = '\n'.join(wrap(key, 64))
                data['dkim_key'] = f'-----BEGIN PRIVATE KEY-----\n{key}\n-----END PRIVATE KEY-----\n'.encode('ascii')

    name = db.Column(IdnaDomain, primary_key=True, nullable=False)
    managers = db.relationship('User', secondary=managers,
        backref=db.backref('manager_of'), lazy='dynamic')
    max_users = db.Column(db.Integer, nullable=False, default=-1)
    max_aliases = db.Column(db.Integer, nullable=False, default=-1)
    max_quota_bytes = db.Column(db.BigInteger(), nullable=False, default=0)
    signup_enabled = db.Column(db.Boolean(), nullable=False, default=False)

    @property
    def dkim_key(self):
        file_path = app.config["DKIM_PATH"].format(
            domain=self.name, selector=app.config["DKIM_SELECTOR"])
        if os.path.exists(file_path):
            with open(file_path, "rb") as handle:
                return handle.read()

    @dkim_key.setter
    def dkim_key(self, value):
        file_path = app.config["DKIM_PATH"].format(
            domain=self.name, selector=app.config["DKIM_SELECTOR"])
        with open(file_path, "wb") as handle:
            handle.write(value)

    @property
    def dkim_publickey(self):
        dkim_key = self.dkim_key
        if dkim_key:
            return dkim.strip_key(self.dkim_key).decode("utf8")

    def generate_dkim_key(self):
        self.dkim_key = dkim.gen_key()

    def has_email(self, localpart):
        for email in self.users + self.aliases:
            if email.localpart == localpart:
                return True
        else:
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
        return self.name

    def __eq__(self, other):
        try:
            return self.name == other.name
        except AttributeError:
            return False


class Alternative(Base):
    """ Alternative name for a served domain.
    The name "domain alias" was avoided to prevent some confusion.
    """

    __tablename__ = "alternative"

    name = db.Column(IdnaDomain, primary_key=True, nullable=False)
    domain_name = db.Column(IdnaDomain, db.ForeignKey(Domain.name))
    domain = db.relationship(Domain,
        backref=db.backref('alternatives', cascade='all, delete-orphan'))

    def __str__(self):
        return self.name


class Relay(Base):
    """ Relayed mail domain.
    The domain is either relayed publicly or through a specified SMTP host.
    """

    __tablename__ = "relay"

    _dict_mandatory = {'smtp'}

    name = db.Column(IdnaDomain, primary_key=True, nullable=False)
    smtp = db.Column(db.String(80), nullable=True)

    def __str__(self):
        return self.name


class Email(object):
    """ Abstraction for an email address (localpart and domain).
    """

    localpart = db.Column(db.String(80), nullable=False)

    @staticmethod
    def _dict_input(data):
        if 'email' in data:
            if 'localpart' in data or 'domain' in data:
                raise ValueError('ambigous key email and localpart/domain')
            elif type(data['email']) is str:
                data['localpart'], data['domain'] = data['email'].rsplit('@', 1)
        else:
            data['email'] = f"{data['localpart']}@{data['domain']}"

    @declarative.declared_attr
    def domain_name(cls):
        return db.Column(IdnaDomain, db.ForeignKey(Domain.name),
            nullable=False, default=IdnaDomain)

    # This field is redundant with both localpart and domain name.
    # It is however very useful for quick lookups without joining tables,
    # especially when the mail server is reading the database.
    @declarative.declared_attr
    def email(cls):
        updater = lambda context: "{0}@{1}".format(
            context.current_parameters["localpart"],
            context.current_parameters["domain_name"],
        )
        return db.Column(IdnaEmail,
            primary_key=True, nullable=False,
            default=updater)

    def sendmail(self, subject, body):
        """ Send an email to the address.
        """
        from_address = "{0}@{1}".format(
            app.config['POSTMASTER'],
            idna.encode(app.config['DOMAIN']).decode('ascii'),
        )
        with smtplib.SMTP(app.config['HOST_AUTHSMTP'], port=10025) as smtp:
            to_address = "{0}@{1}".format(
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
        return self.email


class User(Base, Email):
    """ A user is an email address that has a password to access a mailbox.
    """
    __tablename__ = "user"

    _dict_hide = {'domain_name', 'domain', 'localpart', 'quota_bytes_used'}
    _dict_mandatory = {'localpart', 'domain', 'password'}
    @classmethod
    def _dict_input(cls, data):
        Email._dict_input(data)
        # handle password
        if 'password' in data:
            if 'password_hash' in data or 'hash_scheme' in data:
                raise ValueError('ambigous key password and password_hash/hash_scheme')
            # check (hashed) password
            password = data['password']
            if password.startswith('{') and '}' in password:
                scheme = password[1:password.index('}')]
                if scheme not in cls.scheme_dict:
                    raise ValueError(f'invalid password scheme {scheme!r}')
            else:
                raise ValueError(f'invalid hashed password {password!r}')
        elif 'password_hash' in data and 'hash_scheme' in data:
            if data['hash_scheme'] not in cls.scheme_dict:
                raise ValueError(f'invalid password scheme {scheme!r}')
            data['password'] = '{'+data['hash_scheme']+'}'+ data['password_hash']

    domain = db.relationship(Domain,
        backref=db.backref('users', cascade='all, delete-orphan'))
    password = db.Column(db.String(255), nullable=False)
    quota_bytes = db.Column(db.BigInteger(), nullable=False, default=10**9)
    quota_bytes_used = db.Column(db.BigInteger(), nullable=False, default=0)
    global_admin = db.Column(db.Boolean(), nullable=False, default=False)
    enabled = db.Column(db.Boolean(), nullable=False, default=True)

    # Features
    enable_imap = db.Column(db.Boolean(), nullable=False, default=True)
    enable_pop = db.Column(db.Boolean(), nullable=False, default=True)

    # Filters
    forward_enabled = db.Column(db.Boolean(), nullable=False, default=False)
    forward_destination = db.Column(CommaSeparatedList(), nullable=True, default=[])
    forward_keep = db.Column(db.Boolean(), nullable=False, default=True)
    reply_enabled = db.Column(db.Boolean(), nullable=False, default=False)
    reply_subject = db.Column(db.String(255), nullable=True, default=None)
    reply_body = db.Column(db.Text(), nullable=True, default=None)
    reply_startdate = db.Column(db.Date, nullable=False,
        default=date(1900, 1, 1))
    reply_enddate = db.Column(db.Date, nullable=False,
        default=date(2999, 12, 31))

    # Settings
    displayed_name = db.Column(db.String(160), nullable=False, default="")
    spam_enabled = db.Column(db.Boolean(), nullable=False, default=True)
    spam_threshold = db.Column(db.Integer(), nullable=False, default=80)

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

    scheme_dict = {'PBKDF2': "pbkdf2_sha512",
                   'BLF-CRYPT': "bcrypt",
                   'SHA512-CRYPT': "sha512_crypt",
                   'SHA256-CRYPT': "sha256_crypt",
                   'MD5-CRYPT': "md5_crypt",
                   'CRYPT': "des_crypt"}

    def get_password_context(self):
        return context.CryptContext(
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
            self.password = '{'+hash_scheme+'}' + self.get_password_context().encrypt(password, self.scheme_dict[hash_scheme])

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
        if app.config["WELCOME"]:
            self.sendmail(app.config["WELCOME_SUBJECT"],
                app.config["WELCOME_BODY"])

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
    __tablename__ = "alias"

    _dict_hide = {'domain_name', 'domain', 'localpart'}
    @staticmethod
    def _dict_input(data):
        # handle comma delimited string for backwards compability
        dst = data.get('destination')
        if type(dst) is str:
            data['destination'] = list([adr.strip() for adr in dst.split(',')])

    domain = db.relationship(Domain,
        backref=db.backref('aliases', cascade='all, delete-orphan'))
    wildcard = db.Column(db.Boolean(), nullable=False, default=False)
    destination = db.Column(CommaSeparatedList, nullable=False, default=[])

    @classmethod
    def resolve(cls, localpart, domain_name):
        alias_preserve_case = cls.query.filter(
                sqlalchemy.and_(cls.domain_name == domain_name,
                    sqlalchemy.or_(
                        sqlalchemy.and_(
                            cls.wildcard == False,
                            cls.localpart == localpart
                        ), sqlalchemy.and_(
                            cls.wildcard == True,
                            sqlalchemy.bindparam("l", localpart).like(cls.localpart)
                        )
                    )
                )
            ).order_by(cls.wildcard, sqlalchemy.func.char_length(cls.localpart).desc()).first()

        localpart_lower = localpart.lower() if localpart else None
        alias_lower_case = cls.query.filter(
                sqlalchemy.and_(cls.domain_name == domain_name,
                    sqlalchemy.or_(
                        sqlalchemy.and_(
                            cls.wildcard == False,
                            sqlalchemy.func.lower(cls.localpart) == localpart_lower
                        ), sqlalchemy.and_(
                            cls.wildcard == True,
                            sqlalchemy.bindparam("l", localpart_lower).like(sqlalchemy.func.lower(cls.localpart))
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
    __tablename__ = "token"

    _dict_recurse = True
    _dict_hide = {'user', 'user_email'}
    _dict_mandatory = {'password'}

    id = db.Column(db.Integer(), primary_key=True)
    user_email = db.Column(db.String(255), db.ForeignKey(User.email),
        nullable=False)
    user = db.relationship(User,
        backref=db.backref('tokens', cascade='all, delete-orphan'))
    password = db.Column(db.String(255), nullable=False)
    ip = db.Column(db.String(255))

    def check_password(self, password):
        return hash.sha256_crypt.verify(password, self.password)

    def set_password(self, password):
        self.password = hash.sha256_crypt.using(rounds=1000).hash(password)

    def __str__(self):
        return self.comment or self.ip


class Fetch(Base):
    """ A fetched account is a remote POP/IMAP account fetched into a local
    account.
    """
    __tablename__ = "fetch"

    _dict_recurse = True
    _dict_hide = {'user_email', 'user', 'last_check', 'error'}
    _dict_mandatory = {'protocol', 'host', 'port', 'username', 'password'}
    _dict_secret = {'password'}

    id = db.Column(db.Integer(), primary_key=True)
    user_email = db.Column(db.String(255), db.ForeignKey(User.email),
        nullable=False)
    user = db.relationship(User,
        backref=db.backref('fetches', cascade='all, delete-orphan'))
    protocol = db.Column(db.Enum('imap', 'pop3'), nullable=False)
    host = db.Column(db.String(255), nullable=False)
    port = db.Column(db.Integer(), nullable=False)
    tls = db.Column(db.Boolean(), nullable=False, default=False)
    username = db.Column(db.String(255), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    keep = db.Column(db.Boolean(), nullable=False, default=False)
    last_check = db.Column(db.DateTime, nullable=True)
    error = db.Column(db.String(1023), nullable=True)

    def __str__(self):
        return f'{self.protocol}{"s" if self.tls else ""}://{self.username}@{self.host}:{self.port}'
