import flask
import flask_sqlalchemy
import flask_bootstrap
import flask_login
import flask_script
import flask_migrate
import flask_babel
import flask_limiter

import os
import docker
import socket
import uuid

from werkzeug.contrib import fixers

# Create application
app = flask.Flask(__name__)

default_config = {
    # Specific to the admin UI
    'SQLALCHEMY_DATABASE_URI': 'sqlite:////data/main.db',
    'SQLALCHEMY_TRACK_MODIFICATIONS': False,
    'DOCKER_SOCKET': 'unix:///var/run/docker.sock',
    'BABEL_DEFAULT_LOCALE': 'en',
    'BABEL_DEFAULT_TIMEZONE': 'UTC',
    'BOOTSTRAP_SERVE_LOCAL': True,
    'RATELIMIT_STORAGE_URL': 'redis://redis',
    'DEBUG': False,
    # Statistics management
    'INSTANCE_ID_PATH': '/data/instance',
    'STATS_ENDPOINT': '0.{}.stats.mailu.io',
    # Common configuration variables
    'SECRET_KEY': 'changeMe',
    'DOMAIN': 'mailu.io',
    'HOSTNAMES': 'mail.mailu.io,alternative.mailu.io,yetanother.mailu.io',
    'POSTMASTER': 'postmaster',
    'TLS_FLAVOR': 'cert',
    'AUTH_RATELIMIT': '10/minute;1000/hour',
    'DISABLE_STATISTICS': 'False',
    # Mail settings
    'DMARC_RUA': None,
    'DMARC_RUF': None,
    'WELCOME': 'False',
    'WELCOME_SUBJECT': 'Dummy welcome topic',
    'WELCOME_BODY': 'Dummy welcome body',
    'DKIM_SELECTOR': 'dkim',
    'DKIM_PATH': '/dkim/{domain}.{selector}.key',
    'DEFAULT_QUOTA': 1000000000,
    # Web settings
    'SITENAME': 'Mailu',
    'WEBSITE': 'https://mailu.io',
    'WEB_ADMIN': '/admin',
    'WEB_WEBMAIL': '/webmail',
    # Advanced settings
    'PASSWORD_SCHEME': 'SHA512-CRYPT',
    # Host settings
    'HOST_IMAP': 'imap',
    'HOST_POP3': 'imap',
    'HOST_SMTP': 'smtp',
    'HOST_AUTHSMTP': os.environ.get('HOST_SMTP', 'smtp'),
}

# Load configuration from the environment if available
for key, value in default_config.items():
    app.config[key] = os.environ.get(key, value)

# Load specific DB connections (mysql://username:password@server/db)
if "DB_TYPE" in os.environ and os.environ["DB_TYPE"] == "mysql":
    if "DB_HOST" not in os.environ:
        os.environ["DB_HOST"] = "database"
    if "DB_PORT" not in os.environ:
		os.environ["DB_PORT"] = "3306"
    if "DB_USER" not in os.environ:
        os.environ["DB_USER"] = "mailu"
    if "DB_PASSWORD" not in os.environ:
        os.environ["DB_PASSWORD"] = "mailu"
    if "DB_DATABASE" not in os.environ:
        os.environ["DB_DATABASE"] = "mailu"
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DB_TYPE"]+"+pymysql://"+os.environ["DB_USER"]+":"+os.environ["DB_PASSWORD"]+"@"+os.environ["DB_HOST"]+":"+os.environ["DB_PORT"]+"/"+os.environ["DB_DATABASE"]

# Base application
flask_bootstrap.Bootstrap(app)
db = flask_sqlalchemy.SQLAlchemy(app)
migrate = flask_migrate.Migrate(app, db)
limiter = flask_limiter.Limiter(app, key_func=lambda: current_user.username)

# Debugging toolbar
if app.config.get("DEBUG"):
    import flask_debugtoolbar
    toolbar = flask_debugtoolbar.DebugToolbarExtension(app)

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
login_manager.login_view = "ui.login"

@login_manager.unauthorized_handler
def handle_needs_login():
    return flask.redirect(
        flask.url_for('ui.login', next=flask.request.endpoint)
    )

@app.context_processor
def inject_defaults():
    signup_domains = models.Domain.query.filter_by(signup_enabled=True).all()
    return dict(
        current_user=flask_login.current_user,
        signup_domains=signup_domains,
        config=app.config
    )

# Import views
from mailu import ui, internal
app.register_blueprint(ui.ui, url_prefix='/ui')
app.register_blueprint(internal.internal, url_prefix='/internal')

# Create the prefix middleware
class PrefixMiddleware(object):

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        prefix = environ.get('HTTP_X_FORWARDED_PREFIX', '')
        if prefix:
            environ['SCRIPT_NAME'] = prefix
        return self.app(environ, start_response)

app.wsgi_app = PrefixMiddleware(fixers.ProxyFix(app.wsgi_app))
