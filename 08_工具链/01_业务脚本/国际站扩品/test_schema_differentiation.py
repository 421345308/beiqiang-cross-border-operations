"""Offline preflight: real 266/262/old266, existing families, unknown evidence."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
import contextlib, hashlib, importlib.util, io, json, sys, tempfile, unittest
from unittest.mock import patch
import schema_publish_contract as c

HERE=Path(__file__).resolve().parent

class DifferentiationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=json.loads((HERE/'schema_contract_fixtures/266_262_differentiation.json').read_text(encoding='utf-8'))
        cls.records={r['product_id']:r for r in cls.fixture['records']}
        spec=importlib.util.spec_from_file_location('differentiation_publisher',HERE/'publish_hot_rank_hr_a_batch.py')
        cls.pub=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.pub)

    def record(self,style='266',old=False):
        pid='1601969526580' if old else ('1601969707634' if style=='266' else '1601969810495')
        return deepcopy(self.records[pid])

    def prepared(self,candidate,catalog):
        schema=ET.fromstring('<itemSchema><field id="icbuCatProp" type="complex"><fields><field id="p-3" name="Model Number" type="input"/></fields></field><field id="productTitle"/><field id="scImages"/></itemSchema>')
        payload=ET.fromstring('<itemSchema><field id="icbuCatProp" type="complex"/><field id="productTitle"><value/></field><field id="scImages" type="complex"><complex-value><field id="scImages_0" type="input"><value/></field></complex-value></field></itemSchema>')
        payload.find("./field[@id='productTitle']/value").text=candidate['title']
        payload.find("./field[@id='scImages']/complex-value/field/value").text=candidate['hero_url']
        return c.prepare_scoped_listing(schema,payload,operation='create',category_id=32211,
            field_ids=['icbuCatProp','productTitle','scImages'],expected_model=candidate['model_number'],
            differentiation_context={'candidate':candidate,'catalog':catalog})

    def test_real_266_262_shared_supplier_are_distinct_actual_styles(self):
        a,b=self.record(),self.record('262')
        self.assertEqual(a['source']['reference'],b['source']['reference'])
        for candidate,existing in [(a,b),(b,a)]:
            result=c.check_listing_differentiation(candidate,[existing])
            self.assertEqual(result['status'],'PASS')
            self.assertEqual(result['comparisons'][0]['status'],'distinct_real_style')
            self.assertIn('profile',result['comparisons'][0]['critical_differences'])
        self.assertGreater(self.fixture['full_catalog_record_count'],350)

    def test_real_new266_old266_reports_actual_id_and_conflicting_fields(self):
        result=c.check_listing_differentiation(self.record(),[self.record(old=True),self.record('262')])
        self.assertEqual(result['status'],'BLOCKED_DUPLICATE')
        conflict=result['conflicts'][0]
        self.assertEqual(conflict['product_id'],'1601969526580')
        self.assertTrue({'source_identity','model_number','hero_image','search_intent'} <= set(conflict['fields']))

    def test_unknown_and_different_article_without_structure_do_not_become_duplicates(self):
        candidate=self.record('262');candidate['source'].pop('critical_facts')
        result=c.check_listing_differentiation(candidate,[self.record()])
        self.assertEqual(result['status'],'UNVERIFIED');self.assertEqual(result['conflicts'],[])
        result=c.check_listing_differentiation({},[{'product_id':'UNKNOWN_ID'}])
        self.assertEqual(result['status'],'UNVERIFIED');self.assertEqual(result['conflicts'],[])
        self.assertIn('UNKNOWN_ID',result['unassociated_catalog_ids'])

    def test_existing_abc_expression_allowed_but_same_shoe_new_abc_not_exempt(self):
        candidate,existing=self.record(),self.record(old=True)
        candidate.update(model_number='HR099-A',existing_family='HR099')
        existing.update(model_number='HR099-B',existing_family='HR099')
        candidate['search_intent']={'key':'importer wholesale program','evidence':['OFFLINE_EXISTING_FAMILY_INTENT']}
        candidate['hero_url']='https://sc04.alicdn.com/kf/OFFLINE_REAL_ALTERNATIVE_ANGLE.jpg'
        candidate['hero_review'].update(url=candidate['hero_url'],aliases=[],sha256='OFFLINE_DIFFERENT_FILE',content_key='reviewed_266_black_side_view',evidence=['OFFLINE_REAL_ANGLE_REVIEW'])
        result=c.check_listing_differentiation(candidate,[existing],operation='update',target_product_id=candidate['product_id'])
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['comparisons'][0]['status'],'existing_family_expression')
        self.assertEqual(c.check_listing_differentiation(candidate,[existing],operation='create')['status'],'BLOCKED_DUPLICATE')
        invalid=deepcopy(candidate);invalid['model_number']='HR100-A'
        self.assertNotEqual(c.check_listing_differentiation(invalid,[existing],operation='update',target_product_id=invalid['product_id'])['status'],'PASS')
        same_id=deepcopy(candidate)
        self.assertEqual(c.check_listing_differentiation(candidate,[same_id],operation='update',target_product_id=candidate['product_id'])['comparisons'],[])

    def test_hero_label_identity_and_same_pixels_under_different_url_are_blocked(self):
        candidate=self.record('262');candidate['hero_review'].update(label_status='observed',
            visible_model_number='BQ-W266',expected_visible_model_number='BQ-W262')
        result=c.check_listing_differentiation(candidate,[self.record()])
        self.assertEqual(result['status'],'BLOCKED_DIFFERENTIATION')
        self.assertIn('hero_visible_model_number',result['conflicts'][0]['fields'])
        candidate=self.record('262');candidate['hero_review']['sha256']=self.record()['hero_review']['sha256']
        result=c.check_listing_differentiation(candidate,[self.record()])
        self.assertEqual(result['status'],'BLOCKED_DIFFERENTIATION')
        self.assertIn('hero_image',result['conflicts'][0]['fields'])

    def test_actual_submitter_blocks_duplicate_and_late_model_hero_tampering(self):
        class MemoryClient:
            calls=0
            def top_call(self,*args):self.calls+=1;return {'biz_success':True,'product_id':123}
            def api_error(self,*args):return None
        client=MemoryClient();bad=self.prepared(self.record(),[self.record(old=True)])
        with self.assertRaisesRegex(ValueError,'1601969526580'):self.pub.api_submit(client,{},bad,False)
        self.assertEqual(client.calls,0)
        listing=self.prepared(self.record('262'),[self.record()])
        self.assertEqual(listing['differentiation_review']['status'],'PASS')
        self.pub.api_submit(client,{},listing,False);self.assertEqual(client.calls,1)
        root=ET.fromstring(listing['xml']);root.find("./field[@id='scImages']/complex-value/field/value").text=self.record()['hero_url']
        listing['xml']=ET.tostring(root,encoding='unicode');listing['expected_fields']=self.pub.field_snapshot(root)
        with self.assertRaisesRegex(ValueError,'actual model/hero/title'):self.pub.api_submit(client,{},listing,False)
        self.assertEqual(client.calls,1)

    def manifest(self,tmp,review=True):
        candidate=self.record();listing=self.prepared(candidate,[])
        (tmp/'payload.xml').write_text(listing['xml'],encoding='utf-8')
        schema=ET.fromstring(listing['xml'])
        model=schema.find("./field[@id='icbuCatProp']");definitions=ET.SubElement(model,'fields')
        ET.SubElement(definitions,'field',id='p-3',name='Model Number',type='input')
        (tmp/'schema.xml').write_bytes(ET.tostring(schema))
        manifest={'operation':'create','facts_reviewed':True,'source_evidence':[self.fixture['source_register']],
          'category_id':32211,'expected_model':candidate['model_number'],'current_schema':'schema.xml','payload_xml':'payload.xml',
          'current_schema_sha256':hashlib.sha256((tmp/'schema.xml').read_bytes()).hexdigest(),
          'schema_request_id':'OFFLINE_SCHEMA_GATE','schema_acquired_at':datetime.now(timezone.utc).isoformat(),
          'field_ids':['icbuCatProp','productTitle','scImages']}
        if review:
            snapshots=[dict(x,kind='catalog_snapshot') for x in self.fixture['full_catalog_snapshot_files']]
            snapshots.append({'path':self.fixture['source_register'],'sha256':self.fixture['source_register_sha256'],'kind':'source_register'})
            context={'candidate':candidate,'source_records':self.records,'evidence_files':snapshots,
                'coverage_limit':'Saved local snapshot only; no live query or global dedup clearance asserted.'}
            (tmp/'review.json').write_text(json.dumps(context),encoding='utf-8')
            manifest.update(differentiation_review='review.json',differentiation_review_sha256=hashlib.sha256((tmp/'review.json').read_bytes()).hexdigest())
        (tmp/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8');return tmp/'manifest.json'

    def test_existing_full_local_snapshot_and_source_register_loader_no_live_calls(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp=Path(folder);path=self.manifest(tmp)
            listing=self.pub.load_submission_manifest(path,'create',None)
            result=listing['differentiation_review']
            self.assertEqual(result['status'],'BLOCKED_DUPLICATE')
            self.assertIn('1601969526580',[r['product_id'] for r in result['conflicts']])
            self.assertGreater(result['evidence_provenance']['catalog_records'],350)
            self.assertEqual(result['evidence_provenance']['reported_totals'],[363,364])
            self.assertFalse(result['evidence_provenance']['counts_match_reported_total'])
            context=json.loads((tmp/'review.json').read_text(encoding='utf-8'))
            context['evidence_files'][0]['sha256']='bad hash';(tmp/'review.json').write_text(json.dumps(context),encoding='utf-8')
            manifest=json.loads(path.read_text(encoding='utf-8'));manifest['differentiation_review_sha256']=hashlib.sha256((tmp/'review.json').read_bytes()).hexdigest();path.write_text(json.dumps(manifest),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'evidence hash differs'):self.pub.load_submission_manifest(path,'create',None)

    def test_real_cli_missing_review_and_duplicate_stop_before_credentials_or_receipt(self):
        for reviewed in (False,True):
            with self.subTest(reviewed=reviewed),tempfile.TemporaryDirectory() as folder:
                tmp=Path(folder);manifest=self.manifest(tmp,review=reviewed);receipt=tmp/'receipt.json'
                argv=[str(HERE/'publish_hot_rank_hr_a_batch.py'),'--mode','publish','--input-manifest',str(manifest),'--receipt',str(receipt)]
                with patch.object(sys,'argv',argv),patch.object(self.pub,'load_client') as loader,contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaisesRegex(ValueError,'BLOCKED_DUPLICATE' if reviewed else 'UNVERIFIED'):
                        self.pub.main()
                    loader.assert_not_called();self.assertFalse(receipt.exists())

if __name__=='__main__':unittest.main()
