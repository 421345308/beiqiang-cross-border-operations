"""Synthetic independent-connection commits between a save and its return."""
from pathlib import Path
import tempfile
import unittest

from tests_customer_revision_concurrency import OID, open_workspace
from workspaces import WorkspaceConflict


class CommitHookConnection:
    """Keep real SQLite commit semantics, then run exactly one interleaving."""
    def __init__(self, connection):
        self.connection = connection
        self.after_commit = None
        self.hook_calls = 0

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def commit(self):
        self.connection.commit()
        callback, self.after_commit = self.after_commit, None
        if callback is not None:
            self.hook_calls += 1
            callback()


class CustomerRevisionReturnRaceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        database = str(root / 'synthetic.sqlite3')
        self.app, self.work = open_workspace(root, database)
        self.addCleanup(self.app.db.close)
        self.other_app, self.other = open_workspace(root, database)
        self.addCleanup(self.other_app.db.close)
        self.assertIsNot(self.app.db, self.other_app.db)
        self.connection = CommitHookConnection(self.app.db)
        self.app.db = self.connection

    def test_gmail_second_transition_conflicts_after_intervening_human_action(self):
        before = self.work.workflow(OID)
        committed = {}

        def human_after_commit():
            committed.update(self.other.workflow(OID))
            self.other.save_workflow(OID, {
                'revision': committed['revision'],
                'next_action': 'Human: hold sample discussion'})

        self.connection.after_commit = human_after_commit
        first = self.work.save_workflow(OID, {
            'revision': before['revision'], 'state': 'preparing',
            'next_action': 'First automatic transition'})
        self.assertEqual(self.connection.hook_calls, 1)
        self.assertEqual(first, committed)
        self.assertEqual(first['next_action'], 'First automatic transition')
        with self.assertRaises(WorkspaceConflict):
            self.work.save_workflow(OID, {
                'revision': first['revision'], 'state': 'waiting_customer',
                'next_action': 'Automatic: wait for reply'})
        current = self.other.workflow(OID)
        self.assertEqual(current['state'], 'preparing')
        self.assertEqual(current['next_action'], 'Human: hold sample discussion')
        self.assertNotEqual(current['revision'], first['revision'])
        self.assertEqual(self.connection.hook_calls, 1)
        self.assertFalse(self.app.db.in_transaction)

    def test_analysis_returns_own_committed_snapshot(self):
        before = self.work.profile(OID)
        committed = {}

        def human_after_commit():
            committed.update(self.other.profile(OID))
            self.other.save_profile(OID, {
                'revision': committed['revision'],
                'source_hash': committed['source_hash'],
                'translation_zh': 'Later human translation'})

        self.connection.after_commit = human_after_commit
        returned = self.work.save_profile(OID, {
            'revision': before['revision'], 'source_hash': before['source_hash'],
            'translation_zh': 'First committed translation'})
        self.assertEqual(self.connection.hook_calls, 1)
        self.assertEqual(returned, committed)
        self.assertEqual(returned['translation_zh'], 'First committed translation')
        current = self.other.profile(OID)
        self.assertEqual(current['translation_zh'], 'Later human translation')
        self.assertNotEqual(current['revision'], returned['revision'])
        self.assertFalse(self.app.db.in_transaction)

    def test_commercial_returns_own_committed_snapshot(self):
        before = self.work.commercial(OID)
        committed = {}

        def human_after_commit():
            committed.update(self.other.commercial(OID))
            self.other.save_commercial(OID, {
                'revision': committed['revision'], 'owner': 'Human owner',
                'next_action': 'Human commercial decision'})

        self.connection.after_commit = human_after_commit
        returned = self.work.save_commercial(OID, {
            'revision': before['revision'], 'owner': 'First owner',
            'next_action': 'First commercial decision'})
        self.assertEqual(self.connection.hook_calls, 1)
        self.assertEqual(returned, committed)
        self.assertEqual(returned['owner'], 'First owner')
        self.assertEqual(returned['next_action'], 'First commercial decision')
        current = self.other.commercial(OID)
        self.assertEqual(current['owner'], 'Human owner')
        self.assertEqual(current['next_action'], 'Human commercial decision')
        self.assertNotEqual(current['revision'], returned['revision'])
        self.assertFalse(self.app.db.in_transaction)


if __name__ == '__main__':
    unittest.main()
