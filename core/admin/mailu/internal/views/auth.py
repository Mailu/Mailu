from mailu import models, utils
from mailu.internal import internal, nginx
from flask import current_app as app

import flask
import flask_login
import base64
import ipaddress


@internal.route("/auth/email")
def nginx_authentication():
    """ Main authentication endpoint for Nginx email server
    """
    limiter = utils.limiter.get_limiter(app.config["AUTH_RATELIMIT"], "auth-ip")
    client_ip = flask.request.headers["Client-Ip"]
    if not limiter.test(client_ip):
        response = flask.Response()
        response.headers['Auth-Status'] = 'Authentication rate limit from one source exceeded'
        response.headers['Auth-Error-Code'] = '451 4.3.2'
        if int(flask.request.headers['Auth-Login-Attempt']) < 10:
            response.headers['Auth-Wait'] = '3'
        return response
    headers = nginx.handle_authentication(flask.request.headers)
    response = flask.Response()
    for key, value in headers.items():
        response.headers[key] = str(value)
    if ("Auth-Status" not in headers) or (headers["Auth-Status"] != "OK"):
        limit_subnet = str(app.config["AUTH_RATELIMIT_SUBNET"]) != 'False'
        subnet = ipaddress.ip_network(app.config["SUBNET"])
        if limit_subnet or ipaddress.ip_address(client_ip) not in subnet:
            limiter.hit(flask.request.headers["Client-Ip"])
    return response


@internal.route("/auth/admin")
def admin_authentication():
    """ Fails if the user is not an authenticated admin.
    """
    if (not flask_login.current_user.is_anonymous
        and flask_login.current_user.global_admin
        and flask_login.current_user.enabled):
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
        if user and user.enabled and user.check_password(password.decode("utf8")):
            response = flask.Response()
            response.headers["X-User"] = user.email
            return response
    response = flask.Response(status=401)
    response.headers["WWW-Authenticate"] = 'Basic realm="Login Required"'
    return response
