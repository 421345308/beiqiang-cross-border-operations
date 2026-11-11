import json
import multiprocessing
import os
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent_jobs import AgentJobs
from tests_agent_jobs import Business, Process, join_job_threads
from workspaces import WorkspaceConflict


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
        elif action == 'priority':
            jobs._work = lambda *args: None
            group_id, expected_id, expected_version = job_id
            result = jobs.dispatch_priority_next(group_id, expected_id, expected_version)
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

    def test_priority_preview_orders_eligible_plans_without_starting_them(self):
        group = self.jobs.create_group('product:shoe', '分组')
        low = self.plan('先建低优先级', parent_job_id=group['id'])
        normal = self.plan('普通', parent_job_id=group['id'])
        blocked = self.plan('受阻高优先级', parent_job_id=group['id'], depends_on=[normal['id']])
        high = self.plan('高优先级', parent_job_id=group['id'])
        low = self.jobs.adjust(low['id'], expected_version=low['version'], priority='low')
        blocked = self.jobs.adjust(blocked['id'], expected_version=blocked['version'], priority='high')
        high = self.jobs.adjust(high['id'], expected_version=high['version'], priority='high')
        preview = self.jobs.preview_priority_dispatch(group['id'])
        self.assertEqual(preview['candidate']['id'], high['id'])
        self.assertEqual((preview['ready_count'], preview['blocked_count']), (3, 1))
        self.assertTrue(all(self.jobs.get_job(j['id'])['status']=='planned' for j in (low,normal,blocked,high)))
        self.assertFalse(self.jobs.threads)
        high = self.jobs.adjust(high['id'], expected_version=high['version'], priority='low')
        self.assertEqual(self.jobs.preview_priority_dispatch(group['id'])['candidate']['id'], normal['id'])

    def test_priority_preview_ties_use_creation_order_and_reject_non_group(self):
        group = self.jobs.create_group('product:shoe', '分组')
        first = self.plan('最先创建', parent_job_id=group['id'])
        second = self.plan('后创建', parent_job_id=group['id'])
        self.assertEqual(self.jobs.preview_priority_dispatch(group['id'])['candidate']['id'], first['id'])
        with self.assertRaises(ValueError): self.jobs.preview_priority_dispatch(first['id'])
        with self.jobs._write():
            row = self.jobs.get_job(first['id']); row.update(status='completed', attempt=1)
            self.jobs._save(row)
        self.assertEqual(self.jobs.preview_priority_dispatch(group['id'])['candidate']['id'], second['id'])

    def test_standalone_scope_excludes_groups_children_and_blocked_plans(self):
        group = self.jobs.create_group('product:shoe', '分组')
        nested = self.plan('分组里的工作', parent_job_id=group['id'])
        nested = self.jobs.adjust(nested['id'], expected_version=nested['version'], priority='high')
        first = self.plan('独立普通任务')
        blocked = self.plan('未满足前置的独立任务', depends_on=[nested['id']])
        blocked = self.jobs.adjust(blocked['id'], expected_version=blocked['version'], priority='high')
        high = self.plan('独立高优先级')
        high = self.jobs.adjust(high['id'], expected_version=high['version'], priority='high')
        preview = self.jobs.preview_priority_dispatch('standalone')
        self.assertEqual(preview['scope'], 'standalone')
        self.assertEqual(preview['group_id'], 'standalone')
        self.assertEqual(preview['candidate']['id'], high['id'])
        self.assertEqual((preview['ready_count'], preview['blocked_count']), (2, 1))
        self.assertEqual(self.jobs.preview_priority_dispatch(group['id'])['candidate']['id'], nested['id'])
        self.assertTrue(all(self.jobs.get_job(j['id'])['status']=='planned' for j in (first,blocked,high,nested)))

    def test_standalone_priority_rechecks_candidate_and_never_replays(self):
        first = self.plan('第一个独立工作')
        second = self.plan('第二个独立工作')
        old = self.jobs.preview_priority_dispatch('standalone')['candidate']
        second = self.jobs.adjust(second['id'], expected_version=second['version'], priority='high')
        with self.assertRaises(WorkspaceConflict):
            self.jobs.dispatch_priority_next('standalone', old['id'], old['version'])
        self.assertEqual(self.jobs.get_job(first['id'])['status'], 'planned')
        current = self.jobs.preview_priority_dispatch('standalone')['candidate']
        with patch.object(self.jobs, '_work', return_value=None) as worker:
            started = self.jobs.dispatch_priority_next('standalone', current['id'], current['version'])
            join_job_threads(self.jobs, started['id'])
        self.assertEqual(started['id'], second['id'])
        self.assertEqual(worker.call_count, 1)
        with self.assertRaises(WorkspaceConflict):
            self.jobs.dispatch_priority_next('standalone', current['id'], current['version'])
        self.assertEqual(self.jobs.get_job(first['id'])['status'], 'planned')

    def test_standalone_scope_keeps_object_guard_and_does_not_skip(self):
        running = self.plan('运行中')
        first = self.plan('优先任务')
        other = self.plan('其他任务')
        first = self.jobs.adjust(first['id'], expected_version=first['version'], priority='high')
        with self.jobs._write():
            running.update(status='running', owner_pid=os.getpid(), worker_finished=False)
            self.jobs._save(running)
        preview = self.jobs.preview_priority_dispatch('standalone')['candidate']
        self.assertEqual(preview['id'], first['id'])
        with self.assertRaisesRegex(ValueError, '已有工作正在执行'):
            self.jobs.dispatch_priority_next('standalone', preview['id'], preview['version'])
        self.assertEqual(self.jobs.get_job(running['id'])['status'], 'running')
        self.assertEqual(self.jobs.get_job(first['id'])['status'], 'planned')
        self.assertEqual(self.jobs.get_job(other['id'])['status'], 'planned')

    def test_standalone_scope_excludes_and_reports_batch_research(self):
        with patch.object(self.app.business, 'get_object', side_effect=lambda oid: {'id':oid,'kind':'customer'}):
            restricted = self.jobs.start('customer:buyer', '批次研究', mode='outreach_research',
                                         batch_id='a'*32, defer=True)
        restricted = self.jobs.adjust(restricted['id'], expected_version=restricted['version'], priority='high')
        allowed = self.plan('独立普通任务')
        preview = self.jobs.preview_priority_dispatch('standalone')
        self.assertEqual(preview['candidate']['id'], allowed['id'])
        self.assertEqual(preview['restricted_count'], 1)
        self.assertIn('回原批次继续', preview['reason'])
        with self.assertRaises(WorkspaceConflict):
            self.jobs.dispatch_priority_next('standalone', restricted['id'], restricted['version'])
        self.assertEqual(self.jobs.get_job(restricted['id'])['status'], 'planned')

    def test_priority_dispatch_claims_preview_and_never_replays_or_starts_another(self):
        group = self.jobs.create_group('product:shoe', '分组')
        first = self.plan('先选', parent_job_id=group['id'])
        other = self.plan('另一个', parent_job_id=group['id'])
        chosen = self.jobs.preview_priority_dispatch(group['id'])['candidate']
        with patch.object(self.jobs, '_work', return_value=None) as worker:
            started = self.jobs.dispatch_priority_next(group['id'], chosen['id'], chosen['version'])
            join_job_threads(self.jobs, started['id'])
        self.assertEqual(started['id'], first['id'])
        self.assertEqual(self.jobs.get_job(first['id'])['status'], 'queued')
        self.assertEqual(self.jobs.get_job(other['id'])['status'], 'planned')
        self.assertEqual(worker.call_count, 1)
        with self.assertRaises(WorkspaceConflict):
            self.jobs.dispatch_priority_next(group['id'], chosen['id'], chosen['version'])
        self.assertEqual(self.jobs.get_job(other['id'])['status'], 'planned')

    def test_priority_candidate_or_version_changes_reject_without_starting(self):
        group = self.jobs.create_group('product:shoe', '分组')
        first = self.plan('最先', parent_job_id=group['id'])
        preview = self.jobs.preview_priority_dispatch(group['id'])['candidate']
        self.jobs.adjust(first['id'], expected_version=preview['version'], next_action='新的人工作用')
        with self.assertRaises(WorkspaceConflict):
            self.jobs.dispatch_priority_next(group['id'], preview['id'], preview['version'])
        preview = self.jobs.preview_priority_dispatch(group['id'])['candidate']
        higher = self.plan('后建高优先级', parent_job_id=group['id'])
        self.jobs.adjust(higher['id'], expected_version=higher['version'], priority='high')
        with self.assertRaises(WorkspaceConflict):
            self.jobs.dispatch_priority_next(group['id'], preview['id'], preview['version'])
        self.assertEqual(self.jobs.get_job(first['id'])['status'], 'planned')
        self.assertEqual(self.jobs.get_job(higher['id'])['status'], 'planned')
        self.assertFalse(self.jobs.threads)

    def test_direct_dispatch_rejects_stale_or_invalid_expected_version(self):
        job = self.plan('需要核对版本')
        stale = job['version']
        revised = self.jobs.adjust(job['id'], expected_version=stale, next_action='新的安排')
        for version in (stale, -1, True, str(revised['version'])):
            with self.subTest(version=version):
                with self.assertRaises(WorkspaceConflict):
                    self.jobs.dispatch(job['id'], expected_version=version)
                self.assertEqual(self.jobs.get_job(job['id'])['status'], 'planned')
                self.assertFalse(self.jobs.threads)
        with patch.object(self.jobs, '_work', return_value=None) as worker:
            accepted = self.jobs.dispatch(job['id'], expected_version=revised['version'])
            join_job_threads(self.jobs, accepted['id'])
        self.assertEqual(accepted['status'], 'queued')
        self.assertEqual(worker.call_count, 1)

    def test_new_dependency_after_preview_rejects_stale_candidate(self):
        group = self.jobs.create_group('product:shoe', '分组')
        child = self.plan('待启动', parent_job_id=group['id'])
        dependency = self.plan('外部分组前置')
        preview = self.jobs.preview_priority_dispatch(group['id'])['candidate']
        self.jobs.add_dependency(child['id'], dependency['id'])
        self.assertIsNone(self.jobs.preview_priority_dispatch(group['id'])['candidate'])
        with self.assertRaises(WorkspaceConflict):
            self.jobs.dispatch_priority_next(group['id'], preview['id'], preview['version'])
        self.assertEqual(self.jobs.get_job(child['id'])['status'], 'planned')
        with self.jobs._write():
            row = self.jobs.get_job(dependency['id']);row.update(status='completed', attempt=1)
            self.jobs._save(row)
        self.assertEqual(self.jobs.preview_priority_dispatch(group['id'])['candidate']['id'], child['id'])

    def test_priority_dispatch_respects_object_occupancy_without_skipping(self):
        group = self.jobs.create_group('product:shoe', '分组')
        running = self.plan('已有工作')
        first = self.plan('高优先级', parent_job_id=group['id'])
        other = self.plan('另一项', parent_job_id=group['id'])
        first = self.jobs.adjust(first['id'], expected_version=first['version'], priority='high')
        with self.jobs._write():
            running.update(status='running', owner_pid=os.getpid(), worker_finished=False)
            self.jobs._save(running)
        preview = self.jobs.preview_priority_dispatch(group['id'])['candidate']
        self.assertEqual(preview['id'], first['id'])
        with self.assertRaisesRegex(ValueError, '已有工作正在执行'):
            self.jobs.dispatch_priority_next(group['id'], preview['id'], preview['version'])
        self.assertEqual(self.jobs.get_job(running['id'])['status'], 'running')
        self.assertEqual(self.jobs.get_job(first['id'])['status'], 'planned')
        self.assertEqual(self.jobs.get_job(other['id'])['status'], 'planned')

    def test_priority_dispatch_does_not_bypass_customer_batch_entry(self):
        group = self.jobs.create_group('product:shoe', '批次', batch_id='a'*32,
                                       context={'type':'customer_batch_research'})
        with patch.object(self.app.business, 'get_object', side_effect=lambda oid: {'id':oid,'kind':'customer'}):
            child = self.jobs.start('customer:buyer', '研究', mode='outreach_research', batch_id='a'*32,
                                    parent_job_id=group['id'])
            preview = self.jobs.preview_priority_dispatch(group['id'])['candidate']
            with self.assertRaisesRegex(ValueError, '回到原批次继续'):
                self.jobs.dispatch_priority_next(group['id'], preview['id'], preview['version'])
        self.assertEqual(self.jobs.get_job(child['id'])['status'], 'planned')

    def test_priority_dispatch_keeps_specialized_batch_guard(self):
        group = self.jobs.create_group('product:shoe', '受控分组',
                                       context={'type':'customer_batch_research'})
        self.app.batch_research = SimpleNamespace(check_dispatch=lambda job,obj: (_ for _ in ()).throw(ValueError('禁止联系')))
        with patch.object(self.app.business, 'get_object', side_effect=lambda oid: {'id':oid,'kind':'customer'}):
            child = self.jobs.start('customer:buyer', '研究', mode='outreach_research', parent_job_id=group['id'])
            other = self.jobs.start('customer:other', '研究', mode='outreach_research', parent_job_id=group['id'])
            preview = self.jobs.preview_priority_dispatch(group['id'])['candidate']
            self.assertEqual(preview['id'], child['id'])
            with self.assertRaisesRegex(ValueError, '禁止联系'):
                self.jobs.dispatch_priority_next(group['id'], preview['id'], preview['version'])
        self.assertEqual(self.jobs.get_job(child['id'])['status'], 'planned')
        self.assertEqual(self.jobs.get_job(other['id'])['status'], 'planned')

    def test_priority_dispatch_thread_start_failure_is_recorded_without_retry(self):
        group = self.jobs.create_group('product:shoe', '分组')
        child = self.plan('待执行', parent_job_id=group['id'])
        preview = self.jobs.preview_priority_dispatch(group['id'])['candidate']
        with patch('job_dependencies.threading.Thread.start', side_effect=RuntimeError('fixture')):
            with self.assertRaises(RuntimeError):
                self.jobs.dispatch_priority_next(group['id'], preview['id'], preview['version'])
        stored = self.jobs.get_job(child['id'])
        self.assertEqual(stored['status'], 'failed')
        self.assertTrue(stored['worker_finished'])
        self.assertIsNone(self.jobs.preview_priority_dispatch(group['id'])['candidate'])

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

    def test_independent_priority_dispatch_claims_only_previewed_job_once(self):
        group = self.jobs.create_group('product:shoe', '分组')
        first = self.plan('第一项', parent_job_id=group['id'])
        other = self.plan('第二项', parent_job_id=group['id'])
        preview = self.jobs.preview_priority_dispatch(group['id'])['candidate']
        output = self.race('priority', (group['id'], preview['id'], preview['version']))
        self.assertEqual(sorted(row[0] for row in output), ['error', 'ok'])
        self.assertEqual(next(row[1] for row in output if row[0]=='ok'), first['id'])
        self.assertEqual(self.jobs.get_job(other['id'])['status'], 'planned')

    def test_independent_standalone_priority_claims_only_previewed_job_once(self):
        first = self.plan('第一项独立工作')
        other = self.plan('第二项独立工作')
        preview = self.jobs.preview_priority_dispatch('standalone')['candidate']
        output = self.race('priority', ('standalone', preview['id'], preview['version']))
        self.assertEqual(sorted(row[0] for row in output), ['error', 'ok'])
        self.assertEqual(next(row[1] for row in output if row[0]=='ok'), first['id'])
        self.assertEqual(self.jobs.get_job(other['id'])['status'], 'planned')


if __name__ == '__main__':
    unittest.main()
