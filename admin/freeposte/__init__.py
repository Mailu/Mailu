from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap
from flask.ext import login as flask_login

import os


# Create application
app = Flask(__name__)

default_config = {
    'SQLALCHEMY_DATABASE_URI': 'sqlite:////tmp/freeposte.db',
    'SQLALCHEMY_TRACK_MODIFICATIONS': False,
    'SECRET_KEY': "changeMe",
    'DEBUG': False
}

# Load configuration from the environment if available
for key, value in default_config.items():
    app.config[key] = os.environ.get(key, value)

# Setup Bootstrap
Bootstrap(app)

# Create the database
db = SQLAlchemy(app)

# Import models once the database is ready
from freeposte import models

# Setup Flask-login
login_manager = flask_login.LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.user_loader(models.User.get_by_email)

@app.context_processor
def inject_user():
    return dict(current_user=flask_login.current_user)

# Finally import view
from freeposte import views
