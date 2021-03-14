""" Mailu admin app utilities
"""

from datetime import datetime

from mailu import limiter

import flask
import flask_login
import flask_migrate
import flask_babel
import flask_kvsession
import redis

from simplekv.memory import DictStore
from simplekv.memory.redisstore import RedisStore
from itsdangerous.encoding import want_bytes
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


# session store
class NullSigner(object):
    """NullSigner does not sign nor unsign"""
    def __init__(self, *args, **kwargs):
        pass
    def sign(self, value):
        """Signs the given string."""
        return want_bytes(value)
    def unsign(self, signed_value):
        """Unsigns the given string."""
        return want_bytes(signed_value)

class KVSessionIntf(flask_kvsession.KVSessionInterface):
    """ KVSession interface allowing to run int function on first access """
    def __init__(self, app, init_fn=None):
        if init_fn:
            app.kvsession_init = init_fn
        else:
            self._first_run(None)
    def _first_run(self, app):
        if app:
            app.kvsession_init()
        self.open_session = super().open_session
        self.save_session = super().save_session
    def open_session(self, app, request):
        self._first_run(app)
        return super().open_session(app, request)
    def save_session(self, app, session, response):
        self._first_run(app)
        return super().save_session(app, session, response)

class KVSessionExt(flask_kvsession.KVSessionExtension):
    """ Activates Flask-KVSession for an application. """
    def init_kvstore(self, config):
        """ Initialize kvstore - fallback to DictStore without REDIS_ADDRESS """
        if addr := config.get('REDIS_ADDRESS'):
            self.default_kvstore = RedisStore(redis.StrictRedis().from_url(f'redis://{addr}/3'))
        else:
            self.default_kvstore = DictStore()

    def cleanup_sessions(self, app=None, dkey=None, dvalue=None):
        """ Remove sessions from the store. """
        if not app:
            app = flask.current_app
        if dkey is None and dvalue is None:
            now = datetime.utcnow()
            for key in app.kvsession_store.keys():
                try:
                    sid = flask_kvsession.SessionID.unserialize(key)
                except ValueError:
                    pass
                else:
                    if sid.has_expired(
                        app.config['PERMANENT_SESSION_LIFETIME'],
                        now
                    ):
                        app.kvsession_store.delete(key)
        elif dkey is not None and dvalue is not None:
            for key in app.kvsession_store.keys():
                if app.session_interface.serialization_method.loads(
                    app.kvsession_store.get(key)
                ).get(dkey, None) == dvalue:
                    app.kvsession_store.delete(key)
        else:
            raise ValueError('Need dkey and dvalue.')

    def init_app(self, app, session_kvstore=None):
        """ Initialize application and KVSession. """
        super().init_app(app, session_kvstore)
        app.session_interface = KVSessionIntf(app, self.cleanup_sessions)

kvsession = KVSessionExt()

flask_kvsession.Signer = NullSigner
