"""Synthetic customers only; no network, CRM or Gmail writes."""
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest

from customer_batches import CustomerBatches
from workspaces import WorkspaceConflict


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dbpath = Path(self.temp.name) / '.local' / 'runs.sqlite3'
        self.dbpath.parent.mkdir()
        self.objects = {oid: {'id': oid, 'kind': 'customer', 'title': oid, 'summary': 'Synthetic buyer',
                             'source_type': 'manual_import', 'content': json.dumps({
                                 'country': 'US', 'contact_verification': 'verified', 'suppression_state': 'clear'})}
                        for oid in ('customer:a', 'customer:b')}
        self.profile = {'revision': 'p1', 'cleaned': {'country': 'US'},
                        'provenance': {'source_verification': {'state': 'verified'},
                                       'evidence':[{'url':'https://buyer.example.test/about','observed_at':'2026-11-06'}]}}
        self.raw = b'synthetic catalogue'
        self.drafts = {'customer:a': {'version': 'd1', 'status': 'draft', 'to': 'buyer@example.test',
                                    'subject': 'Synthetic proposal', 'body_en': 'Synthetic English', 'body_zh': 'Synthetic Chinese',
                                    'attachments': [{'id': 'a', 'sha256': hashlib.sha256(self.raw).hexdigest()}]}}
        def get(oid):
            if oid not in self.objects:
                raise ValueError('Missing')
            return copy.deepcopy(self.objects[oid])
        self.business = SimpleNamespace(get_object=get, list_objects=lambda **kw: [copy.deepcopy(o) for o in self.objects.values() if
                                        (not kw.get('kind') or o['kind'] == kw['kind']) and
                                        (not kw.get('q') or kw['q'] in o['title'])])
        self.app = self.make_app()
        self.service = CustomerBatches(self.app)

    def make_app(self):
        db = sqlite3.connect(self.dbpath)
        self.addCleanup(db.close)
        return SimpleNamespace(db=db, lock=threading.RLock(), business=self.business,
                               customer_workspace=SimpleNamespace(profile=lambda oid: copy.deepcopy(self.profile)),
                               gmail_drafts=SimpleNamespace(_saved=lambda oid: copy.deepcopy(self.drafts.get(oid)),
                                                            _attachment_bytes=lambda a: self.raw))

    def create(self, ids=None):
        return self.service.create({'title': 'Synthetic batch', 'object_ids': ids or ['customer:a']})

    def review(self, b, state, **fields):
        return self.service.review_item(b['id'], 'customer:a', {'revision': b['revision'], 'review_state': state, **fields})

    def test_references_only_persist_and_reopen(self):
        b = self.create(['customer:a', 'customer:a'])
        self.assertEqual(b['counts']['total'], 1)
        b = self.review(b, 'changes_requested', change_request='Only this customer', notes='Local note')
        stored = json.loads(self.app.db.execute('SELECT data FROM customer_batches').fetchone()[0])
        self.assertNotIn('Synthetic English', json.dumps(stored))
        self.assertNotIn('buyer@example.test', json.dumps(stored))
        self.assertEqual(stored['items'][0]['change_request'], 'Only this customer')
        self.assertEqual(CustomerBatches(self.make_app()).get(b['id'])['items'][0]['notes'], 'Local note')

    def test_explicit_and_filtered_additions_are_deduplicated(self):
        b = self.create()
        b = self.service.add_items(b['id'], {'revision': b['revision'], 'object_ids': ['customer:a'],
                                             'filters': {'kind': 'customer', 'source_type': 'manual_import'}})
        self.assertEqual(b['counts']['total'], 2)
        self.assertEqual(len(self.service.get(b['id'], q='customer:b')['items']), 1)
        self.assertEqual(self.service.list_batches()['items'][0]['counts']['total'], 2)

    def test_invalid_addition_rolls_back_all_members(self):
        b = self.create()
        with self.assertRaises(ValueError):
            self.service.add_items(b['id'], {'revision': b['revision'], 'object_ids': ['customer:b', 'customer:missing']})
        self.assertEqual(self.service.get(b['id'])['revision'], b['revision'])

    def test_remove_only_batch_reference_preserves_customer_draft_and_suppression(self):
        batch=self.create(['customer:a','customer:b'])
        batch=self.review(batch,'do_not_contact')
        with self.assertRaises(WorkspaceConflict):
            self.service.remove_items(batch['id'],{'revision':'stale','object_ids':['customer:a']})
        result=self.service.remove_items(batch['id'],{'revision':batch['revision'],'object_ids':['customer:a']})
        self.assertEqual([item['object_id'] for item in result['items']],['customer:b'])
        self.assertIn('customer:a',self.objects);self.assertIn('customer:a',self.drafts)
        later=self.service.create({'title':'Later batch','object_ids':['customer:a']})
        self.assertEqual(later['items'][0]['quality']['suppression_state'],'suppressed')

    def test_concurrent_connection_cannot_overwrite_notes(self):
        b = self.create()
        other = CustomerBatches(self.make_app())
        self.review(b, 'deferred', notes='New note')
        with self.assertRaises(WorkspaceConflict):
            other.review_item(b['id'], 'customer:a', {'revision': b['revision'], 'review_state': 'pending', 'notes': 'Old note'})
        self.assertEqual(other.get(b['id'])['items'][0]['notes'], 'New note')

    def test_review_of_one_customer_is_independent_of_other_customer_edit(self):
        b = self.create(['customer:a','customer:b'])
        a = next(item for item in b['items'] if item['object_id']=='customer:a')
        other = CustomerBatches(self.make_app())
        other.review_item(b['id'],'customer:b',{'revision':b['revision'],'review_state':'deferred','notes':'B only'})
        updated=self.service.review_item(b['id'],'customer:a',{'revision':b['revision'],
            'item_revision':a['item_revision'],'review_state':'changes_requested','change_request':'A only'})
        self.assertEqual(next(item for item in updated['items'] if item['object_id']=='customer:b')['notes'],'B only')
        with self.assertRaises(WorkspaceConflict):
            other.review_item(b['id'],'customer:a',{'item_revision':a['item_revision'],
                'review_state':'pending','notes':'stale'})

    def test_customer_and_draft_changes_invalidate_stale_revision(self):
        b = self.create()
        self.profile['revision'] = 'p2'
        with self.assertRaises(WorkspaceConflict):
            self.review(b, 'approved', draft_version='d1')
        b = self.service.get(b['id'])
        self.drafts['customer:a']['version'] = 'd2'
        with self.assertRaises(WorkspaceConflict):
            self.review(b, 'approved', draft_version='d1')

    def test_approval_binds_actual_bytes_and_never_authorizes_send(self):
        b = self.create()
        with self.assertRaises(WorkspaceConflict):
            self.review(b, 'approved', draft_version='wrong')
        b = self.review(b, 'approved', draft_version='d1')
        self.assertFalse(b['items'][0]['review_stale'])
        self.assertFalse(b['items'][0]['quality']['send_ready'])
        self.raw = b'changed attachment despite unchanged draft version'
        b = self.service.get(b['id'])
        self.assertTrue(b['items'][0]['review_stale'])
        self.assertEqual(b['items'][0]['quality']['status'], 'blocked')
        with self.assertRaises(ValueError):
            self.review(b, 'approved', draft_version='d1')

    def test_unknown_provenance_and_suppression_cannot_be_approved(self):
        self.profile['provenance']['source_verification']['state'] = 'unverified'
        self.profile['provenance']['evidence'] = []
        self.objects['customer:a']['content'] = '{}'
        b = self.create()
        self.assertEqual(b['items'][0]['quality']['contact_state'], 'unknown')
        with self.assertRaisesRegex(ValueError, '尚不能通过审核'):
            self.review(b, 'approved', draft_version='d1')

    def test_content_review_does_not_mark_unknown_send_checks_clear(self):
        self.profile['provenance']['source_verification']['state'] = 'unverified'
        self.objects['customer:a']['content'] = '{}'
        b = self.create()
        b = self.review(b, 'approved', draft_version='d1')
        self.assertEqual(b['items'][0]['review_state'],'approved')
        self.assertFalse(b['items'][0]['quality']['send_ready'])
        self.assertIn('客户来源尚未核实',b['items'][0]['quality']['reasons'])

    def test_suppressed_and_missing_draft_stay_blocked_without_creating_draft(self):
        self.objects['customer:a']['content'] = json.dumps({'unsubscribed': True})
        b = self.create(['customer:a', 'customer:b'])
        self.assertEqual(b['items'][0]['quality']['suppression_state'], 'suppressed')
        self.assertIsNone(b['items'][1]['draft'])
        self.assertNotIn('customer:b', self.drafts)

    def test_unavailable_source_remains_a_reference_with_explicit_unknowns(self):
        b = self.create()
        del self.objects['customer:a']
        b = self.service.get(b['id'])
        self.assertEqual(b['items'][0]['object_id'], 'customer:a')
        self.assertEqual(b['items'][0]['quality']['source_state'], 'unknown')
        self.assertEqual(b['items'][0]['quality']['status'], 'blocked')

    def test_invalid_states_fields_and_non_customer_rejected(self):
        b = self.create()
        with self.assertRaises(ValueError):
            self.review(b, 'sent')
        with self.assertRaises(ValueError):
            self.service.create({'title': 'Bad', 'body_en': 'Do not store'})
        self.objects['product:a'] = {'id': 'product:a', 'kind': 'product'}
        with self.assertRaises(ValueError):
            self.create(['product:a'])

    def test_dnc_is_shared_across_batches_and_never_implicitly_cleared(self):
        first=self.create()
        other=self.create()
        self.review(first,'do_not_contact')
        second=self.service.get(other['id'])
        self.assertEqual(second['items'][0]['quality']['suppression_state'],'suppressed')
        with self.assertRaises(ValueError):self.review(second,'approved',draft_version='d1')
        first=self.service.get(first['id'])
        self.review(first,'pending')
        self.assertEqual(self.service.get(other['id'])['items'][0]['quality']['suppression_state'],'suppressed')
        reopened=CustomerBatches(self.make_app())
        self.assertEqual(reopened.get(other['id'])['items'][0]['quality']['suppression_state'],'suppressed')

    def test_legacy_dnc_backfilled_on_reopen_and_persists_after_batch_edit(self):
        first=self.create()
        data=json.loads(self.app.db.execute('SELECT data FROM customer_batches WHERE id=?',(first['id'],)).fetchone()[0])
        data['items'][0]['review_state']='do_not_contact'
        self.app.db.execute('UPDATE customer_batches SET data=? WHERE id=?',(json.dumps(data),first['id']))
        self.app.db.commit()
        reopened=CustomerBatches(self.make_app())
        first=reopened.get(first['id'])
        reopened.review_item(first['id'],'customer:a',{'revision':first['revision'],'review_state':'pending'})
        self.assertEqual(reopened.get(first['id'])['items'][0]['quality']['suppression_state'],'suppressed')


if __name__ == '__main__':
    unittest.main()
