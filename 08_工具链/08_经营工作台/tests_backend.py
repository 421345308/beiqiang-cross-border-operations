"""Run: python -X utf8 tests_backend.py. All mutations use temporary documents."""
import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import server

class BackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.state=self.root/'runtime'
        generator=self.root/'08_工具链/06_工作区维护/build_b2b_workbench.py';generator.parent.mkdir(parents=True)
        original=server.HERE.parent/'06_工作区维护/build_b2b_workbench.py'
        generator.write_bytes(original.read_bytes())
        # Original parser constants determine the three authoritative paths within this fixture.
        import importlib.util
        spec=importlib.util.spec_from_file_location('fixture_parser',generator);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        for index,p in enumerate(module.SOURCES):
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(('国际B2B具体要成为：**长期目标**\r\n**当前位置：A阶段**\r\n[材料](引用.md)\r\n## 工作台任务\r\n| 任务 | 状态 | 主办 | 当前结果 | 下一步 | 依赖/需你决定 | 成果与证据 |\r\n| --- | --- | --- | --- | --- | --- | --- |\r\n| 任务%d | 待开始 | Agent | 原结果 | 继续核验 | 无 | [材料](引用.md) |\r\n'%index).encode())
            (p.parent/'引用.md').write_text('只读材料',encoding='utf-8')
        self.app=server.Workbench(self.root,self.state);self.tasks=self.app.bootstrap()['tasks']
    def tearDown(self):
        for run in self.app.runs():
            if run['status'] in ('queued','running'):self.app.cancel(run['id'])
        self.app.db.close();self.tmp.cleanup()
    def queued(self,index=0):
        with patch.object(threading.Thread,'start'):
            return self.app.start(self.tasks[index]['id'],'核验原文')
    def proposal(self,run):
        result={'summary':'修订结果','changes':[{'path':run['source'],'before':'原结果','after':'核验完成','reason':'测试证据'}],'next_steps':['继续']}
        changes,diff=self.app.validate(run,result);run.update(status='awaiting_review',result=result,changes=changes,diff=diff);self.app.save(run);return run
    def test_live_sources_and_document_allowlist(self):
        self.assertEqual(len(self.tasks),3);self.assertEqual(self.app.bootstrap()['goals']['long_term'],'长期目标')
        rel=self.app.references(self.tasks[0]['source'])[0]['path'];self.assertEqual(self.app.document(rel)['content'],'只读材料')
        for rel in ['../auth.json','.codex/auth.json','AGENTS.md','00_总控台/../../outside.md']:
            with self.assertRaises(ValueError):self.app.document(rel)
    def test_explicit_local_evidence_is_readable_but_unlinked_files_are_not(self):
        source=self.app.path(self.tasks[0]['source']);private=source.parent/'.local/证据.md';private.parent.mkdir();private.write_text('受控本地证据',encoding='utf-8')
        with source.open('a',encoding='utf-8') as stream:stream.write('\n[本地材料](.local/证据.md)\n')
        rel=private.relative_to(self.root).as_posix();self.assertEqual(self.app.document(rel)['content'],'受控本地证据')
        other=private.with_name('未引用.md');other.write_text('不应公开读取',encoding='utf-8')
        with self.assertRaises(ValueError):self.app.document(other.relative_to(self.root).as_posix())
    def test_concurrency_limits_and_cancel_queued(self):
        one=self.queued()
        with self.assertRaises(server.Conflict):self.queued()
        two=self.queued(1)
        with self.assertRaises(server.Conflict):self.queued(2)
        self.assertEqual(self.app.cancel(one['id'])['status'],'cancelled')
        self.assertEqual(self.queued(2)['status'],'queued')
    def test_accept_exact_patch_preserves_crlf(self):
        run=self.proposal(self.queued());self.assertIn('+',run['diff']);self.app.accept(run['id'])
        data=self.app.path(run['source']).read_bytes();self.assertIn('核验完成'.encode(),data);self.assertIn(b'\r\n',data)
        self.assertEqual(self.app.get(run['id'])['status'],'accepted')
        with self.assertRaises(server.Conflict):self.app.accept(run['id'])
    def test_prompt_lf_replacement_matches_crlf_source(self):
        run=self.queued();source=self.app.path(run['source']);prompt_text=source.read_text(encoding='utf-8-sig')
        self.assertNotIn('\r',prompt_text)
        before='国际B2B具体要成为：**长期目标**\n**当前位置：A阶段**'
        self.assertIn(before,prompt_text)
        result={'summary':'更新阶段','changes':[{'path':run['source'],'before':before,'after':before.replace('A阶段','B阶段'),'reason':'测试'}],'next_steps':[]}
        changes,diff=self.app.validate(run,result);run.update(status='awaiting_review',result=result,changes=changes,diff=diff);self.app.save(run);self.app.accept(run['id'])
        raw=source.read_bytes();self.assertIn('**当前位置：B阶段**'.encode(),raw);self.assertEqual(raw.count(b'\n'),raw.count(b'\r\n'))
    def test_stale_hash_and_wrong_path_rejected(self):
        run=self.proposal(self.queued());p=self.app.path(run['source']);p.write_bytes(p.read_bytes()+b'\nnew facts')
        with self.assertRaises(server.Conflict):self.app.accept(run['id'])
        self.assertTrue(p.read_bytes().endswith(b'new facts'))
        other=self.queued(1);result={'summary':'x','changes':[{'path':run['source'],'before':'原结果','after':'x','reason':'x'}],'next_steps':[]}
        with self.assertRaises(ValueError):self.app.validate(other,result)
    def test_restart_marks_interrupted_and_persists_events(self):
        run=self.queued();run['events']=[{'type':'test'}];run['session_id']='session-test';self.app.save(run)
        other=server.Workbench(self.root,self.state)
        self.assertEqual(other.get(run['id'])['status'],'interrupted');self.assertEqual(other.get(run['id'])['events'],run['events']);other.db.close()
    def test_resume_uses_actual_session_and_read_only_cli(self):
        run=self.queued();run.update(status='interrupted',session_id='session-test');self.app.save(run)
        with patch.object(threading.Thread,'start'):resumed=self.app.start(run['task_id'],'继续核验',run['id'])
        command=self.app.command(resumed,True)
        self.assertEqual(command[1:6],['-s','read-only','-a','never','exec']);self.assertIn('resume',command);self.assertIn('session-test',command);self.assertIn('--ignore-user-config',command)
    def test_cli_event_result_flow(self):
        run=self.queued();result={'summary':'已核验无需修改','changes':[],'next_steps':['继续核验']}
        events=[{'type':'thread.started','thread_id':'session-fixture'},{'type':'item.completed','item':{'type':'agent_message','text':json.dumps(result)}},{'type':'turn.completed','usage':{'input_tokens':1}}]
        script='import sys,json;sys.stdin.read();print('+repr('\n'.join(json.dumps(e) for e in events))+')'
        with patch.object(self.app,'command',return_value=[sys.executable,'-c',script]):self.app.execute(run['id'],False)
        actual=self.app.get(run['id']);self.assertEqual(actual['status'],'awaiting_review');self.assertEqual(actual['session_id'],'session-fixture');self.assertEqual(actual['usage'],{'input_tokens':1})
    def test_cancel_owned_process(self):
        run=self.queued();script='import sys,time;sys.stdin.read();print("ready",flush=True);time.sleep(60)'
        with patch.object(self.app,'command',return_value=[sys.executable,'-c',script]):
            worker=threading.Thread(target=self.app.execute,args=(run['id'],False));worker.start()
            for _ in range(100):
                if run['id'] in self.app.processes:break
                time.sleep(.02)
            proc=self.app.processes[run['id']];self.app.cancel(run['id']);worker.join(5)
        self.assertFalse(worker.is_alive());self.assertIsNotNone(proc.poll());self.assertEqual(self.app.get(run['id'])['status'],'cancelled')
    def test_http_csrf_host_and_health(self):
        http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);http.app=self.app;worker=threading.Thread(target=http.serve_forever,daemon=True);worker.start()
        import http.client as hc
        def request(method,path,body=None,headers=None):
            conn=hc.HTTPConnection('127.0.0.1',http.server_port);conn.request(method,path,body,headers or {});resp=conn.getresponse();status=resp.status;data=json.loads(resp.read());conn.close();return status,data
        try:
            status,data=request('GET','/api/health');self.assertEqual(status,200);self.assertEqual(data['app'],'beiqiang-workbench')
            self.assertEqual(request('POST','/api/runs','{}',{'Content-Type':'application/json'})[0],403)
            self.assertEqual(request('GET','/api/bootstrap',headers={'Host':'evil.example'})[0],403)
            self.assertEqual(request('GET','/api/bootstrap',headers={'Origin':'https://evil.example'})[0],403)
            self.assertEqual(request('POST','/api/runs','{}',{'Content-Type':'text/plain','X-Workbench-Token':self.app.token})[0],400)
            self.assertEqual(request('GET','/api/document?path=../auth.json')[0],400)
        finally:http.shutdown();http.server_close();worker.join()

if __name__=='__main__':unittest.main(verbosity=2)
