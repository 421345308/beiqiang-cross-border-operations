import unittest
from types import SimpleNamespace
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

    def test_local_blocker_is_actionable_not_a_log(self):
        self.jobs=[{'id':'a','object_id':'product:BQ01','status':'needs_input','error':'需要最新资料'},
                   {'id':'b','object_id':'product:BQ010','status':'completed'}]
        inbox=self.service.overview()['inbox']
        self.assertEqual(len(inbox),1)
        self.assertEqual(inbox[0]['action']['task_id'],'local:a')
        self.assertEqual(inbox[0]['judgment'],'需要最新资料')

    def test_invalid_instruction_is_rejected(self):
        for value in (None,'',{},'x'*12001):
            with self.assertRaises(ValueError): self.service.route(value)


class WorkspaceHTTPTests(unittest.TestCase):
    from tests_desk_http import DeskHTTPTests as Fixture
    setUp=Fixture.setUp
    tearDown=Fixture.tearDown
    request=Fixture.request
    write=Fixture.write

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


if __name__=='__main__': unittest.main()
