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

    def init_app(self, app):
        self.storage = limits.storage.storage_from_string(app.config["RATELIMIT_STORAGE_URL"])
        self.limiter = limits.strategies.MovingWindowRateLimiter(self.storage)
        self.rate = limits.parse(app.config["AUTH_RATELIMIT"])
        self.subnet = ipaddress.ip_network(app.config["SUBNET"])

    def check(self,clientip):
        # TODO: activate this code if we have limits at webmail level
        #if ipaddress.ip_address(clientip) in self.subnet:
        #    # no limits for internal requests (e.g. from webmail)
        #    return
        if not self.limiter.test(self.rate,"client-ip",clientip):
            raise RateLimitExceeded()

    def hit(self,clientip):
        # TODO: activate this code if we have limits at webmail level
        #if ipaddress.ip_address(clientip) in self.subnet:
        #    # no limits for internal requests (e.g. from webmail)
        #    return
        if not self.limiter.hit(self.rate,"client-ip",clientip):
            raise RateLimitExceeded()
