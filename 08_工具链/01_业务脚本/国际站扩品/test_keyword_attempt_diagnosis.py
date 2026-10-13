"""Bound real HR021 receipts and six rendered Schemas; no network or writes."""
from pathlib import Path
import copy, importlib.util, json, unittest, xml.etree.ElementTree as E

BASE = Path(__file__).parent
import schema_publish_contract as c
case = json.loads((BASE/'schema_contract_fixtures/HR021_keyword_diagnosis_case.json').read_text(encoding='utf-8'))
schema = E.fromstring(case['current_keyword_schema_xml'])

class KeywordAttemptDiagnosis(unittest.TestCase):
    def diagnose(self, **overrides):
        args = dict(current_schema=schema, payload=case['keyword_payload'], before_get=case['keyword_before_get'], after_get=case['after_get'], receipt=case['receipt'], expected_product_id='1601943593293')
        args.update(overrides)
        return c.diagnose_keyword_attempt(**args)

    def test_actual_keyword_only_business_acceptance_is_noop(self):
        r=self.diagnose();self.assertEqual(r['status'],'accepted_keyword_noop');self.assertFalse(r['write_capability_verified']);self.assertFalse(r['retry_same_request'])

    def test_actual_image_only_update_detects_collateral_keyword_loss(self):
        r=self.diagnose(payload=case['gallery_payload'],before_get=case['before_get'],after_get=case['gallery_after_get'],receipt=case['gallery_receipt'])
        self.assertEqual(r['status'],'unexpected_keyword_loss');self.assertFalse(r['keyword_field_submitted'])

    def test_pending_review_cannot_be_noop_or_success(self):
        after=copy.deepcopy(case['after_get']);after['product']['status']='modified'
        self.assertEqual(self.diagnose(after_get=after)['status'],'pending_review')

    def test_retired_and_unknown_writes_do_not_recommend_retry(self):
        for receipt,status in [({'error':{'sub_code':'INTERFACE_HAS_BEEN_OFFLINE'}},'retired_interface_rejected'),({'status':'write_outcome_unknown'},'unknown_write_outcome_stop')]:
            r=self.diagnose(receipt=receipt);self.assertEqual(r['status'],status);self.assertFalse(r['retry_same_request'])

    def test_wrong_target_and_missing_property_are_unverified(self):
        after=copy.deepcopy(case['after_get']);after['product']['product_id']='wrong'
        self.assertEqual(self.diagnose(after_get=after)['status'],'unverified_keyword_readback')
        after=copy.deepcopy(case['after_get']);after['product'].pop('keywords')
        self.assertEqual(self.diagnose(after_get=after)['status'],'unverified_keyword_readback')

    def test_existing_correct_value_does_not_prove_this_write(self):
        after=copy.deepcopy(case['after_get']);after['product']['keywords']=case['before_get']['product']['keywords']
        r=self.diagnose(before_get=case['before_get'],after_get=after)
        self.assertEqual(r['status'],'keyword_value_verified_write_effect_unproven');self.assertFalse(r['write_capability_verified'])

    def test_formal_change_and_positive_receipt_verify_only_bound_attempt(self):
        after=copy.deepcopy(case['after_get']);after['product']['keywords']=case['before_get']['product']['keywords']
        self.assertTrue(self.diagnose(after_get=after)['write_capability_verified'])
        self.assertFalse(self.diagnose(after_get=after,receipt={})['write_capability_verified'])
        self.assertEqual(self.diagnose(after_get=after,receipt={'response':{'biz_success':False}})['status'],'business_rejected')

    def test_six_actual_current_schemas_accept_single_direct_text_and_no_invented_marker(self):
        for name in ['M001','2627BSK','805','H219','F2888','936']:
            with self.subTest(product=name):
                current=E.fromstring(case['six_current_keyword_schemas'][name])
                contract=c.keyword_input_contract(current)
                self.assertEqual((contract['minimum'],contract['maximum']),(1,1))
                node=c.serialize_product_keywords(current,'wholesale footwear')
                payload=E.Element('itemSchema');payload.append(node)
                c.validate_keyword_payload(current,payload)
                node.find('./complex-value/field/value').set('inputValue','invented')
                with self.assertRaises(ValueError):c.validate_keyword_payload(current,payload)

if __name__=='__main__':unittest.main()
