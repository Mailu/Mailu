import flask
import flask_sqlalchemy
import flask_bootstrap
import flask_login
import flask_script
import flask_migrate
import flask_babel

import os
import docker

from apscheduler.schedulers import background


# Create application
app = flask.Flask(__name__)

default_config = {
    'SQLALCHEMY_DATABASE_URI': 'sqlite:////data/main.db',
    'SQLALCHEMY_TRACK_MODIFICATIONS': False,
    'SECRET_KEY': 'changeMe',
    'DOCKER_SOCKET': 'unix:///var/run/docker.sock',
    'HOSTNAME': 'mail.mailu.io',
    'DOMAIN': 'mailu.io',
    'POSTMASTER': 'postmaster',
    'DEBUG': False,
    'BOOTSTRAP_SERVE_LOCAL': True,
    'DKIM_PATH': '/dkim/{domain}.{selector}.key',
    'DKIM_SELECTOR': 'dkim',
    'DMARC_RUA': None,
    'DMARC_RUF': None,
    'BABEL_DEFAULT_LOCALE': 'en',
    'BABEL_DEFAULT_TIMEZONE': 'UTC',
    'FRONTEND': 'none',
    'TLS_FLAVOR': 'cert',
    'CERTS_PATH': '/certs',
    'PASSWORD_SCHEME': 'SHA512-CRYPT',
}

# Load configuration from the environment if available
for key, value in default_config.items():
    app.config[key] = os.environ.get(key, value)

# Base application
flask_bootstrap.Bootstrap(app)
db = flask_sqlalchemy.SQLAlchemy(app)
migrate = flask_migrate.Migrate(app, db)

# Manager commnad
manager = flask_script.Manager(app)
manager.add_command('db', flask_migrate.MigrateCommand)

# Babel configuration
babel = flask_babel.Babel(app)
translations = list(map(str, babel.list_translations()))

@babel.localeselector
def get_locale():
    return flask.request.accept_languages.best_match(translations)

# Login configuration
login_manager = flask_login.LoginManager()
login_manager.init_app(app)
login_manager.login_view = ".login"

@login_manager.unauthorized_handler
def handle_needs_login():
    return flask.redirect(
        flask.url_for('.login', next=flask.request.endpoint)
    )

@app.context_processor
def inject_user():
    return dict(current_user=flask_login.current_user)

# Import views
from mailu import ui
app.register_blueprint(ui.ui, url_prefix='/ui')

# Create the prefix middleware
class PrefixMiddleware(object):

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        prefix = environ.get('HTTP_X_FORWARDED_PREFIX', '')
        if prefix:
            environ['SCRIPT_NAME'] = prefix
        return self.app(environ, start_response)

app.wsgi_app = PrefixMiddleware(app.wsgi_app)
