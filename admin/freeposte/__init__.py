from flask import Flask
from flask_sqlalchemy import SQLAlchemy



# Create application
app = Flask(__name__)

app.config.update({
    'SQLALCHEMY_DATABASE_URI': 'sqlite:////tmp/freeposte.db'
})

# Create the database
db = SQLAlchemy(app)

from freeposte import views
