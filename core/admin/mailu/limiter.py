from mailu import utils
from flask import current_app as app
import limits
import limits.storage
import limits.strategies

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
        limiter = self.get_limiter(app.config["AUTH_RATELIMIT_IP"], "auth-ip")
        client_network = utils.extract_network_from_ip(ip)
        return self.is_subject_to_rate_limits(ip) and not limiter.test(client_network)
    
    def rate_limit_ip(self, ip):
        limit_subnet = str(app.config["AUTH_RATELIMIT_SUBNET"]) != 'False'
        subnet = ipaddress.ip_network(app.config["SUBNET"])
        if limit_subnet or ipaddress.ip_address(ip) not in subnet:
            limiter = self.get_limiter(app.config["AUTH_RATELIMIT_IP"], "auth-ip")
            client_network = utils.extract_network_from_ip(ip)
            if self.is_subject_to_rate_limits(ip):
                limiter.hit(client_network)
    
    def should_rate_limit_user(self, username, ip):
        limiter = self.get_limiter(app.config["AUTH_RATELIMIT_USER"], "auth-user")
        return self.is_subject_to_rate_limits(ip) and not limiter.test(username)
    
    def rate_limit_user(self, username, ip):
        limiter = self.get_limiter(app.config["AUTH_RATELIMIT_USER"], "auth-user")
        if self.is_subject_to_rate_limits(ip):
            limiter.hit(username)
