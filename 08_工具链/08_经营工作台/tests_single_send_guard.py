"""Real GmailDrafts/OutreachChecks, synthetic mailbox/CRM and no external sends."""
import base64
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from customer_batches import suppress_contact
from gmail_drafts import GmailDrafts, SendRejected
from outreach_checks import OutreachChecks
from single_send_guard import SingleSendGuard
from workspaces import WorkspaceConflict

ACCOUNT='sender@example.test';BUYER='buyer@example.test';OID='customer:1'


class SingleSendGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.path=self.root/'single.sqlite3'
        self.now=datetime(2026,11,6,tzinfo=timezone.utc)
        self.objects={OID:{'id':OID,'kind':'customer','content':json.dumps({'email':BUYER})}}
        self.profile={'revision':'profile1','source_hash':'source1','stale':False,'cleaned':{},'provenance':{}}
        self.messages=[];self.calls=[];self.on_context=None;self.on_token=None
        self.mail_status={'state':'ready','account_email':ACCOUNT,'last_success_at':'2026-11-06T00:00:00Z',
            'history_limited':False,'thread_lookup_incomplete':False,'shared_observation':{'state':'complete'}}
        self.crm={'status':'已读取','sha256':'crm1','coverage':'synthetic complete workbook',
            'match_status':'已匹配','stop_state':'未发现明确停止','matches':[]}
        self.bounce={'status':'clear','coverage':{'complete':True}}
        self.patch=patch('gmail_bounce_check.check_bounces',side_effect=lambda *a:self.bounce)
        self.patch.start();self.addCleanup(self.patch.stop)
        self.app=self.open_app();self.guard=self.app.single_send_guard
        draft=self.app.gmail_drafts.get(OID)
        draft=self.app.gmail_drafts.save(OID,draft['version'],{'subject':'Casual shoes','body_en':'Synthetic proposal','body_zh':'合成中文对照'})
        self.app.gmail_drafts.add_attachment(OID,draft['version'],filename='catalog.pdf',data=base64.b64encode(b'actual synthetic pdf').decode())

    def open_app(self):
        db=sqlite3.connect(self.path,timeout=10,check_same_thread=False);self.addCleanup(db.close)
        app=NS(db=db,lock=threading.RLock(),root=self.root,state=self.root/'state')
        app.business=NS(get_object=lambda oid:copy.deepcopy(self.objects[oid]),list_objects=lambda:list(copy.deepcopy(self.objects).values()))
        app.customer_workspace=NS(profile=lambda oid:copy.deepcopy(self.profile))
        def context(addresses,*,force=False):
            self.assertFalse(db.in_transaction)
            if self.on_context:self.on_context()
            return {'status':copy.deepcopy(self.mail_status),'messages':copy.deepcopy(self.messages)}
        app.gmail=NS(_account=ACCOUNT,_mailbox=NS(context=context),status=lambda:{'account_email':ACCOUNT},
            peek=lambda oid:{'status':copy.deepcopy(self.mail_status),'messages':copy.deepcopy(self.messages)})
        def token(account):
            self.assertFalse(db.in_transaction)
            if self.on_token:self.on_token()
            return 'synthetic-token'
        def sender(token,payload):
            self.assertFalse(db.in_transaction);self.calls.append(payload)
            if getattr(self,'send_error',None):raise self.send_error
            return {'id':'gmail-id','threadId':'20'}
        app.gmail_drafts=GmailDrafts(app,token_provider=token,sender=sender,grant_reader=lambda account:{})
        app.gmail_drafts._after_send=lambda draft:None
        app.outreach_checks=OutreachChecks(app,crm_reader=NS(check=lambda candidate:copy.deepcopy(self.crm)))
        app.single_send_guard=SingleSendGuard(app,clock=lambda:self.now)
        return app

    def draft(self):return self.app.gmail_drafts._saved(OID)
    def preflight(self,guard=None):return (guard or self.guard).preflight(OID,self.draft()['version'])
    def send(self,plan,guard=None):return (guard or self.guard).send(OID,self.draft()['version'],plan['plan_id'],True)

    def reply(self):
        inbound={'id':'101','thread_id':'32','direction':'inbound','sent_at':'2026-11-06T01:00:00Z',
            'from':BUYER,'to':ACCOUNT,'reply_to':BUYER,'subject':'Samples','rfc_message_id':'<inbound@example.test>',
            'body':'Please quote this style.','mail_kind':'conversation','customer_emails':[BUYER]}
        outbound={**inbound,'id':'100','direction':'outbound','sent_at':'2026-11-05T01:00:00Z','from':ACCOUNT,'to':BUYER,'body':'Old introduction'}
        self.messages=[outbound,inbound]
        d=self.draft();d.update(subject='Re: Samples',thread_subject='Samples',thread_id='32',reply_message_id='<inbound@example.test>')
        self.app.gmail_drafts._put(d)
        return inbound

    def test_preflight_is_read_only_and_confirmed_exact_plan_sends_once(self):
        plan=self.preflight();self.assertTrue(plan['can_confirm']);self.assertEqual(self.calls,[])
        self.assertEqual(plan['to'],BUYER);self.assertEqual(plan['attachments'][0]['size'],len(b'actual synthetic pdf'))
        result=self.send(plan);self.assertEqual(result['status'],'sent');self.assertEqual(len(self.calls),1)
        self.assertEqual(result['gmail_id'],'gmail-id');self.assertTrue(result['message_id'])
        with self.assertRaises(WorkspaceConflict):self.guard.send(OID,plan['version'],plan['plan_id'],True)
        self.assertNotIn('Synthetic proposal',json.dumps(result))
        self.assertNotIn('合成中文对照',json.dumps(result,ensure_ascii=False))

    def test_explicit_boolean_confirmation_plan_owner_version_and_expiry(self):
        plan=self.preflight()
        for flag in (False,1,'true',None):
            with self.assertRaises(ValueError):self.guard.send(OID,self.draft()['version'],plan['plan_id'],flag)
        with self.assertRaises(WorkspaceConflict):self.guard.send('customer:other',plan['version'],plan['plan_id'],True)
        with self.assertRaises(WorkspaceConflict):self.guard.send(OID,'wrong-version',plan['plan_id'],True)
        self.now+=timedelta(seconds=301)
        with self.assertRaises(WorkspaceConflict):self.send(plan)
        self.assertEqual(self.calls,[])

    def test_plain_prior_contact_cannot_be_exempted(self):
        self.messages=[{'id':'1','direction':'outbound','from':ACCOUNT,'to':BUYER,'body':'Old contact'}]
        plan=self.preflight();self.assertFalse(plan['can_confirm']);self.assertIsNone(plan['plan_id'])
        self.assertIn('previously_contacted',{r['code'] for r in plan['reasons']})

    def test_authentic_reply_ignores_only_prior_contact_and_allows_sent_batch_claim(self):
        self.reply()
        self.app.db.execute('INSERT INTO batch_recipient_claims VALUES (?,?,?,?,?,?,?,?)',(ACCOUNT,BUYER,'sent','old-batch',OID,'old-rfc','old-gmail','2026-11-05'));self.app.db.commit()
        plan=self.preflight();self.assertTrue(plan['can_confirm']);self.assertIsNotNone(plan['reply_proof'])
        result=self.send(plan);self.assertEqual(result['status'],'sent');self.assertEqual(len(self.calls),1)
        self.assertEqual(self.app.db.execute('SELECT plan_id FROM batch_recipient_claims').fetchone()[0],'old-batch')

    def test_reply_without_attachments_is_allowed_but_cold_intro_requires_attachment(self):
        d=self.draft();d['attachments']=[];self.app.gmail_drafts._put(d)
        self.assertFalse(self.preflight()['can_confirm'])
        self.reply();self.assertTrue(self.preflight()['can_confirm'])

    def test_wrong_thread_message_subject_or_recipient_cannot_get_reply_exemption(self):
        for key,value in [('thread_id','other'),('reply_message_id','<other@example.test>'),('subject','Different'),('thread_subject','Different')]:
            self.reply();d=self.draft();d[key]=value;self.app.gmail_drafts._put(d)
            with self.subTest(key=key):self.assertFalse(self.preflight()['can_confirm'])
        self.reply();self.messages[-1]['reply_to']='other@example.test'
        self.assertFalse(self.preflight()['can_confirm'])

    def test_old_inbound_already_answered_or_not_latest_is_not_reply_proof(self):
        for direction in ('inbound','outbound'):
            inbound=self.reply();self.messages.append({**inbound,'id':'103','sent_at':'2026-11-06T03:00:00Z',
                'direction':direction,'rfc_message_id':'<new@example.test>','from':BUYER if direction=='inbound' else ACCOUNT,
                'to':ACCOUNT if direction=='inbound' else BUYER})
            self.assertFalse(self.preflight()['can_confirm'])

    def test_automatic_mail_and_truncated_or_incomplete_context_cannot_exempt(self):
        for key,value in [('history_limited',True),('thread_lookup_incomplete',True),('shared_observation',{'state':'unknown'})]:
            self.reply();old=self.mail_status[key];self.mail_status[key]=value
            self.assertFalse(self.preflight()['can_confirm']);self.mail_status[key]=old
        self.reply();self.messages[-1]['mail_kind']='automatic';self.assertFalse(self.preflight()['can_confirm'])
        self.reply();self.messages[-1]['body_truncated']=True;self.assertFalse(self.preflight()['can_confirm'])

    def test_reply_cannot_waive_optout_rejection_or_hard_bounce(self):
        for text in ('Please unsubscribe us.','We are not interested.','Delivery failed: user unknown'):
            self.reply();self.messages[-1]['body']=text
            self.assertFalse(self.preflight()['can_confirm'])
        self.reply();self.bounce={'status':'blocked','coverage':{'complete':True}}
        self.assertFalse(self.preflight()['can_confirm'])

    def test_reply_cannot_waive_duplicates_or_shared_dnc(self):
        self.reply();self.objects['customer:2']={'id':'customer:2','kind':'customer','content':json.dumps({'email':BUYER})}
        self.assertFalse(self.preflight()['can_confirm']);del self.objects['customer:2']
        with self.guard._write():suppress_contact(self.app,OID,'synthetic-dnc')
        self.assertFalse(self.preflight()['can_confirm'])

    def test_crm_unknown_requires_existing_scoped_review_and_cannot_waive_missing_workbook(self):
        self.crm.update(match_status='未匹配',stop_state='未知')
        self.assertFalse(self.preflight()['can_confirm'])
        binding=self.app.outreach_checks._manual_binding(OID,self.draft(),self.crm)
        saved={'binding':binding,'recorded_at':'2026-11-06','review_id':'existing-scoped-review','evidence':{'synthetic':'existing manual review'}}
        self.app.db.execute('INSERT INTO outreach_crm_reviews VALUES (?,?)',(OID,json.dumps(saved)));self.app.db.commit()
        self.assertTrue(self.preflight()['can_confirm'])
        self.crm['sha256']='new-crm';self.assertFalse(self.preflight()['can_confirm'])
        self.crm.update(status='读取失败',sha256=None);self.assertFalse(self.preflight()['can_confirm'])

    def test_draft_or_actual_attachment_change_after_plan_blocks_sender(self):
        for field,value in [('body_en','new english'),('body_zh','新译文'),('subject','new subject'),('to','other@example.test')]:
            plan=self.preflight();self.assertTrue(plan['can_confirm'])
            d=self.draft();d[field]=value;self.app.gmail_drafts._put(d)
            self.assertEqual(self.send(plan)['status'],'not_sent')
            d=self.draft();d[field]={'body_en':'Synthetic proposal','body_zh':'合成中文对照','subject':'Casual shoes','to':BUYER}[field];self.app.gmail_drafts._put(d)
        plan=self.preflight();a=self.draft()['attachments'][0]
        (self.app.gmail_drafts.directory/a['id']).write_bytes(b'tampered')
        self.assertEqual(self.send(plan)['status'],'not_sent');self.assertEqual(self.calls,[])

    def test_changes_during_credentials_are_caught_in_final_same_transaction(self):
        plan=self.preflight();self.on_token=lambda:self.profile.update(revision='changed')
        self.assertEqual(self.send(plan)['status'],'not_sent');self.assertEqual(self.calls,[])
        self.assertEqual(self.draft()['status'],'draft')

    def test_two_connections_only_one_claims_same_plan(self):
        plan=self.preflight();second=self.open_app().single_send_guard
        gate=threading.Barrier(3);results=[];errors=[]
        def run(guard):
            try:gate.wait();results.append(guard.send(OID,plan['version'],plan['plan_id'],True))
            except Exception as exc:errors.append(exc)
        threads=[threading.Thread(target=run,args=(g,)) for g in (self.guard,second)]
        for t in threads:t.start()
        gate.wait()
        for t in threads:t.join(10)
        self.assertFalse(any(t.is_alive() for t in threads));self.assertEqual(len(self.calls),1)
        self.assertEqual(len(results),1);self.assertEqual(len(errors),1);self.assertIsInstance(errors[0],WorkspaceConflict)

    def test_unknown_outcome_survives_restart_and_never_retries(self):
        plan=self.preflight();self.send_error=TimeoutError('synthetic unknown')
        result=self.send(plan);self.assertEqual(result['status'],'unknown');self.assertEqual(len(self.calls),1)
        restarted=self.open_app().single_send_guard
        self.assertEqual(restarted.get(plan['plan_id'])['status'],'unknown')
        with self.assertRaises(WorkspaceConflict):restarted.send(OID,plan['version'],plan['plan_id'],True)
        self.assertEqual(len(self.calls),1)

    def test_explicit_rejection_records_not_sent_and_releases_only_own_claim(self):
        plan=self.preflight();self.send_error=SendRejected('synthetic rejected')
        result=self.send(plan);self.assertEqual(result['status'],'not_sent');self.assertEqual(self.draft()['status'],'draft')
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM batch_recipient_claims').fetchone()[0],0)
        self.assertTrue(self.preflight()['can_confirm'])

    def test_receipt_postprocess_error_does_not_misreport_sent_as_unsent(self):
        plan=self.preflight()
        def fail(draft):raise OSError('synthetic after receipt')
        self.app.gmail_drafts._after_send=fail
        self.assertEqual(self.send(plan)['status'],'sent');self.assertEqual(len(self.calls),1)

    def test_same_inbound_reply_is_not_claimable_again_but_later_inbound_is(self):
        self.reply();plan=self.preflight();self.assertEqual(self.send(plan)['status'],'sent')
        self.app.gmail_drafts.new(OID)
        d=self.draft();self.app.gmail_drafts.save(OID,d['version'],{'body_en':'Second reply','body_zh':'第二次回复'})
        self.assertFalse(self.preflight()['can_confirm'])
        self.messages[-1].update(id='102',rfc_message_id='<later@example.test>',sent_at='2026-11-06T04:00:00Z')
        d=self.draft();d['reply_message_id']='<later@example.test>';self.app.gmail_drafts._put(d)
        self.assertTrue(self.preflight()['can_confirm'])

    def test_fresh_stop_or_bounce_after_confirmation_never_reaches_sender(self):
        self.reply();plan=self.preflight();self.messages[-1]['body']='Please unsubscribe.'
        self.assertEqual(self.send(plan)['status'],'not_sent');self.assertEqual(self.calls,[])
        self.messages[-1]['body']='Please quote.';plan=self.preflight()
        self.bounce={'status':'blocked','coverage':{'complete':True}}
        self.assertEqual(self.send(plan)['status'],'not_sent');self.assertEqual(self.calls,[])

    def test_live_or_unknown_batch_claim_cannot_be_bypassed_as_reply(self):
        self.reply()
        for state in ('sending','unknown'):
            self.app.db.execute('INSERT OR REPLACE INTO batch_recipient_claims VALUES (?,?,?,?,?,?,?,?)',
                (ACCOUNT,BUYER,state,'old',OID,'old-rfc',None,'2026-11-06'));self.app.db.commit()
            self.assertFalse(self.preflight()['can_confirm'])
        self.assertEqual(self.calls,[])

    def test_rolled_back_callback_claim_is_not_misreported_as_unknown_send(self):
        plan=self.preflight();original=self.guard._put
        def fail_at_claim(value):
            if value['status']=='sending':raise OSError('synthetic local claim failure')
            return original(value)
        self.guard._put=fail_at_claim
        result=self.send(plan)
        self.assertEqual(result['status'],'not_sent');self.assertEqual(self.draft()['status'],'draft')
        self.assertEqual(self.calls,[])
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM batch_recipient_claims').fetchone()[0],0)

    def test_two_different_plans_for_same_draft_have_one_sender(self):
        first=self.preflight();second_plan=self.preflight();second_guard=self.open_app().single_send_guard
        gate=threading.Barrier(3);results=[];errors=[]
        def run(guard,plan):
            try:gate.wait();results.append(guard.send(OID,plan['version'],plan['plan_id'],True))
            except Exception as exc:errors.append(exc)
        threads=[threading.Thread(target=run,args=(self.guard,first)),threading.Thread(target=run,args=(second_guard,second_plan))]
        for t in threads:t.start()
        gate.wait()
        for t in threads:t.join(10)
        self.assertFalse(any(t.is_alive() for t in threads));self.assertEqual(errors,[])
        self.assertEqual(len(self.calls),1);self.assertEqual(sorted(r['status'] for r in results),['not_sent','sent'])

    def test_real_shared_observation_and_customer_revision_do_not_expire_unchanged_reply(self):
        from customer_workspace import CustomerWorkspace
        from gmail_observations import GmailObservations
        from gmail_oauth import GmailOAuthMailbox
        from tests_gmail_oauth import email
        self.reply()
        raw=email(mid='65',body='Please quote the selected style.')
        raw['payload']['headers']=[{'name':'From','value':BUYER},{'name':'To','value':ACCOUNT},
            {'name':'Subject','value':'Samples'},{'name':'Message-ID','value':'<inbound@example.test>'}]
        def request(url,**kwargs):
            self.assertFalse(self.app.db.in_transaction)
            if url.endswith('/profile'):return {'emailAddress':ACCOUNT,'historyId':'1000'}
            if '/messages?' in url:return {'messages':[{'id':'65'}]}
            if '/messages/' in url:return copy.deepcopy(raw)
            raise AssertionError(url)
        mailbox=GmailOAuthMailbox(ACCOUNT,request=request,reader=lambda account:None)
        mailbox._access_token=lambda:'synthetic-token'
        mailbox.observation_store=GmailObservations(self.app)
        self.app.gmail._mailbox=mailbox
        self.app.customer_workspace=CustomerWorkspace(self.app)
        self.crm['matches']=[{'latest_touch':'2026-11-01T00:00:00Z'}]
        plan=self.preflight();self.assertTrue(plan['can_confirm'],plan['reasons'])
        revision=self.app.customer_workspace.profile(OID)['revision']
        self.assertEqual(self.app.customer_workspace.profile(OID)['revision'],revision)
        result=self.send(plan)
        self.assertEqual(result['status'],'sent',result.get('reason'));self.assertEqual(len(self.calls),1)


if __name__=='__main__':unittest.main()
