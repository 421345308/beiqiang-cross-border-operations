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
from urllib.parse import urlencode
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

    def test_artifact_post_edit_and_fresh_get_read_file_content(self):
        status,saved=self.request('/api/desk/artifacts',{'object_id':'product:BQ009','title':'选款方案','content':'# 第一版\n核实来源'})
        self.assertEqual(status,200);original_path=self.root/saved['path'];self.assertEqual(original_path.read_text(encoding='utf8'),'# 第一版\n核实来源')
        status,edited=self.request('/api/desk/artifacts',{'id':saved['id'],'object_id':'product:BQ009','title':'选款方案更新','content':'# 第二版\n仍是同一对象'})
        self.assertEqual(status,200);self.assertEqual(edited['id'],saved['id'])
        self.assertEqual(original_path.with_suffix('.prev.md').read_text(encoding='utf8'),'# 第一版\n核实来源')
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
