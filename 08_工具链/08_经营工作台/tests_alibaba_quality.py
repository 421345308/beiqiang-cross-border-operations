import json
import tempfile
import unittest
from pathlib import Path

from alibaba_quality import latest_quality


class AlibabaQualityTests(unittest.TestCase):
    def test_empty_and_partial_snapshot(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertFalse(latest_quality(root)['available'])
            folder = Path(root) / '08_工具链/08_经营工作台/.local/alibaba/quality-test'
            folder.mkdir(parents=True)
            (folder / 'catalog').mkdir()
            (folder / 'catalog/catalog.json').write_text(json.dumps({'complete': True, 'total_item': 2, 'products': [{'status': 'approved', 'display': 'Y'}, {'status': 'tbd', 'display': 'N'}]}), encoding='utf8')
            (folder / 'quality.json').write_text(json.dumps({
                'observed_at_utc': '2026-11-04T05:00:00+00:00', 'catalog_total': 20,
                'selected': 2, 'scored': 1, 'complete': False, 'errors': [{'id': '2'}],
                'items': [{'id': '1', 'score': 4.5, 'problems': ['price'], 'platform_reason': '平台返回的具体原因', 'observed_at_utc': '2026-11-04T04:00:00+00:00'}, {'id': '2', 'score': None, 'observed_at_utc': '2026-11-04T04:10:00+00:00'}]
            }), encoding='utf8')
            result = latest_quality(root)
            self.assertTrue(result['available'])
            self.assertFalse(result['complete'])
            self.assertEqual(result['below_5_count'], 1)
            self.assertEqual(result['error_count'], 1)
            self.assertEqual(result['below_5'][0]['problems'], ['price'])
            self.assertEqual(result['below_5'][0]['platform_reason'], '平台返回的具体原因')
            self.assertEqual(result['score_observed_from'], '2026-11-04T04:00:00+00:00')
            self.assertEqual(result['score_observed_to'], '2026-11-04T04:10:00+00:00')
            self.assertEqual(result['catalog_state_counts'], {'approved/Y': 1, 'tbd/N': 1})


if __name__ == '__main__':
    unittest.main()
