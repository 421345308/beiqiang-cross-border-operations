"""Real isolated AgentJobs continuation behavior; no real accounts or services."""
import sqlite3
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agent_jobs import AgentJobs
import tests_agent_jobs as fixture
import tests_customer_analysis as customer_fixture
from workspaces import WorkspaceConflict


class CompletionDispatchTests(unittest.TestCase):
    setUp = fixture.AgentJobTests.setUp
    tearDown = fixture.AgentJobTests.tearDown
    wait = fixture.AgentJobTests.wait

    def first_run(self, mode='mail_draft'):
        job = self.jobs.start('product:shoe', '合成任务：读取资料并给出下一步', mode=mode)
        self.wait(job)
        current = self.jobs.get_job(job['id'])
        self.assertTrue(current['worker_finished'])
        self.assertEqual(current['status'], 'completed')
        self.assertEqual(current['completion_events']['1']['run_status'], 'completed')
        self.assertEqual(self.jobs.completion_view(current)[0]['state'], 'awaiting_review')
        return current

    @staticmethod
    def review(job):
        return {'expected_version':job['version'], 'expected_intent_version':job['intent']['version'],
                'disposition':'continue', 'goal_status':'not_met', 'capability_status':'unknown',
                'result_ref':'synthetic-artifact', 'gap':'仍需核对合成资料',
                'next_action':'只读核对合成资料并给出结果',
                'evidence':{'source':'synthetic artifact', 'observed_at':'2026-11-11T12:00:00Z',
                            'detail':'首轮结果已保留，目标尚未达成。'}}

    def wait_until(self, predicate, message, timeout=4):
        deadline = time.monotonic()+timeout
        while time.monotonic()<deadline:
            value = predicate()
            if value:return value
            time.sleep(.01)
        self.fail(message)

    def test_safe_followup_runs_same_task_once_and_receipt_tracks_real_observations(self):
        first = self.first_run()
        self.assertEqual(len(self.processes), 1)
        resolve_entered, resolve_release, worker_release = threading.Event(),threading.Event(),threading.Event()
        self.options['gate'] = worker_release
        def delayed_resolve():
            resolve_entered.set()
            if not resolve_release.wait(5):raise AssertionError('test did not release resolver')
            return '/fake/codex'
        try:
            with patch.object(self.jobs.backend, 'resolve_executable', side_effect=delayed_resolve):
                event = self.jobs.assess_and_continue(first['id'],1,**self.review(first))
                self.assertEqual(event['dispatch']['state'],'accepted')
                request_id = event['dispatch']['request_id']
                self.assertEqual(event['dispatch']['target_job_id'],first['id'])
                self.assertEqual(event['dispatch']['target_attempt'],2)
                self.assertTrue(resolve_entered.wait(3))
                starting = self.jobs.get_job(first['id'])
                self.assertEqual(starting['completion_events']['1']['dispatch']['state'],'starting')
                self.assertIsNone(starting.get('process_id'))
                repeated = self.jobs.continue_followup(first['id'],1,expected_version=0,request_id=request_id)
                self.assertEqual(repeated['dispatch']['request_id'],request_id)
                with self.assertRaises(WorkspaceConflict):
                    self.jobs.continue_followup(first['id'],1,expected_version=starting['version'],request_id='other-request')
                self.assertEqual(len(self.processes),1)
                resolve_release.set()
                def running_receipt():
                    current = self.jobs.get_job(first['id'])
                    receipt = current['completion_events']['1']['dispatch']
                    return current if receipt['state']=='running' and current.get('process_id') else None
                running = self.wait_until(running_receipt,'safe followup did not reach observed process state')
                self.assertEqual(running['attempt'],2)
                self.assertEqual(running['completion_events']['1']['dispatch']['state'],'running')
                self.assertEqual(running['attempt_plan']['followup_request_id'],request_id)
                self.assertEqual(running['attempt_plan']['followup_source_attempt'],1)
                self.assertEqual(running['completion_events']['1']['dispatch']['observed_process_id'],self.processes[-1].pid)
                self.assertTrue(running['completion_events']['1']['dispatch']['started_at'])
                self.assertEqual(len(self.processes),2)
                self.assertIn('read-only',self.command)
                self.wait_until(lambda:self.processes[-1].stdin.closed,'followup prompt was not delivered')
                self.assertIn('只读核对合成资料并给出结果',self.processes[-1].stdin.value)
                worker_release.set()
                self.wait({'id':first['id']})
                completed = self.jobs.get_job(first['id'])
                self.assertEqual(completed['id'],first['id'])
                self.assertEqual(completed['attempt'],2)
                self.assertEqual(completed['completion_events']['1']['dispatch']['state'],'completed')
                self.assertEqual(completed['completion_events']['2']['run_status'],'completed')
                self.assertEqual(self.jobs.completion_view(completed)[0]['state'],'awaiting_review')
                repeated = self.jobs.continue_followup(first['id'],1,expected_version=0,request_id=request_id)
                self.assertEqual(repeated['dispatch']['state'],'completed')
                self.assertEqual(len(self.processes),2)
        finally:
            resolve_release.set();worker_release.set()

    def test_unknown_start_receipt_is_retained_and_never_restarted_by_retry_or_reconcile(self):
        first = self.first_run()
        with patch('completion_dispatch.threading.Thread') as thread:
            thread.return_value.start.side_effect = RuntimeError('synthetic launch acknowledgement lost')
            event = self.jobs.assess_and_continue(first['id'],1,**self.review(first))
            self.assertEqual(event['dispatch']['state'],'unknown')
            request_id = event['dispatch']['request_id']
            self.assertEqual(thread.return_value.start.call_count,1)
            self.assertEqual(len(self.processes),1)
            duplicate = self.jobs.assess_and_continue(first['id'],1,**self.review(first))
            self.assertEqual(duplicate['dispatch']['state'],'unknown')
            self.assertEqual(duplicate['dispatch']['request_id'],request_id)
            self.assertEqual(thread.return_value.start.call_count,1)
            current = self.jobs.get_job(first['id'])
            repeated = self.jobs.continue_followup(first['id'],1,expected_version=current['version'],request_id=request_id)
            self.assertEqual(repeated['dispatch']['state'],'unknown')
            with self.assertRaises(WorkspaceConflict):
                self.jobs.continue_followup(first['id'],1,expected_version=current['version'],request_id='different-request')
            current = self.jobs.get_job(first['id'])
            reconciled = self.jobs.reconcile_followup(first['id'],1,expected_version=current['version'],request_id=request_id)
            self.assertEqual(reconciled['dispatch']['state'],'unknown')
            self.assertEqual(reconciled['dispatch']['request_id'],request_id)
            self.assertEqual(thread.return_value.start.call_count,1)
            self.assertEqual(len(self.processes),1)
        # The synthetic Thread was never started. Do not let fixture cleanup
        # mistake a Mock for a live worker.
        self.jobs.threads.pop(first['id'],None)

    def test_unknown_receipt_blocks_unrelated_resume_and_unbound_attempt_cannot_resolve_it(self):
        first = self.first_run()
        with patch('completion_dispatch.threading.Thread') as thread:
            thread.return_value.start.side_effect = RuntimeError('synthetic lost launch')
            event = self.jobs.assess_and_continue(first['id'],1,**self.review(first))
        self.jobs.threads.pop(first['id'],None)
        with self.jobs._write():
            job=self.jobs.get_job(first['id'])
            job.update(status='failed',worker_finished=True,owner_pid=None,process_id=None)
            self.jobs._save(job)
        current=self.jobs.get_job(first['id'])
        self.assertEqual(current['completion_events']['1']['dispatch']['state'],'unknown')
        with self.assertRaises(WorkspaceConflict):
            self.jobs.resume(first['id'],'完全不同的人工操作',new_session=True,expected_version=current['version'])
        self.assertEqual(len(self.processes),1)
        # Even a legacy or external writer that inserted a numerically equal
        # attempt without the request binding is not evidence of this request.
        with self.jobs._write():
            job=self.jobs.get_job(first['id'])
            job.update(attempt=2,status='running',worker_finished=False,process_id=123456,
                       attempt_plan={'attempt':2})
            self.jobs._save(job)
        unbound=self.jobs.get_job(first['id'])
        self.assertEqual(unbound['completion_events']['1']['dispatch']['state'],'unknown')
        self.assertEqual(unbound['completion_events']['1']['dispatch']['request_id'],event['dispatch']['request_id'])
        with self.jobs._write():
            job=self.jobs.get_job(first['id'])
            job.update(status='failed',worker_finished=True,process_id=None)
            self.jobs._save(job)

    def test_changed_intent_blocks_old_review_before_any_followup(self):
        first = self.first_run()
        self.jobs.assess_completion(first['id'],1,**self.review(first))
        reviewed = self.jobs.get_job(first['id'])
        changed = self.jobs.adjust(first['id'],expected_version=reviewed['version'],current_goal='新的合成目标',
                                   intent_source='合成新指令',intent_reason='目标已改变')
        with self.assertRaises(WorkspaceConflict):
            self.jobs.continue_followup(first['id'],1,expected_version=changed['version'],request_id='stale-review')
        current = self.jobs.get_job(first['id'])
        self.assertIsNone(current['completion_events']['1']['dispatch'])
        self.assertEqual(self.jobs.completion_view(current)[0]['state'],'review_required')
        self.assertEqual(current['attempt'],1)
        self.assertEqual(len(self.processes),1)

    def test_write_capable_task_remains_explicitly_ready_without_automatic_dispatch(self):
        first = self.first_run(mode='draft')
        event = self.jobs.assess_and_continue(first['id'],1,**self.review(first))
        self.assertIsNone(event['dispatch'])
        latest = self.jobs.get_job(first['id'])
        self.assertEqual(latest['attempt'],1)
        self.assertEqual(latest['status'],'completed')
        self.assertEqual(self.jobs.completion_view(latest)[0]['state'],'ready_to_continue')
        self.assertEqual(len(self.processes),1)
        with self.assertRaises(ValueError):
            self.jobs.continue_followup(first['id'],1,expected_version=latest['version'],request_id='unapproved-write')
        self.assertEqual(len(self.processes),1)

    def test_owner_adjustment_between_review_and_claim_is_never_overwritten(self):
        first = self.first_run()
        original = self.jobs.assess_completion
        def review_then_change(*args, **kwargs):
            event = original(*args, **kwargs)
            latest = self.jobs.get_job(first['id'])
            self.jobs.adjust(first['id'],expected_version=latest['version'],next_action='人工刚指定的新下一步')
            return event
        with patch.object(self.jobs,'assess_completion',side_effect=review_then_change):
            event = self.jobs.assess_and_continue(first['id'],1,**self.review(first))
        current = self.jobs.get_job(first['id'])
        self.assertEqual(current['next_action'],'人工刚指定的新下一步')
        self.assertEqual(current['attempt'],1)
        self.assertIsNone(event['dispatch'])
        self.assertTrue(event['dispatch_blocked']['reason'])
        self.assertEqual(len(self.processes),1)

    def test_each_failed_attempt_keeps_its_own_held_output(self):
        self.options.update(code=1,content='FIRST_SYNTHETIC_RESULT')
        started = self.jobs.start('product:shoe','合成失败资料',mode='mail_draft')
        self.wait(started)
        first = self.jobs.get_job(started['id'])
        self.assertEqual(first['status'],'failed')
        self.assertEqual(self.jobs.read_held_result(started['id'],attempt=1)['content'],'FIRST_SYNTHETIC_RESULT')
        self.options['content'] = 'SECOND_SYNTHETIC_RESULT'
        event = self.jobs.assess_and_continue(started['id'],1,**self.review(first))
        self.assertIsNotNone(event['dispatch'])
        self.wait_until(lambda:self.jobs.get_job(started['id']).get('attempt') == 2,'followup did not start')
        self.wait({'id':started['id']})
        job = self.jobs.get_job(started['id'])
        self.assertEqual(job['status'],'failed')
        self.assertEqual(set(job['held_results']),{'1','2'})
        self.assertEqual(self.jobs.read_held_result(started['id'])['content'],'SECOND_SYNTHETIC_RESULT')
        self.assertEqual(self.jobs.read_held_result(started['id'],attempt=1)['content'],'FIRST_SYNTHETIC_RESULT')
        self.assertEqual(self.jobs.read_held_result(started['id'],attempt=2)['content'],'SECOND_SYNTHETIC_RESULT')
        with self.assertRaises(ValueError):self.jobs.read_held_result(started['id'],attempt=3)
        with self.assertRaises(ValueError):self.jobs.read_held_result(started['id'],attempt=True)

    def test_stale_snapshot_cannot_erase_an_earlier_held_attempt(self):
        self.options.update(code=1,content='FIRST_SYNTHETIC_RESULT')
        started = self.jobs.start('product:shoe','合成失败资料',mode='mail_draft')
        self.wait(started)
        saved = self.jobs.get_job(started['id'])
        stale = self.jobs.get_job(started['id'])
        # Simulate a snapshot created before the first hold was persisted.
        for key in ('held_result','held_results','held_revision'):stale.pop(key,None)
        self.jobs._hold_attempt_result(stale,2,'result_unvalidated')
        self.jobs._save(stale)
        current = self.jobs.get_job(started['id'])
        self.assertEqual(set(current['held_results']),{'1','2'})
        self.assertEqual(current['held_results']['1'],saved['held_results']['1'])
        self.assertEqual(current['held_result']['attempt'],2)


class CompletionDispatchSharedConnectionTests(CompletionDispatchTests):
    def setUp(self):
        fixture.AgentJobTests.setUp(self)
        self.app.db.close()
        database = self.root/'shared-completion.sqlite3'
        self.app.db = sqlite3.connect(database,timeout=5,check_same_thread=False)
        self.jobs = AgentJobs(self.app)
        self.other_db = sqlite3.connect(database,timeout=5,check_same_thread=False)
        other_app = SimpleNamespace(root=self.root,state=self.app.state,lock=threading.RLock(),
                                    db=self.other_db,business=self.app.business)
        self.other = AgentJobs(other_app)

    def tearDown(self):
        for process in self.processes:process.kill()
        fixture.join_job_threads(self.other)
        self.other_db.close()
        fixture.AgentJobTests.tearDown(self)

    def test_two_connections_same_request_claim_exactly_one_followup(self):
        first = self.first_run()
        self.jobs.assess_completion(first['id'],1,**self.review(first))
        reviewed = self.jobs.get_job(first['id'])
        gate = threading.Event();self.options['gate']=gate
        barrier = threading.Barrier(3);outcomes=[];errors=[]
        def claim(service):
            try:
                barrier.wait(timeout=3)
                outcomes.append(service.continue_followup(first['id'],1,expected_version=reviewed['version'],request_id='same-synthetic-request'))
            except BaseException as error:errors.append(error)
        callers=[threading.Thread(target=claim,args=(service,)) for service in (self.jobs,self.other)]
        try:
            for caller in callers:caller.start()
            barrier.wait(timeout=3)
            for caller in callers:caller.join(5)
            self.assertFalse(any(caller.is_alive() for caller in callers))
            self.assertEqual(errors,[])
            self.assertEqual(len(outcomes),2)
            self.assertEqual({item['dispatch']['request_id'] for item in outcomes},{'same-synthetic-request'})
            self.wait_until(lambda:len(self.processes)==2,'followup process did not start')
            self.assertEqual(len(self.processes),2)
        finally:
            gate.set()
        self.wait_until(lambda:(self.jobs.get_job(first['id']).get('worker_finished') is True and
                               self.jobs.get_job(first['id']).get('attempt')==2),'followup worker did not finish')
        fixture.join_job_threads(self.jobs);fixture.join_job_threads(self.other)
        final=self.jobs.get_job(first['id'])
        self.assertEqual(final['completion_events']['1']['dispatch']['state'],'completed')
        self.assertEqual(len(self.processes),2)


class CustomerAnalysisContinuationBoundaryTests(unittest.TestCase):
    setUp = customer_fixture.CustomerAnalysisTests.setUp
    tearDown = customer_fixture.CustomerAnalysisTests.tearDown
    wait = customer_fixture.CustomerAnalysisTests.wait

    def test_customer_analysis_is_not_automatically_resumed(self):
        started = self.jobs.start(self.obj['id'], '合成客户分析', mode='customer_analysis')
        self.wait(started)
        first = self.jobs.get_job(started['id'])
        self.assertTrue(first['worker_finished'])
        before = self.app.customer_workspace.profile(self.obj['id'])
        review = {'expected_version':first['version'],'expected_intent_version':first['intent']['version'],
                  'disposition':'continue','goal_status':'not_met','capability_status':'unknown',
                  'result_ref':'合成客户分析','gap':'仍需核对','next_action':'核对合成客户资料',
                  'evidence':{'source':'合成来源','observed_at':'2026-11-11T12:00:00Z','detail':'仍有未完成事项'}}
        event = self.jobs.assess_and_continue(started['id'],1,**review)
        self.assertIsNone(event['dispatch'])
        current = self.jobs.get_job(started['id'])
        self.assertEqual(current['attempt'],1)
        self.assertEqual(self.jobs.completion_view(current)[0]['state'],'ready_to_continue')
        self.assertEqual(self.app.customer_workspace.profile(self.obj['id'])['revision'],before['revision'])
        self.assertEqual(len(self.processes),1)


if __name__ == '__main__':
    unittest.main()
