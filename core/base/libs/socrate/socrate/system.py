import socket
import tenacity
from os import environ
import logging as log

@tenacity.retry(stop=tenacity.stop_after_attempt(100),
                wait=tenacity.wait_random(min=2, max=5))
def resolve_hostname(hostname):
    """ This function uses system DNS to resolve a hostname.
    It is capable of retrying in case the host is not immediately available
    """
    try:
        return sorted(socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM, 0, socket.AI_PASSIVE), key=lambda s:s[0])[0][4][0]
    except Exception as e:
        log.warn("Unable to lookup '%s': %s",hostname,e)
        raise e


def resolve_address(address):
    """ This function is identical to ``resolve_hostname`` but also supports
    resolving an address, i.e. including a port.
    """
    hostname, *rest = address.rsplit(":", 1)
    ip_address = resolve_hostname(hostname)
    if ":" in ip_address:
        ip_address = "[{}]".format(ip_address)
    return ip_address + "".join(":" + port for port in rest)


def get_host_address_from_environment(name, default):
    """ This function looks up an envionment variable ``{{ name }}_ADDRESS``.
    If it's defined, it is returned unmodified. If it's undefined, an environment
    variable ``HOST_{{ name }}`` is looked up and resolved to an ip address.
    If this is also not defined, the default is resolved to an ip address.
    """
    if "{}_ADDRESS".format(name) in environ:
        return environ.get("{}_ADDRESS".format(name))
    return resolve_address(environ.get("HOST_{}".format(name), default))
