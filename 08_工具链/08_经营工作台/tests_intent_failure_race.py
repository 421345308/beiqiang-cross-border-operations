"""Cross-connection exception/intent tests using isolated synthetic data."""
import sqlite3
import threading
import unittest
from types import SimpleNamespace

from agent_jobs import AgentJobs
from customer_workspace import CustomerWorkspace
import tests_customer_analysis as fixture
from workspaces import WorkspaceConflict


class ObservedConnection(sqlite3.Connection):
    """Signal immediately before the second connection requests its write lock."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.begin_attempted = None

    def execute(self, sql, parameters=()):
        if sql.strip().upper() == 'BEGIN IMMEDIATE' and self.begin_attempted is not None:
            self.begin_attempted.set()
        return super().execute(sql, parameters)


class ObservedGate:
    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()

    def wait(self, timeout=None):
        self.entered.set()
        return self.release.wait(timeout)

    def set(self):
        self.release.set()


class IntentFailureRaceTests(unittest.TestCase):
    def setUp(self):
        fixture.CustomerAnalysisTests.setUp(self)
        # The base fixture uses an in-memory DB. Swap in a private file so two
        # independent service instances contend through real SQLite locks.
        old = self.app.db
        self.db_path = self.root / 'intent-exception-race.sqlite3'
        self.app.db = sqlite3.connect(self.db_path, timeout=3, check_same_thread=False)
        old.close()
        self.app.customer_workspace = CustomerWorkspace(self.app)
        self.jobs = AgentJobs(self.app)
        self.other_db = sqlite3.connect(self.db_path, timeout=3, check_same_thread=False,
                                        factory=ObservedConnection)
        other_app = SimpleNamespace(root=self.root, state=self.app.state, db=self.other_db,
                                    lock=threading.RLock(), business=self.app.business)
        self.other = AgentJobs(other_app)
        self.options['content'] = '# synthetic invalid JSON output'

    def tearDown(self):
        self.other_db.close()
        fixture.CustomerAnalysisTests.tearDown(self)

    wait = fixture.CustomerAnalysisTests.wait
    start = fixture.CustomerAnalysisTests.start

    def test_exception_transaction_fences_old_version_and_retains_raw_output(self):
        entered, release = threading.Event(), threading.Event()
        attempted, finished = threading.Event(), threading.Event()
        real_event = self.jobs._event
        outcome = {}
        worker = None
        def block_before_failure_save(job, kind, message):
            if kind == 'failed':
                entered.set()
                if not release.wait(5):
                    raise AssertionError('test did not release failure transaction')
            return real_event(job, kind, message)
        self.jobs._event = block_before_failure_save
        try:
            job = self.start()
            self.assertTrue(entered.wait(3), 'worker did not enter failure transaction')
            old_version = self.other.get_job(job['id'])['version']
            self.other_db.begin_attempted = attempted
            def change_from_other_connection():
                try:
                    outcome['result'] = self.other.adjust(job['id'], expected_version=old_version,
                        current_goal='新任务目标', intent_source='合成负责人记录', intent_reason='更新目标')
                except BaseException as error:
                    outcome['error'] = error
                finally:
                    finished.set()
            worker = threading.Thread(target=change_from_other_connection)
            worker.start()
            self.assertTrue(attempted.wait(3), 'second connection did not attempt the SQLite write lock')
            self.assertFalse(finished.wait(.15), 'second connection did not wait for the failure transaction')
            release.set()
            self.assertTrue(finished.wait(4), 'second connection remained blocked')
            worker.join(1)
            self.assertIsInstance(outcome.get('error'), WorkspaceConflict)
            self.assertNotIn('result', outcome)

            self.wait(job)
            saved = self.jobs.get_job(job['id'])
            self.assertEqual(saved['status'], 'failed')
            self.assertEqual(saved['held_result']['reason'], 'result_unvalidated')
            held = self.jobs.read_held_result(job['id'])
            self.assertEqual(held['content'], '# synthetic invalid JSON output')
            self.assertIn('尚未完成或通过校验', held['warning'])

            latest = self.other.get_job(job['id'])
            changed = self.other.adjust(job['id'], expected_version=latest['version'],
                current_goal='新任务目标', intent_source='合成负责人记录', intent_reason='核对失败后调整')
            self.assertEqual(changed['intent']['goal'], '新任务目标')
            self.assertEqual(changed['held_result'], saved['held_result'])
            self.assertEqual(self.jobs.read_held_result(job['id'])['content'], held['content'])
            self.assertFalse(changed['profile_saved'])
            self.assertEqual(self.artifacts, [])
        finally:
            release.set()
            if worker is not None:
                worker.join(5)
            self.jobs._event = real_event

    def test_adjustment_before_exception_leads_to_readable_held_result(self):
        gate = ObservedGate()
        self.options['gate'] = gate
        original = self.app.customer_workspace.profile(self.obj['id'])
        job = self.start()
        try:
            self.assertTrue(gate.entered.wait(3), 'synthetic worker did not reach its gate')
            running = self.other.get_job(job['id'])
            changed = self.other.adjust(job['id'], expected_version=running['version'],
                current_goal='先调整后的目标', intent_source='合成负责人记录', intent_reason='异常前调整')
        finally:
            gate.set()
        self.wait(job)
        done = self.jobs.get_job(job['id'])
        self.assertEqual(done['status'], 'needs_input')
        self.assertEqual(done['intent']['goal'], '先调整后的目标')
        self.assertEqual(done['intent']['version'], changed['intent']['version'])
        self.assertEqual(done['held_result']['reason'], 'planning_changed_during_attempt')
        held = self.jobs.read_held_result(job['id'])
        self.assertEqual(held['content'], '# synthetic invalid JSON output')
        self.assertIn('尚未完成或通过校验', held['warning'])
        after = self.app.customer_workspace.profile(self.obj['id'])
        self.assertEqual(after['revision'], original['revision'])
        self.assertEqual(after['analysis'], original['analysis'])
        self.assertFalse(done['profile_saved'])
        self.assertEqual(self.artifacts, [])


if __name__ == '__main__':
    unittest.main()
