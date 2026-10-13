"""A-G factual projection through real manifest; all writes are memory-only."""
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
from xml.etree import ElementTree as E
import hashlib,json,tempfile,unittest,contextlib,io,sys
from unittest.mock import patch
import test_schema_differentiation as d

class TaskPackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):d.DifferentiationTests.setUpClass();cls.h=d.DifferentiationTests();cls.pub=d.DifferentiationTests.pub
    def save(self,tmp,name,obj):
        (tmp/name).write_text(json.dumps(obj),encoding='utf-8');return hashlib.sha256((tmp/name).read_bytes()).hexdigest()
    def files(self,tmp,role='REPLACE'):
        path=self.h.manifest(tmp);m=json.loads(path.read_text());review=json.loads((tmp/'review.json').read_text())
        candidate=self.h.record('262');old=self.h.record();listing=self.h.prepared(candidate,[])
        (tmp/'payload.xml').write_text(listing['xml'],encoding='utf-8');m['expected_model']=candidate['model_number']
        catalog={'products':[{'id':old['product_id'],'red_model':old['model_number'],'subject':old['title'],'main_image':{'images':[old['hero_url']]}}]}
        sha=self.save(tmp,'catalog.json',catalog)
        review['evidence_files']=[x for x in review['evidence_files'] if x['kind']!='catalog_snapshot']+[{'path':'catalog.json','sha256':sha,'kind':'catalog_snapshot'}]
        review['candidate']={'title':candidate['title'],'model_number':candidate['model_number'],'hero_url':candidate['hero_url']}
        m['differentiation_review_sha256']=self.save(tmp,'review.json',review)
        canonical=Path(self.pub.__file__).resolve().parents[3]/'02_Alibaba运营/05_扩品工程/工厂店外新款数据采集模板.md'
        (tmp/'taskpack.md').write_text('# OFFLINE synthetic A-G candidate; not production authorization',encoding='utf-8')
        pack={'task_id':'OFFLINE_TASK_PACK','role':role,'phase':'CANDIDATE_REVIEWED','writer':'OFFLINE_MEMORY_OWNER','next_action':'Offline preflight only',
          'public_model':candidate['model_number'],'category_id':m['category_id'],'product_id':None,
          'source_identity':candidate['source'],'search_intent':candidate['search_intent'],'hero_review':candidate['hero_review'],
          'evidence_files':[{'path':str(canonical),'sha256':hashlib.sha256(canonical.read_bytes()).hexdigest(),'kind':'task_pack_template'},
            {'path':'taskpack.md','sha256':hashlib.sha256((tmp/'taskpack.md').read_bytes()).hexdigest(),'kind':'task_pack_document'}]}
        if role=='REPLACE':
            row={'candidate':'OFFLINE_262','old_product_id':old['product_id'],'new_product_id':None,
              'match_type':'STRATEGIC_RETIRE_AND_REAL_SOURCE_REPLACEMENT_NOT_IDENTICAL_SHOE',
              'source_url':candidate['source']['reference'],'protected':False,'growth_tier':'普通品',
              'authorization_scope':'OFFLINE explicit one-to-one planning only','reservation_status':'OWNER_ACK_PENDING','old_action':'NOT_SENT',
              'retained_siblings':[{'product_id':'OFFLINE_KEEP_SIBLING','disposition':'KEEP_UNCHANGED'}]}
            sha=self.save(tmp,'mapping.json',{'rows':[row]});pack['evidence_files'].append({'path':'mapping.json','sha256':sha,'kind':'replacement_mapping'})
            pack['replacement_plan']={'candidate':'OFFLINE_262','old_product_ids':[old['product_id']]}
        m.update(task_pack='taskpack.json',task_pack_sha256=self.save(tmp,'taskpack.json',pack));self.save(tmp,'manifest.json',m)
        return path,m,pack,candidate,old
    def update(self,tmp,path,m,pack):m['task_pack_sha256']=self.save(tmp,'taskpack.json',pack);self.save(tmp,path.name,m)
    def current_template_wrapper(self):
        """Keep historical product/mapping bytes; bind only current template policy."""
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup);tmp=Path(folder.name)
        fixture=Path(__file__).parent/'schema_contract_fixtures/9968_existing_binding/inspect_manifest.json'
        manifest=json.loads(fixture.read_text(encoding='utf-8'))
        pack_path=fixture.parent/manifest['task_pack'];pack=json.loads(pack_path.read_text(encoding='utf-8'))
        canonical=Path(self.pub.__file__).resolve().parents[3]/'02_Alibaba运营/05_扩品工程/工厂店外新款数据采集模板.md'
        for ref in pack['evidence_files']:
            if ref['kind']=='task_pack_template':ref.update(path=str(canonical),sha256=hashlib.sha256(canonical.read_bytes()).hexdigest())
            else:ref['path']=str((pack_path.parent/ref['path']).resolve())
        for key in ['differentiation_review','current_schema','payload_xml']:
            if manifest.get(key):manifest[key]=str((fixture.parent/manifest[key]).resolve())
        manifest.update(task_pack=str(tmp/'current_template_pack.json'),task_pack_sha256=self.save(tmp,'current_template_pack.json',pack))
        self.save(tmp,'wrapper.json',manifest)
        return tmp/'wrapper.json'
    def test_actual_manifest_maps_facts_and_strategic_old_new_receipt_without_waiver(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp=Path(folder);path,m,pack,candidate,old=self.files(tmp)
            listing=self.pub.load_submission_manifest(path,'create',None)
            self.assertEqual(listing['differentiation_review']['status'],'PASS')
            self.assertIsNone(listing['differentiation_review']['replacement_transition'])
            self.assertEqual(listing['task_pack']['role'],'REPLACE')
            self.assertEqual(listing['replacement_plan']['old_product_ids'],[old['product_id']])
            class Memory:
                calls=[]
                def top_call(self,*args):self.calls.append(args);return {'biz_success':True,'product_id':123}
                def api_error(self,*args):return None
            client=Memory();receipt=self.pub.api_submit(client,{},listing,False)
            self.assertEqual(len(client.calls),1);self.assertEqual(client.calls[0][1],'alibaba.icbu.product.schema.add')
            plan=receipt['replacement_plan'];self.assertEqual(plan['new_product_id'],'123');self.assertEqual(plan['old_action'],'NOT_SENT')
            self.assertFalse(plan['whole_family_complete']);self.assertEqual(plan['retained_siblings'][0]['disposition'],'KEEP_UNCHANGED')

    def test_new_role_preserved_without_fabricating_replacement_or_completed_phase(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp=Path(folder);path,m,pack,*_=self.files(tmp,'NEW');listing=self.pub.load_submission_manifest(path,'create',None)
            self.assertEqual(listing['task_pack']['role'],'NEW');self.assertEqual(listing['task_pack']['phase'],'CANDIDATE_REVIEWED')
            self.assertIsNone(listing['replacement_plan'])
            pack['product_id']='1601969788941';self.update(tmp,path,m,pack)
            with self.assertRaisesRegex(ValueError,'never recreate'):self.pub.load_submission_manifest(path,'create',None)

    def test_missing_facts_hash_conflict_and_protected_or_broad_old_targets_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp=Path(folder);path,m,base,*_=self.files(tmp)
            for mode in ['missing_source','broaden_ids','wrong_source','wrong_model','protected','existing_new_id']:
                pack=deepcopy(base)
                if mode=='missing_source':pack.pop('source_identity')
                elif mode=='broaden_ids':pack['replacement_plan']['old_product_ids'].append('999')
                elif mode=='wrong_source':pack['source_identity']['reference']='https://OFFLINE_WRONG_SOURCE'
                elif mode=='wrong_model':pack['public_model']='WRONG'
                elif mode in ['protected','existing_new_id']:
                    row=json.loads((tmp/'mapping.json').read_text())['rows'][0];row['protected']=mode=='protected';row['new_product_id']='123' if mode=='existing_new_id' else None
                    sha=self.save(tmp,'mapping.json',{'rows':[row]});next(x for x in pack['evidence_files'] if x['kind']=='replacement_mapping')['sha256']=sha
                self.update(tmp,path,m,pack)
                with self.subTest(mode=mode),self.assertRaises(ValueError):self.pub.load_submission_manifest(path,'create',None)
            (tmp/'taskpack.md').write_text('changed')
            with self.assertRaisesRegex(ValueError,'evidence hash differs'):self.pub.load_submission_manifest(path,'create',None)

    def test_strategic_mapping_does_not_suppress_actual_same_style_duplicate(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp=Path(folder);path,m,pack,candidate,old=self.files(tmp)
            review=json.loads((tmp/'review.json').read_text());catalog=json.loads((tmp/'catalog.json').read_text())
            duplicate=deepcopy(candidate);duplicate['product_id']='999'
            catalog['products'].append({'id':'999','red_model':duplicate['model_number'],'subject':duplicate['title'],'main_image':{'images':[duplicate['hero_url']]}})
            review['source_records']['999']=duplicate;next(x for x in review['evidence_files'] if x['kind']=='catalog_snapshot')['sha256']=self.save(tmp,'catalog.json',catalog)
            m['differentiation_review_sha256']=self.save(tmp,'review.json',review);self.save(tmp,path.name,m)
            listing=self.pub.load_submission_manifest(path,'create',None)
            self.assertEqual(listing['differentiation_review']['status'],'BLOCKED_DUPLICATE')
            self.assertEqual(listing['differentiation_review']['conflicts'][0]['product_id'],'999')

    def test_real_9968_existing_cli_preserves_original_and_never_loads_client_or_recreates(self):
        wrapper=self.current_template_wrapper()
        manifest=json.loads(wrapper.read_text(encoding='utf-8'));original=Path(manifest['original_manifest']);before=original.read_bytes()
        argv=[self.pub.__file__,'--mode','inspect-existing','--input-manifest',str(wrapper),'--product-id','1601969788941']
        out=io.StringIO()
        with patch.object(sys,'argv',argv),patch.object(self.pub,'load_client') as client,contextlib.redirect_stdout(out):
            self.assertEqual(self.pub.main(),0);client.assert_not_called()
        result=json.loads(out.getvalue());self.assertFalse(result['create_allowed']);self.assertEqual(result['platform_calls'],0)
        self.assertEqual(result['task_pack']['role'],'NEW')
        self.assertEqual(result['existing_product_id'],'1601969788941')
        self.assertEqual(result['replacement_plan']['old_product_ids'],['1601943742273'])
        self.assertEqual(result['replacement_plan']['old_action'],'NOT_SENT')
        self.assertIsNone(result['differentiation_review']['replacement_transition'])
        self.assertEqual(original.read_bytes(),before)
        with patch.object(self.pub,'load_client') as client:
            with self.assertRaisesRegex(ValueError,'never recreate|current Schema'):self.pub.load_submission_manifest(wrapper,'create',None)
            client.assert_not_called()
        with tempfile.TemporaryDirectory() as folder:
            tmp=Path(folder);bad=deepcopy(manifest);receipt=json.loads(Path(manifest['existing_submission_receipt']).read_text(encoding='utf-8'));receipt['product_id']='999';receipt['response']['product_id']=999
            digest=self.save(tmp,'wrong_receipt.json',receipt);bad.update(existing_submission_receipt=str(tmp/'wrong_receipt.json'),existing_submission_receipt_sha256=digest);self.save(tmp,'wrapper.json',bad)
            with self.assertRaisesRegex(ValueError,'not bound/accepted'):self.pub.inspect_existing_submission_manifest(tmp/'wrapper.json','1601969788941')

    def test_real_existing_fixture_does_not_read_mutable_business_mapping_or_taskpack(self):
        wrapper=self.current_template_wrapper()
        root=Path(self.pub.__file__).resolve().parents[3]
        mutable={str((root/'02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21/HR普通品一对一待替换映射_2026-10-02.json').resolve()),
                 str((root/'02_Alibaba运营/05_扩品工程/执行记录/9968_API完整新建_2026-10-02/经营任务包.md').resolve())}
        original=Path.read_bytes
        def guarded(path):
            if str(path.resolve()) in mutable:raise AssertionError('Historical fixture must not read changing business state')
            return original(path)
        with patch.object(Path,'read_bytes',guarded),patch.object(self.pub,'load_client') as client:
            result=self.pub.inspect_existing_submission_manifest(wrapper,'1601969788941')
            client.assert_not_called()
        self.assertFalse(result['create_allowed']);self.assertEqual(result['platform_calls'],0)

    def test_historical_template_fixture_is_preserved_and_not_silently_rehashed(self):
        base=Path(__file__).parent/'schema_contract_fixtures/9968_existing_binding'
        pack=json.loads((base/'taskpack_projection.json').read_text(encoding='utf-8'))
        template=next(x for x in pack['evidence_files'] if x['kind']=='task_pack_template')
        self.assertEqual(hashlib.sha256((base/'taskpack_template_snapshot.md').read_bytes()).hexdigest(),template['sha256'])
        with patch.object(self.pub,'load_client') as client:
            with self.assertRaisesRegex(ValueError,'hash differs|canonical'):
                self.pub.inspect_existing_submission_manifest(base/'inspect_manifest.json','1601969788941')
            client.assert_not_called()

    def test_off_business_plan_cannot_be_routed_to_schema_create(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp=Path(folder);path=tmp/'off_plan.json'
            self.save(tmp,path.name,{'operation':'off','old_product_ids':['1601943742273'],'facts_reviewed':True})
            with patch.object(self.pub,'load_client') as client:
                with self.assertRaisesRegex(ValueError,'identify operation'):
                    self.pub.load_submission_manifest(path,'create',None)
                client.assert_not_called()

if __name__=='__main__':unittest.main()
