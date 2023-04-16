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
        return False if utils.is_exempt_from_ratelimits(ip) else not (self.storage.get(f'exempt-{ip}') > 0)

    def exempt_ip_from_ratelimits(self, ip):
        self.storage.incr(f'exempt-{ip}', app.config["AUTH_RATELIMIT_EXEMPTION_LENGTH"], True)

    def should_rate_limit_ip(self, ip):
        limiter = self.get_limiter(app.config["AUTH_RATELIMIT_IP"], 'auth-ip')
        client_network = utils.extract_network_from_ip(ip)
        is_rate_limited = self.is_subject_to_rate_limits(ip) and not limiter.test(client_network)
        if is_rate_limited:
            app.logger.warn(f'Authentication attempt from {ip} has been rate-limited.')
        return is_rate_limited

    def rate_limit_ip(self, ip, username=None):
        limiter = self.get_limiter(app.config['AUTH_RATELIMIT_IP'], 'auth-ip')
        client_network = utils.extract_network_from_ip(ip)
        if self.is_subject_to_rate_limits(ip):
            if username and self.storage.get(f'dedup-{client_network}-{username}') > 0:
                return
            self.storage.incr(f'dedup-{client_network}-{username}', limits.parse(app.config['AUTH_RATELIMIT_IP']).GRANULARITY.seconds, True)
            limiter.hit(client_network)

    def should_rate_limit_user(self, username, ip, device_cookie=None, device_cookie_name=None):
        limiter = self.get_limiter(app.config["AUTH_RATELIMIT_USER"], 'auth-user')
        is_rate_limited = self.is_subject_to_rate_limits(ip) and not limiter.test(device_cookie if device_cookie_name == username else username)
        if is_rate_limited:
            app.logger.warn(f'Authentication attempt from {ip} for {username} has been rate-limited.')
        return is_rate_limited

    def rate_limit_user(self, username, ip, device_cookie=None, device_cookie_name=None, password=''):
        limiter = self.get_limiter(app.config["AUTH_RATELIMIT_USER"], 'auth-user')
        if self.is_subject_to_rate_limits(ip):
            truncated_password = hmac.new(bytearray(username, 'utf-8'), bytearray(password, 'utf-8'), 'sha256').hexdigest()[-6:]
            if password and (self.storage.get(f'dedup2-{username}-{truncated_password}') > 0):
                return
            self.storage.incr(f'dedup2-{username}-{truncated_password}', limits.parse(app.config['AUTH_RATELIMIT_USER']).GRANULARITY.seconds, True)
            limiter.hit(device_cookie if device_cookie_name == username else username)
            self.rate_limit_ip(ip, username)

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
        sig = str(base64.urlsafe_b64encode(hmac.new(app.device_cookie_key, bytearray(f'device_cookie|{username}|{nonce}', 'utf-8'), 'sha256').digest()[20:]), 'utf-8')
        return f'{username}${nonce}${sig}'
