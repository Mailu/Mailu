from flask import Blueprint

static = Blueprint('static', __name__, static_folder='static', static_url_path='/static')


