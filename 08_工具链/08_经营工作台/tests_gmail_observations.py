"""Synthetic watermarks only. No Gmail connection, dispatch or message storage."""
import copy
import json
import multiprocessing
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest

from customer_workspace import CustomerWorkspace
from gmail_observations import GmailObservations, revision_observations
from gmail_oauth import GmailOAuthMailbox
from gmail_mailbox import GmailMailbox
from tests_gmail_oauth import ACCOUNT, BUYER, email


OID = 'customer:1'


def open_app(path, root):
    obj = {'id': OID, 'kind': 'customer', 'content': json.dumps({'email': BUYER})}
    return SimpleNamespace(root=Path(root), state=Path(root),
        db=sqlite3.connect(path, timeout=10, check_same_thread=False), lock=threading.RLock(),
        business=SimpleNamespace(get_object=lambda oid: copy.deepcopy(obj)),
        gmail=SimpleNamespace(_account=ACCOUNT))


def publish_in_process(path, root, hid, barrier, results):
    app = open_app(path, root)
    try:
        store = GmailObservations(app)
        ticket = store.begin(ACCOUNT, [BUYER])
        barrier.wait(10)
        result = store.finish(ticket, before=hid, after=hid, complete=True, messages=[])
        results.put(result)
    finally:
        app.db.close()


class GmailObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.path = self.root / 'shared.sqlite3'
        self.app = open_app(self.path, self.root); self.addCleanup(self.app.db.close)
        self.store = GmailObservations(self.app)

    def publish(self, hid='100', **kwargs):
        ticket = self.store.begin(ACCOUNT, [BUYER])
        return self.store.finish(ticket, before=hid, after=hid, complete=True,
                                 messages=[{'id':'1','body':'private synthetic body'}], **kwargs)

    def revision(self, app=None):
        return revision_observations(app or self.app, ACCOUNT, [BUYER])

    def test_success_is_stable_across_poll_and_restart_without_mail_content(self):
        self.publish(); before = self.revision(); self.publish()
        self.assertEqual(self.revision(), before)
        app2 = open_app(self.path, self.root); self.addCleanup(app2.db.close)
        self.assertEqual(self.revision(app2), before)
        persisted = '\n'.join(str(row) for row in self.app.db.execute('SELECT * FROM gmail_observations'))
        self.assertNotIn('private synthetic body', persisted); self.assertNotIn(BUYER, persisted)
        self.assertEqual(before[0]['state'], 'complete'); self.assertEqual(before[0]['history_id'], '100')

    def test_older_history_never_replaces_newer_even_with_a_newer_local_attempt(self):
        self.publish('999999999999999999999999999999999999')
        rejected = self.publish('9')
        self.assertFalse(rejected['accepted']); self.assertEqual(rejected['reason'], 'regressed_history_id')
        row = self.revision()[0]
        self.assertEqual(row['history_id'], '999999999999999999999999999999999999')
        self.assertEqual(row['state'], 'unknown')

    def test_late_old_success_or_failure_cannot_overwrite_newer_attempt(self):
        for old_fails in (True, False):
            with self.subTest(old_fails=old_fails):
                old = self.store.begin(ACCOUNT, [BUYER]); newer = self.store.begin(ACCOUNT, [BUYER])
                self.store.finish(newer, before='200', after='200', complete=True, messages=[])
                before = self.revision()
                result = self.store.finish(old, before='100', after='100', complete=not old_fails, messages=[])
                self.assertEqual(result['reason'], 'superseded_attempt'); self.assertEqual(self.revision(), before)

    def test_failure_and_incomplete_do_not_advance_success(self):
        self.publish('100')
        for before, after, complete in [('101','101',False), ('101','102',True), (None,'103',True), ('local-time','local-time',True)]:
            ticket = self.store.begin(ACCOUNT,[BUYER])
            self.store.finish(ticket,before=before,after=after,complete=complete,messages=[])
            row = self.revision()[0]
            self.assertEqual(row['state'],'unknown'); self.assertEqual(row['history_id'],'100')

    def test_same_watermark_conflicting_content_remains_unknown(self):
        self.publish('100'); ticket=self.store.begin(ACCOUNT,[BUYER])
        result=self.store.finish(ticket,before='100',after='100',complete=True,messages=[])
        self.assertEqual(result['reason'],'conflicting_same_watermark')
        self.assertEqual(self.revision()[0]['state'],'unknown')

    def test_pending_attempt_stays_unknown_after_restart(self):
        self.publish(); self.store.begin(ACCOUNT,[BUYER])
        app2=open_app(self.path,self.root); self.addCleanup(app2.db.close)
        GmailObservations(app2)
        self.assertEqual(self.revision(app2)[0]['state'],'unknown')
        self.assertEqual(self.revision(app2)[0]['history_id'],'100')

    def test_spawned_writers_publish_only_latest_claim_and_parent_reads_same_revision(self):
        ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(2);results=ctx.Queue()
        self.addCleanup(results.join_thread);self.addCleanup(results.close)
        processes=[ctx.Process(target=publish_in_process,args=(str(self.path),str(self.root),hid,barrier,results)) for hid in ('100','200')]
        for process in processes:process.start()
        try:
            outcomes=[results.get(timeout=20) for _ in processes]
            for process in processes:process.join(20)
            self.assertTrue(all(process.exitcode==0 for process in processes))
            self.assertEqual(sum(bool(r['accepted']) for r in outcomes),1)
            self.assertEqual(self.revision()[0]['state'],'complete')
        finally:
            for process in processes:
                if process.is_alive():process.terminate();process.join(5)

    def test_customer_revision_reads_shared_observation_without_local_cache(self):
        workspace=CustomerWorkspace(self.app)
        before=workspace.profile(OID)['revision']; self.publish('100')
        changed=workspace.profile(OID)['revision'];self.assertNotEqual(before,changed)
        self.publish('100');self.assertEqual(workspace.profile(OID)['revision'],changed)
        app2=open_app(self.path,self.root);self.addCleanup(app2.db.close)
        self.assertEqual(CustomerWorkspace(app2).profile(OID)['revision'],changed)
        # A different mailbox account/scope cannot masquerade as this customer's observation.
        ticket=self.store.begin('another@example.test',['other@example.test'])
        self.store.finish(ticket,before='900',after='900',complete=True,messages=[])
        self.assertEqual(workspace.profile(OID)['revision'],changed)

    def test_chinese_adjacent_evidence_binds_profile_only_email_to_shared_revision(self):
        # The real CustomerWorkspace save/read path is used; neither the
        # original object nor linked sent addresses supplies this contact.
        obj={'id':OID,'kind':'customer','content':json.dumps({'company':'Synthetic buyer'})}
        self.app.business.get_object=lambda oid:copy.deepcopy(obj)
        workspace=CustomerWorkspace(self.app)
        initial=workspace.profile(OID)
        workspace.save_profile(OID,{'revision':initial['revision'],'source_hash':initial['source_hash'],
            'cleaned':{'email':BUYER},'evidence':[{'text':'官网公开联系邮箱'+BUYER+'用于业务转交。',
                'url':'https://example.test/contact','observed_at':'2026-11-06'}]})
        before=workspace.profile(OID)['revision'];flow_before=workspace.workflow(OID)['revision']
        self.assertNotIn('email',json.loads(obj['content']))
        self.publish('100')
        changed=workspace.profile(OID)['revision'];flow_changed=workspace.workflow(OID)['revision']
        self.assertNotEqual(before,changed);self.assertNotEqual(flow_before,flow_changed)
        self.assertEqual(workspace._gmail_revision_inputs(OID)['mailbox_observations'][0]['history_id'],'100')
        self.publish('100')
        self.assertEqual(workspace.profile(OID)['revision'],changed)
        app2=open_app(self.path,self.root);self.addCleanup(app2.db.close)
        app2.business.get_object=lambda oid:copy.deepcopy(obj)
        restarted=CustomerWorkspace(app2)
        self.assertEqual(restarted.profile(OID)['revision'],changed)
        self.assertEqual(restarted.workflow(OID)['revision'],flow_changed)

    def test_profile_email_substrings_do_not_bind_shared_revision(self):
        obj={'id':OID,'kind':'customer','content':'{}'}
        self.app.business.get_object=lambda oid:copy.deepcopy(obj)
        workspace=CustomerWorkspace(self.app)
        for text in ('different'+BUYER,BUYER+'.other.test'):
            current=workspace.profile(OID)
            workspace.save_profile(OID,{'revision':current['revision'],'source_hash':current['source_hash'],
                'cleaned':{'email':BUYER},'evidence':[{'text':text,
                    'url':'https://example.test/contact','observed_at':'2026-11-06'}]})
            before=workspace.profile(OID)['revision']
            self.publish('100')
            self.assertEqual(workspace.profile(OID)['revision'],before)
            self.assertNotIn('mailbox_observations',workspace._gmail_revision_inputs(OID))

    def mailbox(self, *, history=('100','100'), pagination=False, query_fails=False,
                thread_fails=False, body='Please share samples', profile_fails=False, body_incomplete=False):
        watermarks=iter(history); calls=[]
        raw=email(body=body,direction='outbound' if thread_fails else 'inbound')
        if body_incomplete:raw['payload']['parts'][0]['body']={'attachmentId':'unfetched-text-part'}
        def request(url, **kwargs):
            calls.append(url)
            if url.endswith('/profile'):
                if profile_fails:raise OSError('fixture profile failure')
                return {'emailAddress':ACCOUNT,'historyId':next(watermarks)}
            if '/messages?' in url:
                if query_fails:raise OSError('fixture query failure')
                return {'messages':[{'id':'10'}],**({'nextPageToken':'next'} if pagination else {})}
            if '/threads/' in url:
                if thread_fails:raise OSError('fixture thread failure')
                return {'messages':[raw]}
            if '/messages/' in url:return raw
            raise AssertionError(url)
        box=GmailOAuthMailbox(ACCOUNT,request=request,reader=lambda account:None)
        box._access_token=lambda:'synthetic-token';box.observation_store=self.store
        return box,calls

    def test_oauth_brackets_success_and_cached_reads_do_not_republish(self):
        box,calls=self.mailbox();result=box.context([BUYER],force=True)
        self.assertEqual(result['status']['shared_observation']['state'],'complete')
        self.assertTrue(calls[0].endswith('/profile'));self.assertTrue(calls[-1].endswith('/profile'))
        attempts=self.app.db.execute('SELECT attempt FROM gmail_observations').fetchone()[0]
        cached=box.context([BUYER]);self.assertEqual(cached,result)
        self.assertEqual(self.app.db.execute('SELECT attempt FROM gmail_observations').fetchone()[0],attempts)

    def test_oauth_changed_watermark_query_failure_pagination_thread_or_body_incomplete_is_unknown(self):
        scenarios=[{'history':('100','101')},{'query_fails':True},{'pagination':True},
                   {'thread_fails':True},{'body_incomplete':True},{'profile_fails':True}]
        for options in scenarios:
            with self.subTest(options=list(options)):
                box,_=self.mailbox(**options);result=box.context([BUYER],force=True)
                self.assertEqual(result['status']['shared_observation']['state'],'unknown')
                self.assertIsNone(self.revision()[0]['history_id'])

    def test_imap_without_comparable_watermark_is_unknown_not_local_time(self):
        box=GmailMailbox(ACCOUNT,password_reader=lambda account:'fixture')
        box.observation_store=self.store;box._fetch=lambda customers,password:([],0)
        result=box.context([BUYER],force=True)
        self.assertEqual(result['status']['state'],'ready')
        self.assertEqual(result['status']['shared_observation']['reason'],'imap_watermark_unavailable')
        self.assertEqual(self.revision()[0]['state'],'unknown');self.assertIsNone(self.revision()[0]['history_id'])

    def test_batch_approval_stays_fresh_on_same_observation_but_new_mail_requires_review(self):
        from tests_batch_sending import BatchSendingTests
        fixture=BatchSendingTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        app=fixture.app;app.gmail._account='sender@example.test'
        app.customer_workspace=CustomerWorkspace(app)
        store=GmailObservations(app);recipient='a@example.test'
        def observe(hid,messages):
            ticket=store.begin(app.gmail._account,[recipient])
            store.finish(ticket,before=hid,after=hid,complete=True,messages=messages)
        observe('100',[]);fixture.approve_all()
        view=app.customer_batches.get(fixture.batch['id'])
        approved=next(i for i in view['items'] if i['object_id']=='customer:a')
        self.assertFalse(approved['review_stale'])
        observe('100',[])
        view=app.customer_batches.get(fixture.batch['id'])
        self.assertFalse(next(i for i in view['items'] if i['object_id']=='customer:a')['review_stale'])
        plan=app.batch_sending.preflight(view['id'],{'revision':view['revision'],'object_ids':['customer:a']})
        self.assertTrue(plan['can_confirm'])
        observe('200',[{'id':'new-inbound','direction':'inbound','body':'Synthetic new request'}])
        view=app.customer_batches.get(fixture.batch['id'])
        self.assertTrue(next(i for i in view['items'] if i['object_id']=='customer:a')['review_stale'])
        blocked=app.batch_sending.preflight(view['id'],{'revision':view['revision'],'object_ids':['customer:a']})
        self.assertFalse(blocked['can_confirm']);self.assertIsNone(blocked['plan_id'])
        self.assertEqual(fixture.calls,[])


if __name__=='__main__':
    unittest.main()
