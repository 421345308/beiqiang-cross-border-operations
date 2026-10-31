import io
import json
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent_jobs import AgentJobs, MODEL, child_environment
from desk_cli import invoke
from desk_mcp import DeskTools,dispatch,PRODUCTS,CHANNEL


class Business:
    def __init__(self):
        self.artifacts = []
        self.obj = {'id': 'product:shoe', 'kind': 'product', 'title': '真实鞋款', 'source': 'facts/shoe.md',
                    'content': '逐款证据', 'related': ['customer:buyer']}
        self.fail_save = False
        self.refreshes=[];self.website_state='ready'

    def refresh_website(self,wait=False):
        self.refreshes.append(wait);return {'state':self.website_state}

    def website_status(self):return {'state':self.website_state}

    def get_object(self, oid):
        if oid != self.obj['id']:
            raise ValueError('unknown')
        return self.obj.copy()

    def list_objects(self, kind='', q=''):
        return [self.obj.copy(), {'id': 'customer:buyer', 'kind': 'customer', 'title': '关联需求', 'source': 'buyer.md'},
                {'id': 'customer:unrelated', 'content': 'UNRELATED_PRIVATE_CONTENT'}]

    def save_artifact(self, oid, title, content, artifact_id=None):
        if self.fail_save:
            raise RuntimeError('private failure')
        row = {'id': artifact_id or 'artifact-1', 'object_id': oid, 'title': title, 'content': content,
               'path': 'result.md', 'updated_at': 'now'}
        self.artifacts.append(row)
        return row

    def list_artifacts(self, object_id=None):
        return [a for a in self.artifacts if object_id is None or a['object_id'] == object_id]


class Input:
    def __init__(self): self.value = ''; self.closed = False
    def write(self, value): self.value += value
    def close(self): self.closed = True


class Process:
    def __init__(self, command, *, code=0, content='# 真实成果\n\n有依据的可用草稿。', complete=True, failed=False, gate=None, reconnect=False, source_read=True):
        self.stdin = Input(); self.code = code; self.done = False; self.pid = 987654321
        self.gate = gate; self.stdout = self.Stream(self, complete, failed)
        self.reconnect = reconnect
        if content is not None:
            Path(command[command.index('-o') + 1]).write_text(content, encoding='utf8')
        if source_read:
            Path(command[command.index('-o')+1]).with_name('source-reads.jsonl').write_text(json.dumps({'tool':'get_object','success':True})+'\n'+json.dumps({'tool':'read_source','success':True,'path':'facts/shoe.md','returned':10,'role':'current-object-source'})+'\n',encoding='utf8')

    class Stream:
        def __init__(self, process, complete, failed): self.process=process; self.complete=complete; self.failed=failed
        def __iter__(self):
            if self.process.reconnect:
                yield json.dumps({'type':'error','message':'Reconnecting... 2/5 (request timed out)'})+'\n'
            yield json.dumps({'type':'item.started','item':{'type':'command_execution','command':'private-command'}})+'\n'
            if self.process.gate: self.process.gate.wait(3)
            yield 'unstructured diagnostic access_token=PRIVATE\n'
            yield json.dumps({'type':'item.completed','item':{'type':'command_execution','aggregated_output':'PRIVATE'}})+'\n'
            if self.failed: yield json.dumps({'type':'turn.failed','error':{'message':'PRIVATE'}})+'\n'
            if self.complete: yield json.dumps({'type':'turn.completed'})+'\n'
        def close(self): pass

    def poll(self): return self.code if self.done else None
    def wait(self, timeout=None): self.done=True; return self.code
    def kill(self):
        self.done=True; self.code=-1
        if self.gate: self.gate.set()


class AgentJobTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.app=SimpleNamespace(root=self.root,state=self.root/'.local',lock=threading.RLock(),
                                 db=sqlite3.connect(':memory:',check_same_thread=False),business=Business())
        self.jobs=AgentJobs(self.app);self.processes=[]
        self.options={}
        def spawn(command,**kwargs):
            self.command=command;self.kwargs=kwargs
            process=Process(command,**self.options);self.processes.append(process);return process
        self.popen=patch('agent_jobs.subprocess.Popen',side_effect=spawn);self.popen.start()
        self.which=patch('agent_jobs.shutil.which',return_value='/fake/codex');self.which.start()
        self.stop=patch.object(AgentJobs,'_stop',side_effect=lambda process:process.kill());self.stop.start()

    def tearDown(self):
        for process in self.processes: process.kill()
        for thread in list(self.jobs.threads.values()): thread.join(3)
        self.stop.stop();self.which.stop();self.popen.stop();self.app.db.close();self.tmp.cleanup()

    def wait(self, job):
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            current=self.jobs.get_job(job['id'])
            if current['status'] not in ('queued','running'):
                thread=self.jobs.threads.get(job['id'])
                if thread: thread.join(2)
                return current
            threading.Event().wait(.01)
        self.fail('Job did not terminate')

    def test_async_completed_markdown_saved_to_same_object(self):
        result=self.wait(self.jobs.start('product:shoe','整理选款资料'))
        self.assertEqual(result['status'],'completed');self.assertEqual(result['artifact_id'],'artifact-1')
        self.assertEqual(self.app.business.artifacts[0]['object_id'],'product:shoe')
        self.assertIn('可用草稿',self.app.business.artifacts[0]['content'])
        self.assertIn('completed',[e['type'] for e in result['events']])
        self.assertNotIn('PRIVATE',json.dumps(result))
        self.assertNotIn('private-command',json.dumps(result))

    def test_command_actual_help_flags_and_tools_not_disabled(self):
        self.wait(self.jobs.start('product:shoe','读取依据'))
        self.assertEqual(self.command[self.command.index('-m')+1],MODEL)
        self.assertEqual(self.command[self.command.index('-s')+1],'read-only')
        self.assertIn('--ignore-user-config',self.command)
        self.assertIn('multi_agent',self.command)
        self.assertNotIn('--output-schema',self.command)
        self.assertNotIn('shell',self.command)
        self.assertTrue(self.kwargs['text'])
        self.assertNotIn('UNRELATED_PRIVATE_CONTENT',self.processes[0].stdin.value)
        self.assertIn('buyer.md',self.processes[0].stdin.value)
        self.assertIn('逐款证据',self.processes[0].stdin.value)

    def test_failed_exit_never_saves_existing_output(self):
        self.options={'code':1}
        result=self.wait(self.jobs.start('product:shoe','整理'))
        self.assertEqual(result['status'],'failed');self.assertIsNone(result['artifact_id']);self.assertFalse(self.app.business.artifacts)

    def test_transient_reconnect_followed_by_completed_turn_saves_result(self):
        self.options={'reconnect':True}
        result=self.wait(self.jobs.start('product:shoe','整理'))
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['artifact_id'],'artifact-1')
        self.assertIn('reconnecting',[event['type'] for event in result['events']])

    def test_no_original_read_receipt_keeps_draft_as_needs_input(self):
        self.options={'source_read':False}
        result=self.wait(self.jobs.start('product:shoe','整理'))
        self.assertEqual(result['status'],'needs_input')
        self.assertEqual(result['artifact_id'],'artifact-1')
        self.assertIn('读取未完成',result['error'])

    def test_missing_empty_or_uncompleted_result_is_failure(self):
        for options in ({'content':None},{'content':'  '},{'complete':False},{'failed':True}):
            self.options=options
            self.assertEqual(self.wait(self.jobs.start('product:shoe','整理'))['status'],'failed')
        self.assertFalse(self.app.business.artifacts)

    def test_cli_unavailable_and_save_failure(self):
        with patch('agent_jobs.shutil.which',return_value=None):
            result=self.wait(self.jobs.start('product:shoe','整理'))
            self.assertEqual(result['status'],'failed');self.assertIn('未找到Codex CLI',result['error'])
        self.app.business.fail_save=True
        result=self.wait(self.jobs.start('product:shoe','整理'))
        self.assertEqual(result['status'],'failed');self.assertIn('保存成果失败',result['error'])

    def test_cancel_running_kills_process_no_artifact_and_no_late_completion(self):
        gate=threading.Event();self.options={'gate':gate}
        job=self.jobs.start('product:shoe','整理')
        deadline=time.monotonic()+2
        while not self.processes and time.monotonic()<deadline: threading.Event().wait(.01)
        self.assertEqual(self.jobs.cancel(job['id'])['status'],'cancelled')
        result=self.wait(job);self.assertEqual(result['status'],'cancelled');self.assertFalse(self.app.business.artifacts)
        self.assertEqual(self.jobs.cancel(job['id'])['status'],'cancelled')

    def test_queued_cancel_does_not_spawn(self):
        class HeldThread:
            def __init__(self,**kwargs): pass
            def start(self): pass
        with patch('agent_jobs.threading.Thread',HeldThread):
            job=self.jobs.start('product:shoe','整理')
        self.jobs.cancel(job['id']);self.jobs._work(job['id'],self.app.business.obj)
        self.jobs.threads.pop(job['id'],None)
        self.assertFalse(self.processes)

    def test_restart_marks_active_failed_preserves_terminal(self):
        result=self.wait(self.jobs.start('product:shoe','整理'))
        active={**result,'id':'interrupted-job','status':'running','artifact_id':None}
        self.jobs._save(active)
        other=AgentJobs(self.app)
        self.assertEqual(other.get_job(active['id'])['status'],'failed')
        self.assertEqual(other.get_job(result['id'])['status'],'completed')
        self.assertIn('重启',other.get_job(active['id'])['error'])

    def test_interrupted_running_job_does_not_publish_late_result(self):
        gate=threading.Event();self.options={'gate':gate}
        job=self.jobs.start('product:shoe','整理')
        deadline=time.monotonic()+2
        while not self.processes and time.monotonic()<deadline:threading.Event().wait(.01)
        other=AgentJobs(self.app)
        gate.set()
        result=self.wait(job)
        self.assertEqual(result['status'],'failed')
        self.assertFalse(self.app.business.artifacts)

    def test_cancel_during_process_creation_discards_result(self):
        def spawn(command,**kwargs):
            job=self.jobs.list_jobs()[0]
            self.jobs.cancel(job['id'])
            process=Process(command);self.processes.append(process);return process
        with patch('agent_jobs.subprocess.Popen',side_effect=spawn):
            result=self.wait(self.jobs.start('product:shoe','整理'))
        self.assertEqual(result['status'],'cancelled')
        self.assertFalse(self.app.business.artifacts)

    def test_prompt_and_network_do_not_hold_application_lock(self):
        available=[]
        original=self.jobs._prompt
        def prompt(*args):
            def check():
                ok=self.app.lock.acquire(timeout=.2);available.append(ok)
                if ok:self.app.lock.release()
            thread=threading.Thread(target=check);thread.start();thread.join()
            return original(*args)
        with patch.object(self.jobs,'_prompt',side_effect=prompt):
            self.wait(self.jobs.start('product:shoe','整理'))
        self.assertEqual(available,[True])

    def test_invalid_instruction_object_and_unknown_job(self):
        for instruction in ('',None,'a'*12001):
            with self.assertRaises(ValueError):self.jobs.start('product:shoe',instruction)
        with self.assertRaises(ValueError):self.jobs.start('unknown','整理')
        with self.assertRaises(ValueError):self.jobs.get_job('unknown')

    def test_desktop_cli_reuses_business_artifact_methods(self):
        business=self.app.business
        self.assertEqual(invoke(business,'objects','get',object_id='product:shoe')['id'],'product:shoe')
        self.assertTrue(invoke(business,'objects','list')['objects'])
        saved=invoke(business,'artifacts','save',object_id='product:shoe',title='选款',content='# 正文')
        self.assertEqual(invoke(business,'artifacts','list',object_id='product:shoe')['artifacts'][0]['id'],saved['id'])

    def test_private_diagnostics_retained_redacted_and_progress_has_read_type(self):
        job=self.wait(self.jobs.start('product:shoe','整理'))
        text=(self.app.state/'agent-jobs'/job['id']/'diagnostics.log').read_text(encoding='utf8')
        self.assertIn('unstructured diagnostic',text)
        self.assertNotIn('access_token=PRIVATE',text)
        self.assertIn('read',[e['type'] for e in job['events']])

    def test_cli_waits_only_when_website_source_is_needed(self):
        business=self.app.business
        invoke(business,'objects','list',kind='product')
        self.assertEqual(business.refreshes,[])
        invoke(business,'objects','list',kind='customer')
        self.assertEqual(business.refreshes,[True])
        business.website_state='error'
        with self.assertRaisesRegex(ValueError,'原来源暂不可读'):
            invoke(business,'artifacts','save',object_id='customer:website-real',title='回复',content='draft')
        self.assertFalse(business.artifacts)

    def test_child_proxy_uses_system_without_mutating_parent(self):
        with patch.dict('agent_jobs.os.environ',{'PATH':'cli'},clear=True), patch('agent_jobs.getproxies',return_value={'http':'http://127.0.0.1:7897','https':'http://127.0.0.1:7897'}):
            env=child_environment()
            self.assertEqual(env['HTTP_PROXY'],'http://127.0.0.1:7897')
            self.assertEqual(env['HTTPS_PROXY'],'http://127.0.0.1:7897')
            import os
            self.assertNotIn('HTTP_PROXY',os.environ)
            self.assertIn('localhost',env['NO_PROXY'].split(','))

    def test_explicit_proxy_and_no_proxy_exclusions_take_precedence(self):
        original={'HTTP_PROXY':'http://explicit:81','https_proxy':'http://explicit:82','no_proxy':'internal.example,localhost'}
        with patch('agent_jobs.os.environ',original), patch('agent_jobs.getproxies',return_value={'http':'system','https':'system'}):
            env=child_environment()
            self.assertEqual(env['HTTP_PROXY'],original['HTTP_PROXY'])
            self.assertEqual(env['https_proxy'],original['https_proxy'])
            self.assertNotIn('HTTPS_PROXY',env)
            self.assertEqual(env['no_proxy'],'internal.example,localhost,127.0.0.1,::1')

    def test_mcp_projection_raw_package_read_and_boundaries(self):
        file=self.root/PRODUCTS;file.parent.mkdir(parents=True)
        file.write_text(json.dumps({'products':[{'id':'other','notes':'OTHER_PRIVATE'},
            {'id':'shoe','raw_packages':['01_产品资产/原包/shoe'],'evidence':['facts/shoe.md']}]}),encoding='utf8')
        raw=self.root/'01_产品资产/原包/shoe';raw.mkdir(parents=True)
        (raw/'specs.txt').write_text('Exact shoe facts',encoding='utf8')
        (raw/'secret.json').write_text('PRIVATE',encoding='utf8')
        self.app.business.obj['source']=PRODUCTS
        audit=self.root/'read.jsonl';tools=DeskTools(self.app.business,self.root,'product:shoe',audit)
        reply=dispatch(tools,{'jsonrpc':'2.0','id':1,'method':'initialize','params':{}})
        self.assertIn('tools',reply['result']['capabilities'])
        tools.call('get_object',{})
        source=tools.read(PRODUCTS)
        self.assertEqual(json.loads(source['content'])['id'],'shoe')
        self.assertNotIn('OTHER_PRIVATE',source['content'])
        paths=[r['path'] for r in tools.sources()]
        self.assertIn('01_产品资产/原包/shoe/specs.txt',paths)
        self.assertNotIn('01_产品资产/原包/shoe/secret.json',paths)
        self.assertEqual(tools.read('01_产品资产/原包/shoe/specs.txt')['content'],'Exact shoe facts')
        for path in ('../outside.txt','03_独立站/03_网站源码/.env','other.md'):
            with self.assertRaises(ValueError):tools.read(path)
        events=[json.loads(line) for line in audit.read_text(encoding='utf8').splitlines()]
        self.assertTrue(any(e['tool']=='get_object' for e in events))
        self.assertTrue(any(e['tool']=='read_source' for e in events))

    def test_website_virtual_source_uses_id_not_display_label(self):
        self.app.business.obj.update(id='customer:website-REF',kind='customer',source='网站询盘 · REF',content='original inquiry')
        tools=DeskTools(self.app.business,self.root,'customer:website-REF')
        self.assertEqual(tools.read('website:inquiry:REF')['content'],'original inquiry')

    def test_sources_default_compact_history_search_and_current_projection(self):
        products=self.root/PRODUCTS;products.parent.mkdir(parents=True)
        products.write_text(json.dumps({'products':[{'id':'shoe','evidence':['history/old-'+str(i)+'.json' for i in range(70)]}]}),encoding='utf8')
        self.app.business.obj.update(source=PRODUCTS,content=json.dumps({'selected_evidence_paths':['selected/current.md']}))
        channel=self.root/CHANNEL;channel.parent.mkdir(parents=True)
        channel.write_text(json.dumps({'listings':[{'id':'123','product_id':'shoe','current_platform_fields':{'sizes':'36-45'},'catalog_fields':{'sizes':'35-45'}},
                                                {'id':'999','product_id':'unrelated','current_platform_fields':{'private':'other'}}]}),encoding='utf8')
        tools=DeskTools(self.app.business,self.root,'product:shoe')
        default=tools.sources()
        self.assertLessEqual(len(default),20)
        self.assertFalse(any(r['role']=='historical-evidence' for r in default))
        self.assertEqual(len(tools.sources(q='history')),20)
        self.assertNotIn('history/old-',tools.read(PRODUCTS)['content'])
        current=tools.read(CHANNEL)
        self.assertIn('36-45',current['content'])
        self.assertNotIn('35-45',current['content'])
        self.assertNotIn('unrelated',current['content'])
        self.assertIn('current platform',current['projection'])


if __name__=='__main__':unittest.main()
