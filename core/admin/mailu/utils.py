from mailu import models

import flask
import flask_login
import flask_script
import flask_migrate
import flask_babel
import flask_limiter

from werkzeug.contrib import fixers


# Login configuration
login = flask_login.LoginManager()
login.login_view = "ui.login"

@login.unauthorized_handler
def handle_needs_login():
    return flask.redirect(
        flask.url_for('ui.login', next=flask.request.endpoint)
    )


# Request rate limitation
limiter = flask_limiter.Limiter(key_func=lambda: current_user.username)


# Application translation
babel = flask_babel.Babel()

@babel.localeselector
def get_locale():
    translations = list(map(str, babel.list_translations()))
    return flask.request.accept_languages.best_match(translations)


# Proxy fixer
class PrefixMiddleware(object):
    def __call__(self, environ, start_response):
        prefix = environ.get('HTTP_X_FORWARDED_PREFIX', '')
        if prefix:
            environ['SCRIPT_NAME'] = prefix
        return self.app(environ, start_response)

    def init_app(self, app):
        self.app = fixers.ProxyFix(app.wsgi_app)
        app.wsgi_app = self

proxy = PrefixMiddleware()
