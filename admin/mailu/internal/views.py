from mailu import db, models, app, limiter
from mailu.internal import internal, nginx

import flask


@internal.route("/auth/email")
@limiter.limit(
    app.config["AUTH_RATELIMIT"],
    lambda: flask.request.headers["Client-Ip"]
)
def nginx_authentication():
    """ Main authentication endpoint for Nginx email server
    """
    headers = nginx.handle_authentication(flask.request.headers)
    response = flask.Response()
    for key, value in headers.items():
        response.headers[key] = str(value)
    return response
