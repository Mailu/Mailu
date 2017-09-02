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
app = flask.Flask(__name__, static_url_path='/admin/app_static')

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
    'BABEL_DEFAULT_LOCALE': 'en',
    'BABEL_DEFAULT_TIMEZONE': 'UTC',
    'ENABLE_CERTBOT': False,
    'CERTS_PATH': '/certs',
    'PASSWORD_SCHEME': 'SHA512-CRYPT'
}

# Load configuration from the environment if available
for key, value in default_config.items():
    app.config[key] = os.environ.get(key, value)

# Setup components
flask_bootstrap.Bootstrap(app)
db = flask_sqlalchemy.SQLAlchemy(app)
migrate = flask_migrate.Migrate(app, db)
login_manager = flask_login.LoginManager()
login_manager.init_app(app)
babel = flask_babel.Babel(app)
translations = list(map(str, babel.list_translations()))
scheduler = background.BackgroundScheduler()

# Manager commnad
manager = flask_script.Manager(app)
manager.add_command('db', flask_migrate.MigrateCommand)

# Task scheduling
if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    scheduler.start()

# Babel configuration
@babel.localeselector
def get_locale():
    return flask.request.accept_languages.best_match(translations)

# Certbot configuration
if app.config['ENABLE_CERTBOT']:
    from mailu import certbot

# Finally setup the blueprint and redirect /
from mailu import admin
app.register_blueprint(admin.app, url_prefix='/admin')

@app.route("/")
def index():
    return flask.redirect(flask.url_for("admin.index"))
