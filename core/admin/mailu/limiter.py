from mailu import utils
from flask import current_app as app
import base64
import limits
import limits.storage
import limits.strategies
import hmac
import secrets

class LimitWrapper(object):
    """ Wraps a limit by providing the storage, item and identifiers
    """

    def __init__(self, limiter, limit, *identifiers):
        self.limiter = limiter
        self.limit = limit
        self.base_identifiers = identifiers

    def test(self, *args):
        return self.limiter.test(self.limit, *(self.base_identifiers + args))

    def hit(self, *args):
        return self.limiter.hit(self.limit, *(self.base_identifiers + args))

    def get_window_stats(self, *args):
        return self.limiter.get_window_stats(self.limit, *(self.base_identifiers + args))


class LimitWraperFactory(object):
    """ Global limiter, to be used as a factory
    """

    def init_app(self, app):
        self.storage = limits.storage.storage_from_string(app.config["RATELIMIT_STORAGE_URL"])
        self.limiter = limits.strategies.MovingWindowRateLimiter(self.storage)

    def get_limiter(self, limit, *args):
        return LimitWrapper(self.limiter, limits.parse(limit), *args)

    def is_subject_to_rate_limits(self, ip):
        key = "exempt-{}".format(ip)
        return not (self.storage.get(key) > 0)
    
    def exempt_ip_from_ratelimits(self, ip):
        key = "exempt-{}".format(ip)
        self.storage.incr(key, app.config["AUTH_RATELIMIT_EXEMPTION_LENGTH"], True)
    
    def should_rate_limit_ip(self, ip):
        limiter = self.get_limiter(app.config["AUTH_RATELIMIT_IP"], 'auth-ip')
        client_network = utils.extract_network_from_ip(ip)
        return self.is_subject_to_rate_limits(ip) and not limiter.test(client_network)
    
    def rate_limit_ip(self, ip):
        if ip != app.config['WEBMAIL_ADDRESS']:
            limiter = self.get_limiter(app.config["AUTH_RATELIMIT_IP"], 'auth-ip')
            client_network = utils.extract_network_from_ip(ip)
            if self.is_subject_to_rate_limits(ip):
                limiter.hit(client_network)
    
    def should_rate_limit_user(self, username, ip, device_cookie=None, device_cookie_name=None):
        limiter = self.get_limiter(app.config["AUTH_RATELIMIT_USER"], 'auth-user')
        return self.is_subject_to_rate_limits(ip) and not limiter.test(device_cookie if device_cookie_name == username else username)
    
    def rate_limit_user(self, username, ip, device_cookie=None, device_cookie_name=None):
        limiter = self.get_limiter(app.config["AUTH_RATELIMIT_USER"], 'auth-user')
        if self.is_subject_to_rate_limits(ip):
            limiter.hit(device_cookie if device_cookie_name == username else username)

    """ Device cookies as described on:
    https://owasp.org/www-community/Slow_Down_Online_Guessing_Attacks_with_Device_Cookies
    """
    def parse_device_cookie(self, cookie):
        try:
            login, nonce, _ = cookie.split('$')
            if hmac.compare_digest(cookie, self.device_cookie(login, nonce)):
                return nonce, login
        except:
            pass
        return None, None

    """ Device cookies don't require strong crypto:
        72bits of nonce, 96bits of signature is more than enough
        and these values avoid padding in most cases
    """
    def device_cookie(self, username, nonce=None):
        if not nonce:
            nonce = secrets.token_urlsafe(9)
        return "{}${}${}".format(username, nonce, str(base64.urlsafe_b64encode(hmac.new(app.device_cookie_key, bytearray("device_cookie|{}|{}".format(username,nonce),'utf-8'), 'sha256').digest()[20:]), 'utf-8'))
