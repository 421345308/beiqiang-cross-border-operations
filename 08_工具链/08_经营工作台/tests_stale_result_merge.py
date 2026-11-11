"""Stale worker snapshots must not erase unknown saves or reconciliation."""
import sqlite3
import threading
import unittest
from types import SimpleNamespace

from agent_jobs import AgentJobs
import tests_agent_jobs as fixture
from workspaces import WorkspaceConflict


class ObservedGate:
    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()

    def wait(self, timeout=None):
        self.entered.set()
        return self.release.wait(timeout)

    def set(self):
        self.release.set()


class StaleResultMergeTests(unittest.TestCase):
    def setUp(self):
        fixture.AgentJobTests.setUp(self)
        # Separate service instances and connections share only a private file.
        old = self.app.db
        path = self.root / 'stale-result-merge.sqlite3'
        self.app.db = sqlite3.connect(path, timeout=3, check_same_thread=False)
        old.close()
        self.jobs = AgentJobs(self.app)
        self.other_db = sqlite3.connect(path, timeout=3, check_same_thread=False)
        other_app = SimpleNamespace(root=self.root, state=self.app.state, lock=threading.RLock(),
                                    db=self.other_db, business=self.app.business)
        self.other = AgentJobs(other_app)

    def tearDown(self):
        self.other_db.close()
        fixture.AgentJobTests.tearDown(self)

    wait = fixture.AgentJobTests.wait

    def test_stale_running_snapshot_cannot_erase_unknown_result(self):
        gate = ObservedGate()
        self.options['gate'] = gate
        self.app.business.fail_save = True
        started = self.jobs.start('product:shoe', '合成任务')
        try:
            self.assertTrue(gate.entered.wait(3), 'worker did not reach its synthetic gate')
            stale = self.other.get_job(started['id'])
            self.assertEqual(stale['status'], 'running')
            self.assertNotIn('result_commit', stale)
        finally:
            gate.set()
        self.wait(started)
        unknown = self.other.get_job(started['id'])
        self.assertEqual(unknown['status'], 'needs_input')
        self.assertEqual(unknown['result_commit']['state'], 'outcome_unknown')
        self.assertTrue(unknown.get('held_result'))
        self.assertTrue(unknown.get('completion_events'))
        with self.assertRaises(WorkspaceConflict):
            self.other._save(stale)
        after = self.other.get_job(started['id'])
        self.assertEqual(after['version'], unknown['version'])
        self.assertEqual(after['status'], 'needs_input')
        self.assertEqual(after['result_commit'], unknown['result_commit'])
        self.assertEqual(after['held_result'], unknown['held_result'])
        self.assertEqual(after['completion_events'], unknown['completion_events'])

    def test_stale_unknown_snapshot_cannot_undo_recorded_reconciliation(self):
        self.app.business.fail_save = True
        started = self.jobs.start('product:shoe', '合成任务')
        self.wait(started)
        stale = self.other.get_job(started['id'])
        self.assertEqual(stale['result_commit']['state'], 'outcome_unknown')
        reviewed = self.jobs.reconcile_result_commit(started['id'], expected_version=stale['version'],
            evidence='合成业务保存替身在写入前抛错，确认未保存', outcome='failed')
        self.assertNotIn('result_commit', reviewed)
        self.assertEqual(len(reviewed['result_reconciliations']), 1)
        with self.assertRaises(WorkspaceConflict):
            self.other._save(stale)
        after = self.other.get_job(started['id'])
        self.assertEqual(after['version'], reviewed['version'])
        self.assertNotIn('result_commit', after)
        self.assertEqual(after['result_reconciliations'], reviewed['result_reconciliations'])
        self.assertEqual(after['held_result'], reviewed['held_result'])

    def test_nonconflicting_stale_snapshot_still_preserves_operator_intent(self):
        plan = self.jobs.start('product:shoe', '初始合成目标', defer=True)
        stale = self.other.get_job(plan['id'])
        updated = self.jobs.adjust(plan['id'], expected_version=stale['version'],
            current_goal='最新合成目标', intent_source='合成负责人记录', intent_reason='调整目标')
        self.other._save(stale)
        after = self.other.get_job(plan['id'])
        self.assertEqual(after['intent'], updated['intent'])
        self.assertEqual(after['status'], 'planned')
        self.assertGreaterEqual(after['version'], updated['version'])

    def test_stale_older_attempt_cannot_repoint_latest_held_result(self):
        self.options.update(code=1, content='FIRST_SYNTHETIC_OUTPUT')
        first = self.jobs.start('product:shoe', '首轮合成任务')
        self.wait(first)
        stale = self.other.get_job(first['id'])
        self.assertEqual(stale['held_result']['attempt'], 1)
        self.options['content'] = 'SECOND_SYNTHETIC_OUTPUT'
        second = self.jobs.resume(first['id'], '第二轮合成任务', expected_version=stale['version'])
        self.wait(second)
        latest = self.other.get_job(first['id'])
        self.assertEqual(latest['held_result']['attempt'], 2)
        self.assertEqual(latest['held_revision'], 2)
        # A delayed first-attempt holder can have the same locally incremented
        # revision as the already-persisted second attempt.
        self.other._hold_attempt_result(stale, 1, 'result_unvalidated')
        self.assertEqual(stale['held_revision'], latest['held_revision'])
        try:
            self.other._save(stale)
        except WorkspaceConflict:
            pass  # Rejection is also safe; the old snapshot must not win.
        after = self.other.get_job(first['id'])
        self.assertEqual(after['attempt'], 2)
        self.assertEqual(after['held_result']['attempt'], 2)
        self.assertEqual(set(after['held_results']), {'1', '2'})
        self.assertEqual(self.other.read_held_result(first['id'])['content'], 'SECOND_SYNTHETIC_OUTPUT')
        self.assertEqual(self.other.read_held_result(first['id'], attempt=1)['content'], 'FIRST_SYNTHETIC_OUTPUT')
        self.assertEqual(self.other.read_held_result(first['id'], attempt=2)['content'], 'SECOND_SYNTHETIC_OUTPUT')


if __name__ == '__main__':
    unittest.main()
