"""Typed inquiry workflow, source binding and uncertain-response recovery."""
import importlib.util
import json
from pathlib import Path
import unittest
import test_cloud_task as fixtures
from runner import validate_job, validate_result, model_input, result_schema

spec = importlib.util.spec_from_file_location('inquiry_cloud_client', Path(__file__).with_name('cloud-task.py'))
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)

class InquiryClientTests(unittest.TestCase):
    setUp = fixtures.CloudTaskTests.setUp
    invoke = fixtures.CloudTaskTests.invoke
    claim = fixtures.CloudTaskTests.claim
    def inquiry(self):
        self.job.update(kind='inquiry_review', source=None, document=None,
                        inquiry_reference='BQ-20261030-TEST0001', source_hash='a' * 64, handling_version=2)
        self.job['inquiry_context'] = {'inquiry': {'reference': self.job['inquiry_reference'], 'requirements': 'Need sizes'},
                                     'handling': {'version': 2}, 'source_hash': 'a' * 64, 'handling_version': 2}
        return self.job

    def inquiry_result(self):
        return {'summary': '需要确认尺码', 'changes': [], 'next_steps': ['确认尺码'],
                'fields': {'internal_note': '尚缺尺码与数量', 'next_action': '准备澄清草稿', 'handling_status': 'open'}}

    def test_inquiry_source_binding(self):
        job = self.inquiry()
        self.assertGreater(validate_job(job), 0)
        self.assertEqual(model_input(job)['inquiry_context'], job['inquiry_context'])
        self.assertIn('fields', result_schema(job)['required'])
        for key, value in [('inquiry_reference', 'other'), ('source_hash', 'b' * 64), ('handling_version', 3)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_job(dict(job, **{key: value}))

    def test_inquiry_result_cannot_modify_other_fields(self):
        job, result = self.inquiry(), self.inquiry_result()
        self.assertEqual(validate_result(job, result), result)
        invalid = [dict(result, changes=[{'path': 'other.md'}]), dict(result, send_email=True),
                   dict(result, fields=dict(result['fields'], status='sent')),
                   dict(result, fields=dict(result['fields'], internal_note='a' * 6001))]
        for value in invalid:
            with self.assertRaises(ValueError): validate_result(job, value)

    def test_inquiry_claim_includes_context_and_typed_schema(self):
        self.inquiry()
        output = self.claim()
        self.assertEqual(output['kind'], 'inquiry_review')
        self.assertEqual(output['inquiry_context']['handling_version'], 2)
        self.assertIn('fields', output['result_schema']['required'])

    def test_inquiry_whitespace_matches_server_canonical_result(self):
        self.inquiry(); self.claim()
        path = Path(self.temp.name) / 'result.json'
        raw = self.inquiry_result()
        raw['summary'] = '  需要确认尺码\n'
        raw['next_steps'] = [' 确认尺码 ']
        raw['fields']['internal_note'] = ' 尚缺尺码与数量 '
        path.write_text(json.dumps(raw), encoding='utf-8'); path.chmod(0o600)
        self.queue.call.return_value = {'run': {'id': 'run-1', 'status': 'awaiting_review', 'result': self.inquiry_result()}}
        self.assertEqual(self.invoke('complete', result=str(path), session_id=None)['status'], 'finished')

    def test_uncertain_completion_recovers_only_by_matching_readback(self):
        self.inquiry(); self.claim()
        path = Path(self.temp.name) / 'result.json'
        result = self.inquiry_result()
        path.write_text(json.dumps(result), encoding='utf-8'); path.chmod(0o600)
        self.queue.call.side_effect = RuntimeError('response lost')
        with self.assertRaises(RuntimeError): self.invoke('complete', result=str(path), session_id='actual-session')
        self.assertEqual(self.invoke('status')['status'], 'claimed')
        self.queue.call.side_effect = None
        self.queue.call.return_value = {'run': {'id': 'run-1', 'status': 'awaiting_review', 'result': result}}
        self.assertEqual(self.invoke('status', remote=True)['status'], 'finished')
        self.queue.call.assert_called_with('status', run_id='run-1')
        self.assertNotIn('lease', (self.root / 'run-1.json').read_text())

    def test_inquiry_fields_readback_mismatch_does_not_finish(self):
        self.inquiry(); self.claim()
        path = Path(self.temp.name) / 'result.json'
        result = self.inquiry_result()
        path.write_text(json.dumps(result), encoding='utf-8'); path.chmod(0o600)
        self.queue.call.return_value = {'run': {'id': 'run-1', 'status': 'awaiting_review',
            **{key: result[key] for key in ('summary', 'changes', 'next_steps')},
            'result': dict(result, fields=dict(result['fields'], handling_status='handled'))}}
        with self.assertRaises(ValueError): self.invoke('complete', result=str(path), session_id=None)

    def test_uncertain_claim_status_does_not_reclaim(self):
        self.queue.call.side_effect = RuntimeError('response lost')
        with self.assertRaises(RuntimeError): self.claim()
        self.queue.call.side_effect = None
        self.queue.call.return_value = {'run': {'id': 'run-1', 'status': 'running'}}
        output = self.invoke('status', remote=True)
        self.assertTrue(output['needs_owner_cancel'])
        self.assertEqual(output['status'], 'claim_pending')
        self.queue.call.assert_called_with('status', run_id='run-1')

if __name__ == '__main__': unittest.main()
