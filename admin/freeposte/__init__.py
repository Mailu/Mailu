from flask import Flask
from flask_sqlalchemy import SQLAlchemy

import os


# Create application
app = Flask(__name__)

default_config = {
    'SQLALCHEMY_DATABASE_URI': 'sqlite:////data/freeposte.db',
    'SQLALCHEMY_TRACK_MODIFICATIONS': False,
    'SECRET_KEY': None
}

# Load configuration from the environment if available
for key, value in default_config.items():
    app.config[key] = os.environ.get(key, value)


# Create the database
db = SQLAlchemy(app)

from freeposte import views
