import io
import json
from pathlib import Path
import socket
import unittest
from unittest.mock import patch
import preflight as p

ROOT = Path(__file__).parent


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.card = json.loads((ROOT / 'fixtures/anonymous.json').read_text())

    def test_fixture_matrix(self):
        expected = {'anonymous': 'advertised_compatible', 'http_json': 'advertised_compatible',
                    'legacy': 'unknown', 'grpc': 'unsupported', 'authenticated': 'unsupported',
                    'skill_auth': 'unknown', 'ambiguous_auth': 'unknown', 'required_extension': 'unknown',
                    'bad_interface': 'unknown'}
        for fixture, status in expected.items():
            with self.subTest(fixture=fixture):
                report = p.assess(json.loads((ROOT / f'fixtures/{fixture}.json').read_text()))
                self.assertEqual(report['status'], status)
                self.assertEqual(report['behavioral_acceptance'], 'not_tested')

    def test_version_and_binding_on_same_interface(self):
        self.card['supportedInterfaces'] = [
            {'protocolVersion': '0.3', 'protocolBinding': 'JSONRPC', 'url': 'https://example.com/a2a'},
            {'protocolVersion': '1.0', 'protocolBinding': 'GRPC', 'url': 'https://example.com/a2a'}]
        self.assertEqual(p.assess(self.card)['status'], 'unsupported')

    def test_versions_not_product_version(self):
        for version in ('1.0', '1.0.1', '1.0.12'):
            self.card['supportedInterfaces'][0]['protocolVersion'] = version
            self.assertEqual(p.assess(self.card)['status'], 'advertised_compatible')
        for version in ('1.1', '0.3', '1.0beta', None, 1):
            self.card['supportedInterfaces'][0]['protocolVersion'] = version
            self.assertEqual(p.assess(self.card)['status'], 'unsupported')

    def test_malformed_card(self):
        for value in ([], None, 'card'):
            with self.assertRaises(ValueError):
                p.assess(value)
        self.card['securityRequirements'] = 'bearer'
        self.assertEqual(p.assess(self.card)['status'], 'unknown')

    def test_public_ipv6_and_default_port(self):
        p.public_url('https://[2606:4700:4700::1111]/card')
        p.public_url('https://example.com:443/card')

    def test_url_rejections(self):
        for url in ('http://example.com/card', 'https://127.0.0.1/card',
                    'https://10.1.1.1/card', 'https://localhost/card', 'https://[::1]/card',
                    'https://example.com:8443/card', 'https://u:p@example.com/card',
                    'https://example.com/card?key=x', 'https://example.com/card#x',
                    'https://example.com/\ncard'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                p.public_url(url)

    def network(self, body=b'{}', status=200, headers=None):
        class Response:
            def __init__(self):
                self.status = status
                self.stream = io.BytesIO(body)
            def getheader(self, name, default=None):
                return (headers or {}).get(name, default)
            def read1(self, count):
                return self.stream.read(count)
        self.conn.getresponse.return_value = Response()

    def test_mock_http_get_only_and_pinned_tls(self):
        with patch.object(p.socket, 'getaddrinfo', return_value=[(2, 1, 6, '', ('93.184.216.34', 443))]), \
             patch.object(p.http.client, 'HTTPSConnection') as factory:
            self.conn = factory.return_value
            self.network(json.dumps(self.card).encode())
            self.assertEqual(p.fetch_card('https://example.com/card'), self.card)
            args, kw = self.conn.request.call_args
            self.assertEqual(args, ('GET', '/card'))
            self.assertEqual(kw['headers']['User-Agent'], p.USER_AGENT)
            self.assertNotIn('Authorization', kw['headers'])
            self.assertEqual(factory.call_args.args[:2], ('example.com', 443))
            with patch.object(p.socket, 'create_connection') as connect:
                self.conn._create_connection(('example.com', 443), 8)
                self.assertEqual(connect.call_args.args[0], ('93.184.216.34', 443))
            self.conn.close.assert_called_once()

    def test_mock_network_bounds(self):
        with patch.object(p.socket, 'getaddrinfo', return_value=[(2, 1, 6, '', ('93.184.216.34', 443))]), \
             patch.object(p.http.client, 'HTTPSConnection') as factory:
            self.conn = factory.return_value
            cases = [(b'{}', 302, {}), (b'x' * 65537, 200, {}),
                     (b'{}', 200, {'Content-Length': '65537'}),
                     (b'{}', 200, {'Content-Encoding': 'gzip'}),
                     (b'not json', 200, {})]
            for body, status, headers in cases:
                self.network(body, status, headers)
                with self.assertRaises(ValueError):
                    p.fetch_card('https://example.com/card')
            self.conn.request.side_effect = socket.timeout('timed out')
            with self.assertRaises(socket.timeout):
                p.fetch_card('https://example.com/card')

    def test_private_dns_no_connection(self):
        with patch.object(p.socket, 'getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 443))]), \
             patch.object(p.http.client, 'HTTPSConnection') as factory:
            with self.assertRaises(ValueError):
                p.fetch_card('https://example.com/card')
            factory.assert_not_called()

    def test_cli_exit_codes(self):
        for fixture, code in [('anonymous', 0), ('authenticated', 1), ('legacy', 2)]:
            card = json.loads((ROOT / f'fixtures/{fixture}.json').read_text())
            with patch.object(p, 'fetch_card', return_value=card), patch('sys.stdout', new_callable=io.StringIO):
                self.assertEqual(p.main(['https://example.com/card']), code)
        with patch.object(p, 'fetch_card', side_effect=ValueError('bad JSON')), patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(p.main(['https://example.com/card']), 3)


if __name__ == '__main__':
    unittest.main()
