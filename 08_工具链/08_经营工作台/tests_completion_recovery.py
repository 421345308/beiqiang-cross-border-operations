"""Interrupted-attempt completion events use confirmed local process evidence."""
import copy
import unittest
from unittest.mock import patch

from agent_jobs import AgentJobs
import tests_completion_followup as fixture
import tests_task_workspace as overview_fixture
from workspaces import WorkspaceConflict


class CompletionRecoveryTests(unittest.TestCase):
    setUp = fixture.CompletionFollowupTests.setUp
    tearDown = fixture.CompletionFollowupTests.tearDown
    seed = fixture.CompletionFollowupTests.seed
    register = fixture.CompletionFollowupTests.register

    def active(self, *, owner=1001, child=1002):
        with self.jobs._write():
            job = self.jobs.get_job(self.job_id)
            job.update(status='running', owner_pid=owner, process_id=child, worker_finished=False)
            self.jobs._save(job)
        return self.jobs.get_job(self.job_id)

    def test_confirmed_exits_register_one_reviewable_failed_attempt(self):
        self.seed(status='running')
        self.active()
        with patch.object(AgentJobs, '_pid_alive', return_value=False):
            other = AgentJobs(self.app)
            recovered = other.get_job(self.job_id)
            again = AgentJobs(self.app).get_job(self.job_id)
        self.assertEqual(recovered['status'], 'failed')
        self.assertTrue(recovered['worker_finished'])
        event = recovered['completion_events']['1']
        self.assertEqual(event['event_id'], f'agent-job:{self.job_id}:attempt:1')
        self.assertEqual(event['run_status'], 'failed')
        self.assertEqual(event['intent_version'], 1)
        self.assertEqual(other.completion_view(recovered)[0]['state'], 'awaiting_review')
        self.assertEqual(again['completion_events'], recovered['completion_events'])
        self.assertNotIn('completion_error', recovered)
        assessment = other.assess_completion(self.job_id, 1, expected_version=again['version'],
            expected_intent_version=again['intent']['version'], disposition='needs_decision',
            goal_status='unknown', capability_status='unknown', result_ref='', gap='执行中断',
            next_action='核对已完成资料', evidence=self.evidence)
        self.assertEqual(assessment['assessment']['disposition'], 'needs_decision')

    def test_legacy_attempt_without_frozen_intent_remains_unknown(self):
        self.seed(status='running')
        with self.jobs._write():
            job = self.jobs.get_job(self.job_id)
            job['attempt_plan'].pop('intent')
            job['runs'][0]['attempt_plan'].pop('intent')
            self.jobs._save(job)
        self.active()
        with patch.object(AgentJobs, '_pid_alive', return_value=False):
            other = AgentJobs(self.app)
        job = other.get_job(self.job_id)
        event = other.completion_view(job)[0]
        self.assertIsNone(event['intent_version'])
        self.assertFalse(event['intent_version_known'])
        self.assertEqual(event['state'], 'review_required')

    def test_live_or_unknown_owner_or_child_is_never_marked_finished(self):
        for owner_alive, child_alive, child in ((False, True, 1002), (False, None, 1002),
                                                 (None, False, 1002), (False, None, None)):
            with self.subTest(owner_alive=owner_alive, child_alive=child_alive, child=child):
                self.db.execute('DELETE FROM agent_jobs')
                self.db.commit()
                self.seed(status='running')
                self.active(child=child)
                def alive(pid):
                    return owner_alive if pid == 1001 else child_alive
                with patch.object(AgentJobs, '_pid_alive', side_effect=alive):
                    other = AgentJobs(self.app)
                job = other.get_job(self.job_id)
                self.assertEqual(job['status'], 'running')
                self.assertFalse(job['worker_finished'])
                self.assertNotIn('completion_events', job)
                self.assertNotIn('completion_error', job)

    def test_queued_unstarted_attempt_does_not_fabricate_completion(self):
        self.seed(status='running')
        with self.jobs._write():
            job = self.jobs.get_job(self.job_id)
            job.update(status='queued', attempt=0, runs=[], owner_pid=1001,
                       process_id=None, worker_finished=False)
            self.jobs._save(job)
        with patch.object(AgentJobs, '_pid_alive', return_value=False):
            other = AgentJobs(self.app)
        job = other.get_job(self.job_id)
        self.assertEqual(job['status'], 'failed')
        self.assertTrue(job['worker_finished'])
        self.assertNotIn('completion_events', job)
        self.assertNotIn('completion_error', job)

    def test_queued_continuation_does_not_relabel_previous_attempt(self):
        self.seed(status='completed')
        self.register(self.jobs.get_job(self.job_id))
        with self.jobs._write():
            job = self.jobs.get_job(self.job_id)
            original_event = copy.deepcopy(job['completion_events']['1'])
            job.update(status='queued', owner_pid=1001, process_id=None, worker_finished=False)
            job['attempt_plan'] = {**job['attempt_plan'], 'attempt':2}
            self.jobs._save(job)
        with patch.object(AgentJobs, '_pid_alive', return_value=False):
            other = AgentJobs(self.app)
        job = other.get_job(self.job_id)
        self.assertEqual(job['status'], 'failed')
        self.assertEqual(job['attempt'], 1)
        self.assertEqual(job['completion_events'], {'1':original_event})
        self.assertNotIn('completion_error', job)

    def test_manual_confirmed_recovery_registers_running_attempt(self):
        self.seed(status='running')
        self.active(child=None)
        with patch.object(AgentJobs, '_pid_alive', return_value=False):
            other = AgentJobs(self.app)
            self.assertEqual(other.get_job(self.job_id)['status'], 'running')
            job = other.recover_legacy(self.job_id, confirmed=True, former_owner_pid=1001,
                evidence='已核对原服务 PID 1001 退出，且没有未登记的残留子进程')
        self.assertEqual(job['status'], 'failed')
        self.assertTrue(job['worker_finished'])
        self.assertEqual(job['completion_events']['1']['run_status'], 'failed')
        self.assertEqual(job['completion_events']['1']['intent_version'], 1)

    def test_manual_recovery_keeps_inflight_save_as_unknown(self):
        self.seed(status='running')
        self.active(child=None)
        with self.jobs._write():
            job = self.jobs.get_job(self.job_id)
            job['result_commit'] = {'state':'saving', 'attempt':1, 'owner_pid':1001}
            self.jobs._save(job)
        raw = self.app.state/'agent-jobs'/self.job_id/'attempt-1'/'final.md'
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_text('合成的未确认原始成果', encoding='utf8')
        with patch.object(AgentJobs, '_pid_alive', return_value=False):
            other = AgentJobs(self.app)
            self.assertEqual(other.get_job(self.job_id)['status'], 'running')
            job = other.recover_legacy(self.job_id, confirmed=True, former_owner_pid=1001,
                evidence='已核对原服务 PID 1001 退出，且没有未登记的残留子进程')
        self.assertEqual(job['status'], 'needs_input')
        self.assertTrue(job['worker_finished'])
        self.assertEqual(job['result_commit']['state'], 'outcome_unknown')
        self.assertEqual(job['held_result']['attempt'], 1)
        self.assertEqual(job['held_result']['reason'], 'result_outcome_unknown')
        self.assertEqual(other.read_held_result(self.job_id)['content'], '合成的未确认原始成果')
        self.assertEqual(job['completion_events']['1']['run_status'], 'needs_input')
        with self.assertRaises(ValueError):
            other.reconcile_result_commit(self.job_id, expected_version=job['version'],
                                          evidence='结果仍不明', outcome='unknown')
        self.assertEqual(other.get_job(self.job_id)['result_commit']['state'], 'outcome_unknown')

    def test_manual_recovery_never_assumes_unknown_child_or_bad_commit(self):
        self.seed(status='running')
        self.active()
        with self.jobs._write():
            job = self.jobs.get_job(self.job_id)
            job['result_commit'] = {'state':'saving', 'attempt':1, 'owner_pid':1001}
            self.jobs._save(job)
        with patch.object(AgentJobs, '_pid_alive', side_effect=lambda pid: False if pid == 1001 else None):
            other = AgentJobs(self.app)
            with self.assertRaises(ValueError):
                other.recover_legacy(self.job_id, confirmed=True, former_owner_pid=1001,
                    evidence='已核对原服务 PID 1001 退出，且没有未登记的残留子进程')
        unchanged = other.get_job(self.job_id)
        self.assertEqual(unchanged['status'], 'running')
        self.assertEqual(unchanged['result_commit']['state'], 'saving')
        self.assertNotIn('completion_events', unchanged)
        with self.jobs._write():
            job = self.jobs.get_job(self.job_id)
            job['process_id'] = None
            job['result_commit']['attempt'] = 2
            self.jobs._save(job)
        with patch.object(AgentJobs, '_pid_alive', return_value=False):
            other = AgentJobs(self.app)
            with self.assertRaises(WorkspaceConflict):
                other.recover_legacy(self.job_id, confirmed=True, former_owner_pid=1001,
                    evidence='已核对原服务 PID 1001 退出，且没有未登记的残留子进程')
        unchanged = other.get_job(self.job_id)
        self.assertEqual(unchanged['status'], 'running')
        self.assertEqual(unchanged['result_commit']['state'], 'saving')

    def test_registration_failure_stays_visible_in_inbox(self):
        self.seed(status='running')
        self.active()
        with patch.object(AgentJobs, '_pid_alive', return_value=False), \
             patch.object(AgentJobs, '_record_finished_attempt', side_effect=ValueError('synthetic failure')):
            other = AgentJobs(self.app)
        job = other.get_job(self.job_id)
        self.assertEqual(job['status'], 'failed')
        self.assertEqual(job['completion_error']['state'], 'unavailable')
        self.assertNotIn('completion_events', job)
        view = overview_fixture.WorkspaceTests('test_overview_exposes_current_task_intent_without_history_or_guessing')
        view.setUp()
        view.jobs.append(job)
        view.app.agent_jobs.completion_view = other.completion_view
        inbox = view.service.overview()['inbox']
        self.assertTrue(any(item['kind'] == 'completion_unavailable' for item in inbox))

    def test_missing_attempt_number_remains_visible_without_inventing_one(self):
        self.seed(status='running')
        with self.jobs._write():
            job = self.jobs.get_job(self.job_id)
            job.update(status='running', attempt=None, owner_pid=1001, process_id=1002, worker_finished=False)
            self.jobs._save(job)
        with patch.object(AgentJobs, '_pid_alive', return_value=False):
            other = AgentJobs(self.app)
        job = other.get_job(self.job_id)
        self.assertEqual(job['status'], 'failed')
        self.assertEqual(job['completion_error']['state'], 'unavailable')
        self.assertNotIn('completion_events', job)


if __name__ == '__main__':
    unittest.main()
