""" Mailu config storage model
"""

import os
import json
import secrets
import sqlite3
import uuid

from datetime import date, datetime, timezone
from email.mime import text
from itertools import chain

import flask_sqlalchemy
import sqlalchemy
import passlib.context
import passlib.hash
import passlib.registry
import logging
import os
import smtplib
import idna
import validators
import dns.resolver
import dns.exception

from flask import current_app as app
from sqlalchemy.dialects import mysql
from sqlalchemy.ext import declarative
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.inspection import inspect
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import event
from werkzeug.utils import cached_property

from mailu import dkim, utils


# silence AttributeError: module 'bcrypt' has no attribute '__about__'
logging.getLogger('passlib').setLevel(logging.ERROR)


db = flask_sqlalchemy.SQLAlchemy()


def _sql_variable_enabled(value):
    if isinstance(value, bytes):
        value = value.decode('ascii')
    return str(value).strip().upper() in {'1', 'ON', 'TRUE'}


def _reject_mysql_statement_binlog(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute(
            'SELECT @@GLOBAL.log_bin, @@SESSION.sql_log_bin, '
            '@@SESSION.binlog_format'
        )
        log_bin, sql_log_bin, binlog_format = cursor.fetchone()
    finally:
        cursor.close()

    if isinstance(binlog_format, bytes):
        binlog_format = binlog_format.decode('ascii')
    if (
        _sql_variable_enabled(log_bin)
        and _sql_variable_enabled(sql_log_bin)
        and str(binlog_format).strip().upper() == 'STATEMENT'
    ):
        raise RuntimeError(
            'Mailu requires MySQL/MariaDB binlog_format=ROW or MIXED '
            'while binary logging is active because the admin database '
            'uses READ COMMITTED; binlog_format=STATEMENT is unsupported'
        )


def configure_database_engine(engine):
    if (
        engine.dialect.name in {'mysql', 'mariadb'}
        and not event.contains(
            engine,
            'connect',
            _reject_mysql_statement_binlog,
        )
    ):
        event.listen(
            engine,
            'connect',
            _reject_mysql_statement_binlog,
        )


@sqlalchemy.event.listens_for(sqlalchemy.engine.Engine, 'connect')
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    """Make SQLite enforce the same foreign-key contract as production SQL."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()


class AddressConflict(sqlalchemy.exc.IntegrityError):
    """Raised when two concrete resources claim one routing address."""

    def __init__(self, email, original):
        self.email = email
        if isinstance(original, sqlalchemy.exc.IntegrityError):
            statement = original.statement
            params = original.params
            cause = original.orig
            invalidated = original.connection_invalidated
        else:
            statement = None
            params = {'email': email}
            cause = original
            invalidated = False
        super().__init__(
            statement,
            params,
            cause,
            connection_invalidated=invalidated,
        )


class AddressRenameError(ValueError):
    """Raised when code attempts to mutate a persisted address primary key."""


class IdnaDomain(db.TypeDecorator):
    """ Stores a Unicode string in it's IDNA representation (ASCII only)
    """

    impl = db.String(80)
    cache_ok = True
    python_type = str

    def process_bind_param(self, value, dialect):
        """ encode unicode domain name to punycode """
        return idna.encode(value.lower()).decode('ascii')

    def process_result_value(self, value, dialect):
        """ decode punycode domain name to unicode """
        return idna.decode(value)

class IdnaEmail(db.TypeDecorator):
    """ Stores a Unicode string in it's IDNA representation (ASCII only)
    """

    impl = db.String(255)
    cache_ok = True
    python_type = str

    def process_bind_param(self, value, dialect):
        """ encode unicode domain part of email address to punycode """
        if value is None:
            return None
        if not '@' in value:
            raise ValueError('invalid email address (no "@")')
        localpart, domain_name = value.lower().rsplit('@', 1)
        if '@' in localpart:
            raise ValueError('email local part must not contain "@"')
        return f'{localpart}@{idna.encode(domain_name).decode("ascii")}'

    def process_result_value(self, value, dialect):
        """ decode punycode domain part of email to unicode """
        if value is None:
            return None
        localpart, domain_name = value.rsplit('@', 1)
        return f'{localpart}@{idna.decode(domain_name)}'


def ExactScimId():
    """Store provider IDs with byte-exact MySQL/MariaDB comparisons."""
    return db.String(255).with_variant(
        mysql.VARCHAR(255, collation='utf8mb4_bin'),
        'mysql',
    )


class CommaSeparatedList(db.TypeDecorator):
    """ Stores a list as a comma-separated string, compatible with Postfix.
    """

    impl = db.String(4096)
    cache_ok = True
    python_type = list

    def process_bind_param(self, value, dialect):
        """ join list of items to comma separated string """
        if not isinstance(value, (list, tuple, set)):
            raise TypeError('Must be a list of strings')
        for item in value:
            if ',' in item:
                raise ValueError('list item must not contain ","')
        return ','.join(sorted(set(value)))

    def process_result_value(self, value, dialect):
        """ split comma separated string to list """
        return list(filter(bool, (item.strip() for item in value.split(',')))) if value else []

class JSONEncoded(db.TypeDecorator):
    """ Represents an immutable structure as a json-encoded string.
    """

    impl = db.String(255)
    cache_ok = True
    python_type = str

    def process_bind_param(self, value, dialect):
        """ encode data as json """
        return json.dumps(value) if value else None

    def process_result_value(self, value, dialect):
        """ decode json to data """
        return json.loads(value) if value else None

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

    def __str__(self):
        pkey = self.__table__.primary_key.columns.values()[0].name
        if pkey == 'email':
            # ugly hack for email declared attr. _email is not always up2date
            return str(f'{self.localpart}@{self.domain_name}')
        return str(getattr(self, pkey))

    def __repr__(self):
        return f'<{self.__class__.__name__} {str(self)!r}>'

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            pkey = self.__table__.primary_key.columns.values()[0].name
            this = getattr(self, pkey, None)
            other = getattr(other, pkey, None)
            return this is not None and other is not None and str(this) == str(other)
        else:
            return NotImplemented

    # we need hashable instances here for sqlalchemy to update collections
    # in collections.bulk_replace, but auto-incrementing don't always have
    # a valid primary key, in this case we use the object's id
    __hashed = None
    def __hash__(self):
        if self.__hashed is None:
            primary = getattr(self, self.__table__.primary_key.columns.values()[0].name)
            self.__hashed = id(self) if primary is None else hash(primary)
        return self.__hashed

    def dont_change_updated_at(self):
        """ Mark updated_at as modified, but keep the old date when updating the model"""
        flag_modified(self, 'updated_at')


class Config(Base):
    """ In-database configuration values
    """

    name = db.Column(db.String(255), primary_key=True, nullable=False)
    value = db.Column(JSONEncoded)


def _save_dkim_keys(session):
    """ store DKIM keys after commit """
    for obj in session.identity_map.values():
        if isinstance(obj, Domain):
            obj.save_dkim_key()

def _get_managers():
    return managers


class Domain(Base):
    """ A DNS domain that has mail addresses associated to it.
    """

    __tablename__ = 'domain'

    name = db.Column(IdnaDomain, primary_key=True, nullable=False)
    managers = db.relationship('User', secondary=_get_managers,
        backref=db.backref('manager_of'), lazy='dynamic')
    max_users = db.Column(db.Integer, nullable=False, default=-1)
    max_aliases = db.Column(db.Integer, nullable=False, default=-1)
    max_quota_bytes = db.Column(db.BigInteger, nullable=False, default=0)
    signup_enabled = db.Column(db.Boolean, nullable=False, default=False)
    # Anonymous Email Service integration: enable domain to accept API-generated aliases
    anonmail_enabled = db.Column(db.Boolean, nullable=False, default=False)

    _dkim_key = None
    _dkim_key_on_disk = None

    def _dkim_file(self):
        """ return filename for active DKIM key """
        return app.config['DKIM_PATH'].format(
            domain=self.name,
            selector=app.config['DKIM_SELECTOR']
        )

    def save_dkim_key(self):
        """ save changed DKIM key to disk """
        if self._dkim_key != self._dkim_key_on_disk:
            file_path = self._dkim_file()
            if self._dkim_key:
                with open(file_path, 'wb') as handle:
                    handle.write(self._dkim_key)
            elif os.path.exists(file_path):
                os.unlink(file_path)
            self._dkim_key_on_disk = self._dkim_key

    @cached_property
    def dns_mx(self):
        """ return MX record for domain """
        hostname = app.config['HOSTNAME']
        return f'{idna.encode(self.name.lower()).decode('ascii')}. 600 IN MX 10 {idna.encode(hostname.lower()).decode('ascii')}.'

    @cached_property
    def dns_spf(self):
        """ return SPF record for domain """
        hostname = app.config['HOSTNAME']
        return f'{idna.encode(self.name.lower()).decode('ascii')}. 600 IN TXT "v=spf1 mx a:{idna.encode(hostname.lower()).decode('ascii')} ~all"'

    @property
    def dns_dkim(self):
        """ return DKIM record for domain """
        if self.dkim_key:
            selector = app.config['DKIM_SELECTOR']
            return f'{selector}._domainkey.{idna.encode(self.name.lower()).decode('ascii')}. 600 IN TXT "v=DKIM1; k=rsa; p={self.dkim_publickey}"'

    @cached_property
    def dns_dmarc(self):
        """ return DMARC record for domain """
        if self.dkim_key:
            domain = app.config['DOMAIN']
            rua = app.config['DMARC_RUA']
            rua = f' rua=mailto:{rua}@{idna.encode(domain.lower()).decode('ascii')};' if rua else ''
            ruf = app.config['DMARC_RUF']
            ruf = f' ruf=mailto:{ruf}@{idna.encode(domain.lower()).decode('ascii')};' if ruf else ''
            return f'_dmarc.{idna.encode(self.name.lower()).decode('ascii')}. 600 IN TXT "v=DMARC1; p=reject;{rua}{ruf} adkim=s; aspf=s"'

    @cached_property
    def dns_dmarc_report_needed(self):
        """ return true if DMARC report record is needed """
        return self.name != app.config['DOMAIN']

    @cached_property
    def dns_dmarc_report(self):
        """ return DMARC report record for mailu server """
        if self.dkim_key:
            domain = app.config['DOMAIN']
            return f'{idna.encode(self.name.lower()).decode('ascii')}._report._dmarc.{idna.encode(domain.lower()).decode('ascii')}. 600 IN TXT "v=DMARC1;"'

    @cached_property
    def dns_autoconfig(self):
        """ return list of auto configuration records (RFC6186) """
        ports = {int(port.strip()) for port in app.config['PORTS'].split(',')}.union({465, 993})
        hostname = app.config['HOSTNAME']
        protocols = [
            ('imap', 143, 20),
            ('pop3', 110, 20),
            ('submission', 587, 20),
        ]
        if app.config['TLS_FLAVOR'] != 'notls':
            protocols.extend([
                ('autodiscover', 443, 10),
                ('submissions', 465, 10),
                ('imaps', 993, 10),
                ('pop3s', 995, 10),
            ])

        return [
            f'_{proto}._tcp.{idna.encode(self.name.lower()).decode('ascii')}. 600 IN SRV {prio} 1 {port} {hostname}.' if port in ports else f'_{proto}._tcp.{idna.encode(self.name.lower()).decode('ascii')}. 600 IN SRV 0 0 0 .'
            for proto, port, prio
            in protocols
        ]+[f'autoconfig.{idna.encode(self.name.lower()).decode('ascii')}. 600 IN CNAME {idna.encode(hostname.lower()).decode('ascii')}.', f'autodiscover.{idna.encode(self.name.lower()).decode('ascii')}. 600 IN CNAME {idna.encode(hostname.lower()).decode('ascii')}.']

    @cached_property
    def dns_tlsa(self):
        """ return TLSA record for domain when using letsencrypt """
        hostname = app.config['HOSTNAME']
        if app.config['TLS_FLAVOR'] in ('letsencrypt', 'mail-letsencrypt'):
            return [
                # current ISRG Root X1 (RSA 4096, O = Internet Security Research Group, CN = ISRG Root X1) @20210902
                f'_25._tcp.{idna.encode(hostname.lower()).decode('ascii')}. 86400 IN TLSA 2 1 1 0b9fa5a59eed715c26c1020c711b4f6ec42d58b0015e14337a39dad301c5afc3',
                # current ISRG Root X2 (ECDSA P-384, O = Internet Security Research Group, CN = ISRG Root X2) @20240311
                f'_25._tcp.{idna.encode(hostname.lower()).decode('ascii')}. 86400 IN TLSA 2 1 1 762195c225586ee6c0237456e2107dc54f1efc21f61a792ebd515913cce68332',
            ]
        return []

    @property
    def dkim_key(self):
        """ return private DKIM key """
        if self._dkim_key is None:
            file_path = self._dkim_file()
            if os.path.exists(file_path):
                with open(file_path, 'rb') as handle:
                    self._dkim_key = self._dkim_key_on_disk = handle.read()
            else:
                self._dkim_key = self._dkim_key_on_disk = b''
        return self._dkim_key if self._dkim_key else None

    @dkim_key.setter
    def dkim_key(self, value):
        """ set private DKIM key """
        old_key = self.dkim_key
        self._dkim_key = value if value is not None else b''
        if self._dkim_key != old_key:
            if not sqlalchemy.event.contains(db.session, 'after_commit', _save_dkim_keys):
                sqlalchemy.event.listen(db.session, 'after_commit', _save_dkim_keys)

    @property
    def dkim_publickey(self):
        """ return public part of DKIM key """
        dkim_key = self.dkim_key
        if dkim_key:
            return dkim.strip_key(dkim_key).decode('utf8')

    def generate_dkim_key(self):
        """ generate new DKIM key """
        self.dkim_key = dkim.gen_key()

    def has_email(self, localpart):
        """ checks if localpart is configured for domain """
        localpart = localpart.lower()
        for email in chain(self.users, self.aliases):
            if email.localpart.lower() == localpart:
                return True
        return False

    def check_mx(self):
        """ checks if MX record for domain points to mailu host """
        try:
            hostnames = set(app.config['HOSTNAMES'].split(','))
            return any(
                rset.exchange.to_text().rstrip('.') in hostnames
                for rset in dns.resolver.resolve(self.name, 'MX')
            )
        except dns.exception.DNSException:
            return False


class Alternative(Base):
    """ Alternative name for a served domain.
        The name "domain alias" was avoided to prevent some confusion.
    """

    __tablename__ = 'alternative'

    name = db.Column(IdnaDomain, primary_key=True, nullable=False)
    domain_name = db.Column(IdnaDomain, db.ForeignKey(Domain.name))
    domain = db.relationship(Domain,
        backref=db.backref('alternatives', cascade='all, delete-orphan'))

    @property
    def dns_dkim(self):
        """ return DKIM record for domain """
        if self.domain.dkim_key:
            selector = app.config['DKIM_SELECTOR']
            return f'{selector}._domainkey.{idna.encode(self.name.lower()).decode('ascii')}. 600 IN TXT "v=DKIM1; k=rsa; p={self.domain.dkim_publickey}"'

    @cached_property
    def dns_dmarc(self):
        """ return DMARC record for domain """
        if self.domain.dkim_key:
            domain = app.config['DOMAIN']
            rua = app.config['DMARC_RUA']
            rua = f' rua=mailto:{rua}@{idna.encode(domain.lower()).decode('ascii')};' if rua else ''
            ruf = app.config['DMARC_RUF']
            ruf = f' ruf=mailto:{ruf}@{idna.encode(domain.lower()).decode('ascii')};' if ruf else ''
            return f'_dmarc.{idna.encode(self.name.lower()).decode('ascii')}. 600 IN TXT "v=DMARC1; p=reject;{rua}{ruf} adkim=s; aspf=s"'

    @cached_property
    def dns_dmarc_report_needed(self):
        """ return true if DMARC report record is needed """
        return self.name != app.config['DOMAIN']

    @cached_property
    def dns_dmarc_report(self):
        """ return DMARC report record for mailu server """
        if self.domain.dkim_key:
            domain = app.config['DOMAIN']
            return f'{idna.encode(self.name.lower()).decode('ascii')}._report._dmarc.{idna.encode(domain.lower()).decode('ascii')}. 600 IN TXT "v=DMARC1;"'

    @cached_property
    def dns_mx(self):
        """ return MX record for domain """
        hostname = app.config['HOSTNAME']
        return f'{idna.encode(self.name.lower()).decode('ascii')}. 600 IN MX 10 {idna.encode(hostname.lower()).decode('ascii')}.'

    @cached_property
    def dns_spf(self):
        """ return SPF record for domain """
        hostname = app.config['HOSTNAME']
        return f'{idna.encode(self.name.lower()).decode('ascii')}. 600 IN TXT "v=spf1 mx a:{idna.encode(hostname.lower()).decode('ascii')} ~all"'

    def check_mx(self):
        """ checks if MX record for domain points to mailu host """
        try:
            hostnames = set(app.config['HOSTNAMES'].split(','))
            return any(
                rset.exchange.to_text().rstrip('.') in hostnames
                for rset in dns.resolver.resolve(self.name, 'MX')
            )
        except dns.exception.DNSException:
            return False


class Relay(Base):
    """ Relayed mail domain.
    The domain is either relayed publicly or through a specified SMTP host.
    """

    __tablename__ = 'relay'

    name = db.Column(IdnaDomain, primary_key=True, nullable=False)
    smtp = db.Column(db.String(80), nullable=True)


class MailAddress(db.Model):
    """Single active owner of a canonical routing address.

    This table enforces address uniqueness across the otherwise independent
    User and Alias primary-key namespaces. It is deliberately not a SCIM
    identity or tombstone table.
    """

    __tablename__ = 'mail_address'

    email = db.Column(IdnaEmail, primary_key=True, nullable=False)
    address_type = db.Column(db.String(5), nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            'email',
            'address_type',
            name='mail_address_email_type_key',
        ),
        db.CheckConstraint(
            "address_type IN ('user', 'alias')",
            name='mail_address_type_check',
        ),
    )


class Email(object):
    """ Abstraction for an email address (localpart and domain).
    """

    localpart = db.Column(db.String(80), nullable=False)

    @declarative.declared_attr
    def domain_name(cls):
        """ the domain part of the email address """
        return db.Column(IdnaDomain, db.ForeignKey(Domain.name),
            nullable=False, default=IdnaDomain)

    # This field is redundant with both localpart and domain name.
    # It is however very useful for quick lookups without joining tables,
    # especially when the mail server is reading the database.
    @declarative.declared_attr
    def _email(cls):
        """ the complete email address (localpart@domain) """

        def updater(ctx):
            key = f'{cls.__tablename__}_email'
            if key in ctx.current_parameters:
                return ctx.current_parameters[key]
            return '{localpart}@{domain_name}'.format_map(ctx.current_parameters)

        return db.Column('email', IdnaEmail, primary_key=True, nullable=False, onupdate=updater)

    # We need to keep email, localpart and domain_name in sync.
    # But IMHO using email as primary key was not a good idea in the first place.
    @hybrid_property
    def email(self):
        """ getter for email - gets _email """
        return self._email

    @email.setter
    def email(self, value):
        """ setter for email - sets _email, localpart and domain_name at once """
        self._email = value.lower()
        self.localpart, self.domain_name = self._email.rsplit('@', 1)

    @staticmethod
    def _update_localpart(target, value, *_):
        # email local parts are case-insensitive: keep them lowercased so the
        # localpart stays in sync with the (lowercased) email primary key (#2695)
        value = value.lower() if value else value
        if target.domain_name:
            target._email = f'{value}@{target.domain_name}'
        return value

    @staticmethod
    def _update_domain_name(target, value, *_):
        if target.localpart:
            target._email = f'{target.localpart}@{value}'

    @classmethod
    def __declare_last__(cls):
        # gets called after mappings are completed
        sqlalchemy.event.listen(cls.localpart, 'set', cls._update_localpart, propagate=True, retval=True)
        sqlalchemy.event.listen(cls.domain_name, 'set', cls._update_domain_name, propagate=True)

    def sendmail(self, subject, body):
        """ send an email to the address """
        try:
            f_addr = f'{app.config["POSTMASTER"]}@{idna.encode(app.config["DOMAIN"]).decode("ascii")}'
            with smtplib.LMTP(host=app.config['FRONT_ADDRESS'], port=2525) as lmtp:
                to_address = f'{self.localpart}@{idna.encode(self.domain_name).decode("ascii")}'
                msg = text.MIMEText(body)
                msg['Subject'] = subject
                msg['From'] = f_addr
                msg['To'] = to_address
                lmtp.sendmail(f_addr, [to_address], msg.as_string())
            return True
        except smtplib.SMTPException:
            return False

    @classmethod
    def resolve_domain(cls, email):
        """ resolves domain alternative to real domain """
        localpart, domain_name = email.rsplit('@', 1) if '@' in email else (None, email)
        if alternative := Alternative.query.get(domain_name):
            domain_name = alternative.domain_name
        return (localpart, domain_name)

    @staticmethod
    def _append_detail(address, detail):
        """ insert a recipient-delimiter detail into an address localpart """
        if not detail or '@' not in address:
            return address
        localpart, domain_name = address.rsplit('@', 1)
        return f'{localpart}{detail}@{domain_name}'

    @classmethod
    def resolve_destination(cls, localpart, domain_name, ignore_forward_keep=False):
        """ return destination for email address localpart@domain_name """

        localpart_stripped = None
        stripped_alias = None

        if delims := os.environ.get('RECIPIENT_DELIMITER'):
            try:
                pos = next(i for i, c in enumerate(localpart) if c in delims)
            except StopIteration:
                pass
            else:
                localpart_stripped = localpart[:pos]

        # is localpart@domain_name or localpart_stripped@domain_name an user?
        user = User.query.get(f'{localpart}@{domain_name}')
        if not user and localpart_stripped:
            user = User.query.get(f'{localpart_stripped}@{domain_name}')

        if user:
            email = f'{localpart}@{domain_name}'

            if not user.forward_enabled:
                return [email]

            destination = user.forward_destination
            if user.forward_keep or ignore_forward_keep:
                destination.append(email)
            return destination

        # is localpart, domain_name or localpart_stripped@domain_name an alias?
        if pure_alias := Alias.resolve(localpart, domain_name):
            if not pure_alias.wildcard:
                return pure_alias.destination

        if stripped_alias := Alias.resolve(localpart_stripped, domain_name):
            if stripped_alias.wildcard:
                return stripped_alias.destination
            # Re-attach the recipient delimiter detail (e.g. '+tag') that was
            # stripped for the lookup, so it is not lost for the recipient. This
            # mirrors postfix' propagate_unmatched_extensions for explicit aliases.
            detail = localpart[len(localpart_stripped):]
            return [cls._append_detail(dst, detail) for dst in stripped_alias.destination]

        if pure_alias:
            return pure_alias.destination

        return None


class User(Base, Email):
    """ A user is an email address that has a password to access a mailbox.
    """

    __tablename__ = 'user'
    ADDRESS_TYPE = 'user'
    _ctx = None
    _credential_cache = {}

    address_type = db.Column(
        db.String(5),
        nullable=False,
        default=ADDRESS_TYPE,
        server_default=ADDRESS_TYPE,
    )

    __table_args__ = (
        db.CheckConstraint(
            "address_type = 'user'",
            name='user_address_type_check',
        ),
        db.ForeignKeyConstraint(
            ['email', 'address_type'],
            ['mail_address.email', 'mail_address.address_type'],
            name='user_mail_address_fkey',
        ),
    )

    domain = db.relationship(Domain,
        backref=db.backref('users', cascade='all, delete-orphan'))
    password = db.Column(db.String(255), nullable=False)
    auth_generation = db.Column(
        db.String(32),
        nullable=False,
        default=lambda: secrets.token_hex(16),
    )
    quota_bytes = db.Column(db.BigInteger, nullable=False, default=10**9)
    quota_bytes_used = db.Column(db.BigInteger, nullable=False, default=0)
    global_admin = db.Column(db.Boolean, nullable=False, default=False)
    enabled = db.Column(db.Boolean, nullable=False, default=True)

    # Features
    enable_imap = db.Column(db.Boolean, nullable=False, default=True)
    enable_pop = db.Column(db.Boolean, nullable=False, default=True)
    allow_spoofing = db.Column(db.Boolean, nullable=False, default=False)

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
    spam_mark_as_read = db.Column(db.Boolean, nullable=False, default=True)
    spam_threshold = db.Column(db.Integer, nullable=False, default=lambda:int(app.config.get("DEFAULT_SPAM_THRESHOLD", 80)))
    change_pw_next_login = db.Column(db.Boolean, nullable=False, default=False)

    # Flask-login attributes
    is_authenticated = True
    is_anonymous = False

    @property
    def is_active(self):
        """Disabled users are not valid Flask-Login principals."""
        return bool(self.enabled)

    def get_id(self):
        """ return users email address """
        return self.email

    @property
    def destination(self):
        """ returns comma separated string of destinations """
        if self.forward_enabled:
            result = list(self.forward_destination)
            if self.forward_keep:
                result.append(self.email)
            return ','.join(result)
        else:
            return self.email

    @property
    def reply_active(self):
        """ returns status of autoreply function """
        now = date.today()
        return (
            self.reply_enabled and
            self.reply_startdate <= now and
            self.reply_enddate >= now
        )

    @property
    def sender_limiter(self):
        return utils.limiter.get_limiter(
            app.config["MESSAGE_RATELIMIT"], "sender", self.email
        )

    @classmethod
    def get_password_context(cls):
        """ create password context for hashing and verification
        """
        if cls._ctx:
            return cls._ctx

        # compile schemes
        # - skip scrypt (throws a warning if the native wheels aren't found)
        # - skip plaintext schemes (will be misidentified)
        schemes = [
            scheme for scheme in passlib.registry.list_crypt_handlers()
            if not (scheme == 'scrypt' or scheme.endswith('plaintext'))
        ]
        cls._ctx = passlib.context.CryptContext(
            schemes=schemes,
            default='bcrypt_sha256',
            bcrypt_sha256__rounds=app.config['CREDENTIAL_ROUNDS'],
            deprecated='auto'
        )
        return cls._ctx

    def check_password(self, password):
        """ verifies password against stored hash
            and updates hash if outdated
        """
        if password == '':
            return False
        cache_result = self._credential_cache.get(self.get_id())
        current_salt = self.password.split('$')[3] if len(self.password.split('$')) == 5 else None
        if cache_result and current_salt:
            cache_salt, cache_hash = cache_result
            if cache_salt == current_salt:
                return passlib.hash.pbkdf2_sha256.verify(password, cache_hash)
            else:
                # the cache is local per gunicorn; the password has changed
                # so the local cache can be invalidated
                del self._credential_cache[self.get_id()]
        reference = self.password
        # strip {scheme} if that's something mailu has added
        # passlib will identify *crypt based hashes just fine
        # on its own
        if reference.startswith(('{PBKDF2}', '{BLF-CRYPT}', '{SHA512-CRYPT}', '{SHA256-CRYPT}', '{MD5-CRYPT}', '{CRYPT}')):
            reference = reference.split('}', 1)[1]

        result, new_hash = User.get_password_context().verify_and_update(password, reference)
        if new_hash:
            self._preserve_auth_generation = True
            try:
                self.password = new_hash
            finally:
                del self._preserve_auth_generation
            db.session.add(self)
            db.session.commit()

        if result:
            """The credential cache uses a low number of rounds to be fast.
While it's not meant to be persisted to cold-storage, no additional measures
are taken to ensure it isn't (mlock(), encrypted swap, ...) on the basis that
we have little control over GC and string interning anyways.

 An attacker that can dump the process' memory is likely to find credentials
in clear-text regardless of the presence of the cache.
            """
            self._credential_cache[self.get_id()] = (self.password.split('$')[3], passlib.hash.pbkdf2_sha256.using(rounds=1).hash(password))
        return result

    def set_password(self, password, raw=False, keep_sessions=None):
        """Set a credential and rotate SQL-backed session authority.

            @password: plain text password to encrypt (or, if raw is True: the hash itself)
            @keep_sessions: retained for caller compatibility; physical session
              cleanup must run only after the surrounding SQL transaction commits.
        """
        replacement = (
            password
            if raw
            else User.get_password_context().hash(password)
        )
        self.password = replacement

    def rotate_auth_generation(self):
        """Invalidate every previously issued browser/webmail session."""
        self.auth_generation = secrets.token_hex(16)

    def get_managed_domains(self):
        """ return list of domains this user can manage """
        if self.global_admin:
            return Domain.query.all()
        else:
            return self.manager_of

    def get_managed_emails(self, include_aliases=True):
        """ returns list of email addresses this user can manage """
        emails = []
        for domain in self.get_managed_domains():
            emails.extend(domain.users)
            if include_aliases:
                emails.extend(domain.aliases)
        return emails

    def send_welcome(self):
        """ send welcome email to user """
        if app.config['WELCOME']:
            self.sendmail(app.config['WELCOME_SUBJECT'], app.config['WELCOME_BODY'])

    @classmethod
    def get(cls, email):
        """ find user object for email address """
        return cls.query.get(email)

    @classmethod
    def login(cls, email, password):
        """ login user when enabled and password is valid """
        user = cls.query.get(email)
        return user if (user and user.enabled and user.check_password(password)) else None


@sqlalchemy.event.listens_for(
    User.enabled,
    'set',
    active_history=True,
)
def _rotate_auth_generation_on_enabled_change(
    target,
    value,
    oldvalue,
    _initiator,
):
    """Make enablement changes invalidate sessions at the model boundary."""
    if (
        oldvalue is not sqlalchemy.orm.attributes.NO_VALUE
        and bool(value) != bool(oldvalue)
    ):
        target.rotate_auth_generation()


@sqlalchemy.event.listens_for(
    User.password,
    'set',
    active_history=True,
)
def _rotate_auth_generation_on_password_change(
    target,
    value,
    oldvalue,
    _initiator,
):
    """Catch every ORM credential writer, including Marshmallow imports."""
    if (
        oldvalue is not sqlalchemy.orm.attributes.NO_VALUE
        and oldvalue is not None
        and value != oldvalue
        and not getattr(target, '_preserve_auth_generation', False)
    ):
        target.rotate_auth_generation()


class Alias(Base, Email):
    """ An alias is an email address that redirects to some destination.
    """

    __tablename__ = 'alias'
    ADDRESS_TYPE = 'alias'

    address_type = db.Column(
        db.String(5),
        nullable=False,
        default=ADDRESS_TYPE,
        server_default=ADDRESS_TYPE,
    )

    __table_args__ = (
        db.CheckConstraint(
            "address_type = 'alias'",
            name='alias_address_type_check',
        ),
        db.ForeignKeyConstraint(
            ['email', 'address_type'],
            ['mail_address.email', 'mail_address.address_type'],
            name='alias_mail_address_fkey',
        ),
    )

    domain = db.relationship(Domain,
        backref=db.backref('aliases', cascade='all, delete-orphan'))
    wildcard = db.Column(db.Boolean, nullable=False, default=False)
    destination = db.Column(CommaSeparatedList, nullable=False, default=list)

    # Anonymous Email Service metadata
    hostname = db.Column(db.String(255), nullable=True)
    owner_email = db.Column(db.String(255), db.ForeignKey('user.email'), nullable=True)
    owner = db.relationship('User', backref=db.backref('owned_aliases', cascade='all, delete-orphan'))
    disabled = db.Column(db.Boolean, nullable=False, default=False)

    @classmethod
    def resolve(cls, localpart, domain_name):
        """ find aliases matching email address localpart@domain_name """

        # An alias is active if it is not explicitly disabled AND its owner
        # (if any) is enabled. These two flags are independent: disabling the
        # owner suspends delivery without touching alias.disabled, so
        # re-enabling the owner restores delivery automatically.
        owner_enabled = sqlalchemy.or_(
            cls.owner_email == None,
            sqlalchemy.exists().where(
                sqlalchemy.and_(
                    User.email == cls.owner_email,
                    User.enabled == True
                )
            )
        )

        alias_preserve_case = cls.query.filter(
                sqlalchemy.and_(cls.domain_name == domain_name, cls.disabled == False, owner_enabled,
                    sqlalchemy.or_(
                        sqlalchemy.and_(
                            cls.wildcard == False,
                            cls.localpart == localpart
                        ), sqlalchemy.and_(
                            cls.wildcard == True,
                            sqlalchemy.bindparam('l', localpart).like(cls.localpart)
                        )
                    )
                )
            ).order_by(cls.wildcard, sqlalchemy.func.char_length(cls.localpart).desc()).first()

        localpart_lower = localpart.lower() if localpart else None
        alias_lower_case = cls.query.filter(
                sqlalchemy.and_(cls.domain_name == domain_name, cls.disabled == False, owner_enabled,
                    sqlalchemy.or_(
                        sqlalchemy.and_(
                            cls.wildcard == False,
                            sqlalchemy.func.lower(cls.localpart) == localpart_lower
                        ), sqlalchemy.and_(
                            cls.wildcard == True,
                            sqlalchemy.bindparam('l', localpart_lower).like(
                                sqlalchemy.func.lower(cls.localpart))
                        )
                    )
                )
            ).order_by(cls.wildcard, sqlalchemy.func.char_length(
                sqlalchemy.func.lower(cls.localpart)).desc()).first()

        if alias_preserve_case and alias_lower_case:
            return alias_lower_case if alias_preserve_case.wildcard else alias_preserve_case

        if alias_preserve_case and not alias_lower_case:
            return alias_preserve_case

        if alias_lower_case and not alias_preserve_case:
            return alias_lower_case

        return None


# end of Alias class helpers


def _address_value(target):
    """Return and materialize the canonical email before mapper INSERT."""
    if target.email:
        return target.email
    domain_name = target.domain_name
    if not domain_name and target.domain is not None:
        domain_name = target.domain.name
    if not target.localpart or not domain_name:
        raise ValueError('User and Alias require a complete email address')
    target.email = f'{target.localpart}@{domain_name}'
    return target.email


def _claim_mail_address(_mapper, connection, target):
    email = _address_value(target)
    target.address_type = target.ADDRESS_TYPE
    graph_lock = globals().get('_lock_scim_graph_connection')
    destination_model = globals().get('ScimGroupDestination')
    if graph_lock is not None:
        graph_lock(connection)
    if (
        destination_model is not None
        and connection.execute(
            sqlalchemy.select(destination_model.group_id).where(
                destination_model.destination == email
            ).limit(1).with_for_update()
        ).first()
        is not None
    ):
        original = RuntimeError(
            f'Routing address {email!r} is reserved as an external '
            'destination'
        )
        raise AddressConflict(email, original) from original
    try:
        connection.execute(
            MailAddress.__table__.insert().values(
                email=email,
                address_type=target.ADDRESS_TYPE,
            )
        )
    except sqlalchemy.exc.IntegrityError as exc:
        raise AddressConflict(email, exc) from exc


def _reject_mail_address_rename(_mapper, _connection, target):
    if sqlalchemy.inspect(target).attrs._email.history.has_changes():
        raise AddressRenameError(
            f'Persisted email address {target.email} cannot be renamed'
        )


def _release_mail_address(_mapper, connection, target):
    connection.execute(
        MailAddress.__table__.delete().where(
            sqlalchemy.and_(
                MailAddress.email == target.email,
                MailAddress.address_type == target.ADDRESS_TYPE,
            )
        )
    )


for _address_model in (User, Alias):
    sqlalchemy.event.listen(
        _address_model,
        'before_insert',
        _claim_mail_address,
    )
    sqlalchemy.event.listen(
        _address_model,
        'before_update',
        _reject_mail_address_rename,
    )
    sqlalchemy.event.listen(
        _address_model,
        'after_delete',
        _release_mail_address,
    )


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
    ip = db.Column(CommaSeparatedList, nullable=True, default=list)

    def check_password(self, password):
        """ verifies password against stored hash
            and updates hash if outdated
        """
        if self.password.startswith("$5$"):
            if passlib.hash.sha256_crypt.verify(password, self.password):
                self.set_password(password)
                db.session.add(self)
                db.session.commit()
                return True
            return False
        return passlib.hash.pbkdf2_sha256.verify(password, self.password)

    def set_password(self, password):
        """ sets password using pbkdf2_sha256 (1 round) """
        # tokens have 128bits of entropy, they are not bruteforceable
        self.password = passlib.hash.pbkdf2_sha256.using(rounds=1).hash(password)

    def __repr__(self):
        return f'<Token #{self.id}: {self.comment or self.ip or self.password}>'


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
    scan = db.Column(db.Boolean, nullable=False, default=False)
    invisible = db.Column(db.Boolean, nullable=False, default=False)
    folders = db.Column(CommaSeparatedList, nullable=True, default=list)
    last_check = db.Column(db.DateTime, nullable=True)
    error = db.Column(db.String(1023), nullable=True)

    def __repr__(self):
        return (
            f'<Fetch #{self.id}: {self.protocol}{"s" if self.tls else ""}:'
            f'//{self.username}@{self.host}:{self.port}>'
        )


# Many-to-many association table for domain managers
managers = db.Table('manager', Base.metadata,
    db.Column('domain_name', IdnaDomain, db.ForeignKey(Domain.name)),
    db.Column('user_email', IdnaEmail, db.ForeignKey(User.email))
)


class DomainAccess(Base):
    """Per-user access grant to use Anonymous Email Service API for a domain"""

    __tablename__ = 'domain_access'
    __table_args__ = (
        db.UniqueConstraint('domain_name', 'user_email', name='uq_domain_access_user'),
    )

    id = db.Column(db.Integer, primary_key=True)
    domain_name = db.Column(IdnaDomain, db.ForeignKey(Domain.name), nullable=False)
    domain = db.relationship(Domain, backref=db.backref('domain_accesses', cascade='all, delete-orphan'))
    user_email = db.Column(IdnaEmail, db.ForeignKey(User.email), nullable=True)
    user = db.relationship(User, backref=db.backref('domain_accesses', cascade='all, delete-orphan'), foreign_keys=[user_email])

    def __repr__(self):
        return f'<DomainAccess {self.domain_name} for {self.user_email}>'


def has_domain_access(domain_name, user=None):
    """Return True if the given user has access to domain_name.
    Administrators implicitly have access to all domains.
    """
    if user is not None and getattr(user, 'global_admin', False):
        return True
    
    if user is not None:
        domain = Domain.query.get(domain_name)
        if domain and domain.managers.filter_by(email=user.email).first():
            return True

    if user is None:
        return False

    query = DomainAccess.query.filter(
        DomainAccess.domain_name == domain_name,
        DomainAccess.user_email == user.email
    )
    return db.session.query(query.exists()).scalar()


class ScimIdentityError(RuntimeError):
    """Base error for persistent SCIM identity invariants."""


class ScimGraphError(ScimIdentityError):
    """Raised when a normalized Group graph would be invalid."""


class ScimManagedAliasError(ScimIdentityError):
    """Raised when an ordinary writer mutates a SCIM-owned Alias."""


class ScimGroupAdoptionError(ScimIdentityError):
    """Raised when an Alias cannot safely enter exclusive SCIM ownership."""


class ScimExternalDestinationError(ScimIdentityError):
    """Raised when a raw destination conflicts with local routing ownership."""


class ScimState(db.Model):
    """Singleton row used to serialize every normalized graph mutation."""

    __tablename__ = 'scim_state'

    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    revision = db.Column(db.BigInteger, nullable=False, default=0)

    __table_args__ = (
        db.CheckConstraint('id = 1', name='scim_state_singleton_check'),
    )


class ScimResource(Base):
    """Stable provider identity and ownership marker for a SCIM resource."""

    __tablename__ = 'scim_resource'

    id = db.Column(ExactScimId(), primary_key=True, nullable=False)
    resource_type = db.Column(db.String(5), nullable=False)
    external_id_bytes = db.Column(db.LargeBinary(1024), nullable=True)
    user_email = db.Column(
        IdnaEmail,
        db.ForeignKey(User.email),
        nullable=True,
        unique=True,
    )
    alias_email = db.Column(
        IdnaEmail,
        db.ForeignKey(Alias.email),
        nullable=True,
        unique=True,
    )
    subject_address = db.Column(IdnaEmail, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship(
        User,
        foreign_keys=[user_email],
        backref=db.backref(
            'scim_resource',
            uselist=False,
            passive_deletes=True,
        ),
    )
    alias = db.relationship(
        Alias,
        foreign_keys=[alias_email],
        backref=db.backref(
            'scim_resource',
            uselist=False,
            passive_deletes=True,
        ),
    )

    __table_args__ = (
        db.CheckConstraint(
            "resource_type IN ('User', 'Group')",
            name='scim_resource_type_check',
        ),
        db.CheckConstraint(
            '('
            "deleted_at IS NULL AND resource_type = 'User' "
            'AND user_email IS NOT NULL AND alias_email IS NULL '
            'AND subject_address = user_email'
            ') OR ('
            "deleted_at IS NULL AND resource_type = 'Group' "
            'AND user_email IS NULL AND alias_email IS NOT NULL '
            'AND subject_address = alias_email'
            ') OR ('
            'deleted_at IS NOT NULL '
            'AND user_email IS NULL AND alias_email IS NULL'
            ')',
            name='scim_resource_lifecycle_check',
        ),
    )

    @property
    def external_id(self):
        if self.external_id_bytes is None:
            return None
        return self.external_id_bytes.decode('utf-8')

    @external_id.setter
    def external_id(self, value):
        if value is None:
            self.external_id_bytes = None
            return
        if not isinstance(value, str):
            raise TypeError('externalId must be a string or null')
        encoded = value.encode('utf-8')
        if len(encoded) > 1024:
            raise ValueError('externalId must not exceed 1024 UTF-8 bytes')
        self.external_id_bytes = encoded

    @property
    def active(self):
        return self.deleted_at is None

    @classmethod
    def get_exact(cls, resource_id, *, resource_type=None, active_only=True):
        """Fetch an opaque ID without trusting a case-insensitive collation."""
        if not isinstance(resource_id, str):
            return None
        resource = db.session.get(cls, resource_id)
        if resource is None or resource.id != resource_id:
            return None
        if resource_type is not None and resource.resource_type != resource_type:
            return None
        if active_only and resource.deleted_at is not None:
            return None
        return resource


class ScimGroupMember(db.Model):
    """Stable normalized edge from one managed Group to a SCIM resource."""

    __tablename__ = 'scim_group_member'

    group_id = db.Column(
        ExactScimId(),
        db.ForeignKey(ScimResource.id),
        primary_key=True,
    )
    member_id = db.Column(
        ExactScimId(),
        db.ForeignKey(ScimResource.id),
        primary_key=True,
    )

    group = db.relationship(
        ScimResource,
        foreign_keys=[group_id],
        backref=db.backref(
            'member_edges',
            cascade='all, delete-orphan',
        ),
    )
    member = db.relationship(
        ScimResource,
        foreign_keys=[member_id],
        backref=db.backref(
            'membership_edges',
            cascade='all, delete-orphan',
        ),
    )


class ScimGroupDestination(db.Model):
    """Raw, non-local forwarding destination owned by a managed Group."""

    __tablename__ = 'scim_group_destination'

    group_id = db.Column(
        ExactScimId(),
        db.ForeignKey(ScimResource.id),
        primary_key=True,
    )
    destination = db.Column(IdnaEmail, primary_key=True)

    __table_args__ = (
        db.Index(
            'scim_group_destination_destination_idx',
            'destination',
        ),
    )

    group = db.relationship(
        ScimResource,
        foreign_keys=[group_id],
        backref=db.backref(
            'destinations',
            cascade='all, delete-orphan',
        ),
    )


@sqlalchemy.event.listens_for(ScimState.__table__, 'after_create')
def _seed_scim_state(_target, connection, **_kwargs):
    connection.execute(
        ScimState.__table__.insert().values(id=1, revision=0)
    )


def new_scim_id():
    """Return the one canonical representation used for new provider IDs."""
    return str(uuid.uuid4()).lower()


def _lock_scim_graph_connection(connection):
    result = connection.execute(
        ScimState.__table__.update().where(
            ScimState.id == 1
        ).values(
            revision=ScimState.revision,
        )
    )
    if result.rowcount != 1:
        raise ScimGraphError('SCIM graph state row is missing')


def lock_scim_graph(session=None):
    """Acquire the portable singleton graph write lock for this transaction."""
    session = session or db.session
    result = session.execute(
        ScimState.__table__.update().where(
            ScimState.id == 1
        ).values(
            revision=ScimState.revision,
        )
    )
    if result.rowcount != 1:
        raise ScimGraphError('SCIM graph state row is missing')


def create_scim_user_mapping(
    user,
    *,
    resource_id=None,
    external_id=None,
):
    """Return or create the active mapping for a persistent User."""
    if inspect(user).persistent is False:
        raise ScimIdentityError(
            'User must be persistent before its SCIM mapping is created'
        )
    lock_scim_graph()
    existing = db.session.execute(
        sqlalchemy.select(ScimResource)
        .where(
            ScimResource.resource_type == 'User',
            ScimResource.user_email == user.email,
            ScimResource.deleted_at.is_(None),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if existing is not None:
        if existing.deleted_at is not None:
            raise ScimIdentityError(
                f'User {user.email} has a deleted SCIM mapping'
            )
        if resource_id is not None and resource_id != existing.id:
            raise ScimIdentityError(
                f'User {user.email} already has a different SCIM mapping'
            )
        if external_id is not None:
            existing.external_id = external_id
        return existing
    reserved = db.session.execute(
        sqlalchemy.select(ScimResource)
        .where(
            ScimResource.resource_type == 'User',
            ScimResource.subject_address == user.email,
            ScimResource.deleted_at.is_not(None),
        )
        .limit(1)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if reserved is not None:
        raise ScimIdentityError(
            f'User address {user.email} is permanently reserved by a '
            'deleted SCIM identity'
        )
    resource = ScimResource(
        id=resource_id or new_scim_id(),
        resource_type='User',
        user=user,
        subject_address=user.email,
    )
    resource.external_id = external_id
    db.session.add(resource)
    return resource


def validate_scim_group_adoption(alias):
    """Require a live, exact, unowned Alias before exclusive adoption."""
    if inspect(alias).persistent is False:
        raise ScimGroupAdoptionError('Alias must be persistent before adoption')
    if alias.disabled:
        raise ScimGroupAdoptionError('Disabled Alias cannot be adopted')
    if alias.wildcard:
        raise ScimGroupAdoptionError('Wildcard Alias cannot be adopted')
    if alias.owner_email is not None:
        raise ScimGroupAdoptionError('Owned Alias cannot be adopted')
    if alias.scim_resource is not None:
        raise ScimGroupAdoptionError('Alias is already SCIM managed')
    return alias


def create_scim_group_mapping(
    alias,
    *,
    resource_id=None,
    external_id=None,
):
    """Adopt an existing Alias; graph initialization remains explicit."""
    lock_scim_graph()
    alias = db.session.execute(
        sqlalchemy.select(Alias)
        .where(Alias._email == alias.email)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if alias is None:
        raise ScimGroupAdoptionError('Alias disappeared during adoption')
    existing_mapping = db.session.execute(
        sqlalchemy.select(ScimResource.id)
        .where(
            ScimResource.alias_email == alias.email,
            ScimResource.deleted_at.is_(None),
        )
        .limit(1)
        .with_for_update()
    ).first()
    if existing_mapping is not None:
        raise ScimGroupAdoptionError('Alias is already SCIM managed')
    validate_scim_group_adoption(alias)
    resource = ScimResource(
        id=resource_id or alias.email,
        resource_type='Group',
        alias=alias,
        subject_address=alias.email,
    )
    resource.external_id = external_id
    db.session.add(resource)
    return resource


def scrub_scim_user_authority(user):
    """Remove identity-bound authority before retaining a deleted mailbox."""
    user.global_admin = False
    user.allow_spoofing = False
    user.forward_enabled = False
    user.forward_destination = []
    user.forward_keep = True
    user.reply_enabled = False
    user.reply_subject = None
    user.reply_body = None
    user.reply_startdate = date(1900, 1, 1)
    user.reply_enddate = date(2999, 12, 31)
    user.set_password(secrets.token_urlsafe(48))
    for token in list(user.tokens):
        db.session.delete(token)
    for fetch in list(user.fetches):
        db.session.delete(fetch)
    for alias in list(user.owned_aliases):
        db.session.delete(alias)
    for access in list(user.domain_accesses):
        db.session.delete(access)
    db.session.execute(
        managers.delete().where(managers.c.user_email == user.email)
    )


def canonicalize_scim_destination(value):
    if not isinstance(value, str):
        raise ScimExternalDestinationError(
            'External destinations must be strings'
        )
    value = value.strip().lower()
    if not value or ',' in value or value.count('@') != 1:
        raise ScimExternalDestinationError(
            f'Invalid external destination {value!r}'
        )
    localpart, domain_name = value.rsplit('@', 1)
    if not localpart or not domain_name:
        raise ScimExternalDestinationError(
            f'Invalid external destination {value!r}'
        )
    try:
        domain_name = idna.decode(idna.encode(domain_name))
    except idna.IDNAError as exc:
        raise ScimExternalDestinationError(
            f'Invalid external destination {value!r}'
        ) from exc
    destination = f'{localpart}@{domain_name}'
    if not validators.email(destination):
        raise ScimExternalDestinationError(
            f'Invalid external destination {value!r}'
        )
    return destination


def _active_scim_resource(resource_id):
    resource = db.session.execute(
        sqlalchemy.select(ScimResource)
        .where(ScimResource.id == resource_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if (
        resource is None
        or resource.id != resource_id
        or resource.deleted_at is not None
    ):
        raise ScimGraphError(
            f'SCIM member {resource_id!r} is not an active resource'
        )
    return resource


def _validate_scim_cycle(group, member_ids):
    adjacency = {}
    edges = db.session.execute(
        sqlalchemy.select(
            ScimGroupMember.group_id,
            ScimGroupMember.member_id,
        ).with_for_update()
    ).all()
    for group_id, member_id in edges:
        if group_id == group.id:
            continue
        adjacency.setdefault(group_id, set()).add(member_id)
    adjacency[group.id] = set(member_ids)

    def reaches_group(resource_id, seen):
        if resource_id == group.id:
            return True
        if resource_id in seen:
            return False
        seen.add(resource_id)
        return any(
            reaches_group(child_id, seen)
            for child_id in adjacency.get(resource_id, ())
        )

    if any(reaches_group(member_id, set()) for member_id in member_ids):
        raise ScimGraphError('SCIM Group membership would create a cycle')


def permit_scim_managed_alias_edit(alias):
    """Permit exactly one pending flush of a managed Alias mutation."""
    session = inspect(alias).session
    if session is None:
        raise ScimManagedAliasError('Managed Alias is detached')
    session.info.setdefault('_scim_alias_edit_permits', set()).add(id(alias))


def materialize_scim_group(group):
    """Project normalized members and raw destinations into Alias.destination."""
    if (
        group.resource_type != 'Group'
        or group.deleted_at is not None
        or group.alias is None
    ):
        raise ScimGraphError('Only an active Group can be materialized')

    destinations = set(db.session.execute(
        sqlalchemy.select(ScimResource.subject_address)
        .join(
            ScimGroupMember,
            ScimGroupMember.member_id == ScimResource.id,
        )
        .where(
            ScimGroupMember.group_id == group.id,
            ScimResource.deleted_at.is_(None),
        )
        .with_for_update()
    ).scalars())
    destinations.update(db.session.execute(
        sqlalchemy.select(ScimGroupDestination.destination)
        .where(ScimGroupDestination.group_id == group.id)
        .with_for_update()
    ).scalars()
    )
    projection = sorted(destinations)
    if any(',' in destination for destination in projection):
        raise ScimGraphError('Group destinations cannot contain commas')
    if len(','.join(projection)) > 1023:
        raise ScimGraphError(
            'Materialized Group destinations exceed 1023 characters'
        )
    permit_scim_managed_alias_edit(group.alias)
    group.alias.destination = projection
    return projection


def replace_scim_group_graph(
    group,
    *,
    member_ids,
    external_destinations,
):
    """Atomically stage and materialize one complete managed Group graph."""
    if not isinstance(group, ScimResource):
        raise TypeError('group must be a ScimResource')
    if (
        group.resource_type != 'Group'
        or group.deleted_at is not None
        or group.alias is None
    ):
        raise ScimGraphError('Only an active Group can own graph state')
    lock_scim_graph()

    member_ids = list(dict.fromkeys(member_ids or ()))
    members = [_active_scim_resource(member_id) for member_id in member_ids]
    _validate_scim_cycle(group, member_ids)

    normalized_destinations = sorted({
        canonicalize_scim_destination(value)
        for value in (external_destinations or ())
    })
    for destination in normalized_destinations:
        local = db.session.execute(
            sqlalchemy.select(MailAddress.email)
            .where(MailAddress.email == destination)
            .with_for_update()
        ).scalar_one_or_none()
        if local is not None:
            raise ScimExternalDestinationError(
                f'External destination {destination!r} is locally owned'
            )

    db.session.execute(
        sqlalchemy.delete(ScimGroupMember).where(
            ScimGroupMember.group_id == group.id
        )
    )
    db.session.execute(
        sqlalchemy.delete(ScimGroupDestination).where(
            ScimGroupDestination.group_id == group.id
        )
    )
    db.session.add_all(
        ScimGroupMember(group=group, member=member)
        for member in members
    )
    db.session.add_all(
        ScimGroupDestination(group=group, destination=destination)
        for destination in normalized_destinations
    )
    materialize_scim_group(group)
    return group


def _remove_scim_resource_edges(resource):
    membership_edges = db.session.execute(
        sqlalchemy.select(ScimGroupMember)
        .where(ScimGroupMember.member_id == resource.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalars().all()
    member_edges = db.session.execute(
        sqlalchemy.select(ScimGroupMember)
        .where(ScimGroupMember.group_id == resource.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalars().all()
    destinations = db.session.execute(
        sqlalchemy.select(ScimGroupDestination)
        .where(ScimGroupDestination.group_id == resource.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalars().all()
    affected_ids = {
        edge.group_id
        for edge in membership_edges
    }
    affected_groups = db.session.execute(
        sqlalchemy.select(ScimResource)
        .where(
            ScimResource.id.in_(affected_ids),
            ScimResource.deleted_at.is_(None),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalars().all() if affected_ids else []
    db.session.execute(
        sqlalchemy.delete(ScimGroupMember).where(
            ScimGroupMember.member_id == resource.id
        )
    )
    db.session.execute(
        sqlalchemy.delete(ScimGroupMember).where(
            ScimGroupMember.group_id == resource.id
        )
    )
    db.session.execute(
        sqlalchemy.delete(ScimGroupDestination).where(
            ScimGroupDestination.group_id == resource.id
        )
    )
    return affected_groups


def tombstone_scim_resource(
    resource,
    *,
    retain_subject=True,
    scrub_user_authority=False,
):
    """Detach one active mapping while retaining its provider ID forever."""
    if resource.deleted_at is not None:
        raise ScimIdentityError(f'SCIM resource {resource.id} is already deleted')
    lock_scim_graph()
    user = resource.user
    affected_groups = _remove_scim_resource_edges(resource)

    if user is not None and retain_subject:
        user.enabled = False
        if scrub_user_authority:
            scrub_scim_user_authority(user)

    resource.user = None
    resource.alias = None
    resource.user_email = None
    resource.alias_email = None
    resource.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)

    for group in affected_groups:
        if group not in db.session.deleted and group.deleted_at is None:
            materialize_scim_group(group)
    return resource


def _create_scim_mapping_after_user_insert(_mapper, connection, target):
    _lock_scim_graph_connection(connection)
    connection.execute(
        ScimResource.__table__.insert().values(
            id=new_scim_id(),
            resource_type='User',
            user_email=target.email,
            alias_email=None,
            subject_address=target.email,
            deleted_at=None,
            created_at=date.today(),
            updated_at=None,
            comment='',
        )
    )


@sqlalchemy.event.listens_for(ScimResource, 'before_update')
def _reject_scim_identity_change(_mapper, _connection, target):
    state = inspect(target)
    for attribute in ('id', 'resource_type', 'subject_address'):
        if state.attrs[attribute].history.has_changes():
            raise ScimIdentityError(
                f'SCIM resource {attribute} is immutable'
            )
    deleted_history = state.attrs.deleted_at.history
    was_deleted = (
        deleted_history.deleted[-1]
        if deleted_history.deleted
        else target.deleted_at
    )
    lifecycle_attributes = (
        'external_id_bytes',
        'user_email',
        'alias_email',
        'deleted_at',
    )
    if was_deleted is not None:
        if any(
            state.attrs[attribute].history.has_changes()
            for attribute in lifecycle_attributes
        ):
            raise ScimIdentityError(
                f'SCIM resource {target.id} tombstone is immutable'
            )
        return
    transitioning_to_tombstone = (
        target.deleted_at is not None
        and target.user_email is None
        and target.alias_email is None
    )
    if (
        any(
            state.attrs[attribute].history.has_changes()
            for attribute in ('user_email', 'alias_email', 'deleted_at')
        )
        and not transitioning_to_tombstone
    ):
        raise ScimIdentityError(
            f'SCIM resource {target.id} principal binding is immutable'
        )


@sqlalchemy.event.listens_for(ScimResource, 'before_delete')
def _reject_scim_resource_hard_delete(_mapper, _connection, target):
    raise ScimIdentityError(
        f'SCIM resource {target.id} must be retained as a tombstone'
    )


@sqlalchemy.event.listens_for(sqlalchemy.orm.Session, 'before_flush')
def _maintain_scim_identity_lifecycle(session, _flush_context, _instances):
    permits = session.info.setdefault('_scim_alias_edit_permits', set())
    deleted = set(session.deleted)

    dirty_aliases = [
        value for value in session.dirty
        if isinstance(value, Alias) and value not in deleted
    ]
    address_deletes = [
        value for value in deleted
        if isinstance(value, (User, Alias))
    ]
    if dirty_aliases or address_deletes:
        lock_scim_graph(session)

    for alias in dirty_aliases:
        state = inspect(alias)
        changed = any(
            state.attrs[property_.key].history.has_changes()
            for property_ in state.mapper.column_attrs
            if property_.key not in ('created_at', 'updated_at')
        )
        if not changed:
            continue
        managed = session.execute(
            sqlalchemy.select(ScimResource)
            .where(
                ScimResource.alias_email == alias.email,
                ScimResource.deleted_at.is_(None),
            )
            .limit(1)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if managed is not None and managed.deleted_at is None:
            if id(alias) not in permits:
                raise ScimManagedAliasError(
                    f'Alias {alias.email} is exclusively SCIM managed'
                )
            permits.discard(id(alias))

    mapped_deletes = []
    with session.no_autoflush:
        for target in deleted:
            if isinstance(target, User):
                resource = session.execute(
                    sqlalchemy.select(ScimResource).where(
                        ScimResource.user_email == target.email,
                        ScimResource.deleted_at.is_(None),
                    ).with_for_update().execution_options(
                        populate_existing=True
                    )
                ).scalar_one_or_none()
            elif isinstance(target, Alias):
                resource = session.execute(
                    sqlalchemy.select(ScimResource).where(
                        ScimResource.alias_email == target.email,
                        ScimResource.deleted_at.is_(None),
                    ).with_for_update().execution_options(
                        populate_existing=True
                    )
                ).scalar_one_or_none()
                if resource is not None and resource.deleted_at is None:
                    raise ScimManagedAliasError(
                        f'Alias {target.email} is exclusively SCIM managed'
                    )
                continue
            else:
                continue
            if resource is not None:
                mapped_deletes.append(resource)

    for resource in mapped_deletes:
        tombstone_scim_resource(
            resource,
            retain_subject=False,
            scrub_user_authority=False,
        )


@sqlalchemy.event.listens_for(sqlalchemy.orm.Session, 'after_flush')
def _clear_scim_alias_edit_permits(session, _flush_context):
    session.info.pop('_scim_alias_edit_permits', None)


@sqlalchemy.event.listens_for(sqlalchemy.orm.Session, 'after_rollback')
def _clear_scim_alias_edit_permits_after_rollback(session):
    session.info.pop('_scim_alias_edit_permits', None)


@sqlalchemy.event.listens_for(sqlalchemy.orm.Session, 'after_soft_rollback')
def _clear_scim_alias_edit_permits_after_soft_rollback(
    session,
    _previous_transaction,
):
    session.info.pop('_scim_alias_edit_permits', None)


sqlalchemy.event.listen(
    User,
    'after_insert',
    _create_scim_mapping_after_user_insert,
)


class MailuConfig:
    """ Class which joins whole Mailu config for dumping
        and loading
    """

    class MailuCollection:
        """ Provides dict- and list-like access to instances
            of a sqlalchemy model
        """

        def __init__(self, model : db.Model):
            self.model = model

        def __repr__(self):
            return f'<{self.model.__name__}-Collection>'

        @cached_property
        def _items(self):
            return {
                inspect(item).identity: item
                for item in self.model.query.all()
            }

        def __len__(self):
            return len(self._items)

        def __iter__(self):
            return iter(self._items.values())

        def __getitem__(self, key):
            return self._items[key]

        def __setitem__(self, key, item):
            if not isinstance(item, self.model):
                raise TypeError(f'expected {self.model.name}')
            if key != inspect(item).identity:
                raise ValueError(f'item identity != key {key!r}')
            self._items[key] = item

        def __delitem__(self, key):
            del self._items[key]

        def append(self, item, update=False):
            """ list-like append """
            if not isinstance(item, self.model):
                raise TypeError(f'expected {self.model.name}')
            key = inspect(item).identity
            if key in self._items:
                if not update:
                    raise ValueError(f'item {key!r} already present in collection')
            self._items[key] = item

        def extend(self, items, update=False):
            """ list-like extend """
            add = {}
            for item in items:
                if not isinstance(item, self.model):
                    raise TypeError(f'expected {self.model.name}')
                key = inspect(item).identity
                if not update and key in self._items:
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
            if not isinstance(item, self.model):
                raise TypeError(f'expected {self.model.name}')
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
                if not isinstance(item, self.model):
                    raise TypeError(f'expected {self.model.name}')
                if key != inspect(item).identity:
                    raise ValueError(f'item identity != key {key!r}')
            self._items.update(items)

        def setdefault(self, key, item=None):
            """ dict-like setdefault """
            if key in self._items:
                return self._items[key]
            if item is None:
                return None
            if not isinstance(item, self.model):
                raise TypeError(f'expected {self.model.name}')
            if key != inspect(item).identity:
                raise ValueError(f'item identity != key {key!r}')
            self._items[key] = item
            return item

    def __init__(self):
        # The class attributes below are collection templates. Each config
        # object needs fresh collections: sharing the cached query results
        # leaks detached ORM instances across app/session lifetimes.
        self._sections = {}
        for name in dir(type(self)):
            template = getattr(type(self), name)
            if isinstance(template, self.MailuCollection):
                section = self.MailuCollection(template.model)
                setattr(self, name, section)
                self._sections[name] = section

        # known models
        self._models = tuple(section.model for section in self._sections.values())

        # model -> attr
        self._sections.update({
            section.model: section for section in self._sections.values()
        })

    def _get_model(self, section):
        if section is None:
            return None
        model = self._sections.get(section)
        if model is None:
            raise ValueError(f'Invalid section: {section!r}')
        if isinstance(model, self.MailuCollection):
            return model.model
        return model

    def _add(self, items, section, update):

        model = self._get_model(section)
        if isinstance(items, self._models):
            items = [items]
        elif not hasattr(items, '__iter__'):
            raise ValueError(f'{items!r} is not iterable')

        for item in items:
            if model is not None and not isinstance(item, model):
                what = item.__class__.__name__.capitalize()
                raise ValueError(f'{what} can not be added to section {section!r}')
            self._sections[type(item)].append(item, update=update)

    def add(self, items, section=None):
        """ add item to config """
        self._add(items, section, update=False)

    def update(self, items, section=None):
        """ add or replace item in config """
        self._add(items, section, update=True)

    def remove(self, items, section=None):
        """ remove item from config """
        model = self._get_model(section)
        if isinstance(items, self._models):
            items = [items]
        elif not hasattr(items, '__iter__'):
            raise ValueError(f'{items!r} is not iterable')

        for item in items:
            if isinstance(item, str):
                if section is None:
                    raise ValueError(f'Cannot remove key {item!r} without section')
                del self._sections[model][item]
            elif model is not None and not isinstance(item, model):
                what = item.__class__.__name__.capitalize()
                raise ValueError(f'{what} can not be removed from section {section!r}')
            self._sections[type(item)].remove(item,)

    def clear(self, models=None):
        """ remove complete configuration """
        # Delete via the ORM (load + session.delete) instead of a bulk
        # query(model).delete(). Bulk deletes neither honour FK ordering nor
        # trigger ORM cascades / many-to-many (manager) secondary cleanup, so on
        # a FK-enforcing backend (e.g. PostgreSQL) "DELETE FROM domain" fails
        # while users/aliases/managers still reference it (#2715). Loading the
        # rows lets the unit-of-work emit deletes in dependency order and
        # cascade to dependent rows. The explicit flush keeps the tables
        # physically empty before the new configuration is loaded.
        for model in self._models:
            if models is None or model in models:
                for item in model.query.all():
                    db.session.delete(item)
        db.session.flush()

    def check(self):
        """ check for duplicate domain names """
        dup = set()
        for fqdn in chain(
            db.session.query(Domain.name),
            db.session.query(Alternative.name),
            db.session.query(Relay.name)
        ):
            if fqdn in dup:
                raise ValueError(f'Duplicate domain name: {fqdn}')
            dup.add(fqdn)

    domain = MailuCollection(Domain)
    user = MailuCollection(User)
    alias = MailuCollection(Alias)
    relay = MailuCollection(Relay)
    config = MailuCollection(Config)
