from mailu import db, models, app, limiter
from mailu.internal import internal, nginx

import flask
import flask_login


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


@internal.route("/auth/admin")
def admin_authentication():
    """ Fails if the user is not an authenticated admin.
    """
    if (not flask_login.current_user.is_anonymous
        and flask_login.current_user.global_admin):
        return ""
    return flask.abort(403)
