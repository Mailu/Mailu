from flask import Blueprint


ui = Blueprint('ui', __name__, static_folder='static', template_folder='templates')

from mailu.ui.views import *
