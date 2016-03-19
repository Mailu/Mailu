from freeposte import db

from sqlalchemy.ext import declarative
from passlib import context


# Many-to-many association table for domain administrators
admins = db.Table('admin',
    db.Column('domain_name', db.String(80), db.ForeignKey('domain.name')),
    db.Column('user_domain_name', db.String(80)),
    db.Column('user_localpart', db.String(80)),
    db.ForeignKeyConstraint(
        ('user_domain_name', 'user_localpart'),
        ('user.domain_name', 'user.localpart')
    )
)


class Domain(db.Model):
    """ A DNS domain that has mail addresses associated to it.
    """
    name = db.Column(db.String(80), primary_key=True, nullable=False)
    admins = db.relationship('User', secondary=admins,
        backref=db.backref('admin_of'), lazy='dynamic')
    max_users = db.Column(db.Integer, nullable=True)
    max_aliases = db.Column(db.Integer, nullable=True)

    def __str__(self):
        return self.name


class Address(db.Model):
    """ Abstraction for a mail address (localpart and domain).
    """
    __abstract__ = True

    localpart = db.Column(db.String(80), primary_key=True, nullable=False)

    @declarative.declared_attr
    def domain_name(cls):
        return db.Column(db.String(80), db.ForeignKey(Domain.name),
            primary_key=True, nullable=False)

    def __str__(self):
        return '{0}@{1}'.format(self.localpart, self.domain_name)

    def get_id(self):
        return str(self)

    @classmethod
    def get_by_email(cls, email):
        localpart, domain = email.split('@', maxsplit=1)
        # Get the user object
        return cls.query.filter_by(domain_name=domain, localpart=localpart).first()


class User(Address):
    """ A user is a mail address that has a password to access a mailbox.
    """
    domain = db.relationship(Domain, backref='users')
    password = db.Column(db.String(255), nullable=False)
    quota_bytes = db.Column(db.Integer(), nullable=False, default=10**9)
    forward = db.Column(db.String(160), nullable=True, default=None)
    global_admin = db.Column(db.Boolean(), nullable=False, default=False)

    is_authenticated = True
    is_active = True
    is_anonymous = False

    pw_context = context.CryptContext(["sha512_crypt", "sha256_crypt"])

    def check_password(self, password):
        return User.pw_context.verify(password, self.password)

    def set_password(self, password):
        self.password = User.pw_context.encrypt(password)

    def get_managed_domains(self):
        if self.global_admin:
            return Domain.query.all()
        else:
            return self.admin_of

    @classmethod
    def login(cls, email, password):
        user = cls.get_by_email(email)
        return user if (user and user.check_password(password)) else None


class Alias(Address):
    """ An alias is a mail address that redirects to some other addresses.
    """
    domain = db.relationship(Domain, backref='aliases')
    destination = db.Column(db.String(), nullable=False)
