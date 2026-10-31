import csv
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from business import Business,PRODUCTS,SUPPLY,ASSETS,CHANNEL,CRM
from website_inquiries import WebsiteInquiries

class BusinessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.website=WebsiteInquiries(self.root,fetch=lambda:{'ok':True,'records':[],'total':0})
        self.website.refresh(wait=True)
        self.app=SimpleNamespace(root=self.root,db=sqlite3.connect(':memory:'),lock=threading.RLock(),website_inquiries=self.website)
        self.addCleanup(self.app.db.close);self.business=Business(self.app)
    def write(self,path,value):
        target=self.root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(value,ensure_ascii=False),encoding='utf8')
    def product(self):
        self.write(PRODUCTS,{'products':[{'id':'BQ009','aliases':['BQ-009'],'source_state':'ADOPTED','adopted_source_id':'src-1','supply_mode':{'current':'outsourced','scope':'verified source only'},'local_assets':{'asset_roots':['01_产品资产/02_成品素材/BQ009']}}]})
        self.write(SUPPLY,{'sources':[{'id':'src-1','supplier':'Supplier','model':'model-1','url':'https://example.test/source','price':'59','currency':'CNY','observed_at':'2026-01-01'}]})
        self.write(CHANNEL,{'listings':[{'id':'1601','product_id':'BQ009','url':'https://example.test/product','catalog_fields':{'title':'Old title'},'current_platform_fields':{'title':'Current title','at':'2026-10-31','scope':'official readback'}}]})
        self.write(ASSETS,{'files':[{'file':'01_产品资产/02_成品素材/BQ009/shoe.png','products':['BQ009'],'roles':['Main image'],'sha256':'abc'},{'file':'01_产品资产/../private.png','products':['BQ009'],'roles':[]}]})
    def test_real_product_schema_links_supply_current_channel_and_asset(self):
        self.product();obj=self.business.get_object('product:BQ009')
        self.assertEqual(obj['title'],'BQ009');self.assertEqual(obj['subtitle'],'Current title')
        self.assertEqual(len(obj['assets']),1);self.assertTrue(obj['assets'][0]['url'].startswith('/api/media/file?'))
        self.assertIn('Old title',obj['content']);self.assertIn('Current title',obj['content'])
        self.assertEqual(len(self.business.list_objects(kind='product',q='Supplier')),1)
    def test_empty_temp_project_does_not_break_local_sources(self):
        self.assertEqual(self.business.list_objects(),[])
    def test_customer_explicit_crm_and_project_records_skip_example(self):
        path=self.root/CRM;path.parent.mkdir(parents=True)
        with path.open('w',encoding='utf8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=['Company','Email','Next_Action']);writer.writeheader();writer.writerow({'Company':'示例公司'});writer.writerow({'Company':'Real company','Email':'private@example.test','Next_Action':'Prepare sample discussion'})
        project=self.root/'04_客户开发/05_客户项目/VORLEN_BQ009/PROJECT.md';project.parent.mkdir(parents=True);project.write_text('# VORLEN original\nConfirmed facts. No medical promise.',encoding='utf8')
        child=project.parent/'报价/notes.md';child.parent.mkdir();child.write_text('Same customer, different source document.',encoding='utf8')
        crm=self.root/'04_客户开发/01_线索与CRM/research.md';crm.parent.mkdir(parents=True);crm.write_text('| 账户 | 状态 | 下一动作 |\n| --- | --- | --- |\n| Candidate Brand | TECHNICAL_HOLD | Check real capability |\n',encoding='utf8')
        rows=self.business.list_objects('customer');self.assertEqual(len(rows),3)
        original_id=next(r['id'] for r in rows if r['title']=='Real company')
        self.assertIn('private@example.test',self.business.get_object(original_id)['content'])
        self.assertEqual(next(r['id'] for r in self.business.list_objects('customer') if r['title']=='Real company'),original_id)
        vorlen=next(r for r in rows if r['title']=='VORLEN')
        self.assertIn('Same customer',self.business.get_object(vorlen['id'])['content'])
        self.assertFalse(any(r['title']=='示例公司' for r in rows))
    def test_artifact_body_file_is_unique_and_reloads_original_text(self):
        self.product();before=(self.root/PRODUCTS).read_bytes()
        result=self.business.save_artifact('product:BQ009','Draft','Original body')
        path=self.root/result['path'];self.assertIn('/.local/',result['path']);self.assertEqual(path.read_text(encoding='utf8'),'Original body')
        # Body is read from its only authoritative file, not a DB copy.
        path.write_text('Edited in original artifact file',encoding='utf8')
        self.assertEqual(self.business.list_artifacts('product:BQ009')[0]['content'],'Edited in original artifact file')
        other=Business(self.app);saved=other.save_artifact('product:BQ009','Revised','New body',artifact_id=result['id'])
        self.assertEqual(saved['path'],result['path']);self.assertEqual(len(other.list_artifacts()),1)
        self.assertEqual(path.with_suffix('.prev.md').read_text(encoding='utf8'),'Edited in original artifact file')
        columns=[row[1] for row in self.app.db.execute('PRAGMA table_info(business_artifacts)')];self.assertNotIn('content',columns)
        self.assertEqual((self.root/PRODUCTS).read_bytes(),before)
    def test_website_tests_filtered_and_artifacts_keep_website_original_readonly(self):
        payload={'ok':True,'records':[{'reference':'BQ-REAL','company':'Buyer','requirements':'Need sample','internalTest':False},{'reference':'BQ-TEST','internalTest':True}]}
        self.website.fetch=lambda:payload;self.website.refresh(wait=True)
        rows=self.business.list_objects('customer');self.assertEqual(len(rows),1);self.assertEqual(rows[0]['id'],'customer:website-BQ-REAL')
        saved=self.business.save_artifact(rows[0]['id'],'Reply draft','Internal proposal, not sent')
        self.assertTrue(saved['path'].startswith('04_客户开发/.local/网站询盘/BQ-REAL/'))
        self.assertEqual(payload['records'][0]['requirements'],'Need sample')
        self.assertEqual(self.business.website_status()['excluded_internal_tests'],1)
    def test_website_summary_is_bounded_and_full_requirements_only_in_content(self):
        requirements='完整采购需求。'*100
        self.website.fetch=lambda:{'ok':True,'records':[{'reference':'BQ-LONG','name':'Buyer','company':'Company',
            'email':'buyer@example.test','quantity':'500','requirements':requirements,'status':'new','receivedAt':'2026-10-31'}]}
        self.website.refresh(wait=True)
        obj=self.business.get_object('customer:website-BQ-LONG')
        self.assertEqual(len(obj['summary']),240);self.assertTrue(obj['summary'].endswith('…'))
        self.assertEqual(json.loads(obj['content'])['requirements'],requirements)
        self.assertNotIn(requirements,json.dumps(obj['facts'],ensure_ascii=False))
        self.assertEqual(next(f['value'] for f in obj['facts'] if f['label']=='处理状态'),'待处理')
        self.assertEqual(obj['source'],'网站记录 · BQ-LONG')
        self.assertTrue({'联系人','公司','邮箱','采购数量','收到时间'}.issubset({f['label'] for f in obj['facts']}))
    def test_artifact_id_and_object_boundaries(self):
        self.product()
        with self.assertRaises(ValueError):self.business.save_artifact('product:BQ009','Title','Body',artifact_id='../../secret')
        with self.assertRaises(ValueError):self.business.get_object('file:/etc/passwd')

class WebsiteTests(unittest.TestCase):
    def test_memory_cache_status_failure_is_visible_and_old_record_remains_stale(self):
        clock=[1000];calls=[]
        def fetch():calls.append(True);return {'ok':True,'records':[{'reference':'REAL','internalTest':False}]}
        website=WebsiteInquiries(Path('/not-used'),fetch=fetch,clock=lambda:clock[0],ttl=10)
        website.refresh(wait=True);self.assertEqual(len(website.records()),1);self.assertEqual(len(calls),1)
        old=website.status()['observed_at'];clock[0]=1011
        website.fetch=lambda:(_ for _ in ()).throw(RuntimeError('PRIVATE token=NEVER'))
        website.refresh(wait=True)
        self.assertEqual(website.status()['observed_at'],old);self.assertTrue(website.status()['stale'])
        self.assertEqual(website.status()['state'],'error');self.assertEqual(len(website.records()),1)
        self.assertNotIn('NEVER',json.dumps(website.status()))
    def test_missing_env_is_not_configured_and_does_not_request_network(self):
        with tempfile.TemporaryDirectory() as directory,patch('website_inquiries.build_opener') as opener:
            website=WebsiteInquiries(directory);website.refresh(wait=True)
            self.assertEqual(website.status()['state'],'not_configured');opener.assert_not_called()

if __name__=='__main__':unittest.main()
