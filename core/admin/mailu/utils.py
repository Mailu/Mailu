from mailu import models, limiter

import flask
import flask_login
import flask_script
import flask_migrate
import flask_babel

from werkzeug.contrib import fixers


# Login configuration
login = flask_login.LoginManager()
login.login_view = "ui.login"

@login.unauthorized_handler
def handle_needs_login():
    return flask.redirect(
        flask.url_for('ui.login', next=flask.request.endpoint)
    )

# Rate limiter
limiter = limiter.LimitWraperFactory()

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
        self.app = fixers.ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
        app.wsgi_app = self

proxy = PrefixMiddleware()


# Data migrate
migrate = flask_migrate.Migrate()
