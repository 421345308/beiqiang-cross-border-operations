"""HTTP integration: real Handler/Business/AgentJobs, temporary source files.

Only the model process and website GET transport are fixtures. No real model,
website/API mutation, or original business file is accessed by these tests.
"""
import http.client
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from urllib.parse import urlencode, parse_qs, urlsplit
from unittest.mock import patch
import server
from business import PRODUCTS,SUPPLY,ASSETS,CHANNEL
from tests_agent_jobs import Process
from website_inquiries import WebsiteInquiries

class DeskHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        generator=self.root/'08_工具链/06_工作区维护/build_b2b_workbench.py';generator.parent.mkdir(parents=True)
        generator.write_bytes((server.HERE.parent/'06_工作区维护/build_b2b_workbench.py').read_bytes())
        spec=importlib.util.spec_from_file_location('desk_http_fixture_parser',generator)
        parser=importlib.util.module_from_spec(spec);spec.loader.exec_module(parser)
        for path in parser.SOURCES:
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('国际B2B具体要成为：**隔离HTTP测试目标**\n**当前位置：隔离测试**\n## 工作台任务\n'
                '| 任务 | 状态 | 主办 | 当前结果 | 下一步 | 依赖/需你决定 | 成果与证据 |\n'
                '| --- | --- | --- | --- | --- | --- | --- |\n'
                '| Fixture | 待开始 | Test | 未执行 | 核验 | 无 | |\n',encoding='utf8')
        self.write(PRODUCTS,{'products':[{'id':'BQ009','aliases':['BQ-009'],'source_state':'ADOPTED','adopted_source_id':'source-1','raw_packages':['01_产品资产/01_原始素材/BQ009']}]})
        self.write(SUPPLY,{'sources':[{'id':'source-1','supplier':'Fixture supplier','model':'MODEL-009','url':'https://example.invalid/source','observed_at':'2026-10-01'}]})
        self.write(ASSETS,{'files':[{'file':'01_产品资产/02_成品素材/BQ009/shoe.png','products':['BQ009'],'roles':['商品主图']}]})
        self.write(CHANNEL,{'listings':[{'id':'1601','product_id':'BQ009','current_platform_fields':{'title':'Verified fixture title','status':'approved','at':'2026-10-31'}}]})
        self.app=server.Workbench(self.root,self.root/'runtime')
        self.app.gmail.translator=None
        self.clock=[1000]
        self.website=WebsiteInquiries(self.root,fetch=lambda:{'ok':True,'records':[
            {'reference':'BQ-REAL','company':'Fixture buyer','country':'US','requirements':'Need sample options','internalTest':False},
            {'reference':'BQ-TEST','company':'Internal only','internalTest':True}]},clock=lambda:self.clock[0],ttl=120)
        self.website.refresh(wait=True);self.app.business.website=self.website
        self.options={};self.processes=[]
        def spawn(command,**kwargs):
            process=Process(command,**self.options);self.processes.append(process);return process
        self.popen=patch('agent_jobs.subprocess.Popen',side_effect=spawn);self.popen.start()
        self.which=patch('agent_jobs.shutil.which',return_value='/fixture/codex');self.which.start()
        self.stop=patch.object(type(self.app.agent_jobs),'_stop',side_effect=lambda process:process.kill());self.stop.start()
        self.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);self.http.app=self.app
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()

    def write(self,path,data):
        target=self.root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')

    def tearDown(self):
        self.http.shutdown();self.thread.join(2);self.http.server_close()
        for process in self.processes:process.kill()
        for thread in self.app.agent_jobs.threads.values():thread.join(3)
        self.stop.stop();self.which.stop();self.popen.stop();self.app.db.close();self.temp.cleanup()

    def request(self,path,body=None,token=True):
        headers={};method='GET';payload=None
        if body is not None:
            method='POST';payload=json.dumps(body,ensure_ascii=False).encode();headers['Content-Type']='application/json'
            if token:headers['X-Workbench-Token']=self.app.token
        connection=http.client.HTTPConnection('127.0.0.1',self.http.server_port,timeout=5)
        try:
            connection.request(method,path,body=payload,headers=headers);response=connection.getresponse()
            return response.status,json.loads(response.read())
        finally:connection.close()

    def wait_job(self,job_id):
        deadline=time.monotonic()+4
        while time.monotonic()<deadline:
            status,job=self.request('/api/desk/job?'+urlencode({'id':job_id}));self.assertEqual(status,200)
            if job['status'] not in ('queued','running'):return job
            time.sleep(.01)
        self.fail('Fixture job did not finish')

    def test_object_search_detail_and_bootstrap_use_actual_business(self):
        status,index=self.request('/api/desk/objects?'+urlencode({'kind':'product','q':'Fixture supplier'}))
        self.assertEqual(status,200);self.assertEqual([row['id'] for row in index['objects']],['product:BQ009'])
        status,obj=self.request('/api/desk/object?'+urlencode({'id':'product:BQ009'}))
        self.assertEqual(status,200);self.assertEqual(obj['title'],'BQ009')
        self.assertTrue(obj['facts']);self.assertEqual(obj['assets'][0]['path'],'01_产品资产/02_成品素材/BQ009/shoe.png')
        self.assertIn('MODEL-009',obj['content'])
        status,bootstrap=self.request('/api/desk/bootstrap')
        self.assertEqual(status,200);self.assertEqual(bootstrap['csrf_token'],self.app.token)
        self.assertEqual(bootstrap['website_status']['state'],'ready')

    def test_alibaba_manual_inquiry_to_analysis_and_queue(self):
        from tests_customer_analysis import response
        original='Please send a quotation for 500 pairs of walking shoes.'
        status,created=self.request('/api/desk/inquiries',{'channel':'alibaba','company':'Fixture buyer','original_text':original})
        self.assertEqual(status,201);oid=created['object_id']
        status,profile=self.request('/api/desk/customer-profile?'+urlencode({'object_id':oid}))
        self.assertEqual(status,200);self.assertEqual(profile['original_text'],original)
        self.options={'content':json.dumps(response(),ensure_ascii=False)}
        status,job=self.request('/api/desk/jobs',{'object_id':oid,'mode':'customer_analysis','instruction':'翻译并整理回复要点'})
        self.assertEqual(status,201);done=self.wait_job(job['id']);self.assertEqual(done['status'],'completed')
        status,profile=self.request('/api/desk/customer-profile?'+urlencode({'object_id':oid}))
        self.assertEqual(status,200);self.assertEqual(profile['original_text'],original);self.assertTrue(profile['translation_zh'])
        status,queue=self.request('/api/desk/inquiry-queue?bucket=active');self.assertEqual(status,200);self.assertTrue(any(row['object_id']==oid for row in queue['items']))

    def test_buyer_search_and_libtv_routes(self):
        with patch('buyer_discovery.search_buyers',return_value={'status':'success','records':[{'company':'Sample buyer'}]}) as search:
            status,result=self.request('/api/desk/buyer-search?q=footwear');self.assertEqual(status,200);self.assertEqual(result['records'][0]['company'],'Sample buyer');search.assert_called_once_with('footwear')
        with patch.object(self.app.creation,'libtv_execute',return_value={'ok':True,'data':{}}) as execute:
            status,result=self.request('/api/desk/creation/libtv/nodes?project_id=canvas-id');self.assertEqual(status,200);execute.assert_called_with('nodes',project_id='canvas-id')
            status,result=self.request('/api/desk/creation/libtv/create',{'name':'项目','workspace_id':'0'});self.assertEqual(status,200);execute.assert_called_with('create_project',name='项目',workspace_id='0')
            status,result=self.request('/api/desk/creation/libtv/text',{'project_id':'canvas-id','title':'标题','content':'内容'});self.assertEqual(status,200);execute.assert_called_with('create_text_node',project_id='canvas-id',title='标题',content='内容',x=0,y=0)

    def test_customer_material_update_and_remove_keep_original(self):
        file=self.root/'04_客户开发/.local/网站询盘/BQ-REAL/工厂介绍.pdf'
        file.parent.mkdir(parents=True);file.write_bytes(b'%PDF material')
        path=file.relative_to(self.root).as_posix();oid='customer:website-BQ-REAL'
        status,created=self.request('/api/library',{'title':'工厂材料','path':path,'object_ids':[oid]})
        self.assertEqual(status,200)
        status,edited=self.request('/api/library/update',{'id':created['id'],'title':'工厂介绍','object_ids':[]})
        self.assertEqual(status,200);self.assertEqual(edited['title'],'工厂介绍');self.assertEqual(edited['object_ids'],[])
        status,removed=self.request('/api/library/remove',{'id':created['id']})
        self.assertEqual(status,200);self.assertEqual(removed['removed'],created['id']);self.assertEqual(file.read_bytes(),b'%PDF material')
        self.assertEqual(self.request('/api/library')[1]['items'],[])

    def test_company_lookup_uses_saved_candidate(self):
        entry=self.app.customer_workspace.create_discovery({'kind':'candidate','company':'Example Buyer'})
        with patch('company_lookup.lookup_company',return_value={'status':'candidates','candidates':[{'website':'https://buyer.example'}]}) as lookup:
            status,result=self.request('/api/desk/company-lookup',{'object_id':entry['object_id']})
            self.assertEqual(status,200);self.assertEqual(result['candidates'][0]['website'],'https://buyer.example')
            self.assertEqual(lookup.call_args.args[0]['id'],entry['object_id'])

    def test_gmail_reply_enters_customer_queue_and_dispatches_draft(self):
        oid='customer:website-BQ-REAL'
        self.app.customer_workspace.save_workflow(oid,{'state':'preparing'})
        self.app.customer_workspace.save_workflow(oid,{'state':'waiting_customer'})
        self.app.gmail._cache[oid]={'status':{'state':'connected'},'messages':[],
                                    'reply_pending':True,'next_action':'阅读客户新邮件'}
        status,queue=self.request('/api/desk/inquiry-queue?bucket=active')
        row=next(item for item in queue['items'] if item['object_id']==oid)
        self.assertEqual(status,200);self.assertTrue(row['workflow']['gmail_reply_pending'])
        self.assertEqual(row['workflow']['state_label'],'待处理')
        with patch.object(self.app.agent_jobs,'start',return_value={'id':'draft-job'}) as start:
            self.app._gmail_reply(oid,{'id':'message-1'},{})
            self.assertEqual(start.call_args.args[0],oid)
            self.assertIn('get_customer_gmail',start.call_args.args[1])

    def test_gmail_local_routes_connect_and_read_without_sending(self):
        oid='customer:website-BQ-REAL'
        with patch.object(self.app.gmail,'connect',return_value={'state':'connected'}) as connect, \
             patch.object(self.app.gmail,'start') as start, \
             patch.object(self.app.gmail,'customer',return_value={'status':{'state':'connected'},'messages':[]}) as customer:
            status,result=self.request('/api/desk/gmail/connect',{'account_email':'seller@example.test','app_password':'synthetic-password'})
            self.assertEqual(status,200);self.assertEqual(result['status']['state'],'connected');start.assert_called_once()
            status,result=self.request('/api/desk/gmail/sync',{'object_id':oid})
            self.assertEqual(status,200);customer.assert_called_with(oid,force=True)
            status,result=self.request('/api/desk/gmail/customer?'+urlencode({'object_id':oid}))
            self.assertEqual(status,200);customer.assert_called_with(oid)

    def test_google_oauth_start_and_callback_use_same_workbench_port(self):
        config={'installed':{'client_id':'fixture.apps.googleusercontent.com','client_secret':'fixture'}}
        with patch.object(self.app.gmail,'start_oauth',return_value='https://accounts.google.com/o/oauth2/v2/auth?state=fixture') as start, \
             patch.object(self.app.gmail,'finish_oauth') as finish:
            status,result=self.request('/api/desk/gmail/oauth/start',{'client_config':config})
            self.assertEqual(status,200);self.assertIn('accounts.google.com',result['authorization_url'])
            self.assertEqual(start.call_args.args[1],f'http://127.0.0.1:{self.http.server_port}/api/desk/gmail/oauth/callback')
            connection=http.client.HTTPConnection('127.0.0.1',self.http.server_port,timeout=5)
            try:
                connection.request('GET','/api/desk/gmail/oauth/callback?state=fixture&code=one-time-code')
                response=connection.getresponse();page=response.read().decode('utf8')
                self.assertEqual(response.status,200);self.assertIn('连接成功',page);self.assertNotIn('one-time-code',page)
            finally:connection.close()
            finish.assert_called_once_with('fixture','one-time-code')

    def test_google_oauth_reply_reaches_customer_queue_and_agent(self):
        from gmail_oauth import GmailOAuthMailbox, SCOPE
        import base64
        oid='customer:website-BQ-REAL';buyer='buyer@example.test';account='seller@example.test'
        self.website.fetch=lambda:{'ok':True,'records':[{'reference':'BQ-REAL','company':'Fixture buyer','email':buyer,'requirements':'Need footwear'}]}
        self.website.refresh(wait=True);self.app.customer_workspace.save_workflow(oid,{'state':'preparing'})
        self.app.customer_workspace.save_workflow(oid,{'state':'waiting_customer'})
        saved={}
        def request(url,*,token=None,form=None):
            if form and form.get('grant_type')=='authorization_code':return {'access_token':'fixture-access','refresh_token':'fixture-refresh','scope':SCOPE}
            if form and form.get('grant_type')=='refresh_token':return {'access_token':'fixture-access','expires_in':3600}
            if url.endswith('/profile'):return {'emailAddress':account}
            if '/messages?' in url:return {'messages':[{'id':'10'}]}
            if '/messages/10?' in url:
                return {'id':'10','threadId':'20','internalDate':'32503680000000','payload':{'mimeType':'text/plain',
                    'headers':[{'name':'From','value':buyer},{'name':'To','value':account},{'name':'Subject','value':'Reply'}],
                    'body':{'data':base64.urlsafe_b64encode(b'Please share details.').decode().rstrip('=')}}}
            raise AssertionError(url)
        self.app.gmail.oauth.request=request;self.app.gmail.oauth.saver=lambda email,value:saved.update({email:value})
        self.app.gmail.oauth_mailbox_factory=lambda email:GmailOAuthMailbox(email,request=request,reader=lambda _:saved[email])
        config={'installed':{'client_id':'fixture.apps.googleusercontent.com','client_secret':'fixture'}}
        with patch.object(self.app.gmail,'start'),patch.object(self.app.agent_jobs,'start',return_value={'id':'draft-job'}) as start:
            status,result=self.request('/api/desk/gmail/oauth/start',{'client_config':config})
            state=parse_qs(urlsplit(result['authorization_url']).query)['state'][0]
            connection=http.client.HTTPConnection('127.0.0.1',self.http.server_port,timeout=5)
            try:
                connection.request('GET','/api/desk/gmail/oauth/callback?'+urlencode({'state':state,'code':'fixture-code'}))
                response=connection.getresponse();response.read();self.assertEqual(response.status,200)
            finally:connection.close()
            self.app.gmail.scan_once();self.app.gmail.scan_once();self.assertEqual(start.call_count,1)
            status,mail=self.request('/api/desk/gmail/customer?'+urlencode({'object_id':oid}))
            self.assertEqual(mail['messages'][0]['body'],'Please share details.');self.assertTrue(mail['reply_pending'])
            status,queue=self.request('/api/desk/inquiry-queue?bucket=active')
            self.assertTrue(next(row for row in queue['items'] if row['object_id']==oid)['workflow']['gmail_reply_pending'])

    def test_new_gmail_reply_drives_queue_draft_and_acknowledgement(self):
        from gmail_sync import GmailService
        oid='customer:website-BQ-REAL';buyer='buyer@example.test';account='seller@example.test'
        self.website.fetch=lambda:{'ok':True,'records':[{'reference':'BQ-REAL','company':'Fixture buyer','email':buyer,'requirements':'Need footwear'}]}
        self.website.refresh(wait=True)
        self.app.customer_workspace.save_workflow(oid,{'state':'preparing'})
        self.app.customer_workspace.save_workflow(oid,{'state':'waiting_customer'})
        class Mailbox:
            def __init__(self):self.messages=[]
            def context(self,emails,force=False):
                return {'status':{'state':'ready','last_success_at':'2999-01-01T01:00:00+00:00','error':None},
                        'messages':list(self.messages),'reply_pending':True,'next_action':''}
        class Translator:
            def apply(self,account,messages,ids,retry=False):
                for message in messages:
                    if message['id'] in ids:message.update(translation_zh='请提供详细资料。',subject_zh='咨询',translation_state='ready')
        mail=Mailbox()
        self.app.gmail=GmailService(self.app,mailbox_factory=lambda account:mail,credential_tester=lambda *a:None,
                                    credential_saver=lambda *a:None,credential_checker=lambda *a:True,on_new_reply=self.app._gmail_reply,
                                    translator=Translator())
        self.app.gmail.connect(account,'synthetic-password')
        mail.messages=[{'id':'mail-1','direction':'inbound','sent_at':'2999-01-01T00:00:00+00:00','from':buyer,'to':account,'body':'Please share details.'}]
        with patch.object(self.app.agent_jobs,'start',return_value={'id':'draft-job'}) as start:
            self.app.gmail.scan_once();self.app.gmail.scan_once();self.assertEqual(start.call_count,1)
            status,result=self.request('/api/desk/gmail/customer?'+urlencode({'object_id':oid}))
            self.assertEqual(status,200);self.assertTrue(result['reply_pending']);self.assertEqual(result['messages'][0]['id'],'mail-1')
            self.assertEqual(result['messages'][0]['translation_zh'],'请提供详细资料。')
            from desk_mcp import DeskTools
            agent_mail=DeskTools(self.app.business,self.root,oid).call('get_customer_gmail',{})
            self.assertEqual(agent_mail['messages'][0]['body'],'Please share details.')
            status,queue=self.request('/api/desk/inquiry-queue?bucket=active')
            self.assertTrue(next(row for row in queue['items'] if row['object_id']==oid)['workflow']['gmail_reply_pending'])
            status,result=self.request('/api/desk/gmail/ack',{'object_id':oid})
            self.assertEqual(status,200);self.assertFalse(result['reply_pending'])
            self.app.gmail.scan_once();self.assertEqual(start.call_count,1)

    def test_channel_and_creation_pages_use_real_local_sources(self):
        project = self.root/'05_内容与视频/示例/PROJECT.md'
        project.parent.mkdir(parents=True, exist_ok=True)
        project.write_text('# 创作项目\n这里是当前记录', encoding='utf8')
        (self.root/'05_内容与视频/README.md').write_text('[项目](示例/PROJECT.md)', encoding='utf8')
        status, overview = self.request('/api/desk/channels')
        self.assertEqual(status, 200)
        self.assertEqual([x['id'] for x in overview['channels']], ['alibaba', 'website', 'douyin'])
        status, result = self.request('/api/desk/creation')
        self.assertEqual(status, 200)
        self.assertEqual(result['projects'][0]['title'], '创作项目')
        status, detail = self.request('/api/desk/creation/item?'+urlencode({'id': result['projects'][0]['id']}))
        self.assertEqual(status, 200)
        self.assertIn('这里是当前记录', detail['content'])
        oid = result['projects'][0]['id']
        status, initial = self.request('/api/desk/creation-canvas?'+urlencode({'object_id': oid}))
        self.assertEqual(status, 200)
        self.assertIn('创作项目', initial['canvas']['nodes'][0]['data']['title'])
        canvas = initial['canvas']; canvas['nodes'][0]['data']['title'] = '继续制作'
        canvas['nodes'].append({'id':'shot1','type':'creation','position':{'x':120,'y':280},'data':{'kind':'shot','title':'镜头一','duration':'3','visual':'鞋子侧面行走','copy':'轻松出行','status':'待制作','media_path':'05_内容与视频/示例/鞋图.png'}})
        status, saved = self.request('/api/desk/creation-canvas', canvas)
        self.assertEqual(status, 200)
        self.assertTrue(saved['canvas']['version'])
        self.assertEqual(self.request('/api/desk/creation-canvas', canvas)[0], 409)
        self.assertEqual(self.request('/api/desk/creation-canvas?'+urlencode({'object_id': oid}))[1]['canvas']['nodes'][0]['data']['title'], '继续制作')
        self.assertEqual(self.request('/api/desk/creation-canvas?'+urlencode({'object_id': oid}))[1]['canvas']['nodes'][1]['data']['visual'], '鞋子侧面行走')
        self.assertEqual(project.read_text(encoding='utf8'), '# 创作项目\n这里是当前记录')
        malformed = saved['canvas'].copy(); malformed['nodes'] = [None]
        self.assertEqual(self.request('/api/desk/creation-canvas', malformed)[0], 400)
        dangling = saved['canvas'].copy(); dangling['edges'] = [{'id':'e1','source':'missing','target':'brief'}]
        self.assertEqual(self.request('/api/desk/creation-canvas', dangling)[0], 400)

    def test_artifact_post_edit_and_fresh_get_read_file_content(self):
        status,saved=self.request('/api/desk/artifacts',{'object_id':'product:BQ009','title':'选款方案','content':'# 第一版\n核实来源'})
        self.assertEqual(status,200);original_path=self.root/saved['path'];self.assertEqual(original_path.read_text(encoding='utf8'),'# 第一版\n核实来源')
        status,edited=self.request('/api/desk/artifacts',{'id':saved['id'],'object_id':'product:BQ009','title':'选款方案更新','content':'# 第二版\n仍是同一对象'})
        self.assertEqual(status,200);self.assertEqual(edited['id'],saved['id'])
        self.assertFalse(original_path.with_suffix('.prev.md').exists())
        status,refreshed=self.request('/api/desk/artifacts?'+urlencode({'object_id':'product:BQ009'}))
        self.assertEqual(status,200);self.assertEqual(len(refreshed['artifacts']),1)
        self.assertEqual(refreshed['artifacts'][0]['content'],'# 第二版\n仍是同一对象')
        self.assertEqual(self.request('/api/desk/artifacts',{'object_id':'product:BQ009','title':'Denied','content':'No'},token=False)[0],403)

    def test_website_source_filter_and_stale_failure_do_not_hide_local_objects(self):
        status,rows=self.request('/api/desk/objects?kind=customer')
        self.assertEqual(status,200);self.assertEqual([row['id'] for row in rows['objects']],['customer:website-BQ-REAL'])
        status,obj=self.request('/api/desk/object?'+urlencode({'id':'customer:website-BQ-REAL'}))
        self.assertEqual(status,200);self.assertIn('Need sample options',obj['content'])
        self.assertEqual(self.request('/api/desk/object?'+urlencode({'id':'customer:website-BQ-TEST'}))[0],400)
        observed=self.website.status()['observed_at'];self.clock[0]+=121
        self.website.fetch=lambda:(_ for _ in ()).throw(RuntimeError('PRIVATE_SOURCE_TOKEN'))
        self.website.refresh(wait=True)
        status,bootstrap=self.request('/api/desk/bootstrap')
        self.assertEqual(status,200);self.assertEqual(bootstrap['website_status']['state'],'error')
        self.assertTrue(bootstrap['website_status']['stale']);self.assertEqual(bootstrap['website_status']['observed_at'],observed)
        self.assertNotIn('PRIVATE_SOURCE_TOKEN',json.dumps(bootstrap))
        self.assertTrue(any(row['id']=='product:BQ009' for row in bootstrap['objects']))

    def test_job_completion_publishes_artifact_for_same_object_over_http(self):
        status,job=self.request('/api/desk/jobs',{'object_id':'product:BQ009','instruction':'整理本款真实选款依据'})
        self.assertEqual(status,201);done=self.wait_job(job['id']);self.assertEqual(done['status'],'completed')
        status,result=self.request('/api/desk/artifacts?'+urlencode({'object_id':'product:BQ009'}))
        self.assertEqual(status,200);self.assertEqual(len(result['artifacts']),1)
        artifact=result['artifacts'][0];self.assertEqual(artifact['id'],done['artifact_id'])
        self.assertEqual(artifact['object_id'],'product:BQ009');self.assertIn('可用草稿',artifact['content'])
        self.assertEqual((self.root/artifact['path']).read_text(encoding='utf8'),artifact['content'])
        self.assertIn('MODEL-009',self.processes[0].stdin.value)
        self.assertNotIn('PRIVATE',json.dumps(done))

    def test_failed_model_never_presents_output_file_as_saved_artifact(self):
        self.options={'code':1}
        status,job=self.request('/api/desk/jobs',{'object_id':'product:BQ009','instruction':'只测试失败处理'})
        self.assertEqual(status,201);done=self.wait_job(job['id'])
        self.assertEqual(done['status'],'failed');self.assertIsNone(done['artifact_id'])
        self.assertEqual(self.request('/api/desk/artifacts?object_id=product%3ABQ009')[1]['artifacts'],[])

if __name__=='__main__':unittest.main()
