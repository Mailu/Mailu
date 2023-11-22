from mailu import models, utils
from flask import current_app as app
from socrate import system

import urllib
import ipaddress
import sqlalchemy.exc

SUPPORTED_AUTH_METHODS = ["none", "plain"]


STATUSES = {
    "authentication": ("Authentication credentials invalid", {
        "imap": "AUTHENTICATIONFAILED",
        "smtp": "535 5.7.8",
        "submission": "535 5.7.8",
        "pop3": "-ERR Authentication failed",
        "sieve": "AuthFailed"
    }),
    "encryption": ("Must issue a STARTTLS command first", {
        "smtp": "530 5.7.0"
    }),
    "ratelimit": ("Temporary authentication failure (rate-limit)", {
        "imap": "LIMIT",
        "smtp": "451 4.3.2",
        "submission": "451 4.3.2",
        "pop3": "-ERR [LOGIN-DELAY] Retry later",
        "sieve": "AuthFailed"
    }),
}

WEBMAIL_PORTS = ['14190', '10143', '10025']

def check_credentials(user, password, ip, protocol=None, auth_port=None, source_port=None, raw_user=None):
    if not user or not user.enabled or (protocol == "imap" and not user.enable_imap and not auth_port in WEBMAIL_PORTS) or (protocol == "pop3" and not user.enable_pop):
        app.logger.info(f'Login attempt for: {user or raw_user!r}/{protocol}/{auth_port} from: {ip}/{source_port}: failed: account disabled')
        return False
    # webmails
    if auth_port in WEBMAIL_PORTS and password.startswith('token-'):
        if utils.verify_temp_token(user.get_id(), password):
            app.logger.debug(f'Login attempt for: {user}/{protocol}/{auth_port} from: {ip}/{source_port}: success: webmail-token')
            return True
    if utils.is_app_token(password):
        for token in user.tokens:
            if token.check_password(password):
                if not token.ip or utils.is_ip_in_subnet(ip, token.ip):
                    app.logger.info(f'Login attempt for: {user}/{protocol}/{auth_port} from: {ip}/{source_port}: success: token-{token.id}: {token.comment or ""!r}')
                    return True
                else:
                    app.logger.info(f'Login attempt for: {user}/{protocol}/{auth_port} from: {ip}/{source_port}: failed: badip: token-{token.id}: {token.comment or ""!r}')
                    return False # we can return directly here since the token is valid
    if user.check_password(password):
        if app.config['AUTH_REQUIRE_TOKENS'] and not protocol in ['web', 'sso']:
            app.logger.info(f'Login attempt for: {user}/{protocol}/{auth_port} from: {ip}/{source_port}: failed: password ok, but a token is required')
            return False
        else:
            app.logger.info(f'Login attempt for: {user}/{protocol}/{auth_port} from: {ip}/{source_port}: success: password')
            return True
    app.logger.info(f'Login attempt for: {user}/{protocol}/{auth_port} from: {ip}/{source_port}: failed: badauth: {utils.truncated_pw_hash(password)}')
    return False

def handle_authentication(headers):
    """ Handle an HTTP nginx authentication request
    See: http://nginx.org/en/docs/mail/ngx_mail_auth_http_module.html#protocol
    """
    method = headers["Auth-Method"].lower()
    protocol = headers["Auth-Protocol"].lower()
    # Incoming mail, no authentication
    if method in ['', 'none'] and protocol in ['smtp', 'lmtp']:
        server, port = get_server(protocol, False)
        if app.config["INBOUND_TLS_ENFORCE"]:
            if "Auth-SSL" in headers and headers["Auth-SSL"] == "on":
                return {
                    "Auth-Status": "OK",
                    "Auth-Server": server,
                    "Auth-Port": port
                }
            else:
                status, code = get_status(protocol, "encryption")
                return {
                    "Auth-Status": status,
                    "Auth-Error-Code" : code,
                    "Auth-Wait": 0
                }
        else:
            return {
                "Auth-Status": "OK",
                "Auth-Server": server,
                "Auth-Port": port
            }
    # Authenticated user
    elif method in ['plain', 'login']:
        is_valid_user = False
        # According to RFC2616 section 3.7.1 and PEP 3333, HTTP headers should
        # be ASCII and are generally considered ISO8859-1. However when passing
        # the password, nginx does not transcode the input UTF string, thus
        # we need to manually decode.
        raw_user_email = urllib.parse.unquote(headers["Auth-User"])
        raw_password = urllib.parse.unquote(headers["Auth-Pass"])
        user_email = 'invalid'
        password = 'invalid'
        try:
            user_email = raw_user_email.encode("iso8859-1").decode("utf8")
            password = raw_password.encode("iso8859-1").decode("utf8")
            ip = urllib.parse.unquote(headers["Client-Ip"])
        except:
            app.logger.warn(f'Received undecodable user/password from nginx: {raw_user_email!r}/{raw_password!r}')
        else:
            try:
                user = models.User.query.get(user_email) if '@' in user_email else None
            except sqlalchemy.exc.StatementError as exc:
                exc = str(exc).split('\n', 1)[0]
                app.logger.warn(f'Invalid user {user_email!r}: {exc}')
            else:
                is_valid_user = user is not None
                ip = urllib.parse.unquote(headers["Client-Ip"])
                if check_credentials(user, password, ip, protocol, headers["Auth-Port"], headers['Client-Port'], user_email):
                    server, port = get_server(headers["Auth-Protocol"], True)
                    return {
                        "Auth-Status": "OK",
                        "Auth-Server": server,
                        "Auth-User": user_email,
                        "Auth-User-Exists": is_valid_user,
                        "Auth-Port": port
                    }
        status, code = get_status(protocol, "authentication")
        return {
            "Auth-Status": status,
            "Auth-Error-Code": code,
            "Auth-User": user_email,
            "Auth-User-Exists": is_valid_user,
            "Auth-Wait": 0
        }
    # Unexpected
    raise Exception(f"SHOULD NOT HAPPEN {protocol} {method}")


def get_status(protocol, status):
    """ Return the proper error code depending on the protocol
    """
    status, codes = STATUSES[status]
    return status, codes[protocol]

def get_server(protocol, authenticated=False):
    if protocol == 'imap':
        hostname, port = app.config['IMAP_ADDRESS'], 143
    elif protocol == 'pop3':
        hostname, port = app.config['IMAP_ADDRESS'], 110
    elif protocol == 'smtp':
        if authenticated:
            hostname, port = app.config['SMTP_ADDRESS'], 10025
        else:
            hostname, port = app.config['SMTP_ADDRESS'], 25
    elif protocol == 'submission':
        hostname, port = app.config['SMTP_ADDRESS'], 10025
    elif protocol == 'lmtp':
        hostname, port = app.config['IMAP_ADDRESS'], 2525
    elif protocol == 'sieve':
        hostname, port = app.config['IMAP_ADDRESS'], 4190
    try:
        # test if hostname is already resolved to an ip address
        ipaddress.ip_address(hostname)
    except:
        # hostname is not an ip address - so we need to resolve it
        hostname = system.resolve_hostname(hostname)
    return hostname, port
