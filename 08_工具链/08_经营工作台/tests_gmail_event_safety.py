"""Gmail event claims must survive independent connections and uncertain callbacks."""
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from gmail_sync import GmailDispatchDeferred, GmailService
from server import Workbench
from tests_gmail_sync import ACCOUNT, Business, Mailbox, message


class GmailEventSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.connections=[]
        self.now=1000
        self.flow={'state':'waiting_customer','bucket':'active','waiting_since':'2026-11-01T01:00:00Z'}
        self.context={'reply_pending':True,'messages':[{'id':'message-1','direction':'inbound','sent_at':'2026-11-01T02:00:00Z'}]}

    def tearDown(self):
        for db in self.connections:db.close()

    def service(self,callback):
        db=sqlite3.connect(self.root/'runs.sqlite3',timeout=10,check_same_thread=False)
        self.connections.append(db)
        app=SimpleNamespace(state=self.root,db=db,lock=threading.RLock(),
                            customer_workspace=SimpleNamespace(_saved_profile=lambda oid:{'workflow':self.flow}))
        service=GmailService(app,on_new_reply=callback,clock=lambda:self.now)
        service._cache['customer:1']={}
        return service

    def row(self,db):
        return db.execute('SELECT dispatch_state,job_id,last_error FROM gmail_reply_events WHERE object_id=? AND message_id=?',('customer:1','message-1')).fetchone()

    def test_independent_connections_claim_one_event_once(self):
        gate=threading.Event();entered=threading.Event();calls=[];failures=[]
        def callback(*args):
            calls.append(args[1]['id']);entered.set()
            if not gate.wait(5):raise AssertionError('callback not released')
            return {'id':'job-1'}
        first=self.service(callback);second=self.service(callback)
        barrier=threading.Barrier(3)
        def run(service):
            try:barrier.wait();service._dispatch('customer:1',self.context)
            except Exception as exc:failures.append(exc)
        threads=[threading.Thread(target=run,args=(service,)) for service in (first,second)]
        try:
            for thread in threads:thread.start()
            barrier.wait();self.assertTrue(entered.wait(5))
        finally:
            gate.set()
            for thread in threads:thread.join(10)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(failures,[])
        self.assertEqual(calls,['message-1'])
        self.assertEqual(self.row(first.app.db),('dispatched','job-1',None))

    def test_reply_claim_is_committed_before_publishing_customer_cache(self):
        calls=[];errors=[];claimed=threading.Event();release=threading.Event()
        service=self.service(lambda *args:(calls.append(args[1]['id']) or {'id':'job-1'}))
        service.app.business=Business();service._account=ACCOUNT
        mailbox=Mailbox();mailbox.messages=[message('message-1')];service._mailbox=mailbox
        service._connected_at='2026-11-01T00:00:00Z'
        original=service._claim_dispatch
        def blocked(*args):
            result=original(*args);claimed.set()
            if not release.wait(5):raise AssertionError('claim gate timed out')
            return result
        service._claim_dispatch=blocked
        observer=sqlite3.connect(self.root/'runs.sqlite3',timeout=10,check_same_thread=False)
        self.connections.append(observer)
        def run():
            try:service.customer('customer:1')
            except Exception as exc:errors.append(exc)
        thread=threading.Thread(target=run);thread.start()
        try:
            self.assertTrue(claimed.wait(5))
            self.assertEqual(self.row(observer),('dispatching',None,None))
            with service.lock:self.assertEqual(service._cache['customer:1'],{})
            self.assertEqual(calls,[])
        finally:
            release.set();thread.join(10)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
        self.assertEqual(calls,['message-1'])
        self.assertTrue(service.peek('customer:1')['reply_pending'])
        self.assertEqual(self.row(observer),('dispatched','job-1',None))

    def test_acknowledgement_committed_between_read_and_claim_blocks_dispatch(self):
        calls=[];errors=[];before_claim=threading.Event();release=threading.Event()
        service=self.service(lambda *args:(calls.append(args[1]['id']) or {'id':'job-1'}))
        service.app.business=Business();service._account=ACCOUNT
        mailbox=Mailbox();mailbox.messages=[message('message-1')];service._mailbox=mailbox
        service._connected_at='2026-11-01T00:00:00Z'
        original=service._claim_dispatch
        def blocked(*args):
            before_claim.set()
            if not release.wait(5):raise AssertionError('ack gate timed out')
            return original(*args)
        service._claim_dispatch=blocked
        observer=sqlite3.connect(self.root/'runs.sqlite3',timeout=10,check_same_thread=False)
        self.connections.append(observer)
        def run():
            try:service.customer('customer:1')
            except Exception as exc:errors.append(exc)
        thread=threading.Thread(target=run);thread.start()
        try:
            self.assertTrue(before_claim.wait(5))
            observer.execute('INSERT OR REPLACE INTO gmail_acknowledged VALUES (?,?)',('customer:1','message-1'))
            observer.commit()
        finally:
            release.set();thread.join(10)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[]);self.assertEqual(calls,[])
        self.assertIsNone(self.row(observer))
        self.assertFalse(service.peek('customer:1')['reply_pending'])

    def test_acknowledgement_blocks_a_due_deferred_claim(self):
        calls=[];service=self.service(lambda *args:(calls.append(args) or {'id':'must-not-start'}))
        service.app.db.execute('INSERT INTO gmail_reply_events (object_id,message_id,dispatch_state,updated_at) VALUES (?,?,?,?)',('customer:1','message-1','deferred','1970-01-01T00:00:01+00:00'))
        service.app.db.execute('INSERT INTO gmail_acknowledged VALUES (?,?)',('customer:1','message-1'))
        service.app.db.commit()
        service._dispatch('customer:1',self.context)
        self.assertEqual(calls,[])
        self.assertEqual(self.row(service.app.db)[0],'deferred')

    def test_job_created_before_callback_error_stays_unknown_after_restart(self):
        jobs=[];calls=[]
        def callback(*args):
            calls.append(args[1]['id']);jobs.append('created-job')
            raise RuntimeError('failure after creation')
        first=self.service(callback)
        first._dispatch('customer:1',self.context)
        self.assertEqual(self.row(first.app.db),('outcome_unknown',None,'RuntimeError'))
        self.assertIn('未确认',first._cache['customer:1']['callback_error'])
        restarted=self.service(callback)
        restarted._dispatch('customer:1',self.context)
        self.assertEqual(calls,['message-1'])
        self.assertEqual(jobs,['created-job'])
        self.assertIn('未确认',restarted._cache['customer:1']['callback_error'])

    def test_legacy_failed_or_dispatching_events_never_automatically_replay(self):
        calls=[];service=self.service(lambda *args:calls.append(args))
        for state in ('failed','dispatching','dispatched_unlinked','dispatched'):
            service.app.db.execute('DELETE FROM gmail_reply_events')
            service.app.db.execute('INSERT INTO gmail_reply_events(object_id,message_id,dispatch_state) VALUES (?,?,?)',('customer:1','message-1',state))
            service.app.db.commit()
            service._dispatch('customer:1',self.context)
            self.assertEqual(self.row(service.app.db)[0],state)
            self.assertIn('未确认',service._cache['customer:1']['callback_error'])
        self.assertEqual(calls,[])

    def test_unlinked_callback_is_reported_without_retry(self):
        calls=[];service=self.service(lambda *args:calls.append(args))
        service._dispatch('customer:1',self.context)
        service._dispatch('customer:1',self.context)
        self.assertEqual(len(calls),1)
        self.assertEqual(self.row(service.app.db),('dispatched_unlinked',None,'回调未返回可关联的任务ID'))
        self.assertIn('未确认',service._cache['customer:1']['callback_error'])

    def test_explicit_precreation_deferral_retries_only_when_due_even_after_restart(self):
        calls=[];busy=[True]
        def callback(*args):
            calls.append(args[1]['id'])
            if busy[0]:raise GmailDispatchDeferred('before creation')
            return {'id':'new-job'}
        service=self.service(callback)
        service._dispatch('customer:1',self.context)
        self.assertEqual(self.row(service.app.db)[0],'deferred')
        self.assertIn('稍后再次检查',service._cache['customer:1']['callback_error'])
        restarted=self.service(callback)
        self.now+=119;restarted._dispatch('customer:1',self.context)
        self.assertEqual(len(calls),1)
        busy[0]=False;self.now+=2;restarted._dispatch('customer:1',self.context)
        self.assertEqual(len(calls),2)
        self.assertEqual(self.row(restarted.app.db),('dispatched','new-job',None))
        self.assertNotIn('callback_error',restarted._cache['customer:1'])

    def test_server_defers_existing_customer_job_before_creation(self):
        created=[];jobs=[{'object_id':'customer:1','status':'running'}]
        service=self.service(None)
        service.app.agent_jobs=SimpleNamespace(list_jobs=lambda:jobs,start=lambda *args,**kwargs:(created.append(args) or {'id':'job-after-wait'}))
        service.on_new_reply=lambda oid,message,context:Workbench._gmail_reply(service.app,oid,message,context)
        service._dispatch('customer:1',self.context)
        self.assertEqual(self.row(service.app.db)[0],'deferred')
        self.assertEqual(created,[])
        jobs.clear();self.now+=121;service._dispatch('customer:1',self.context)
        self.assertEqual(len(created),1)
        self.assertEqual(self.row(service.app.db),('dispatched','job-after-wait',None))

    def test_newer_reply_takes_precedence_over_older_deferred_event(self):
        calls=[];busy=[True]
        def callback(oid,message,context):
            calls.append(message['id'])
            if busy[0]:raise GmailDispatchDeferred('before creation')
            return {'id':'job-for-latest'}
        service=self.service(callback)
        service._dispatch('customer:1',self.context)
        busy[0]=False;self.now+=121
        newer={'id':'message-2','direction':'inbound','sent_at':'2026-11-01T03:00:00Z'}
        context={'reply_pending':True,'messages':[self.context['messages'][0],newer]}
        service._dispatch('customer:1',context)
        service._dispatch('customer:1',context)
        self.assertEqual(calls,['message-1','message-2'])
        self.assertEqual(self.row(service.app.db)[0],'deferred')
        self.assertEqual(service.app.db.execute('SELECT dispatch_state,job_id FROM gmail_reply_events WHERE message_id=?',('message-2',)).fetchone(),('dispatched','job-for-latest'))

    def test_concurrent_legacy_schema_migration_preserves_rows(self):
        db=sqlite3.connect(self.root/'runs.sqlite3')
        db.execute('CREATE TABLE gmail_reply_events (object_id TEXT NOT NULL,message_id TEXT NOT NULL,dispatch_state TEXT NOT NULL,PRIMARY KEY(object_id,message_id))')
        db.execute('INSERT INTO gmail_reply_events VALUES (?,?,?)',('customer:1','legacy','failed'))
        db.commit();db.close()
        barrier=threading.Barrier(2);failures=[];services=[]
        class Connection:
            def __init__(self,raw):self.raw=raw;self.first=True
            def execute(self,sql,*args):
                result=self.raw.execute(sql,*args)
                if sql=='PRAGMA table_info(gmail_reply_events)' and self.first:
                    self.first=False;result=list(result);barrier.wait(timeout=5)
                return result
            def commit(self):return self.raw.commit()
        def initialize():
            try:
                raw=sqlite3.connect(self.root/'runs.sqlite3',timeout=10,check_same_thread=False)
                self.connections.append(raw)
                app=SimpleNamespace(state=self.root,db=Connection(raw),lock=threading.RLock())
                services.append(GmailService(app))
            except Exception as exc:failures.append(exc)
        threads=[threading.Thread(target=initialize) for _ in range(2)]
        for thread in threads:thread.start()
        for thread in threads:thread.join(15)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(failures,[])
        self.assertEqual(len(services),2)
        columns={row[1] for row in self.connections[0].execute('PRAGMA table_info(gmail_reply_events)')}
        self.assertTrue({'job_id','updated_at','last_error'}<=columns)
        self.assertEqual(self.connections[0].execute('SELECT dispatch_state FROM gmail_reply_events WHERE message_id=?',('legacy',)).fetchone(),('failed',))


if __name__=='__main__':unittest.main()
