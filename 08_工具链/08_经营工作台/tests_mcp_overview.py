"""Synthetic-only checks for the explicit overview MCP binding."""
import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from desk_mcp import DeskTools, LocalOverviewClient, OVERVIEW_OBJECT, TOOLS, WorkOverviewError, dispatch, main
from workspaces import WorkspaceConflict


class OverviewMcpTests(unittest.TestCase):
    def setUp(self):
        self.overview = {'tasks':[
            {'id':'local:demo','version':1,'priority':'normal','capabilities':{'adjust':True}},
            {'id':'cloud:demo','capabilities':{'adjust':False}},
            {'id':'reference:demo','reference_only':True}],
            'sources':{'cloud':{'state':'unavailable'}},'inbox':[]}
        self.workspace = SimpleNamespace(overview=Mock(return_value=self.overview))
        self.jobs = SimpleNamespace(adjust=Mock(return_value={'id':'demo','version':2}))
        self.business = SimpleNamespace(app=SimpleNamespace(task_workspace=self.workspace,agent_jobs=self.jobs))
        self.tools = DeskTools(self.business,'.',OVERVIEW_OBJECT)

    def names(self, tools):
        result=dispatch(tools,{'id':1,'method':'tools/list'})
        return {tool['name'] for tool in result['result']['tools']}

    def test_explicit_binding_and_existing_worker_restrictions(self):
        self.assertEqual(self.names(self.tools),{'get_work_overview','adjust_local_task'})
        ordinary=DeskTools(self.business,'.','product:DEMO')
        self.assertNotIn('get_work_overview',self.names(ordinary))
        for tools in (ordinary,DeskTools(self.business,'.',OVERVIEW_OBJECT,draft_only=True),
                      DeskTools(self.business,'.',OVERVIEW_OBJECT,research_only=True)):
            with self.assertRaises(ValueError):tools.call('get_work_overview',{})
        with self.assertRaises(ValueError):self.tools.call('read_object',{'object_id':'customer:demo'})

    def test_read_preserves_capabilities_reference_and_source_failures(self):
        self.assertEqual(self.tools.call('get_work_overview',{'filters':{'executor':'local'}}),self.overview)
        self.workspace.overview.assert_called_once_with(filters={'executor':'local'})
        for filters in ({'secret':'x'},[],{'priority':3}):
            with self.assertRaises(ValueError):self.tools.call('get_work_overview',{'filters':filters})

    def test_adjust_requires_local_id_version_and_supported_fields(self):
        value=self.tools.call('adjust_local_task',{'id':'local:demo','expected_version':1,'priority':'high','next_action':'Review synthetic result'})
        self.assertEqual(value['version'],2)
        self.jobs.adjust.assert_called_once_with('demo',expected_version=1,priority='high',next_action='Review synthetic result')
        for fields in ({'id':'cloud:demo'},{'id':'reference:demo'},{'id':'local:demo','expected_version':''},
                       {'id':'local:demo','instruction':'replace'},{'id':'local:demo','priority':'urgent'}):
            with self.assertRaises(ValueError):self.tools.call('adjust_local_task',{'expected_version':1,'priority':'high',**fields})

    def test_intent_fields_are_validated_forwarded_and_scoped(self):
        body={'id':'local:demo','expected_version':1,'current_goal':'完成合成目标',
              'effective_decisions':[{'text':'保留已验收能力','source':'合成决定'}],
              'intent_source':'合成负责人要求','intent_reason':'体现当前目标'}
        self.assertEqual(self.tools.call('adjust_local_task',body)['version'],2)
        self.jobs.adjust.assert_called_once_with('demo',expected_version=1,
            current_goal=body['current_goal'],effective_decisions=body['effective_decisions'],
            intent_source=body['intent_source'],intent_reason=body['intent_reason'])
        self.jobs.adjust.reset_mock()
        empty={**body,'effective_decisions':[]}
        self.tools.call('adjust_local_task',empty)
        self.assertEqual(self.jobs.adjust.call_args.kwargs['effective_decisions'],[])
        self.jobs.adjust.reset_mock()
        for task_id in ('cloud:demo','reference:demo'):
            with self.subTest(id=task_id),self.assertRaises(ValueError):
                self.tools.call('adjust_local_task',{**body,'id':task_id})
        with self.assertRaises(ValueError):
            DeskTools(self.business,'.',OVERVIEW_OBJECT,read_only=True).call('adjust_local_task',body)
        self.jobs.adjust.assert_not_called()
        schema=next(tool for tool in TOOLS if tool['name']=='adjust_local_task')['inputSchema']
        self.assertEqual(schema['properties']['current_goal']['maxLength'],4000)
        decisions=schema['properties']['effective_decisions']
        self.assertEqual(decisions['maxItems'],20)
        self.assertEqual(decisions['items']['required'],['text','source'])
        self.assertFalse(decisions['items']['additionalProperties'])
        self.assertEqual(schema['properties']['intent_source']['maxLength'],500)
        self.assertEqual(schema['properties']['intent_reason']['maxLength'],1000)

    def test_invalid_intent_payloads_never_call_local_service(self):
        base={'id':'local:demo','expected_version':1,'intent_source':'测试来源','intent_reason':'测试理由'}
        invalid=[
            {'current_goal':''}, {'current_goal':'  '}, {'current_goal':'x'*4001}, {'current_goal':None},
            {'effective_decisions':None}, {'effective_decisions':'not a list'},
            {'effective_decisions':[{'text':'x'}]}, {'effective_decisions':[{'text':'x','source':' '}]},
            {'effective_decisions':[{'text':'x','source':'s','unexpected':'field'}]},
            {'effective_decisions':[{'text':'x'*501,'source':'s'}]},
            {'effective_decisions':[{'text':'x','source':'s'}]*21},
            {'effective_decisions':[{'text':'x'*500,'source':'s'*500}]*7},
            {'current_goal':'x','intent_source':''}, {'current_goal':'x','intent_reason':' '*5},
            {'current_goal':'x','intent_source':'s'*501}, {'current_goal':'x','intent_reason':'r'*1001},
        ]
        for extra in invalid:
            with self.subTest(extra=str(extra)[:100]),self.assertRaises(ValueError):
                self.tools.call('adjust_local_task',{**base,**extra})
        for omitted in ('intent_source','intent_reason'):
            payload={**base,'current_goal':'x'};payload.pop(omitted)
            with self.subTest(omitted=omitted),self.assertRaises(ValueError):
                self.tools.call('adjust_local_task',payload)
        with self.assertRaises(ValueError):self.tools.call('adjust_local_task',base)
        self.jobs.adjust.assert_not_called()

    def test_mcp_to_isolated_http_persists_intent_and_rejects_stale_version(self):
        from tests_desk_http import DeskHTTPTests
        fixture=DeskHTTPTests();fixture.setUp()
        try:
            job=fixture.app.agent_jobs.start('product:BQ009','旧合成目标',defer=True)
            tools=DeskTools(None,fixture.root,OVERVIEW_OBJECT)
            origin='http://127.0.0.1:'+str(fixture.http.server_port)
            request={'id':'local:'+job['id'],'expected_version':job['version'],
                     'current_goal':'新合成目标','effective_decisions':[{'text':'不覆盖原件','source':'合成决定'}],
                     'intent_source':'合成负责人要求','intent_reason':'目标已更新'}
            with patch.object(LocalOverviewClient,'origin',origin):
                updated=tools.call('adjust_local_task',request)
                self.assertEqual(updated['intent']['goal'],'新合成目标')
                self.assertEqual(updated['intent']['decisions'],request['effective_decisions'])
                with self.assertRaises(WorkspaceConflict):tools.call('adjust_local_task',request)
            self.assertEqual(fixture.app.agent_jobs.get_job(job['id'])['intent']['goal'],'新合成目标')
            self.assertEqual(len(fixture.processes),0)
        finally:
            fixture.tearDown()

    def test_read_only_and_conflict_are_not_reported_as_success(self):
        readonly=DeskTools(self.business,'.',OVERVIEW_OBJECT,read_only=True)
        self.assertEqual(self.names(readonly),{'get_work_overview'})
        with self.assertRaises(ValueError):readonly.call('adjust_local_task',{'id':'local:demo','expected_version':1,'priority':'high'})
        self.jobs.adjust.side_effect=WorkspaceConflict('synthetic conflict')
        result=dispatch(self.tools,{'id':2,'method':'tools/call','params':{'name':'adjust_local_task','arguments':{'id':'local:demo','expected_version':1,'priority':'high'}}})['result']
        self.assertTrue(result['isError'])
        self.assertEqual(json.loads(result['content'][0]['text'])['code'],'version_conflict')

    def test_historical_zero_version_is_valid_but_negative_and_boolean_are_not(self):
        self.tools.call('adjust_local_task',{'id':'local:demo','expected_version':0,'priority':'high'})
        self.jobs.adjust.assert_called_once_with('demo',expected_version=0,priority='high')
        schema=next(tool for tool in TOOLS if tool['name']=='adjust_local_task')['inputSchema']
        self.assertEqual(schema['properties']['expected_version']['minimum'],0)
        for version in (-1,True,'0'):
            with self.assertRaises(ValueError):
                self.tools.call('adjust_local_task',{'id':'local:demo','expected_version':version,'priority':'high'})

    def test_overview_stdio_does_not_open_business_or_initialize_services(self):
        source=io.StringIO(json.dumps({'id':1,'method':'tools/call','params':{'name':'get_work_overview'}})+'\n')
        target=io.StringIO()
        with patch('sys.argv',['desk_mcp.py','--root','.','--state','unused-synthetic-state','--object-id',OVERVIEW_OBJECT]), \
             patch('sys.stdin',source),patch('sys.stdout',target), \
             patch('desk_cli.open_business',side_effect=AssertionError('must not initialize')) as opened, \
             patch.object(LocalOverviewClient,'overview',return_value=self.overview) as read:
            main()
        opened.assert_not_called()
        read.assert_called_once_with({})
        self.assertFalse(json.loads(target.getvalue())['result']['isError'])

    def test_stdio_app_without_task_services_uses_existing_local_endpoint(self):
        tools=DeskTools(SimpleNamespace(app=SimpleNamespace()),'.',OVERVIEW_OBJECT)
        with patch.object(LocalOverviewClient,'overview',return_value=self.overview) as read:
            self.assertEqual(tools.call('get_work_overview',{}),self.overview)
            read.assert_called_once_with({})

    def test_local_http_auth_payload_and_no_mutation_retry(self):
        calls=[]
        def open_request(request,timeout):
            calls.append(request)
            if request.data is None:return io.BytesIO(b'{"csrf_token":"synthetic-test-token"}')
            self.assertEqual(request.get_header('X-workbench-token'),'synthetic-test-token')
            self.assertEqual(json.loads(request.data),{'id':'demo','expected_version':1,'priority':'high'})
            raise URLError('synthetic failure with private diagnostic')
        with patch('urllib.request.build_opener',return_value=SimpleNamespace(open=open_request)):
            with self.assertRaises(WorkOverviewError) as caught:
                LocalOverviewClient().adjust('demo',expected_version=1,priority='high')
        self.assertEqual(caught.exception.code,'outcome_unknown')
        self.assertNotIn('private diagnostic',str(caught.exception))
        self.assertEqual(len(calls),2)
        self.assertEqual(calls[0].full_url,'http://127.0.0.1:8766/api/desk/bootstrap')

    def test_http_conflict_and_source_unavailable_are_explicit(self):
        client=LocalOverviewClient()
        for error,expected in [(HTTPError(client.origin,409,'conflict',{},None),WorkspaceConflict),
                               (URLError('private path or token'),WorkOverviewError)]:
            with patch('urllib.request.build_opener',return_value=SimpleNamespace(open=Mock(side_effect=error))):
                with self.assertRaises(expected):client.overview({'priority':'high'})

    def test_non_conflict_post_http_errors_are_unknown_and_never_retried(self):
        client=LocalOverviewClient()
        for code in (302,400,403,404,500,503):
            opened=Mock(side_effect=HTTPError(client.origin,code,'private diagnostic',{},None))
            with self.subTest(code=code),patch('urllib.request.build_opener',return_value=SimpleNamespace(open=opened)):
                with self.assertRaises(WorkOverviewError) as caught:
                    client._request('/api/desk/job/adjust',{'id':'demo','expected_version':0,'priority':'high'},'synthetic-token')
                self.assertEqual(caught.exception.code,'outcome_unknown')
                self.assertNotIn('private diagnostic',str(caught.exception))
                opened.assert_called_once()


if __name__=='__main__':unittest.main()
