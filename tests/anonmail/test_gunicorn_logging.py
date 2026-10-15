"""Gunicorn logging regressions, collected by the admin unit test suite."""

import errno
import importlib.util
import logging
from pathlib import Path
import unittest

from gunicorn.http2.errors import HTTP2ConnectionError, HTTP2ProtocolError


source = Path(__file__).resolve().parents[2] / 'core/admin/mailu/gunicorn_logging.py'
if not source.is_file():
    # The admin image has a flattened /app/mailu layout.
    source = Path(importlib.util.find_spec('mailu').origin).with_name('gunicorn_logging.py')
spec = importlib.util.spec_from_file_location('gunicorn_logging', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DisconnectLoggingTest(unittest.TestCase):
    def setUp(self):
        self.logger = object.__new__(module.Logger)
        self.logger.error_log = logging.Logger('test.gunicorn', logging.DEBUG)

    def log_wrapped_error(self, error, *, explicit=False):
        try:
            try:
                raise error
            except OSError as exc:
                if explicit:
                    raise HTTP2ConnectionError('Socket error') from exc
                raise HTTP2ConnectionError('Socket error')
        except HTTP2ConnectionError:
            self.logger.exception('HTTP/2 connection error')

    def test_disconnects_are_debug_with_traceback(self):
        for code in (errno.EPIPE, errno.ECONNRESET):
            for explicit in (False, True):
                with self.subTest(code=code, explicit=explicit):
                    with self.assertLogs(self.logger.error_log, logging.DEBUG) as logs:
                        self.log_wrapped_error(OSError(code, 'disconnected'), explicit=explicit)
                    self.assertEqual(logs.records[0].levelno, logging.DEBUG)
                    self.assertIsNotNone(logs.records[0].exc_info)

    def test_disconnects_are_quiet_at_info(self):
        with self.assertNoLogs(self.logger.error_log, logging.INFO):
            self.log_wrapped_error(BrokenPipeError(errno.EPIPE, 'broken pipe'))

    def test_other_socket_errors_remain_errors(self):
        with self.assertLogs(self.logger.error_log, logging.ERROR) as logs:
            self.log_wrapped_error(OSError(errno.EIO, 'I/O error'))
        self.assertIsNotNone(logs.records[0].exc_info)

    def test_protocol_and_application_errors_remain_errors(self):
        for error in (HTTP2ConnectionError('protocol failure'),
                      HTTP2ProtocolError('invalid frame'), ValueError('application error'),
                      BrokenPipeError(errno.EPIPE, 'unwrapped error')):
            with self.subTest(error=error):
                with self.assertLogs(self.logger.error_log, logging.ERROR) as logs:
                    try:
                        raise error
                    except Exception:
                        self.logger.exception('Error handling request')
                self.assertIsNotNone(logs.records[0].exc_info)


if __name__ == '__main__':
    unittest.main()
