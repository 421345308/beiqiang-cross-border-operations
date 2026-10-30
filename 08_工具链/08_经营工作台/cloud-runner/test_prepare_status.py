import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('prepare_status', Path(__file__).with_name('prepare-status.py'))
status = importlib.util.module_from_spec(spec)
spec.loader.exec_module(status)


class StatusTests(unittest.TestCase):
    def test_times_require_timezone_and_normalize_utc(self):
        self.assertEqual(status.iso('2026-10-30T18:00:00+08:00'), '2026-10-30T10:00:00.000Z')
        self.assertEqual(status.iso('2026-10-30T10:00:00.123456Z'), '2026-10-30T10:00:00.123Z')
        self.assertIsNone(status.iso('2026-10-30'))
        self.assertIsNone(status.iso('2026-10-30T18:00:00'))

    def test_usage_whitelist_and_zero_credit_not_zero_quota(self):
        usage = {'ordinaryUsageAllowed': True, 'accountId': 'PRIVATE',
                 'rateLimits': {'primary': {'usedPercent': 40, 'windowDurationMins': 10080, 'resetsAt': 1793774168},
                                'credits': {'balance': '0', 'hasCredits': False}},
                 'rateLimitResetCredits': {'availableCount': 1, 'resetCreditId': 'PRIVATE'}}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'usage.json'
            path.write_text(json.dumps({'observed_at': '2026-10-30T18:00:00+08:00', 'usage': usage}))
            result = status.codex_status(path)
        self.assertTrue(result['available'])
        self.assertEqual(result['windows'][0]['used_percent'], 40)
        self.assertEqual(result['reset_credits'], 1)
        self.assertTrue(result['windows'][0]['resets_at'].endswith('Z'))
        self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertNotIn('balance', json.dumps(result))

    def test_unknown_is_null_and_no_fake_metrics(self):
        result = status.codex_status()
        self.assertIsNone(result['available'])
        self.assertIsNone(result['reset_credits'])
        self.assertEqual(result['windows'], [])
        with tempfile.TemporaryDirectory() as folder:
            def offline():
                raise OSError('offline')
            snapshot = status.prepare(Path(folder), fetcher=offline)
        self.assertEqual(set(snapshot), {'schema_version', 'observed_at', 'channels', 'codex'})
        self.assertEqual(snapshot['schema_version'], 1)
        for channel in snapshot['channels']:
            self.assertEqual(set(channel), {'id', 'title', 'observed_at', 'period', 'source', 'summary', 'metrics', 'limitations'})
            self.assertIsNone(channel['observed_at'])
            self.assertEqual(channel['metrics'], [])

    def test_real_archive_window_not_collection_date(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fixtures = {
                status.ALI: {'summary': {'observed_at': '2026-10-21T14:50:40+00:00', 'period': '2026-10-11~2026-10-17', 'totals': {'search_clicks': 866}}},
                status.GSC: {'observedAt': '2026-10-09', 'performance': {'visibleChartStart': '2026-08-26', 'visibleChartEnd': '2026-10-06', 'clicks': 1}},
            }
            for relative, value in fixtures.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value), encoding='utf-8')
            (root / status.DIAG).write_text('历史后台数据复核', encoding='utf-8')
            snapshot = status.prepare(root, fetcher=lambda: {'releaseId': 'test', 'releasedAt': '2026-10-30T10:00:00Z'})
        ali, website = snapshot['channels']
        self.assertEqual(ali['period'], '2026-10-11~2026-10-17')
        self.assertTrue(ali['observed_at'].startswith('2026-10-21'))
        self.assertIn('2026-10-06', website['period'])
        self.assertTrue(all(isinstance(m['value'], str) for c in snapshot['channels'] for m in c['metrics']))

    def test_bucket_map_wins_and_windows_are_never_merged(self):
        window = {'usedPercent': 20, 'windowDurationMins': 300, 'resetsAt': None}
        usage = {'rateLimits': {'primary': {**window, 'usedPercent': 99}},
                 'rateLimitsByLimitId': {f'codex_{i}': {'primary': window, 'secondary': window} for i in range(5)}}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'usage.json'
            path.write_text(json.dumps({'observed_at': '2026-10-30T10:00:00Z', 'usage': usage}))
            result = status.codex_status(path)
        self.assertEqual(len(result['windows']), 8)
        self.assertEqual(result['windows'][0]['label'], 'codex_0 · 主额度窗口')
        self.assertTrue(all(w['used_percent'] == 20 for w in result['windows']))
        self.assertTrue(any('2个窗口未展示' in x for x in result['limitations']))


if __name__ == '__main__':
    unittest.main()
