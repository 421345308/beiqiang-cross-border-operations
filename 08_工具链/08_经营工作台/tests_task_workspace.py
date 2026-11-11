import unittest
from unittest.mock import patch
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import quote
from task_workspace import TaskWorkspace

class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.objects=[{'id':'product:BQ01','title':'One','kind':'product'},
                      {'id':'product:BQ010','title':'Ten','kind':'product'}]
        self.jobs=[]
        self.cloud={'runs':[], 'observed_at':'2026-11-10T00:00:00Z', 'dispatch':{'ready':False}}
        def get_object(oid):
            return next(row for row in self.objects if row['id']==oid)
        self.app=SimpleNamespace(
            business=SimpleNamespace(list_objects=lambda:self.objects,get_object=get_object),
            agent_jobs=SimpleNamespace(list_jobs=lambda:self.jobs),
            cloud_review=SimpleNamespace(workspace_status=lambda:self.cloud))
        self.service=TaskWorkspace(self.app)

    def test_overview_exposes_current_task_intent_without_history_or_guessing(self):
        self.jobs.extend([
            {'id':'current','object_id':'product:BQ01','status':'completed', 'instruction':'旧委托',
             'next_action':'核对成果','intent':{'version':2,'goal':'现行目标','decisions_recorded':True,
                 'source':'最新负责人指令','decisions':[{'text':'有效决定','source':'依据'}],
                 'history':[{'goal':'已替代目标','decisions':[{'text':'已替代决定','source':'旧依据'}]}]}},
            {'id':'legacy','object_id':'product:BQ01','status':'completed',
             'instruction':'最后续接指令','initial_instruction':'原始任务目标'},
            {'id':'fallback','object_id':'product:BQ01','status':'completed','instruction':'遗留指令'},
            {'id':'null','object_id':'product:BQ01','status':'completed','intent':None},
            {'id':'invalid','object_id':'product:BQ01','status':'completed','intent':{'version':2}}])
        rows={row['id']:row for row in self.service.overview()['tasks']}
        current=rows['local:current']
        self.assertEqual((current['current_goal'],current['intent_version']),('现行目标',2))
        self.assertEqual(current['effective_decisions'],[{'text':'有效决定','source':'依据'}])
        self.assertNotIn('已替代决定',str(current))
        self.assertEqual(current['next_action'],'核对成果')
        self.assertEqual(rows['local:legacy']['current_goal'],'原始任务目标')
        self.assertFalse(rows['local:legacy']['decisions_recorded'])
        self.assertEqual(rows['local:fallback']['intent_source'],'legacy_instruction_fallback')
        self.assertEqual(rows['local:null']['intent_state'],'unavailable')
        self.assertEqual(rows['local:invalid']['intent_state'],'unavailable')
        self.assertIsNone(rows['local:invalid']['current_goal'])

    def test_adjustments_describe_actual_effect_and_allow_clearing_next_action(self):
        self.jobs.extend([
            {'id':'group','object_id':'product:BQ01','task_kind':'group','status':'planned'},
            {'id':'child','object_id':'product:BQ01','task_kind':'work','parent_job_id':'group',
             'status':'planned','next_action':'','priority':'high'},
            {'id':'solo','object_id':'product:BQ010','task_kind':'work','status':'planned'},
        ])
        self.app.agent_jobs.get_graph=lambda group_id:{'aggregate':{'status':'ready','total':1}}
        result=self.service.overview()
        rows={row['id']:row for row in result['tasks']}
        self.assertEqual(result['scheduling_effect'],'explicit_standalone_or_group_dispatch_only')
        self.assertEqual(rows['local:child']['capabilities']['scheduling_effect'],'explicit_group_dispatch')
        self.assertEqual(rows['local:child']['capabilities']['next_action_effect'],'next_attempt')
        self.assertEqual(rows['local:child']['next_action'],'')
        self.assertEqual(rows['local:solo']['capabilities']['scheduling_effect'],'explicit_standalone_dispatch')
        self.assertEqual(rows['local:group']['capabilities']['next_action_effect'],'none')

    @staticmethod
    def supervised_job(job_id='managed', **changes):
        config={'enabled':True,'policy':'mail_draft_read_only_v1',
                'acceptance_criteria':{'kind':'artifact_contains','text':'私有验收条件'},
                'continuation_instruction':'私有内部指令', 'authorization_ref':'私有授权来源',
                'max_auto_continuations':1, 'prerequisite_state':'ready','value_state':'supported',
                'business_case':{'business_outcome':'结果','current_bottleneck':'阻塞','intended_change':'变化',
                                 'stop_condition':'停止条件','evidence_source':'依据'}}
        return {'id':job_id,'object_id':'product:BQ01','status':'completed','mode':'mail_draft',
                'supervision':config,'supervision_revision':1,**changes}

    def test_supervisor_projection_limits_leases_to_explicitly_supervised_local_jobs(self):
        instant=datetime.now(timezone.utc);observed=instant.isoformat();expires=(instant+timedelta(seconds=50)).isoformat()
        self.jobs=[self.supervised_job(),{'id':'ordinary','object_id':'product:BQ01','status':'planned'}]
        self.app.desktop_snapshot=SimpleNamespace(read=lambda:{'state':'ok','observed_at':observed,'threads':[
            {'id':'external','hostId':'host1','status':'active'}]})
        status={'instance_id':'instance-1','state':'running','observed_at':observed,
                'heartbeat_at':(instant-timedelta(seconds=2)).isoformat(),'heartbeat_age_seconds':2,
                'lease_seconds':30,'active_leases':2,'supervised_tasks':1,'pending':1,'blocked':0,'unknown':0,
                'leases':[{'job_id':'managed','owner_id':'owner-1','expires_at':expires,'fence':'PRIVATE-TOKEN'},
                          {'job_id':'ordinary','owner_id':'owner-2','expires_at':expires}],
                'planner':'not_connected','notification':'not_connected','scan_mode':'caller_driven',
                'private_path':'C:\\PRIVATE-LOCATION','last_scan':{'token':'PRIVATE-SCAN'}}
        calls=[];self.app.supervisor=SimpleNamespace(status=lambda:(calls.append('read') or status))
        result=self.service.overview();rows={row['id']:row for row in result['tasks']}
        self.assertEqual(calls,['read']);self.assertEqual(result['supervisor']['state'],'running')
        self.assertEqual(result['supervisor']['active_leases'],1)
        self.assertEqual(result['supervisor']['leases'],[{'job_id':'managed','owner_id':'owner-1','expires_at':expires}])
        self.assertEqual(rows['local:managed']['supervision']['state'],'configured')
        self.assertEqual(rows['local:managed']['supervision']['leases'][0]['owner_id'],'owner-1')
        self.assertNotIn('supervision',rows['local:ordinary'])
        self.assertNotIn('supervision',rows['desktop:host1:external'])
        for secret in ('PRIVATE-TOKEN','PRIVATE-LOCATION','PRIVATE-SCAN','私有内部指令','私有授权来源','私有验收条件'):
            self.assertNotIn(secret,str(result))

    def test_supervisor_stale_or_unavailable_merges_into_existing_completion_inbox(self):
        instant=datetime.now(timezone.utc);job=self.supervised_job(review_events=[{
            'event_id':'run:1','attempt':1,'state':'ready_to_continue','dispatch':None,
            'dispatch_blocked':{'reason':'前置未满足','source':'supervisor'}}])
        self.jobs=[job];self.app.agent_jobs.completion_view=lambda item:item['review_events']
        status={'instance_id':'one','state':'running','observed_at':instant.isoformat(),
                'heartbeat_at':(instant-timedelta(seconds=70)).isoformat(),'heartbeat_age_seconds':70,
                'lease_seconds':30,'leases':[],'supervised_tasks':1,'pending':0,'blocked':1,'unknown':0,
                'planner':'not_connected','notification':'not_connected','scan_mode':'caller_driven'}
        self.app.supervisor=SimpleNamespace(status=lambda:status)
        result=self.service.overview();self.assertEqual(result['supervisor']['state'],'stale')
        self.assertEqual(len(result['inbox']),1);item=result['inbox'][0]
        self.assertEqual(item['state'],'dispatch_blocked');self.assertIn('前置未满足',item['judgment'])
        self.assertIn('心跳已过期',item['judgment']);self.assertEqual(item['severity'],'high')
        self.assertIn('心跳已过期',item['supervision_issue'])
        def unavailable():raise OSError('不要显示隐私路径')
        self.app.supervisor.status=unavailable
        result=self.service.overview();self.assertEqual(result['supervisor']['state'],'unavailable')
        self.assertIsNone(result['supervisor']['pending']);self.assertIsNone(result['supervisor']['active_leases'])
        self.assertEqual(len(result['inbox']),1);self.assertIn('状态暂不可读',result['inbox'][0]['judgment'])
        self.assertNotIn('不要显示隐私路径',str(result))

    def test_supervision_unknown_unsupported_and_nonready_are_actionable_without_fake_management(self):
        unsupported=self.supervised_job('unsupported');unsupported['supervision']['policy']='untrusted-other-policy'
        bad=self.supervised_job('bad');bad['supervision']['business_case']=None
        waiting=self.supervised_job('waiting');waiting['supervision']['prerequisite_state']='waiting_asset'
        disabled=self.supervised_job('disabled');disabled['supervision']['enabled']=False
        ordinary={'id':'ordinary','object_id':'product:BQ01','status':'completed'}
        self.jobs=[unsupported,bad,waiting,disabled,ordinary]
        result=self.service.overview();rows={row['job_id']:row for row in result['tasks']}
        self.assertEqual(rows['unsupported']['supervision']['state'],'unsupported')
        self.assertEqual(rows['bad']['supervision']['state'],'unknown')
        self.assertEqual(rows['waiting']['supervision']['state'],'configured')
        self.assertNotIn('supervision',rows['disabled']);self.assertNotIn('supervision',rows['ordinary'])
        self.assertEqual({item['task_id'] for item in result['inbox']}, {'local:unsupported','local:bad','local:waiting'})
        self.assertTrue(all(item['severity']=='high' for item in result['inbox']))
        self.assertTrue(all(item['action']['type']=='open_task' for item in result['inbox']))
        self.assertIsNone(result['supervisor']['pending'])

    def test_supervisor_bad_status_or_config_validator_cannot_break_overview(self):
        job=self.supervised_job();self.jobs=[job]
        self.app.supervisor=SimpleNamespace(status=lambda:{'state':'running','observed_at':datetime.now(timezone.utc).isoformat(),
            'heartbeat_at':datetime.now(timezone.utc).isoformat(),'heartbeat_age_seconds':10**400,
            'lease_seconds':30,'leases':[{'job_id':[],'owner_id':'owner'}], 'pending':0})
        result=self.service.overview();self.assertEqual(result['supervisor']['state'],'unknown')
        self.assertIsNone(result['supervisor']['pending']);self.assertEqual(len(result['tasks']),1)
        with patch('supervisor._criteria',side_effect=RuntimeError('temporary validator failure')):
            result=self.service.overview()
        self.assertEqual(result['tasks'][0]['supervision']['state'],'unknown')
        self.assertEqual(result['inbox'][0]['kind'],'supervision_issue')

    def test_explicit_workstream_references_use_individual_freshness_without_guessing(self):
        self.jobs.append({'id':'related','object_id':'product:BQ01','status':'completed',
            'conversations':[{'provider':'codex','conversation_id':'one','control':'reference_only',
                              'host_id':'durable','host_bound_at':'2026-11-11T10:00:00+00:00'}]})
        snapshot={'state':'unavailable','source':'complete snapshot','observed_at':'2026-11-11T11:00:00+00:00',
            'snapshot_observed_at':'2026-11-11T05:00:00+00:00','threads':[
                {'id':'one','hostId':'durable','title':'Same title','status':'active'},
                {'id':'two','hostId':'durable','title':'Same title','status':'active',
                 'individual_observation':{'state':'ok','observed_at':'2026-11-11T10:59:00+00:00',
                    'attempted_at':'2026-11-11T10:59:00+00:00','source':'official single read','age_seconds':4}},
                {'id':'three','hostId':'durable','title':'Other','status':'notLoaded',
                 'individual_observation':{'state':'ok','observed_at':'2026-11-11T10:59:00+00:00',
                    'attempted_at':'2026-11-11T10:59:00+00:00','source':'official single read','age_seconds':4}}],
            'workstream_links':[{'workstream':'tools','host_id':'durable','thread_id':'one'},
                {'workstream':'alibaba','host_id':'durable','thread_id':'two'},
                {'workstream':'website','host_id':'durable','thread_id':'three'}]}
        self.app.desktop_snapshot=SimpleNamespace(read=lambda:snapshot)
        with tempfile.TemporaryDirectory() as root:
            self.app.root=Path(root)
            result=self.service.overview()
        rows={row['id']:row for row in result['tasks']}
        self.assertEqual(rows['desktop:durable:one']['status'],'unknown')
        self.assertEqual(rows['desktop:durable:one']['source_status'],'active')
        self.assertEqual(rows['desktop:durable:one']['freshness']['state'],'unavailable')
        self.assertEqual(rows['desktop:durable:two']['status'],'active')
        self.assertEqual(rows['desktop:durable:two']['business_line'],'alibaba')
        self.assertEqual(rows['desktop:durable:three']['status'],'unknown')
        self.assertEqual(rows['local:related']['workstream_id'],'tools')
        self.assertEqual(result['workstreams'][0]['source']['state'],'unavailable')
        self.assertEqual([x['id'] for x in result['workstreams'][0]['related_jobs']],['local:related'])
        self.assertEqual(result['workstreams'][0]['related_jobs'][0]['status'],'completed')

    def test_exact_product_id_does_not_match_prefix(self):
        result=self.service.route('优化 BQ010 的内容')
        self.assertEqual(result['object_id'],'product:BQ010')
        self.assertEqual(result['action'],'create')
        self.assertEqual(self.jobs,[])

    def test_full_name_inside_command_is_candidate_until_confirmed(self):
        self.objects.append({'id':'creation:canvas','title':'贝强产品视频画布','kind':'creation'})
        result=self.service.route('继续贝强产品视频画布的下一步')
        self.assertEqual(result['action'],'choose')
        self.assertEqual([row['id'] for row in result['candidates']],['creation:canvas'])
        self.assertEqual(result['jobs'],[])
        self.assertEqual(self.jobs,[])
        confirmed=self.service.route('继续贝强产品视频画布的下一步','creation:canvas')
        self.assertEqual(confirmed['action'],'create')
        self.assertEqual(self.service.route('贝强产品视频画布')['action'],'create')

    def test_alias_and_current_model_supply_candidates_with_identifier_boundaries(self):
        self.objects[0].update(aliases=['旧鞋款名','AB01'],current_model='NEW001')
        for command in ('优化旧鞋款名图片','研究 AB01 的价格','检查 NEW001'):
            result=self.service.route(command)
            self.assertEqual(result['action'],'choose')
            self.assertEqual([row['id'] for row in result['candidates']],['product:BQ01'])
        for command in ('研究 AB010','研究 XAB01','研究 NEW0019','someone else'):
            self.assertEqual(self.service.route(command)['candidates'],[])
        self.assertEqual(self.service.route('优化 BQ01')['action'],'create')

    def test_ambiguous_alias_or_name_never_guesses_even_with_one_exact_id(self):
        self.objects[0].update(aliases=['共同名称'])
        self.objects[1].update(aliases=['共同名称'])
        result=self.service.route('继续共同名称')
        self.assertEqual(result['action'],'choose')
        self.assertEqual(len(result['candidates']),2)
        mixed=self.service.route('比较 BQ01 和 Ten')
        self.assertEqual(mixed['action'],'choose')
        self.assertEqual(len(mixed['candidates']),2)
        self.assertEqual(self.jobs,[])

    def test_ambiguity_and_missing_object_never_create_work(self):
        self.assertEqual(self.service.route('研究 BQ01 和 BQ010')['action'],'choose')
        self.assertEqual(self.service.route('提高销售')['action'],'choose')
        self.assertEqual(self.jobs,[])

    def test_existing_task_is_presented_without_replay(self):
        self.jobs=[{'id':'a','object_id':'product:BQ01','status':'failed'}]
        result=self.service.route('继续 BQ01')
        self.assertEqual(result['action'],'continue')
        self.assertEqual(result['jobs'][0]['status'],'failed')

    def test_unavailable_cloud_does_not_look_empty_or_completed(self):
        def fail(): raise ValueError('离线')
        self.app.cloud_review.workspace_status=fail
        self.jobs=[{'id':'a','object_id':'product:BQ01','status':'running'}]
        result=self.service.overview()
        self.assertEqual(result['sources']['cloud']['state'],'unavailable')
        self.assertEqual(result['tasks'][0]['status'],'running')

    def test_cloud_and_local_id_collision_preserves_origins(self):
        self.jobs=[{'id':'a','object_id':'product:BQ01','status':'completed'}]
        self.cloud['runs']=[{'id':'a','status':'awaiting_review','title':'Cloud','summary':'Review me'}]
        result=self.service.overview()
        self.assertEqual({row['id'] for row in result['tasks']},{'local:a','cloud:a'})
        self.assertEqual(result['inbox'][0]['action']['run_id'],'a')
        self.assertEqual(result['tasks'][1]['status'],'awaiting_review')
        cloud=next(row for row in result['tasks'] if row['origin']=='cloud')
        self.assertIsNone(cloud['priority'])
        self.assertEqual(cloud['priority_basis'],'unregistered')
        self.assertEqual(cloud['observed_at'],self.cloud['observed_at'])
        self.cloud.pop('observed_at')
        self.assertIsNone(next(row for row in self.service.overview()['tasks'] if row['origin']=='cloud')['observed_at'])

    def test_local_blocker_is_actionable_not_a_log(self):
        self.jobs=[{'id':'a','object_id':'product:BQ01','status':'needs_input','error':'需要最新资料'},
                   {'id':'b','object_id':'product:BQ010','status':'completed'}]
        inbox=self.service.overview()['inbox']
        self.assertEqual(len(inbox),1)
        self.assertEqual(inbox[0]['action']['task_id'],'local:a')
        self.assertEqual(inbox[0]['judgment'],'需要最新资料')

    def test_unclosed_completion_events_project_once_and_keep_evidence(self):
        review={'event_id':'run:1','attempt':1,'state':'awaiting_review','source':'local_run',
                'observed_at':'2026-11-11T10:00:00Z','notification':{'state':'not_connected'},
                'assessment':None}
        unknown={'event_id':'run:2','attempt':2,'state':'dispatch_unknown','source':'local_run',
                 'observed_at':'2026-11-11T11:00:00Z','notification':{'state':'not_connected'},
                 'assessment':{'gap':'尚未确认','next_action':'先核对派工回执'}}
        complete={'event_id':'run:3','attempt':3,'state':'verified_complete','source':'local_run'}
        self.jobs=[{'id':'a','object_id':'product:BQ01','status':'needs_input','error':'原任务错误',
                    'intent':{'version':1,'goal':'当前目标','source':'负责人','decisions_recorded':True,'decisions':[]},
                    'review_events':[review,dict(review),unknown,complete]}]
        self.app.agent_jobs.completion_view=lambda job:job['review_events']
        result=self.service.overview()
        self.assertEqual(len(result['inbox']),2)
        self.assertEqual({item['event_id'] for item in result['inbox']},{'run:1','run:2'})
        self.assertTrue(all(item['task_id']=='local:a' and item['action']['type']=='open_task' for item in result['inbox']))
        pending=next(item for item in result['inbox'] if item['event_id']=='run:2')
        self.assertEqual(pending['source'],'local_run')
        self.assertEqual(pending['observed_at'],'2026-11-11T11:00:00Z')
        self.assertEqual(pending['current_goal'],'当前目标')
        self.assertEqual(pending['next_action'],'先核对派工回执')
        self.assertEqual(pending['notification']['state'],'not_connected')
        self.assertIn('不要重复派发',pending['judgment'])
        task=next(row for row in result['tasks'] if row['id']=='local:a')
        self.assertEqual(task['completion_pending'],2)
        self.assertEqual(task['blocker'],'原任务错误')
        self.jobs[0].update(status='completed',review_events=[complete])
        self.assertEqual(self.service.overview()['inbox'],[])

    @staticmethod
    def external_event(turn, state='awaiting_review', *, current=True, ambiguous=False, **extra):
        return {'event_id':'external:'+turn, 'host_id':'host1', 'thread_id':'thread1', 'turn_id':turn,
                'source':'official-read-thread', 'observed_at':'2026-11-11T10:00:00Z',
                'completed_at':'2026-11-11T09:59:00Z', 'head_turn_id':turn, 'head_status':'idle',
                'current':current, 'order_ambiguous':ambiguous, 'state':state,
                'assessment':None, 'dispatch':None, **extra}

    def test_external_current_and_local_completion_coexist_without_duplicating_history(self):
        current=self.external_event('two','dispatch_unknown',dispatch={'state':'unknown','request_id':'req-1'},source_stale=True)
        old=self.external_event('one','historical',current=False)
        self.jobs=[{'id':'a','object_id':'product:BQ01','status':'completed','next_action':'核对原请求',
                    'review_events':[{'event_id':'run:1','attempt':1,'state':'awaiting_review'}],
                    'external_events':[current,dict(current),old]}]
        self.app.agent_jobs.completion_view=lambda job:job['review_events']
        self.app.agent_jobs.external_turns_view=lambda job:job['external_events']
        result=self.service.overview();items=result['inbox']
        self.assertEqual({item['kind'] for item in items},{'completion_review','external_turn_review'})
        item=next(item for item in items if item['kind']=='external_turn_review')
        self.assertEqual((item['state'],item['severity'],item['task_id']),('dispatch_unknown','high','local:a'))
        self.assertEqual(item['action']['job_id'],'a')
        self.assertEqual(item['observed_at'],'2026-11-11T10:00:00Z')
        self.assertEqual(item['notification']['state'],'not_connected')
        self.assertIn('不要重复派发',item['judgment'])
        self.assertIn('旧观察，需正式重新读取',item['judgment'])
        self.assertTrue(item['source_stale'])
        task=result['tasks'][0]
        self.assertEqual(task['external_turn_pending'],1)
        self.assertEqual(task['external_turn_state'],'dispatch_unknown')
        self.assertEqual(len(task['external_turns']),2)
        self.assertEqual(result['completion_capabilities']['external_turn_bridge'],'not_connected')

    def test_external_only_verified_current_without_dispatch_leaves_inbox(self):
        job={'id':'a','object_id':'product:BQ01','status':'completed','external_events':[]}
        self.jobs=[job];self.app.agent_jobs.external_turns_view=lambda item:item['external_events']
        done=self.external_event('one','verified_complete',assessment={'disposition':'verified_complete'})
        job['external_events']=[done]
        self.assertEqual(self.service.overview()['inbox'],[])
        for state in ('awaiting_review','review_required','ready_to_continue','needs_decision','blocked',
                      'unknown','dispatch_unknown','dispatch_accepted','dispatch_running','dispatch_completed','dispatch_failed'):
            with self.subTest(state=state):
                job['external_events']=[self.external_event('one',state)]
                item=self.service.overview()['inbox'][0]
                self.assertEqual((item['kind'],item['state']),('external_turn_review',state))
                if state=='dispatch_completed':self.assertIn('新回合并验收',item['judgment'])
        done['dispatch']={'state':'completed','request_id':'req-1'}
        job['external_events']=[done]
        self.assertEqual(self.service.overview()['inbox'][0]['state'],'dispatch_completed')
        done.update(dispatch=None,assessment=None)
        self.assertEqual(self.service.overview()['inbox'][0]['state'],'unknown')

    def test_external_ambiguous_order_is_actionable_and_bad_source_is_not_empty(self):
        job={'id':'a','object_id':'product:BQ01','status':'completed','external_events':[
            self.external_event('one','historical',current=False,ambiguous=True)]}
        self.jobs=[job];self.app.agent_jobs.external_turns_view=lambda item:item['external_events']
        result=self.service.overview();self.assertIn('顺序不明确',result['inbox'][0]['judgment'])
        self.assertEqual(result['tasks'][0]['external_turn_state'],'order_ambiguous')
        job['external_events']=[self.external_event('one'),self.external_event('two')]
        result=self.service.overview();self.assertEqual(len(result['inbox']),2)
        self.assertTrue(all('顺序不明确' in item['judgment'] for item in result['inbox']))
        job['external_events']=[self.external_event('one'),self.external_event('one',state='unknown')]
        result=self.service.overview()
        self.assertEqual(result['tasks'][0]['external_turns_state'],'unavailable')
        self.assertEqual(result['inbox'][0]['kind'],'external_turn_unavailable')
        self.assertIn('不可读',result['inbox'][0]['judgment'])
        job['external_events']=[{'event_id':'bad'}]
        self.assertEqual(self.service.overview()['inbox'][0]['kind'],'external_turn_unavailable')
        del self.app.agent_jobs.external_turns_view
        result=self.service.overview();self.assertEqual(result['tasks'][0]['external_turns_state'],'not_supported')
        self.assertEqual(result['inbox'],[])
        job['external_turn_events']={'retained':'evidence'}
        result=self.service.overview();self.assertEqual(result['tasks'][0]['external_turns_state'],'unavailable')
        self.assertEqual(result['inbox'][0]['kind'],'external_turn_unavailable')

    def test_external_unresolved_receipts_remain_visible_after_head_advances(self):
        job={'id':'a','object_id':'product:BQ01','status':'completed','external_events':[]}
        self.jobs=[job];self.app.agent_jobs.external_turns_view=lambda item:item['external_events']
        for state in ('dispatch_unknown','dispatch_accepted','dispatch_running','dispatch_completed'):
            with self.subTest(state=state):
                job['external_events']=[self.external_event('one',state,current=False)]
                item=self.service.overview()['inbox'][0]
                self.assertEqual((item['kind'],item['state']),('external_turn_review',state))
        job['external_events']=[self.external_event('one','historical',current=False)]
        self.assertEqual(self.service.overview()['inbox'],[])

    def test_external_failed_dispatch_requires_real_failure_review_even_after_new_head(self):
        receipt={'state':'failed','request_id':'req-1'}
        event=self.external_event('one','dispatch_failed',current=False,dispatch=receipt,
                                  assessment={'next_action':'旧的建议'})
        job={'id':'a','object_id':'product:BQ01','status':'completed','next_action':'当前目标的下一步',
             'external_events':[event]}
        self.jobs=[job];self.app.agent_jobs.external_turns_view=lambda item:item['external_events']
        item=self.service.overview()['inbox'][0]
        self.assertEqual((item['severity'],item['failure_review_state']),('high','pending'))
        self.assertIn('可能的副作用',item['judgment']);self.assertIn('不要重发',item['judgment'])
        receipt['failure_resolution']={}
        item=self.service.overview()['inbox'][0]
        self.assertEqual(item['failure_review_state'],'unavailable');self.assertIn('不可读',item['judgment'])
        receipt['failure_resolution']={'verification':'caller_attested','recorded_at':'2026-11-11T10:01:00Z',
            'evidence':{'source':'codex_app.read_thread','observed_at':'2026-11-11T10:00:00Z','detail':'已核对影响'}}
        self.assertEqual(self.service.overview()['inbox'],[])
        event['current']=True
        result=self.service.overview();item=result['inbox'][0]
        self.assertEqual((item['severity'],item['failure_review_state']),('normal','checked'))
        self.assertEqual(item['next_action'],'当前目标的下一步')
        self.assertIn('失败影响已由调用方登记核对，按当前目标选择下一步',item['judgment'])
        self.assertEqual(result['tasks'][0]['external_turns'][0]['dispatch']['state'],'failed')

    def test_changed_intent_never_presents_old_review_next_action_as_current(self):
        self.jobs=[{'id':'a','object_id':'product:BQ01','status':'completed','next_action':'核对新目标',
                    'review_events':[{'event_id':'run:1','attempt':1,'state':'intent_changed',
                      'assessment':{'gap':'旧目标缺口','next_action':'旧的执行建议'}}]}]
        self.app.agent_jobs.completion_view=lambda job:job['review_events']
        row=self.service.overview()['inbox'][0]
        self.assertEqual(row['next_action'],'核对新目标')
        self.assertNotIn('旧目标缺口',row['judgment'])
        self.assertIn('重新验收',row['judgment'])

    def test_next_action_uses_recorded_baseline_not_job_version_or_review_suggestion(self):
        event={'event_id':'run:1','attempt':1,'state':'ready_to_continue',
               'assessment':{'next_action':'验收时建议','task_next_action_at_review':'人工原安排',
                             'task_version_at_review':2}}
        job={'id':'a','object_id':'product:BQ01','status':'completed','version':17,
             'next_action':'人工原安排','review_events':[event]}
        self.jobs=[job];self.app.agent_jobs.completion_view=lambda item:item['review_events']
        result=self.service.overview()
        self.assertEqual(result['inbox'][0]['state'],'ready_to_continue')
        self.assertEqual(result['inbox'][0]['next_action'],'验收时建议')
        self.assertEqual(result['tasks'][0]['completion_events'][0]['next_action_comparison'],'unchanged')
        job['next_action']='人工更新安排'
        result=self.service.overview();item=result['inbox'][0]
        self.assertEqual(item['state'],'review_required')
        self.assertEqual(item['next_action'],'人工更新安排')
        self.assertIn('下一动作已变化',item['judgment'])
        self.assertEqual(item['severity'],'high')
        job['next_action']=''
        self.assertEqual(self.service.overview()['inbox'][0]['next_action'],'')
        event['state']='verified_complete'
        self.assertEqual(self.service.overview()['inbox'][0]['state'],'review_required')
        event['assessment'].pop('task_next_action_at_review')
        result=self.service.overview()
        self.assertEqual(result['inbox'],[])
        self.assertEqual(result['tasks'][0]['completion_events'][0]['next_action_comparison'],'unknown')

    def test_sent_receipt_and_target_event_are_not_reopened_by_task_next_action(self):
        previous={'event_id':'run:1','attempt':1,'state':'dispatch_completed',
                  'assessment':{'next_action':'原验收建议','task_next_action_at_review':'验收时安排'},
                  'dispatch':{'state':'completed','request_id':'req-1','target_job_id':'a','target_attempt':2}}
        current={'event_id':'run:2','attempt':2,'state':'awaiting_review'}
        self.jobs=[{'id':'a','object_id':'product:BQ01','status':'completed','version':50,
                    'next_action':'接续中登记的安排','review_events':[previous,current]}]
        self.app.agent_jobs.completion_view=lambda item:item['review_events']
        result=self.service.overview()
        self.assertEqual([row['event_id'] for row in result['inbox']],['run:2'])
        projected=next(e for e in result['tasks'][0]['completion_events'] if e['event_id']=='run:1')
        self.assertEqual(projected['state'],'dispatch_completed')
        self.assertEqual(projected['dispatch']['request_id'],'req-1')
        self.assertNotIn('next_action_review_required',projected)
        previous.update(state='dispatch_unknown',dispatch={'state':'unknown','request_id':'req-1'})
        self.jobs[0]['review_events']=[previous]
        item=self.service.overview()['inbox'][0]
        self.assertEqual(item['state'],'dispatch_unknown')
        self.assertIn('不要重复派发',item['judgment'])
        previous['intent_changed']=True
        self.assertIn('任务目标或决定已变化',self.service.overview()['inbox'][0]['judgment'])

    def test_uncertain_result_save_has_high_priority_even_with_completion_events(self):
        self.jobs=[{'id':'a','object_id':'product:BQ01','status':'needs_input','attempt':2,
                    'result_commit':{'state':'outcome_unknown','attempt':2},
                    'held_results':{'1':{'attempt':1,'reason':'result_outcome_unknown'},
                                    '2':{'attempt':2,'reason':'result_outcome_unknown'}},
                    'result_reconciliations':[{'attempt':1,'evidence':'旧记录仅记录检查依据'}],
                    'review_events':[{'event_id':'run:2','attempt':2,'state':'awaiting_review'}]}]
        self.app.agent_jobs.completion_view=lambda item:item['review_events']
        result=self.service.overview()
        unknown=[item for item in result['inbox'] if item['kind']=='result_outcome_unknown']
        self.assertEqual([item['attempt'] for item in unknown],[1,2])
        self.assertTrue(all(item['severity']=='high' and item['action']['task_id']=='local:a' for item in unknown))
        self.assertTrue(all('不要重做' in item['judgment'] for item in unknown))
        self.assertIn('保存结果不明',result['tasks'][0]['blocker'])
        self.assertTrue(any(item.get('event_id')=='run:2' for item in result['inbox']))
        self.jobs[0]['result_reconciliations'].append({'attempt':1,'outcome':'completed','evidence':'正式回执'})
        self.assertEqual([item['attempt'] for item in self.service.overview()['inbox']
                          if item['kind']=='result_outcome_unknown'],[2])
        self.jobs[0]['result_commit']['state']='saving'
        self.assertEqual([item['attempt'] for item in self.service.overview()['inbox']
                          if item['kind']=='result_outcome_unknown'],[2])
        self.jobs[0]['status']='running'
        self.jobs[0]['held_results'].pop('2')
        self.assertFalse(any(item['kind']=='result_outcome_unknown' for item in self.service.overview()['inbox']))
        self.jobs[0]['status']='completed'
        self.assertEqual([item['attempt'] for item in self.service.overview()['inbox']
                          if item['kind']=='result_outcome_unknown'],[2])
        self.jobs[0]['result_commit']={'state':'outcome_unknown'}
        self.assertIn('不可读',next(item for item in self.service.overview()['inbox']
                                   if item['kind']=='result_outcome_unknown')['judgment'])

    def test_predispatch_blocked_shows_reason_without_claiming_dispatch(self):
        self.jobs=[{'id':'a','object_id':'product:BQ01','status':'completed','review_events':[
            {'event_id':'run:1','state':'ready_to_continue','dispatch':None,
             'dispatch_blocked':{'request_id':'req-1','reason':'前置任务未完成','observed_at':'2026-11-11T10:00:00Z'}}]}]
        self.app.agent_jobs.completion_view=lambda job:job['review_events']
        result=self.service.overview();row=result['inbox'][0]
        self.assertEqual(row['state'],'dispatch_blocked')
        self.assertIn('尚未发出派工',row['judgment'])
        self.assertIn('前置任务未完成',row['judgment'])
        self.assertNotIn('已受理',row['judgment'])
        self.assertEqual(result['tasks'][0]['completion_state'],'dispatch_blocked')

    def test_completed_dispatch_uses_target_event_and_running_is_not_inbox(self):
        prior={'event_id':'run:1','attempt':1,'state':'dispatch_completed',
               'dispatch':{'state':'completed','target_job_id':'a','target_attempt':2}}
        target={'event_id':'run:2','attempt':2,'state':'awaiting_review'}
        self.jobs=[{'id':'a','object_id':'product:BQ01','status':'completed','review_events':[target,prior]}]
        self.app.agent_jobs.completion_view=lambda job:job['review_events']
        result=self.service.overview()
        self.assertEqual([row['event_id'] for row in result['inbox']],['run:2'])
        self.assertEqual(result['tasks'][0]['completion_pending'],2)
        self.assertEqual(result['tasks'][0]['completion_state'],'awaiting_review')
        prior['intent_changed']=True
        self.assertEqual({row['event_id'] for row in self.service.overview()['inbox']},{'run:1','run:2'})
        prior.update(intent_changed=False,state='dispatch_running',dispatch={'state':'running','target_job_id':'a','target_attempt':2})
        self.jobs[0]['review_events']=[prior]
        result=self.service.overview()
        self.assertEqual(result['inbox'],[])
        self.assertEqual(result['tasks'][0]['completion_state'],'dispatch_running')
        prior['intent_changed']=True
        self.assertIn('任务目标或决定已变化',self.service.overview()['inbox'][0]['judgment'])

    def test_dispatch_completion_without_matching_target_remains_unclosed(self):
        self.jobs=[{'id':'a','object_id':'product:BQ01','status':'completed','review_events':[
            {'event_id':'run:1','attempt':1,'state':'dispatch_completed',
             'dispatch':{'state':'completed','target_job_id':'a','target_attempt':2}}]}]
        self.app.agent_jobs.completion_view=lambda job:job['review_events']
        self.assertEqual(self.service.overview()['inbox'][0]['event_id'],'run:1')

    def test_conflicting_or_unreadable_completion_never_looks_closed(self):
        self.jobs=[{'id':'a','object_id':'product:BQ01','status':'completed','review_events':[
            {'event_id':'same','state':'verified_complete'}, {'event_id':'same','state':'awaiting_review'}]}]
        self.app.agent_jobs.completion_view=lambda job:job['review_events']
        result=self.service.overview()
        self.assertEqual(len(result['inbox']),1)
        self.assertEqual(result['inbox'][0]['state'],'unknown')
        self.assertIn('矛盾',result['inbox'][0]['judgment'])
        def failed(_job):raise ValueError('来源不可用')
        self.app.agent_jobs.completion_view=failed
        result=self.service.overview()
        self.assertEqual(result['inbox'][0]['kind'],'completion_unavailable')
        self.assertIn('不能据此认定已闭环',result['inbox'][0]['judgment'])
        def malformed(_job):raise AttributeError('source projection failed')
        self.app.agent_jobs.completion_view=malformed
        self.assertEqual(self.service.overview()['inbox'][0]['kind'],'completion_unavailable')

    def test_changed_intent_does_not_disappear_even_if_source_marks_verified(self):
        self.jobs=[{'id':'a','object_id':'product:BQ01','status':'completed','review_events':[
            {'event_id':'run:1','state':'verified_complete','intent_changed':True}]}]
        self.app.agent_jobs.completion_view=lambda job:job['review_events']
        self.assertEqual(self.service.overview()['inbox'][0]['state'],'review_required')
        self.jobs[0]['review_events']=[{'event_id':'run:1','state':'verified_complete','intent_version_known':False}]
        item=self.service.overview()['inbox'][0]
        self.assertEqual(item['state'],'review_required')
        self.assertIn('无法比较',item['judgment'])
        self.jobs[0]['review_events']=[{'event_id':'run:1','state':'verified_complete','dispatch':{'state':'unknown'}}]
        self.assertEqual(self.service.overview()['inbox'][0]['state'],'dispatch_unknown')

    def test_completion_record_error_is_visible_even_without_events(self):
        self.jobs=[{'id':'a','object_id':'product:BQ01','status':'completed','review_events':[],
                    'completion_error':{'state':'unavailable','observed_at':'2026-11-11T10:00:00Z'}}]
        self.app.agent_jobs.completion_view=lambda job:job['review_events']
        result=self.service.overview();item=result['inbox'][0]
        self.assertEqual(item['kind'],'completion_unavailable')
        self.assertEqual(item['task_id'],'local:a')
        self.assertEqual(item['observed_at'],'2026-11-11T10:00:00Z')
        self.assertEqual(item['notification']['state'],'not_connected')
        self.assertIn('不能据此认定已闭环',item['judgment'])
        self.assertIn('验收状态暂不可读',result['tasks'][0]['blocker'])
        self.assertEqual(result['completion_capabilities'],{'local_finished_events':'agent_jobs',
                         'external_turn_bridge':'not_connected','push_notification':'not_connected'})

    def test_external_completion_bridge_and_push_are_not_claimed_connected(self):
        result=self.service.overview()
        self.assertEqual(result['completion_capabilities']['local_finished_events'],'unavailable')
        self.assertEqual(result['completion_capabilities']['external_turn_bridge'],'not_connected')
        self.assertEqual(result['completion_capabilities']['push_notification'],'not_connected')

    def test_inbox_prioritizes_cloud_failure_over_normal_local_blocker(self):
        self.jobs=[{'id':'a','object_id':'product:BQ01','status':'needs_input'}]
        self.cloud['runs']=[{'id':'b','status':'interrupted'}]
        inbox=self.service.overview()['inbox']
        self.assertEqual([row['id'] for row in inbox],['cloud:b','local:a'])

    def test_invalid_instruction_is_rejected(self):
        for value in (None,'',{},'x'*12001):
            with self.assertRaises(ValueError): self.service.route(value)

    def test_business_inbox_reuses_customer_decisions_and_exposes_source_health(self):
        self.app.today=SimpleNamespace(snapshot=lambda:{
            'sources':{'customers':{'state':'ok'},'prospects':{'state':'ok'},
                       'gmail':{'state':'error'},'website':{'state':'ready','stale':True}},
            'groups':{'act':[
                {'id':'reply:1','kind':'customer_reply','object_id':'customer:one','severity':'high',
                 'action':{'type':'open_object','object_id':'customer:one'}},
                {'id':'website:2','kind':'customer_action','object_id':'customer:website-two'},
                {'id':'other:3','kind':'customer_action','object_id':'customer:other'},
                {'id':'mail:4','kind':'buyer_mail','action':{'type':'open_development'}}],
                'watch':[{'id':'wait','kind':'customer_waiting','object_id':'customer:website-three'}]}})
        result=self.service.overview()
        self.assertEqual({row['id'] for row in result['inbox']},{'reply:1','website:2','mail:4'})
        self.assertEqual(result['sources']['gmail']['state'],'error')
        self.assertTrue(result['sources']['website']['stale'])
        self.assertEqual(len(result['tasks']),5)
        self.assertTrue(all(not row['capabilities']['adjust'] for row in result['tasks']))
        self.assertTrue(all(row['priority_basis']=='business_severity' for row in result['tasks']))

    def test_business_source_failure_does_not_hide_tasks_or_claim_empty_sources(self):
        def fail():raise RuntimeError('fixture failure')
        self.app.today=SimpleNamespace(snapshot=fail)
        self.jobs=[{'id':'one','object_id':'product:BQ01','status':'failed'}]
        result=self.service.overview()
        self.assertEqual(result['tasks'][0]['id'],'local:one')
        self.assertEqual(result['sources']['customers']['state'],'unavailable')
        self.assertEqual(result['sources']['gmail']['state'],'unavailable')

    def test_business_line_uses_channel_kind_and_source_fields(self):
        self.objects.extend([{'id':'customer:website-new','title':'Website buyer','kind':'customer'},
            {'id':'channel:alibaba','title':'Channel','kind':'channel'},
            {'id':'creation:site','title':'Source based','kind':'creation','source':'03_独立站/project.md'}])
        self.jobs=[{'id':'web','object_id':'customer:website-new','status':'planned'},
            {'id':'channel','object_id':'channel:alibaba','status':'planned'},
            {'id':'source','object_id':'creation:site','status':'planned'}]
        self.cloud['runs']=[{'id':'cloud-source','status':'queued','source':'02_Alibaba运营/record.md'}]
        self.app.today=SimpleNamespace(snapshot=lambda:{'sources':{},'groups':{'act':[
            {'id':'catalog','kind':'catalog_status','title':'Catalog','severity':'normal'}]}})
        result=self.service.overview()
        self.assertEqual({row['id'] for row in self.service.overview({'business_line':'website'})['tasks']},
                         {'local:web','local:source'})
        self.assertEqual({row['id'] for row in self.service.overview({'business_line':'alibaba'})['tasks']},
                         {'local:channel','cloud:cloud-source','business:catalog'})
        self.assertEqual(next(row for row in result['tasks'] if row['id']=='cloud:cloud-source')['source'],
                         '02_Alibaba运营/record.md')

    def test_filters_only_offer_observed_values_and_source_time_is_distinct(self):
        self.jobs=[{'id':'x','object_id':'product:BQ01','status':'planned',
                    'updated_at':'2020-01-01T00:00:00Z', 'version':3,
                    'conversations':[{'control':'reference_only'}]}]
        result=self.service.overview({'business_line':'products','priority':'normal'})
        row=result['tasks'][0]
        self.assertEqual(row['freshness']['state'],'older')
        self.assertEqual(row['conversation_scope'],'reference_only')
        self.assertFalse(row['capabilities']['external_conversation_control'])
        self.assertEqual(result['filters']['executor'],[{'value':'codex_cli','label':'codex_cli'}])
        self.assertEqual(self.service.overview({'business_line':'domestic'})['tasks'],[])



class WorkspaceHTTPTests(unittest.TestCase):
    from tests_desk_http import DeskHTTPTests as Fixture
    setUp=Fixture.setUp
    tearDown=Fixture.tearDown
    request=Fixture.request
    write=Fixture.write

    def test_adjust_roundtrip_conflict_and_worker_snapshot_preservation(self):
        job=self.app.agent_jobs.start('product:BQ009','Plan',defer=True)
        stale=self.app.agent_jobs.get_job(job['id'])
        status,changed=self.request('/api/desk/job/adjust',{'id':job['id'],
            'expected_version':job['version'],'priority':'high','next_action':'Review source'})
        self.assertEqual(status,200)
        self.assertEqual(changed['status'],'planned')
        self.assertEqual(changed['instruction'],'Plan')
        self.assertEqual(changed['adjustments'][-1]['scheduling_effect'],'explicit_standalone_dispatch_only')
        status,_=self.request('/api/desk/job/adjust',{'id':job['id'],
            'expected_version':job['version'],'priority':'low'})
        self.assertEqual(status,409)
        self.app.agent_jobs._save(stale)
        saved=self.app.agent_jobs.get_job(job['id'])
        self.assertEqual(saved['priority'],'high')
        self.assertEqual(saved['next_action'],'Review source')
        self.assertEqual(saved['adjustments'],changed['adjustments'])
        for bad in ([],{},True,'urgent'):
            with self.assertRaises(ValueError):
                self.app.agent_jobs.adjust(job['id'],expected_version=saved['version'],priority=bad)
        self.assertEqual(saved['attempt'],0)

    def test_command_plan_and_context_survive_read(self):
        self.app.cloud_review=SimpleNamespace(workspace_status=lambda:{'runs':[], 'dispatch':{'ready':False}})
        status,route=self.request('/api/desk/command',{'instruction':'研究 BQ009'})
        self.assertEqual(status,200)
        self.assertEqual(route['object_id'],'product:BQ009')
        self.assertEqual(self.app.agent_jobs.list_jobs(),[])
        status,job=self.request('/api/desk/job/plan',{'object_id':'product:BQ009','instruction':'研究 BQ009','idempotency_key':'workspace-http'})
        self.assertEqual(status,201)
        status,context=self.request('/api/desk/task-context?id='+job['id'])
        self.assertEqual(status,200)
        self.assertEqual(context['job']['id'],job['id'])
        self.assertFalse(context['capabilities']['external_conversation_control'])
        status,index=self.request('/api/desk/task-overview')
        self.assertEqual(status,200)
        self.assertEqual(index['tasks'][0]['status'],'planned')
        self.assertEqual(index['sources']['cloud']['state'],'ok')

    def test_conversation_link_never_resumes_and_stale_version_rejected(self):
        job=self.app.agent_jobs.start('product:BQ009','研究',defer=True)
        body={'id':job['id'],'provider':'chatgpt','conversation_id':'fixture-chat',
              'provenance':'explicit_manual','expected_version':job['version'],
              'url':'https://chatgpt.com/c/fixture-chat'}
        status,linked=self.request('/api/desk/job/conversation',body)
        self.assertEqual(status,200)
        self.assertEqual(linked['status'],'planned')
        self.assertEqual(linked['conversations'][-1]['control'],'reference_only')
        self.assertEqual(self.request('/api/desk/job/conversation',body)[0],400)
        self.assertEqual(len(self.processes),0)

    def test_website_customer_reply_lifecycle_uses_same_object_and_task(self):
        oid='customer:website-BQ-REAL'
        record={'reference':'BQ-REAL','company':'Fixture buyer','email':'buyer@example.com',
                'requirements':'Synthetic inquiry','internalTest':False,'messages':[]}
        self.website.fetch=lambda:{'ok':True,'records':[record,{'reference':'INTERNAL','internalTest':True}]}
        self.website.refresh(wait=True)
        planned=self.app.agent_jobs.start(oid,'Review this inquiry',defer=True)
        def inbox():return self.request('/api/desk/task-overview')[1]
        def flow():return self.request('/api/desk/customer-workflow?object_id='+quote(oid))[1]
        def save(**fields):
            status,result=self.request('/api/desk/customer-workflow',{'object_id':oid,'revision':flow()['revision'],**fields})
            self.assertEqual(status,200);return result
        first=inbox()
        self.assertTrue(any(x.get('kind')=='customer_action' and x.get('object_id')==oid for x in first['inbox']))
        self.assertEqual(first['tasks'][0]['job_id'],planned['id'])
        save(state='preparing');save(state='waiting_customer')
        self.assertFalse(any(x.get('object_id')==oid for x in inbox()['inbox']))
        at=datetime.now(timezone.utc)
        def add_message(mid,minutes):
            record['messages'].append({'id':mid,'sender':'buyer','body':'Synthetic buyer reply',
                                       'sentAt':(at+timedelta(minutes=minutes)).isoformat()})
            self.website.refresh(wait=True)
        add_message('website-1',2)
        def replies():return [x for x in inbox()['inbox'] if x.get('kind')=='customer_reply' and x.get('object_id')==oid]
        self.assertEqual(len(replies()),1)
        self.assertEqual(replies()[0]['action']['object_id'],oid)
        self.assertEqual(len(replies()),1)
        save(state='waiting_customer')
        self.assertEqual(replies(),[])
        save(bucket='history')
        add_message('website-2',4)
        self.assertEqual(len(replies()),1)
        self.assertEqual(flow()['bucket'],'history')
        def unavailable():raise OSError('fixture offline')
        self.website.fetch=unavailable;self.website.refresh(wait=True)
        stale=inbox()
        self.assertTrue(stale['sources']['website']['stale'])
        self.assertNotEqual(stale['sources']['website']['state'],'ready')
        self.assertEqual(len([x for x in stale['inbox'] if x.get('kind')=='customer_reply' and x.get('object_id')==oid]),1)
        self.assertEqual(len(self.app.agent_jobs.list_jobs()),1)

    def test_gmail_reply_links_existing_customer_and_job_then_acknowledges(self):
        from tests_gmail_sync import ACCOUNT, BUYER, Mailbox, message
        oid='customer:website-BQ-REAL'
        record={'reference':'BQ-REAL','company':'Fixture buyer','email':BUYER,
                'requirements':'Synthetic inquiry','internalTest':False,'messages':[]}
        self.website.fetch=lambda:{'ok':True,'records':[record]};self.website.refresh(wait=True)
        def flow():return self.request('/api/desk/customer-workflow?object_id='+quote(oid))[1]
        def save(**fields):
            status,result=self.request('/api/desk/customer-workflow',{'object_id':oid,'revision':flow()['revision'],**fields})
            self.assertEqual(status,200);return result
        save(state='preparing');save(state='waiting_customer');save(bucket='history')
        mailbox=Mailbox();mail=self.app.gmail
        mail._account=ACCOUNT;mail._connected_at='2020-01-01T00:00:00Z';mail._mailbox=mailbox
        at=datetime.now(timezone.utc)
        mailbox.messages=[message('gmail-1',at=(at+timedelta(minutes=2)).isoformat())]
        self.assertTrue(mail.customer(oid)['reply_pending'])
        def replies():
            result=self.request('/api/desk/task-overview')[1]
            return [x for x in result['inbox'] if x.get('kind')=='customer_reply' and x.get('object_id')==oid]
        self.assertEqual(len(replies()),1)
        jobs=self.app.agent_jobs.list_jobs()
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0]['object_id'],oid)
        self.assertEqual(jobs[0]['source_event']['message_id'],'gmail-1')
        mail.customer(oid);self.assertEqual(len(self.app.agent_jobs.list_jobs()),1)
        self.assertEqual(self.request('/api/desk/gmail/ack',{'object_id':oid})[0],200)
        self.assertEqual(replies(),[])
        mailbox.messages.append(message('gmail-2',at=(at+timedelta(minutes=3)).isoformat()))
        mail.on_new_reply=None
        self.assertTrue(mail.customer(oid)['reply_pending'])
        self.assertEqual(len(replies()),1)
        self.assertEqual(flow()['bucket'],'history')


if __name__=='__main__': unittest.main()
