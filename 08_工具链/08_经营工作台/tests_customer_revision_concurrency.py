"""Real spawn-process revision races over synthetic customer data only."""
import copy
import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest

from customer_workspace import CustomerWorkspace
from workspaces import WorkspaceConflict


OID = 'customer:website-revision-fixture'
OBJECT = {'id': OID, 'kind': 'customer', 'source': 'synthetic fixture',
          'content': json.dumps({'requirements': 'Synthetic sample request'})}


def open_workspace(root, database):
    app = SimpleNamespace(root=Path(root), db=sqlite3.connect(database, timeout=10),
                          lock=threading.RLock(), business=SimpleNamespace(
                              get_object=lambda oid: copy.deepcopy(OBJECT)))
    return app, CustomerWorkspace(app)


def save_snapshot(root, database, kind, body, ready, start, results):
    app = None
    try:
        app, work = open_workspace(root, database)
        ready.set()
        if not start.wait(15):
            raise RuntimeError('Synthetic race start timed out')
        getattr(work, 'save_' + kind)(OID, body)
        results.put(('saved', os.getpid(), body))
    except WorkspaceConflict:
        results.put(('conflict', os.getpid(), body))
    except Exception as exc:
        results.put(('unexpected', os.getpid(), type(exc).__name__, str(exc)))
    finally:
        if app is not None:
            app.db.close()


class CustomerRevisionConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.database = str(self.root / 'synthetic.sqlite3')
        self.app, self.work = open_workspace(self.root, self.database)
        self.addCleanup(self.app.db.close)

    def race(self, kind, field):
        snapshot = getattr(self.work, kind)(OID)
        bodies = [{'revision': snapshot['revision'], field: value}
                  for value in ('writer one', 'writer two')]
        if kind == 'profile':
            for body in bodies:
                body['source_hash'] = snapshot['source_hash']
        ctx = multiprocessing.get_context('spawn')
        ready = [ctx.Event(), ctx.Event()]
        start, results = ctx.Event(), ctx.Queue()
        children = [ctx.Process(target=save_snapshot,
                                args=(str(self.root), self.database, kind, body,
                                      signal, start, results))
                    for body, signal in zip(bodies, ready)]
        try:
            for child in children:
                child.start()
            for signal in ready:
                self.assertTrue(signal.wait(15), 'Independent child did not become ready')
            start.set()
            outcomes = [results.get(timeout=20), results.get(timeout=20)]
            for child in children:
                child.join(15)
                self.assertEqual(child.exitcode, 0)
            self.assertEqual(len({row[1] for row in outcomes}), 2)
            self.assertNotIn(os.getpid(), {row[1] for row in outcomes})
            self.assertCountEqual([row[0] for row in outcomes], ['saved', 'conflict'])
            winner = next(row[2] for row in outcomes if row[0] == 'saved')
            reopened, work = open_workspace(self.root, self.database)
            try:
                current = getattr(work, kind)(OID)
                self.assertEqual(current[field], winner[field])
                self.assertNotEqual(current['revision'], snapshot['revision'])
            finally:
                reopened.db.close()
        finally:
            start.set()
            for child in children:
                if child.pid is not None:
                    child.join(3)
                    if child.is_alive():
                        child.terminate()
                        child.join(3)
            results.close()
            results.join_thread()

    def test_same_profile_field_has_exactly_one_winner(self):
        self.race('profile', 'translation_zh')

    def test_same_workflow_field_has_exactly_one_winner(self):
        self.race('workflow', 'note')

    def assert_snapshots_rejected(self, profile, workflow):
        self.assertNotEqual(profile['revision'], self.work.profile(OID)['revision'])
        self.assertNotEqual(workflow['revision'], self.work.workflow(OID)['revision'])
        with self.assertRaises(WorkspaceConflict):
            self.work.save_profile(OID, {'revision': profile['revision'],
                                        'source_hash': profile['source_hash'],
                                        'translation_zh': 'stale analysis'})
        with self.assertRaises(WorkspaceConflict):
            self.work.save_workflow(OID, {'revision': workflow['revision'],
                                         'note': 'stale workflow'})
        self.assertEqual(self.work.profile(OID)['translation_zh'], '')
        self.assertEqual(self.work.workflow(OID)['note'], '')

    def test_independent_connection_reply_event_and_ack_invalidate_both_snapshots(self):
        self.app.db.execute('CREATE TABLE gmail_reply_events '
                            '(object_id TEXT, message_id TEXT, dispatch_state TEXT, '
                            'PRIMARY KEY(object_id,message_id))')
        self.app.db.execute('CREATE TABLE gmail_acknowledged '
                            '(object_id TEXT PRIMARY KEY,message_id TEXT)')
        self.app.db.commit()
        other = sqlite3.connect(self.database, timeout=10)
        try:
            old_profile, old_workflow = self.work.profile(OID), self.work.workflow(OID)
            other.execute('INSERT INTO gmail_reply_events VALUES (?,?,?)',
                          (OID, 'synthetic-message', 'dispatching'))
            other.commit()
            self.assert_snapshots_rejected(old_profile, old_workflow)
            after_event_profile = self.work.profile(OID)
            after_event_workflow = self.work.workflow(OID)
            other.execute('INSERT INTO gmail_acknowledged VALUES (?,?)',
                          (OID, 'synthetic-message'))
            other.commit()
            self.assert_snapshots_rejected(after_event_profile, after_event_workflow)
        finally:
            other.close()


if __name__ == '__main__':
    unittest.main()
