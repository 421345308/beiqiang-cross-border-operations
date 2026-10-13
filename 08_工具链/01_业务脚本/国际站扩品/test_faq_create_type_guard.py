"""Actual formal rejection: update fragments must not pass new-product preflight."""
from pathlib import Path
from copy import deepcopy
import json, unittest
from xml.etree import ElementTree as E
import schema_publish_contract as c
class FAQCreateTypeGuard(unittest.TestCase):
    def test_actual_type_free_725_and_partial_fix_are_rejected_offline(self):
        fx=json.loads((Path(__file__).parent/'schema_contract_fixtures/725_faq_type_rejection_20261004.json').read_text(encoding='utf8'))
        self.assertFalse(fx['business_response']['biz_success'])
        self.assertIn('31002',fx['business_response']['message'])
        definition=E.fromstring(fx['current_faq_definition_xml']);payload=E.fromstring(fx['actual_rejected_faq_xml'])
        with self.assertRaisesRegex(ValueError,'companyFaqDesc'):
            c.validate_current_faq(definition,payload,require_types=True)
        payload.set('type',definition.get('type'))
        with self.assertRaisesRegex(ValueError,'question'):
            c.validate_current_faq(definition,payload,require_types=True)
        defs={f.get('id'):f for f in definition.findall('./fields/field')}
        for field in payload.findall('./complex-values/field'):
            field.set('type',defs[field.get('id')].get('type'))
        c.validate_current_faq(definition,payload,require_types=True)
        # Existing incremental omission remains separate; no global assertion.
        c.validate_current_faq(definition,E.fromstring(fx['actual_rejected_faq_xml']))
if __name__=='__main__':unittest.main()
