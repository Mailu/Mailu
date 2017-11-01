from flask import Blueprint


internal = Blueprint('internal', __name__)

from mailu.internal import views
