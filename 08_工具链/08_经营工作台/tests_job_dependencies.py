import json
import multiprocessing
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent_jobs import AgentJobs
from tests_agent_jobs import Business, Process, join_job_threads


def app_at(root):
    return SimpleNamespace(root=Path(root), state=Path(root)/'.local', lock=threading.RLock(),
                           db=sqlite3.connect(str(Path(root)/'jobs.sqlite3'), check_same_thread=False),
                           business=Business())


def competing(root, action, job_id, gate, results):
    app = app_at(root)
    try:
        jobs = AgentJobs(app)
        gate.wait(10)
        if action == 'create':
            result = jobs.start('product:shoe', '独立研究', defer=True, idempotency_key='shared')
        else:
            # Persist a real claim without launching an external side effect.
            jobs._work = lambda *args: None
            result = jobs.dispatch(job_id)
        results.put(('ok', result['id']))
    except Exception as exc:
        results.put(('error', str(exc)))
    finally:
        app.db.close()


class DependencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = app_at(self.tmp.name)
        self.jobs = AgentJobs(self.app)

    def tearDown(self):
        join_job_threads(self.jobs)
        self.app.db.close()
        self.tmp.cleanup()

    def plan(self, text='研究', **kwargs):
        return self.jobs.start('product:shoe', text, defer=True, **kwargs)

    def complete(self, job):
        with patch('agent_jobs.shutil.which', return_value='/fake/codex'), \
             patch('agent_jobs.subprocess.Popen', side_effect=lambda command, **kw: Process(command)):
            self.jobs.dispatch(job['id'])
            join_job_threads(self.jobs, job['id'])
        return self.jobs.get_job(job['id'])

    def test_dynamic_children_persist_and_dispatch_only_ready_without_replay(self):
        root = self.plan('目标')
        first = self.plan('第一项', parent_job_id=root['id'])
        second = self.plan('第二项', parent_job_id=root['id'], depends_on=[first['id']])
        other = AgentJobs(self.app)
        self.assertEqual(len(other.get_graph(root['id'])['jobs']), 3)
        self.assertEqual(other.get_job(first['id'])['status'], 'planned')
        with self.assertRaises(ValueError): other.dispatch(second['id'])
        self.assertEqual(self.complete(first)['status'], 'completed')
        self.assertEqual(self.jobs.get_job(second['id'])['status'], 'planned')
        self.assertEqual(self.complete(second)['status'], 'completed')
        with self.assertRaises(ValueError): self.jobs.dispatch(second['id'])
        self.assertEqual(self.jobs.get_job(first['id'])['attempt'], 1)
        self.assertEqual(self.jobs.get_job(root['id'])['status'], 'planned')

    def test_group_is_non_executing_and_aggregate_reopens_for_new_child(self):
        group = self.jobs.create_group('product:shoe', '批次', idempotency_key='batch')
        self.assertEqual(self.jobs.get_graph(group['id'])['aggregate']['status'], 'empty')
        with self.assertRaises(ValueError): self.jobs.dispatch(group['id'])
        with self.assertRaises(ValueError): self.plan(depends_on=[group['id']])
        with self.assertRaises(ValueError): self.jobs.add_dependency(group['id'], group['id'])
        child = self.plan(parent_job_id=group['id'])
        self.assertEqual(self.jobs.get_graph(group['id'])['aggregate']['status'], 'ready')
        self.complete(child)
        graph = self.jobs.get_graph(group['id'])
        self.assertEqual(graph['aggregate'], {'status':'completed', 'counts':{'completed':1}, 'total':1})
        self.assertEqual(self.jobs.get_job(group['id'])['attempt'], 0)
        self.plan('新增工作', parent_job_id=group['id'])
        self.assertEqual(self.jobs.get_graph(group['id'])['aggregate']['status'], 'ready')

    def test_local_resume_preserves_children_and_does_not_replay_siblings(self):
        group = self.jobs.create_group('product:shoe', '批次')
        a = self.plan('A', parent_job_id=group['id'])
        b = self.plan('B', parent_job_id=group['id'], depends_on=[a['id']])
        self.complete(a)
        with patch('agent_jobs.shutil.which', return_value='/fake/codex'), \
             patch('agent_jobs.subprocess.Popen', side_effect=lambda command, **kw: Process(command, code=1)):
            self.jobs.dispatch(b['id'])
            join_job_threads(self.jobs, b['id'])
        self.assertEqual(self.jobs.get_graph(group['id'])['aggregate']['status'], 'needs_attention')
        with patch('agent_jobs.shutil.which', return_value='/fake/codex'), \
             patch('agent_jobs.subprocess.Popen', side_effect=lambda command, **kw: Process(command)):
            self.jobs.resume(b['id'], '核对已有成果后继续')
            join_job_threads(self.jobs, b['id'])
        self.assertEqual(self.jobs.get_job(a['id'])['attempt'], 1)
        self.assertEqual(self.jobs.get_job(b['id'])['attempt'], 2)
        self.assertEqual(self.jobs.get_graph(group['id'])['aggregate']['status'], 'completed')

    def test_cycle_missing_links_and_failure_rollback(self):
        a, b = self.plan('A'), self.plan('B')
        self.jobs.add_dependency(a['id'], b['id'])
        with self.assertRaises(ValueError): self.jobs.add_dependency(b['id'], a['id'])
        self.assertEqual(self.jobs.get_job(b['id'])['depends_on'], [])
        with self.assertRaises(ValueError): self.jobs.add_dependency(a['id'], a['id'])
        with self.assertRaises(ValueError): self.plan(parent_job_id='missing')
        with self.assertRaises(ValueError): self.plan(depends_on=['missing'])
        self.assertEqual(len(self.jobs.list_jobs()), 2)

    def test_idempotency_deduplicates_but_conflicting_payload_rejected(self):
        a = self.plan(idempotency_key='key')
        self.assertEqual(a['id'], self.plan(idempotency_key='key')['id'])
        with self.assertRaises(ValueError): self.plan('不同工作', idempotency_key='key')
        self.complete(a)
        self.assertEqual(self.plan(idempotency_key='key')['status'], 'completed')
        self.assertEqual(len(self.app.business.artifacts), 1)

    def test_idempotency_keeps_original_instruction_after_local_resume(self):
        job = self.plan('原始工作', idempotency_key='resume-key')
        with self.jobs._write():
            job.update(status='completed', instruction='续接时的新说明', attempt=2)
            self.jobs._save(job)
        self.assertEqual(self.plan('原始工作', idempotency_key='resume-key')['id'],job['id'])
        with self.assertRaises(ValueError):
            self.plan('续接时的新说明', idempotency_key='resume-key')

    def test_cancel_plan_and_failed_dependency_never_dispatch(self):
        a = self.plan()
        b = self.plan(depends_on=[a['id']])
        self.assertEqual(self.jobs.cancel(a['id'])['status'], 'cancelled')
        with self.assertRaises(ValueError): self.jobs.dispatch(b['id'])
        with self.assertRaises(ValueError): self.jobs.resume(b['id'], '继续')
        with self.assertRaises(ValueError): self.jobs.dispatch(a['id'])

    def test_legacy_rows_require_no_rewrite_or_migration(self):
        old = {'id':'old', 'object_id':'product:shoe', 'status':'completed', 'events':[], 'attempt':1}
        self.app.db.execute('INSERT INTO agent_jobs VALUES (?, ?)', ('old', json.dumps(old)))
        self.app.db.commit()
        self.assertEqual(AgentJobs(self.app).get_job('old'), old)
        child = self.plan(parent_job_id='old', depends_on=['old'])
        self.assertEqual(self.complete(child)['status'], 'completed')
        with self.assertRaises(ValueError): self.jobs.add_dependency(child['id'], 'old')

    def test_dead_owner_is_interrupted_without_replay_and_plans_survive(self):
        a = self.plan()
        child = self.plan(depends_on=[a['id']])
        with self.jobs._write():
            a.update(status='queued', owner_pid=123456789, worker_finished=False)
            self.jobs._save(a)
        with patch.object(AgentJobs, '_pid_alive', return_value=False):
            other = AgentJobs(self.app)
        self.assertEqual(other.get_job(a['id'])['status'], 'failed')
        self.assertEqual(other.get_job(child['id'])['status'], 'planned')
        with self.assertRaises(ValueError): other.dispatch(a['id'])
        with self.assertRaises(ValueError): other.dispatch(child['id'])

    def race(self, action, job_id=None):
        ctx = multiprocessing.get_context('spawn')
        gate, results = ctx.Event(), ctx.Queue()
        workers = [ctx.Process(target=competing, args=(self.tmp.name, action, job_id, gate, results)) for _ in range(2)]
        for worker in workers: worker.start()
        gate.set()
        output = [results.get(timeout=20) for _ in workers]
        for worker in workers:
            worker.join(20)
            self.assertEqual(worker.exitcode, 0)
        results.close()
        return output

    def test_independent_process_creation_deduplicates(self):
        output = self.race('create')
        self.assertEqual([row[0] for row in output], ['ok', 'ok'])
        self.assertEqual(output[0][1], output[1][1])
        self.assertEqual(len(self.jobs.list_jobs()), 1)

    def test_independent_process_dispatch_claims_only_once(self):
        job = self.plan()
        output = self.race('dispatch', job['id'])
        self.assertEqual(sorted(row[0] for row in output), ['error', 'ok'])


if __name__ == '__main__':
    unittest.main()
