"""Exercise the actual publisher entry paths with an in-memory transport only."""
import contextlib
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
PUBLISHER = HERE / 'publish_hot_rank_hr_a_batch.py'
CURRENT = '<itemSchema><field id="catId"><value>32211</value></field><field id="icbuCatProp" type="complex"><fields><field id="p-3" name="Model Number" type="input"/></fields></field><field id="productTitle"><rules/><value>old</value></field><field id="sku"><complex-values><field id="skuId"><value>77</value></field><field id="skuOuterId"><value>target</value></field></complex-values></field><field id="detailImage"><complex-values><field id="gallery"><value>150</value></field></complex-values></field></itemSchema>'
TITLE = '<itemSchema><field id="productTitle"><value>new</value></field></itemSchema>'

def load_publisher():
    spec = importlib.util.spec_from_file_location('real_offline_publisher', PUBLISHER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class MemoryClient:
    def __init__(self, response=None, error=None):
        self.calls = []
        self.response = response if response is not None else {'biz_success': True, 'product_id': 123}
        self.error = error
    def load_config(self, path):
        return {}
    def api_error(self, response):
        return None
    def top_call(self, config, method, params):
        self.calls.append((method, params))
        if self.error:
            raise self.error
        return self.response

class RealPathTests(unittest.TestCase):
    def setUp(self):
        self.pub = load_publisher()
    def listing(self, operation='create', xml=TITLE, fields=('productTitle',), dependencies=()):
        intended=ET.fromstring(xml)
        if operation!='update':
            fields=tuple(fields)+('icbuCatProp',)
            ET.SubElement(intended,'field',id='icbuCatProp',type='complex')
        return self.pub.prepare_scoped_listing(ET.fromstring(CURRENT), intended, operation=operation,
            category_id=32211, target_product_id='123' if operation=='update' else None,
            field_ids=fields, dependency_ids=dependencies,expected_model='OFFLINE_MODEL' if operation!='update' else None)

    def test_timeout_and_connection_failure_are_one_write_attempt(self):
        for operation in ('create','createDraft','update'):
            for exc in (TimeoutError('server may have committed'), ConnectionError('lost reply')):
                client = MemoryClient(error=exc)
                result = self.pub.api_submit(client, {}, self.listing(operation), operation=='createDraft',
                    '123' if operation=='update' else None)
                self.assertEqual(len(client.calls), 1)
                self.assertEqual(result['status'], 'write_outcome_unknown')
                self.assertEqual(result['content_status'], 'unverified_content')

    def test_existing_draft_promotion_is_bound_to_fresh_matching_render(self):
        listing = self.listing()
        draft_xml = '<itemSchema><field id="icbuCatProp"><complex-value><field id="p-3"><value inputValue="OFFLINE_MODEL">-3</value></field></complex-value></field></itemSchema>'
        evidence = {'product_id':'456','request_id':'read-456','xml':draft_xml,
                    'acquired_at':datetime.now(timezone.utc).isoformat()}
        client = MemoryClient()
        self.pub.api_submit(client, {}, listing, False, publish_draft_id='456', draft_readback=evidence)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0][0], 'alibaba.icbu.product.schema.add')
        self.assertEqual(client.calls[0][1]['param_product_top_publish_request']['product_id'], 456)
        for change in ({'product_id':'789'}, {'request_id':None},
                       {'xml':draft_xml.replace('OFFLINE_MODEL','OTHER_MODEL')},
                       {'acquired_at':(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()}):
            rejected = MemoryClient()
            with self.assertRaises(ValueError):
                self.pub.api_submit(rejected, {}, listing, False, publish_draft_id='456', draft_readback={**evidence,**change})
            self.assertEqual(rejected.calls, [])

    def test_external_spec_import_with_no_sibling_on_sys_path(self):
        code = "import importlib.util; s=importlib.util.spec_from_file_location('foreign', " + repr(str(PUBLISHER)) + "); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); assert callable(m.api_submit); print('external import OK')"
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-I', '-B', '-c', code], cwd=directory, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('external import OK', result.stdout)

    def test_update_actual_wire_contains_only_target_and_dependencies(self):
        client = MemoryClient()
        listing = self.listing('update', dependencies=('sku',))
        result = self.pub.api_submit(client, {}, listing, False, '123')
        wire = ET.fromstring(client.calls[0][1]['param_product_top_publish_request']['xml'])
        self.assertEqual({f.get('id') for f in wire}, {'productTitle','sku'})
        self.assertEqual(wire.find(".//field[@id='skuId']/value").text, '77')
        self.assertIsNone(wire.find("./field[@id='detailImage']"))
        self.assertEqual(result['content_status'], 'pending_readback')

    def test_full_historical_payload_missing_scope_and_changed_sku_rejected_before_write(self):
        client = MemoryClient()
        with self.assertRaises(ValueError):
            self.pub.api_submit(client, {}, {'xml':CURRENT, 'category_id':32211}, False, '123')
        with self.assertRaises(ValueError):
            self.listing('update', xml=CURRENT)
        changed = '<itemSchema><field id="sku"><complex-values><field id="skuId"><value>88</value></field></complex-values></field></itemSchema>'
        with self.assertRaises(ValueError):
            self.listing('update', xml=changed, fields=('sku',))
        self.assertEqual(client.calls, [])

    def test_recursive_failure_first_and_ambiguous_flags(self):
        for response in ({'success':False,'biz_success':True,'product_id':123},
                         {'biz_success':True,'product_id':123,'data':{'result':{'model':{'success':False}}}},
                         {'biz_success':True,'product_id':123,'data':'{"result":{"success":false}}'},
                         {'biz_success':True,'product_id':123,'result':{'data':[{'error_code':'DESCRIPTION_REQUIRED'}]}}):
            result = self.pub.api_submit(MemoryClient(response), {}, self.listing(), False)
            self.assertEqual(result['status'], 'business_rejected')
            self.assertEqual(result['content_status'], 'unverified_content')
        for response in ({'product_id':123,'success':True}, {'biz_success':'true','product_id':123}, 'unknown reply'):
            result = self.pub.api_submit(MemoryClient(response), {}, self.listing(), False)
            self.assertEqual(result['status'], 'unverified_business_result')

    def test_content_noop_gate_is_connected_to_actual_submitter(self):
        listing = self.listing('update')
        old = self.pub.field_snapshot(ET.fromstring(CURRENT))
        result = self.pub.api_submit(MemoryClient(), {}, listing, False, '123', formal_readback=old)
        self.assertEqual(result['status'], 'submitted_needs_readback')
        self.assertEqual(result['content_status'], 'content_mismatch_or_noop')
        result = self.pub.api_submit(MemoryClient(), {}, listing, False, '123', formal_readback=listing['expected_fields'])
        self.assertEqual(result['content_status'], 'formal_fields_verified')
        self.assertEqual(self.pub.verify_content('submitted_needs_readback',{},{}),'unverified_content')

    def manifest(self, directory):
        directory = Path(directory)
        (directory/'schema.xml').write_text(CURRENT,encoding='utf-8')
        (directory/'payload.xml').write_text(TITLE,encoding='utf-8')
        data = {'operation':'update','product_id':'123','facts_reviewed':True,'source_evidence':['target source review'],
                'current_schema':'schema.xml','payload_xml':'payload.xml','category_id':32211,
                'current_schema_sha256':hashlib.sha256((directory/'schema.xml').read_bytes()).hexdigest(),
                'schema_request_id':'OFFLINE_TEST','schema_acquired_at':datetime.now(timezone.utc).isoformat(),
                'field_ids':['productTitle'],'dependency_ids':['sku']}
        path=directory/'manifest.json'
        path.write_text(json.dumps(data),encoding='utf-8')
        return path

    def test_real_cli_update_uses_manifest_and_never_calls_historical_builder(self):
        client = MemoryClient()
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.manifest(directory)
            receipt = Path(directory)/'receipt.json'
            argv = [str(PUBLISHER),'--mode','update','--product-id','123','--input-manifest',str(manifest),'--receipt',str(receipt)]
            with patch.object(sys,'argv',argv), patch.object(self.pub,'load_client',return_value=client), contextlib.redirect_stdout(io.StringIO()):
                # Any use of the legacy builder would try to read missing historic data.
                self.pub.SOURCE_XML = Path(directory)/'FORBIDDEN_HISTORICAL_SOURCE.xml'
                self.pub.PACK_ROOT = Path(directory)/'FORBIDDEN_PACKAGE'
                self.assertEqual(self.pub.main(), 2)
            result=json.loads(receipt.read_text(encoding='utf-8'))
            self.assertEqual(len(client.calls),1)
            wire = ET.fromstring(client.calls[0][1]['param_product_top_publish_request']['xml'])
            self.assertEqual(wire.find(".//field[@id='skuId']/value").text,'77')
            self.assertEqual(result['content_status'],'pending_readback')

    def test_legacy_cli_update_fails_before_client_or_history_access(self):
        with patch.object(sys,'argv',[str(PUBLISHER),'--mode','update','--product-id','123']), patch.object(self.pub,'load_client') as loader:
            with self.assertRaises(ValueError):
                self.pub.main()
            loader.assert_not_called()

    def test_cli_existing_receipt_stops_another_write(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.manifest(directory)
            receipt = Path(directory)/'receipt.json'
            receipt.write_text('{"status":"write_outcome_unknown"}',encoding='utf-8')
            argv=[str(PUBLISHER),'--mode','update','--product-id','123','--input-manifest',str(manifest),'--receipt',str(receipt)]
            with patch.object(sys,'argv',argv), patch.object(self.pub,'load_client') as loader:
                with self.assertRaises(FileExistsError):
                    self.pub.main()
                loader.assert_not_called()

    def test_real_cli_timeout_persists_unknown_and_blocks_reexecution(self):
        client=MemoryClient(error=TimeoutError('committed reply lost'))
        with tempfile.TemporaryDirectory() as directory:
            manifest=self.manifest(directory)
            receipt=Path(directory)/'receipt.json'
            argv=[str(PUBLISHER),'--mode','update','--product-id','123','--input-manifest',str(manifest),'--receipt',str(receipt)]
            with patch.object(sys,'argv',argv), patch.object(self.pub,'load_client',return_value=client), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(self.pub.main(),1)
                self.assertEqual(json.loads(receipt.read_text(encoding='utf-8'))['status'],'write_outcome_unknown')
                with self.assertRaises(FileExistsError):
                    self.pub.main()
            self.assertEqual(len(client.calls),1)

    def test_cli_verify_serialized_receipt_requires_later_target_readback(self):
        result = self.pub.api_submit(MemoryClient(), {}, self.listing('update'), False, '123')
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            receipt = directory/'receipt.json'
            receipt.write_text(json.dumps(result),encoding='utf-8')
            formal = directory/'formal.xml'
            evidence = directory/'readback.json'
            acquired = (datetime.fromisoformat(result['attempted_at'])+timedelta(seconds=1)).isoformat()
            for xml, code in ((CURRENT,2),(TITLE,2)):
                formal.write_text(xml,encoding='utf-8')
                evidence.write_text(json.dumps({'product_id':'123','request_id':'INDEPENDENT_READ',
                    'acquired_at':acquired,'schema_file':'formal.xml',
                    'schema_sha256':hashlib.sha256(formal.read_bytes()).hexdigest()}),encoding='utf-8')
                argv = [str(PUBLISHER),'--mode','verify','--product-id','123','--receipt',str(receipt),'--formal-readback',str(evidence)]
                with patch.object(sys,'argv',argv), patch.object(self.pub,'load_client') as loader, contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(self.pub.main(),code)
                    loader.assert_not_called()

    def test_stale_and_wrong_target_manifests_rejected_before_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.manifest(directory)
            data = json.loads(path.read_text(encoding='utf-8'))
            data['schema_acquired_at'] = (datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
            path.write_text(json.dumps(data),encoding='utf-8')
            with self.assertRaises(ValueError):
                self.pub.load_submission_manifest(path,'update','123')
            with self.assertRaises(ValueError):
                self.pub.load_submission_manifest(path,'update','999')

    def test_current_faq_max_items_and_required_fields_are_enforced(self):
        definition='<itemSchema><field id="companyFaqDesc"><rules><rule name="maxItemsRule" value="2" exProperty="include"/></rules><fields><field id="question"><rules><rule name="requiredRule" value="true"/><rule name="maxInputNumRule" value="150"/></rules></field><field id="answers"><rules><rule name="requiredRule" value="true"/></rules></field></fields></field></itemSchema>'
        item='<complex-values><field id="question"><value>'+('q'*151)+'</value></field><field id="answers"><value>a</value></field></complex-values>'
        current=ET.fromstring(definition)
        for count in (1,2):
            result=self.pub.prepare_scoped_listing(current,ET.fromstring('<itemSchema><field id="companyFaqDesc">'+item*count+'</field></itemSchema>'),operation='update',category_id=32211,target_product_id='123',field_ids=['companyFaqDesc'])
            self.assertEqual(len(ET.fromstring(result['xml']).findall('./field/complex-values')),count)
        with self.assertRaises(ValueError):
            self.pub.prepare_scoped_listing(current,ET.fromstring('<itemSchema><field id="companyFaqDesc">'+item*3+'</field></itemSchema>'),operation='update',category_id=32211,target_product_id='123',field_ids=['companyFaqDesc'])
        with self.assertRaises(ValueError):
            self.pub.prepare_scoped_listing(current,ET.fromstring('<itemSchema><field id="companyFaqDesc"><complex-values><field id="question"><value>q</value></field></complex-values></field></itemSchema>'),operation='update',category_id=32211,target_product_id='123',field_ids=['companyFaqDesc'])

    def test_latest_raw_receipt_fixture_has_exact_category_and_approved_formal_scope(self):
        fixture=json.loads((HERE/'schema_contract_fixtures/266_verified_receipts.json').read_text(encoding='utf-8'))
        self.assertEqual(fixture['category_id'],'32211')
        self.assertEqual(fixture['formal_after']['faq_count'],6)
        self.assertTrue(fixture['unrelated_formal_fields_unchanged'])
        status=self.pub._contract.capability('update','4','32211',field='companyFaqDesc')
        self.assertEqual(status['status'],'formal_fields_verified_approved')
        self.assertEqual(fixture['formal_approved']['status'],'approved')
        self.assertEqual(fixture['formal_approved']['display'],'Y')
        self.assertEqual(status['field_evidence'][0]['public_verification']['status'],'reported_verified')
        self.assertEqual(status['field_evidence'][0]['request_id'],'21501b8d17909310882434553')

if __name__ == '__main__':
    unittest.main()
