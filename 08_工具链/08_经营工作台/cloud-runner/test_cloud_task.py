"""Native Cloud client offline tests; no credentials, network or model execution."""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

spec = importlib.util.spec_from_file_location('cloud_task', Path(__file__).with_name('cloud-task.py'))
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class CloudTaskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'state'
        content = 'one unique phrase'
        self.job = {'id': 'run-1', 'lease_token': 'private-lease',
                    'lease_expires_at': '2099-01-01T00:00:00Z', 'instruction': 'draft',
                    'source': 'a.md', 'document': {'path': 'a.md', 'content': content,
                    'hash': hashlib.sha256(content.encode()).hexdigest()}}
        self.queue = Mock()
        self.queue.call.return_value = {'job': self.job}

    def invoke(self, command, **kwargs):
        return client.perform(argparse.Namespace(command=command, run_id='run-1', **kwargs),
                              self.queue, self.root, 'proxy-placeholder-secret')

    def claim(self):
        return self.invoke('claim')

    def proposal(self):
        path = Path(self.temp.name) / 'result.json'
        result = {'summary': 'draft', 'changes': [{'path': 'a.md', 'before': 'unique',
                  'after': 'clear', 'reason': 'wording'}], 'next_steps': []}
        path.write_text(json.dumps(result), encoding='utf-8')
        path.chmod(0o600)
        return path, result

    def test_claim_redacts_lease_and_secret_even_in_document(self):
        self.job['instruction'] = 'private-lease proxy-placeholder-secret'
        output = self.claim()
        self.assertNotIn('private-lease', json.dumps(output))
        self.assertNotIn('proxy-placeholder-secret', json.dumps(output))
        self.assertEqual(output['run_id'], 'run-1')
        self.queue.call.assert_called_once_with('claim', run_id='run-1')
        path = self.root / 'run-1.json'
        self.assertIn('private-lease', path.read_text())
        if os.name != 'nt':
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(self.root.stat().st_mode & 0o777, 0o700)

    def test_duplicate_claim_never_calls_server_or_prints_task_again(self):
        self.claim()
        output = self.claim()
        self.assertEqual(output, {'run_id': 'run-1', 'status': 'claimed'})
        self.assertEqual(self.queue.call.call_count, 1)

    def test_uncertain_claim_is_not_replayed(self):
        self.queue.call.side_effect = RuntimeError('delivery unknown')
        with self.assertRaises(RuntimeError):
            self.claim()
        self.assertEqual(self.claim()['status'], 'claim_pending')
        self.assertEqual(self.queue.call.call_count, 1)

    def test_rejected_auth_allows_explicit_corrected_claim(self):
        self.queue.call.side_effect = HTTPError('https://queue', 401, 'Unauthorized', {}, None)
        with self.assertRaises(HTTPError):
            self.claim()
        self.assertEqual(self.invoke('status')['status'], 'claim_rejected')
        self.assertEqual(self.queue.call.call_count, 1)
        self.queue.call.side_effect = None
        self.queue.call.return_value = {'job': self.job}
        self.assertEqual(self.claim()['status'], 'claimed')
        self.assertEqual(self.queue.call.call_count, 2)

    def test_conflict_claim_is_not_reclaimed(self):
        self.queue.call.side_effect = HTTPError('https://queue', 409, 'Conflict', {}, None)
        with self.assertRaises(HTTPError):
            self.claim()
        self.assertEqual(self.claim()['status'], 'claim_rejected')
        self.assertEqual(self.queue.call.call_count, 1)

    def test_server_canonical_line_endings_are_accepted(self):
        self.claim()
        path, result = self.proposal()
        result['changes'][0]['after'] = 'new\r\ntext\rfinal'
        path.write_text(json.dumps(result))
        self.queue.call.return_value = {'run': {'id': 'run-1', 'status': 'awaiting_review',
                                              'result': client.canonical_result(result)}}
        self.assertEqual(self.invoke('complete', result=str(path), session_id=None)['status'], 'finished')

    def test_wrong_run_rejected(self):
        self.job['id'] = 'other'
        with self.assertRaises(ValueError):
            self.claim()
        self.assertEqual(self.invoke('status')['status'], 'claim_pending')

    def test_complete_requires_matching_server_proposal_readback(self):
        self.claim()
        path, result = self.proposal()
        self.queue.call.return_value = {'run': {'id': 'run-1', 'status': 'awaiting_review',
                                              'result': result}}
        self.assertEqual(self.invoke('complete', result=str(path), session_id='native-session')['status'], 'finished')
        self.queue.call.assert_called_with('complete', run_id='run-1', lease_token='private-lease',
                                          result=result, session_id='native-session')
        self.assertNotIn('lease', (self.root / 'run-1.json').read_text())
        with self.assertRaises(ValueError):
            self.invoke('heartbeat')

    def test_unconfirmed_submission_does_not_finish(self):
        self.claim()
        path, _ = self.proposal()
        self.queue.call.return_value = {'ok': True}
        with self.assertRaises(ValueError):
            self.invoke('complete', result=str(path), session_id=None)
        self.assertEqual(self.invoke('status')['status'], 'claimed')

    def test_real_validator_rejects_cross_source_and_no_source_changes(self):
        self.claim()
        path, result = self.proposal()
        result['changes'][0]['path'] = 'other.md'
        path.write_text(json.dumps(result))
        with self.assertRaisesRegex(ValueError, 'Cross-source'):
            self.invoke('complete', result=str(path), session_id=None)
        self.assertEqual(self.queue.call.call_count, 1)
        job = dict(self.job, source=None, document=None)
        with self.assertRaisesRegex(ValueError, 'without a source'):
            client.validate_result(job, result)

    def test_expired_lease_prevents_all_mutations(self):
        self.claim()
        path = self.root / 'run-1.json'
        state = json.loads(path.read_text())
        state['job']['lease_expires_at'] = '2000-01-01T00:00:00Z'
        client.write_state(path, state)
        with self.assertRaises(ValueError):
            self.invoke('heartbeat')
        self.assertEqual(self.queue.call.call_count, 1)

    def test_heartbeat_and_event(self):
        self.claim()
        self.queue.call.return_value = {'lease_expires_at': '2099-02-01T00:00:00Z'}
        self.invoke('heartbeat')
        self.invoke('event', message='draft in progress')
        self.queue.call.assert_called_with('event', run_id='run-1', lease_token='private-lease',
                                          event={'type': 'agent_progress', 'message': 'draft in progress'})

    def test_fail_readback(self):
        self.claim()
        self.queue.call.return_value = {'run': {'id': 'run-1', 'status': 'failed'}}
        self.assertEqual(self.invoke('fail', message='insufficient evidence')['status'], 'failed')

    def test_url_and_run_id_boundaries(self):
        for url in ('http://host', 'https://user:secret@host', 'https://host?secret=x'):
            with self.assertRaises(ValueError):
                client.Queue(url, 'placeholder')
        for run_id in ('../escape', '/absolute', 'a.b', ''):
            with self.assertRaises(ValueError):
                client.state_path(self.root, run_id)

    def test_commands_require_explicit_run_id(self):
        for command in ('claim', 'heartbeat', 'event', 'complete', 'fail', 'status'):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                client.parser().parse_args([command])

    @unittest.skipIf(os.name == 'nt', 'POSIX permission contract')
    def test_result_must_be_private(self):
        self.claim()
        path, _ = self.proposal()
        path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, 'private permissions'):
            self.invoke('complete', result=str(path), session_id=None)
        self.assertEqual(self.queue.call.call_count, 1)

    def test_status_does_not_require_credentials(self):
        self.claim()
        with patch.object(client, 'STATE_DIR', self.root), patch.dict(os.environ, {}, clear=True):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(client.main(['status', '--run-id', 'run-1']), 0)
        self.assertNotIn('lease', output.getvalue())

    def test_placeholder_secret_is_accepted_and_errors_do_not_leak(self):
        with patch.object(client, 'STATE_DIR', self.root), patch.dict(os.environ,
                {'WORKBENCH_RUNNER_SECRET': 'proxy-placeholder-secret'}, clear=True), \
                patch.object(client, 'Queue') as queue:
            queue.return_value.call.side_effect = RuntimeError('private-lease proxy-placeholder-secret')
            output = io.StringIO()
            with contextlib.redirect_stderr(output):
                self.assertEqual(client.main(['claim', '--run-id', 'run-1']), 1)
            queue.assert_called_once_with(client.DEFAULT_URL, 'proxy-placeholder-secret')
        self.assertNotIn('private-lease', output.getvalue())
        self.assertNotIn('proxy-placeholder-secret', output.getvalue())

    def test_missing_secret_prints_actionable_fixed_message(self):
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stderr(output):
            self.assertEqual(client.main(['claim', '--run-id', 'run-1']), 1)
        self.assertIn('Set WORKBENCH_RUNNER_SECRET', output.getvalue())


if __name__ == '__main__':
    unittest.main()
