import hmac
import logging as log
import os
import socket
import tenacity

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

    return {
            key: _coerce_value(os.environ.get(key, value))
            for key, value in os.environ.items()
           }

def clean_env():
    """ remove all secret keys """
    [os.environ.pop(key, None) for key in os.environ.keys() if key.endswith("_KEY")]
