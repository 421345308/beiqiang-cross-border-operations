"""Actual create/repair regressions; no credentials, SDK transport or platform I/O."""
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from xml.etree import ElementTree as ET

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('model_gallery_contract',HERE/'schema_publish_contract.py')
contract=importlib.util.module_from_spec(spec);spec.loader.exec_module(contract)
F=HERE/'schema_contract_fixtures'

def parent_payload(field):
    root=ET.Element('itemSchema')
    parent=ET.SubElement(root,'field',id='icbuCatProp',type='complex')
    cv=ET.SubElement(parent,'complex-value');cv.append(deepcopy(field))
    return root

class ModelGalleryTests(unittest.TestCase):
    def setUp(self):
        self.cases=json.loads((F/'model_number_cases.json').read_text(encoding='utf-8'))['cases']
    def test_three_real_bare_model_requests_are_serialized_as_product_attributes(self):
        for case in self.cases:
            schema=ET.fromstring(case['schema'])
            bad=ET.fromstring(case['bad_create_model_field'])
            self.assertIsNone(bad.find('./value').get('inputValue'))
            listing=contract.prepare_scoped_listing(schema,parent_payload(bad),operation='create',
                category_id=case['category_id'],field_ids=['icbuCatProp'],expected_model=case['expected_model'])
            root=ET.fromstring(listing['xml'])
            contract.validate_model_payload(root,listing['model_serialization'])
            value=root.find("./field/complex-value/field/value")
            self.assertEqual(value.get('inputValue'),case['expected_model'])
            self.assertEqual(value.text,'-3') # Exact observed fixture marker, not derived from ID.
            self.assertIsNone(bad.find('./value').get('inputValue')) # Input object remains untouched.
    def test_sku_model_cannot_replace_product_attribute_or_expected_model(self):
        case=self.cases[0];schema=ET.fromstring(case['schema'])
        payload=ET.fromstring('<itemSchema><field id="icbuCatProp" type="complex"><complex-value/></field></itemSchema>')
        with self.assertRaisesRegex(ValueError,'expected_model'):
            contract.prepare_scoped_listing(schema,payload,operation='create',category_id=case['category_id'],field_ids=['icbuCatProp'])
        listing=contract.prepare_scoped_listing(schema,payload,operation='create',category_id=case['category_id'],field_ids=['icbuCatProp'],expected_model=case['expected_model'])
        root=ET.fromstring(listing['xml']);root.remove(root.find('./field'))
        sku=ET.SubElement(root,'field',id='sku');cv=ET.SubElement(sku,'complex-values');f=ET.SubElement(cv,'field',id='skuOuterId');ET.SubElement(f,'value').text=case['sku_outer_id_examples'][0]
        with self.assertRaisesRegex(ValueError,'SKU'):
            contract.validate_model_payload(root,listing['model_serialization'])
        with self.assertRaisesRegex(ValueError,'model update requires expected_model'):
            contract.prepare_scoped_listing(schema,parent_payload(ET.fromstring(case['bad_create_model_field'])),operation='update',
                category_id=case['category_id'],target_product_id='OFFLINE',field_ids=['icbuCatProp'])
    def test_no_model_field_reports_unsupported_without_guessing_p3(self):
        schema=ET.fromstring('<itemSchema><field id="icbuCatProp" type="complex"><fields><field id="p-3" name="Material" type="input"/></fields></field></itemSchema>')
        with self.assertRaisesRegex(contract.UnsupportedProductModel,'unsupported_model_field'):
            contract.serialize_product_model(schema,'BQ-EXPECTED')
    def test_changed_model_field_uses_current_marker_and_byte_rule(self):
        schema=ET.fromstring('<itemSchema><field id="icbuCatProp" type="complex"><fields><field id="p-987" name="Model Number" type="input"><rules><rule name="maxLengthRule" value="6" unit="byte"/></rules></field></fields><complex-value><field id="p-987" name="Model Number" type="input"><value inputValue="old" custom="keep">-71</value></field></complex-value></field></itemSchema>')
        model=contract.serialize_product_model(schema,'AB-12')
        self.assertEqual(model.get('id'),'p-987')
        self.assertEqual(model.find('./value').text,'-71')
        self.assertEqual(model.find('./value').attrib,{'inputValue':'AB-12','custom':'keep'})
        with self.assertRaises(ValueError):contract.serialize_product_model(schema,'中文中文')
        empty=deepcopy(schema);empty.find('./field').remove(empty.find('./field/complex-value'))
        with self.assertRaisesRegex(contract.UnsupportedProductModel,'unsupported_attribute_value_format'):
            contract.serialize_product_model(empty,'AB-12')
    def test_formal_negative_marker_normalization_does_not_hide_actual_model_mismatch(self):
        for case in self.cases:
            if 'formal_model_field' not in case:continue
            request=parent_payload(ET.fromstring(case['corrected_model_field']))
            # Minimal requests lack name; serialize via current metadata before comparing.
            listing=contract.prepare_scoped_listing(ET.fromstring(case['schema']),request,operation='update',
                category_id=case['category_id'],target_product_id='OFFLINE',field_ids=['icbuCatProp'],expected_model=case['expected_model'])
            formal=parent_payload(ET.fromstring(case['formal_model_field']))
            self.assertEqual(contract.verify_content('submitted_needs_readback',listing['expected_fields'],contract.field_snapshot(formal)),'formal_fields_verified')
            formal.find('./field/complex-value/field/value').set('inputValue','WRONG')
            self.assertEqual(contract.verify_content('submitted_needs_readback',listing['expected_fields'],contract.field_snapshot(formal)),'content_mismatch_or_noop')
    def test_source_gallery_values_attributes_and_nesting_survive_cleanup(self):
        galleries=json.loads((F/'gallery_success_shapes.json').read_text(encoding='utf-8'))['cases']
        for case in galleries:
            source=ET.fromstring(case['xml']);clean=contract.values_only(source)
            self.assertEqual(ET.tostring(clean),ET.tostring(source))
            for field in source:
                items=field.findall('./complex-values')
                self.assertGreaterEqual(len(items),4)
                for item in items:
                    role=item.find("./field[@id='gallery']/value")
                    self.assertTrue(role.text)
                    self.assertTrue(role.get('displayName'))
                    self.assertTrue(item.find("./field[@id='images']/complex-values/field[@id='imageURL']/value").text)
        # Source property preservation does not assert a universal displayName rule.
        without=ET.fromstring(galleries[0]['xml'])
        for value in without.findall(".//field[@id='gallery']/value"):
            value.attrib.pop('displayName',None)
        self.assertEqual(ET.tostring(contract.values_only(without)),ET.tostring(without))
    def test_actual_entry_requires_expected_model_and_serializes_before_client_load(self):
        spec=importlib.util.spec_from_file_location('actual_model_publisher',HERE/'publish_hot_rank_hr_a_batch.py')
        publisher=importlib.util.module_from_spec(spec);spec.loader.exec_module(publisher)
        case=self.cases[2]
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory)
            (directory/'schema.xml').write_text(case['schema'],encoding='utf-8')
            (directory/'payload.xml').write_text(ET.tostring(parent_payload(ET.fromstring(case['bad_create_model_field'])),encoding='unicode'),encoding='utf-8')
            data={'operation':'create','facts_reviewed':True,'source_evidence':['OFFLINE_CASE'],
                  'current_schema':'schema.xml','current_schema_sha256':hashlib.sha256((directory/'schema.xml').read_bytes()).hexdigest(),
                  'schema_request_id':'OFFLINE_SCHEMA','schema_acquired_at':datetime.now(timezone.utc).isoformat(),
                  'payload_xml':'payload.xml','category_id':case['category_id'],'field_ids':['icbuCatProp'],'dependency_ids':[]}
            path=directory/'manifest.json';path.write_text(json.dumps(data),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'expected_model'):
                publisher.load_submission_manifest(path,'create',None)
            data['expected_model']=case['expected_model'];path.write_text(json.dumps(data),encoding='utf-8')
            listing=publisher.load_submission_manifest(path,'create',None)
            class NeverNetwork:
                calls=0
                def top_call(self,*args):self.calls+=1;return {'biz_success':True,'product_id':123}
                def api_error(self,*args):return None
            client=NeverNetwork()
            root=ET.fromstring(listing['xml']);root.find('./field/complex-value/field/value').attrib.clear()
            listing['xml']=ET.tostring(root,encoding='unicode');listing['expected_fields']=publisher.field_snapshot(root)
            with self.assertRaisesRegex(ValueError,'model representation'):
                publisher.api_submit(client,{},listing,False)
            self.assertEqual(client.calls,0)

if __name__=='__main__':unittest.main()
