"""Current keyword Schema and real empty/nonempty read excerpts; no platform calls."""
from pathlib import Path
from xml.etree import ElementTree as E
import json,unittest,importlib.util
from urllib.parse import urlencode,parse_qs
import schema_publish_contract as c

class KeywordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.fx=json.loads((Path(__file__).parent/'schema_contract_fixtures/keyword_current_cases.json').read_text(encoding='utf-8'))
    def schema(self):return E.fromstring('<itemSchema>'+self.fx['keyword_schema_xml']+'</itemSchema>')
    def test_current_single_input_384_bytes_and_actual_documented_xml(self):
        s=self.schema();kw=c.serialize_product_keywords(s,'mens suede slip on loafers')
        self.assertEqual(kw.find('./complex-value/field').get('id'),'productKeywords_0')
        self.assertEqual(kw.find('./complex-value/field/value').text,'mens suede slip on loafers')
        c.serialize_product_keywords(s,'a'*384)
        for bad in [['a','b'],'a'*385,'shoe; supplier','shoe, supplier','shoe: supplier','']:
            with self.subTest(bad=str(bad)[:20]),self.assertRaises(ValueError):c.serialize_product_keywords(s,bad)
        s.find("./field/rules/rule[@name='maxInputNumRule']").set('value','2')
        s.find('./field/fields').append(E.fromstring('<field id="productKeywords_7" type="input"><rules><rule name="maxLengthRule" value="9" unit="byte"/></rules></field>'))
        node=c.serialize_product_keywords(s,['a','b']);self.assertEqual([x.get('id') for x in node.findall('./complex-value/field')],['productKeywords_0','productKeywords_7'])

    def test_actual_prepare_guard_rejects_wrong_shape_marker_count_before_transport(self):
        s=self.schema()
        def prepare(text):return c.prepare_scoped_listing(s,E.fromstring('<itemSchema>'+text+'</itemSchema>'),operation='update',category_id=201334413,target_product_id='1601969920294',field_ids=['productKeywords'])
        kw=c.serialize_product_keywords(s,'mens suede slip on loafers');listing=prepare(E.tostring(kw,encoding='unicode'))
        self.assertEqual(listing['keyword_input']['values'],['mens suede slip on loafers'])
        for bad in ['<field id="productKeywords"><value>loafers</value></field>', '<field id="productKeywords"><complex-value><field id="productKeywords_9"><value>loafers</value></field></complex-value></field>', '<field id="productKeywords"><complex-value><field id="productKeywords_0"><value inputValue="loafers">-2</value></field></complex-value></field>']:
            with self.subTest(payload=bad),self.assertRaises(ValueError):prepare(bad)

    def test_real_positive_get_keywords_and_empty_after_schema_success_are_distinct(self):
        positive=self.fx['positive_read'];negative=self.fx['negative_read']
        def get(row):return {'product':{'product_id':row.get('encrypted_id') or row['product_id'],'keywords':row['keywords'],'status':row['status']}}
        result=c.compare_keyword_readback(positive['keywords'],get(positive),self.schema(),expected_product_id=positive['encrypted_id'])
        self.assertEqual(result['status'],'keyword_verified_get');self.assertEqual(result['render_status'],'definitions_only_or_absent')
        result=c.compare_keyword_readback('mens suede slip on loafers',get(negative),self.schema(),expected_product_id=negative['product_id'])
        self.assertEqual(result['status'],'keyword_not_persisted');self.assertEqual(result['get_values'],[''])
        wrong=c.compare_keyword_readback(positive['keywords'],get(positive),expected_product_id='wrong target')
        self.assertEqual(wrong['status'],'unverified_keyword_readback')

    def test_review_pending_missing_read_and_conflicting_actual_render_never_pass(self):
        get={'product':{'product_id':'OFFLINE_BOUND_TARGET','keywords':[''],'status':'modified'}}
        self.assertEqual(c.compare_keyword_readback('loafers',get,expected_product_id='OFFLINE_BOUND_TARGET')['status'],'pending_review')
        get['product']['status']='approved';get['product'].pop('keywords')
        self.assertEqual(c.compare_keyword_readback('loafers',get,expected_product_id='OFFLINE_BOUND_TARGET')['status'],'unverified_keyword_readback')
        get['product']['keywords']=['loafers'];render=E.fromstring('<itemSchema>'+E.tostring(c.serialize_product_keywords(self.schema(),'different'),encoding='unicode')+'</itemSchema>')
        self.assertEqual(c.compare_keyword_readback('loafers',get,render,expected_product_id='OFFLINE_BOUND_TARGET')['status'],'readback_disagrees')

    def test_actual_sdk_encodes_keyword_list_as_json_array_without_business_scope_expansion(self):
        file=Path(__file__).resolve().parents[3]/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py'
        spec=importlib.util.spec_from_file_location('keyword_scalar_sdk',file);sdk=importlib.util.module_from_spec(spec);spec.loader.exec_module(sdk)
        params={'product_id':'OFFLINE_ENCRYPTED_TARGET','product_type':'sourcing','language':'ENGLISH','keywords':['mens suede slip on loafers']}
        encoded=parse_qs(urlencode(sdk.clean_params(params)))
        self.assertEqual(set(encoded),set(params))
        self.assertEqual(json.loads(encoded['keywords'][0]),params['keywords'])
        self.assertEqual(encoded['product_id'],['OFFLINE_ENCRYPTED_TARGET'])

if __name__=='__main__':unittest.main()
