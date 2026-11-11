"""Synthetic-only checks for the explicit overview MCP binding."""
import io
import json
import unittest
from contextlib import ExitStack
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
        self.jobs = SimpleNamespace(adjust=Mock(return_value={'id':'demo','version':2}),
            assess_and_continue=Mock(return_value={'assessment':{'state':'continue'}}),
            continue_followup=Mock(return_value={'dispatch':{'state':'unknown','request_id':'request-1'}}),
            reconcile_followup=Mock(return_value={'dispatch':{'state':'unknown','request_id':'request-1'}}),
            link_conversation=Mock(return_value={'id':'p1','conversations':[{'control':'reference_only'}]}),
            bind_external_thread=Mock(return_value={'id':'p1'}),register_external_turn=Mock(return_value={'event':'recorded'}),
            assess_external_turn=Mock(return_value={'event':'assessed'}),
            prepare_external_dispatch=Mock(return_value={'event':{'state':'unknown'},'created':True}),
            observe_external_dispatch=Mock(return_value={'dispatch':{'state':'unknown'}}),
            resolve_external_failure=Mock(return_value={'event':'failure_reviewed'}))
        self.business = SimpleNamespace(app=SimpleNamespace(task_workspace=self.workspace,agent_jobs=self.jobs))
        self.tools = DeskTools(self.business,'.',OVERVIEW_OBJECT)

    def names(self, tools):
        result=dispatch(tools,{'id':1,'method':'tools/list'})
        return {tool['name'] for tool in result['result']['tools']}

    def test_explicit_binding_and_existing_worker_restrictions(self):
        self.assertEqual(self.names(self.tools),{'get_work_overview','adjust_local_task','assess_local_run','continue_local_run','reconcile_local_run',
            'link_local_conversation','bind_external_thread','register_external_turn','assess_external_turn',
            'prepare_external_dispatch','observe_external_dispatch','resolve_external_failure',
            'get_supervisor_status','configure_task_supervision','disable_task_supervision'})
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

    def test_external_tools_scope_validation_and_exact_caller_observations(self):
        from tests_desk_http import external_cases
        link={'id':'local:p1','expected_version':3,'provider':'codex',
              'conversation_id':'thread-1','provenance':'合成正式工具观测'}
        self.assertEqual(self.tools.call('link_local_conversation',link)['conversations'][0]['control'],'reference_only')
        self.jobs.link_conversation.assert_called_once_with('p1',**{k:v for k,v in link.items() if k!='id'})
        for route,name,raw in external_cases():
            body={**raw,'id':'local:p1'}
            self.tools.call(name,body)
            action=getattr(self.jobs,name)
            fields={k:v for k,v in body.items() if k not in ('id','event_id')}
            positional=('p1',body['event_id']) if 'event_id' in body else ('p1',)
            action.assert_called_once_with(*positional,**fields)
            spec=next(tool for tool in TOOLS if tool['name']==name)
            self.assertFalse(spec['annotations']['readOnlyHint'])
            self.assertFalse(spec['inputSchema']['additionalProperties'])
            readonly=DeskTools(self.business,'.',OVERVIEW_OBJECT,read_only=True)
            ordinary=DeskTools(self.business,'.','product:DEMO')
            for scoped in (readonly,ordinary):
                with self.assertRaises(ValueError):scoped.call(name,body)
            for bad in ({'id':'reference:p1'},{'id':'cloud:p1'},{'expected_version':True},{'extra':'malicious'}):
                with self.subTest(name=name,bad=bad),self.assertRaises(ValueError):self.tools.call(name,{**body,**bad})
            if name=='observe_external_dispatch':
                for bad in ({'observed_instruction_sha256':'A'*64},{'observed_instruction_sha256':None},
                            {'correlation':'text_similarity'},{'target_turn_id':None}):
                    with self.subTest(name=name,bad=bad),self.assertRaises(ValueError):self.tools.call(name,{**body,**bad})
            self.assertEqual(action.call_count,1)
        for bad in ({'provider':'chatgpt'},{'conversation_id':'../x'},{'provenance':'  '},{'extra':'x'}):
            with self.subTest(link=bad),self.assertRaises(ValueError):self.tools.call('link_local_conversation',{**link,**bad})
        with self.assertRaises(ValueError):DeskTools(self.business,'.',OVERVIEW_OBJECT,read_only=True).call('link_local_conversation',link)
        with self.assertRaises(ValueError):DeskTools(self.business,'.','product:DEMO').call('link_local_conversation',link)
        self.assertEqual(self.jobs.link_conversation.call_count,1)

    def test_external_tools_real_isolated_http_and_conflict(self):
        from tests_desk_http import DeskHTTPTests,external_cases
        fixture=DeskHTTPTests();fixture.setUp()
        link={'id':'local:p1','expected_version':3,'provider':'codex','conversation_id':'thread-1','provenance':'合成观测'}
        try:
            tools=DeskTools(None,fixture.root,OVERVIEW_OBJECT)
            cases=external_cases()
            with ExitStack() as stack:
                stack.enter_context(patch.object(LocalOverviewClient,'origin','http://127.0.0.1:'+str(fixture.http.server_port)))
                mocks={name:stack.enter_context(patch.object(fixture.app.agent_jobs,name,create=True,
                       return_value={'event':{'state':'unknown'},'created':True})) for _,name,_ in cases}
                linked=stack.enter_context(patch.object(fixture.app.agent_jobs,'link_conversation',create=True,
                       return_value={'id':'p1','conversations':[{'control':'reference_only'}]}))
                self.assertEqual(tools.call('link_local_conversation',link)['conversations'][0]['control'],'reference_only')
                linked.assert_called_once_with('p1',url=None,**{k:v for k,v in link.items() if k!='id'})
                for _,name,raw in cases:
                    body={**raw,'id':'local:p1'}
                    self.assertEqual(tools.call(name,body)['event']['state'],'unknown')
                    fields={k:v for k,v in body.items() if k not in ('id','event_id')}
                    positional=('p1',body['event_id']) if 'event_id' in body else ('p1',)
                    mocks[name].assert_called_once_with(*positional,**fields)
                name='assess_external_turn';raw=next(body for _,method,body in cases if method==name)
                mocks[name].side_effect=WorkspaceConflict('合成版本冲突')
                response=dispatch(tools,{'id':1,'method':'tools/call','params':{'name':name,
                    'arguments':{**raw,'id':'local:p1'}}})['result']
                self.assertTrue(response['isError'])
                self.assertEqual(json.loads(response['content'][0]['text'])['code'],'version_conflict')
                self.assertEqual(len(fixture.processes),0)
        finally:fixture.tearDown()

    def test_external_turn_mcp_accepts_official_in_progress_and_compatible_alias(self):
        from tests_desk_http import external_cases
        _,_,raw=next(item for item in external_cases() if item[0]=='external-turn')
        body={**raw,'id':'local:p1'}
        for state in ('inProgress','in_progress'):
            with self.subTest(state=state):
                self.tools.call('register_external_turn',{**body,'head_status':state})
                self.assertEqual(self.jobs.register_external_turn.call_args.kwargs['head_status'],state)
        self.assertEqual(self.jobs.register_external_turn.call_count,2)
        schema=next(tool for tool in TOOLS if tool['name']=='register_external_turn')['inputSchema']
        self.assertIn('inProgress',schema['properties']['head_status']['enum'])
        self.assertIn('in_progress',schema['properties']['head_status']['enum'])

    def test_external_turn_mcp_accepts_missing_running_head_time_only(self):
        from tests_desk_http import external_cases
        _,_,raw=next(item for item in external_cases() if item[0]=='external-turn')
        body={**raw,'id':'local:p1','head_started_at':None}
        for state in ('inProgress','in_progress','unknown'):
            with self.subTest(state=state):
                self.tools.call('register_external_turn',{**body,'head_status':state})
                self.assertIsNone(self.jobs.register_external_turn.call_args.kwargs['head_started_at'])
        for change in ({'head_status':'completed'}, {'head_status':'failed'},
                       {'head_status':'cancelled'}, {'head_turn_id':body['turn_id']}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.tools.call('register_external_turn',{**body,**change})
        self.assertEqual(self.jobs.register_external_turn.call_count,3)
        schema=next(tool for tool in TOOLS if tool['name']=='register_external_turn')['inputSchema']
        self.assertEqual(schema['properties']['head_started_at']['anyOf'],
                         [{'type':'number','minimum':0},{'type':'null'}])

    def test_external_prepare_unknown_transport_is_not_replayed(self):
        from tests_desk_http import external_cases
        raw=next(body for _,name,body in external_cases() if name=='prepare_external_dispatch')
        requests=[]
        def open_request(request,timeout):
            requests.append(request)
            if request.data is None:return io.BytesIO(b'{"csrf_token":"synthetic-test-token"}')
            self.assertEqual(json.loads(request.data),raw)
            raise URLError('synthetic failure after request')
        with patch('urllib.request.build_opener',return_value=SimpleNamespace(open=open_request)):
            response=dispatch(DeskTools(None,'.',OVERVIEW_OBJECT),{'id':2,'method':'tools/call',
                'params':{'name':'prepare_external_dispatch','arguments':{**raw,'id':'local:p1'}}})['result']
        self.assertTrue(response['isError'])
        self.assertEqual(json.loads(response['content'][0]['text'])['code'],'outcome_unknown')
        self.assertEqual(len(requests),2)
        self.assertTrue(requests[1].full_url.endswith('/api/desk/job/external-prepare'))

    def test_run_assessment_and_followup_forward_exact_local_scope_and_versions(self):
        body={'id':'local:demo','attempt':2,'expected_version':3,'expected_intent_version':1,
              'disposition':'continue','goal_status':'not_met','capability_status':'unknown',
              'result_ref':'artifact:synthetic','gap':'尚未完成','next_action':'核对下一项',
              'evidence':{'source':'合成任务成果','observed_at':'2026-11-11T13:00:00Z','detail':'隔离测试'}}
        result=self.tools.call('assess_local_run',body)
        self.assertEqual(result['assessment']['state'],'continue')
        self.jobs.assess_and_continue.assert_called_once_with('demo',2,**{k:v for k,v in body.items() if k not in ('id','attempt')})
        dispatch_args={'id':'local:demo','attempt':2,'expected_version':3,'request_id':'request-1'}
        for name,method in (('continue_local_run',self.jobs.continue_followup),('reconcile_local_run',self.jobs.reconcile_followup)):
            with self.subTest(name=name):
                result=self.tools.call(name,dispatch_args)
                self.assertEqual(result['dispatch']['state'],'unknown')
                method.assert_called_once_with('demo',2,expected_version=3,request_id='request-1')
        for name in ('assess_local_run','continue_local_run','reconcile_local_run'):
            schema=next(tool for tool in TOOLS if tool['name']==name)
            self.assertFalse(schema['annotations']['readOnlyHint'])
            self.assertFalse(schema['inputSchema']['additionalProperties'])
            self.assertEqual(schema['inputSchema']['properties']['attempt']['minimum'],1)

    def test_run_operations_reject_invalid_or_read_only_without_writes(self):
        body={'id':'local:demo','attempt':2,'expected_version':3,'expected_intent_version':1,
              'disposition':'continue','goal_status':'not_met','capability_status':'unknown',
              'result_ref':'','gap':'尚未完成','next_action':'继续核对',
              'evidence':{'source':'合成来源','observed_at':'2026-11-11T13:00:00+00:00','detail':'隔离测试'}}
        invalid=[{'id':'cloud:demo'},{'id':'reference:demo'},{'id':'local:../demo'}, {'attempt':True},
                 {'attempt':0},{'expected_version':True},{'expected_intent_version':-1},
                 {'disposition':'completed'},{'goal_status':'passed'}, {'evidence':{}},
                 {'evidence':{'source':'x','observed_at':'2026-11-11T13:00:00','detail':'x'}},
                 {'evidence':{'source':'x','observed_at':'bad','detail':'x'}}, {'extra':'x'}]
        for extra in invalid:
            with self.subTest(extra=extra),self.assertRaises(ValueError):self.tools.call('assess_local_run',{**body,**extra})
        follow={'id':'local:demo','attempt':2,'expected_version':3,'request_id':'request-1'}
        for name in ('continue_local_run','reconcile_local_run'):
            for extra in ({'id':'cloud:demo'},{'attempt':True},{'request_id':''},{'request_id':'bad/id'},{'extra':'x'}):
                with self.subTest(name=name,extra=extra),self.assertRaises(ValueError):self.tools.call(name,{**follow,**extra})
        readonly=DeskTools(self.business,'.',OVERVIEW_OBJECT,read_only=True)
        for name,args in [('assess_local_run',body),('continue_local_run',follow),('reconcile_local_run',follow)]:
            with self.subTest(name=name),self.assertRaises(ValueError):readonly.call(name,args)
            ordinary=DeskTools(self.business,'.','product:DEMO')
            with self.assertRaises(ValueError):ordinary.call(name,args)
        self.jobs.assess_and_continue.assert_not_called();self.jobs.continue_followup.assert_not_called();self.jobs.reconcile_followup.assert_not_called()

    def test_run_operation_conflict_and_unknown_transport_never_replay(self):
        body={'id':'local:demo','attempt':2,'expected_version':3,'request_id':'request-1'}
        self.jobs.continue_followup.side_effect=WorkspaceConflict('合成版本冲突')
        response=dispatch(self.tools,{'id':1,'method':'tools/call','params':{'name':'continue_local_run','arguments':body}})['result']
        self.assertTrue(response['isError'])
        self.assertEqual(json.loads(response['content'][0]['text'])['code'],'version_conflict')
        self.jobs.continue_followup.assert_called_once()
        requests=[]
        def open_request(request,timeout):
            requests.append(request)
            if request.data is None:return io.BytesIO(b'{"csrf_token":"synthetic-test-token"}')
            self.assertEqual(json.loads(request.data),{'id':'demo','attempt':2,'expected_version':3,'request_id':'request-1'})
            raise URLError('synthetic failure after dispatch')
        tools=DeskTools(None,'.',OVERVIEW_OBJECT)
        with patch('urllib.request.build_opener',return_value=SimpleNamespace(open=open_request)):
            response=dispatch(tools,{'id':2,'method':'tools/call','params':{'name':'continue_local_run','arguments':body}})['result']
        self.assertTrue(response['isError'])
        self.assertEqual(json.loads(response['content'][0]['text'])['code'],'outcome_unknown')
        self.assertEqual(len(requests),2)
        self.assertTrue(requests[1].full_url.endswith('/api/desk/job/continue-followup'))

    def test_mcp_to_isolated_http_forwards_assessment_and_unknown_followup(self):
        from tests_desk_http import DeskHTTPTests
        fixture=DeskHTTPTests();fixture.setUp()
        body={'id':'local:demo','attempt':2,'expected_version':3,'expected_intent_version':1,
              'disposition':'continue','goal_status':'not_met','capability_status':'unknown',
              'result_ref':'artifact:synthetic','gap':'尚未完成','next_action':'核对下一项',
              'evidence':{'source':'合成任务成果','observed_at':'2026-11-11T13:00:00Z','detail':'隔离测试'}}
        follow={'id':'local:demo','attempt':2,'expected_version':4,'request_id':'request-1'}
        try:
            tools=DeskTools(None,fixture.root,OVERVIEW_OBJECT)
            origin='http://127.0.0.1:'+str(fixture.http.server_port)
            with patch.object(LocalOverviewClient,'origin',origin), \
                 patch.object(fixture.app.agent_jobs,'assess_and_continue',create=True,return_value={'assessment':{'state':'continue'}}) as assess, \
                 patch.object(fixture.app.agent_jobs,'continue_followup',create=True,return_value={'dispatch':{'state':'unknown'}}) as start, \
                 patch.object(fixture.app.agent_jobs,'reconcile_followup',create=True,return_value={'dispatch':{'state':'unknown'}}) as reconcile:
                self.assertEqual(tools.call('assess_local_run',body)['assessment']['state'],'continue')
                self.assertEqual(tools.call('continue_local_run',follow)['dispatch']['state'],'unknown')
                self.assertEqual(tools.call('reconcile_local_run',follow)['dispatch']['state'],'unknown')
                assess.assert_called_once_with('demo',2,**{k:v for k,v in body.items() if k not in ('id','attempt')})
                start.assert_called_once_with('demo',2,expected_version=4,request_id='request-1')
                reconcile.assert_called_once_with('demo',2,expected_version=4,request_id='request-1')
                self.assertEqual(len(fixture.processes),0)
        finally:
            fixture.tearDown()

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
        self.assertEqual(self.names(readonly),{'get_work_overview','get_supervisor_status'})
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
