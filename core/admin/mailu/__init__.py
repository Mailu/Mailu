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

# Create application
app = flask.Flask(__name__)

default_config = {
    'SQLALCHEMY_DATABASE_URI': 'sqlite:////data/main.db',
    'SQLALCHEMY_TRACK_MODIFICATIONS': False,
    'INSTANCE_ID_PATH': '/data/instance',
    'STATS_ENDPOINT': '15.{}.stats.mailu.io',
    'SECRET_KEY': 'changeMe',
    'DOCKER_SOCKET': 'unix:///var/run/docker.sock',
    'HOSTNAMES': 'mail.mailu.io',
    'DOMAIN': 'mailu.io',
    'POSTMASTER': 'postmaster',
    'SITENAME': 'Mailu',
    'WEBSITE': 'https://mailu.io',
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
    'WEBMAIL': 'none',
    'AUTH_RATELIMIT': '10/minute;1000/hour',
    'RATELIMIT_STORAGE_URL': 'redis://redis',
    'DISABLE_STATISTICS': 'False'
}

# Load configuration from the environment if available
for key, value in default_config.items():
    app.config[key] = os.environ.get(key, value)

# Base application
flask_bootstrap.Bootstrap(app)
db = flask_sqlalchemy.SQLAlchemy(app)
migrate = flask_migrate.Migrate(app, db)
limiter = flask_limiter.Limiter(app, key_func=lambda: current_user.username)

# Run statistics
if os.path.isfile(app.config["INSTANCE_ID_PATH"]):
    with open(app.config["INSTANCE_ID_PATH"], "r") as handle:
        instance_id = handle.read()
else:
    instance_id = str(uuid.uuid4())
    with open(app.config["INSTANCE_ID_PATH"], "w") as handle:
        handle.write(instance_id)
if app.config["DISABLE_STATISTICS"].lower() != "true":
    try:
        socket.gethostbyname(app.config["STATS_ENDPOINT"].format(instance_id))
    except:
        pass

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
login_manager.login_view = ".login"

@login_manager.unauthorized_handler
def handle_needs_login():
    return flask.redirect(
        flask.url_for('.login', next=flask.request.endpoint)
    )

@app.context_processor
def inject_defaults():
    return dict(
        current_user=flask_login.current_user,
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

app.wsgi_app = PrefixMiddleware(app.wsgi_app)
