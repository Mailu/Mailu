from mailu import db, models

import socket
import urllib


SUPPORTED_AUTH_METHODS = ["none", "plain"]


STATUSES = {
    "authentication": ("Authentication credentials invalid", {
        "imap": "AUTHENTICATIONFAILED",
        "smtp": "535 5.7.8",
        "pop3": "-ERR Authentication failed"
    }),
}


def handle_authentication(headers):
    """ Handle an HTTP nginx authentication request
    See: http://nginx.org/en/docs/mail/ngx_mail_auth_http_module.html#protocol
    """
    method = headers["Auth-Method"]
    protocol = headers["Auth-Protocol"]
    # Incoming mail, no authentication
    if method == "none" and protocol == "smtp":
        server, port = get_server(headers["Auth-Protocol"], False)
        return {
            "Auth-Status": "OK",
            "Auth-Server": server,
            "Auth-Port": port
        }
    # Authenticated user
    elif method == "plain":
        server, port = get_server(headers["Auth-Protocol"], True)
        user_email = urllib.parse.unquote(headers["Auth-User"])
        password = urllib.parse.unquote(headers["Auth-Pass"])
        ip = urllib.parse.unquote(headers["Client-Ip"])
        user = models.User.query.get(user_email)
        status = False
        if user:
            for token in user.tokens:
                if (token.check_password(password) and
                    (not token.ip or token.ip == ip)):
                        status = True
            if user.check_password(password):
                status = True
            if status:
                if protocol == "imap" and not user.enable_imap:
                    status = False
                elif protocol == "pop3" and not user.enable_pop:
                    status = False
        if status:
            return {
                "Auth-Status": "OK",
                "Auth-Server": server,
                "Auth-Port": port
            }
        else:
            status, code = get_status(protocol, "authentication")
            return {
                "Auth-Status": status,
                "Auth-Error-Code": code,
                "Auth-Wait": 0
            }
    # Unexpected
    return {}


def get_status(protocol, status):
    """ Return the proper error code depending on the protocol
    """
    status, codes = STATUSES[status]
    return status, codes[protocol]


def get_server(protocol, authenticated=False):
    if protocol == "imap":
        hostname, port = "imap", 143
    elif protocol == "pop3":
        hostname, port = "imap", 110
    elif protocol == "smtp":
        hostname = "smtp"
        port = 10025 if authenticated else 25
    address = socket.gethostbyname(hostname)
    return address, port
