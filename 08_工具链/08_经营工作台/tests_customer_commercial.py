import copy
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from customer_workspace import CustomerWorkspace
from desk_mcp import DeskTools


class CommercialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.original = {'id': 'customer:website-ANON', 'kind': 'customer', 'source': 'anonymous fixture',
                         'content': json.dumps({'requirements': 'Discuss samples before bulk'})}
        self.app = SimpleNamespace(root=Path(self.temp.name), db=sqlite3.connect(':memory:'),
                                   lock=threading.RLock(), business=SimpleNamespace(get_object=lambda oid: copy.deepcopy(self.original)))
        self.addCleanup(self.app.db.close)
        self.work = CustomerWorkspace(self.app)

    def save(self, **data):
        return self.work.save_commercial(self.original['id'], {'revision': self.work.commercial(self.original['id'])['revision'], **data})

    def test_roundtrip_all_stages_and_shared_next_action(self):
        before = copy.deepcopy(self.original)
        for kind in ('quotation', 'sample', 'order'):
            result = self.save(record={'kind': kind, 'status': 'draft', 'summary': 'Discussion only'},
                               owner='Sales', next_action='Confirm selection', due_at=None)
        self.assertEqual(len(result['records']), 3)
        self.assertEqual(self.work.workflow(self.original['id'])['next_action'], 'Confirm selection')
        self.assertEqual(self.original, before)
        self.assertEqual(CustomerWorkspace(self.app).commercial(self.original['id'])['records'], result['records'])
        self.assertFalse(result['external_action'])

    def test_agent_writes_current_customer_record_without_external_action(self):
        self.app.customer_workspace=self.work
        self.app.business.app=self.app
        tools=DeskTools(self.app.business,self.app.root,self.original['id'])
        result=tools.call('save_customer_commercial',{'record':{'kind':'quotation','status':'draft','summary':'准备选款报价'},'next_action':'确认尺码'})
        self.assertEqual(result['records'][0]['summary'],'准备选款报价')
        self.assertEqual(result['next_action'],'确认尺码')
        self.assertFalse(result['external_action'])

    def test_actual_without_attachment_and_partial_edit(self):
        result = self.save(record={'kind': 'sample', 'status': 'recorded', 'summary': 'Agreement confirmed',
                                   'purpose': 'Fit evaluation', 'exclusions': 'No controlled hardness versions'})
        row = result['records'][0]
        result = self.save(record={'id': row['id'], 'actual_result': 'Evaluation pending', 'reference': 'Original project'})
        self.assertEqual(len(result['records']), 1)
        self.assertEqual(result['records'][0]['status'], 'recorded')

    def test_conflict_and_invalid_updates_do_not_write(self):
        old = self.work.commercial(self.original['id'])
        self.save(owner='Other editor')
        with self.assertRaisesRegex(ValueError, '已变化'):
            self.work.save_commercial(self.original['id'], {'revision': old['revision'], 'owner': 'Overwrite'})
        for record in ({'kind': 'order', 'status': 'won', 'summary': 'Bad'},
                       {'kind': 'sample', 'status': 'draft', 'summary': ''},
                       {'id': 'missing', 'kind': 'order', 'status': 'draft', 'summary': 'Bad'}):
            with self.assertRaises(ValueError):
                self.save(record=record)
        self.assertEqual(self.work.commercial(self.original['id'])['owner'], 'Other editor')

    def test_order_projection_and_continuation_remain_separate_from_inquiry_queue(self):
        self.original.update(source_type='alibaba_order_buyer', content=json.dumps({'orders': [{'id': 'anon', 'status': 'Awaiting payment'}]}))
        result = self.save(next_action='Check payment', owner='Sales')
        self.assertTrue(self.work.workflow(self.original['id'])['excluded'])
        self.assertEqual(result['source_orders'][0]['id'], 'anon')
        result['source_orders'][0]['status'] = 'Changed'
        self.assertEqual(self.work.commercial(self.original['id'])['source_orders'][0]['status'], 'Awaiting payment')


if __name__ == '__main__':
    unittest.main()
