"""Real supervisor through isolated loopback HTTP and MCP; no external actions."""
import io
import json
import sys
import threading
import time
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock, patch

import server
import tests_desk_http as fixture
from desk_mcp import DeskTools, LocalOverviewClient, OVERVIEW_OBJECT, dispatch


CASE = {'business_outcome':'synthetic business result',
        'current_bottleneck':'synthetic missing information',
        'intended_change':'synthetic next improvement',
        'stop_condition':'synthetic stop condition',
        'evidence_source':'synthetic artifact source'}


class SupervisorHTTPMCPTests(unittest.TestCase):
    tearDown = fixture.DeskHTTPTests.tearDown
    write = fixture.DeskHTTPTests.write
    request = fixture.DeskHTTPTests.request

    def setUp(self):
        fixture.DeskHTTPTests.setUp(self)
        self.assertNotEqual(self.http.server_port,8766)
        self.tools=DeskTools(None,self.root,OVERVIEW_OBJECT)
        origin=patch.object(LocalOverviewClient,'origin','http://127.0.0.1:'+str(self.http.server_port))
        origin.start();self.addCleanup(origin.stop)

    def mcp(self,name,args):
        result=dispatch(self.tools,{'jsonrpc':'2.0','id':1,'method':'tools/call',
            'params':{'name':name,'arguments':args}})['result']
        return result,json.loads(result['content'][0]['text'])

    def call(self,name,args):
        result,value=self.mcp(name,args)
        self.assertFalse(result['isError'],(name,value))
        return value

    def test_isolated_configuration_versions_states_and_disable(self):
        self.assertFalse(self.app.supervisor._running,'Workbench construction must not start a loop')
        status=self.call('get_supervisor_status',{})
        self.assertEqual(status['state'],'idle')
        self.assertEqual(status['scan_mode'],'caller_driven')
        self.assertEqual(status['planner'],'not_connected')
        self.assertEqual(status['notification'],'not_connected')
        self.assertEqual(status['scope'],['mail_draft'])
        self.assertEqual(status['supervised_tasks'],0)

        job=self.app.agent_jobs.start('product:BQ009','synthetic goal',mode='mail_draft',defer=True)
        local='local:'+job['id']
        config={'id':local,'expected_version':job['version'],
            'acceptance_criteria':{'kind':'artifact_contains','text':'synthetic marker'},
            'continuation_instruction':'synthetic read-only continuation',
            'authorization_ref':'synthetic explicit authorization','business_case':CASE,
            'prerequisite_state':'ready','value_state':'supported'}
        body={**config,'id':job['id']}
        try:denied=self.request('/api/desk/supervisor/configure',body,token=False)[0]
        except (ConnectionAbortedError,ConnectionResetError):denied=0
        self.assertIn(denied,(0,403))
        self.assertNotIn('supervision',self.app.agent_jobs.get_job(job['id']))

        configured=self.call('configure_task_supervision',config)
        self.assertEqual(configured['supervision']['business_case'],CASE)
        self.assertEqual(configured['supervision']['prerequisite_state'],'ready')
        self.assertEqual(configured['supervision']['value_state'],'supported')
        self.assertTrue(configured['supervision']['enabled'])
        self.assertEqual(configured['supervision']['max_auto_continuations'],1)
        stale,error=self.mcp('configure_task_supervision',config)
        self.assertTrue(stale['isError']);self.assertEqual(error['code'],'version_conflict')
        self.assertEqual(self.call('get_supervisor_status',{})['supervised_tasks'],1)

        for extra in ({'business_case':{}},
                      {'business_case':{**CASE,'stop_condition':' '}},
                      {'prerequisite_state':[]}, {'value_state':'guessed'},
                      {'acceptance_criteria':{'kind':'unsupported','text':'x'}},
                      {'expected_version':True}, {'extra':'unexpected'}):
            with self.subTest(extra=extra):
                result,value=self.mcp('configure_task_supervision',
                    {**config,'expected_version':configured['version'],**extra})
                self.assertTrue(result['isError']);self.assertEqual(value['code'],'invalid_input')
        self.assertEqual(self.app.agent_jobs.get_job(job['id'])['version'],configured['version'])

        waiting=self.call('configure_task_supervision',{**config,'expected_version':configured['version'],
            'prerequisite_state':'waiting_asset','value_state':'none'})
        self.assertEqual(waiting['supervision']['prerequisite_state'],'waiting_asset')
        self.assertEqual(waiting['supervision']['value_state'],'none')
        ready=self.call('configure_task_supervision',{**config,'expected_version':waiting['version']})
        disabled=self.call('disable_task_supervision',{'id':local,'expected_version':ready['version']})
        self.assertFalse(disabled['supervision']['enabled'])
        self.assertEqual(disabled['supervision']['business_case'],CASE)
        self.assertEqual(disabled['status'],'planned')
        stale,error=self.mcp('disable_task_supervision',{'id':local,'expected_version':ready['version']})
        self.assertTrue(stale['isError']);self.assertEqual(error['code'],'version_conflict')
        self.assertEqual(self.call('get_supervisor_status',{})['supervised_tasks'],0)
        self.assertFalse(self.app.supervisor._running)
        self.assertEqual(self.processes,[])

    def test_http_configuration_blocks_synthetic_followup_until_preconditions_hold(self):
        started=self.app.agent_jobs.start('product:BQ009','synthetic research',mode='mail_draft')
        deadline=time.monotonic()+6
        while time.monotonic()<deadline:
            job=self.app.agent_jobs.get_job(started['id'])
            if job.get('worker_finished') is True and '1' in job.get('completion_events',{}):break
            time.sleep(.01)
        else:self.fail('synthetic first attempt did not finish')
        self.assertEqual(job['status'],'completed')
        self.assertEqual(len(self.processes),1)
        config={'id':'local:'+job['id'],'expected_version':job['version'],
            'acceptance_criteria':{'kind':'artifact_contains','text':'synthetic missing marker'},
            'continuation_instruction':'synthetic continuation','authorization_ref':'synthetic authorization',
            'business_case':CASE,'prerequisite_state':'waiting_asset','value_state':'supported'}
        self.call('configure_task_supervision',config)
        report=self.app.supervisor.scan_once()
        self.assertEqual(report['blocked'],1)
        self.assertIn('waiting_asset',report['events'][0]['reason'])
        self.assertEqual(len(self.processes),1)
        current=self.app.agent_jobs.get_job(job['id'])
        self.call('configure_task_supervision',{**config,'expected_version':current['version'],
            'prerequisite_state':'ready','value_state':'none'})
        report=self.app.supervisor.scan_once()
        self.assertEqual(report['blocked'],1)
        self.assertIn('none',report['events'][0]['reason'])
        self.assertEqual(len(self.processes),1)
        current=self.app.agent_jobs.get_job(job['id'])
        ready=self.call('configure_task_supervision',{**config,'expected_version':current['version'],
            'prerequisite_state':'ready','value_state':'supported'})
        self.call('disable_task_supervision',{'id':'local:'+job['id'],'expected_version':ready['version']})
        self.assertEqual(self.app.supervisor.scan_once()['events'],[])
        self.assertEqual(len(self.processes),1)

    def test_supervisor_tools_require_scope_and_read_only_hides_writes(self):
        readonly=DeskTools(None,self.root,OVERVIEW_OBJECT,read_only=True)
        listed=dispatch(readonly,{'jsonrpc':'2.0','id':1,'method':'tools/list'})['result']['tools']
        names={item['name'] for item in listed}
        self.assertIn('get_supervisor_status',names)
        self.assertNotIn('configure_task_supervision',names)
        self.assertNotIn('disable_task_supervision',names)
        with self.assertRaises(ValueError):
            readonly.call('disable_task_supervision',{'id':'local:synthetic','expected_version':0})
        with self.assertRaises(ValueError):
            DeskTools(None,self.root,'product:BQ009').call('get_supervisor_status',{})
        self.assertEqual(self.processes,[])


class SupervisorMainLifecycleTests(unittest.TestCase):
    def test_main_starts_and_joins_loop_only_for_service_lifecycle(self):
        entered,stopped=threading.Event(),threading.Event()
        def supervise(stop):
            entered.set()
            if stop.wait(5):stopped.set()
        supervisor=SimpleNamespace(run_forever=supervise)
        app=SimpleNamespace(supervisor=supervisor,gmail=SimpleNamespace(stop=Mock()),
            search_console=SimpleNamespace(stop=Mock()),agent_jobs=SimpleNamespace(list_jobs=lambda:[]),runs=lambda:[])
        def serve():self.assertTrue(entered.wait(3),'main never started the supervisor loop')
        http=SimpleNamespace(server_port=54321,serve_forever=serve,server_close=Mock())
        with patch.object(server,'Workbench',return_value=app), \
             patch.object(server,'ThreadingHTTPServer',return_value=http), \
             patch.object(sys,'argv',['server.py','--root','.','--port','0']), \
             redirect_stdout(io.StringIO()):
            server.main()
        self.assertTrue(stopped.is_set())
        app.gmail.stop.assert_called_once();app.search_console.stop.assert_called_once()
        http.server_close.assert_called_once()

    def test_failed_stop_does_not_cancel_tasks_or_report_success(self):
        thread=Mock();thread.is_alive.return_value=True
        app=SimpleNamespace(supervisor=SimpleNamespace(run_forever=Mock()),gmail=SimpleNamespace(stop=Mock()),
            search_console=SimpleNamespace(stop=Mock()),agent_jobs=SimpleNamespace(list_jobs=Mock()),runs=Mock())
        http=SimpleNamespace(server_port=54321,serve_forever=Mock(),server_close=Mock())
        with patch.object(server,'Workbench',return_value=app), \
             patch.object(server,'ThreadingHTTPServer',return_value=http), \
             patch.object(server.threading,'Thread',return_value=thread), \
             patch.object(sys,'argv',['server.py','--root','.','--port','0']), \
             redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError):server.main()
        thread.join.assert_called_once_with(timeout=30)
        http.server_close.assert_called_once()
        app.agent_jobs.list_jobs.assert_not_called();app.runs.assert_not_called()


if __name__=='__main__':
    unittest.main()
