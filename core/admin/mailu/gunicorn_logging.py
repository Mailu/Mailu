"""Gunicorn logging policy for the admin service."""

import errno
import logging
import sys

from gunicorn import glogging
from gunicorn.http2.errors import HTTP2ConnectionError


class NoPingFilter(logging.Filter):
    skipAccessLogs = False

    def __init__(self, filterAccessLogs=False):
        self.skipAccessLogs = filterAccessLogs

    def filter(self, record):
        if self.skipAccessLogs and record.args['r'].endswith(' HTTP/1.1'):
            return False
        if record.args['r'].endswith(' /ping HTTP/1.1'):
            return False
        if record.args['r'].endswith(' /internal/rspamd/local_domains HTTP/1.1'):
            return False
        return True


class Logger(glogging.Logger):
    def setup(self, cfg):
        super().setup(cfg)
        logger = logging.getLogger("gunicorn.access")
        logger.addFilter(NoPingFilter(logger.getEffectiveLevel() > logging.DEBUG))

    def exception(self, msg, *args, **kwargs):
        exc = sys.exc_info()[1]
        if isinstance(exc, HTTP2ConnectionError):
            # Gunicorn wraps socket errors with implicit exception chaining.
            # Only ordinary peer disconnects should lose their ERROR severity.
            socket_error = exc.__cause__ or exc.__context__
            if isinstance(socket_error, OSError) and socket_error.errno in (
                errno.EPIPE, errno.ECONNRESET,
            ):
                kwargs.setdefault('exc_info', True)
                self.debug(msg, *args, **kwargs)
                return
        super().exception(msg, *args, **kwargs)
