from mailu.sso import sso
from flask import current_app as app

@sso.route("/")
def hello_world():
    return "<p>Hello, World!</p>"
