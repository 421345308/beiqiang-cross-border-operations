import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from adapter import Adapter

PROJECT='11111111-2222-3333-4444-555555555555'
ACCOUNT={'accounts':[{'accountName':'Test','accountType':'personal','isActive':True,'credits':0,'token':'NEVER','email':'private@example.invalid'}]}

class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.calls=[];self.payload={'folders':[],'total':0}
        self.adapter=Adapter(runner=self.fake_run,executable='/fixture/libtv.exe',receipt_dir=Path(self.directory.name)/'receipts')

    def fake_run(self,args,**kwargs):
        self.calls.append((args,kwargs))
        self.assertIs(kwargs['shell'],False)
        self.assertNotIn('LIBTV_DEBUG',kwargs['env'])
        self.assertFalse((Path(kwargs['cwd'])/'.libtv').exists())
        value=ACCOUNT if args[1:]==['account','list'] else self.payload
        if args[1]=='node' and args[2]!='list' and 'nodes' in self.payload:
            value=self.payload['nodes'][0]
        return SimpleNamespace(returncode=0,stdout=json.dumps(value),stderr='')

    def test_account_only_name_status_and_credit_fields(self):
        result=self.adapter.execute('account')
        self.assertTrue(result['ok']);self.assertEqual(result['data']['account']['credits'],0)
        self.assertNotIn('NEVER',json.dumps(result));self.assertNotIn('private@',json.dumps(result))
        self.assertEqual(self.calls[0][0][1:],['account','list'])

    def test_lists_normalize_documented_shapes_and_pages(self):
        self.payload={'folders':[{'id':42,'name':'Workspace','token':'PRIVATE'}],'total':7}
        result=self.adapter.execute('workspaces',page=2,page_size=5)
        self.assertEqual(result['data']['workspaces']['items'][0]['id'],'42')
        self.assertEqual(result['data']['workspaces']['total'],7)
        self.assertNotIn('PRIVATE',json.dumps(result))
        self.payload={'projectMetaList':[{'uuid':PROJECT,'name':'Canvas','folderId':42}],'total':1}
        result=self.adapter.execute('projects',workspace_id=42)
        self.assertEqual(result['data']['projects']['items'][0]['id'],PROJECT)
        self.assertEqual(self.calls[-1][0][-2:],['-w','42'])

    def test_project_and_nodes_require_explicit_uuid(self):
        self.payload={'uuid':PROJECT,'nodes':[{'id':'node-id','data':{'name':'Text','content':['hello']},'position':{'x':1,'y':2}}],'edges':[]}
        result=self.adapter.execute('project',project_id=PROJECT)
        self.assertEqual(result['data']['project']['nodes'][0]['title'],'Text')
        result=self.adapter.execute('nodes',project_id=PROJECT)
        self.assertEqual(result['data']['nodes']['items'][0]['content'],['hello'])
        self.assertEqual(self.calls[-1][0][-2:],['-p',PROJECT])
        result=self.adapter.execute('nodes',project_id=PROJECT.replace('-',''))
        self.assertTrue(result['ok'])

    def test_auth_failure_never_becomes_false_empty_projects(self):
        def failed(args,**kwargs):return SimpleNamespace(returncode=1,stdout='',stderr='401 token=PRIVATE https://private.invalid')
        result=Adapter(runner=failed,executable='libtv.exe').execute('projects')
        self.assertEqual(result['error']['code'],'AUTH_REQUIRED')
        self.assertIsNone(result['data']);self.assertNotIn('PRIVATE',json.dumps(result))

    def test_invalid_inputs_do_not_run_any_cli(self):
        cases=[('run',{}),('projects',{'run':True}),('project',{'project_id':'list'}),('create_project',{'name':'Hello'}),('nodes',{'project_id':PROJECT+';bad'}),('create_text_node',{'project_id':PROJECT,'title':'a','content':'b','x':float('nan')})]
        for operation,kwargs in cases:
            with self.subTest(operation=operation):self.assertFalse(self.adapter.execute(operation,**kwargs)['ok'])
        self.assertEqual(self.calls,[])

    def test_create_project_is_explicit_no_binding_or_model_run(self):
        self.payload={'uuid':PROJECT,'name':'--run & echo evil','requestId':'remote-id'}
        result=self.adapter.execute('create_project',workspace_id=0,name='--run & echo evil')
        self.assertTrue(result['ok'])
        self.assertEqual(self.calls[-1][0][1:],['project','create','-w','0','--','--run & echo evil'])
        self.assertEqual(len(list((Path(self.directory.name)/'receipts').glob('*.json'))),1)

    def test_text_content_is_property_not_model_parameter_or_generation(self):
        self.payload={'id':'node-created','data':{'name':'Notes','content':['a=b\nhello']}}
        result=self.adapter.execute('create_text_node',project_id=PROJECT,title='Notes',content='a=b\nhello',x=-2,y=3)
        self.assertTrue(result['ok'])
        args=self.calls[-1][0]
        self.assertEqual(args[1:6],['node','--x','-2','--y','3'])
        self.assertIn('content=["a=b\\nhello"]',args)
        self.assertNotIn('--run',args);self.assertNotIn('-s',args)

    def test_missing_created_id_preserves_receipt_but_is_not_success(self):
        self.payload={'ok':True}
        result=self.adapter.execute('create_project',workspace_id=0,name='Canvas')
        self.assertFalse(result['ok']);self.assertEqual(result['error']['code'],'WRITE_RESULT_UNCONFIRMED')
        self.assertIsNotNone(result['source']['receipt'])

    def test_web_hyphen_operation_alias_keeps_requested_operation(self):
        self.payload={'uuid':PROJECT}
        result=self.adapter.execute('create-project',workspace_id=1,name='Canvas')
        self.assertTrue(result['ok']);self.assertEqual(result['operation'],'create-project')
        self.assertFalse(result['source']['read_only'])

    def test_real_project_create_projectmeta_envelope(self):
        # Structure read from the first real UI creation receipt. Identity fields
        # are synthetic; no remote create is performed by this regression test.
        self.payload={'projectMeta':{'id':12,'uuid':PROJECT.replace('-',''),
            'name':'连接验收（无生成）','visibility':0,'ownerId':0,
            'createdAtMs':1793440481000,'updatedAtMs':1793440481000,
            'projectType':0,'bizScene':0,'source':0}}
        result=self.adapter.execute('create-project',workspace_id=0,name='连接验收（无生成）')
        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['project']['id'],PROJECT.replace('-',''))
        self.assertEqual(result['data']['project']['name'],'连接验收（无生成）')
        self.assertEqual(result['data']['project']['updated_at'],1793440481000)
        self.assertNotIn('ownerId',result['data']['project'])
        self.assertIsNotNone(result['source']['receipt'])

    def test_timeout_has_no_raw_diagnostics_and_no_retry(self):
        def timed(args,**kwargs):raise subprocess.TimeoutExpired(args,45,stderr='PRIVATE')
        result=Adapter(runner=timed,executable='libtv.exe').execute('account')
        self.assertEqual(result['error']['code'],'CLI_TIMEOUT');self.assertFalse(result['error']['retryable'])
        self.assertNotIn('PRIVATE',json.dumps(result))

if __name__=='__main__':unittest.main()
