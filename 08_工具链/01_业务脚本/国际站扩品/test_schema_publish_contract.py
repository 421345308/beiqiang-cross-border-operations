"""Network-free regressions using whitelisted historical receipt/XML fixtures."""
import json
from pathlib import Path
import unittest
import importlib.util
from xml.etree import ElementTree as ET
from schema_publish_contract import capability, classify_result, values_only, verify_content, faq_constraints

FIXTURES = Path(__file__).with_name("schema_contract_fixtures")

class ContractTests(unittest.TestCase):
    def test_existing_publisher_routes_and_classifies_without_api(self):
        spec = importlib.util.spec_from_file_location('offline_publisher', Path(__file__).with_name('publish_hot_rank_hr_a_batch.py'))
        publisher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(publisher)
        class FakeClient:
            def top_call(self, config, method, params):
                return {'biz_success': True, 'product_id': 123}
            def api_error(self, response):
                return None
        client = FakeClient()
        current = ET.fromstring('<itemSchema><field id="productTitle"><value>old</value></field><field id="icbuCatProp" type="complex"><fields><field id="p-3" name="Model Number" type="input"/></fields></field></itemSchema>')
        patch = ET.fromstring('<itemSchema><field id="productTitle"><value>new</value></field><field id="icbuCatProp" type="complex"><complex-value/></field></itemSchema>')
        for draft, target, op, method in ((True,None,'createDraft','add.draft'),(False,None,'create','add'),(False,'123','update','update')):
            listing = publisher.prepare_scoped_listing(current, patch, operation=op, category_id=201334413, target_product_id=target, field_ids=['productTitle','icbuCatProp'],expected_model='OFFLINE_MODEL')
            result = publisher.api_submit(client, None, listing, draft, target)
            self.assertEqual(result['operation'], op)
            self.assertTrue(result['method'].endswith(method))
            self.assertIn(result['status'], ('draft_created_needs_readback', 'submitted_needs_readback'))
        client.top_call = lambda *args, **kwargs: {'success': True, 'data': ''}
        listing = publisher.prepare_scoped_listing(current, patch, operation='create', category_id=201334413, field_ids=['productTitle','icbuCatProp'],expected_model='OFFLINE_MODEL')
        self.assertEqual(publisher.api_submit(client,None,listing,False)['status'], 'unverified_business_result')

    def test_real_formal_receipts(self):
        receipts = json.loads((FIXTURES / "formal_receipts.json").read_text(encoding="utf-8"))
        self.assertEqual(len(receipts), 23)
        for row in receipts:
            self.assertEqual(classify_result("create", row["response"]), "submitted_needs_readback")

    def test_scope_operation_and_type_do_not_leak(self):
        self.assertEqual(capability("create", "4", "201334413")["status"], "historically_verified")
        for op, kind, cat in (("createDraft", "4", "201334413"), ("update", "4", "201334413"), ("create", "2", "201334413"), ("create", "5", "201334413"), ("create", "4", "other")):
            self.assertEqual(capability(op, kind, cat)["status"], "unverified")

    def test_draft_failure_does_not_block_formal_evidence(self):
        self.assertEqual(classify_result("createDraft", {"biz_success": False}), "business_rejected")
        self.assertEqual(capability("create", "4", "201334413")["status"], "historically_verified")

    def test_outer_success_and_description_error(self):
        self.assertEqual(classify_result("create", {"success": True, "result": {"success": False, "sub_code": "DESCRIPTION_REQUIRED"}}), "business_rejected")
        self.assertEqual(classify_result("create", {"success": True, "data": ""}), "unverified_business_result")
        self.assertEqual(classify_result("create", {"biz_success": True}), "unverified_business_result")

    def test_successful_receipt_cannot_verify_content(self):
        status = classify_result('update', {'biz_success': True})
        self.assertEqual(verify_content(status, {'detailImage': ['new']}, None), 'pending_readback')
        self.assertEqual(verify_content(status, {'detailImage': ['new']}, {'detailImage': ['old']}), 'content_mismatch_or_noop')
        self.assertEqual(verify_content(status, {'productTitle': 'new'}, {'productTitle': 'new'}), 'formal_fields_verified')
        self.assertEqual(capability('update','4','201334413',field='companyFaqDesc')['status'], 'unverified')
        self.assertEqual(capability('update','4','201334413',field='detailImage')['status'], 'observed_noop')

    def test_faq_current_rules_have_no_invented_units(self):
        schema = ET.fromstring('<itemSchema><field id="companyFaqDesc"><rules><rule name="maxValueNumRule" value="8"/></rules><fields><field id="question"><rules><rule name="maxInputNumRule" value="150"/></rules></field><field id="answers"><rules><rule name="maxInputNumRule" value="500"/></rules></field></fields></field></itemSchema>')
        rules = faq_constraints(schema)
        self.assertEqual(rules['rules'][0]['value'], '8')
        self.assertEqual(rules['unit_interpretation'], 'unverified_unless_current_schema_defines_unit')

    def test_nested_galleries_and_dynamic_faq(self):
        root = ET.parse(FIXTURES / "type4_detail.xml").getroot()
        result = values_only(root)
        for name in ("detailImage", "companyImage"):
            self.assertIsNotNone(result.find(f"./field[@id='{name}']/complex-values/field[@id='images']/complex-values/field[@id='imageURL']/value"))
        faq = root.find("./field[@id='companyFaqDesc']")
        original = len(faq.findall("./complex-values"))
        self.assertGreater(original, 4)
        for count in (0, 1, original):
            copy = ET.fromstring(ET.tostring(root))
            f = copy.find("./field[@id='companyFaqDesc']")
            for child in f.findall("./complex-values")[count:]:
                f.remove(child)
            self.assertEqual(len(values_only(copy).findall("./field[@id='companyFaqDesc']/complex-values")), count)

    def test_metadata_sku_ids_and_update_dependencies(self):
        root = ET.fromstring('<itemSchema><field id="sku"><complex-values><field id="skuId"><value>old</value></field><field id="props"><rules/><value>kept</value></field></complex-values><options/><fields/><label-group/></field><field id="companyFaqDesc"><complex-values><field id="question"><value>q</value></field></complex-values></field></itemSchema>')
        result = values_only(root)
        self.assertIsNone(result.find(".//field[@id='skuId']"))
        self.assertFalse(any(n.tag in ('rules','options','fields','label-group') for n in result.iter()))
        self.assertEqual(result.find(".//field[@id='props']/value").text, "kept")
        with self.assertRaises(ValueError):
            values_only(root, operation="update")
        update = values_only(root, operation="update", field_ids={"sku"})
        self.assertIsNotNone(update.find(".//field[@id='skuId']"))
        self.assertIsNone(update.find("./field[@id='companyFaqDesc']"))

if __name__ == '__main__':
    unittest.main()
