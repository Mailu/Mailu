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
        # /24
        return str(n.supernet(prefixlen_diff=(32-int(app.config["AUTH_RATELIMIT_IP_V4_MASK"]))).network_address)
    elif isinstance(n, ipaddress.IPv6Network):
        # /56
        return str(n.supernet(prefixlen_diff=(128-int(app.config["AUTH_RATELIMIT_IP_V6_MASK"]))).network_address)
    else: # not sure what to do with it
        return ip

def isExempt(ip):
    key = "exempt-{}".format(ip)
    return utils.limiter.storage.get(key) > 0

def exemptIP(ip):
    key = "exempt-{}".format(ip)
    utils.limiter.storage.incr(key, app.config["AUTH_RATELIMIT_EXEMPTION_LENGTH"], True)

def shouldRateLimitSubnet(ip):
    """ Tell us whether we should take rate-limiting into account for this IP
    """
    limiter = utils.limiter.get_limiter(app.config["AUTH_RATELIMIT_IP"], "auth-ip")
    client_network = extract_network_from_ip(ip)
    return not isExempt(ip) and not limiter.test(client_network)

def rateLimitSubnet(ip):
    """ Increase the hit count to ensure that subsequent attempts can be rate-limited
    """
    limit_subnet = str(app.config["AUTH_RATELIMIT_SUBNET"]) != 'False'
    subnet = ipaddress.ip_network(app.config["SUBNET"])
    if limit_subnet or ipaddress.ip_address(ip) not in subnet:
        limiter = utils.limiter.get_limiter(app.config["AUTH_RATELIMIT_IP"], "auth-ip")
        client_network = extract_network_from_ip(ip)
        if not isExempt(ip):
            limiter.hit(client_network)

def shouldRateLimitUser(username, ip):
    """ Tell us whether we should take rate-limiting into account for this username
    """
    limiter = utils.limiter.get_limiter(app.config["AUTH_RATELIMIT_USER"], "auth-user")
    return not isExempt(ip) and not limiter.test(username)

def rateLimitUser(username, ip):
    """ Increase the hit count to ensure that subsequent attempts can be rate-limited
    """
    limiter = utils.limiter.get_limiter(app.config["AUTH_RATELIMIT_USER"], "auth-user")
    if not isExempt(ip):
        limiter.hit(username)

@internal.route("/auth/email")
def nginx_authentication():
    """ Main authentication endpoint for Nginx email server
    """
    client_ip = flask.request.headers["Client-Ip"]
    if shouldRateLimitSubnet(client_ip):
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

    isValidUser = False
    if "Auth-User-Exists" in response.headers and response.headers["Auth-User-Exists"] == "True":
        username = response.headers["Auth-User"]
        if shouldRateLimitUser(username, client_ip):
            # FIXME should be done before the handle_authentication
            response = flask.Response()
            response.headers['Auth-Status'] = 'Authentication rate limit for this username exceeded'
            response.headers['Auth-Error-Code'] = '451 4.3.2'
            if int(flask.request.headers['Auth-Login-Attempt']) < 10:
                response.headers['Auth-Wait'] = '3'
            return response
        isValidUser = True
    if ("Auth-Status" not in headers) or (headers["Auth-Status"] != "OK"):
        if isValidUser:
            rateLimitUser(username, client_ip)
        else:
            rateLimitSubnet(client_ip)
    elif ("Auth-Status" in headers) and (headers["Auth-Status"] == "OK"):
        exemptIP(client_ip)
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
    if shouldRateLimitSubnet(client_ip):
        response = flask.Response(status=401)
        response.headers["WWW-Authenticate"] = 'Basic realm="Authentication rate limit from one source exceeded"'
        response.headers['Retry-After'] = '60'
        return response
    authorization = flask.request.headers.get("Authorization")
    if authorization and authorization.startswith("Basic "):
        encoded = authorization.replace("Basic ", "")
        user_email, password = base64.b64decode(encoded).split(b":")
        user_email = user_email.decode("utf8")
        if shouldRateLimitUser(user_email, client_ip):
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
                exemptIP(client_ip)
                return response
            rateLimitUser(user_email, client_ip)
        else:
            rateLimitSubnet(client_ip)
    response = flask.Response(status=401)
    response.headers["WWW-Authenticate"] = 'Basic realm="Login Required"'
    return response
