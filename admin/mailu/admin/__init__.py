from flask import Blueprint
from mailu import login_manager, db

import flask_login


app = Blueprint(
    'admin', __name__,
    template_folder='templates',
    static_folder='static')

# Import models
from mailu.admin import models

# Register the login components
login_manager.login_view = "admin.login"
login_manager.user_loader(models.User.query.get)

@app.context_processor
def inject_user():
    return dict(current_user=flask_login.current_user)

# Import views
from mailu.admin.views import \
    admins, \
    managers, \
    base, \
    aliases, \
    users, \
    domains, \
    relays, \
    alternatives, \
    fetches
