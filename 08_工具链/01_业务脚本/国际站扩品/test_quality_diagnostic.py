import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import quality_diagnostic as diagnostic


class QualityDiagnosticTests(unittest.TestCase):
    def test_reason_uses_english_if_no_chinese(self):
        result = diagnostic.summarize_score({'id': 9}, {'result': {'final_score': '4.5', 'problem_map': {'extendProblemMap': {'imageText': True}, 'errorReasonMap': {'en': 'Actual platform detail'}}}})
        self.assertEqual(result['platform_reason'], 'Actual platform detail')
        self.assertEqual(result['problems'], ['imageText'])

    def test_sample_is_not_complete_and_retains_issue_identity(self):
        products = [{'id': 11, 'product_id': 'one', 'red_model': 'A'},
                    {'id': 12, 'product_id': 'two', 'red_model': 'B'}]
        snapshot = {'products': products, 'total_item': 2, 'observed_at_utc': '2026-11-04T00:00:00Z'}
        response = {'result': {'final_score': '4.70', 'problem_map': json.dumps({'extendProblemMap': {'price': True, 'image_num': False}, 'errorReasonMap': {'zh': '平台返回的具体原因', 'en': 'platform reason'}})}, 'request_id': 'req'}
        with tempfile.TemporaryDirectory() as folder, patch.object(diagnostic, 'fetch_catalog', return_value=snapshot), patch.object(diagnostic, 'read_only_call', return_value=response):
            result = diagnostic.diagnose(None, None, folder, max_items=1)
            self.assertFalse(result['complete'])
            self.assertEqual(result['below_5'][0]['id'], '11')
            self.assertEqual(result['below_5'][0]['problems'], ['price'])
            self.assertEqual(result['below_5'][0]['platform_reason'], '平台返回的具体原因')
            self.assertEqual(json.loads((Path(folder) / 'quality.json').read_text(encoding='utf8'))['scored'], 1)

    def test_missing_score_or_error_cannot_pass_complete(self):
        products = [{'id': 11, 'product_id': 'one'}, {'id': 12, 'product_id': 'two'}]
        snapshot = {'products': products, 'total_item': 2, 'observed_at_utc': '2026-11-04T00:00:00Z'}
        with tempfile.TemporaryDirectory() as folder, patch.object(diagnostic, 'fetch_catalog', return_value=snapshot), patch.object(diagnostic, 'read_only_call', side_effect=[{'result': {}}, RuntimeError('failure')]):
            result = diagnostic.diagnose(None, None, folder)
            self.assertFalse(result['complete'])
            self.assertEqual(result['scored'], 0)
            self.assertIn(result['errors'][0]['id'], {'11', '12'})

    def test_resume_uses_existing_catalog_and_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'catalog').mkdir()
            (root / 'scores').mkdir()
            snapshot = {'complete': True, 'products': [{'id': 11, 'product_id': 'one'}], 'total_item': 1, 'observed_at_utc': '2026-11-04T00:00:00Z'}
            (root / 'catalog/catalog.json').write_text(json.dumps(snapshot), encoding='utf8')
            (root / 'scores/11.json').write_text(json.dumps({'result': {'final_score': '5.00'}}), encoding='utf8')
            with patch.object(diagnostic, 'fetch_catalog') as catalog, patch.object(diagnostic, 'read_only_call') as call:
                result = diagnostic.diagnose(None, None, root, resume=True)
            catalog.assert_not_called()
            call.assert_not_called()
            self.assertTrue(result['complete'])
            self.assertEqual(result['scored'], 1)
            self.assertIsNone(result['items'][0]['platform_reason'])

    def test_rebuild_only_preserves_errors_without_platform_calls(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / 'catalog').mkdir()
            (root / 'catalog/catalog.json').write_text(json.dumps({'complete': True, 'products': [{'id': 12, 'product_id': 'two'}], 'total_item': 1, 'observed_at_utc': '2026-11-04T00:00:00Z'}), encoding='utf8')
            (root / 'quality.json').write_text(json.dumps({'errors': [{'id': '12', 'type': 'ReadBusinessError', 'evidence': {'code': '15'}}]}), encoding='utf8')
            with patch.object(diagnostic, 'read_only_call') as call:
                result = diagnostic.diagnose(None, None, root, resume=True, rebuild_only=True)
            call.assert_not_called()
            self.assertFalse(result['complete'])
            self.assertEqual(result['errors'][0]['evidence']['code'], '15')


if __name__ == '__main__':
    unittest.main()
