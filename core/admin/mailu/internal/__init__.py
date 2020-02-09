import flask


internal = flask.Blueprint('internal', __name__, template_folder='templates')


from mailu.internal.views import *
