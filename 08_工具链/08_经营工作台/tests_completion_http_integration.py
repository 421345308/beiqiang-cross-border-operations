"""Real isolated HTTP-to-AgentJobs completion/continuation integration."""
import time
import unittest
from urllib.parse import urlencode
from unittest.mock import patch

import tests_desk_http as fixture


class CompletionHTTPIntegrationTests(unittest.TestCase):
    setUp = fixture.DeskHTTPTests.setUp
    tearDown = fixture.DeskHTTPTests.tearDown
    write = fixture.DeskHTTPTests.write
    request = fixture.DeskHTTPTests.request

    def wait_finished(self, job_id, attempt):
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            job = self.app.agent_jobs.get_job(job_id)
            if (job.get('attempt') == attempt and job.get('worker_finished') is True and
                    str(attempt) in job.get('completion_events', {})):
                return job
            time.sleep(.01)
        self.fail('synthetic attempt did not finish and register its event')

    def test_finished_run_in_inbox_review_starts_one_safe_continuation(self):
        started = self.app.agent_jobs.start('product:BQ009', '读取合成资料', mode='mail_draft')
        first = self.wait_finished(started['id'], 1)
        status, overview = self.request('/api/desk/task-overview')
        self.assertEqual(status, 200)
        event_id = first['completion_events']['1']['event_id']
        self.assertEqual(len([x for x in overview['inbox'] if x.get('event_id') == event_id]), 1)
        self.assertEqual(next(x for x in overview['inbox'] if x.get('event_id') == event_id)['state'], 'awaiting_review')
        status, context = self.request('/api/desk/task-context?'+urlencode({'id':started['id']}))
        self.assertEqual(status, 200)
        self.assertEqual(context['completion_events'][0]['state'], 'awaiting_review')
        body = {'id':started['id'], 'attempt':1, 'expected_version':context['job']['version'],
                'expected_intent_version':context['intent_version'], 'disposition':'continue',
                'goal_status':'not_met', 'capability_status':'unknown', 'result_ref':'合成成果',
                'gap':'仍需核对合成资料', 'next_action':'只读核对合成资料',
                'evidence':{'source':'合成测试来源','observed_at':'2026-11-11T12:00:00Z','detail':'目标尚未达成'}}
        status, event = self.request('/api/desk/job/assess-completion', body)
        self.assertEqual(status, 200)
        self.assertIn(event['dispatch']['state'], ('accepted','starting','running','completed'))
        request_id = event['dispatch']['request_id']
        final = self.wait_finished(started['id'], 2)
        self.assertEqual(final['completion_events']['1']['dispatch']['state'], 'completed')
        self.assertEqual(final['completion_events']['1']['dispatch']['request_id'], request_id)
        self.assertEqual(final['completion_events']['2']['run_status'], 'completed')
        self.assertEqual(len(self.processes), 2)
        status, repeated = self.request('/api/desk/job/assess-completion', body)
        self.assertEqual(status, 200)
        self.assertEqual(repeated['dispatch']['request_id'], request_id)
        self.assertEqual(len(self.processes), 2)
        status, overview = self.request('/api/desk/task-overview')
        self.assertEqual(status, 200)
        items = [x for x in overview['inbox'] if x.get('task_id') == 'local:'+started['id']]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['event_id'], final['completion_events']['2']['event_id'])
        self.assertEqual(items[0]['state'], 'awaiting_review')

    def test_registration_error_keeps_finished_job_visible_for_repair(self):
        with patch.object(self.app.agent_jobs, '_record_finished_attempt', side_effect=ValueError('synthetic conflict')):
            started = self.app.agent_jobs.start('product:BQ009', '读取合成资料', mode='mail_draft')
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline:
                job = self.app.agent_jobs.get_job(started['id'])
                if job.get('worker_finished') is True:
                    break
                time.sleep(.01)
            self.assertTrue(job.get('worker_finished'))
        self.assertEqual(job['status'], 'completed')
        self.assertEqual(job['completion_error']['state'], 'unavailable')
        status, context = self.request('/api/desk/task-context?'+urlencode({'id':started['id']}))
        self.assertEqual(status, 200)
        self.assertEqual(context['completion_state'], 'unavailable')
        status, overview = self.request('/api/desk/task-overview')
        self.assertEqual(status, 200)
        self.assertTrue(any(x.get('task_id')=='local:'+started['id'] and x.get('kind')=='completion_unavailable'
                            for x in overview['inbox']))


if __name__ == '__main__':
    unittest.main()
