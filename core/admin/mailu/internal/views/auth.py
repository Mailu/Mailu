from mailu import models, utils
from mailu.internal import internal, nginx
from flask import current_app as app

import flask
import flask_login
import base64
import ipaddress

def extract_network_from_ip(ip):
    n = ipaddress.ip_network(ip)
    if isinstance(n, ipaddress.IPv4Network):
        return str(n.supernet(prefixlen_diff=(32-int(app.config["AUTH_RATELIMIT_IP_V4_MASK"]))).network_address)
    elif isinstance(n, ipaddress.IPv6Network):
        return str(n.supernet(prefixlen_diff=(128-int(app.config["AUTH_RATELIMIT_IP_V6_MASK"]))).network_address)
    else: # not sure what to do with it
        return ip

def is_subject_to_rate_limits(ip):
    key = "exempt-{}".format(ip)
    return not (utils.limiter.storage.get(key) > 0)

def exempt_ip_from_ratelimits(ip):
    key = "exempt-{}".format(ip)
    utils.limiter.storage.incr(key, app.config["AUTH_RATELIMIT_EXEMPTION_LENGTH"], True)

def should_rate_limit_ip(ip):
    limiter = utils.limiter.get_limiter(app.config["AUTH_RATELIMIT_IP"], "auth-ip")
    client_network = extract_network_from_ip(ip)
    return is_subject_to_rate_limits(ip) and not limiter.test(client_network)

def rate_limit_ip(ip):
    limit_subnet = str(app.config["AUTH_RATELIMIT_SUBNET"]) != 'False'
    subnet = ipaddress.ip_network(app.config["SUBNET"])
    if limit_subnet or ipaddress.ip_address(ip) not in subnet:
        limiter = utils.limiter.get_limiter(app.config["AUTH_RATELIMIT_IP"], "auth-ip")
        client_network = extract_network_from_ip(ip)
        if is_subject_to_rate_limits(ip):
            limiter.hit(client_network)

def should_rate_limit_user(username, ip):
    limiter = utils.limiter.get_limiter(app.config["AUTH_RATELIMIT_USER"], "auth-user")
    return is_subject_to_rate_limits(ip) and not limiter.test(username)

def rate_limit_user(username, ip):
    limiter = utils.limiter.get_limiter(app.config["AUTH_RATELIMIT_USER"], "auth-user")
    if is_subject_to_rate_limits(ip):
        limiter.hit(username)

@internal.route("/auth/email")
def nginx_authentication():
    """ Main authentication endpoint for Nginx email server
    """
    client_ip = flask.request.headers["Client-Ip"]
    if should_rate_limit_ip(client_ip):
        status, code = nginx.get_status(flask.request.headers['Auth-Protocol'], 'ratelimit')
        response = flask.Response()
        response.headers['Auth-Status'] = status
        response.headers['Auth-Error-Code'] = code
        if int(flask.request.headers['Auth-Login-Attempt']) < 10:
            response.headers['Auth-Wait'] = '3'
        return response
    headers = nginx.handle_authentication(flask.request.headers)
    response = flask.Response()
    for key, value in headers.items():
        response.headers[key] = str(value)

    is_valid_user = False
    if "Auth-User-Exists" in response.headers and response.headers["Auth-User-Exists"] == "True":
        username = response.headers["Auth-User"]
        if should_rate_limit_user(username, client_ip):
            # FIXME could be done before handle_authentication()
            status, code = nginx.get_status(flask.request.headers['Auth-Protocol'], 'ratelimit')
            response = flask.Response()
            response.headers['Auth-Status'] = status
            response.headers['Auth-Error-Code'] = code
            if int(flask.request.headers['Auth-Login-Attempt']) < 10:
                response.headers['Auth-Wait'] = '3'
            return response
        is_valid_user = True
    if ("Auth-Status" not in headers) or (headers["Auth-Status"] != "OK"):
        rate_limit_user(username, client_ip) if is_valid_user else rate_limit_ip(client_ip)
    elif ("Auth-Status" in headers) and (headers["Auth-Status"] == "OK"):
        exempt_ip_from_ratelimits(client_ip)
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
    client_ip = flask.request.headers["X-Real-IP"] if 'X-Real-IP' in flask.request.headers else flask.request.remote_addr
    if should_rate_limit_ip(client_ip):
        response = flask.Response(status=401)
        response.headers["WWW-Authenticate"] = 'Basic realm="Authentication rate limit from one source exceeded"'
        response.headers['Retry-After'] = '60'
        return response
    authorization = flask.request.headers.get("Authorization")
    if authorization and authorization.startswith("Basic "):
        encoded = authorization.replace("Basic ", "")
        user_email, password = base64.b64decode(encoded).split(b":")
        user_email = user_email.decode("utf8")
        if should_rate_limit_user(user_email, client_ip):
            response = flask.Response(status=401)
            response.headers["WWW-Authenticate"] = 'Basic realm="Authentication rate limit for this username exceeded"'
            response.headers['Retry-After'] = '60'
            return response
        user = models.User.query.get(user_email)
        if user and user.enabled:
            password = password.decode("utf8")
            status = False
            if len(password) == 32:
                for token in user.tokens:
                    if (token.check_password(password) and
                        (not token.ip or token.ip == ip)):
                            status = True
                            break
            if not status and user.check_password(password):
                status = True
            if status:
                response = flask.Response()
                response.headers["X-User"] = user.email
                exempt_ip_from_ratelimits(client_ip)
                return response
            rate_limit_user(user_email, client_ip)
        else:
            rate_limit_ip(client_ip)
    response = flask.Response(status=401)
    response.headers["WWW-Authenticate"] = 'Basic realm="Login Required"'
    return response
