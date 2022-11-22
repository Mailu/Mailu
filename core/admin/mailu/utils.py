""" Mailu admin app utilities
"""

try:
    import cPickle as pickle
except ImportError:
    import pickle

import dns.resolver
import dns.exception
import dns.flags
import dns.rdtypes
import dns.rdatatype
import dns.rdataclass

import hmac
import secrets
import time

from multiprocessing import Value
from mailu import limiter
from flask import current_app as app

import flask
import flask_login
import flask_migrate
import flask_babel
import ipaddress
import redis

from datetime import datetime, timedelta
from flask.sessions import SessionMixin, SessionInterface
from itsdangerous.encoding import want_bytes
from werkzeug.datastructures import CallbackDict
from werkzeug.middleware.proxy_fix import ProxyFix

# Login configuration
login = flask_login.LoginManager()
login.login_view = "sso.login"

@login.unauthorized_handler
def handle_needs_login():
    """ redirect unauthorized requests to login page """
    return flask.redirect(
        flask.url_for('sso.login')
    )

# DNS stub configured to do DNSSEC enabled queries
resolver = dns.resolver.Resolver()
resolver.use_edns(0, dns.flags.DO, 1232)
resolver.flags = dns.flags.AD | dns.flags.RD

def has_dane_record(domain, timeout=10):
    try:
        result = resolver.resolve(f'_25._tcp.{domain}', dns.rdatatype.TLSA,dns.rdataclass.IN, lifetime=timeout)
        if result.response.flags & dns.flags.AD:
            for record in result:
                if isinstance(record, dns.rdtypes.ANY.TLSA.TLSA):
                    if record.usage in [2,3] and record.selector in [0,1] and record.mtype in [0,1,2]:
                        return True
    except dns.resolver.NoNameservers:
        # If the DNSSEC data is invalid and the DNS resolver is DNSSEC enabled
        # we will receive this non-specific exception. The safe behaviour is to
        # accept to defer the email.
        app.logger.warn(f'Unable to lookup the TLSA record for {domain}. Is the DNSSEC zone okay on https://dnsviz.net/d/{domain}/dnssec/?')
        return app.config['DEFER_ON_TLS_ERROR']
    except dns.exception.Timeout:
        app.logger.warn(f'Timeout while resolving the TLSA record for {domain} ({timeout}s).')
    except (dns.resolver.NXDOMAIN, dns.name.EmptyLabel):
        pass # this is expected, not TLSA record is fine
    except Exception as e:
        app.logger.info(f'Error while looking up the TLSA record for {domain} {e}')
        pass

# Rate limiter
limiter = limiter.LimitWraperFactory()

def extract_network_from_ip(ip):
    n = ipaddress.ip_network(ip)
    if n.version == 4:
        return str(n.supernet(prefixlen_diff=(32-app.config["AUTH_RATELIMIT_IP_V4_MASK"])).network_address)
    else:
        return str(n.supernet(prefixlen_diff=(128-app.config["AUTH_RATELIMIT_IP_V6_MASK"])).network_address)

def is_exempt_from_ratelimits(ip):
    ip = ipaddress.ip_address(ip)
    return any(ip in cidr for cidr in app.config['AUTH_RATELIMIT_EXEMPTION'])

# Application translation
babel = flask_babel.Babel()

@babel.localeselector
def get_locale():
    """ selects locale for translation """
    if not app.config['SESSION_COOKIE_NAME'] in flask.request.cookies:
        return flask.request.accept_languages.best_match(app.config.translations.keys())
    language = flask.session.get('language')
    if not language in app.config.translations:
        language = flask.request.accept_languages.best_match(app.config.translations.keys())
        flask.session['language'] = language
    return language


# Proxy fixer
class PrefixMiddleware(object):
    """ fix proxy headers """
    def __init__(self):
        self.app = None

    def __call__(self, environ, start_response):
        return self.app(environ, start_response)

    def init_app(self, app):
        self.app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
        app.wsgi_app = self

proxy = PrefixMiddleware()


# Data migrate
migrate = flask_migrate.Migrate()

# session store (inspired by https://github.com/mbr/flask-kvsession)
class RedisStore:
    """ Stores session data in a redis db. """

    def __init__(self, redisstore):
        self.redis = redisstore

    def get(self, key):
        """ load item from store. """
        value = self.redis.get(key)
        if value is None:
            raise KeyError(key)
        return value

    def put(self, key, value, ttl=None):
        """ save item to store. """
        if ttl:
            self.redis.setex(key, int(ttl), value)
        else:
            self.redis.set(key, value)

    def delete(self, key):
        """ delete item from store. """
        self.redis.delete(key)

    def list(self, prefix=None):
        """ return list of keys starting with prefix """
        if prefix:
            prefix += b'*'
        return list(self.redis.scan_iter(match=prefix))

class DictStore:
    """ Stores session data in a python dict. """

    def __init__(self):
        self.dict = {}

    def get(self, key):
        """ load item from store. """
        return self.dict[key]

    def put(self, key, value, ttl=None):
        """ save item to store. """
        self.dict[key] = value

    def delete(self, key):
        """ delete item from store. """
        try:
            del self.dict[key]
        except KeyError:
            pass

    def list(self, prefix=None):
        """ return list of keys starting with prefix """
        if prefix is None:
            return list(self.dict.keys())
        return [key for key in self.dict if key.startswith(prefix)]

class MailuSession(CallbackDict, SessionMixin):
    """ Custom flask session storage. """

    # default modified to false
    modified = False

    def __init__(self, key=None, app=None):

        self.app = app or flask.current_app

        initial = None

        key = want_bytes(key)
        if parsed := self.app.session_config.parse_key(key, self.app):
            try:
                initial = pickle.loads(app.session_store.get(key))
            except (KeyError, EOFError, pickle.UnpicklingError):
                # either the cookie was manipulated or we did not find the
                # session in the backend or the pickled data is invalid.
                # => start new session
                pass
            else:
                (self._uid, self._sid, self._created) = parsed
                self._key = key

        if initial is None:
            # start new session
            self.new = True
            self._uid = None
            self._sid = None
            self._created = self.app.session_config.gen_created()
            self._key = None

        def _on_update(obj):
            obj.modified = True

        CallbackDict.__init__(self, initial, _on_update)

    @property
    def saved(self):
        """ this reflects if the session was saved. """
        return self._key is not None

    @property
    def sid(self):
        """ this reflects the session's id. """
        if self._sid is None or self._uid is None or self._created is None:
            return None
        return b''.join([self._uid, self._sid, self._created])

    def destroy(self):
        """ destroy session for security reasons. """
        self.delete()

        self._uid = None
        self._sid = None
        self._created = None

        self.clear()

        self.modified = True
        self.new = False

    def regenerate(self):
        """ generate new id for session to avoid `session fixation`. """
        self.delete(clear_token=False)
        self._sid = None
        self.modified = True

    def delete(self, clear_token=True):
        """ Delete stored session. """
        if self.saved:
            if clear_token and 'webmail_token' in self:
                self.app.session_store.delete(self['webmail_token'])
            self.app.session_store.delete(self._key)
            self._key = None

    def save(self):
        """ Save session to store. """
        set_cookie = False
        # set uid from dict data
        if self._uid is None:
            self._uid = self.app.session_config.gen_uid(self.get('_user_id', ''))

        # create new session id for new or regenerated sessions and force setting the cookie
        if self._sid is None:
            self._sid = self.app.session_config.gen_sid()
            set_cookie = True
            if 'webmail_token' in self:
                self.app.session_store.put(self['webmail_token'],
                        self.sid,
                        self.app.config['PERMANENT_SESSION_LIFETIME'],
                )

        # get new session key
        key = self.sid

        # delete old session if key has changed
        if key != self._key:
            self.delete()

        # save session
        self.app.session_store.put(
            key,
            pickle.dumps(dict(self)),
            app.config['SESSION_TIMEOUT'],
        )

        self._key = key

        self.new = False
        self.modified = False

        return set_cookie

class MailuSessionConfig:
    """ Stores sessions crypto config """

    # default size of session key parts
    uid_bits = 64 # default if SESSION_KEY_BITS is not set in config
    sid_bits = 128 # for now. must be multiple of 8!
    time_bits = 32 # for now. must be multiple of 8!  

    def __init__(self, app=None):

        if app is None:
            app = flask.current_app

        bits = app.config.get('SESSION_KEY_BITS', self.uid_bits)
        if not 64 <= bits <= 256:
            raise ValueError('SESSION_KEY_BITS must be between 64 and 256!')

        uid_bytes = bits//8 + (bits%8>0)
        sid_bytes = self.sid_bits//8

        key = want_bytes(app.secret_key)

        self._hmac    = hmac.new(hmac.digest(key, b'SESSION_UID_HASH', digest='sha256'), digestmod='sha256')
        self._uid_len = uid_bytes
        self._uid_b64 = len(self._encode(bytes(uid_bytes)))
        self._sid_len = sid_bytes
        self._sid_b64 = len(self._encode(bytes(sid_bytes)))
        self._key_min = self._uid_b64 + self._sid_b64
        self._key_max = self._key_min + len(self._encode(bytes(self.time_bits//8)))

    def gen_sid(self):
        """ Generate random session id. """
        return self._encode(secrets.token_bytes(self._sid_len))

    def gen_uid(self, uid):
        """ Generate hashed user id part of session key. """
        _hmac = self._hmac.copy()
        _hmac.update(want_bytes(uid))
        return self._encode(_hmac.digest()[:self._uid_len])

    def gen_created(self, now=None):
        """ Generate base64 representation of creation time. """
        return self._encode(int(now or time.time()).to_bytes(8, byteorder='big').lstrip(b'\0'))

    def parse_key(self, key, app=None, now=None):
        """ Split key into sid, uid and creation time. """

        if app is None:
            app = flask.current_app

        if not (isinstance(key, bytes) and self._key_min <= len(key) <= self._key_max):
            return None

        uid = key[:self._uid_b64]
        sid = key[self._uid_b64:self._key_min]
        crt = key[self._key_min:]

        # validate if parts are decodeable
        created = self._decode(crt)
        if created is None or self._decode(uid) is None or self._decode(sid) is None:
            return None

        # validate creation time
        if now is None:
            now = int(time.time())
        created = int.from_bytes(created, byteorder='big')
        if not created <= now <= created + app.config['PERMANENT_SESSION_LIFETIME']:
            return None

        return (uid, sid, crt)

    def _encode(self, value):
        return secrets.base64.urlsafe_b64encode(value).rstrip(b'=')

    def _decode(self, value):
        try:
            return secrets.base64.urlsafe_b64decode(value + b'='*(4-len(value)%4))
        except secrets.binascii.Error:
            return None

class MailuSessionInterface(SessionInterface):
    """ Custom flask session interface. """

    def open_session(self, app, request):
        """ Load or create session. """
        return MailuSession(request.cookies.get(app.config['SESSION_COOKIE_NAME'], None), app)

    def save_session(self, app, session, response):
        """ Save modified session. """

        # If the session is modified to be empty, remove the cookie.
        # If the session is empty, return without setting the cookie.
        if not session:
            if session.modified:
                session.delete()
                response.delete_cookie(
                    app.session_cookie_name,
                    domain=self.get_cookie_domain(app),
                    path=self.get_cookie_path(app),
                )
            return

        # Add a "Vary: Cookie" header if the session was accessed
        if session.accessed:
            response.vary.add('Cookie')

        # save session and update cookie if necessary
        if session.save():
            response.set_cookie(
                app.session_cookie_name,
                session.sid,
                expires=datetime.now()+timedelta(seconds=app.config['PERMANENT_SESSION_LIFETIME']),
                httponly=self.get_cookie_httponly(app),
                domain=self.get_cookie_domain(app),
                path=self.get_cookie_path(app),
                secure=self.get_cookie_secure(app),
                samesite=self.get_cookie_samesite(app)
            )

class MailuSessionExtension:
    """ Server side session handling """

    @staticmethod
    def cleanup_sessions(app=None):
        """ Remove invalid or expired sessions. """

        app = app or flask.current_app
        now = int(time.time())

        count = 0
        for key in app.session_store.list():
            if key.startswith(b'token-'):
                if sessid := app.session_store.get(key):
                    if not app.session_config.parse_key(sessid, app, now=now):
                        app.session_store.delete(sessid)
                        app.session_store.delete(key)
                        count += 1
                else:
                    app.session_store.delete(key)
                    count += 1
            elif not app.session_config.parse_key(key, app, now=now):
                app.session_store.delete(key)
                count += 1

        return count

    @staticmethod
    def prune_sessions(uid=None, keep=None, app=None):
        """ Remove sessions
            uid: remove all sessions (NONE) or sessions belonging to a specific user
            keep: keep listed sessions
        """

        keep = keep or set()
        app = app or flask.current_app

        prefix = None if uid is None else app.session_config.gen_uid(uid)

        count = 0
        for key in app.session_store.list(prefix):
            if key not in keep and not key.startswith(b'token-'):
                app.session_store.delete(key)
                count += 1

        return count

    def init_app(self, app):
        """ Replace session management of application. """

        if app.config.get('MEMORY_SESSIONS'):
            # in-memory session store for use in development
            app.session_store = DictStore()

        else:
            # redis-based session store for use in production
            app.session_store = RedisStore(
                redis.StrictRedis().from_url(app.config['SESSION_STORAGE_URL'])
            )

            # clean expired sessions once on first use in case lifetime was changed
            def cleaner():
                with cleaned.get_lock():
                    if not cleaned.value:
                        cleaned.value = True
                        app.logger.info('cleaning session store')
                        MailuSessionExtension.cleanup_sessions(app)

            app.before_first_request(cleaner)

        app.session_config = MailuSessionConfig(app)
        app.session_interface = MailuSessionInterface()

cleaned = Value('i', False)
session = MailuSessionExtension()

# this is used by the webmail to authenticate IMAP/SMTP
def verify_temp_token(email, token):
    try:
        if token.startswith('token-'):
            if sessid := app.session_store.get(token):
                session = MailuSession(sessid, app)
                if session.get('_user_id', '') == email:
                    return True
    except:
        pass

def gen_temp_token(email, session):
    token = session.get('webmail_token', 'token-'+secrets.token_urlsafe())
    session['webmail_token'] = token
    app.session_store.put(token,
            session.sid,
            app.config['PERMANENT_SESSION_LIFETIME'],
    )
    return token

def isBadOrPwned(form):
    try:
        if len(form.pw.data) < 8:
            return "This password is too short."
        breaches = int(form.pwned.data)
    except ValueError:
        breaches = -1
    if breaches > 0:
        return f"This password appears in {breaches} data breaches! It is not unique; please change it."
    return None

def formatCSVField(field):
    if isinstance(field.data,str):
        data = field.data.replace(" ","").split(",")
    else:
        data = field.data
    field.data = ", ".join(data)
