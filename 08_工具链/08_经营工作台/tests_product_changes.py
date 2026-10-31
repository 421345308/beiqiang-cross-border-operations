import copy
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from product_changes import CATALOG, GET, RENDER, UPDATE, ProductChanges


class Client:
    def __init__(self):
        self.product = {'id': '123', 'subject': 'Old title', 'status': 'approved', 'display': 'Y',
                        'category_id': 32299, 'keywords': ['original'], 'main_image': {'images': ['image']},
                        'product_sku': {'skus': ['original']}, 'attributes': {'material': 'verified'}}
        self.calls = []
        self.receipt = {'biz_success': True, 'request_id': 'req-1'}
        self.after_write = None

    def call(self, method, params):
        self.calls.append((method, copy.deepcopy(params)))
        if method == GET:
            return {'product': copy.deepcopy(self.product), 'request_id': 'read-1'}
        if method == RENDER:
            from xml.etree import ElementTree as E
            root=E.Element('itemSchema');field=E.SubElement(root,'field',id='productTitle',type='input')
            E.SubElement(field,'value').text=self.product['subject']
            E.SubElement(field,'rules')
            E.SubElement(root,'field',id='productKeywords',type='input')
            return {'data': E.tostring(root,encoding='unicode')}
        if method == UPDATE:
            if self.after_write:
                self.after_write()
            if isinstance(self.receipt, Exception):
                raise self.receipt
            return copy.deepcopy(self.receipt)
        raise AssertionError('Unexpected method')


class ProductChangeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.path=self.root/CATALOG;self.path.parent.mkdir(parents=True)
        self.initial={'schema_version':1,'updated_on':'old-date','listings':[
            {'id':'123','product_id':'shared-model','catalog_fields':{'title':'Old catalog','at':'old-date','keywords':['keep']},
             'current_platform_fields':{'title':'Old title','at':'current-date','highlights':'keep'},
             'local_sync':{'state':'EXISTING_STATE','current_fields_file':'existing.json'},
             'formal_fields':{'file':'existing.json','at':'existing-date'},'notes':'preserve'},
            {'id':'456','product_id':'other','notes':'other original'}]}
        self.write(self.initial)
        (self.root/'facts.md').write_text('Verified facts',encoding='utf8')
        self.app=SimpleNamespace(root=self.root,state=self.root/'.local',lock=threading.RLock(),db=sqlite3.connect(':memory:'))
        self.client=Client();self.changes=ProductChanges(self.app,self.client)

    def tearDown(self):
        self.app.db.close();self.temp.cleanup()

    def write(self,value):
        self.path.write_text(json.dumps(value),encoding='utf8')

    def read(self):
        return json.loads(self.path.read_text(encoding='utf8'))

    def prepare(self):
        result=self.changes.prepare('123','New title',rationale='Owner-reviewed facts',evidence=['facts.md'])
        self.assertTrue(result['ok'],result)
        return result['change']

    def apply(self,change):
        return self.changes.apply(change['id'],confirmed=True,expected_version=change['version'])

    def test_prepare_real_shape_and_persistent_list(self):
        before=self.path.read_bytes();change=self.prepare()
        self.assertEqual(change['diff'],{'field':'title','before':'Old title','after':'New title','localBefore':'Old title'})
        self.assertEqual(change['state'],'prepared')
        self.assertEqual([c[0] for c in self.client.calls],[GET,RENDER])
        self.assertNotIn('productKeywords',change['xml'])
        self.assertNotIn('rules',change['xml'])
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(ProductChanges(self.app,self.client).list_changes()[0]['id'],change['id'])

    def test_confirmation_version_and_platform_conflicts_do_not_write(self):
        change=self.prepare()
        for result in (self.changes.apply(change['id'],confirmed=False,expected_version=change['version']),
                       self.changes.apply(change['id'],confirmed=True,expected_version='old')):
            self.assertFalse(result['ok'])
        self.client.product['keywords']=['changed']
        self.assertEqual(self.apply(change)['error']['code'],'PLATFORM_VERSION_CONFLICT')
        self.assertNotIn(UPDATE,[c[0] for c in self.client.calls])

    def test_local_same_object_change_blocks_submit(self):
        change=self.prepare();data=self.read();data['listings'][0]['notes']='new notes';self.write(data)
        self.assertEqual(self.apply(change)['error']['code'],'LOCAL_VERSION_CONFLICT')
        self.assertNotIn(UPDATE,[c[0] for c in self.client.calls])

    def test_submit_is_not_formal_or_public_and_exact_payload(self):
        change=self.prepare();before=self.path.read_bytes();result=self.apply(change)
        self.assertEqual(result['change']['state'],'submitted')
        self.assertEqual(result['change']['formal']['state'],'not-verified')
        self.assertEqual(result['change']['publicVerification']['state'],'not-verified')
        req=[c[1] for c in self.client.calls if c[0]==UPDATE][0]['param_product_top_publish_request']
        self.assertEqual(set(req),{'product_id','cat_id','language','xml'})
        self.assertEqual(req['product_id'],123)
        self.assertEqual(self.path.read_bytes(),before)

    def test_timeout_unknown_no_retry_even_after_restart(self):
        change=self.prepare();self.client.receipt=RuntimeError('token=private')
        result=self.apply(change);self.assertEqual(result['change']['state'],'outcome_unknown')
        other=ProductChanges(self.app,self.client)
        self.assertEqual(other.apply(change['id'],confirmed=True,expected_version=result['change']['version'])['error']['code'],'ALREADY_ATTEMPTED_RECONCILE_ONLY')
        second=self.prepare()
        self.assertEqual(self.apply(second)['error']['code'],'PRODUCT_CHANGE_IN_PROGRESS')
        self.assertEqual(sum(c[0]==UPDATE for c in self.client.calls),1)
        self.assertNotIn('private',json.dumps(result))

    def test_submission_reserved_before_client_write(self):
        change=self.prepare()
        def inspect():
            self.assertEqual(self.changes.get(change['id'])['change']['submission']['state'],'outcome-unknown')
        self.client.after_write=inspect
        self.assertTrue(self.apply(change)['ok'])

    def test_positive_transport_without_business_flag_unknown(self):
        change=self.prepare();self.client.receipt={'request_id':'req'}
        self.assertEqual(self.apply(change)['change']['state'],'outcome_unknown')

    def test_business_rejection_no_repeat(self):
        change=self.prepare();self.client.receipt={'biz_success':False,'msg':'private'}
        result=self.apply(change)
        self.assertEqual(result['change']['state'],'business_rejected')
        self.assertNotIn('private',json.dumps(result))
        self.assertFalse(self.changes.apply(change['id'],confirmed=True,expected_version=result['change']['version'])['ok'])

    def test_readback_title_match_under_review_not_synced(self):
        change=self.prepare();self.apply(change);before=self.path.read_bytes()
        self.client.product.update(subject='New title',status='modified')
        result=self.changes.reconcile(change['id'])
        self.assertEqual(result['change']['state'],'formal_pending')
        self.assertEqual(self.path.read_bytes(),before)

    def test_critical_keyword_side_effect_blocks_local_sync(self):
        change=self.prepare();self.apply(change);before=self.path.read_bytes()
        self.client.product.update(subject='New title',keywords=['unexpected'])
        result=self.changes.reconcile(change['id'])
        self.assertFalse(result['change']['formal']['protectedFieldsMatch'])
        self.assertEqual(result['change']['state'],'formal_pending')
        self.assertEqual(self.path.read_bytes(),before)

    def test_formal_sync_updates_actual_title_fields_preserves_other_objects(self):
        change=self.prepare();self.apply(change)
        data=self.read();data['listings'][1]['notes']='parallel update';self.write(data)
        self.client.product['subject']='New title'
        result=self.changes.reconcile(change['id']);self.assertTrue(result['ok'],result)
        self.assertEqual(result['change']['state'],'local_synced')
        data=self.read();row=data['listings'][0]
        for key in ('catalog_fields','current_platform_fields'):
            self.assertEqual(row[key]['title'],'New title')
        self.assertEqual(row['catalog_fields']['at'],'old-date')
        self.assertEqual(row['current_platform_fields']['at'],'current-date')
        self.assertEqual(row['product_id'],'shared-model')
        self.assertEqual(row['local_sync']['state'],'EXISTING_STATE')
        self.assertEqual(row['formal_fields']['file'],'existing.json')
        self.assertEqual(data['listings'][1]['notes'],'parallel update')
        self.assertEqual(result['change']['localSync']['indexState'],'pending-regeneration')
        self.assertEqual(result['change']['publicVerification']['state'],'not-verified')
        self.assertTrue(self.changes.reconcile(change['id'])['ok'])

    def test_same_object_parallel_change_readback_local_conflict(self):
        change=self.prepare();self.apply(change);data=self.read();data['listings'][0]['notes']='parallel';self.write(data)
        self.client.product['subject']='New title'
        result=self.changes.reconcile(change['id'])
        self.assertEqual(result['change']['state'],'local_conflict')
        self.assertEqual(self.read()['listings'][0]['notes'],'parallel')

    def test_missing_readback_protection_or_schema_fails_safe(self):
        self.client.product.pop('keywords')
        result=self.changes.prepare('123','New title',rationale='facts',evidence=['facts.md'])
        self.assertEqual(result['error']['code'],'PROTECTION_FIELDS_UNAVAILABLE')

    def test_invalid_evidence_and_identity_no_write(self):
        for ref in ('../facts.md','C:/private.json','.local/private.json'):
            result=self.changes.prepare('123','New title',rationale='facts',evidence=[ref])
            self.assertFalse(result['ok'])
        self.client.product['id']='999'
        self.assertFalse(self.changes.prepare('123','New title',rationale='facts',evidence=['facts.md'])['ok'])

    def test_atomic_replace_error_preserves_old_catalog_and_pending_record(self):
        change=self.prepare();self.apply(change);self.client.product['subject']='New title';before=self.path.read_bytes()
        with patch('product_changes.os.replace',side_effect=PermissionError('private')):
            result=self.changes.reconcile(change['id'])
        self.assertFalse(result['ok']);self.assertEqual(self.path.read_bytes(),before)
        self.assertFalse(list(self.path.parent.glob('.title-change-*')))
        self.assertTrue(self.changes.reconcile(change['id'])['ok'])

    def test_raw_receipts_retained_locally_never_in_ui(self):
        change=self.prepare();result=self.apply(change)
        files=list((self.app.state/'product-changes'/change['id']).glob('*.json'))
        receipts=[json.loads(f.read_text(encoding='utf8')) for f in files]
        self.assertTrue(any(r['method']==GET and 'product' in r['response'] for r in receipts))
        self.assertTrue(any(r['method']==RENDER and 'data' in r['response'] for r in receipts))
        self.assertTrue(any(r['method']==UPDATE and r['response'].get('biz_success') is True for r in receipts))
        self.assertNotIn('response',result['change'])
        self.assertNotIn('original',json.dumps(result['change']))

    def test_network_does_not_hold_shared_application_lock(self):
        change=self.prepare();available=[]
        def inspect():
            def check():
                acquired=self.app.lock.acquire(timeout=.2);available.append(acquired)
                if acquired:self.app.lock.release()
            thread=threading.Thread(target=check);thread.start();thread.join()
        self.client.after_write=inspect
        self.assertTrue(self.apply(change)['ok'])
        self.assertEqual(available,[True])

    def test_current_fields_without_legacy_catalog_is_idempotent(self):
        data=self.read();data['listings'][0].pop('catalog_fields');self.write(data)
        change=self.prepare();self.apply(change);self.client.product['subject']='New title'
        for _ in range(2):
            self.assertEqual(self.changes.reconcile(change['id'])['change']['state'],'local_synced')

    def test_edit_during_atomic_write_detected_without_overwriting(self):
        change=self.prepare();self.apply(change);self.client.product['subject']='New title'
        original=self.changes._catalog
        def concurrently_changed(pid):
            result=original(pid)
            data=self.read();data['listings'][1]['notes']='late parallel';self.write(data)
            return result
        with patch.object(self.changes,'_catalog',side_effect=concurrently_changed):
            result=self.changes.reconcile(change['id'])
        self.assertEqual(result['change']['state'],'local_conflict')
        self.assertEqual(self.read()['listings'][1]['notes'],'late parallel')
        self.assertEqual(self.read()['listings'][0]['current_platform_fields']['title'],'Old title')

    def test_display_change_blocks_sync(self):
        change=self.prepare();self.apply(change);self.client.product.update(subject='New title',display='N')
        result=self.changes.reconcile(change['id'])
        self.assertEqual(result['change']['state'],'formal_pending')
        self.assertFalse(result['change']['formal']['displayPreserved'])

    def test_internal_test_cannot_submit(self):
        result=self.changes.prepare('123','New title',rationale='Only development verification',evidence=['facts.md'],internal_test=True)
        self.assertEqual(self.apply(result['change'])['error']['code'],'INTERNAL_TEST_NOT_SUBMITTABLE')
        self.assertNotIn(UPDATE,[c[0] for c in self.client.calls])

    def test_formal_render_unavailable_does_not_sync(self):
        change=self.prepare();self.apply(change);self.client.product['subject']='New title'
        original=self.client.call
        def call(method,params):
            return {'request_id':'render-pending'} if method==RENDER else original(method,params)
        with patch.object(self.client,'call',side_effect=call):
            result=self.changes.reconcile(change['id'])
        self.assertEqual(result['change']['state'],'formal_pending')
        self.assertEqual(result['change']['formal']['schemaState'],'unavailable')


if __name__=='__main__':
    unittest.main()
