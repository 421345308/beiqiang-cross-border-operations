"""Synthetic end-to-end batch confirmations with real SQLite and Gmail service.

No network or external send occurs. Race tests use independent connections.
"""
import base64
import copy
from datetime import timedelta
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from batch_sending import BatchSending, _now
from customer_batches import CustomerBatches
from gmail_drafts import GmailDrafts, SendRejected
from workspaces import WorkspaceConflict


class BatchSendingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.calls, self.inspections = [], []
        self.ids = ['customer:a','customer:b']
        self.objects = {oid:{'id':oid,'kind':'customer','title':oid,'content':json.dumps({
            'email':oid[-1]+'@example.test','evidence':[{'url':'https://example.test/contact','observed_at':'2026-11-06'}]})} for oid in self.ids}
        self.profiles = {oid:{'revision':'p1','stale':False,'provenance':{'source_verification':{'state':'verified'}}} for oid in self.ids}
        self.check_status = 'clear'
        self.on_check = None
        self.sender = lambda token,payload:{'id':'sent'+str(len(self.calls))}
        self.app = self.make_app()
        for oid in self.ids:
            draft = self.app.gmail_drafts.get(oid)
            draft = self.app.gmail_drafts.save(oid,draft['version'],{'subject':'Proposal '+oid,'body_en':'Synthetic English','body_zh':'Synthetic Chinese'})
            self.app.gmail_drafts.add_attachment(oid,draft['version'],filename='synthetic.pdf',data=base64.b64encode(b'synthetic catalogue').decode())
        self.batch = self.app.customer_batches.create({'title':'Synthetic batch','object_ids':self.ids})
        self.approve_all()

    def make_app(self):
        db = sqlite3.connect(self.root/'runs.sqlite3',check_same_thread=False,timeout=5)
        self.addCleanup(db.close)
        app = SimpleNamespace(db=db,lock=threading.RLock(),root=self.root,state=self.root)
        app.business = SimpleNamespace(get_object=lambda oid:copy.deepcopy(self.objects[oid]))
        app.customer_workspace = SimpleNamespace(profile=lambda oid:copy.deepcopy(self.profiles[oid]))
        app.gmail = SimpleNamespace(status=lambda:{'account_email':'sender@example.test'},peek=lambda oid:{})
        def sender(token,payload):
            self.assertFalse(db.in_transaction)
            self.calls.append(payload)
            return self.sender(token,payload)
        app.gmail_drafts = GmailDrafts(app,token_provider=lambda account:'fixture',sender=sender,grant_reader=lambda account:{})
        app.gmail_drafts._after_send = lambda draft:None
        def inspect(oid,draft,*,refresh,batch_ids):
            self.inspections.append((oid,refresh,list(batch_ids)))
            if refresh:
                self.assertFalse(db.in_transaction, 'Network guard ran inside write transaction')
                if self.on_check:self.on_check(app,oid,draft)
            status = self.check_status
            return {'object_id':oid,'draft_version':draft['version'],'status':status,
                    'can_auto_send':status=='clear','reasons':[] if status=='clear' else [{'code':status,'status':status,'message':'Synthetic check failure'}],
                    'crm':{'status':'已读取','sha256':'synthetic-hash','coverage':'synthetic complete workbook'},
                    'mail':{'refreshed':refresh,'state':'ready','last_success_at':'2026-11-06T00:00:00Z',
                            'history_limited':False,'thread_lookup_incomplete':False},
                    'bounce':{'status':'clear','coverage':{'complete':True}}}
        app.outreach_checks = SimpleNamespace(inspect=inspect)
        app.customer_batches = CustomerBatches(app)
        app.batch_sending = BatchSending(app)
        return app

    def approve_all(self):
        for oid in self.ids:
            self.batch = self.app.customer_batches.get(self.batch['id'])
            self.batch = self.app.customer_batches.review_item(self.batch['id'],oid,{
                'revision':self.batch['revision'],'review_state':'approved',
                'draft_version':self.app.gmail_drafts._saved(oid)['version']})

    def preflight(self, app=None, ids=None):
        app = app or self.app
        view = app.customer_batches.get(self.batch['id'])
        return app.batch_sending.preflight(view['id'],{'revision':view['revision'],'object_ids':ids or self.ids})

    def send(self, plan, app=None, confirmed=True):
        return (app or self.app).batch_sending.send(self.batch['id'],{'plan_id':plan['plan_id'],'confirmed':confirmed})

    def test_full_confirmed_send_records_receipts_once(self):
        plan = self.preflight()
        self.assertTrue(plan['can_confirm'])
        self.assertEqual(len(self.calls),0)
        result = self.send(plan)
        self.assertEqual(result['status'],'completed')
        self.assertEqual([i['status'] for i in result['items']],['sent','sent'])
        self.assertTrue(all(i['message_id'] and i['gmail_id'] for i in result['items']))
        self.assertEqual(len(self.calls),2)
        with self.assertRaises(WorkspaceConflict):self.send(plan)
        self.assertTrue(all(ids==self.ids for _,refresh,ids in self.inspections if refresh))
        stored = json.dumps(result)
        self.assertNotIn('Synthetic English',stored)
        self.assertNotIn('fixture',stored)

    def test_explicit_boolean_confirmation_required(self):
        plan = self.preflight()
        for confirmed in (False,None,1,'true'):
            with self.subTest(confirmed=confirmed):
                with self.assertRaises(ValueError):self.send(plan,confirmed=confirmed)
        self.assertEqual(self.calls,[])
        self.assertEqual(self.app.batch_sending.get(plan['plan_id'])['status'],'ready')

    def test_preflight_checks_unknown_blocked_and_missing_capability(self):
        for status in ('blocked','unknown'):
            self.check_status=status
            result=self.preflight()
            self.assertFalse(result['can_confirm'])
            self.assertIsNone(result['plan_id'])
        self.app.outreach_checks=None
        result=self.preflight()
        self.assertFalse(result['can_confirm'])
        self.assertEqual(self.calls,[])

    def test_pending_and_stale_review_never_generate_plan(self):
        self.app.customer_batches.review_item(self.batch['id'],self.ids[0],{'revision':self.batch['revision'],'review_state':'pending'})
        self.assertFalse(self.preflight()['can_confirm'])
        self.approve_all()
        self.profiles[self.ids[0]]['revision']='changed'
        self.assertFalse(self.preflight()['can_confirm'])

    def test_changed_draft_after_confirmation_never_sends_that_item(self):
        plan = self.preflight()
        draft=self.app.gmail_drafts._saved(self.ids[0])
        self.app.gmail_drafts.save(self.ids[0],draft['version'],{'to':'changed@example.test'})
        result=self.send(plan)
        self.assertEqual(result['items'][0]['status'],'not_sent')
        self.assertEqual(result['items'][1]['status'],'sent')
        self.assertEqual(len(self.calls),1)

    def test_changed_actual_attachment_blocks_even_without_version_change(self):
        plan=self.preflight()
        draft=self.app.gmail_drafts._saved(self.ids[0])
        (self.app.gmail_drafts.directory/draft['attachments'][0]['id']).write_bytes(b'tampered')
        result=self.send(plan)
        self.assertEqual(result['items'][0]['status'],'not_sent')
        self.assertEqual(len(self.calls),1)

    def test_review_changed_after_plan_prevents_all_sends(self):
        plan=self.preflight()
        view=self.app.customer_batches.get(self.batch['id'])
        self.app.customer_batches.review_item(view['id'],self.ids[0],{'revision':view['revision'],'review_state':'deferred'})
        result=self.send(plan)
        self.assertTrue(all(i['status']=='not_sent' for i in result['items']))
        self.assertEqual(self.calls,[])

    def test_check_changes_after_plan_prevents_send(self):
        plan=self.preflight()
        self.check_status='blocked'
        result=self.send(plan)
        self.assertTrue(all(i['status']=='not_sent' for i in result['items']))
        self.assertEqual(self.calls,[])

    def test_local_edit_during_network_check_is_caught_in_claim(self):
        plan=self.preflight()
        def edit(app,oid,draft):
            if oid==self.ids[0]:
                self.profiles[oid]['revision']='concurrent edit'
        self.on_check=edit
        result=self.send(plan)
        self.assertEqual(result['items'][0]['status'],'not_sent')
        self.assertEqual(len(self.calls),1)

    def test_edit_after_network_check_during_token_refresh_is_caught_by_callback(self):
        plan=self.preflight()
        def token(account):
            self.profiles[self.ids[0]]['revision']='last moment edit'
            return 'fixture'
        self.app.gmail_drafts.token_provider=token
        result=self.send(plan)
        self.assertEqual(result['items'][0]['status'],'not_sent')
        self.assertEqual(len(self.calls),1)

    def test_partial_success_then_unknown_stops_and_never_replays(self):
        third='customer:c'
        self.objects[third]={**self.objects[self.ids[0]],'id':third,'content':json.dumps({'email':'c@example.test','evidence':[{'url':'https://example.test','observed_at':'2026-11-06'}]})}
        self.profiles[third]=copy.deepcopy(self.profiles[self.ids[0]])
        d=self.app.gmail_drafts.get(third)
        d=self.app.gmail_drafts.save(third,d['version'],{'subject':'Third','body_en':'English','body_zh':'Chinese'})
        self.app.gmail_drafts.add_attachment(third,d['version'],filename='third.pdf',data=base64.b64encode(b'catalogue').decode())
        view=self.app.customer_batches.get(self.batch['id'])
        self.app.customer_batches.add_items(view['id'],{'revision':view['revision'],'object_ids':[third]})
        self.ids.append(third)
        self.approve_all()
        plan=self.preflight()
        def sender(token,payload):
            if len(self.calls)==2:raise TimeoutError()
            return {'id':'sent1'}
        self.sender=sender
        result=self.send(plan)
        self.assertEqual(result['status'],'stopped_unknown')
        self.assertEqual([i['status'] for i in result['items']],['sent','unknown','pending'])
        self.assertEqual(len(self.calls),2)
        reopened=self.make_app()
        with self.assertRaises(WorkspaceConflict):self.send(plan,app=reopened)
        self.assertEqual(len(self.calls),2)

    def test_explicit_provider_rejection_is_definitely_not_sent(self):
        plan=self.preflight()
        self.sender=lambda token,payload:(_ for _ in ()).throw(SendRejected('Synthetic rejection'))
        result=self.send(plan)
        self.assertEqual([i['status'] for i in result['items']],['not_sent','not_sent'])
        with self.assertRaises(WorkspaceConflict):self.send(plan)

    def test_competing_connections_cannot_claim_same_plan_twice(self):
        plan=self.preflight()
        other=self.make_app()
        started,finish=threading.Event(),threading.Event()
        def sender(token,payload):
            started.set()
            if not finish.wait(5):raise TimeoutError()
            return {'id':'sent1'}
        self.sender=sender
        results=[]
        thread=threading.Thread(target=lambda:results.append(self.send(plan)))
        thread.start()
        try:
            self.assertTrue(started.wait(5))
            with self.assertRaises(WorkspaceConflict):self.send(plan,app=other)
            reopened=self.make_app()
            active=reopened.batch_sending.get(plan['plan_id'])
            self.assertEqual(active['status'],'running')
            self.assertEqual(active['items'][0]['status'],'sending')
            self.assertEqual(reopened.gmail_drafts._saved(self.ids[0])['status'],'sending')
            with self.assertRaises(WorkspaceConflict):self.send(plan,app=reopened)
        finally:
            finish.set()
            thread.join(10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results[0]['status'],'completed')
        self.assertEqual(len(self.calls),2)

    def test_expired_plan_and_wrong_batch_rejected(self):
        plan=self.preflight()
        with patch('batch_sending._now',return_value=_now()+timedelta(minutes=10)):
            with self.assertRaises(WorkspaceConflict):self.send(plan)
        with self.assertRaises(ValueError):
            self.app.batch_sending.send('another-batch',{'plan_id':plan['plan_id'],'confirmed':True})
        self.assertEqual(self.calls,[])

    def test_confirmed_in_time_plan_continues_after_expiry_with_fresh_checks(self):
        plan=self.preflight()
        real_now=_now()
        clock={'now':real_now}
        def advance_during_check(app,oid,draft):
            clock['now']=real_now+timedelta(minutes=10)
        self.on_check=advance_during_check
        with patch('batch_sending._now',side_effect=lambda:clock['now']):
            result=self.send(plan)
        self.assertEqual(result['status'],'completed')
        self.assertEqual([v['status'] for v in result['items']],['sent','sent'])
        self.assertEqual(len(self.calls),2)

    def test_incomplete_fresh_check_cannot_generate_confirmation(self):
        original=self.app.outreach_checks.inspect
        for field in ('crm','mail','bounce'):
            def inspect(*args,**kwargs):
                check=original(*args,**kwargs)
                if kwargs['refresh']:check.pop(field)
                return check
            with self.subTest(field=field), patch.object(self.app.outreach_checks,'inspect',side_effect=inspect):
                self.assertFalse(self.preflight()['can_confirm'])
        self.assertEqual(self.calls,[])

    def test_duplicate_suppression_and_bounce_failure_all_block(self):
        original=self.app.outreach_checks.inspect
        for code in ('crm_suppressed','batch_duplicate','mail_bounce','bounce_coverage_unknown'):
            def inspect(*args,**kwargs):
                check=original(*args,**kwargs)
                if kwargs['refresh']:
                    check.update(status='blocked' if code!='bounce_coverage_unknown' else 'unknown',can_auto_send=False,
                                 reasons=[{'code':code,'message':'Synthetic guard','status':'blocked'}])
                return check
            with self.subTest(code=code),patch.object(self.app.outreach_checks,'inspect',side_effect=inspect):
                self.assertFalse(self.preflight()['can_confirm'])
        self.assertEqual(self.calls,[])

    def test_interrupted_running_plan_is_not_replayed_after_reopen(self):
        plan=self.preflight()
        with self.app.batch_sending._write():
            interrupted=self.app.batch_sending.get(plan['plan_id'])
            interrupted.update(status='running',owner='interrupted-worker')
            interrupted['items'][0]['status']='sending'
            self.app.batch_sending._put(interrupted)
        reopened=self.make_app()
        with self.assertRaises(WorkspaceConflict):self.send(plan,app=reopened)
        self.assertEqual(reopened.batch_sending.get(plan['plan_id'])['items'][1]['status'],'pending')
        self.assertEqual(self.calls,[])

    def same_recipient_plans(self):
        oid=self.ids[1]
        record=json.loads(self.objects[oid]['content'])
        record['email']='A@EXAMPLE.TEST'
        self.objects[oid]['content']=json.dumps(record)
        draft=self.app.gmail_drafts._saved(oid)
        self.app.gmail_drafts.save(oid,draft['version'],{'to':'A@EXAMPLE.TEST'})
        plans=[]
        for oid in self.ids:
            batch=self.app.customer_batches.create({'title':'Separate batch '+oid,'object_ids':[oid]})
            batch=self.app.customer_batches.review_item(batch['id'],oid,{
                'revision':batch['revision'],'review_state':'approved',
                'draft_version':self.app.gmail_drafts._saved(oid)['version']})
            plan=self.app.batch_sending.preflight(batch['id'],{'revision':batch['revision'],'object_ids':[oid]})
            self.assertTrue(plan['can_confirm'])
            plans.append(plan)
        return plans

    def send_separate(self,plan,app=None):
        return (app or self.app).batch_sending.send(plan['batch_id'],{'plan_id':plan['plan_id'],'confirmed':True})

    def test_distinct_batches_same_normalized_address_compete_atomically(self):
        first,second=self.same_recipient_plans()
        other=self.make_app()
        barrier=threading.Barrier(2)
        def token(account):
            barrier.wait(timeout=5)
            return 'fixture'
        self.app.gmail_drafts.token_provider=token
        other.gmail_drafts.token_provider=token
        results=[]
        threads=[threading.Thread(target=lambda:results.append(self.send_separate(first))),
                 threading.Thread(target=lambda:results.append(self.send_separate(second,other)))]
        for thread in threads:thread.start()
        for thread in threads:thread.join(10)
        self.assertFalse(any(t.is_alive() for t in threads))
        self.assertEqual(len(results),2)
        self.assertEqual(sorted(r['items'][0]['status'] for r in results),['not_sent','sent'])
        self.assertEqual(len(self.calls),1)
        claim=self.app.db.execute('SELECT account,recipient,status FROM batch_recipient_claims').fetchall()
        self.assertEqual(claim,[('sender@example.test','a@example.test','sent')])

    def test_unknown_claim_blocks_other_already_preflighted_batch(self):
        first,second=self.same_recipient_plans()
        self.sender=lambda token,payload:(_ for _ in ()).throw(TimeoutError())
        result=self.send_separate(first)
        self.assertEqual(result['items'][0]['status'],'unknown')
        reopened=self.make_app()
        result=self.send_separate(second,reopened)
        self.assertEqual(result['items'][0]['status'],'not_sent')
        self.assertEqual(len(self.calls),1)
        self.assertEqual(reopened.db.execute('SELECT status FROM batch_recipient_claims').fetchone()[0],'unknown')

    def test_crash_keeps_sending_claim_and_never_replays_other_batch(self):
        first,second=self.same_recipient_plans()
        self.sender=lambda token,payload:(_ for _ in ()).throw(SystemExit('Synthetic process interruption'))
        with self.assertRaises(SystemExit):self.send_separate(first)
        reopened=self.make_app()
        self.assertEqual(reopened.batch_sending.get(first['plan_id'])['status'],'running')
        self.assertEqual(reopened.db.execute('SELECT status FROM batch_recipient_claims').fetchone()[0],'sending')
        result=self.send_separate(second,reopened)
        self.assertEqual(result['items'][0]['status'],'not_sent')
        self.assertEqual(len(self.calls),1)

    def test_explicit_rejection_releases_only_its_own_recipient_claim(self):
        first,second=self.same_recipient_plans()
        self.sender=lambda token,payload:(_ for _ in ()).throw(SendRejected('Synthetic explicit rejection'))
        self.assertEqual(self.send_separate(first)['items'][0]['status'],'not_sent')
        self.assertEqual(self.app.db.execute('SELECT COUNT(*) FROM batch_recipient_claims').fetchone()[0],0)
        self.sender=lambda token,payload:{'id':'sent-after-rejection'}
        self.assertEqual(self.send_separate(second)['items'][0]['status'],'sent')
        self.assertEqual(len(self.calls),2)

    def test_success_blocks_new_batch_preflight_but_direct_followup_still_works(self):
        first,second=self.same_recipient_plans()
        self.send_separate(first)
        view=self.app.customer_batches.get(second['batch_id'])
        plan=self.app.batch_sending.preflight(view['id'],{'revision':view['revision'],'object_ids':[self.ids[1]]})
        self.assertFalse(plan['can_confirm'])
        self.assertIsNone(plan['plan_id'])
        # The shared key prevents repeated batch prospecting, not normal replies.
        oid=self.ids[0]
        draft=self.app.gmail_drafts.new(oid)
        draft=self.app.gmail_drafts.save(oid,draft['version'],{'subject':'Requested followup','body_en':'Synthetic followup'})
        self.assertEqual(self.app.gmail_drafts.send(oid,draft['version'])['status'],'sent')
        self.assertEqual(len(self.calls),2)

    def test_existing_plan_claim_is_backfilled_after_migration(self):
        first,second=self.same_recipient_plans()
        self.send_separate(first)
        self.app.db.execute('DELETE FROM batch_recipient_claims')
        self.app.db.commit()
        reopened=self.make_app()
        claim=reopened.db.execute('SELECT recipient,status FROM batch_recipient_claims').fetchone()
        self.assertEqual(claim,('a@example.test','sent'))
        self.assertEqual(self.send_separate(second,reopened)['items'][0]['status'],'not_sent')
        self.assertEqual(len(self.calls),1)


if __name__=='__main__':
    unittest.main()
