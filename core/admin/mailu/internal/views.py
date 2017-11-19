from mailu import db, models, app, limiter
from mailu.internal import internal, nginx

import flask
import flask_login
import base64
import urllib


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


@internal.route("/auth/basic")
def basic_authentication():
    """ Tries to authenticate using the Authorization header.
    """
    authorization = flask.request.headers.get("Authorization")
    if authorization and authorization.startswith("Basic "):
        encoded = authorization.replace("Basic ", "")
        user_email, password = base64.b64decode(encoded).split(b":")
        user = models.User.query.get(user_email.decode("utf8"))
        if user and user.check_password(password.decode("utf8")):
            response = flask.Response()
            response.headers["X-User"] = user.email
            return response
    response = flask.Response(status=401)
    response.headers["WWW-Authenticate"] = 'Basic realm="Login Required"'
    return response
