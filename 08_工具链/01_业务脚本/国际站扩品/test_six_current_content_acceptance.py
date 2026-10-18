"""Actual observed content snapshots. Pure offline, no platform client."""
from pathlib import Path
from copy import deepcopy
import json, unittest
from xml.etree import ElementTree as E
import schema_publish_contract as contract

class SixCurrentContentAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases=json.loads((Path(__file__).parent/'schema_contract_fixtures/current_content_six_20261003.json').read_text(encoding='utf8'))['cases']
    def evaluate(self, case, **changes):
        row=case['registry_row']
        args=dict(product_id=row['product_id'],category_id=row['category_id'],editor_observation_id=row['editor_observation_id'],observed_at=case['observed_at'])
        args.update(changes)
        return contract.evaluate_versioned_content(E.fromstring(case['schema_xml']),case['formal_get'],case['public_text'],**args)
    def test_registered_actual_current_chains_pass_without_keyword_or_retirement_claims(self):
        self.assertGreaterEqual(len(self.cases),4)
        for name, case in self.cases.items():
            with self.subTest(product=name):
                result=self.evaluate(case)
                self.assertEqual(result['status'],'product_summary_verified')
                self.assertEqual(result['summary_characters'],len(case['public_text']))
                self.assertFalse(result['keyword_write_verified'])
                self.assertFalse(result['replacement_closeout_verified'])
    def test_new_observations_still_require_exact_product_date_and_public_body(self):
        for name,case in self.cases.items():
            for change in [{'observed_at':'2026-10-04T12:00:00Z'}, {'product_id':'unverified-product'}, {'editor_observation_id':'unobserved-editor'}]:
                with self.subTest(product=name,change=change):
                    self.assertEqual(self.evaluate(case,**change)['status'],'content_version_unverified')
            missing=deepcopy(case);missing['public_text']='Public evidence not captured'
            self.assertEqual(self.evaluate(missing)['status'],'selling_point_content_pending')

if __name__=='__main__':
    unittest.main()
