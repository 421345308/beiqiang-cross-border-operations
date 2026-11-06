"""Synthetic-only reconciliation checks; no Workbench/AgentJobs/network setup."""
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest

from gmail_event_reconcile import (GmailEventReconcile, ReconcileRejected,
                                   ReconcileConflict, ReconcileOutcomeUnknown)


class GmailEventReconcileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'events.sqlite3'
        self.connections = []
        self.app = self.open_app()
        self.app.db.executescript('''
            CREATE TABLE gmail_reply_events (object_id TEXT,message_id TEXT,
                dispatch_state TEXT,job_id TEXT,updated_at TEXT,last_error TEXT,
                PRIMARY KEY(object_id,message_id));
            CREATE TABLE gmail_acknowledged (object_id TEXT PRIMARY KEY,message_id TEXT);
            CREATE TABLE agent_jobs (id TEXT PRIMARY KEY,data TEXT NOT NULL);
        ''')
        self.service = GmailEventReconcile(self.app, clock=lambda: '2026-11-06T09:00:00Z')

    def tearDown(self):
        for db in self.connections:
            db.close()

    def open_app(self):
        db = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        self.connections.append(db)
        return SimpleNamespace(db=db, lock=threading.RLock())

    def event(self, mid='m1', state='outcome_unknown', jid=None, at='2026-11-05T00:00:00Z', oid='customer:1'):
        self.app.db.execute('INSERT INTO gmail_reply_events VALUES (?,?,?,?,?,?)', (oid, mid, state, jid, at, 'callback error'))
        self.app.db.commit()

    def job(self, jid='j1', oid='customer:1', mode='mail_draft', status='running', source=None):
        data = {'id': jid, 'object_id': oid, 'mode': mode, 'status': status, 'updated_at': '2026-11-05',
                'instruction': 'private body must not appear in reports'}
        if source is not None:
            data['source_event'] = source
        self.app.db.execute('INSERT INTO agent_jobs VALUES (?,?)', (jid, json.dumps(data)))
        self.app.db.commit()
        return data

    def snapshot(self, mid='m1', service=None):
        result = (service or self.service).list_events('customer:1')
        return next(r['snapshot'] for r in result['events'] if r['message_id'] == mid)

    def link(self, mid='m1', jid='j1', snapshot=None, service=None, **kwargs):
        target = service or self.service
        return target.link_existing('customer:1', mid, jid, snapshot or self.snapshot(mid),
                                    confirmed=True, manual_note='Checked original mail and existing task manually.', **kwargs)

    def test_constructor_and_report_never_write_or_recover_running_jobs(self):
        self.event(); before = self.job()
        changes = self.app.db.total_changes
        statements = []
        self.app.db.set_trace_callback(statements.append)
        report = GmailEventReconcile(self.app).list_events('customer:1')
        self.assertEqual(self.app.db.total_changes, changes)
        self.assertFalse(any(s.lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'BEGIN')) for s in statements))
        self.assertEqual(json.loads(self.app.db.execute('SELECT data FROM agent_jobs').fetchone()[0]), before)
        self.assertEqual(report['candidate_jobs'][0]['status'], 'running')
        self.assertEqual(report['candidate_jobs'][0]['origin'], 'manual_review_required')
        self.assertFalse(report['candidate_jobs'][0]['automatic_match'])
        self.assertNotIn('private body', json.dumps(report))

    def test_reports_missing_invalid_cross_object_mode_and_actual_status(self):
        self.event('missing', jid='absent')
        self.event('invalid', jid='broken')
        self.app.db.execute('INSERT INTO agent_jobs VALUES (?,?)', ('broken', '{broken'))
        self.app.db.commit()
        self.job('other', oid='customer:2'); self.event('mismatch', jid='other')
        self.job('mode', mode='draft'); self.event('mode-mismatch', jid='mode')
        self.job('good', status='failed'); self.event('legacy-linked', state='dispatched', jid='good')
        rows = {x['message_id']: x for x in self.service.list_events('customer:1')['events']}
        self.assertEqual(rows['missing']['relation'], 'job_missing')
        self.assertEqual(rows['invalid']['relation'], 'job_record_invalid')
        self.assertEqual(rows['mismatch']['relation'], 'object_mismatch')
        self.assertEqual(rows['mode-mismatch']['relation'], 'mode_mismatch')
        self.assertEqual(rows['legacy-linked']['job']['status'], 'failed')
        self.assertEqual(rows['legacy-linked']['relation'], 'object_only_manual_review_required')

    def test_link_legacy_records_persists_manual_audit_and_never_changes_job(self):
        for index, state in enumerate(('outcome_unknown', 'dispatched_unlinked', 'failed')):
            mid, jid = 'm'+str(index), 'j'+str(index)
            self.event(mid, state=state, at=None); before = self.job(jid)
            linked = self.link(mid, jid)
            self.assertEqual(linked['dispatch_state'], 'dispatched')
            self.assertEqual(linked['manual_link_audit']['origin'], 'manual_review_required')
            self.assertEqual(linked['manual_link_audit']['previous_snapshot']['updated_at'], None)
            self.assertEqual(linked['manual_link_audit']['previous_error'], 'callback error')
            self.assertEqual(json.loads(self.app.db.execute('SELECT data FROM agent_jobs WHERE id=?', (jid,)).fetchone()[0]), before)
        restarted = GmailEventReconcile(self.open_app())
        report = restarted.list_events('customer:1')
        self.assertTrue(all(r['relation'] == 'manually_verified' for r in report['events']))
        self.assertTrue(all(not r['manual_link_allowed'] for r in report['events']))
        self.assertTrue(all(not r['automatic_replay'] for r in report['events']))

    def test_explicit_human_confirmation_and_note_are_required(self):
        self.event(); self.job(); snap = self.snapshot()
        for confirmed, note in [(False, 'checked'), (1, 'checked'), (True, ''), (True, ' '), (True, 'x'*4001)]:
            with self.subTest(confirmed=confirmed, note=note[:20]):
                with self.assertRaises(ReconcileRejected):
                    self.service.link_existing('customer:1', 'm1', 'j1', snap, confirmed=confirmed, manual_note=note)
        self.assertEqual(self.snapshot(), snap)

    def test_rejects_active_deferred_acknowledged_and_already_linked_events(self):
        self.job()
        for index, state in enumerate(('dispatching', 'deferred', 'dispatched', 'acknowledged', 'unexpected')):
            mid = 'm'+str(index); self.event(mid, state=state)
            with self.assertRaises(ReconcileRejected):
                self.link(mid)
        self.event('has-job', jid='missing-job')
        with self.assertRaises(ReconcileRejected): self.link('has-job')
        self.event('ack')
        self.app.db.execute('INSERT INTO gmail_acknowledged VALUES (?,?)', ('customer:1', 'ack')); self.app.db.commit()
        with self.assertRaises(ReconcileRejected): self.link('ack')
        row = next(r for r in self.service.list_events('customer:1')['events'] if r['message_id'] == 'ack')
        self.assertTrue(row['acknowledged']); self.assertFalse(row['manual_link_allowed'])

    def test_rejects_missing_cross_object_wrong_mode_invalid_or_conflicting_job(self):
        self.event(); self.job('cross', oid='customer:2'); self.job('mode', mode='outreach_draft')
        self.job('source', source={'kind': 'gmail_reply', 'object_id': 'customer:1', 'message_id': 'other-mail'})
        self.app.db.execute('INSERT INTO agent_jobs VALUES (?,?)', ('invalid', '[]')); self.app.db.commit()
        for jid in ('absent', 'cross', 'mode', 'source', 'invalid'):
            with self.subTest(jid=jid):
                with self.assertRaises(ReconcileRejected): self.link(jid=jid)
        self.assertIsNone(self.snapshot()['job_id'])

    def test_explicit_event_origin_is_checked_but_does_not_skip_human_confirmation(self):
        self.event(); self.job(source={'kind': 'gmail_reply', 'object_id': 'customer:1', 'message_id': 'm1'})
        result = self.link()
        self.assertEqual(result['manual_link_audit']['origin'], 'explicit_event')
        self.assertEqual(self.service.list_events('customer:1')['events'][0]['relation'], 'manually_verified')

    def test_duplicate_job_link_is_rejected_across_objects(self):
        self.event(); self.job(); self.event('other', state='dispatched', jid='j1', oid='customer:2')
        with self.assertRaises(ReconcileRejected): self.link()
        self.assertIsNone(self.snapshot()['job_id'])

    def test_all_three_snapshot_fields_are_compared_including_null(self):
        self.event(); self.job(); original = self.snapshot()
        for key, value in [('dispatch_state', 'failed'), ('job_id', 'different'), ('updated_at', None)]:
            snap = dict(original); snap[key] = value
            with self.subTest(key=key):
                with self.assertRaises(ReconcileConflict): self.link(snapshot=snap)
        with self.assertRaises(ReconcileRejected):
            self.service.link_existing('customer:1', 'm1', 'j1', {'dispatch_state': 'failed'}, confirmed=True, manual_note='checked')
        self.assertEqual(self.snapshot(), original)

    def test_acknowledgement_on_another_connection_after_snapshot_blocks_link(self):
        self.event(); self.job(); snap = self.snapshot(); other = self.open_app()
        other.db.execute('INSERT INTO gmail_acknowledged VALUES (?,?)', ('customer:1', 'm1')); other.db.commit()
        with self.assertRaises(ReconcileRejected): self.link(snapshot=snap)
        self.assertEqual(self.snapshot(), snap)

    def test_two_connections_competing_same_event_have_exactly_one_winner(self):
        self.event(); self.job('j1'); self.job('j2')
        first = self.service; second = GmailEventReconcile(self.open_app())
        snap = self.snapshot(); barrier = threading.Barrier(3); successes = []; failures = []
        def run(service, jid):
            try:
                barrier.wait(); successes.append(self.link(jid=jid, snapshot=snap, service=service))
            except Exception as exc:
                failures.append(exc)
        threads = [threading.Thread(target=run, args=(first, 'j1')), threading.Thread(target=run, args=(second, 'j2'))]
        for thread in threads: thread.start()
        barrier.wait()
        for thread in threads: thread.join(10)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(len(successes), 1); self.assertEqual(len(failures), 1)
        self.assertIsInstance(failures[0], ReconcileConflict)
        self.assertEqual(len(self.service.list_events('customer:1')['events']), 1)

    def test_two_events_cannot_claim_same_job_even_with_independent_connections(self):
        self.event('m1'); self.event('m2'); self.job()
        first = self.service; second = GmailEventReconcile(self.open_app())
        snapshots = {mid: self.snapshot(mid) for mid in ('m1', 'm2')}
        barrier = threading.Barrier(3); successes = []; failures = []
        def run(service, mid):
            try:
                barrier.wait(); successes.append(self.link(mid, snapshot=snapshots[mid], service=service))
            except Exception as exc: failures.append(exc)
        threads = [threading.Thread(target=run, args=(first, 'm1')), threading.Thread(target=run, args=(second, 'm2'))]
        for thread in threads: thread.start()
        barrier.wait()
        for thread in threads: thread.join(10)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(len(successes), 1); self.assertEqual(len(failures), 1)
        self.assertIsInstance(failures[0], ReconcileRejected)
        self.assertEqual(self.app.db.execute("SELECT count(*) FROM gmail_reply_events WHERE job_id='j1'").fetchone()[0], 1)

    def test_unknown_states_survive_restart_without_replay(self):
        for state in ('outcome_unknown', 'dispatched_unlinked', 'failed', 'dispatching', 'deferred'):
            self.event(state, state=state)
        before = self.app.db.execute('SELECT * FROM gmail_reply_events ORDER BY message_id').fetchall()
        restarted = GmailEventReconcile(self.open_app())
        self.assertEqual(len(restarted.list_events('customer:1')['events']), 5)
        self.assertEqual(self.app.db.execute('SELECT * FROM gmail_reply_events ORDER BY message_id').fetchall(), before)

    def test_caller_transaction_is_never_committed_or_rolled_back(self):
        self.event(); self.job(); snap = self.snapshot()
        self.app.db.execute('BEGIN'); self.app.db.execute("UPDATE agent_jobs SET data=data")
        with self.assertRaises(ReconcileRejected): self.link(snapshot=snap)
        self.assertTrue(self.app.db.in_transaction)
        self.app.db.rollback()

    def test_missing_tables_and_legacy_columns_are_readable_without_migration(self):
        empty = SimpleNamespace(db=sqlite3.connect(':memory:'), lock=threading.RLock())
        self.addCleanup(empty.db.close)
        service = GmailEventReconcile(empty)
        self.assertFalse(service.list_events('customer:1')['available'])
        empty.db.execute('CREATE TABLE gmail_reply_events (object_id TEXT,message_id TEXT,dispatch_state TEXT)')
        empty.db.execute("INSERT INTO gmail_reply_events VALUES ('customer:1','m1','failed')"); empty.db.commit()
        report = service.list_events('customer:1')
        self.assertTrue(report['available']); self.assertIsNone(report['events'][0]['acknowledged'])
        self.assertFalse(report['events'][0]['manual_link_allowed'])
        self.assertEqual(len(list(empty.db.execute('PRAGMA table_info(gmail_reply_events)'))), 3)
        with self.assertRaises(ReconcileRejected):
            service.link_existing('customer:1', 'm1', 'j1', report['events'][0]['snapshot'], confirmed=True, manual_note='checked')

    def test_unknown_commit_result_requires_readback_and_does_not_replay(self):
        self.event(); self.job(); snap = self.snapshot(); real = self.app.db
        class CommitThenRaise:
            def __getattr__(self, name): return getattr(real, name)
            def commit(self):
                real.commit()
                raise OSError('connection lost after commit')
        self.app.db = CommitThenRaise()
        with self.assertRaises(ReconcileOutcomeUnknown): self.link(snapshot=snap)
        restarted = GmailEventReconcile(self.open_app())
        row = restarted.list_events('customer:1')['events'][0]
        self.assertEqual(row['job_id'], 'j1'); self.assertFalse(row['automatic_replay'])
        with self.assertRaises(ReconcileConflict): self.link(snapshot=snap, service=restarted)


if __name__ == '__main__':
    unittest.main()
