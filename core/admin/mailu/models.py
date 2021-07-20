""" Mailu config storage model
"""

import os
import smtplib
import json

from datetime import date
from email.mime import text
from itertools import chain

import flask_sqlalchemy
import sqlalchemy
import passlib.context
import passlib.hash
import passlib.registry
import time
import os
import hmac
import smtplib
import idna
import dns

from flask import current_app as app
from sqlalchemy.ext import declarative
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.inspection import inspect
from werkzeug.utils import cached_property

from mailu import dkim


db = flask_sqlalchemy.SQLAlchemy()


class IdnaDomain(db.TypeDecorator):
    """ Stores a Unicode string in it's IDNA representation (ASCII only)
    """

    impl = db.String(80)

    def process_bind_param(self, value, dialect):
        """ encode unicode domain name to punycode """
        return idna.encode(value.lower()).decode('ascii')

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
        localpart, domain_name = value.rsplit('@', 1)
        if '@' in localpart:
            raise ValueError('email local part must not contain "@"')
        domain_name = domain_name.lower()
        return f'{localpart}@{idna.encode(domain_name).decode("ascii")}'

    def process_result_value(self, value, dialect):
        """ decode punycode domain part of email to unicode """
        localpart, domain_name = value.rsplit('@', 1)
        return f'{localpart}@{idna.decode(domain_name)}'

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
                raise ValueError('list item must not contain ","')
        return ','.join(sorted(set(value)))

    def process_result_value(self, value, dialect):
        """ split comma separated string to list """
        return list(filter(bool, (item.strip() for item in value.split(',')))) if value else []

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


def _save_dkim_keys(session):
    """ store DKIM keys after commit """
    for obj in session.identity_map.values():
        if isinstance(obj, Domain):
            obj.save_dkim_key()

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

    @property
    def dns_mx(self):
        """ return MX record for domain """
        hostname = app.config['HOSTNAMES'].split(',', 1)[0]
        return f'{self.name}. 600 IN MX 10 {hostname}.'

    @property
    def dns_spf(self):
        """ return SPF record for domain """
        hostname = app.config['HOSTNAMES'].split(',', 1)[0]
        return f'{self.name}. 600 IN TXT "v=spf1 mx a:{hostname} ~all"'

    @property
    def dns_dkim(self):
        """ return DKIM record for domain """
        if self.dkim_key:
            selector = app.config['DKIM_SELECTOR']
            return (
                f'{selector}._domainkey.{self.name}. 600 IN TXT'
                f'"v=DKIM1; k=rsa; p={self.dkim_publickey}"'
            )

    @property
    def dns_dmarc(self):
        """ return DMARC record for domain """
        if self.dkim_key:
            domain = app.config['DOMAIN']
            rua = app.config['DMARC_RUA']
            rua = f' rua=mailto:{rua}@{domain};' if rua else ''
            ruf = app.config['DMARC_RUF']
            ruf = f' ruf=mailto:{ruf}@{domain};' if ruf else ''
            return f'_dmarc.{self.name}. 600 IN TXT "v=DMARC1; p=reject;{rua}{ruf} adkim=s; aspf=s"'

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
        """ generate and activate new DKIM key """
        self.dkim_key = dkim.gen_key()

    def has_email(self, localpart):
        """ checks if localpart is configured for domain """
        for email in chain(self.users, self.aliases):
            if email.localpart == localpart:
                return True
        return False

    def check_mx(self):
        """ checks if MX record for domain points to mailu host """
        try:
            hostnames = set(app.config['HOSTNAMES'].split(','))
            return any(
                rset.exchange.to_text().rstrip('.') in hostnames
                for rset in dns.resolver.query(self.name, 'MX')
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


class Relay(Base):
    """ Relayed mail domain.
    The domain is either relayed publicly or through a specified SMTP host.
    """

    __tablename__ = 'relay'

    name = db.Column(IdnaDomain, primary_key=True, nullable=False)
    smtp = db.Column(db.String(80), nullable=True)


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
        self.localpart, self.domain_name = value.rsplit('@', 1)
        self._email = value

    @staticmethod
    def _update_localpart(target, value, *_):
        if target.domain_name:
            target._email = f'{value}@{target.domain_name}'

    @staticmethod
    def _update_domain_name(target, value, *_):
        if target.localpart:
            target._email = f'{target.localpart}@{value}'

    @classmethod
    def __declare_last__(cls):
        # gets called after mappings are completed
        sqlalchemy.event.listen(User.localpart, 'set', cls._update_localpart, propagate=True)
        sqlalchemy.event.listen(User.domain_name, 'set', cls._update_domain_name, propagate=True)

    def sendmail(self, subject, body):
        """ send an email to the address """
        f_addr = f'{app.config["POSTMASTER"]}@{idna.encode(app.config["DOMAIN"]).decode("ascii")}'
        with smtplib.SMTP(app.config['HOST_AUTHSMTP'], port=10025) as smtp:
            to_address = f'{self.localpart}@{idna.encode(self.domain_name).decode("ascii")}'
            msg = text.MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = f_addr
            msg['To'] = to_address
            smtp.sendmail(f_addr, [to_address], msg.as_string())

    @classmethod
    def resolve_domain(cls, email):
        """ resolves domain alternative to real domain """
        localpart, domain_name = email.rsplit('@', 1) if '@' in email else (None, email)
        alternative = Alternative.query.get(domain_name)
        if alternative:
            domain_name = alternative.domain_name
        return (localpart, domain_name)

    @classmethod
    def resolve_destination(cls, localpart, domain_name, ignore_forward_keep=False):
        """ return destination for email address localpart@domain_name """

        localpart_stripped = None
        stripped_alias = None

        if os.environ.get('RECIPIENT_DELIMITER') in localpart:
            localpart_stripped = localpart.rsplit(os.environ.get('RECIPIENT_DELIMITER'), 1)[0]

        user = User.query.get(f'{localpart}@{domain_name}')
        if not user and localpart_stripped:
            user = User.query.get(f'{localpart_stripped}@{domain_name}')
        if user:
            email = f'{localpart}@{domain_name}'

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

        if stripped_alias:
            return stripped_alias.destination

        if pure_alias:
            return pure_alias.destination

        return None


class User(Base, Email):
    """ A user is an email address that has a password to access a mailbox.
    """

    __tablename__ = 'user'
    _ctx = None
    _credential_cache = {}

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
            self.reply_startdate < now and
            self.reply_enddate > now
        )

    @classmethod
    def get_password_context(cls):
        """ create password context for hashing and verification
        """
        if cls._ctx:
            return cls._ctx

        schemes = passlib.registry.list_crypt_handlers()
        # scrypt throws a warning if the native wheels aren't found
        schemes.remove('scrypt')
        # we can't leave plaintext schemes as they will be misidentified
        for scheme in schemes:
            if scheme.endswith('plaintext'):
                schemes.remove(scheme)
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
            self.password = new_hash
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

    def set_password(self, password, raw=False):
        """ Set password for user
            @password: plain text password to encrypt (or, if raw is True: the hash itself)
        """
        self.password = password if raw else User.get_password_context().hash(password)

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

    @classmethod
    def get_temp_token(cls, email):
        user = cls.query.get(email)
        return hmac.new(app.temp_token_key, bytearray("{}|{}".format(time.strftime('%Y%m%d'), email), 'utf-8'), 'sha256').hexdigest() if (user and user.enabled) else None

    def verify_temp_token(self, token):
        return hmac.compare_digest(self.get_temp_token(self.email), token)



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
        """ find aliases matching email address localpart@domain_name """

        alias_preserve_case = cls.query.filter(
                sqlalchemy.and_(cls.domain_name == domain_name,
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
                sqlalchemy.and_(cls.domain_name == domain_name,
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
    last_check = db.Column(db.DateTime, nullable=True)
    error = db.Column(db.String(1023), nullable=True)

    def __repr__(self):
        return (
            f'<Fetch #{self.id}: {self.protocol}{"s" if self.tls else ""}:'
            f'//{self.username}@{self.host}:{self.port}>'
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

        # section-name -> attr
        self._sections = {
            name: getattr(self, name)
            for name in dir(self)
            if isinstance(getattr(self, name), self.MailuCollection)
        }

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
        for model in self._models:
            if models is None or model in models:
                db.session.query(model).delete()

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
