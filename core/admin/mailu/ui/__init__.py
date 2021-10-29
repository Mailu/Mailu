from flask import Blueprint


ui = Blueprint('ui', __name__, static_folder=None, template_folder='templates')

from mailu.ui.views import *
