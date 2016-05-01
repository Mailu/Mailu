from flask import Blueprint
from flask.ext import login as flask_login
from freeposte import login_manager, db


app = Blueprint(
    'admin', __name__,
    template_folder='templates',
    static_folder='static')

# Import models
from freeposte.admin import models

# Register the login components
login_manager.login_view = "admin.login"
login_manager.user_loader(models.User.query.get)

@app.context_processor
def inject_user():
    return dict(current_user=flask_login.current_user)

# Import views
from freeposte.admin.views import \
    admins, \
    managers, \
    base, \
    aliases, \
    users, \
    domains, \
    fetches
