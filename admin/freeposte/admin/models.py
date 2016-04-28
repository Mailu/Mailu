from freeposte.admin import db

from sqlalchemy.ext import declarative
from passlib import context
from datetime import datetime

import re


# Many-to-many association table for domain managers
managers = db.Table('manager',
    db.Column('domain_name', db.String(80), db.ForeignKey('domain.name')),
    db.Column('user_address', db.String(255), db.ForeignKey('user.address'))
)


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
    name = db.Column(db.String(80), primary_key=True, nullable=False)
    managers = db.relationship('User', secondary=managers,
        backref=db.backref('manager_of'), lazy='dynamic')
    max_users = db.Column(db.Integer, nullable=False, default=0)
    max_aliases = db.Column(db.Integer, nullable=False, default=0)

    def has_address(self, localpart):
        for address in self.users + self.aliases:
            if address.localpart == localpart:
                return True
        else:
            return False

    def __str__(self):
        return self.name


class Address(Base):
    """ Abstraction for a mail address (localpart and domain).
    """
    __abstract__ = True

    localpart = db.Column(db.String(80), nullable=False)

    @declarative.declared_attr
    def domain_name(cls):
        return db.Column(db.String(80), db.ForeignKey(Domain.name),
            nullable=False)

    # This field is redundant with both localpart and domain name.
    # It is however very useful for quick lookups without joining tables,
    # especially when the mail server il reading the database.
    @declarative.declared_attr
    def address(cls):
        updater = lambda context: "{0}@{1}".format(
            context.current_parameters["localpart"],
            context.current_parameters["domain_name"],
        )
        return db.Column(db.String(255),
            primary_key=True, nullable=False,
            default=updater)

    @classmethod
    def get_by_email(cls, email):
        return cls.query.filter_by(address=email).first()

    def __str__(self):
        return self.address


class User(Address):
    """ A user is a mail address that has a password to access a mailbox.
    """
    domain = db.relationship(Domain, backref='users')
    password = db.Column(db.String(255), nullable=False)
    quota_bytes = db.Column(db.Integer(), nullable=False, default=10**9)
    global_admin = db.Column(db.Boolean(), nullable=False, default=False)

    # Features
    enable_imap = db.Column(db.Boolean(), nullable=False, default=True)
    enable_pop = db.Column(db.Boolean(), nullable=False, default=True)

    # Filters
    forward = db.Column(db.String(160), nullable=True, default=None)
    reply_subject = db.Column(db.String(255), nullable=True, default=None)
    reply_body = db.Column(db.Text(), nullable=True, default=None)

    # Settings
    displayed_name = db.Column(db.String(160), nullable=False, default="")
    spam_enabled = db.Column(db.Boolean(), nullable=False, default=True)
    spam_threshold = db.Column(db.Numeric(), nullable=False, default=5.0)

    # Flask-login attributes
    is_authenticated = True
    is_active = True
    is_anonymous = False

    def get_id(self):
        return self.address

    pw_context = context.CryptContext(
        ["sha512_crypt", "sha256_crypt", "md5_crypt"]
    )

    def check_password(self, password):
        reference = re.match('({[^}]+})?(.*)', self.password).group(2)
        return User.pw_context.verify(password, reference)

    def set_password(self, password):
        self.password = '{SHA512-CRYPT}' + User.pw_context.encrypt(password)

    def get_managed_domains(self):
        if self.global_admin:
            return Domain.query.all()
        else:
            return self.manager_of

    def get_managed_addresses(self):
        addresses = []
        for domain in self.get_managed_domains():
            addresses.extend(domain.users)
            addresses.extend(domain.aliases)
        return addresses

    @classmethod
    def login(cls, email, password):
        user = cls.get_by_email(email)
        return user if (user and user.check_password(password)) else None


class Alias(Address):
    """ An alias is a mail address that redirects to some other addresses.
    """
    domain = db.relationship(Domain, backref='aliases')
    destination = db.Column(db.String(), nullable=False)


class Fetch(Base):
    """ A fetched account is a repote POP/IMAP account fetched into a local
    account.
    """
    id = db.Column(db.Integer(), primary_key=True)
    user_address = db.Column(db.String(255), db.ForeignKey(User.address),
        nullable=False)
    user = db.relationship(User, backref='fetches')
    protocol = db.Column(db.Enum('imap', 'pop3'), nullable=False)
    host = db.Column(db.String(255), nullable=False)
    port = db.Column(db.Integer(), nullable=False)
    tls = db.Column(db.Boolean(), nullable=False)
    username = db.Column(db.String(255), nullable=False)
    password = db.Column(db.String(255), nullable=False)
