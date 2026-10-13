"""Actual approved HR021 receipts: a 5.0 score does not verify preservation."""
from pathlib import Path
import json, sys, unittest

ROOT = Path(r'C:\Users\spq\Desktop\贝强')
CODE = ROOT / '08_工具链/01_业务脚本/国际站扩品'
sys.path.insert(0, str(CODE))
from schema_publish_contract import compare_keyword_readback

class HR021Preservation(unittest.TestCase):
    def test_three_approved_actual_readbacks_detect_loss(self):
        fixture = json.loads((CODE / 'schema_contract_fixtures/HR021_keyword_preservation_failure.json').read_text(encoding='utf-8'))
        self.assertEqual(fixture['scope']['category_id'], '201152005')
        for row in fixture['evidence']:
            with self.subTest(label=row['label']):
                result = compare_keyword_readback(row['expected'], row['product_get'],
                    expected_product_id=row['product_get']['product']['product_id'])
                self.assertEqual(result['status'], 'keyword_not_persisted')
                self.assertEqual(row['sku_count'], 12)
                self.assertTrue(all(row['unrelated_fields_unchanged'].values()))

    def test_actual_five_score_does_not_override_keyword_failure(self):
        fixture = json.loads((CODE / 'schema_contract_fixtures/HR021_keyword_preservation_failure.json').read_text(encoding='utf-8'))
        row = next(r for r in fixture['evidence'] if r['label'] == 'A')
        self.assertEqual(row['actual_score'], 5.0)
        result = compare_keyword_readback(row['expected'], row['product_get'],
            expected_product_id=row['product_get']['product']['product_id'])
        self.assertNotEqual(result['status'], 'keyword_verified_get')

if __name__ == '__main__':
    unittest.main()
