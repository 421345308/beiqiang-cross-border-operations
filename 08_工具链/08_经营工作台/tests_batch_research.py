import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent_jobs import AgentJobs
from batch_research import BatchResearch
from workspaces import WorkspaceConflict


class Business:
    def get_object(self, object_id):
        if object_id not in ('customer:a', 'customer:b'):
            raise ValueError('对象不存在')
        return {'id': object_id, 'kind': 'customer', 'title': object_id}


class Batches:
    def __init__(self):
        self.batch = {'id': 'a'*32, 'revision': 'r1', 'items': [
            {'object_id': oid, 'review_state': 'pending', 'quality': {'suppression_state': 'clear'},
             'checks': {'status': 'clear'}} for oid in ('customer:a', 'customer:b')]}
    def get(self, batch_id):
        if batch_id != self.batch['id']:
            raise ValueError('批次不存在')
        return self.batch
    _load = get


class BatchResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = SimpleNamespace(root=Path(self.tmp.name), state=Path(self.tmp.name), lock=threading.RLock(),
            db=sqlite3.connect(str(Path(self.tmp.name)/'jobs.sqlite3'), check_same_thread=False),
            business=Business(), customer_batches=Batches())
        self.app.agent_jobs = AgentJobs(self.app)
        self.service = BatchResearch(self.app)
        self.app.batch_research = self.service
        self.app.db.execute('CREATE TABLE customer_contact_suppressions (key TEXT PRIMARY KEY, object_id TEXT, batch_id TEXT, created_at TEXT)')
        self.app.db.commit()
        self.body = {'batch_id':'a'*32, 'revision':'r1', 'object_ids':['customer:a','customer:b'],
                     'instruction':'研究各客户', 'request_id':'b'*32}
        # Preserve the claimed state without launching a real model or touching business data.
        self.work = patch.object(self.app.agent_jobs, '_work', lambda *_: None)
        self.work.start()

    def tearDown(self):
        for thread in list(self.app.agent_jobs.threads.values()):
            thread.join(5)
        self.work.stop(); self.app.db.close(); self.tmp.cleanup()

    def test_repeated_request_uses_same_children_and_does_not_replay(self):
        first = self.service.begin(self.body)
        self.assertEqual([row['status'] for row in first['results']], ['started','started'])
        self.assertEqual(len(first['group']['jobs']), 2)
        self.app.customer_batches.batch['revision'] = 'r2'
        second = self.service.begin(self.body)
        self.assertEqual(second['group_id'], first['group_id'])
        self.assertEqual([row['status'] for row in second['results']], ['existing','existing'])
        self.assertEqual(len(self.app.agent_jobs.list_jobs()), 3)
        with self.assertRaises(ValueError):
            self.service.begin({**self.body, 'instruction':'不同要求'})
        with self.assertRaises(WorkspaceConflict):
            self.service.begin({**self.body, 'request_id':'c'*32})

    def test_interrupted_planning_can_continue_missing_without_replaying_started(self):
        real_start = self.app.agent_jobs.start
        def interrupted(oid, instruction, *args, **kwargs):
            if oid == 'customer:b' and kwargs.get('parent_job_id'):
                raise RuntimeError('simulated interruption')
            return real_start(oid, instruction, *args, **kwargs)
        with patch.object(self.app.agent_jobs, 'start', side_effect=interrupted):
            with self.assertRaises(RuntimeError): self.service.begin(self.body)
        groups = self.service.list_groups(self.body['batch_id'])['items']
        self.assertEqual(groups[0]['not_planned'], ['customer:b'])
        old_child = groups[0]['jobs'][0]['id']
        # An independently constructed service reads the persisted task graph.
        resumed = BatchResearch(self.app).continue_group(groups[0]['id'])
        self.assertEqual([row['status'] for row in resumed['results']], ['existing','started'])
        self.assertEqual(resumed['results'][0]['job']['id'], old_child)
        self.assertEqual(resumed['group']['not_planned'], [])
        self.assertEqual(len(self.app.agent_jobs.list_jobs()), 3)

    def test_recovery_rechecks_current_membership_and_contact_stop(self):
        self.app.customer_batches.batch['items'][1]['review_state'] = 'do_not_contact'
        first = self.service.begin(self.body)
        self.assertEqual([row['status'] for row in first['results']], ['started','blocked'])
        self.app.customer_batches.batch['items'] = self.app.customer_batches.batch['items'][:1]
        again = self.service.continue_group(first['group_id'])
        self.assertEqual(again['results'][1]['status'], 'blocked')
        self.assertIn('不在当前批次', again['results'][1]['reason'])
        self.assertEqual(len(again['group']['jobs']), 1)

    def test_unavailable_first_customer_does_not_block_independent_second(self):
        original=self.app.business.get_object
        def get_object(oid):
            if oid=='customer:a': raise ValueError('原客户暂不可读取')
            return original(oid)
        with patch.object(self.app.business,'get_object',side_effect=get_object):
            result=self.service.begin(self.body)
        self.assertEqual([row['status'] for row in result['results']],['not_started','started'])
        self.assertEqual(result['group']['not_planned'],['customer:a'])

    def test_removed_or_suppressed_after_planning_cannot_be_dispatched(self):
        for change in ('remove','suppress'):
            with self.subTest(change=change):
                # Give each scenario a distinct request and reset the synthetic batch.
                self.app.customer_batches = Batches()
                request={**self.body,'request_id':('c' if change=='remove' else 'd')*32}
                original=self.app.agent_jobs.start
                def start_then_change(oid,instruction,*args,**kwargs):
                    job=original(oid,instruction,*args,**kwargs)
                    if oid=='customer:a' and kwargs.get('parent_job_id'):
                        if change=='remove':
                            self.app.customer_batches.batch['items']=self.app.customer_batches.batch['items'][1:]
                        else:
                            self.app.customer_batches.batch['items'][0]['review_state']='do_not_contact'
                    return job
                with patch.object(self.app.agent_jobs,'start',side_effect=start_then_change):
                    result=self.service.begin(request)
                self.assertEqual(result['results'][0]['status'],'not_started')
                self.assertEqual(next(j for j in result['group']['jobs'] if j['object_id']=='customer:a')['status'],'planned')
                self.assertIn('不在当前批次' if change=='remove' else '不联系',result['results'][0]['reason'])
                self.assertNotEqual(result['group']['aggregate']['status'],'completed')
                self.assertIn('customer:a',result['group']['last_reasons'])

    def test_unplanned_customer_prevents_a_false_completed_group(self):
        self.app.customer_batches.batch['items'][1]['review_state']='do_not_contact'
        result=self.service.begin(self.body)
        first=result['results'][0]['job']
        with self.app.agent_jobs._write():
            first.update(status='completed',attempt=1,worker_finished=True)
            self.app.agent_jobs._save(first)
        group=self.service.describe(result['group_id'])
        self.assertEqual(group['aggregate']['status'],'incomplete')
        self.assertEqual(group['aggregate']['requested_total'],2)
        self.assertEqual(group['not_planned'],['customer:b'])
        self.assertIn('不联系',group['last_reasons']['customer:b'])

    def test_address_suppression_is_rechecked_at_claim(self):
        self.app.gmail_drafts=SimpleNamespace(_saved=lambda oid:{'to':'buyer@example.test'} if oid=='customer:a' else None)
        original=self.app.agent_jobs.start
        def start_then_suppress(oid,instruction,*args,**kwargs):
            job=original(oid,instruction,*args,**kwargs)
            if oid=='customer:a' and kwargs.get('parent_job_id'):
                self.app.db.execute('INSERT INTO customer_contact_suppressions VALUES (?,?,?,?)',
                    ('email:buyer@example.test','customer:other','other','now'))
                self.app.db.commit()
            return job
        with patch.object(self.app.agent_jobs,'start',side_effect=start_then_suppress):
            result=self.service.begin(self.body)
        self.assertEqual(result['results'][0]['status'],'not_started')
        self.assertIn('不联系',result['results'][0]['reason'])
        self.assertEqual(result['results'][1]['status'],'started')

    def test_cancelled_group_cannot_launch_a_planned_child(self):
        group = self.app.agent_jobs.create_group('customer:a','group')
        child = self.app.agent_jobs.start('customer:b','work',parent_job_id=group['id'])
        self.app.agent_jobs.cancel(group['id'])
        with self.assertRaisesRegex(ValueError, '父任务已取消'):
            self.app.agent_jobs.dispatch(child['id'])


if __name__ == '__main__':
    unittest.main()
