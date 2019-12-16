import limits
import limits.storage
import limits.strategies
import ipaddress

class RateLimitExceeded(Exception):
    pass

class Limiter:

    def __init__(self):
        self.storage = None
        self.limiter = None
        self.rate = None
        self.subnet = None
        self.rate_limit_subnet = True

    def init_app(self, app):
        self.storage = limits.storage.storage_from_string(app.config["RATELIMIT_STORAGE_URL"])
        self.limiter = limits.strategies.MovingWindowRateLimiter(self.storage)
        self.rate = limits.parse(app.config["AUTH_RATELIMIT"])
        self.rate_limit_subnet = str(app.config["AUTH_RATELIMIT_SUBNET"])!='False'
        self.subnet = ipaddress.ip_network(app.config["SUBNET"])

    def check(self,clientip):
        # disable limits for internal requests (e.g. from webmail)?
        if rate_limit_subnet==False and ipaddress.ip_address(clientip) in self.subnet:
            return
        if not self.limiter.test(self.rate,"client-ip",clientip):
            raise RateLimitExceeded()

    def hit(self,clientip):
        # disable limits for internal requests (e.g. from webmail)?
        if rate_limit_subnet==False and ipaddress.ip_address(clientip) in self.subnet:
            return
        self.limiter.hit(self.rate,"client-ip",clientip)
