from mailu import models, utils
from mailu.internal import internal, nginx
from flask import current_app as app

import flask
import flask_login
import base64
import binascii
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
    headers = nginx.handle_authentication(flask.request.headers)
    response = flask.Response()
    username = headers.get('Auth-User', None)
    for key, value in headers.items():
        # Auth-User is optional in an auth_http response. Omitting it preserves
        # the client-supplied username and avoids putting SMTPUTF8 data in an
        # HTTP header, which WSGI requires to be Latin-1 encodable.
        if key == 'Auth-User':
            continue
        response.headers[key] = str(value)
    is_valid_user = False
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
        password = urllib.parse.unquote(headers.get('Auth-Pass', ''))
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
        original_uri = flask.request.headers.get("X-Mailu-Original-URI", "").split("?", 1)[0]
        if original_uri.endswith("/sso.php"):
            storage_email = models.IdnaEmail.process_bind_param(flask_login, email, "")
            aliases = models.Alias.query.filter(
                sqlalchemy.cast(models.Alias.destination, sqlalchemy.String).contains(
                    storage_email, autoescape=True
                )
            ).all()
            addresses = sorted({
                models.IdnaEmail.process_bind_param(flask_login, alias.email, "")
                for alias in aliases
                if not alias.wildcard
                and not alias.disabled
                and (not alias.owner or alias.owner.enabled)
                and storage_email in alias.destination
            })
            serialized_aliases = ",".join(addresses)
            if len(serialized_aliases) <= 2048:
                response.headers["X-User-Aliases"] = serialized_aliases
                response.headers["X-User-Aliases-Complete"] = "true"
            else:
                response.headers["X-User-Aliases-Complete"] = "false"
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
        try:
            user_email, password = base64.b64decode(encoded).split(b":", 1)
            user_email = user_email.decode("utf8")
        except (binascii.Error, ValueError, UnicodeDecodeError):
            # malformed header: fall through to the generic 401 below
            user_email = None
        if user_email is not None:
            user, via_alias = models.User.resolve_login(user_email) if '@' in user_email else (None, None)
            target_username = user.email if via_alias else user_email
            if utils.limiter.should_rate_limit_user(target_username, client_ip):
                response = flask.Response(status=401)
                response.headers["WWW-Authenticate"] = 'Basic realm="Authentication rate limit for this username exceeded"'
                response.headers['Retry-After'] = '60'
                return response
            try:
                if not via_alias:
                    user = models.db.session.get(models.User, user_email) if '@' in user_email else None
            except sqlalchemy.exc.StatementError as exc:
                exc = str(exc).split('\n', 1)[0]
                app.logger.warning(f'Invalid user {user_email!r}: {exc}')
            else:
                port = flask.request.headers.get('X-Real-Port', None)
                if user is not None and nginx.check_credentials(
                    user, password.decode('utf-8'), client_ip, "web",
                    port, target_username, via_alias
                ):
                    response = flask.Response()
                    response.headers["X-User"] = models.IdnaEmail.process_bind_param(flask_login, user.email, "")
                    utils.limiter.exempt_ip_from_ratelimits(client_ip)
                    return response
                # We failed check_credentials
                if user:
                    utils.limiter.rate_limit_user(target_username, client_ip)
                else:
                    utils.limiter.rate_limit_ip(client_ip, target_username)
    response = flask.Response(status=401)
    response.headers["WWW-Authenticate"] = 'Basic realm="Login Required"'
    return response
