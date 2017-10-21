from mailu import db, models

import socket


SUPPORTED_AUTH_METHODS = ["none", "plain"]

STATUSES = {
    "authentication": ("Authentication credentials invalid", {
        "imap": "AUTHENTICATIONFAILED",
        "smtp": "535 5.7.8",
        "pop3": ""
    }),
}


SERVER_MAP = {
    "imap": ("imap", 143),
    "smtp": ("smtp", 25)
}


def handle_authentication(headers):
    """ Handle an HTTP nginx authentication request
    See: http://nginx.org/en/docs/mail/ngx_mail_auth_http_module.html#protocol
    """
    method = headers["Auth-Method"]
    protocol = headers["Auth-Protocol"]
    server, port = get_server(headers["Auth-Protocol"])
    # Incoming mail, no authentication
    if method == "none" and protocol == "smtp":
        return {
            "Auth-Status": "OK",
            "Auth-Server": server,
            "Auth-Port": port
        }
    # Authenticated user
    elif method == "plain":
        user_email = headers["Auth-User"]
        password = headers["Auth-Pass"]
        user = models.User.query.get(user_email)
        if user and user.check_password(password):
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
    else:
        return {}


def get_status(protocol, status):
    """ Return the proper error code depending on the protocol
    """
    status, codes = STATUSES[status]
    return status, codes[protocol]


def get_server(protocol):
    hostname, port = SERVER_MAP[protocol]
    address = socket.gethostbyname(hostname)
    return address, port
