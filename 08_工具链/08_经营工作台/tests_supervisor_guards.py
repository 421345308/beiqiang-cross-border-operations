"""Isolated tests of supervisor fencing at the real AgentJobs write boundary."""
import copy
import hashlib
import json
import time
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from agent_jobs import AgentJobs
import tests_agent_jobs as fixture
from workspaces import WorkspaceConflict


class SupervisorGuardTests(unittest.TestCase):
    setUp = fixture.AgentJobTests.setUp
    tearDown = fixture.AgentJobTests.tearDown
    wait = fixture.AgentJobTests.wait

    def prepare(self, *, text='not in synthetic output'):
        self.app.db.execute('''CREATE TABLE supervisor_leases (
            job_id TEXT NOT NULL, event_id TEXT NOT NULL, owner_id TEXT NOT NULL,
            fence INTEGER NOT NULL, expires_at REAL NOT NULL, heartbeat_at REAL NOT NULL,
            PRIMARY KEY(job_id, event_id))''')
        self.app.db.commit()
        job = self.jobs.start('product:shoe', 'synthetic supervisor test', mode='mail_draft')
        self.wait(job)
        job = self.jobs.get_job(job['id'])
        self.assertEqual(job['status'], 'completed')
        self.assertEqual(len(job['completion_events']['1']['artifact_ids']), 1)
        with self.jobs._write():
            job = self.jobs.get_job(job['id'])
            job['supervision'] = {
                'enabled': True, 'policy': 'mail_draft_read_only_v1',
                'acceptance_criteria': {'kind': 'artifact_contains', 'text': text},
                'continuation_instruction': 'check synthetic material',
                'authorization_ref': 'synthetic authorization', 'max_auto_continuations': 1,
                'business_case': {'business_outcome':'synthetic result', 'current_bottleneck':'synthetic gap',
                                  'intended_change':'review synthetic output', 'stop_condition':'condition met',
                                  'evidence_source':'synthetic fixture'},
                'prerequisite_state':'ready', 'value_state':'supported',
                'configured_at': datetime.now(timezone.utc).isoformat(),
            }
            job['supervision_revision'] = 1
            self.jobs._save(job)
        job = self.jobs.get_job(job['id'])
        self.set_lease(job['id'])
        return job

    def set_lease(self, job_id, *, owner='owner-a', fence=1, attempt=1, expires=None):
        now = time.time()
        with self.jobs._write():
            self.app.db.execute('INSERT OR REPLACE INTO supervisor_leases VALUES (?,?,?,?,?,?)',
                (job_id, f'agent-job:{job_id}:attempt:{attempt}', owner, fence,
                 now + 60 if expires is None else expires, now))

    def assessment(self, job, *, met=False):
        event = job['completion_events']['1']
        artifact_id = event['artifact_ids'][0]
        artifact = next(a for a in self.app.business.artifacts if a['id'] == artifact_id)
        detail = json.dumps({'artifact_id': artifact_id,
                             'sha256': hashlib.sha256(artifact['content'].encode('utf8')).hexdigest(),
                             'condition_met': met}, ensure_ascii=False)
        return {'expected_version': job['version'], 'expected_intent_version': job['intent']['version'],
                'disposition': 'needs_decision' if met else 'continue',
                'goal_status': 'unknown', 'capability_status': 'unknown',
                'result_ref': artifact_id, 'gap': 'mechanical condition requires review',
                'next_action': '人工核对机械验收结果及整体业务目标。' if met else 'check synthetic material',
                'evidence': {'source': 'agent_jobs:artifact_contains',
                             'observed_at': datetime.now(timezone.utc).isoformat(), 'detail': detail},
                'supervisor_guard': {'owner_id': 'owner-a', 'fence': 1}}

    def test_guard_rejects_wrong_owner_fence_expired_and_wrong_event(self):
        job = self.prepare()
        for owner, fence, attempt, expires in [
                ('owner-b', 1, 1, None), ('owner-a', 2, 1, None),
                ('owner-a', 1, 1, time.time() - 1), ('owner-a', 1, 2, None)]:
            with self.subTest(owner=owner, fence=fence, attempt=attempt, expires=expires):
                self.set_lease(job['id'], owner=owner, fence=fence, attempt=attempt, expires=expires)
                if attempt == 2:
                    self.set_lease(job['id'], owner='other', fence=1, attempt=1)
                with self.assertRaises(WorkspaceConflict):
                    self.jobs.assess_completion(job['id'], 1, **self.assessment(job))
                self.assertIsNone(self.jobs.get_job(job['id'])['completion_events']['1']['assessment'])
        self.assertEqual(len(self.processes), 1)

    def test_valid_guard_binds_evidence_and_condition_match_is_human_review(self):
        job = self.prepare(text='synthetic condition matched')
        self.app.business.artifacts[0]['content'] = 'synthetic condition matched'
        event = self.jobs.assess_completion(job['id'], 1, **self.assessment(job, met=True))
        self.assertEqual(event['assessment']['disposition'], 'needs_decision')
        self.assertEqual(event['assessment']['supervision_revision'], 1)
        self.assertIsNone(event['dispatch'])
        self.assertEqual(len(self.processes), 1)

    def test_artifact_change_between_assessment_and_claim_never_dispatches(self):
        job = self.prepare()
        event = self.jobs.assess_completion(job['id'], 1, **self.assessment(job))
        self.app.business.artifacts[0]['content'] += ' changed after observation'
        with self.assertRaises(WorkspaceConflict):
            self.jobs.continue_followup(job['id'], 1,
                expected_version=event['assessment']['task_version_at_review'], request_id='synthetic-1',
                supervisor_guard={'owner_id':'owner-a', 'fence':1})
        current = self.jobs.get_job(job['id'])
        self.assertEqual(current['status'], 'completed')
        self.assertIsNone(current['completion_events']['1']['dispatch'])
        self.assertEqual(len(self.processes), 1)

    def test_loss_between_review_and_dispatch_does_not_write_blocker(self):
        job = self.prepare()
        real_continue = self.jobs.continue_followup
        def lose_lease(*args, **kwargs):
            self.set_lease(job['id'], owner='owner-b', fence=2)
            return real_continue(*args, **kwargs)
        with patch.object(self.jobs, 'continue_followup', side_effect=lose_lease):
            with self.assertRaises(WorkspaceConflict):
                self.jobs.assess_and_continue(job['id'], 1, **self.assessment(job))
        event = self.jobs.get_job(job['id'])['completion_events']['1']
        self.assertIsNotNone(event['assessment'])
        self.assertIsNone(event['dispatch'])
        self.assertNotIn('dispatch_blocked', event)
        self.assertEqual(len(self.processes), 1)

    def test_expiry_before_save_rolls_back_assessment(self):
        job = self.prepare()
        with patch('supervisor.verify_guard', side_effect=[None, WorkspaceConflict('lease expired')]):
            with self.assertRaises(WorkspaceConflict):
                self.jobs.assess_completion(job['id'], 1, **self.assessment(job))
        event = self.jobs.get_job(job['id'])['completion_events']['1']
        self.assertIsNone(event['assessment'])
        self.assertEqual(len(self.processes), 1)

    def test_disabling_supervision_after_review_prevents_claim(self):
        job = self.prepare()
        event = self.jobs.assess_completion(job['id'], 1, **self.assessment(job))
        with self.jobs._write():
            changed = self.jobs.get_job(job['id'])
            changed['supervision']['enabled'] = False
            changed['supervision_revision'] += 1
            self.jobs._save(changed)
        with self.assertRaises(WorkspaceConflict):
            self.jobs.continue_followup(job['id'], 1,
                expected_version=event['assessment']['task_version_at_review'], request_id='synthetic-1',
                supervisor_guard={'owner_id':'owner-a', 'fence':1})
        self.assertIsNone(self.jobs.get_job(job['id'])['completion_events']['1']['dispatch'])
        self.assertEqual(len(self.processes), 1)

    def test_business_intent_and_ready_supported_states_are_required(self):
        job = self.prepare()
        base = copy.deepcopy(job['supervision'])
        variants = []
        missing_case = copy.deepcopy(base)
        missing_case.pop('business_case')
        variants.append(missing_case)
        missing_evidence = copy.deepcopy(base)
        missing_evidence['business_case']['evidence_source'] = ' '
        variants.append(missing_evidence)
        for state in ('waiting_asset', 'waiting_review', 'unknown'):
            value = copy.deepcopy(base)
            value['prerequisite_state'] = state
            variants.append(value)
        for state in ('none', 'unknown'):
            value = copy.deepcopy(base)
            value['value_state'] = state
            variants.append(value)
        for policy in variants:
            with self.subTest(policy=policy):
                with self.jobs._write():
                    current = self.jobs.get_job(job['id'])
                    current['supervision'] = policy
                    current['supervision_revision'] += 1
                    self.jobs._save(current)
                current = self.jobs.get_job(job['id'])
                with self.assertRaises(WorkspaceConflict):
                    self.jobs.assess_completion(job['id'], 1, **self.assessment(current))
                self.assertIsNone(self.jobs.get_job(job['id'])['completion_events']['1']['assessment'])
        self.assertEqual(len(self.processes), 1)

    def test_business_value_removed_after_review_blocks_claim(self):
        job = self.prepare()
        event = self.jobs.assess_completion(job['id'], 1, **self.assessment(job))
        with self.jobs._write():
            current = self.jobs.get_job(job['id'])
            current['supervision']['value_state'] = 'none'
            current['supervision_revision'] += 1
            self.jobs._save(current)
        with self.assertRaises(WorkspaceConflict):
            self.jobs.continue_followup(job['id'], 1,
                expected_version=event['assessment']['task_version_at_review'], request_id='synthetic-1',
                supervisor_guard={'owner_id':'owner-a', 'fence':1})
        self.assertIsNone(self.jobs.get_job(job['id'])['completion_events']['1']['dispatch'])
        self.assertEqual(len(self.processes), 1)

    def test_prior_automatic_receipt_uses_the_one_continuation_limit(self):
        job = self.prepare()
        self.jobs.assess_completion(job['id'], 1, **self.assessment(job))
        with self.jobs._write():
            current = self.jobs.get_job(job['id'])
            current['completion_events']['2'] = {
                'event_id': f"agent-job:{job['id']}:attempt:2", 'attempt': 2,
                'dispatch': {'state': 'completed', 'supervision_revision': 1},
            }
            current['completion_events']['1']['assessment']['task_version_at_review'] = current['version'] + 1
            current['completion_revision'] += 1
            self.jobs._save(current)
        current = self.jobs.get_job(job['id'])
        with self.assertRaises(WorkspaceConflict):
            self.jobs.continue_followup(job['id'], 1, expected_version=current['version'],
                request_id='synthetic-new-attempt', supervisor_guard={'owner_id':'owner-a', 'fence':1})
        self.assertIsNone(self.jobs.get_job(job['id'])['completion_events']['1']['dispatch'])
        self.assertEqual(len(self.processes), 1)

    def test_same_guarded_dispatch_is_idempotent_and_retains_revision(self):
        job = self.prepare()
        try:
            with patch('completion_dispatch.threading.Thread') as thread:
                event = self.jobs.assess_and_continue(job['id'], 1, **self.assessment(job))
                self.assertEqual(event['dispatch']['state'], 'accepted')
                self.assertEqual(event['dispatch']['supervision_revision'], 1)
                self.assertEqual(thread.return_value.start.call_count, 1)
                duplicate = self.jobs.continue_followup(job['id'], 1, expected_version=0,
                    request_id=event['dispatch']['request_id'], supervisor_guard={'owner_id':'owner-a','fence':1})
                self.assertEqual(duplicate['dispatch']['request_id'], event['dispatch']['request_id'])
                self.assertEqual(thread.return_value.start.call_count, 1)
                self.set_lease(job['id'], owner='owner-b', fence=2)
                with self.assertRaises(WorkspaceConflict):
                    self.jobs.continue_followup(job['id'], 1, expected_version=0,
                        request_id=event['dispatch']['request_id'], supervisor_guard={'owner_id':'owner-a','fence':1})
                self.assertEqual(thread.return_value.start.call_count, 1)
        finally:
            self.jobs.threads.pop(job['id'], None)

    def test_lost_lease_after_launch_error_keeps_original_accepted_receipt(self):
        job = self.prepare()
        try:
            with patch('completion_dispatch.threading.Thread') as thread:
                def lose_and_fail():
                    self.set_lease(job['id'], owner='owner-b', fence=2)
                    raise RuntimeError('synthetic uncertain launch')
                thread.return_value.start.side_effect = lose_and_fail
                with self.assertRaises(WorkspaceConflict):
                    self.jobs.assess_and_continue(job['id'], 1, **self.assessment(job))
                event = self.jobs.get_job(job['id'])['completion_events']['1']
                self.assertEqual(event['dispatch']['state'], 'accepted')
                self.assertEqual(event['dispatch']['supervision_revision'], 1)
                self.assertNotIn('dispatch_blocked', event)
                self.assertEqual(thread.return_value.start.call_count, 1)
        finally:
            self.jobs.threads.pop(job['id'], None)

    def test_revision_merge_preserves_newer_supervision_and_rejects_equal_conflicts(self):
        job = self.prepare()
        stale = copy.deepcopy(job)
        with self.jobs._write():
            current = self.jobs.get_job(job['id'])
            current['supervision']['enabled'] = False
            current['supervision_revision'] += 1
            self.jobs._event(current, 'supervision_disabled', 'synthetic supervisor disabled')
            self.jobs._save(current)
        with self.jobs._write():
            self.jobs._save(stale)
        saved = self.jobs.get_job(job['id'])
        self.assertEqual(saved['supervision_revision'], 2)
        self.assertIs(saved['supervision']['enabled'], False)
        self.assertIn('supervision_disabled', [event['type'] for event in saved['events']])
        with self.assertRaises(WorkspaceConflict):
            with self.jobs._write():
                changed = self.jobs.get_job(job['id'])
                changed['supervision']['enabled'] = True
                self.jobs._save(changed)
        with self.assertRaises(WorkspaceConflict):
            with self.jobs._write():
                changed = self.jobs.get_job(job['id'])
                changed['completion_events']['1']['summary'] = 'conflicting same-revision event'
                self.jobs._save(changed)


if __name__ == '__main__':
    unittest.main()
