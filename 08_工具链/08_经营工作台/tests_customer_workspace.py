import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest
from customer_workspace import CustomerWorkspace,CANDIDATES

class CustomerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.record={'reference':'BQ-REAL','company':'Buyer','country':'US','quantity':'500','requirements':'Need custom samples.','receivedAt':'2026-10-28T14:48:30.121Z','status':'new'}
        self.obj={'id':'customer:website-BQ-REAL','kind':'customer','title':'Buyer','source':'网站询盘 · BQ-REAL','content':json.dumps(self.record)}
        def get_object(oid):
            if oid!=self.obj['id']:raise ValueError('Unknown')
            return copy.deepcopy(self.obj)
        self.app=SimpleNamespace(root=self.root,db=sqlite3.connect(':memory:'),lock=threading.RLock(),business=SimpleNamespace(get_object=get_object))
        self.addCleanup(self.app.db.close);self.work=CustomerWorkspace(self.app)
    def candidates(self):
        path=self.root/CANDIDATES;path.parent.mkdir(parents=True)
        path.write_text(json.dumps([{'id':'stable-company','company':'Real Buyer','website':'https://buyer.test','source_url':'https://buyer.test/about','market_hint':'US hint, not confirmed','discovery_note':'Check product fit','discovered_at':'2026-10-21','review':{'state':'未核验'},'analysis':{'tier':'PRIORITIZE','method':'rules'},'contacts':[{'kind':'email','value':'business@buyer.test','delivery_status':'unknown','permission':'not_confirmed'}],'pages':[{'url':'https://buyer.test/about','title':'About','checked_at':'2026-10-21'}]},
            {'id':'example','company':'Synthetic Example Footwear','website':'https://company.example/'}]),encoding='utf8')
        return path
    def test_original_website_record_has_unknown_origin_not_false_natural_acquisition(self):
        profile=self.work.profile(self.obj['id'])
        self.assertEqual(profile['original_text'],'Need custom samples.')
        self.assertEqual(profile['original_language'],'unknown');self.assertEqual(profile['translation_zh'],'')
        self.assertEqual(profile['provenance']['acquisition'],'unknown')
        self.assertEqual(profile['analysis']['intent'],'unknown');self.assertEqual(profile['analysis']['fit'],'unknown')
        self.assertEqual(profile['cleaned']['quantity'],'500')
        self.assertFalse(profile['stale']);self.assertFalse((self.root/'04_客户开发').exists())
    def test_translation_analysis_are_derived_file_only_and_original_unchanged(self):
        before=copy.deepcopy(self.obj);profile=self.work.profile(self.obj['id'])
        saved=self.work.save_profile(self.obj['id'],{'source_hash':profile['source_hash'],'original_language':'en','translation_zh':'需要定制样品。',
            'analysis':{'intent':'待核实','fit':'需核样品能力','facts':[{'claim':'要求定制样品','evidence':'original_text'}],'inferences':['可能是品牌开发需求'],'missing':['实际鞋款规格'],'next_action':'询问样品要求'},
            'source_note':'后台记录存在，不证明自然获客；归因字段为空。','evidence':[{'path':'原迁移证据.json','text':'已人工核元数据','observed_at':'2026-10-31'}]})
        self.assertEqual(saved['translation_zh'],'需要定制样品。');self.assertEqual(self.obj,before)
        self.assertEqual(saved['analysis']['facts'][0]['claim'],'要求定制样品')
        self.assertIn('不证明自然获客',saved['provenance']['evidence_notes'])
        row=self.app.db.execute('SELECT path FROM customer_profiles').fetchone();data=json.loads((self.root/row[0]).read_text(encoding='utf8'))
        self.assertNotIn('original_text',data);self.assertNotIn('requirements',data)
        self.assertEqual(CustomerWorkspace(self.app).profile(self.obj['id'])['translation_zh'],'需要定制样品。')
        self.assertEqual([r[1] for r in self.app.db.execute('PRAGMA table_info(customer_profiles)')],['object_id','path'])
    def test_source_change_marks_old_translation_stale_and_refuses_stale_save(self):
        old=self.work.profile(self.obj['id']);self.work.save_profile(self.obj['id'],{'source_hash':old['source_hash'],'translation_zh':'旧译文'})
        self.record['requirements']='Different need';self.obj['content']=json.dumps(self.record)
        current=self.work.profile(self.obj['id']);self.assertTrue(current['stale']);self.assertEqual(current['translation_zh'],'旧译文')
        with self.assertRaisesRegex(ValueError,'原来源已变化'):self.work.save_profile(self.obj['id'],{'source_hash':old['source_hash'],'translation_zh':'Bad overwrite'})
        self.assertEqual(self.work.profile(self.obj['id'])['translation_zh'],'旧译文')
    def test_source_type_alibaba_order_is_not_misclassified_as_natural_website_lead(self):
        self.obj.update(id='customer:order-buyer-1',source_type='alibaba_order_buyer',content=json.dumps({'company':'Order Buyer','quantity':100}))
        result=self.work.profile(self.obj['id']);self.assertEqual(result['source_type'],'alibaba_order_buyer')
        self.assertEqual(result['provenance']['acquisition'],'unknown')
    def test_existing_18_style_pool_is_projected_readonly_with_ids_and_evidence(self):
        path=self.candidates();before=path.read_bytes();result=self.work.discovery()
        self.assertEqual(len(result['candidates']),1);candidate=result['candidates'][0]
        self.assertEqual(candidate['id'],'candidate:stable-company');self.assertEqual(candidate['object_id'],'prospect:candidate:stable-company')
        self.assertEqual(candidate['crm_status'],'not_checked');self.assertEqual(candidate['outreach_status'],'unknown')
        self.assertTrue(candidate['evidence']);self.assertFalse(candidate['ready_for_customer'])
        self.assertEqual(candidate['source_record']['analysis']['method'],'rules')
        self.assertEqual(path.read_bytes(),before);self.assertEqual(self.work.list_discovery('candidate','Real')[0]['id'],candidate['id'])
    def test_existing_candidate_updates_only_annotation_file_not_source_pool(self):
        path=self.candidates();before=path.read_bytes()
        updated=self.work.update_discovery('candidate:stable-company',{'next_action':'核官网采购入口','status':'推进准备','ready_for_customer':True,'evidence':[{'url':'https://buyer.test/contact','text':'人工新增公开出处'}]})
        self.assertEqual(updated['next_action'],'核官网采购入口');self.assertTrue(updated['ready_for_customer'])
        self.assertEqual(updated['outreach_status'],'unknown');self.assertEqual(path.read_bytes(),before)
        indexed=self.app.db.execute('SELECT path FROM customer_discovery').fetchone();derived=json.loads((self.root/indexed[0]).read_text(encoding='utf8'))
        self.assertIn('annotations',derived);self.assertNotIn('contacts',derived);self.assertNotIn('source_record',derived)
    def test_create_research_task_and_manual_candidate_persist_without_fake_external_effects(self):
        task=self.work.create_discovery({'kind':'research_task','title':'找美国休闲鞋批发商','target':'公开采购入口','next_action':'由Agent研究官网','evidence':[]})
        candidate=self.work.create_discovery({'kind':'candidate','company':'Manually researched buyer','website':'https://manual.test'})
        self.assertEqual(len(self.work.discovery()['tasks']),1);self.assertEqual(len(self.work.discovery()['candidates']),1)
        self.assertEqual(self.work.get_discovery(task['id'])['object_id'],'prospect:'+task['id'])
        self.assertEqual(candidate['outreach_status'],'unknown');self.assertFalse(self.work.discovery()['outreach_enabled'])
        updated=self.work.update_discovery(task['id'],{'notes':'已列公开证据，未联系','next_action':'人工核对目标'})
        self.assertEqual(updated['notes'],'已列公开证据，未联系')
        self.assertEqual(CustomerWorkspace(self.app).get_discovery(task['id'])['next_action'],'人工核对目标')
    def test_unsupported_original_mutation_or_claim_fields_rejected(self):
        profile=self.work.profile(self.obj['id'])
        with self.assertRaises(ValueError):self.work.save_profile(self.obj['id'],{'source_hash':profile['source_hash'],'original_text':'overwrite'})
        with self.assertRaises(ValueError):self.work.create_discovery({'kind':'candidate','company':'Buyer','sent':True})

if __name__=='__main__':unittest.main()
