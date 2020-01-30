from mailu.limiter import RateLimitExceeded

from mailu import utils
from flask import current_app as app

import socket
import flask


internal = flask.Blueprint('internal', __name__, template_folder='templates')


@internal.app_errorhandler(RateLimitExceeded)
def rate_limit_handler(e):
    response = flask.Response()
    response.headers['Auth-Status'] = 'Authentication rate limit from one source exceeded'
    response.headers['Auth-Error-Code'] = '451 4.3.2'
    if int(flask.request.headers['Auth-Login-Attempt']) < 10:
        response.headers['Auth-Wait'] = '3'
    return response


from mailu.internal.views import *
