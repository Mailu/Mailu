""" Mailu admin app utilities
"""

try:
    import cPickle as pickle
except ImportError:
    import pickle

import hashlib
import secrets
import time

from multiprocessing import Value

from mailu import limiter

import flask
import flask_login
import flask_migrate
import flask_babel
import redis

from flask.sessions import SessionMixin, SessionInterface
from itsdangerous.encoding import want_bytes
from werkzeug.datastructures import CallbackDict
from werkzeug.contrib import fixers


# Login configuration
login = flask_login.LoginManager()
login.login_view = "ui.login"

@login.unauthorized_handler
def handle_needs_login():
    """ redirect unauthorized requests to login page """
    return flask.redirect(
        flask.url_for('ui.login', next=flask.request.endpoint)
    )

# Rate limiter
limiter = limiter.LimitWraperFactory()

# Application translation
babel = flask_babel.Babel()

@babel.localeselector
def get_locale():
    """ selects locale for translation """
    translations = [str(translation) for translation in babel.list_translations()]
    return flask.request.accept_languages.best_match(translations)


# Proxy fixer
class PrefixMiddleware(object):
    """ fix proxy headers """
    def __init__(self):
        self.app = None

    def __call__(self, environ, start_response):
        prefix = environ.get('HTTP_X_FORWARDED_PREFIX', '')
        if prefix:
            environ['SCRIPT_NAME'] = prefix
        return self.app(environ, start_response)

    def init_app(self, app):
        self.app = fixers.ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
        app.wsgi_app = self

proxy = PrefixMiddleware()


# Data migrate
migrate = flask_migrate.Migrate()


# session store (inspired by https://github.com/mbr/flask-kvsession)
class RedisStore:
    """ Stores session data in a redis db. """

    has_ttl = True

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

    has_ttl = False

    def __init__(self):
        self.dict = {}

    def get(self, key):
        """ load item from store. """
        return self.dict[key]

    def put(self, key, value, ttl_secs=None):
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

        self.delete()

        self._sid = None
        self._created = self.app.session_config.gen_created()

        self.modified = True

    def delete(self):
        """ Delete stored session. """
        if self.saved:
            self.app.session_store.delete(self._key)
            self._key = None

    def save(self):
        """ Save session to store. """

        # set uid from dict data
        if self._uid is None:
            self._uid = self.app.session_config.gen_uid(self.get('user_id', ''))

        # create new session id for new or regenerated sessions
        if self._sid is None:
            self._sid = self.app.session_config.gen_sid()

        # get new session key
        key = self.sid

        # delete old session if key has changed
        if key != self._key:
            self.delete()

        # save session
        self.app.session_store.put(
            key,
            pickle.dumps(dict(self)),
            self.app.permanent_session_lifetime.total_seconds()
        )

        self._key = key

        self.new = False
        self.modified = False

class MailuSessionConfig:
    """ Stores sessions crypto config """

    def __init__(self, app=None):

        if app is None:
            app = flask.current_app

        bits = app.config.get('SESSION_KEY_BITS', 64)

        if bits < 64:
            raise ValueError('Session id entropy must not be less than 64 bits!')

        hash_bytes = bits//8 + (bits%8>0)
        time_bytes = 4 # 32 bit timestamp for now
        shaker = hashlib.shake_256 if bits>128 else hashlib.shake_128

        self._shaker   = shaker(want_bytes(app.config.get('SECRET_KEY', '')))
        self._hash_len = hash_bytes
        self._hash_b64 = len(self._encode(bytes(hash_bytes)))
        self._key_min  = 2*self._hash_b64
        self._key_max  = self._key_min + len(self._encode(bytes(time_bytes)))

    def gen_sid(self):
        """ Generate random session id. """
        return self._encode(secrets.token_bytes(self._hash_len))

    def gen_uid(self, uid):
        """ Generate hashed user id part of session key. """
        shaker = self._shaker.copy()
        shaker.update(want_bytes(uid))
        return self._encode(shaker.digest(self._hash_len))

    def gen_created(self, now=None):
        """ Generate base64 representation of creation time. """
        return self._encode(int(now or time.time()).to_bytes(8, byteorder='big').lstrip(b'\0'))

    def parse_key(self, key, app=None, validate=False, now=None):
        """ Split key into sid, uid and creation time. """

        if not (isinstance(key, bytes) and self._key_min <= len(key) <= self._key_max):
            return None

        uid = key[:self._hash_b64]
        sid = key[self._hash_b64:self._key_min]
        crt = key[self._key_min:]

        # validate if parts are decodeable
        created = self._decode(crt)
        if created is None or self._decode(uid) is None or self._decode(sid) is None:
            return None

        # validate creation time when requested or store does not support ttl
        if validate or not app.session_store.has_ttl:
            if now is None:
                now = int(time.time())
            created = int.from_bytes(created, byteorder='big')
            if not (created < now < created + app.permanent_session_lifetime.total_seconds()):
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

        # TODO: set cookie from time to time to prevent expiration in browser
        # also update expire in redis

        if not self.should_set_cookie(app, session):
            return

        # save session and update cookie
        session.save()
        response.set_cookie(
            app.session_cookie_name,
            session.sid,
            expires=self.get_expiration_time(app, session),
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
            if not app.session_config.parse_key(key, app, validate=True, now=now):
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
            if key not in keep:
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

            # clean expired sessions oonce on first use in case lifetime was changed
            def cleaner():
                with cleaned.get_lock():
                    if not cleaned.value:
                        cleaned.value = True
                        flask.current_app.logger.error('cleaning')
                        MailuSessionExtension.cleanup_sessions(app)

            app.before_first_request(cleaner)

        app.session_config = MailuSessionConfig(app)
        app.session_interface = MailuSessionInterface()

cleaned = Value('i', False)
session = MailuSessionExtension()
