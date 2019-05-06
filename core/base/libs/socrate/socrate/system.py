import socket
import tenacity


@tenacity.retry(stop=tenacity.stop_after_attempt(100),
                wait=tenacity.wait_random(min=2, max=5))
def resolve_hostname(hostname):
    """ This function uses system DNS to resolve a hostname.
    It is capable of retrying in case the host is not immediately available
    """
    return socket.gethostbyname(hostname)


def resolve_address(address):
    """ This function is identical to ``resolve_host`` but also supports
    resolving an address, i.e. including a port.
    """
    hostname, *rest = address.rsplit(":", 1)
    ip_address = resolve_hostname(hostname)
    return ip_address + "".join(":" + port for port in rest)
