"""Exercise the runtime HTTP-01 check without starting the certificate daemon."""

import ast
from http.server import BaseHTTPRequestHandler
import logging
from pathlib import Path
import socket
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class RequestException(Exception):
    pass


class ConnectivityTest(unittest.TestCase):
    def setUp(self):
        # The script starts its daemon at module scope. Load only the probe
        # function so these tests cannot invoke certbot or modify certificates.
        source = Path(__file__).resolve().parents[2] / 'core/nginx/letsencrypt.py'
        tree = ast.parse(source.read_text())
        probe = next(node for node in tree.body
                     if isinstance(node, ast.FunctionDef) and node.name == 'reachable_hostnames')
        self.logger = logging.Logger('test.http01', logging.WARNING)
        self.session = Mock()
        self.session.get.return_value = SimpleNamespace(status_code=200, content=b'test-token')
        self.server = Mock()
        self.dns = Mock(return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.0.2.1', 80)),
        ])
        namespace = dict(
            secrets=SimpleNamespace(token_urlsafe=lambda size: 'test-token'),
            hostname_list=('mail.example.com',), BaseHTTPRequestHandler=BaseHTTPRequestHandler,
            HTTPServer=Mock(return_value=self.server), threading=Mock(),
            requests=SimpleNamespace(Session=lambda: self.session, RequestException=RequestException),
            socket=SimpleNamespace(getaddrinfo=self.dns, AF_INET=socket.AF_INET,
                                   AF_INET6=socket.AF_INET6, SOCK_STREAM=socket.SOCK_STREAM,
                                   gaierror=socket.gaierror),
            time=Mock(), log=self.logger, http01_help='https://mailu.io/master/faq.html#letsencrypt-http-01-connectivity',
        )
        exec(compile(ast.Module(body=[probe], type_ignores=[]), str(source), 'exec'), namespace)
        self.probe = namespace['reachable_hostnames']

    def test_network_failure_has_guidance_without_traceback(self):
        self.session.get.side_effect = RequestException('raw urllib3 connection pool error')
        with self.assertLogs(self.logger, logging.WARNING) as logs:
            self.assertEqual(self.probe(), ())
        output = '\n'.join(logs.output)
        for text in ('mail.example.com', '192.0.2.1', 'TCP port 80', 'hairpin NAT',
                     '#letsencrypt-http-01-connectivity'):
            self.assertIn(text, output)
        self.assertNotIn('raw urllib3', output)
        self.assertTrue(all(record.exc_info is None for record in logs.records))
        self.assertEqual(self.session.get.call_count, 3)
        self.session.close.assert_called_once()
        self.server.shutdown.assert_called_once()
        self.server.server_close.assert_called_once()

    def test_dns_failure_explains_records(self):
        self.dns.side_effect = socket.gaierror('lookup failed')
        with self.assertLogs(self.logger, logging.WARNING) as logs:
            self.assertEqual(self.probe(), ())
        self.assertIn('A/AAAA records', '\n'.join(logs.output))
        self.session.get.assert_not_called()

    def test_wrong_response_explains_proxy_routing(self):
        for status, body in ((301, b''), (404, b''), (200, b'wrong token')):
            with self.subTest(status=status, body=body):
                self.session.get.return_value = SimpleNamespace(status_code=status, content=body)
                with self.assertLogs(self.logger, logging.WARNING) as logs:
                    self.assertEqual(self.probe(), ())
                self.assertIn('without authentication or redirects', '\n'.join(logs.output))

    def test_valid_challenge_is_accepted(self):
        with self.assertNoLogs(self.logger, logging.WARNING):
            self.assertEqual(self.probe(), ('mail.example.com',))
        self.assertFalse(self.session.trust_env)
        self.assertFalse(self.session.get.call_args.kwargs['allow_redirects'])


if __name__ == '__main__':
    unittest.main()
