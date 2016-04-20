from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap
from flask.ext import login as flask_login

import os
import docker


# Create application
app = Flask(__name__)

default_config = {
    'SQLALCHEMY_DATABASE_URI': 'sqlite:////data/freeposte.db',
    'SQLALCHEMY_TRACK_MODIFICATIONS': False,
    'SECRET_KEY': 'changeMe',
    'DOCKER_SOCKET': 'unix:///var/run/docker.sock',
    'DEBUG': False
}

# Load configuration from the environment if available
for key, value in default_config.items():
    app.config[key] = os.environ.get(key, value)

# Setup components
Bootstrap(app)
db = SQLAlchemy(app)
login_manager = flask_login.LoginManager()
login_manager.init_app(app)

# Connect to the Docker socket
dockercli = docker.Client(base_url=app.config['DOCKER_SOCKET'])

# Finally setup the blueprint
from freeposte import admin
app.register_blueprint(admin.app, url_prefix='/admin')
