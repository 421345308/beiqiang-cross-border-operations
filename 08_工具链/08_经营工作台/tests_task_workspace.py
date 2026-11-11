import unittest
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
        self.assertEqual(changed['adjustments'][-1]['scheduling_effect'],'display_only')
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
