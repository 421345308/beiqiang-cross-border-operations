import json
import subprocess
import unittest
from unittest.mock import patch
from company_lookup import _lookup, lookup_company


class Transport:
    def __init__(self, body='', status=200):
        self.body, self.status = body, status
    def get(self, url, **kwargs):
        return {'url': url, 'status': self.status, 'body': self.body}


class LookupTests(unittest.TestCase):
    def setUp(self):
        self.obj = {'id': 'prospect:test', 'kind': 'prospect', 'title': 'Example Footwear',
                    'content': json.dumps({'company_url': 'https://www.importyeti.com/company/example-footwear'})}

    def test_third_party_mention_is_candidate_never_identity(self):
        result = _lookup(self.obj, Transport(r'{\"website\":\"example.com\"}'))
        self.assertEqual(result['status'], 'candidates')
        candidate = result['candidates'][0]
        self.assertEqual(candidate['website'], 'https://example.com/')
        self.assertEqual(candidate['identity_status'], 'unverified')
        self.assertTrue(candidate['requires_confirmation'])
        self.assertNotIn('website', self.obj)

    def test_unavailable_and_challenge_pages_preserve_failure(self):
        self.assertEqual(_lookup(self.obj, Transport(status=403))['status'], 'failed')
        result = _lookup(self.obj, Transport('<html>Enable JavaScript</html>'))
        self.assertEqual(result['status'], 'not_found')
        self.assertEqual(result['candidates'], [])
        self.assertTrue(result['attempts'])
        self.assertIn('Example', result['manual_search_url'])

    def test_reject_platform_local_and_source_spoof(self):
        result = _lookup(self.obj, Transport('{"website":"https://127.0.0.1/"}'))
        self.assertEqual(result['candidates'], [])
        result = _lookup(self.obj, Transport('{"website":"https://google.com/"}'))
        self.assertEqual(result['candidates'], [])
        obj = dict(self.obj, content=json.dumps({'company_url': 'https://www.importyeti.com.evil.test/company/example'}))
        self.assertEqual(_lookup(obj, Transport())['attempts'][0]['status'], 'missing_source')

    def test_search_mentions_are_sourced_and_require_selection(self):
        search = lambda company: {'status': 'read', 'rows': [
            {'url': 'https://www.linkedin.com/company/example', 'title': 'Example Footwear',
             'description': 'Example Footwear. Website: http://www.example.com. Industry: shoes'},
            {'url': 'https://www.indeed.com/cmp/example-footwear', 'title': 'Example Footwear', 'description': 'Example Footwear reviews'},
            {'url': 'https://www.zoominfo.com/c/example-footwear/123', 'title': 'Example Footwear',
             'description': 'Example Footwear official website is www.example.com.'},
            {'url': 'https://wrong.example/', 'title': 'Unrelated Company', 'description': 'Website: wrong.example'}]}
        result = _lookup(self.obj, Transport(), search)
        self.assertEqual(result['status'], 'candidates')
        self.assertEqual(len(result['candidates']), 1)
        self.assertEqual(result['candidates'][0]['website'], 'http://www.example.com/')
        self.assertEqual(result['candidates'][0]['discovery_method'], 'public_search')
        self.assertEqual(len(result['candidates'][0]['supporting_sources']), 1)
        self.assertTrue(result['selection_required'])

    def test_timeout_kills_worker_and_returns_manual_route(self):
        class Process:
            calls = 0
            killed = False
            def communicate(self, *args, **kwargs):
                self.calls += 1
                if self.calls == 1: raise subprocess.TimeoutExpired('worker', 1)
                return '', ''
            def kill(self): self.killed = True
        process = Process()
        with patch('company_lookup.subprocess.Popen', return_value=process):
            result = lookup_company(self.obj, 1)
        self.assertTrue(process.killed)
        self.assertEqual(result['status'], 'timeout')
        self.assertEqual(result['candidates'], [])
        self.assertTrue(result['manual_search_url'])


if __name__ == '__main__': unittest.main()
