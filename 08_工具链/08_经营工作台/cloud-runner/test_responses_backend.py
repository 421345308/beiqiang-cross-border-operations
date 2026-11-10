import io
import json
from datetime import datetime, timedelta, timezone
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

import responses_backend
import runner


def response(value):
    return io.BytesIO(json.dumps(value).encode())


def valid_response(proposal):
    return {'id': 'resp_test_123', 'status': 'completed', 'model': 'gpt-6-luna',
            'output': [{'type': 'reasoning'}, {'type': 'message', 'role': 'assistant',
                       'content': [{'type': 'output_text', 'text': json.dumps(proposal)}]}],
            'usage': {'input_tokens': 14, 'output_tokens': 8,
                      'input_tokens_details': {'cached_tokens': 2}}}


class ResponsesBackendTests(unittest.TestCase):
    def setUp(self):
        self.proposal = {'summary': '内部测试', 'changes': [], 'next_steps': []}
        self.input = {'source': None, 'instruction': 'test', 'document': ''}

    def call(self, value):
        return responses_backend.request_proposal(key='sk-fixture', model='gpt-6-luna',
            schema=runner.SCHEMA, input_data=self.input, open_request=lambda *a, **k: response(value))

    def test_fixed_endpoint_tool_free_request_and_usage_mapping(self):
        observed = {}
        def opener(request, timeout):
            observed['url'] = request.full_url
            observed['body'] = json.loads(request.data)
            observed['auth'] = request.get_header('Authorization')
            observed['timeout'] = timeout
            return response(valid_response(self.proposal))
        proposal, usage, receipt = responses_backend.request_proposal(
            key='sk-fixture', model='gpt-6-luna', schema=runner.SCHEMA,
            input_data=self.input, open_request=opener)
        self.assertEqual(observed['url'], 'https://api.openai.com/v1/responses')
        self.assertFalse(observed['body']['store'])
        self.assertNotIn('tools', observed['body'])
        self.assertTrue(observed['body']['text']['format']['strict'])
        self.assertNotIn('sk-fixture', json.dumps(observed['body']))
        self.assertEqual(observed['auth'], 'Bearer sk-fixture')
        self.assertEqual((proposal, receipt), (self.proposal, 'resp_test_123'))
        self.assertEqual(usage, {'input_tokens': 14, 'cached_input_tokens': 2, 'output_tokens': 8})

    def test_refusal_incomplete_and_unexpected_tool_call_fail_closed(self):
        values = [dict(valid_response(self.proposal), status='incomplete'),
                  dict(valid_response(self.proposal), output=[{'type': 'function_call'}]),
                  dict(valid_response(self.proposal), output=[{'type': 'message', 'role': 'assistant',
                        'content': [{'type': 'refusal', 'refusal': 'private'}]}]),
                  dict(valid_response(self.proposal), id=None)]
        for value in values:
            with self.subTest(value=value), self.assertRaises(responses_backend.ResponsesError):
                self.call(value)

    def test_http_errors_do_not_expose_response_body_or_credential(self):
        def fail(request, timeout):
            raise HTTPError(request.full_url, 401, 'private', {}, io.BytesIO(b'private-secret'))
        with self.assertRaises(responses_backend.ResponsesError) as err:
            responses_backend.request_proposal(key='sk-private', model='gpt-6-luna',
                schema=runner.SCHEMA, input_data=self.input, open_request=fail)
        self.assertIn('401', str(err.exception))
        self.assertNotIn('private', str(err.exception))

    def test_lease_expiry_prevents_submission(self):
        job = {'id': 'a' * 32, 'lease_token': 'fixture',
               'lease_expires_at': (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
               'instruction': 'test', 'source': None, 'document': None, 'model': 'gpt-6-luna'}
        queue = Mock()
        with tempfile.TemporaryDirectory() as state, \
             patch.dict(runner.os.environ, {'WORKBENCH_RUNNER_ENGINE': 'responses'}), \
             patch('preflight.read_api_credential', return_value='sk-fixture'), \
             patch('responses_backend.request_proposal', return_value=(self.proposal, {}, 'resp_test')), \
             patch.object(runner.time, 'time', return_value=datetime.now(timezone.utc).timestamp()+3600):
            with self.assertRaisesRegex(RuntimeError, 'lease expired'):
                runner.execute(queue, job, None, state)
        self.assertEqual([c.args[0] for c in queue.call.call_args_list], ['event'])

    def test_complete_acknowledgement_must_match_result(self):
        queue = Mock()
        identity = {'run_id': 'a'*32, 'lease_token': 'fixture'}
        queue.call.return_value = {'run': {'id': identity['run_id'], 'status': 'awaiting_review', 'result': self.proposal}}
        runner.submit_result(queue, identity, self.proposal, 'resp_test', {})
        queue.call.return_value = {'run': {'id': identity['run_id'], 'status': 'awaiting_review', 'result': {'summary': 'different'}}}
        with self.assertRaisesRegex(RuntimeError, 'reconcile'):
            runner.submit_result(queue, identity, self.proposal, 'resp_test', {})


if __name__ == '__main__':
    unittest.main()
