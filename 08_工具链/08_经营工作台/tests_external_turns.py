"""Adversarial tests use only planned jobs and caller-attested synthetic data."""
import copy
import hashlib
import sqlite3
import threading
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from agent_jobs import AgentJobs
from external_turns import SEND_SOURCE, SOURCE
import tests_agent_jobs as fixture
from workspaces import WorkspaceConflict


THREAD = '12345678-1234-4234-8234-123456789abc'
BASE = 1605092400
NOW = datetime.now(timezone.utc)
OBSERVED = (NOW - timedelta(minutes=2)).isoformat()
LATER = (NOW - timedelta(minutes=1)).isoformat()
LAST = NOW.isoformat()


def proof(source=SOURCE, observed_at=OBSERVED):
    return {'source': source, 'observed_at': observed_at, 'detail': 'synthetic observation'}


class ExternalTurnsTests(unittest.TestCase):
    # Reuse the in-memory AgentJobs environment and fake subprocess guard.
    setUp = fixture.AgentJobTests.setUp
    tearDown = fixture.AgentJobTests.tearDown

    def planned(self, thread=THREAD, bind=True):
        job = self.jobs.start('product:shoe', 'synthetic objective', defer=True)
        self.assertEqual(job['status'], 'planned')
        job = self.jobs.link_conversation(
            job['id'], provider='codex', conversation_id=thread,
            provenance='synthetic explicit reference', expected_version=job['version'])
        self.assertEqual(job['conversations'][0]['control'], 'reference_only')
        if bind:
            job = self.jobs.bind_external_thread(
                job['id'], expected_version=job['version'], host_id='durable', thread_id=thread)
            self.assertEqual(job['conversations'][0]['control'], 'reference_only')
        return job['id']

    def current(self, job_id):
        return self.jobs.get_job(job_id)

    def register(self, job_id, turn='turn-1', start=BASE, end=BASE+10,
                 head=None, head_start=None, head_status='completed', observed=OBSERVED,
                 expected_version=None, host='durable', thread=THREAD):
        job = self.current(job_id)
        return self.jobs.register_external_turn(
            job_id, expected_version=job['version'] if expected_version is None else expected_version,
            host_id=host, thread_id=thread, turn_id=turn, started_at=start, completed_at=end,
            head_turn_id=head or turn, head_status=head_status,
            head_started_at=start if head_start is None else head_start,
            observed_at=observed, evidence='synthetic read of completed turn and page head')

    def assess(self, job_id, event_id, **overrides):
        job = self.current(job_id)
        values = dict(expected_version=job['version'], expected_intent_version=job['intent']['version'],
                      disposition='continue', goal_status='not_met', capability_status='unknown',
                      result_ref='synthetic/result', gap='synthetic remaining gap',
                      next_action='inspect the synthetic gap', evidence=proof())
        values.update(overrides)
        return self.jobs.assess_external_turn(job_id, event_id, **values)

    def prepare(self, job_id, event_id, request='request-1', instruction='synthetic next instruction'):
        job = self.current(job_id)
        return self.jobs.prepare_external_dispatch(
            job_id, event_id, expected_version=job['version'],
            expected_intent_version=job['intent']['version'], request_id=request, instruction=instruction)

    def observe(self, job_id, event_id, **overrides):
        job = self.current(job_id)
        values = dict(expected_version=job['version'], request_id='request-1', state='completed',
                      evidence=proof(observed_at=LAST), target_turn_id='turn-2')
        values.update(overrides)
        return self.jobs.observe_external_dispatch(job_id, event_id, **values)

    def test_end_to_end_is_attested_and_does_not_start_or_send(self):
        job_id = self.planned()
        event = self.register(job_id)
        self.assertEqual(event['verification'], 'caller_attested')
        self.assertEqual(event['source'], SOURCE)
        self.assertEqual(self.jobs.external_turns_view(self.current(job_id))[0]['state'], 'awaiting_review')
        assessment = self.assess(job_id, event['event_id'])['assessment']
        self.assertEqual(assessment['goal_status'], 'not_met')
        self.assertEqual(self.jobs.external_turns_view(self.current(job_id))[0]['state'], 'ready_to_continue')
        result = self.prepare(job_id, event['event_id'])
        self.assertTrue(result['created'])
        receipt = result['event']['dispatch']
        self.assertEqual(receipt['state'], 'unknown')
        self.assertEqual(receipt['instruction_sha256'], hashlib.sha256(b'synthetic next instruction').hexdigest())
        self.assertEqual(self.current(job_id)['status'], 'planned')
        self.assertEqual(self.processes, [])

    def test_same_event_is_idempotent_and_identity_time_conflicts(self):
        job_id = self.planned()
        stale = self.current(job_id)['version']
        event = self.register(job_id, expected_version=stale)
        version = self.current(job_id)['version']
        duplicate = self.register(job_id, expected_version=stale)
        self.assertEqual(duplicate['event_id'], event['event_id'])
        self.assertEqual(self.current(job_id)['version'], version)
        self.assertEqual(len(self.current(job_id)['external_turn_events']), 1)
        with self.assertRaises(WorkspaceConflict):
            self.register(job_id, end=BASE+11)
        with self.assertRaises(WorkspaceConflict):
            self.register(job_id, start=BASE+1, head_start=BASE+1)
        self.assertEqual(self.current(job_id)['version'], version)

    def test_late_older_turn_cannot_replace_newer_head_or_be_dispatched(self):
        job_id = self.planned()
        newest = self.register(job_id, turn='turn-2', start=BASE+20, end=BASE+30)
        older = self.register(job_id, observed=LATER)
        rows = {item['turn_id']: item for item in self.jobs.external_turns_view(self.current(job_id))}
        self.assertEqual(rows['turn-2']['head_turn_id'], 'turn-2')
        self.assertTrue(rows['turn-2']['current'])
        self.assertEqual(rows['turn-1']['state'], 'historical')
        with self.assertRaises(WorkspaceConflict):
            self.assess(job_id, older['event_id'])
        self.assess(job_id, newest['event_id'])

    def test_equal_head_times_and_conflicting_same_observation_are_rejected(self):
        job_id = self.planned()
        self.register(job_id, turn='turn-2', start=BASE+20, end=BASE+30)
        with self.assertRaises(WorkspaceConflict):
            self.register(job_id, head='other-turn', head_start=BASE+20, observed=LATER)
        with self.assertRaises(WorkspaceConflict):
            self.register(job_id, observed=OBSERVED)

    def test_stale_source_cannot_authorize_assessment(self):
        job_id = self.planned()
        old = (NOW - timedelta(minutes=20)).isoformat()
        event = self.register(job_id, observed=old)
        row = self.jobs.external_turns_view(self.current(job_id))[0]
        self.assertTrue(row['source_stale'])
        with self.assertRaises(WorkspaceConflict):
            self.assess(job_id, event['event_id'])

    def test_ambiguous_tasks_and_wrong_host_cannot_register(self):
        job_id = self.planned()
        with self.assertRaises(WorkspaceConflict):
            self.register(job_id, host='other-host')
        with self.assertRaises(WorkspaceConflict):
            self.jobs.bind_external_thread(job_id, expected_version=self.current(job_id)['version'],
                                           host_id='other-host', thread_id=THREAD)
        other = self.planned(bind=False)
        with self.assertRaises(WorkspaceConflict):
            self.register(job_id)
        with self.assertRaises(WorkspaceConflict):
            self.jobs.bind_external_thread(other, expected_version=self.current(other)['version'],
                                           host_id='durable', thread_id=THREAD)
        self.assertEqual(self.current(job_id).get('external_turn_events', {}), {})
        self.assertEqual(self.processes, [])

    def test_same_thread_identifier_on_explicit_distinct_hosts_stays_distinct(self):
        first = self.planned()
        second = self.planned(bind=False)
        self.jobs.bind_external_thread(second, expected_version=self.current(second)['version'],
                                       host_id='other-host', thread_id=THREAD)
        one = self.register(first)
        two = self.register(second, host='other-host')
        self.assertNotEqual(one['event_id'], two['event_id'])
        self.assertEqual(one['host_id'], 'durable')
        self.assertEqual(two['host_id'], 'other-host')
        self.assertEqual(len(self.current(first)['external_turn_events']), 1)
        self.assertEqual(len(self.current(second)['external_turn_events']), 1)

    def test_intent_and_expected_versions_invalidate_previous_assessment(self):
        job_id = self.planned()
        event = self.register(job_id)
        job = self.current(job_id)
        old_version, old_intent = job['version'], job['intent']['version']
        self.assess(job_id, event['event_id'])
        job = self.current(job_id)
        job = self.jobs.adjust(job_id, expected_version=job['version'], current_goal='changed synthetic goal',
                               intent_source='synthetic decision', intent_reason='synthetic change')
        view = self.jobs.external_turns_view(self.current(job_id))[0]
        self.assertEqual(view['state'], 'review_required')
        with self.assertRaises(WorkspaceConflict):
            self.assess(job_id, event['event_id'], expected_version=old_version,
                        expected_intent_version=old_intent)
        with self.assertRaises(WorkspaceConflict):
            self.prepare(job_id, event['event_id'])
        updated = self.assess(job_id, event['event_id'])
        self.assertEqual(updated['assessment']['intent_version'], job['intent']['version'])
        self.assertEqual(updated['assessment_history'][0]['status'], 'superseded')

    def test_unknown_receipt_survives_new_turn_and_blocks_another_request(self):
        job_id = self.planned()
        old = self.register(job_id)
        self.assess(job_id, old['event_id'])
        self.prepare(job_id, old['event_id'])
        with self.assertRaises(WorkspaceConflict):
            self.observe(job_id, old['event_id'])
        with self.assertRaises(WorkspaceConflict):
            self.observe(job_id, old['event_id'], correlation='matching_receipt')
        new = self.register(job_id, turn='turn-2', start=BASE+20, end=BASE+30, observed=LATER)
        old_state = self.current(job_id)['external_turn_events'][old['event_id']]['dispatch']['state']
        self.assertEqual(old_state, 'unknown')
        self.assess(job_id, new['event_id'])
        with self.assertRaises(WorkspaceConflict):
            self.prepare(job_id, new['event_id'], request='request-2')
        self.assertEqual(self.processes, [])

    def test_manual_verification_requires_exact_full_request_hash(self):
        job_id = self.planned()
        old = self.register(job_id)
        self.assess(job_id, old['event_id'])
        self.prepare(job_id, old['event_id'])
        self.register(job_id, turn='turn-2', start=BASE+20, end=BASE+30, observed=LATER)
        digest = hashlib.sha256(b'synthetic next instruction').hexdigest()
        with self.assertRaises(ValueError):
            self.observe(job_id, old['event_id'], correlation='manual_verification',
                         observed_instruction_sha256=digest[:16])
        with self.assertRaises(WorkspaceConflict):
            self.observe(job_id, old['event_id'], correlation='manual_verification',
                         observed_instruction_sha256='0'*64)
        self.assertEqual(self.current(job_id)['external_turn_events'][old['event_id']]['dispatch']['state'], 'unknown')
        observed = self.observe(job_id, old['event_id'], correlation='manual_verification',
                                observed_instruction_sha256=digest)
        self.assertEqual(observed['dispatch']['state'], 'completed')
        self.assertEqual(observed['dispatch']['target_turn_id'], 'turn-2')
        self.assertEqual(observed['dispatch']['observations'][-1]['verification'], 'caller_attested')
        repeated = self.observe(job_id, old['event_id'], correlation='manual_verification',
                                observed_instruction_sha256=digest)
        self.assertEqual(len(repeated['dispatch']['observations']), 1)

    def test_accepted_without_correlating_identifier_does_not_prove_new_turn(self):
        job_id = self.planned()
        old = self.register(job_id)
        self.assess(job_id, old['event_id'])
        self.prepare(job_id, old['event_id'])
        self.observe(job_id, old['event_id'], state='accepted', evidence=proof(SEND_SOURCE), target_turn_id=None)
        self.register(job_id, turn='turn-2', start=BASE+20, end=BASE+30, observed=LATER)
        with self.assertRaises(WorkspaceConflict):
            self.observe(job_id, old['event_id'], correlation='matching_receipt')
        self.assertEqual(self.current(job_id)['external_turn_events'][old['event_id']]['dispatch']['state'], 'accepted')

    def test_later_unavailable_read_makes_running_receipt_unknown(self):
        job_id = self.planned()
        old = self.register(job_id)
        self.assess(job_id, old['event_id'])
        self.prepare(job_id, old['event_id'])
        self.observe(job_id, old['event_id'], state='accepted', evidence=proof(SEND_SOURCE),
                     target_turn_id='turn-2')
        self.observe(job_id, old['event_id'], state='running', evidence=proof(observed_at=LATER),
                     correlation='matching_receipt')
        event = self.observe(job_id, old['event_id'], state='unknown', target_turn_id=None,
                             evidence={'source': SOURCE, 'observed_at': LAST,
                                       'detail': 'synthetic later read unavailable'})
        receipt = event['dispatch']
        self.assertEqual(receipt['state'], 'unknown')
        self.assertEqual([item['state'] for item in receipt['observations']],
                         ['accepted', 'running', 'unknown'])
        self.assertEqual(self.jobs.external_turns_view(self.current(job_id))[0]['state'], 'dispatch_unknown')

    def test_same_request_id_cannot_be_created_again_on_a_newer_turn(self):
        job_id = self.planned()
        old = self.register(job_id)
        self.assess(job_id, old['event_id'])
        self.prepare(job_id, old['event_id'])
        new = self.register(job_id, turn='turn-2', start=BASE+20, end=BASE+30, observed=LATER)
        digest = hashlib.sha256(b'synthetic next instruction').hexdigest()
        self.observe(job_id, old['event_id'], correlation='manual_verification',
                     observed_instruction_sha256=digest)
        self.assess(job_id, new['event_id'])
        try:
            repeated = self.prepare(job_id, new['event_id'])
        except WorkspaceConflict:
            pass
        else:
            self.assertFalse(repeated['created'], 'same request_id must not create a second dispatch')

    def test_assessment_replay_conflicts_after_prepared_intent_changes(self):
        job_id = self.planned()
        event = self.register(job_id)
        before = self.current(job_id)
        self.assess(job_id, event['event_id'])
        self.prepare(job_id, event['event_id'])
        current = self.current(job_id)
        self.jobs.adjust(job_id, expected_version=current['version'], current_goal='new synthetic goal',
                         intent_source='synthetic decision', intent_reason='synthetic revision')
        with self.assertRaises(WorkspaceConflict):
            self.assess(job_id, event['event_id'], expected_version=before['version'],
                        expected_intent_version=before['intent']['version'])
        self.assertEqual(self.current(job_id)['external_turn_events'][event['event_id']]['dispatch']['state'], 'unknown')

    def test_unknown_receipt_on_another_host_blocks_same_thread(self):
        first = self.planned()
        old = self.register(first)
        self.assess(first, old['event_id'])
        self.prepare(first, old['event_id'])
        second = self.planned(bind=False)
        self.jobs.bind_external_thread(second, expected_version=self.current(second)['version'],
                                       host_id='other-host', thread_id=THREAD)
        new = self.register(second, host='other-host')
        self.assertNotEqual(old['event_id'], new['event_id'])
        self.assess(second, new['event_id'])
        with self.assertRaises(WorkspaceConflict):
            self.prepare(second, new['event_id'], request='request-2', instruction='different instruction')
        self.assertEqual(self.current(first)['external_turn_events'][old['event_id']]['dispatch']['state'], 'unknown')
        digest = hashlib.sha256(b'synthetic next instruction').hexdigest()
        self.observe(first, old['event_id'], correlation='manual_verification',
                     observed_instruction_sha256=digest)
        with self.assertRaises(WorkspaceConflict):
            self.prepare(second, new['event_id'], request='request-2')
        self.assertTrue(self.prepare(second, new['event_id'], request='request-2',
                                     instruction='different instruction')['created'])
        self.assertEqual(self.processes, [])

    def test_failed_request_requires_complete_resolution_and_new_instruction(self):
        job_id = self.planned()
        old = self.register(job_id)
        self.assess(job_id, old['event_id'])
        self.prepare(job_id, old['event_id'])
        new = self.register(job_id, turn='turn-2', start=BASE+20, end=BASE+30, observed=LATER)
        digest = hashlib.sha256(b'synthetic next instruction').hexdigest()
        self.observe(job_id, old['event_id'], state='failed', correlation='manual_verification',
                     observed_instruction_sha256=digest)
        self.assess(job_id, new['event_id'], gap='unresolved failure')
        with self.assertRaises(WorkspaceConflict):
            self.prepare(job_id, new['event_id'], request='request-2', instruction='different instruction')

        # Deliberately corrupt only the isolated synthetic fixture.
        for label, bad in (('empty', {}),
                           ('bad timestamp', {'verification':'caller_attested',
                                              'recorded_at':'not-a-time', 'evidence':proof()})):
            with self.jobs._write():
                job = self.current(job_id)
                job['external_turn_events'][old['event_id']]['dispatch']['failure_resolution'] = bad
                job['external_revision'] += 1
                self.jobs._save(job)
            self.assess(job_id, new['event_id'], gap='corrupt resolution: '+label)
            with self.assertRaises(WorkspaceConflict):
                self.prepare(job_id, new['event_id'], request='request-2', instruction='different instruction')

        with self.jobs._write():
            job = self.current(job_id)
            del job['external_turn_events'][old['event_id']]['dispatch']['failure_resolution']
            job['external_revision'] += 1
            self.jobs._save(job)
        job = self.current(job_id)
        resolved = self.jobs.resolve_external_failure(job_id, old['event_id'], expected_version=job['version'],
                                                       request_id='request-1', evidence=proof(observed_at=LAST))
        self.assertEqual(resolved['dispatch']['failure_resolution']['verification'], 'caller_attested')
        self.assess(job_id, new['event_id'], gap='failure resolved; verify revised instruction')
        with self.assertRaises(WorkspaceConflict):
            self.prepare(job_id, new['event_id'], request='request-2')
        prepared = self.prepare(job_id, new['event_id'], request='request-2', instruction='different instruction')
        self.assertTrue(prepared['created'])

    def test_stale_worker_save_cannot_erase_external_events_or_receipt(self):
        job_id = self.planned()
        stale = copy.deepcopy(self.current(job_id))
        event = self.register(job_id)
        self.assess(job_id, event['event_id'])
        self.prepare(job_id, event['event_id'])
        stale['summary'] = 'synthetic stale worker summary'
        try:
            with self.jobs._write():
                self.jobs._save(stale)
        except WorkspaceConflict:
            pass  # Rejecting a stale save is also safe.
        stored = self.current(job_id)
        self.assertEqual(stored['external_turn_events'][event['event_id']]['dispatch']['state'], 'unknown')
        self.assertEqual(self.jobs.external_turns_view(stored)[0]['head_turn_id'], 'turn-1')
        self.assertEqual(stored['conversations'][0]['host_id'], 'durable')

    def test_two_connections_concurrently_deduplicate_and_preserve_stale_save(self):
        # Both services use independent SQLite connections and locks, on a
        # private temporary database; no actual worker or send call is started.
        old_db = self.app.db
        path = self.root / 'synthetic-external.sqlite3'
        self.app.db = sqlite3.connect(path, timeout=3, check_same_thread=False)
        old_db.close()
        self.jobs = AgentJobs(self.app)
        other_db = sqlite3.connect(path, timeout=3, check_same_thread=False)
        other_app = SimpleNamespace(root=self.root, state=self.app.state, lock=threading.RLock(),
                                    db=other_db, business=self.app.business)
        other = AgentJobs(other_app)
        try:
            job_id = self.planned()
            stale = other.get_job(job_id)
            version = stale['version']

            def concurrent(call):
                barrier = threading.Barrier(3)
                results, errors = [], []

                def run(service):
                    try:
                        barrier.wait(timeout=3)
                        results.append(call(service))
                    except Exception as exc:
                        errors.append(exc)

                threads = [threading.Thread(target=run, args=(service,)) for service in (self.jobs, other)]
                for thread in threads:
                    thread.start()
                barrier.wait(timeout=3)
                for thread in threads:
                    thread.join(timeout=5)
                    self.assertFalse(thread.is_alive(), 'synthetic concurrent call timed out')
                self.assertEqual(errors, [])
                self.assertEqual(len(results), 2)
                return results

            events = concurrent(lambda service: service.register_external_turn(
                job_id, expected_version=version, host_id='durable', thread_id=THREAD,
                turn_id='turn-1', started_at=BASE, completed_at=BASE+10,
                head_turn_id='turn-1', head_status='completed', head_started_at=BASE,
                observed_at=OBSERVED, evidence='synthetic concurrent read'))
            self.assertEqual(events[0]['event_id'], events[1]['event_id'])
            current = self.current(job_id)
            self.assertEqual(len(current['external_turn_events']), 1)
            self.assertEqual(current['version'], version+1)
            event_id = events[0]['event_id']
            self.assess(job_id, event_id)
            reviewed = self.current(job_id)
            dispatches = concurrent(lambda service: service.prepare_external_dispatch(
                job_id, event_id, expected_version=reviewed['version'],
                expected_intent_version=reviewed['intent']['version'], request_id='request-1',
                instruction='synthetic next instruction'))
            self.assertEqual(sorted(item['created'] for item in dispatches), [False, True])
            self.assertEqual(self.current(job_id)['version'], reviewed['version']+1)
            stale['summary'] = 'synthetic delayed worker'
            try:
                with other._write():
                    other._save(stale)
            except WorkspaceConflict:
                pass  # Conflict rejection also preserves the newer event.
            after = other.get_job(job_id)
            self.assertEqual(len(after['external_turn_events']), 1)
            self.assertEqual(after['external_turn_events'][event_id]['dispatch']['state'], 'unknown')
            self.assertEqual(other.external_turns_view(after)[0]['head_turn_id'], 'turn-1')
            self.assertEqual(self.processes, [])
        finally:
            other_db.close()


if __name__ == '__main__':
    unittest.main()
