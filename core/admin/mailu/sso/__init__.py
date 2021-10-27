from flask import Blueprint

sso = Blueprint('sso', __name__, template_folder='templates')

from mailu.sso.views import *
