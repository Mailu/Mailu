from mailu import models
from flask import current_app as app

import re
import urllib
import ipaddress
import socket
import tenacity


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
        if status and user.enabled:
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

def extract_host_port(host_and_port, default_port):
    host, _, port = re.match('^(.*)(:([0-9]*))?$', host_and_port).groups()
    return host, int(port) if port else default_port

def get_server(protocol, authenticated=False):
    if protocol == "imap":
        hostname, port = extract_host_port(app.config['IMAP_ADDRESS'], 143)
    elif protocol == "pop3":
        hostname, port = extract_host_port(app.config['POP3_ADDRESS'], 110)
    elif protocol == "smtp":
        if authenticated:
            hostname, port = extract_host_port(app.config['AUTHSMTP_ADDRESS'], 10025)
        else:
            hostname, port = extract_host_port(app.config['SMTP_ADDRESS'], 25)
    try:
        # test if hostname is already resolved to an ip adddress
        ipaddress.ip_address(hostname)
    except:
        # hostname is not an ip address - so we need to resolve it
        hostname = resolve_hostname(hostname)
    return hostname, port

@tenacity.retry(stop=tenacity.stop_after_attempt(100),
                wait=tenacity.wait_random(min=2, max=5))
def resolve_hostname(hostname):
    """ This function uses system DNS to resolve a hostname.
    It is capable of retrying in case the host is not immediately available
    """
    return socket.gethostbyname(hostname)
