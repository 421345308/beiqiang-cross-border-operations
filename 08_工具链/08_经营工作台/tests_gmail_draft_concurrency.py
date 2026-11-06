"""Real separate SQLite connections and overlapping workers; synthetic mail only."""
import base64
import json
import multiprocessing
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from gmail_drafts import GmailDrafts
from customer_batches import CustomerBatches


def _suppressed_process_send(root,oid,version,ready,proceed,queue):
    """Child uses a separate process and DB connection; sender is a pure stub."""
    db=sqlite3.connect(Path(root)/'db.sqlite3',timeout=5)
    app=SimpleNamespace(state=Path(root),db=db,lock=threading.RLock(),
        business=SimpleNamespace(get_object=lambda oid:{'id':oid,'kind':'customer','content':'{}','facts':[]}),
        gmail=SimpleNamespace(status=lambda:{'account_email':'seller@example.test'},peek=lambda oid:{}))
    def token(account):
        ready.set()
        if not proceed.wait(10):raise TimeoutError('Synthetic child wait')
        return 'fixture'
    service=GmailDrafts(app,token_provider=token,sender=lambda t,p:queue.put('SENDER_CALLED') or {'id':'fake'},grant_reader=lambda a:{})
    try:
        service.send(oid,version)
        queue.put('unexpected_success')
    except ValueError:
        queue.put('blocked')
    except Exception as exc:
        queue.put(type(exc).__name__)
    finally:db.close()


class ConcurrentDraftTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.oid = 'customer:synthetic'
        self.calls = []

    def service(self, sender=None):
        db = sqlite3.connect(self.root / 'db.sqlite3', check_same_thread=False, timeout=5)
        self.addCleanup(db.close)
        obj = {'id': self.oid, 'kind': 'customer', 'content': json.dumps({'email': 'buyer@example.test'}), 'facts': []}
        app = SimpleNamespace(state=self.root, db=db, lock=threading.RLock(),
                              business=SimpleNamespace(get_object=lambda oid:{**obj, 'id':oid}),
                              gmail=SimpleNamespace(status=lambda:{'account_email':'seller@example.test'}, peek=lambda oid:{}))
        service = GmailDrafts(app, token_provider=lambda account:'fixture', sender=sender or (lambda t,p:self.calls.append(p) or {'id':'sent1'}),
                              grant_reader=lambda account:{}, request=lambda *a,**kw:{'messages':[]})
        service._after_send = lambda draft:None
        return service

    def filled(self, service):
        d = service.get(self.oid)
        return service.save(self.oid, d['version'], {'subject':'Synthetic mail', 'body_en':'Synthetic body'})

    def race(self, calls):
        barrier = threading.Barrier(len(calls))
        results = []
        def run(call):
            try:
                barrier.wait(timeout=5)
                results.append(('ok', call()))
            except Exception as exc:
                results.append(('error', exc))
        threads = [threading.Thread(target=run, args=(call,)) for call in calls]
        for t in threads:t.start()
        for t in threads:t.join(10)
        self.assertFalse(any(t.is_alive() for t in threads))
        return results

    def test_simultaneous_first_get_preserves_single_created_version(self):
        a, b = self.service(), self.service()
        results = self.race([lambda:a.get(self.oid), lambda:b.get(self.oid)])
        self.assertEqual([x[0] for x in results], ['ok', 'ok'])
        self.assertEqual(results[0][1]['version'], results[1][1]['version'])

    def test_two_connections_same_version_save_only_one_wins(self):
        a, b = self.service(), self.service()
        d = self.filled(a)
        results = self.race([lambda:a.save(self.oid,d['version'],{'body_en':'A'}),
                             lambda:b.save(self.oid,d['version'],{'body_en':'B'})])
        self.assertEqual(sum(r[0] == 'ok' for r in results), 1)
        self.assertEqual(sum(isinstance(r[1], ValueError) for r in results), 1)

    def test_attachment_and_text_edit_compete_on_same_version(self):
        a, b = self.service(), self.service()
        d = self.filled(a)
        results = self.race([lambda:a.add_attachment(self.oid,d['version'],filename='synthetic.pdf', data=base64.b64encode(b'fake').decode()),
                             lambda:b.save(self.oid,d['version'],{'body_en':'Changed'})])
        self.assertEqual(sum(r[0] == 'ok' for r in results), 1)

    def test_send_claim_is_exclusive_reopen_does_not_change_inflight(self):
        started, finish = threading.Event(), threading.Event()
        def sender(token, payload):
            self.calls.append(payload)
            started.set()
            if not finish.wait(5):raise TimeoutError()
            return {'id':'sent1'}
        a, b = self.service(sender), self.service(sender)
        d = self.filled(a)
        results = []
        thread = threading.Thread(target=lambda:results.append(a.send(self.oid,d['version'])))
        thread.start()
        try:
            self.assertTrue(started.wait(5))
            reopened = self.service(sender)
            self.assertEqual(reopened.get(self.oid)['status'], 'sending')
            self.assertEqual(reopened.reconcile(self.oid)['status'], 'sending')
            with self.assertRaises(ValueError):reopened.resume_unsent(self.oid, True)
            with self.assertRaises(ValueError):b.send(self.oid, d['version'])
            # Network wait does not hold a database transaction.
            other = b.get('customer:another')
            self.assertEqual(other['status'], 'draft')
        finally:
            finish.set()
            thread.join(10)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(results[0]['status'], 'sent')

    def test_simultaneous_send_calls_one_external_send(self):
        a, b = self.service(), self.service()
        d = self.filled(a)
        results = self.race([lambda:a.send(self.oid,d['version']), lambda:b.send(self.oid,d['version'])])
        self.assertEqual(sum(r[0] == 'ok' for r in results), 1)
        self.assertEqual(len(self.calls), 1)

    def test_unknown_cannot_be_resent_by_another_connection(self):
        def sender(t,p):
            self.calls.append(p)
            raise TimeoutError()
        a, b = self.service(sender), self.service(sender)
        d = self.filled(a)
        self.assertEqual(a.send(self.oid,d['version'])['status'], 'unknown')
        with self.assertRaises(ValueError):b.send(self.oid,d['version'])
        self.assertEqual(len(self.calls), 1)

    def test_late_result_does_not_overwrite_new_draft(self):
        a = self.service()
        d = self.filled(a)
        sent = a.send(self.oid,d['version'])
        new = a.new(self.oid)
        a._sent(sent, {'id':'old-late-id'})
        self.assertEqual(a.get(self.oid)['version'], new['version'])
        self.assertEqual(a.get(self.oid)['status'], 'draft')

    def test_interrupted_owner_requires_reconciliation_before_manual_restore(self):
        a = self.service()
        d = self.filled(a)
        d.update(status='sending', message_id='<interrupted@example.test>', sender_pid=123456789)
        a._put(d)
        b = self.service()
        self.assertEqual(b.get(self.oid)['status'], 'sending')
        with self.assertRaises(ValueError):b.resume_unsent(self.oid, True)
        with patch.object(b, '_sender_alive', return_value=False):
            self.assertEqual(b.reconcile(self.oid)['status'], 'unknown')
        with self.assertRaises(ValueError):b.resume_unsent(self.oid, False)
        restored = b.resume_unsent(self.oid, True)
        self.assertEqual(restored['status'], 'draft')
        self.assertNotEqual(restored['version'], d['version'])
        self.assertEqual(self.calls, [])

    def test_attachment_file_not_deleted_when_database_write_rolls_back(self):
        a = self.service()
        d = self.filled(a)
        d = a.add_attachment(self.oid,d['version'],filename='synthetic.pdf',data=base64.b64encode(b'fake').decode())
        attachment = d['attachments'][0]
        real = a._changed
        def fail(draft):
            real(draft)
            raise OSError('Synthetic failure before commit')
        with patch.object(a, '_changed', side_effect=fail):
            with self.assertRaises(OSError):a.remove_attachment(self.oid,d['version'],attachment['id'])
        self.assertTrue((a.directory / attachment['id']).exists())
        self.assertEqual(a.get(self.oid)['attachments'][0]['id'], attachment['id'])
        a.remove_attachment(self.oid,d['version'],attachment['id'])
        self.assertFalse((a.directory / attachment['id']).exists())

    def batches(self,service):
        service.app.gmail_drafts=service
        service.app.customer_workspace=SimpleNamespace(profile=lambda oid:{'revision':'p1','provenance':{}})
        return CustomerBatches(service.app)

    def test_shared_dnc_blocks_direct_single_send_and_same_email_alias(self):
        service=self.service()
        draft=self.filled(service)
        alias='customer:alias'
        other=service.get(alias)
        other=service.save(alias,other['version'],{'subject':'Alias','body_en':'Synthetic body'})
        batches=self.batches(service)
        batch=batches.create({'title':'Synthetic DNC','object_ids':[self.oid]})
        batches.review_item(batch['id'],self.oid,{'revision':batch['revision'],'review_state':'do_not_contact'})
        for oid,version in ((self.oid,draft['version']),(alias,other['version'])):
            with self.subTest(oid=oid),self.assertRaisesRegex(ValueError,'不联系'):
                service.send(oid,version)
        self.assertEqual(self.calls,[])

    def test_cross_process_dnc_committed_during_token_preparation_blocks_claim(self):
        service=self.service()
        draft=self.filled(service)
        batches=self.batches(service)
        batch=batches.create({'title':'Concurrent DNC','object_ids':[self.oid]})
        context=multiprocessing.get_context('spawn')
        ready,proceed,queue=context.Event(),context.Event(),context.Queue()
        process=context.Process(target=_suppressed_process_send,args=(str(self.root),self.oid,draft['version'],ready,proceed,queue))
        process.start()
        try:
            self.assertTrue(ready.wait(10))
            batches.review_item(batch['id'],self.oid,{'revision':batch['revision'],'review_state':'do_not_contact'})
            proceed.set()
            process.join(10)
            self.assertFalse(process.is_alive())
            self.assertEqual(process.exitcode,0)
            self.assertEqual(queue.get(timeout=3),'blocked')
            self.assertEqual(service.get(self.oid)['status'],'draft')
        finally:
            proceed.set()
            if process.is_alive():process.terminate();process.join(5)
            queue.close()

    def test_dnc_without_saved_draft_suppresses_exact_original_email(self):
        service=self.service()
        draft=self.filled(service)
        batches=self.batches(service)
        batch=batches.create({'title':'No draft DNC','object_ids':['customer:never-drafted']})
        batches.review_item(batch['id'],'customer:never-drafted',{'revision':batch['revision'],'review_state':'do_not_contact'})
        with self.assertRaisesRegex(ValueError,'不联系'):service.send(self.oid,draft['version'])
        self.assertEqual(self.calls,[])

    def test_existing_process_rechecks_legacy_dnc_inserted_after_startup(self):
        service=self.service()
        draft=self.filled(service)
        batches=self.batches(service)
        batch=batches.create({'title':'Legacy DNC','object_ids':[self.oid]})
        value=batches._load(batch['id'])
        value['items'][0]['review_state']='do_not_contact'
        with service.app.lock:
            service.app.db.execute('UPDATE customer_batches SET data=? WHERE id=?',(json.dumps(value),batch['id']))
            service.app.db.commit()
        with self.assertRaisesRegex(ValueError,'不联系'):service.send(self.oid,draft['version'])
        self.assertEqual(self.calls,[])


if __name__ == '__main__':
    unittest.main()
