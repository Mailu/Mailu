from mailu import limiter

import socket
import flask


internal = flask.Blueprint('internal', __name__)


@limiter.request_filter
def whitelist_webmail():
    try:
        return flask.request.headers["Client-Ip"] ==\
            socket.gethostbyname("webmail")
    except:
        return False


from mailu.internal import views
