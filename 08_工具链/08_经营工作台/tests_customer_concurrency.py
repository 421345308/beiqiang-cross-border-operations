"""Cross-process serialization for the shared customer profile JSON."""
import copy
import json
import multiprocessing
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from customer_workspace import CustomerWorkspace, CustomerWriteOutcomeUnknown

OID='customer:website-test'
OBJ={'id':OID,'kind':'customer','source':'fixture','content':json.dumps({'requirements':'sample'})}


def open_workspace(root, database, gmail=None):
    app=SimpleNamespace(root=Path(root),db=sqlite3.connect(database,timeout=10),lock=threading.RLock(),
                        business=SimpleNamespace(get_object=lambda oid:copy.deepcopy(OBJ)))
    if gmail is not None:app.gmail=gmail
    return app,CustomerWorkspace(app)


def competing_writer(root,database,operation,revision,ready,start,held,release,read_started,results):
    app=None
    try:
        app,work=open_workspace(root,database)
        profile_snapshot=work.profile(OID) if operation=='analysis' else None
        workflow_snapshot=work.workflow(OID) if operation=='workflow' else None
        original_write=work._write
        original_read=work._saved_profile
        if operation in ('analysis','commercial_first'):
            def paused_write(path,data):
                held.set()
                if not release.wait(10):raise RuntimeError('writer release timed out')
                return original_write(path,data)
            work._write=paused_write
        else:
            def observed_read(oid):
                read_started.set()
                return original_read(oid)
            work._saved_profile=observed_read
        ready.set()
        if not start.wait(10):raise RuntimeError('start timed out')
        if operation=='analysis':
            profile=profile_snapshot
            work.save_profile(OID,{'revision':profile['revision'],'source_hash':profile['source_hash'],'analysis':{'intent':'analysis kept'}})
        elif operation=='workflow':
            work.save_workflow(OID,{'revision':workflow_snapshot['revision'],'next_action':'workflow kept'})
        elif operation=='commercial_first':
            work.save_commercial(OID,{'revision':revision,'owner':'first'})
        else:
            work.save_commercial(OID,{'revision':revision,'owner':'second'})
        results.put((operation,'ok'))
    except Exception as exc:
        results.put((operation,type(exc).__name__,str(exc)))
    finally:
        if app:app.db.close()


class CustomerConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.database=str(self.root/'state.sqlite3')
        self.app,self.work=open_workspace(self.root,self.database)
        self.addCleanup(self.app.db.close)
        # An existing indexed profile makes the competing read observable.
        profile=self.work.profile(OID)
        self.work.save_profile(OID,{'revision':profile['revision'],'source_hash':profile['source_hash'],'analysis':{'fit':'existing'}})

    def run_competing(self,first,second,revision=None):
        ctx=multiprocessing.get_context('spawn')
        ready_a,ready_b,start_a,start_b,held,release,read_started=[ctx.Event() for _ in range(7)]
        results=ctx.Queue()
        args=(str(self.root),self.database)
        a=ctx.Process(target=competing_writer,args=(*args,first,revision,ready_a,start_a,held,release,read_started,results))
        b=ctx.Process(target=competing_writer,args=(*args,second,revision,ready_b,start_b,held,release,read_started,results))
        a.start();b.start()
        try:
            self.assertTrue(ready_a.wait(15));self.assertTrue(ready_b.wait(15))
            start_a.set();self.assertTrue(held.wait(15))
            start_b.set()
            # The second process cannot read the profile inside its write until
            # the first process completes its transaction.
            self.assertFalse(read_started.wait(.4))
            release.set()
            values=[results.get(timeout=15),results.get(timeout=15)]
            a.join(15);b.join(15)
            self.assertEqual((a.exitcode,b.exitcode),(0,0))
            return {row[0]:row[1:] for row in values}
        finally:
            release.set();start_a.set();start_b.set()
            for process in (a,b):
                process.join(3)
                if process.is_alive():process.terminate();process.join(3)
            results.close();results.join_thread()

    def test_analysis_and_workflow_from_different_processes_preserve_both(self):
        result=self.run_competing('analysis','workflow')
        self.assertEqual(result['analysis'],('ok',));self.assertEqual(result['workflow'],('ok',))
        profile=self.work.profile(OID)
        self.assertEqual(profile['analysis']['intent'],'analysis kept')
        self.assertEqual(profile['workflow']['next_action'],'workflow kept')

    def test_concurrent_commercial_writes_only_one_old_revision_succeeds(self):
        revision=self.work.commercial(OID)['revision']
        result=self.run_competing('commercial_first','commercial_second',revision)
        self.assertEqual(result['commercial_first'],('ok',))
        self.assertEqual(result['commercial_second'][0],'WorkspaceConflict')
        self.assertEqual(self.work.commercial(OID)['owner'],'first')

    def test_failed_validation_releases_transaction_and_rejects_nested(self):
        with self.assertRaises(ValueError):self.work.save_workflow(OID,{'revision':self.work.workflow(OID)['revision'],'priority':'bad'})
        self.assertFalse(self.app.db.in_transaction)
        with patch.object(self.work,'_write',side_effect=OSError('write failed')):
            with self.assertRaises(OSError):self.work.save_workflow(OID,{'revision':self.work.workflow(OID)['revision'],'next_action':'not persisted'})
        self.assertFalse(self.app.db.in_transaction)
        self.app.db.execute('BEGIN')
        try:
            with self.assertRaisesRegex(RuntimeError,'已有数据库事务'):
                self.work.save_workflow(OID,{'revision':self.work.workflow(OID)['revision'],'next_action':'must not commit caller transaction'})
            self.assertTrue(self.app.db.in_transaction)
        finally:self.app.db.rollback()
        with self.work._profile_write():
            with self.assertRaisesRegex(RuntimeError,'不能提前提交'):
                self.work._store_profile(OID,{},commit=True)
        self.assertEqual(self.work.save_workflow(OID,{'revision':self.work.workflow(OID)['revision'],'next_action':'recovered'})['next_action'],'recovered')

    def test_index_failure_restores_existing_and_removes_first_created_profile(self):
        row=self.app.db.execute('SELECT path FROM customer_profiles WHERE object_id=?',(OID,)).fetchone()
        existing=self.root/row[0]
        before=existing.read_bytes()
        self.app.db.execute("CREATE TRIGGER refuse_customer BEFORE INSERT ON customer_profiles BEGIN SELECT RAISE(ABORT, 'fixture index failure'); END")
        self.app.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.work.save_workflow(OID,{'revision':self.work.workflow(OID)['revision'],'next_action':'should not persist'})
        self.assertEqual(existing.read_bytes(),before)
        self.assertFalse(self.app.db.in_transaction)
        new_id='customer:website-new'
        new_path=self.root/'04_客户开发/.local/网站询盘/new/客户分析.json'
        with self.assertRaises(sqlite3.IntegrityError):
            self.work.save_workflow(new_id,{'revision':self.work.workflow(new_id)['revision'],'next_action':'should not persist'})
        self.assertFalse(new_path.exists())
        self.assertIsNone(self.app.db.execute('SELECT path FROM customer_profiles WHERE object_id=?',(new_id,)).fetchone())
        self.app.db.execute('DROP TRIGGER refuse_customer');self.app.db.commit()
        self.assertEqual(self.work.save_workflow(OID,{'revision':self.work.workflow(OID)['revision'],'next_action':'after failure'})['next_action'],'after failure')

    def test_sqlite_automatic_rollback_reports_uncertain_file_outcome(self):
        self.app.db.execute("CREATE TRIGGER rollback_customer BEFORE INSERT ON customer_profiles BEGIN SELECT RAISE(ROLLBACK, 'fixture'); END")
        self.app.db.commit()
        with self.assertRaisesRegex(CustomerWriteOutcomeUnknown,'结果不明'):
            self.work.save_workflow(OID,{'revision':self.work.workflow(OID)['revision'],'next_action':'may have been written'})
        self.assertFalse(self.app.db.in_transaction)
        # Once SQLite has released the lock, blindly restoring could overwrite
        # an intervening process. The caller must inspect the current file.
        self.assertEqual(self.work.workflow(OID)['next_action'],'may have been written')

    def test_process_local_gmail_cache_does_not_create_false_conflict(self):
        pending={'value':False}
        self.app.gmail=SimpleNamespace(peek=lambda oid:{'reply_pending':pending['value']})
        self.work.save_workflow(OID,{'revision':self.work.workflow(OID)['revision'],'state':'preparing'})
        self.work.save_workflow(OID,{'revision':self.work.workflow(OID)['revision'],'state':'waiting_customer','next_action':'wait'})
        old=self.work.commercial(OID)
        pending['value']=True
        new=self.work.commercial(OID)
        self.assertEqual(old['revision'],new['revision'])
        self.assertNotEqual(old['next_action'],new['next_action'])
        # A different process with the same DB but an empty Gmail cache sees
        # the same revision. Persisted events, tested below, change it.
        other,other_work=open_workspace(self.root,self.database,SimpleNamespace(peek=lambda oid:{'reply_pending':False}))
        try:self.assertEqual(other_work.commercial(OID)['revision'],new['revision'])
        finally:other.db.close()

    def test_gmail_event_from_independent_connection_invalidates_old_revision(self):
        self.app.db.execute('CREATE TABLE gmail_reply_events (object_id TEXT, message_id TEXT, dispatch_state TEXT, PRIMARY KEY(object_id,message_id))')
        self.app.db.execute('CREATE TABLE gmail_acknowledged (object_id TEXT PRIMARY KEY, message_id TEXT)')
        self.app.db.commit()
        old=self.work.commercial(OID)
        other=sqlite3.connect(self.database,timeout=5)
        try:
            other.execute('INSERT INTO gmail_reply_events VALUES (?,?,?)',(OID,'message-1','dispatching'));other.commit()
            self.assertNotEqual(old['revision'],self.work.commercial(OID)['revision'])
            with self.assertRaisesRegex(ValueError,'已变化'):
                self.work.save_commercial(OID,{'revision':old['revision'],'next_action':'stale'})
            after_event=self.work.commercial(OID)
            other.execute('UPDATE gmail_reply_events SET dispatch_state=? WHERE object_id=?',('dispatched',OID));other.commit()
            self.assertEqual(after_event['revision'],self.work.commercial(OID)['revision'])
            other.execute('INSERT INTO gmail_acknowledged VALUES (?,?)',(OID,'message-1'));other.commit()
            self.assertNotEqual(after_event['revision'],self.work.commercial(OID)['revision'])
        finally:other.close()

    def test_website_source_change_invalidates_old_revision(self):
        holder={'object':copy.deepcopy(OBJ)}
        self.app.business.get_object=lambda oid:copy.deepcopy(holder['object'])
        old=self.work.commercial(OID)
        holder['object']['content']=json.dumps({'requirements':'sample','messages':[{'id':'new','sender':'buyer','body':'changed'}]})
        self.assertNotEqual(old['revision'],self.work.commercial(OID)['revision'])
        with self.assertRaisesRegex(ValueError,'已变化'):
            self.work.save_commercial(OID,{'revision':old['revision'],'owner':'stale'})


if __name__=='__main__':unittest.main()
