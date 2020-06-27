from mailu import dkim

from sqlalchemy.ext import declarative
from passlib import context, hash
from datetime import datetime, date
from email.mime import text
from flask import current_app as app

import flask_sqlalchemy
import sqlalchemy
import re
import time
import os
import glob
import smtplib
import idna
import dns


db = flask_sqlalchemy.SQLAlchemy()


class IdnaDomain(db.TypeDecorator):
    """ Stores a Unicode string in it's IDNA representation (ASCII only)
    """

    impl = db.String(80)

    def process_bind_param(self, value, dialect):
        return idna.encode(value).decode("ascii").lower()

    def process_result_value(self, value, dialect):
        return idna.decode(value)


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


class CommaSeparatedList(db.TypeDecorator):
    """ Stores a list as a comma-separated string, compatible with Postfix.
    """

    impl = db.String

    def process_bind_param(self, value, dialect):
        if type(value) is not list:
            raise TypeError("Shoud be a list")
        for item in value:
            if "," in item:
                raise ValueError("No item should contain a comma")
        return ",".join(value)

    def process_result_value(self, value, dialect):
        return list(filter(bool, value.split(","))) if value else []


class JSONEncoded(db.TypeDecorator):
    """Represents an immutable structure as a json-encoded string.
    """

    impl = db.String

    def process_bind_param(self, value, dialect):
        return json.dumps(value) if value else None

    def process_result_value(self, value, dialect):
        return json.loads(value) if value else None


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
        except Exception as e:
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

    name = db.Column(IdnaDomain, primary_key=True, nullable=False)
    smtp = db.Column(db.String(80), nullable=True)

    def __str__(self):
        return self.name


class Email(object):
    """ Abstraction for an email address (localpart and domain).
    """

    localpart = db.Column(db.String(80), nullable=False)

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
    spam_folder = os.environ.get('JUNK_FOLDER', 'Junk')

    # Flask-login attributes
    is_authenticated = True
    is_active = True
    is_anonymous = False

    def get_id(self):
        return self.email

    @property
    def destination(self):
        if self.forward_enabled:
            result = self.forward_destination
            if self.forward_keep:
                result += ',' + self.email
            return result
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
        return self.comment


class Fetch(Base):
    """ A fetched account is a repote POP/IMAP account fetched into a local
    account.
    """
    __tablename__ = "fetch"

    id = db.Column(db.Integer(), primary_key=True)
    user_email = db.Column(db.String(255), db.ForeignKey(User.email),
        nullable=False)
    user = db.relationship(User,
        backref=db.backref('fetches', cascade='all, delete-orphan'))
    protocol = db.Column(db.Enum('imap', 'pop3'), nullable=False)
    host = db.Column(db.String(255), nullable=False)
    port = db.Column(db.Integer(), nullable=False)
    tls = db.Column(db.Boolean(), nullable=False)
    username = db.Column(db.String(255), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    keep = db.Column(db.Boolean(), nullable=False)
    last_check = db.Column(db.DateTime, nullable=True)
    error = db.Column(db.String(1023), nullable=True)
