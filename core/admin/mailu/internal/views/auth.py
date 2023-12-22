from mailu import models, utils
from mailu.internal import internal, nginx
from flask import current_app as app

import flask
import flask_login
import base64
import sqlalchemy.exc
import urllib

@internal.route("/auth/email")
def nginx_authentication():
    """ Main authentication endpoint for Nginx email server
    """
    client_ip = flask.request.headers["Client-Ip"]
    headers = flask.request.headers
    is_port_25 = headers["Auth-Port"] == '25'
    if is_port_25 and headers['Auth-Method'] != 'none':
        response = flask.Response()
        response.headers['Auth-Status'] = 'AUTH not supported'
        response.headers['Auth-Error-Code'] = '502 5.5.1'
        utils.limiter.rate_limit_ip(client_ip)
        return response
    is_from_webmail = headers['Auth-Port'] in ['10143', '10025']
    is_app_token = utils.is_app_token(headers.get('Auth-Pass',''))
    if not is_from_webmail and not is_port_25 and not is_app_token and utils.limiter.should_rate_limit_ip(client_ip):
        status, code = nginx.get_status(flask.request.headers['Auth-Protocol'], 'ratelimit')
        response = flask.Response()
        response.headers['Auth-Status'] = status
        response.headers['Auth-Error-Code'] = code
        return response
    raw_password = urllib.parse.unquote(headers['Auth-Pass']) if 'Auth-Pass' in headers else ''
    headers = nginx.handle_authentication(flask.request.headers)
    response = flask.Response()
    for key, value in headers.items():
        response.headers[key] = str(value)
    is_valid_user = False
    username = response.headers.get('Auth-User', None)
    if response.headers.get("Auth-User-Exists") == "True":
        if not is_from_webmail and not is_app_token and utils.limiter.should_rate_limit_user(username, client_ip):
            # FIXME could be done before handle_authentication()
            status, code = nginx.get_status(flask.request.headers['Auth-Protocol'], 'ratelimit')
            response = flask.Response()
            response.headers['Auth-Status'] = status
            response.headers['Auth-Error-Code'] = code
            return response
        is_valid_user = True
    if headers.get("Auth-Status") == "OK":
        # successful email delivery isn't enough to warrant an exemption
        if not is_port_25:
            utils.limiter.exempt_ip_from_ratelimits(client_ip)
    elif is_valid_user:
        password = None
        try:
            password = raw_password.encode("iso8859-1").decode("utf8")
        except:
            app.logger.warn(f'Received undecodable password for {username} from nginx: {raw_password!r}')
            utils.limiter.rate_limit_user(username, client_ip, password=None)
        else:
            utils.limiter.rate_limit_user(username, client_ip, password=password)
    elif not is_from_webmail:
        utils.limiter.rate_limit_ip(client_ip, username)
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

@internal.route("/auth/user")
def user_authentication():
    """ Fails if the user is not authenticated.
    """
    if (not flask_login.current_user.is_anonymous
        and flask_login.current_user.enabled):
        response = flask.Response()
        email = flask_login.current_user.get_id()
        response.headers["X-User"] = models.IdnaEmail.process_bind_param(flask_login, email, "")
        response.headers["X-User-Token"] = utils.gen_temp_token(email, flask.session)
        return response
    return flask.abort(403)


@internal.route("/auth/basic")
def basic_authentication():
    """ Tries to authenticate using the Authorization header.
    """
    client_ip = flask.request.headers.get('X-Real-IP', flask.request.remote_addr)
    if utils.limiter.should_rate_limit_ip(client_ip):
        response = flask.Response(status=401)
        response.headers["WWW-Authenticate"] = 'Basic realm="Authentication rate limit from one source exceeded"'
        response.headers['Retry-After'] = '60'
        return response
    authorization = flask.request.headers.get("Authorization")
    if authorization and authorization.startswith("Basic "):
        encoded = authorization.replace("Basic ", "")
        user_email, password = base64.b64decode(encoded).split(b":", 1)
        user_email = user_email.decode("utf8")
        if utils.limiter.should_rate_limit_user(user_email, client_ip):
            response = flask.Response(status=401)
            response.headers["WWW-Authenticate"] = 'Basic realm="Authentication rate limit for this username exceeded"'
            response.headers['Retry-After'] = '60'
            return response
        try:
            user = models.User.query.get(user_email) if '@' in user_email else None
        except sqlalchemy.exc.StatementError as exc:
            exc = str(exc).split('\n', 1)[0]
            app.logger.warn(f'Invalid user {user_email!r}: {exc}')
        else:
            if user is not None and nginx.check_credentials(user, password.decode('utf-8'), client_ip, "web", flask.request.headers.get('X-Real-Port', None), user_email):
                response = flask.Response()
                response.headers["X-User"] = models.IdnaEmail.process_bind_param(flask_login, user.email, "")
                utils.limiter.exempt_ip_from_ratelimits(client_ip)
                return response
            # We failed check_credentials
            utils.limiter.rate_limit_user(user_email, client_ip) if user else utils.limiter.rate_limit_ip(client_ip, user_email)
    response = flask.Response(status=401)
    response.headers["WWW-Authenticate"] = 'Basic realm="Login Required"'
    return response
