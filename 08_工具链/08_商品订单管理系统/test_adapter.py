"""离线协议测试，不持有真实凭证，不产生网络调用。"""
import hashlib
import hmac
import unittest
from urllib.parse import parse_qs, urlsplit

from doudian_adapter import prepare, serialize, signature


class AdapterTests(unittest.TestCase):
    def test_signature_matches_independent_protocol_vector(self):
        body = '{"code":"HHK","product_id":"123"}'
        expected = hmac.new(b'test-secret',
                            ('test-secretapp_keyappmethodproduct.detailparam_json' + body +
                             'timestamp2026-10-15 00:00:00v2test-secret').encode(), hashlib.sha256).hexdigest()
        self.assertEqual(signature('app', 'test-secret', 'product.detail',
                                   '2026-10-15 00:00:00', body), expected)

    def test_body_and_signature_use_identical_sorted_utf8(self):
        request = prepare('APP', 'SECRET', 'TOKEN', 'product.detail',
                          {'z': '汉字&<>😀', 'a': {'b': True, 'a': 1}}, '2026-10-15 00:00:00')
        parsed = urlsplit(request.url)
        query = parse_qs(parsed.query)
        self.assertEqual(parsed.hostname, 'openapi-fxg.jinritemai.com')
        self.assertEqual(parsed.path, '/product/detail')
        self.assertEqual(request.body.decode(), '{"a":{"a":1,"b":true},"z":"汉字&<>😀"}')
        self.assertNotIn('param_json', query)
        self.assertEqual(query['sign'][0], signature('APP', 'SECRET', 'product.detail',
                                                   query['timestamp'][0], request.body.decode()))

    def test_preview_and_repr_do_not_disclose_credentials(self):
        request = prepare('PRIVATE-KEY', 'PRIVATE-SECRET', 'PRIVATE-TOKEN', 'product.detail', {})
        self.assertNotIn('PRIVATE', str(request.preview()) + repr(request))
        self.assertFalse(request.preview()['sent'])

    def test_bad_method_credentials_and_nonfinite_json_rejected(self):
        for method in ('../etc/passwd', 'https://evil.example', 'product/detail', ''):
            with self.assertRaises(ValueError):
                prepare('A', 'B', 'C', method, {})
        with self.assertRaises(ValueError):
            prepare('', 'B', 'C', 'product.detail', {})
        with self.assertRaises(ValueError):
            serialize({'x': float('nan')})


if __name__ == '__main__':
    unittest.main()
