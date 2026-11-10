import hashlib
import tempfile
import unittest
from pathlib import Path

from cloud_review import CloudReview


class FakeQueue:
    def __init__(self, run):
        self.run = run
        self.calls = []
    def call(self, action, **body):
        self.calls.append((action, body))
        if action == 'tasks':
            return {'tasks': [{'id': self.run['task_id'], 'title': '云端任务', 'source': self.run['source'],
                               'version': 1, 'source_version': self.run['source_version'], 'source_hash': self.run['source_hash']}]}
        if action == 'enqueue': return {'run': {'id': self.run['id'], 'task_id': self.run['task_id'], 'source': self.run['source'], 'status': 'queued'}}
        if action == 'request_status': return {'found': True, 'run': {'id': self.run['id'], 'task_id': self.run['task_id'], 'source': self.run['source'], 'status': 'queued'}}
        if action == 'pending_reviews':
            return {'runs': [{key: self.run.get(key) for key in ('id', 'title', 'summary', 'source', 'status', 'updated_at')}]}
        if action == 'status':
            return {'run': self.run.copy()}
        raise AssertionError('Unexpected cloud mutation')


class CloudReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = '00_总控台/当前状态.md'
        self.path = self.root / self.source
        self.path.parent.mkdir()
        self.path.write_text('旧成果\n', encoding='utf-8')
        self.state = self.root / 'private'
        self.state.mkdir()
        (self.state / 'cloud-bridge').mkdir()
        (self.state / 'cloud-bridge' / 'secret').write_text('fixture-secret-'+'x'*40, encoding='utf-8')
        self.run = {'id': 'a'*32, 'task_id': 'b'*32, 'title': '云端测试', 'status': 'awaiting_review',
                    'source': self.source, 'source_version': 2, 'source_hash': hashlib.sha256('旧成果\n'.encode()).hexdigest(),
                    'summary': '建议更新', 'updated_at': '2026-11-10T00:00:00Z',
                    'result': {'summary': '建议更新', 'next_steps': ['核对'],
                               'changes': [{'path': self.source, 'before': '旧成果', 'after': '新成果', 'reason': '测试'}]}}
        self.queue = FakeQueue(self.run)
        self.bridge = CloudReview(self.root, self.state, lambda endpoint, secret: self.queue)

    def test_list_preview_and_explicit_apply_reuse_original_source(self):
        self.assertEqual(self.bridge.list_pending()['runs'][0]['id'], self.run['id'])
        preview = self.bridge.preview(self.run['id'])
        self.assertIn('新成果', preview['diff'])
        self.assertEqual(self.path.read_text(encoding='utf-8'), '旧成果\n')
        result = self.bridge.apply(self.run['id'], preview['proposal_hash'])
        self.assertEqual(result['status'], 'applied')
        self.assertEqual(self.path.read_text(encoding='utf-8'), '新成果\n')
        self.assertEqual(self.bridge.apply(self.run['id'], preview['proposal_hash'])['status'], 'already_applied')
        self.assertTrue(all(action in ('pending_reviews', 'status') for action, _ in self.queue.calls))

    def test_local_edit_or_changed_cloud_proposal_blocks_write(self):
        preview = self.bridge.preview(self.run['id'])
        self.path.write_text('人工更新\n', encoding='utf-8')
        with self.assertRaises(ValueError): self.bridge.apply(self.run['id'], preview['proposal_hash'])
        self.assertTrue(self.bridge.preview(self.run['id'])['conflict'])
        self.assertEqual(self.path.read_text(encoding='utf-8'), '人工更新\n')

    def test_cloud_status_change_or_cross_source_is_not_applied(self):
        preview = self.bridge.preview(self.run['id'])
        self.run['status'] = 'rejected'
        with self.assertRaises(ValueError): self.bridge.apply(self.run['id'], preview['proposal_hash'])
        self.run['status'] = 'awaiting_review'
        self.run['result']['changes'][0]['path'] = '../outside.md'
        with self.assertRaises(ValueError): self.bridge.preview(self.run['id'])
        self.assertEqual(self.path.read_text(encoding='utf-8'), '旧成果\n')

    def test_inquiry_and_old_server_result_are_not_misrepresented(self):
        self.run['kind'] = 'inquiry_review'
        with self.assertRaises(ValueError): self.bridge.preview(self.run['id'])
        self.run.pop('kind')
        self.run.pop('source_version')
        with self.assertRaisesRegex(ValueError, '服务更新'): self.bridge.preview(self.run['id'])

    def test_local_task_snapshot_is_submitted_with_durable_request_identity(self):
        result = self.bridge.enqueue(self.run['task_id'], 1, 2, '只做内部分析', 'gpt-6-luna')
        self.assertEqual(result['run_id'], self.run['id'])
        self.assertEqual(self.bridge.dispatches()['dispatches'][0]['status'], 'confirmed')
        action, payload = next(call for call in self.queue.calls if call[0] == 'enqueue')
        self.assertEqual(payload['source_content'], '旧成果\n')
        self.assertEqual(payload['request_id'], result['request_id'])

    def test_lost_submit_response_is_persisted_and_reconciled_without_replay(self):
        real_call = self.queue.call
        def broken(action, **body):
            if action == 'enqueue': raise TimeoutError('private network detail')
            return real_call(action, **body)
        self.queue.call = broken
        with self.assertRaisesRegex(ValueError, '尚未确认'):
            self.bridge.enqueue(self.run['task_id'], 1, 2, '内部分析', 'gpt-6-luna')
        pending = self.bridge.dispatches()['dispatches'][0]
        self.assertEqual(pending['status'], 'pending')
        with self.assertRaisesRegex(ValueError, '未确认提交'):
            self.bridge.enqueue(self.run['task_id'], 1, 2, '再次提交', 'gpt-6-luna')
        result = self.bridge.reconcile_dispatch(pending['request_id'])
        self.assertEqual(result['status'], 'confirmed')
        self.assertEqual(result['run_id'], self.run['id'])
        self.assertEqual(self.bridge.dispatches()['dispatches'][0]['status'], 'confirmed')
        self.assertEqual([action for action, _ in self.queue.calls].count('request_status'), 1)

    def test_partial_local_request_journal_blocks_new_submission(self):
        directory = self.state/'cloud-bridge'/'dispatch'; directory.mkdir()
        (directory/('a'*32+'.json')).write_text('{',encoding='utf8')
        with self.assertRaisesRegex(ValueError, '记录不完整'):
            self.bridge.enqueue(self.run['task_id'], 1, 2, '内部分析', 'gpt-6-luna')


if __name__ == '__main__': unittest.main()
