"""Synthetic external-turn chain through the MCP dispatcher and isolated HTTP.

The caller assertions below stand in for read_thread output. No external
conversation is read, no message is sent, and no Codex process is started.
The fixture binds a random loopback port and uses temporary business data.
"""
import hashlib
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import urlencode

from desk_mcp import DeskTools, LocalOverviewClient, OVERVIEW_OBJECT, dispatch
import tests_desk_http as fixture


THREAD = '12345678-1234-4234-8234-123456789abc'
HOST = 'synthetic-host'
SOURCE = 'codex_app.read_thread'


class ExternalHTTPIntegrationTests(unittest.TestCase):
    tearDown = fixture.DeskHTTPTests.tearDown
    write = fixture.DeskHTTPTests.write
    request = fixture.DeskHTTPTests.request

    def setUp(self):
        fixture.DeskHTTPTests.setUp(self)
        self.assertNotEqual(self.http.server_port, 8766)
        self.tools = DeskTools(None, self.root, OVERVIEW_OBJECT)
        origin = 'http://127.0.0.1:' + str(self.http.server_port)
        origin_patch = patch.object(LocalOverviewClient, 'origin', origin)
        origin_patch.start()
        self.addCleanup(origin_patch.stop)
        self.base = datetime.now(timezone.utc) - timedelta(minutes=3)

    def moment(self, seconds):
        return (self.base + timedelta(seconds=seconds)).isoformat()

    def mcp_result(self, name, arguments):
        envelope = dispatch(self.tools, {'jsonrpc':'2.0', 'id':1, 'method':'tools/call',
            'params':{'name':name, 'arguments':arguments}})
        result = envelope['result']
        return result, json.loads(result['content'][0]['text'])

    def call(self, name, arguments):
        result, value = self.mcp_result(name, arguments)
        self.assertFalse(result['isError'], (name, value))
        return value

    def conflict(self, name, arguments):
        result, value = self.mcp_result(name, arguments)
        self.assertTrue(result['isError'], (name, value))
        self.assertEqual(value['code'], 'version_conflict')

    def context(self, job_id):
        status, result = self.request('/api/desk/task-context?' + urlencode({'id':job_id}))
        self.assertEqual(status, 200)
        return result

    def planned_bound_task(self):
        job = self.app.agent_jobs.start('product:BQ009', 'synthetic business goal', defer=True)
        self.assertEqual(job['status'], 'planned')
        task_id = 'local:' + job['id']
        linked = self.call('link_local_conversation', {'id':task_id,
            'expected_version':job['version'], 'provider':'codex', 'conversation_id':THREAD,
            'provenance':'explicit synthetic test reference'})
        self.assertEqual(linked['conversations'][0]['control'], 'reference_only')
        bound = self.call('bind_external_thread', {'id':task_id,
            'expected_version':linked['version'], 'host_id':HOST, 'thread_id':THREAD})
        self.assertEqual(bound['conversations'][0]['host_id'], HOST)
        self.assertEqual(bound['conversations'][0]['control'], 'reference_only')
        return job['id'], task_id

    def turn(self, task_id, version, turn, start, observation):
        started = (self.base + timedelta(seconds=start)).timestamp()
        return {'id':task_id, 'expected_version':version, 'host_id':HOST,
                'thread_id':THREAD, 'turn_id':turn, 'started_at':started,
                'completed_at':started+10, 'head_turn_id':turn,
                'head_status':'completed', 'head_started_at':started,
                'observed_at':self.moment(observation),
                'evidence':'caller-attested synthetic read_thread output'}

    def assessment(self, task_id, context, event_id):
        return {'id':task_id, 'event_id':event_id,
                'expected_version':context['job']['version'],
                'expected_intent_version':context['intent_version'],
                'disposition':'continue', 'goal_status':'not_met',
                'capability_status':'unknown', 'result_ref':'synthetic/result',
                'gap':'synthetic goal remains open', 'next_action':'inspect synthetic gap',
                'evidence':{'source':SOURCE, 'observed_at':self.moment(65),
                            'detail':'caller-attested synthetic result'}}

    def overview(self):
        return self.call('get_work_overview', {})

    def inbox(self, overview, event_id):
        return [item for item in overview['inbox'] if item.get('event_id') == event_id]

    def test_mcp_http_turn_review_prepare_and_manual_receipt(self):
        job_id, task_id = self.planned_bound_task()
        context = self.context(job_id)
        self.assertEqual(context['goal'], 'synthetic business goal')
        self.assertFalse(context['capabilities']['external_conversation_control'])
        turn1 = self.turn(task_id, context['job']['version'], 'synthetic-turn-1', 0, 50)
        event = self.call('register_external_turn', turn1)
        event_id = event['event_id']
        self.assertEqual(event['verification'], 'caller_attested')
        self.assertEqual(event['source'], SOURCE)
        duplicate = self.call('register_external_turn', turn1)
        self.assertEqual(duplicate['event_id'], event_id)
        self.conflict('register_external_turn', {**turn1, 'completed_at':turn1['completed_at'] + 1})

        overview = self.overview()
        self.assertEqual(len(self.inbox(overview, event_id)), 1)
        self.assertEqual(self.inbox(overview, event_id)[0]['state'], 'awaiting_review')
        self.assertEqual(self.inbox(overview, event_id)[0]['notification']['state'], 'not_connected')
        row = next(item for item in overview['tasks'] if item['id'] == task_id)
        self.assertEqual(row['conversations'][0]['control'], 'reference_only')
        self.assertEqual(row['conversations'][0]['host_id'], HOST)

        context = self.context(job_id)
        self.assertEqual(context['external_turns'][0]['event_id'], event_id)
        assessment = self.call('assess_external_turn', self.assessment(task_id, context, event_id))
        self.assertEqual(assessment['assessment']['goal_status'], 'not_met')
        self.assertEqual(self.inbox(self.overview(), event_id)[0]['state'], 'ready_to_continue')

        context = self.context(job_id)
        instruction = 'Synthetic continuation instruction; do not send.'
        digest = hashlib.sha256(instruction.encode('utf-8')).hexdigest()
        prepare = {'id':task_id, 'event_id':event_id,
                   'expected_version':context['job']['version'],
                   'expected_intent_version':context['intent_version'],
                   'request_id':'synthetic-request-1', 'instruction':instruction}
        first = self.call('prepare_external_dispatch', prepare)
        self.assertTrue(first['created'])
        self.assertEqual(first['event']['dispatch']['state'], 'unknown')
        self.assertEqual(first['event']['dispatch']['instruction_sha256'], digest)
        repeated = self.call('prepare_external_dispatch', prepare)
        self.assertFalse(repeated['created'])
        self.assertEqual(repeated['event']['dispatch']['request_id'], prepare['request_id'])
        self.conflict('prepare_external_dispatch', {**prepare, 'request_id':'synthetic-request-2'})
        self.assertEqual(self.inbox(self.overview(), event_id)[0]['state'], 'dispatch_unknown')

        # A second synthetic caller-observed turn does not prove delivery.
        context = self.context(job_id)
        turn2 = self.turn(task_id, context['job']['version'], 'synthetic-turn-2', 70, 100)
        second = self.call('register_external_turn', turn2)
        context = self.context(job_id)
        original = next(item for item in context['external_turns'] if item['event_id'] == event_id)
        self.assertEqual(original['dispatch']['state'], 'unknown')
        self.assertEqual(len(self.inbox(self.overview(), event_id)), 1)
        late = self.call('register_external_turn', turn1)
        self.assertEqual(late['event_id'], event_id)
        self.conflict('prepare_external_dispatch', prepare)

        evidence = {'source':SOURCE, 'observed_at':self.moment(115),
                    'detail':'synthetic manual comparison of full instruction'}
        observe = {'id':task_id, 'event_id':event_id,
                   'expected_version':self.context(job_id)['job']['version'],
                   'request_id':prepare['request_id'], 'state':'completed',
                   'evidence':evidence, 'target_turn_id':'synthetic-turn-2',
                   'correlation':'manual_verification', 'observed_instruction_sha256':digest}
        self.conflict('observe_external_dispatch', {**observe, 'observed_instruction_sha256':'0'*64})
        final = self.call('observe_external_dispatch', observe)
        self.assertEqual(final['dispatch']['state'], 'completed')
        self.assertEqual(final['dispatch']['observations'][0]['verification'], 'caller_attested')
        self.conflict('observe_external_dispatch', observe)
        observe['expected_version'] = self.context(job_id)['job']['version']
        again = self.call('observe_external_dispatch', observe)
        self.assertEqual(len(again['dispatch']['observations']), 1)

        context = self.context(job_id)
        self.assertEqual(len(context['external_turns']), 2)
        self.assertEqual(sum(isinstance(x['dispatch'], dict) for x in context['external_turns']), 1)
        self.assertEqual(self.inbox(self.overview(), event_id), [])
        self.assertEqual(self.inbox(self.overview(), second['event_id'])[0]['state'], 'awaiting_review')
        self.assertEqual(context['job']['status'], 'planned')
        self.assertEqual(self.processes, [])

    def test_stale_goal_version_cannot_assess_or_prepare(self):
        job_id, task_id = self.planned_bound_task()
        context = self.context(job_id)
        event = self.call('register_external_turn',
                          self.turn(task_id, context['job']['version'], 'synthetic-turn-1', 0, 50))
        old_context = self.context(job_id)
        self.call('assess_external_turn', self.assessment(task_id, old_context, event['event_id']))
        before_change = self.context(job_id)
        updated = self.call('adjust_local_task', {'id':task_id,
            'expected_version':before_change['job']['version'], 'current_goal':'updated synthetic goal',
            'intent_source':'synthetic decision', 'intent_reason':'test version change'})
        self.assertEqual(updated['intent']['goal'], 'updated synthetic goal')
        self.conflict('assess_external_turn', self.assessment(task_id, old_context, event['event_id']))
        now = self.context(job_id)
        self.assertEqual(now['external_turns'][0]['state'], 'review_required')
        self.conflict('prepare_external_dispatch', {'id':task_id, 'event_id':event['event_id'],
            'expected_version':now['job']['version'], 'expected_intent_version':now['intent_version'],
            'request_id':'synthetic-request-1', 'instruction':'synthetic instruction'})
        self.assertEqual(self.inbox(self.overview(), event['event_id'])[0]['state'], 'review_required')
        self.assertEqual(self.processes, [])


if __name__ == '__main__':
    unittest.main()
