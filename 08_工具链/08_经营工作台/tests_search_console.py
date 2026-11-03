import tempfile
import unittest
import time
import io
import json
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

from search_console import SearchConsole, SCOPE, API, TOKEN_URL, _request, SearchConsoleAPIError

CONFIG = {'installed': {'client_id': 'test.apps.googleusercontent.com', 'client_secret': 'secret'}}
SITE = 'sc-domain:beiqiang.online'


class SearchConsoleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.saved = None
        self.calls = []
        self.fail = False
        def request(url, **kwargs):
            self.calls.append((url, kwargs))
            if self.fail:
                raise ValueError('Google 搜索授权已失效，请重新授权')
            if url == TOKEN_URL:
                return {'access_token': 'access', 'refresh_token': 'refresh', 'scope': SCOPE}
            if url == API:
                return {'siteEntry': [{'siteUrl': SITE, 'permissionLevel': 'siteOwner'}]}
            return {'rows': [{'keys': kwargs['body']['dimensions'], 'clicks': 2, 'impressions': 10, 'ctr': .2, 'position': 3}]}
        def save(account, value):
            self.saved = value
        self.service = SearchConsole(self.tmp.name, request=request, reader=lambda _: self.saved, saver=save)

    def connect(self):
        url = self.service.start(CONFIG, 'http://127.0.0.1:8766/api/desk/search/oauth/callback')
        args = parse_qs(urlsplit(url).query)
        self.assertEqual(args['scope'], [SCOPE])
        self.assertIn('code_challenge', args)
        self.service.finish(args['state'][0], 'code')
        self.service.select_site(SITE)

    def test_snapshot_is_offline_and_not_connected(self):
        self.assertEqual(self.service.snapshot()['state'], 'not_connected')
        self.assertFalse(self.calls)

    def test_separate_consent_and_real_api_dimensions(self):
        self.connect()
        result = self.service.refresh('2026-10-01', '2026-10-28')
        self.assertEqual(result['state'], 'ready')
        self.assertEqual(set(result['tables']), {'totals', 'dates', 'queries', 'pages', 'countries'})
        calls = [c for c in self.calls if 'body' in c[1]]
        self.assertEqual(len(calls), 5)
        self.assertIn('sc-domain%3Abeiqiang.online', calls[0][0])
        self.assertEqual(calls[0][1]['body']['dataState'], 'final')
        text = self.service.path.read_text(encoding='utf-8')
        self.assertNotIn('secret', text)
        self.assertNotIn('refresh_token', text)
        count = len(self.calls)
        self.service.snapshot()
        self.assertEqual(count, len(self.calls))

    def test_state_and_missing_scope_rejected(self):
        self.service.start(CONFIG, 'http://127.0.0.1:8766/callback')
        with self.assertRaises(ValueError):
            self.service.finish('wrong', 'code')
        self.assertIsNone(self.saved)
        self.service.oauth.request = lambda *args, **kwargs: {'access_token': 'a', 'refresh_token': 'r', 'scope': 'gmail.readonly'}
        with self.assertRaises(ValueError):
            self.service.finish(self.service.oauth.pending['state'], 'code')
        self.assertIsNone(self.saved)

    def test_consent_is_saved_before_any_site_api_request(self):
        url = self.service.start(CONFIG, 'http://127.0.0.1:8766/callback')
        state = parse_qs(urlsplit(url).query)['state'][0]
        self.service.finish(state, 'code')
        self.assertTrue(self.saved['refresh_token'])
        self.assertEqual(self.calls[-1][0], TOKEN_URL)
        self.fail = True
        with self.assertRaises(ValueError):
            self.service.sites()
        self.assertTrue(self.saved['refresh_token'])
        self.assertEqual(self.service.snapshot()['state'], 'select_site')

    def test_http_reasons_distinguish_disabled_api_from_scope_or_site(self):
        cases = [('SERVICE_DISABLED', API, 'api_disabled'),
                 ('accessNotConfigured', API, 'api_disabled'),
                 ('ACCESS_TOKEN_SCOPE_INSUFFICIENT', API, 'insufficient_scope'),
                 ('forbidden', API + '/site/searchAnalytics/query', 'site_permission_denied'),
                 ('forbidden', API, 'request_rejected')]
        for reason, url, expected in cases:
            with self.subTest(reason=reason, url=url):
                raw = {'error': {'message': 'secret-should-not-leak', 'details': [{'reason': reason}]}}
                error = HTTPError(url, 403, 'Forbidden', {}, io.BytesIO(json.dumps(raw).encode()))
                with patch('search_console.urlopen', side_effect=error):
                    with self.assertRaises(SearchConsoleAPIError) as caught:
                        _request(url, token='private-access-token')
                self.assertEqual(caught.exception.reason, expected)
                self.assertNotIn('secret-should-not-leak', str(caught.exception))
                self.assertNotIn('private-access-token', str(caught.exception))

    def test_error_keeps_dated_cache_but_marks_unavailable(self):
        self.connect()
        self.service.refresh('2026-10-01', '2026-10-28')
        self.fail = True
        result = self.service.refresh('2026-10-01', '2026-10-28')
        self.assertEqual(result['state'], 'error')
        self.assertFalse(result['available'])
        self.assertIn('last_success_at', result)
        self.assertIn('tables', result)

    def test_site_and_dates_are_validated(self):
        self.connect()
        with self.assertRaises(ValueError):
            self.service.select_site('https://unowned.example/')
        with self.assertRaises(ValueError):
            self.service.refresh('2026-10-28', '2026-10-01')
        self.assertIn('code_challenge', self.service.start(None, 'http://127.0.0.1:8766/callback'))

    def test_selected_site_refreshes_in_background(self):
        self.connect()
        self.service.start_auto()
        for _ in range(100):
            if self.service.snapshot()['state']=='ready':break
            time.sleep(.01)
        self.service.stop()
        self.service._thread.join(1)
        self.assertEqual(self.service.snapshot()['state'],'ready')
        self.assertEqual(len([c for c in self.calls if 'body' in c[1]]),5)


if __name__ == '__main__':
    unittest.main()
