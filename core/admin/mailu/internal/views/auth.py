from mailu import models, utils
from mailu.internal import internal, nginx
from flask import current_app as app

import flask
import flask_login
import base64
import binascii
import sqlalchemy.exc
import sqlalchemy
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
            aliases = models.db.session.query(
                models.Alias.email, models.Alias.destination,
            ).outerjoin(
                models.User, models.Alias.owner_email == models.User.email,
            ).filter(
                sqlalchemy.cast(models.Alias.destination, sqlalchemy.String).contains(
                    storage_email, autoescape=True
                ),
                models.Alias.wildcard.is_(False),
                models.Alias.disabled.is_(False),
                sqlalchemy.or_(models.Alias.owner_email.is_(None), models.User.enabled.is_(True)),
            ).all()
            addresses = sorted({
                models.IdnaEmail.process_bind_param(flask_login, alias_email, "")
                for alias_email, destinations in aliases
                if storage_email in destinations
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
    """Authenticate device credentials, browser sessions and webmail tokens.

    Nginx forwards the source address in X-Forwarded-By, replacing any
    client-supplied value. Public DAV requests may use webmail tokens only from
    the configured container subnet. The private webmail listener marks its
    requests separately and is not published by Compose. An explicit
    Authorization header never falls back to the browser session.
    """
    context = flask.request.headers.get("X-Mailu-Auth-Context")
    source_ip = flask.request.headers.get("X-Forwarded-By", "")
    subnets = [app.config["SUBNET"], app.config["SUBNET6"]]
    webmail = context == "webdav-internal"
    if context == "webdav" and source_ip:
        try:
            webmail = utils.is_ip_in_subnet(source_ip, [subnet for subnet in subnets if subnet])
        except ValueError:
            # A missing or invalid forwarded address must never grant local access.
            pass
    if context == "webdav" and not flask.request.headers.get("Authorization"):
        method = flask.request.headers.get("X-Mailu-Original-Method", "")
        # DAV writes use non-simple HTTP methods, but also require Fetch
        # Metadata here to prevent cross-site requests using session cookies.
        if method in ("GET", "HEAD") or flask.request.headers.get("Sec-Fetch-Site") == "same-origin":
            if not flask_login.current_user.is_anonymous and flask_login.current_user.enabled:
                response = flask.Response()
                response.headers["X-User"] = models.IdnaEmail.process_bind_param(
                    flask_login, flask_login.current_user.email, "",
                )
                return response
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
            password = password.decode("utf8")
        except (binascii.Error, ValueError, UnicodeDecodeError):
            # malformed header: fall through to the generic 401 below
            user_email = None
        if user_email is not None:
            if utils.limiter.should_rate_limit_user(user_email, client_ip):
                response = flask.Response(status=401)
                response.headers["WWW-Authenticate"] = 'Basic realm="Authentication rate limit for this username exceeded"'
                response.headers['Retry-After'] = '60'
                return response
            try:
                user = models.db.session.get(models.User, user_email) if '@' in user_email else None
            except sqlalchemy.exc.StatementError as exc:
                exc = str(exc).split('\n', 1)[0]
                app.logger.warning(f'Invalid user {user_email!r}: {exc}')
            else:
                valid = user is not None and (
                    (webmail and user.enabled and utils.verify_temp_token(user.get_id(), password))
                    or nginx.check_credentials(user, password, client_ip, "web", flask.request.headers.get('X-Real-Port', None), user_email)
                )
                if valid:
                    response = flask.Response()
                    response.headers["X-User"] = models.IdnaEmail.process_bind_param(flask_login, user.email, "")
                    utils.limiter.exempt_ip_from_ratelimits(client_ip)
                    return response
                # We failed check_credentials
                utils.limiter.rate_limit_user(user_email, client_ip) if user else utils.limiter.rate_limit_ip(client_ip, user_email)
    response = flask.Response(status=401)
    response.headers["WWW-Authenticate"] = 'Basic realm="Login Required"'
    return response
