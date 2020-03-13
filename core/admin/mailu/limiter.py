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