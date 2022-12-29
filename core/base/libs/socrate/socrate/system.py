import dns.resolver
import hmac
import logging as log
import os
from pwd import getpwnam
import socket
import sys
import tenacity
from textwrap import wrap

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

def _coerce_value(value):
    if isinstance(value, str) and value.lower() in ('true','yes'):
        return True
    elif isinstance(value, str) and value.lower() in ('false', 'no'):
        return False
    return value

def set_env(required_secrets=[]):
    """ This will set all the environment variables and retains only the secrets we need """
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key:
        try:
            secret_key = open(os.environ.get("SECRET_KEY_FILE"), "r").read().strip()
        except Exception as exc:
            log.error(f"Can't read SECRET_KEY from file: {exc}")
            raise exc
    clean_env()
    # derive the keys we need
    for secret in required_secrets:
        os.environ[f'{secret}_KEY'] = hmac.new(bytearray(secret_key, 'utf-8'), bytearray(secret, 'utf-8'), 'sha256').hexdigest()

    try:
        ip_resolver = dns.resolver.query("resolver")[0].address
        log.info(f'Setting DNS to {ip_resolver}')
        with open('/etc/resolv.conf','w') as f:
            f.write(f'nameserver {ip_resolver}\noptions ndots:0\n')
    except:
        pass

    if not os.environ.get('SUBNET'):
        os.environ['SUBNET'] = get_network_v4()

    return {
            key: _coerce_value(os.environ.get(key, value))
            for key, value in os.environ.items()
           }

def clean_env():
    """ remove all secret keys """
    [os.environ.pop(key, None) for key in os.environ.keys() if key.endswith("_KEY")]

def drop_privs_to(username='mailu'):
    pwnam = getpwnam(username)
    os.setgroups([])
    os.setgid(pwnam.pw_gid)
    os.setuid(pwnam.pw_uid)
    os.environ['HOME'] = pwnam.pw_dir

def get_network_v4():
	dflgw = None
	routes = []
	for line in open('/proc/net/route', 'r'):
		r = line.strip().split()
		try:
			route = [r[0]] + [int(c, 16) for c in r[1:]]
		except ValueError:
			pass
		else:
			if route[1] != 0:
				routes.append(route)
			elif dflgw is None:
				dflgw = (route[0], route[2])

	if dflgw is None:
		return None

	intf, ip = dflgw
	for route in routes:
		if route[0] == intf and route[1] == ip&route[7]:
			net = route[1]
			mask = bin(route[7]).count("1")
			return f'{net&0xff}.{net>>8&0xff}.{net>>16&0xff}.{net>>24&0xff}/{mask}'

def get_network_v6():
	dflgw = None
	routes = []
	for line in open('/proc/net/ipv6_route', 'r'):
		r = line.strip().split()
		try:
			route = [r[-1]] + [int(c, 16) for c in r[:-1]]
		except ValueError:
			pass
		else:
			if route[1] != 0 and route[2] != 0:
				routes.append(route)
			elif dflgw is None and route[9] == 3:
				dflgw = (route[0], route[5])

	if dflgw is None:
		return None

	intf, ip = dflgw
	for route in routes:
		if route[0] == intf and route[1] == ip&((2**route[2]-1)^0xffffffffffffffffffffffffffffffff):
			prefix = ':'.join(wrap(f'{route[1]:032x}', 4))
			mask = route[2]
			return f'{prefix}/{mask}'
