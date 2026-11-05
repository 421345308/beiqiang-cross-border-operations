"""Gmail test event through the real job manager, with a simulated executor.

No Gmail account, network, model call, message send, or customer data is used.
"""
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from agent_jobs import AgentJobs, codex_executable
from gmail_sync import GmailService
from server import Workbench
from tests_agent_jobs import join_job_threads, stop_job_threads
from tests_gmail_sync import ACCOUNT, Business as MailBusiness, Mailbox, message
from tests_runtime_backend import FakeBackend


class Business(MailBusiness):
    def __init__(self):
        super().__init__()
        self.artifacts=[]

    def save_artifact(self, object_id, title, content, artifact_id=None):
        row={'id':'test-artifact','object_id':object_id,'title':title,'content':content}
        self.artifacts.append(row)
        return row


class GmailJobIntegrationTests(unittest.TestCase):
    def test_reply_event_links_real_persisted_job_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            db=sqlite3.connect(root/'runs.sqlite3',check_same_thread=False,timeout=10)
            flow={'state':'waiting_customer','bucket':'active','waiting_since':'2026-11-01T01:00:00Z'}
            workspace=SimpleNamespace(_saved_profile=lambda oid:{'workflow':flow},profile=lambda oid:{})
            app=SimpleNamespace(root=root,state=root,lock=threading.RLock(),db=db,
                                business=Business(),customer_workspace=workspace)
            backend=FakeBackend()
            app.agent_jobs=AgentJobs(app,backend=backend)
            mailbox=Mailbox()
            mailbox.messages=[message('test-inbound')]
            callbacks=[]
            def on_reply(oid,msg,context):
                callbacks.append(msg['id'])
                return Workbench._gmail_reply(app,oid,msg,context)
            def service():
                result=GmailService(app,on_new_reply=on_reply)
                result._account=ACCOUNT
                result._connected_at='2026-11-01T00:00:00Z'
                result._mailbox=mailbox
                return result
            try:
                first=service()
                result=first.customer('customer:1')
                self.assertTrue(result['reply_pending'])
                state,job_id=db.execute('SELECT dispatch_state,job_id FROM gmail_reply_events WHERE object_id=? AND message_id=?',('customer:1','test-inbound')).fetchone()
                self.assertEqual(state,'dispatched')
                self.assertTrue(job_id)
                deadline=time.monotonic()+10
                while time.monotonic()<deadline:
                    job=app.agent_jobs.get_job(job_id)
                    if job['status'] not in ('queued','running'):break
                    time.sleep(.01)
                join_job_threads(app.agent_jobs,job_id)
                job=app.agent_jobs.get_job(job_id)
                self.assertEqual(job['status'],'completed')
                self.assertEqual(job['mode'],'mail_draft')
                self.assertEqual(job['object_id'],'customer:1')
                self.assertEqual(job['artifact_id'],'test-artifact')
                self.assertEqual(backend.commands[0]['mode'],'mail_draft')
                service().customer('customer:1')
                self.assertEqual(callbacks,['test-inbound'])
                self.assertEqual(len(app.agent_jobs.list_jobs()),1)
                self.assertEqual(db.execute('SELECT job_id FROM gmail_reply_events WHERE object_id=? AND message_id=?',('customer:1','test-inbound')).fetchone()[0],job_id)
            finally:
                stop_job_threads(app.agent_jobs)
                db.close()

    @unittest.skipUnless(os.environ.get('BEIQIANG_RUN_LIVE_CODEX_TEST')=='1',
                         '真实 Codex 验证需显式启用')
    def test_synthetic_reply_runs_real_codex_without_real_mail_or_send(self):
        self.assertTrue(codex_executable(), '未找到 Codex CLI')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            db=sqlite3.connect(root/'runs.sqlite3',check_same_thread=False,timeout=10)
            flow={'state':'waiting_customer','bucket':'active','waiting_since':'2026-11-01T01:00:00Z'}
            app=SimpleNamespace(root=root,state=root,lock=threading.RLock(),db=db,
                                business=Business(),customer_workspace=SimpleNamespace(
                                    _saved_profile=lambda oid:{'workflow':flow},profile=lambda oid:{}))
            app.agent_jobs=AgentJobs(app)
            # A synthetic prompt keeps the test isolated from real customers,
            # Gmail, platform writes and external communications.
            app.agent_jobs._prompt=lambda job,obj:'只根据以下模拟内容写一句内部摘要：测试买家询问日常休闲鞋。不要调用工具或发送消息。'
            mailbox=Mailbox();mailbox.messages=[message('live-synthetic')]
            mail=GmailService(app,on_new_reply=lambda oid,msg,ctx:Workbench._gmail_reply(app,oid,msg,ctx))
            mail._account=ACCOUNT;mail._connected_at='2026-11-01T00:00:00Z';mail._mailbox=mailbox
            try:
                mail.customer('customer:1')
                state,job_id=db.execute('SELECT dispatch_state,job_id FROM gmail_reply_events WHERE message_id=?',('live-synthetic',)).fetchone()
                self.assertEqual(state,'dispatched');self.assertTrue(job_id)
                deadline=time.monotonic()+180
                while time.monotonic()<deadline:
                    job=app.agent_jobs.get_job(job_id)
                    if job['status'] not in ('queued','running'):break
                    time.sleep(.2)
                self.assertNotIn(job['status'],('queued','running'),'真实 Codex 运行超时')
                join_job_threads(app.agent_jobs,job_id)
                job=app.agent_jobs.get_job(job_id)
                self.assertEqual(job['status'],'completed',job.get('error'))
                self.assertTrue(job.get('session_id'));self.assertTrue(job.get('artifact_id'))
                self.assertEqual(job['mode'],'mail_draft')
                print('synthetic_gmail_real_codex: completed; linked_job=yes; session=yes; cost=unknown')
            finally:
                stop_job_threads(app.agent_jobs)
                db.close()


if __name__=='__main__':unittest.main()
