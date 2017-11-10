from mailu import app, db, dkim, login_manager

from sqlalchemy.ext import declarative
from passlib import context, hash
from datetime import datetime, date
from email.mime import text


import re
import time
import os
import glob
import smtplib


# Many-to-many association table for domain managers
managers = db.Table('manager',
    db.Column('domain_name', db.String(80), db.ForeignKey('domain.name')),
    db.Column('user_email', db.String(255), db.ForeignKey('user.email'))
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
        return filter(bool, value.split(","))


class Base(db.Model):
    """ Base class for all models
    """

    __abstract__ = True

    created_at = db.Column(db.Date, nullable=False, default=datetime.now)
    updated_at = db.Column(db.Date, nullable=True, onupdate=datetime.now)
    comment = db.Column(db.String(255), nullable=True)


class Domain(Base):
    """ A DNS domain that has mail addresses associated to it.
    """
    __tablename__ = "domain"

    name = db.Column(db.String(80), primary_key=True, nullable=False)
    managers = db.relationship('User', secondary=managers,
        backref=db.backref('manager_of'), lazy='dynamic')
    max_users = db.Column(db.Integer, nullable=False, default=0)
    max_aliases = db.Column(db.Integer, nullable=False, default=0)
    max_quota_bytes = db.Column(db.Integer(), nullable=False, default=0)

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

    name = db.Column(db.String(80), primary_key=True, nullable=False)
    domain_name = db.Column(db.String(80), db.ForeignKey(Domain.name))
    domain = db.relationship(Domain,
        backref=db.backref('alternatives', cascade='all, delete-orphan'))

    def __str__(self):
        return self.name


class Relay(Base):
    """ Relayed mail domain.
    The domain is either relayed publicly or through a specified SMTP host.
    """

    __tablename__ = "relay"

    name = db.Column(db.String(80), primary_key=True, nullable=False)
    smtp = db.Column(db.String(80), nullable=True)

    def __str__(self):
        return self.name


class Email(object):
    """ Abstraction for an email address (localpart and domain).
    """

    localpart = db.Column(db.String(80), nullable=False)

    @declarative.declared_attr
    def domain_name(cls):
        return db.Column(db.String(80), db.ForeignKey(Domain.name),
            nullable=False)

    # This field is redundant with both localpart and domain name.
    # It is however very useful for quick lookups without joining tables,
    # especially when the mail server il reading the database.
    @declarative.declared_attr
    def email(cls):
        updater = lambda context: "{0}@{1}".format(
            context.current_parameters["localpart"],
            context.current_parameters["domain_name"],
        )
        return db.Column(db.String(255, collation="NOCASE"),
            primary_key=True, nullable=False,
            default=updater)

    def sendmail(self, subject, body):
        """ Send an email to the address.
        """
        from_address = '{}@{}'.format(
            app.config['POSTMASTER'], app.config['DOMAIN'])
        with smtplib.SMTP('smtp', port=10025) as smtp:
            msg = text.MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = from_address
            msg['To'] = self.email
            smtp.sendmail(from_address, [self.email], msg.as_string())

    def __str__(self):
        return self.email


class User(Base, Email):
    """ A user is an email address that has a password to access a mailbox.
    """
    __tablename__ = "user"

    domain = db.relationship(Domain,
        backref=db.backref('users', cascade='all, delete-orphan'))
    password = db.Column(db.String(255), nullable=False)
    quota_bytes = db.Column(db.Integer(), nullable=False, default=10**9)
    global_admin = db.Column(db.Boolean(), nullable=False, default=False)

    # Features
    enable_imap = db.Column(db.Boolean(), nullable=False, default=True)
    enable_pop = db.Column(db.Boolean(), nullable=False, default=True)

    # Filters
    forward_enabled = db.Column(db.Boolean(), nullable=False, default=False)
    forward_destination = db.Column(db.String(255), nullable=True, default=None)
    forward_keep = db.Column(db.Boolean(), nullable=False, default=True)
    reply_enabled = db.Column(db.Boolean(), nullable=False, default=False)
    reply_subject = db.Column(db.String(255), nullable=True, default=None)
    reply_body = db.Column(db.Text(), nullable=True, default=None)
    reply_enddate = db.Column(db.Date, nullable=False,
        default=date(2999, 12, 31))

    # Settings
    displayed_name = db.Column(db.String(160), nullable=False, default="")
    spam_enabled = db.Column(db.Boolean(), nullable=False, default=True)
    spam_threshold = db.Column(db.Integer(), nullable=False, default=80.0)

    # Flask-login attributes
    is_authenticated = True
    is_active = True
    is_anonymous = False

    def get_id(self):
        return self.email

    scheme_dict = {'SHA512-CRYPT': "sha512_crypt",
                   'SHA256-CRYPT': "sha256_crypt",
                   'MD5-CRYPT': "md5_crypt",
                   'CRYPT': "des_crypt"}
    pw_context = context.CryptContext(
        schemes = scheme_dict.values(),
        default=scheme_dict[app.config['PASSWORD_SCHEME']],
    )

    def check_password(self, password):
        reference = re.match('({[^}]+})?(.*)', self.password).group(2)
        return User.pw_context.verify(password, reference)

    def set_password(self, password, hash_scheme=app.config['PASSWORD_SCHEME'], raw=False):
        """Set password for user with specified encryption scheme
           @password: plain text password to encrypt (if raw == True the hash itself)
        """
        # for the list of hash schemes see https://wiki2.dovecot.org/Authentication/PasswordSchemes
        if raw:
            self.password = '{'+hash_scheme+'}' + password
        else:
            self.password = '{'+hash_scheme+'}' + User.pw_context.encrypt(password, self.scheme_dict[hash_scheme])

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
        if app.config["WELCOME"].lower() == "true":
            self.sendmail(app.config["WELCOME_SUBJECT"],
                app.config["WELCOME_BODY"])

    @classmethod
    def login(cls, email, password):
        user = cls.query.get(email)
        return user if (user and user.check_password(password)) else None

login_manager.user_loader(User.query.get)


class Alias(Base, Email):
    """ An alias is an email address that redirects to some destination.
    """
    __tablename__ = "alias"

    domain = db.relationship(Domain,
        backref=db.backref('aliases', cascade='all, delete-orphan'))
    wildcard = db.Column(db.Boolean(), nullable=False, default=False)
    destination = db.Column(CommaSeparatedList, nullable=False, default=[])


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
