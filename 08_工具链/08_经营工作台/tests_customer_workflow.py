import copy
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest
from customer_workspace import CustomerWorkspace
from customer_workflow import STATES

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.rows={}
        def add(oid,source_type,record):
            self.rows[oid]={'id':oid,'kind':'customer','title':oid,'source_type':source_type,'source':'fixture',
                'content':json.dumps(record),'original_text':record.get('original_text')}
        add('customer:website-one','website',{'reference':'one','name':'Contact','email':'buyer@example.test','requirements':'Need shoes','receivedAt':'2000-01-01T00:00:00Z','status':'new'})
        add('customer:intake:two','manual_import',{'original_text':'New request','company':'Buyer','received_at':'2026-10-31T00:00:00Z'})
        add('customer:oldcrm','local',{'notes':'Historic CRM review'})
        add('customer:order','alibaba_order_buyer',{'orders':[{'id':'71','status':'paid','products':[{'name':'Shoe','quantity':'12','unit':'pair'}]}]})
        self.app=SimpleNamespace(root=Path(self.temp.name),db=sqlite3.connect(':memory:'),lock=threading.RLock(),
            business=SimpleNamespace(get_object=lambda oid:copy.deepcopy(self.rows[oid]),list_objects=lambda kind='':[copy.deepcopy(row) for row in self.rows.values()]))
        self.addCleanup(self.app.db.close);self.work=CustomerWorkspace(self.app)
    def test_default_buckets_no_old_received_urgency_and_orders_excluded(self):
        active=self.work.queue();self.assertEqual(len(active['items']),2);self.assertIs(active['items'],active['rows'])
        self.assertEqual(active['counts']['history'],1);self.assertEqual(active['counts']['archive'],0)
        self.assertEqual(active['counts']['overdue'],0)
        self.assertFalse(any(row['source_type']=='alibaba_order_buyer' for row in active['items']))
        old=next(row for row in active['items'] if row['object_id']=='customer:website-one')
        self.assertEqual(old['workflow']['priority'],'normal');self.assertIsNone(old['workflow']['due_at']);self.assertFalse(old['workflow']['overdue'])
        self.assertEqual(self.work.queue('history')['items'][0]['object_id'],'customer:oldcrm')
    def test_progress_graph_same_state_updates_and_ended_reopen(self):
        oid='customer:website-one'
        with self.assertRaises(ValueError):self.work.save_workflow(oid,{'state':'won'})
        first=self.work.save_workflow(oid,{'state':'preparing','next_action':'Prepare answer'})
        self.assertEqual(first['pending_party'],'internal')
        waiting=self.work.save_workflow(oid,{'state':'waiting_customer'})
        self.assertEqual(waiting['pending_party'],'customer')
        self.work.save_workflow(oid,{'state':'quoting'})
        won=self.work.save_workflow(oid,{'state':'won'})
        self.assertEqual(won['bucket'],'archive');self.assertEqual(won['pending_label'],'已结束')
        self.assertEqual({r['state'] for r in won['allowed_transitions']},{'new','preparing'})
        with self.assertRaises(ValueError):self.work.save_workflow(oid,{'state':'sampling'})
        reopen=self.work.save_workflow(oid,{'bucket':'active'})
        self.assertEqual(reopen['state'],'new');self.assertEqual(reopen['bucket'],'active')
        same=self.work.save_workflow(oid,{'state':'new','priority':'high'})
        self.assertEqual(same['priority'],'high');self.assertEqual(len(same['history']),len(reopen['history']))
    def test_history_can_choose_real_current_stage_and_archive_lost(self):
        activated=self.work.save_workflow('customer:oldcrm',{'bucket':'active','state':'sampling','note':'Manually confirmed current sample discussion'})
        self.assertEqual(activated['bucket'],'active');self.assertEqual(activated['state'],'sampling')
        ended=self.work.save_workflow('customer:oldcrm',{'state':'lost'})
        self.assertEqual(ended['bucket'],'archive');self.assertEqual(self.work.queue('history')['items'],[])
        self.assertEqual(self.work.queue('archive')['items'][0]['object_id'],'customer:oldcrm')
    def test_priority_explicit_due_sort_and_queue_filters(self):
        now=datetime.now(timezone.utc)
        self.work.save_workflow('customer:intake:two',{'priority':'urgent','next_action':'Urgent confirmed task'})
        self.work.save_workflow('customer:website-one',{'priority':'high','due_at':(now-timedelta(days=1)).isoformat()})
        rows=self.work.queue()['items'];self.assertEqual(rows[0]['object_id'],'customer:intake:two')
        self.assertTrue(rows[1]['workflow']['overdue']);self.assertEqual(self.work.queue()['counts']['overdue'],1)
        self.assertEqual(len(self.work.queue(q='Urgent confirmed')['items']),1)
        self.work.save_workflow('customer:website-one',{'due_at':''})
        self.assertEqual(self.work.queue()['counts']['overdue'],0)
        with self.assertRaises(ValueError):self.work.save_workflow('customer:website-one',{'due_at':'next Friday'})
        with self.assertRaises(ValueError):self.work.save_workflow('customer:website-one',{'priority':'inferred_urgent'})
    def test_same_profile_file_preserves_analysis_and_workflow_in_both_directions(self):
        oid='customer:website-one';profile=self.work.profile(oid)
        saved=self.work.save_profile(oid,{'source_hash':profile['source_hash'],'translation_zh':'需要鞋。',
            'operator_context':'这条数量为表单必填，不能当真实订单数量。',
            'analysis':{'brief':'采购条件待核','core_need':'选择合适鞋款','secondary_requests':['样品费用'],
                'conflicts':[],'questions_now':['实际采购数量？'],'recommended_reply':'先确认鞋款。'}})
        path=self.app.db.execute('SELECT path FROM customer_profiles WHERE object_id=?',(oid,)).fetchone()[0]
        self.work.save_workflow(oid,{'state':'preparing','note':'Internal only, no email sent'})
        self.assertEqual(self.app.db.execute('SELECT path FROM customer_profiles WHERE object_id=?',(oid,)).fetchone()[0],path)
        current=self.work.profile(oid);self.assertEqual(current['translation_zh'],'需要鞋。');self.assertEqual(current['workflow']['state'],'preparing')
        self.work.save_profile(oid,{'source_hash':profile['source_hash'],'analysis':{'next_action':'核实采购数量'}})
        final=self.work.profile(oid);self.assertEqual(final['workflow']['state'],'preparing');self.assertIn('不能当真实',final['operator_context'])
        row=next(row for row in self.work.queue()['items'] if row['object_id']==oid)
        self.assertEqual(row['analysis']['brief'],'采购条件待核');self.assertEqual(row['analysis']['questions_now'],['实际采购数量？'])
        with self.assertRaises(ValueError):self.work.save_profile(oid,{'source_hash':profile['source_hash'],'workflow':{'state':'won'}})
    def test_workflow_only_does_not_falsely_mark_empty_analysis_stale(self):
        oid='customer:website-one';original=copy.deepcopy(self.rows[oid])
        self.work.save_workflow(oid,{'next_action':'Check actual request'})
        profile=self.work.profile(oid);self.assertFalse(profile['stale']);self.assertIsNone(profile['derived_source_hash'])
        self.assertEqual(self.rows[oid],original)
    def test_recent_transition_history_is_bounded_and_persists(self):
        oid='customer:website-one'
        for i in range(26):self.work.save_workflow(oid,{'state':'preparing' if i%2==0 else 'waiting_customer'})
        current=CustomerWorkspace(self.app).workflow(oid)
        self.assertEqual(len(current['history']),20);self.assertEqual(current['history'][-1]['to'],'waiting_customer')
        self.assertEqual(current['history'][-1]['to_label'],'等客户')
    def test_order_summary_is_chinese_business_context_not_json_buyer_quotation(self):
        profile=self.work.profile('customer:order')
        self.assertEqual(profile['original_language'],'zh');self.assertIn('不是买家原话',profile['original_text'])
        self.assertIn('订单编号：71',profile['original_text']);self.assertIn('数量：12 pair',profile['original_text'])
        self.assertFalse(profile['original_text'].startswith('{'))
        with self.assertRaises(ValueError):self.work.save_workflow('customer:order',{'state':'preparing'})

if __name__=='__main__':unittest.main()
