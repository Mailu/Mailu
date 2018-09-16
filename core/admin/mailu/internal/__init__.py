from flask_limiter import RateLimitExceeded

from mailu import limiter

import socket
import flask


internal = flask.Blueprint('internal', __name__)

@internal.app_errorhandler(RateLimitExceeded)
def rate_limit_handler(e):
    response = flask.Response()
    response.headers['Auth-Status'] = 'Authentication rate limit from one source exceeded'
    response.headers['Auth-Error-Code'] = '451 4.3.2'
    if int(flask.request.headers['Auth-Login-Attempt']) < 10:
        response.headers['Auth-Wait'] = '3'
    return response

@limiter.request_filter
def whitelist_webmail():
    try:
        return flask.request.headers["Client-Ip"] ==\
            socket.gethostbyname("webmail")
    except:
        return False


from mailu.internal import views
