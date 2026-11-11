"""Outcome-unknown continuation and object guards, isolated from production."""
import json
import unittest
from unittest.mock import patch

import tests_agent_jobs as fixture
import tests_completion_dispatch as completion_fixture
from workspaces import WorkspaceConflict


class OutcomeUnknownBoundaryTests(unittest.TestCase):
    setUp = fixture.AgentJobTests.setUp
    tearDown = fixture.AgentJobTests.tearDown
    wait = fixture.AgentJobTests.wait
    first_run = completion_fixture.CompletionDispatchTests.first_run
    review = staticmethod(completion_fixture.CompletionDispatchTests.review)

    def uncertain_followup(self):
        first = self.first_run()
        # The actual isolated Business.save_artifact is called and raises at
        # the final save boundary, after the followup process returned output.
        self.app.business.fail_save = True
        event = self.jobs.assess_and_continue(first['id'], 1, **self.review(first))
        request_id = event['dispatch']['request_id']
        self.wait({'id':first['id']})
        current = self.jobs.get_job(first['id'])
        self.assertEqual(current['attempt'], 2)
        self.assertEqual(current['status'], 'needs_input')
        self.assertEqual(current['result_commit']['state'], 'outcome_unknown')
        self.assertEqual(current['completion_events']['1']['dispatch']['state'], 'unknown')
        self.assertEqual(current['completion_events']['1']['dispatch']['request_id'], request_id)
        self.assertEqual(len(self.processes), 2)
        self.assertIn('有依据的可用草稿', self.jobs.read_held_result(first['id'], attempt=2)['content'])
        return current, request_id

    def test_uncertain_save_never_retries_or_allows_same_object_until_failed_confirmed(self):
        current, request_id = self.uncertain_followup()
        job_id = current['id']
        again = self.jobs.continue_followup(job_id, 1, expected_version=0, request_id=request_id)
        self.assertEqual(again['dispatch']['state'], 'unknown')
        current = self.jobs.get_job(job_id)
        reconciled = self.jobs.reconcile_followup(job_id, 1, expected_version=current['version'], request_id=request_id)
        self.assertEqual(reconciled['dispatch']['state'], 'unknown')
        with self.assertRaises(WorkspaceConflict):
            self.jobs.start('product:shoe', '不能绕过未知结果另建工作', mode='mail_draft')
        self.assertEqual(len(self.processes), 2)
        current = self.jobs.get_job(job_id)
        for outcome in (None, 'unknown'):
            with self.assertRaisesRegex(ValueError, '仍不明时保持待核对'):
                self.jobs.reconcile_result_commit(job_id, expected_version=current['version'],
                                                  evidence='核对原任务和合成回执', outcome=outcome)
            self.assertEqual(self.jobs.get_job(job_id)['result_commit']['state'], 'outcome_unknown')
        with self.assertRaises(ValueError):
            self.jobs.reconcile_result_commit(job_id, expected_version=current['version'], evidence=' ', outcome='failed')
        self.assertEqual(len(self.processes), 2)
        current = self.jobs.get_job(job_id)
        reviewed = self.jobs.reconcile_result_commit(job_id, expected_version=current['version'], outcome='failed',
                    evidence='人工核对合成业务对象与保存回执，确认该次保存失败。')
        self.assertNotIn('result_commit', reviewed)
        self.assertEqual(reviewed['result_reconciliations'][-1]['outcome'], 'failed')
        self.assertEqual(reviewed['completion_events']['1']['dispatch']['state'], 'failed')
        self.assertEqual(len(self.processes), 2)
        self.app.business.fail_save = False
        new = self.jobs.start('product:shoe', '核对明确失败后的新合成工作', mode='mail_draft')
        self.wait(new)
        self.assertEqual(len(self.processes), 3)

    def test_completed_outcome_is_not_misreported_as_failed(self):
        current, request_id = self.uncertain_followup()
        reviewed = self.jobs.reconcile_result_commit(current['id'], expected_version=current['version'],
                    outcome='completed', evidence='人工核对合成成果和回执，确认该次保存已完成。')
        self.assertEqual(reviewed['result_reconciliations'][-1]['outcome'], 'completed')
        self.assertEqual(reviewed['completion_events']['1']['dispatch']['state'], 'completed')
        self.assertEqual(reviewed['status'], 'needs_input')
        self.assertEqual(len(self.processes), 2)
        replay = self.jobs.continue_followup(current['id'], 1, expected_version=0, request_id=request_id)
        self.assertEqual(replay['dispatch']['state'], 'completed')
        self.assertEqual(len(self.processes), 2)

    def test_legacy_evidence_without_outcome_remains_unknown_until_explicitly_resolved(self):
        first = self.first_run()
        with self.jobs._write():
            job = self.jobs.get_job(first['id'])
            self.jobs._hold_attempt_result(job, 1, 'result_outcome_unknown')
            job.update(status='needs_input', worker_finished=True)
            job.setdefault('result_reconciliations', []).append({'attempt':1, 'evidence':'旧记录仅说明曾核对'})
            self.jobs._save(job)
        current = self.jobs.get_job(first['id'])
        self.assertNotIn('result_commit', current)
        with self.assertRaises(WorkspaceConflict):
            self.jobs.start('product:shoe', '不能绕过旧未知结果', mode='mail_draft')
        reviewed = self.jobs.reconcile_result_commit(first['id'], expected_version=current['version'],
                    outcome='failed', evidence='人工再次核对旧轮次的业务对象和回执，确认保存失败。')
        self.assertEqual(reviewed['result_reconciliations'][-1]['attempt'], 1)
        self.assertEqual(reviewed['result_reconciliations'][-1]['outcome'], 'failed')
        self.assertEqual(reviewed['held_results']['1']['reason'], 'result_outcome_unknown')
        new = self.jobs.start('product:shoe', '已对账后继续合成工作', mode='mail_draft')
        self.wait(new)
        self.assertEqual(len(self.processes), 2)

    def test_ordinary_needs_input_does_not_block_a_distinct_job(self):
        first = self.first_run()
        with self.jobs._write():
            job = self.jobs.get_job(first['id'])
            job.update(status='needs_input', worker_finished=True)
            self.jobs._save(job)
        new = self.jobs.start('product:shoe', '普通待输入不等于结果未知', mode='mail_draft')
        self.wait(new)
        self.assertEqual(len(self.processes), 2)

    def test_finished_worker_with_saving_marker_has_unknown_followup_receipt(self):
        job = {'attempt':2, 'status':'needs_input', 'worker_finished':True,
               'attempt_plan':{'attempt':2,'followup_request_id':'one','followup_source_attempt':1},
               'result_commit':{'attempt':2,'state':'saving'},
               'completion_events':{'1':{'attempt':1,'dispatch':{'request_id':'one','target_attempt':2,'state':'running'}}}}
        self.assertTrue(self.jobs._sync_followup_receipts(job))
        self.assertEqual(job['completion_events']['1']['dispatch']['state'], 'unknown')

    def saving_followup(self):
        current, request_id = self.uncertain_followup()
        with self.jobs._write():
            job = self.jobs.get_job(current['id'])
            job['result_commit']['state'] = 'saving'
            job['process_id'] = 987654321
            self.jobs._save(job)
        return self.jobs.get_job(current['id']), request_id

    def test_finished_saving_requires_exited_original_pid_and_explicit_outcome(self):
        current, request_id = self.saving_followup()
        job_id = current['id']
        self.assertEqual(current['completion_events']['1']['dispatch']['state'], 'unknown')
        for alive in (True, None):
            with patch.object(self.jobs, '_pid_alive', return_value=alive):
                with self.assertRaisesRegex(ValueError, '原进程仍在运行或状态未知'):
                    self.jobs.reconcile_result_commit(job_id, expected_version=current['version'],
                                outcome='failed', evidence='已核对合成成果和回执。')
            self.assertEqual(self.jobs.get_job(job_id)['result_commit']['state'], 'saving')
        with self.jobs._write():
            job = self.jobs.get_job(job_id)
            job['process_id'] = None
            self.jobs._save(job)
        missing = self.jobs.get_job(job_id)
        with self.assertRaisesRegex(ValueError, '原进程编号缺失'):
            self.jobs.reconcile_result_commit(job_id, expected_version=missing['version'],
                        outcome='failed', evidence='已核对合成成果和回执。')
        with self.jobs._write():
            job = self.jobs.get_job(job_id)
            job.update(process_id=987654321, worker_finished=False)
            self.jobs._save(job)
        unfinished = self.jobs.get_job(job_id)
        with patch.object(self.jobs, '_pid_alive', return_value=False):
            with self.assertRaisesRegex(ValueError, '执行仍在收尾'):
                self.jobs.reconcile_result_commit(job_id, expected_version=unfinished['version'],
                            outcome='failed', evidence='已核对合成成果和回执。')
        with self.jobs._write():
            job = self.jobs.get_job(job_id)
            job.update(worker_finished=True, status='running')
            self.jobs._save(job)
        active = self.jobs.get_job(job_id)
        with patch.object(self.jobs, '_pid_alive', return_value=False):
            with self.assertRaisesRegex(ValueError, '工作仍在执行'):
                self.jobs.reconcile_result_commit(job_id, expected_version=active['version'],
                            outcome='failed', evidence='已核对合成成果和回执。')
        with self.jobs._write():
            job = self.jobs.get_job(job_id)
            job['status'] = 'needs_input'
            self.jobs._save(job)
        current = self.jobs.get_job(job_id)
        with patch.object(self.jobs, '_pid_alive', return_value=False):
            with self.assertRaisesRegex(ValueError, '仍不明时保持待核对'):
                self.jobs.reconcile_result_commit(job_id, expected_version=current['version'],
                            outcome='unknown', evidence='合成回执仍不明。')
            with self.assertRaises(WorkspaceConflict):
                self.jobs.start('product:shoe', '不绕过未知保存结果', mode='mail_draft')
            reviewed = self.jobs.reconcile_result_commit(job_id, expected_version=current['version'], outcome='failed',
                         evidence='人工检查合成业务记录和回执，确认第二轮保存失败。')
        self.assertNotIn('result_commit', reviewed)
        self.assertEqual(reviewed['result_reconciliations'][-1]['prior_state'], 'saving')
        self.assertEqual(reviewed['result_reconciliations'][-1]['outcome'], 'failed')
        self.assertEqual(reviewed['completion_events']['1']['dispatch']['state'], 'failed')
        self.assertEqual(len(self.processes), 2)

    def test_finished_saving_can_confirm_completion_without_relaunch(self):
        current, request_id = self.saving_followup()
        with patch.object(self.jobs, '_pid_alive', return_value=False):
            reviewed = self.jobs.reconcile_result_commit(current['id'], expected_version=current['version'],
                         outcome='completed', evidence='人工核对合成业务记录和回执，确认成果已保存。')
        self.assertEqual(reviewed['result_reconciliations'][-1]['prior_state'], 'saving')
        self.assertEqual(reviewed['result_reconciliations'][-1]['outcome'], 'completed')
        self.assertEqual(reviewed['completion_events']['1']['dispatch']['state'], 'completed')
        self.assertEqual(len(self.processes), 2)
        repeated = self.jobs.continue_followup(current['id'], 1, expected_version=0, request_id=request_id)
        self.assertEqual(repeated['dispatch']['state'], 'completed')
        self.assertEqual(len(self.processes), 2)

    def test_saving_reconciliation_never_clears_a_different_unresolved_attempt(self):
        current, _ = self.saving_followup()
        with self.jobs._write():
            job = self.jobs.get_job(current['id'])
            self.jobs._hold_attempt_result(job, 1, 'result_outcome_unknown')
            self.jobs._save(job)
        current = self.jobs.get_job(current['id'])
        with patch.object(self.jobs, '_pid_alive', return_value=False):
            with self.assertRaisesRegex(ValueError, '没有该轮待核对'):
                self.jobs.reconcile_result_commit(current['id'], expected_version=current['version'], attempt=3,
                            outcome='failed', evidence='人工核对合成回执。')
            one = self.jobs.reconcile_result_commit(current['id'], expected_version=current['version'], attempt=1,
                      outcome='failed', evidence='人工核对第一轮合成回执，确认保存失败。')
            self.assertEqual(one['result_commit']['attempt'], 2)
            self.assertEqual(one['result_commit']['state'], 'saving')
            self.assertEqual(one['completion_events']['1']['dispatch']['state'], 'unknown')
            with self.assertRaises(WorkspaceConflict):
                self.jobs.start('product:shoe', '第二轮仍未知', mode='mail_draft')
            two = self.jobs.reconcile_result_commit(current['id'], expected_version=one['version'], attempt=2,
                      outcome='completed', evidence='人工核对第二轮合成回执，确认成果已保存。')
        self.assertNotIn('result_commit', two)
        self.assertEqual([item['attempt'] for item in two['result_reconciliations']], [1, 2])
        self.assertEqual([item['prior_state'] for item in two['result_reconciliations']], ['outcome_unknown', 'saving'])
        self.assertEqual(two['completion_events']['1']['dispatch']['state'], 'completed')
        self.assertEqual(len(self.processes), 2)

    def test_old_persisted_false_failed_receipt_is_corrected_without_relaunch(self):
        current, request_id = self.uncertain_followup()
        # Simulate the old version's already-persisted false failed receipt.
        current['completion_events']['1']['dispatch']['state'] = 'failed'
        with self.app.lock:
            self.app.db.execute('UPDATE agent_jobs SET data=? WHERE id=?',
                                (json.dumps(current, ensure_ascii=False), current['id']))
            self.app.db.commit()
        # Reads project the actual unknown result without writing or dispatching.
        projected = self.jobs.completion_view(self.jobs.get_job(current['id']))
        self.assertEqual(next(row for row in projected if row['attempt']==1)['dispatch']['state'],'unknown')
        replay = self.jobs.assess_completion(current['id'],1,**self.review(current))
        self.assertEqual(replay['dispatch']['state'],'unknown')
        self.assertEqual(self.jobs.get_job(current['id'])['completion_events']['1']['dispatch']['state'],'failed')
        self.assertEqual(len(self.processes),2)
        repeated = self.jobs.continue_followup(current['id'], 1, expected_version=0, request_id=request_id)
        self.assertEqual(repeated['dispatch']['state'], 'unknown')
        self.assertEqual(self.jobs.get_job(current['id'])['completion_events']['1']['dispatch']['state'], 'unknown')
        self.assertEqual(len(self.processes), 2)

    def test_multiple_legacy_unknowns_require_explicit_attempt_and_all_are_resolved(self):
        first = self.first_run()
        with self.jobs._write():
            job = self.jobs.get_job(first['id'])
            job.update(attempt=2, status='needs_input', worker_finished=True, process_id=None)
            self.jobs._hold_attempt_result(job, 1, 'result_outcome_unknown')
            self.jobs._hold_attempt_result(job, 2, 'result_outcome_unknown')
            self.jobs._save(job)
        current = self.jobs.get_job(first['id'])
        with self.assertRaisesRegex(ValueError, '多个未核对轮次'):
            self.jobs.reconcile_result_commit(first['id'], expected_version=current['version'],
                        outcome='failed', evidence='人工核对对应合成回执。')
        one = self.jobs.reconcile_result_commit(first['id'], expected_version=current['version'],
                    attempt=1, outcome='failed', evidence='人工核对第一轮合成回执，确认保存失败。')
        with self.assertRaises(WorkspaceConflict):
            self.jobs.start('product:shoe', '第二轮仍未知', mode='mail_draft')
        two = self.jobs.reconcile_result_commit(first['id'], expected_version=one['version'],
                    attempt=2, outcome='completed', evidence='人工核对第二轮合成结果，确认保存完成。')
        self.assertEqual([item['attempt'] for item in two['result_reconciliations']], [1, 2])
        new = self.jobs.start('product:shoe', '两轮均有明确回执后继续', mode='mail_draft')
        self.wait(new)
        self.assertEqual(len(self.processes), 2)


if __name__ == '__main__':
    unittest.main()
