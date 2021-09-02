from flask import Blueprint


sso = Blueprint('sso', __name__, static_folder='static', template_folder='templates')

from mailu.sso.views import *
