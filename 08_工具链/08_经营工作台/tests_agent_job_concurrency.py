"""Independent SQLite/PID claims; held workers never run Codex or network."""
import multiprocessing
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from agent_jobs import AgentJobs


class HeldThread:
    def __init__(self,**kwargs):pass
    def start(self):pass


def app_for(path):
    return SimpleNamespace(db=sqlite3.connect(path,check_same_thread=False,timeout=5),lock=threading.RLock(),
        business=SimpleNamespace(get_object=lambda oid:{'id':oid,'kind':'product','title':oid}))


def claim_process(path,oid,barrier,finish,queue):
    app=app_for(path)
    try:
        jobs=AgentJobs(app)
        barrier.wait(timeout=10)
        with patch('agent_jobs.threading.Thread',HeldThread):
            try:
                job=jobs.start(oid,'Synthetic local claim')
                result=('queued',job['id'],os.getpid())
            except ValueError:result=('conflict',None,os.getpid())
        queue.put(result)
        finish.wait(15)
    finally:app.db.close()


class JobConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'jobs.sqlite3'
        self.application=self.app();self.jobs=AgentJobs(self.application)

    def app(self):
        app=app_for(self.path);self.addCleanup(app.db.close);return app

    def start(self,jobs,oid='product:a'):
        with patch('agent_jobs.threading.Thread',HeldThread):return jobs.start(oid,'Synthetic claim')

    def test_two_connections_only_one_same_object_claim(self):
        other=AgentJobs(self.app());barrier=threading.Barrier(2);results=[]
        def run(jobs):
            barrier.wait(timeout=5)
            try:results.append(('queued',jobs.start('product:a','Synthetic claim')))
            except ValueError:results.append(('conflict',None))
        threads=[threading.Thread(target=run,args=(jobs,)) for jobs in (self.jobs,other)]
        with patch('agent_jobs.threading.Thread',HeldThread):
            for t in threads:t.start()
            for t in threads:t.join(10)
        self.assertFalse(any(t.is_alive() for t in threads))
        self.assertEqual(sorted(v[0] for v in results),['conflict','queued'])
        self.assertEqual(len(self.jobs.list_jobs()),1)

    def processes(self,oids):
        context=multiprocessing.get_context('spawn')
        barrier=context.Barrier(len(oids));finish=context.Event();queue=context.Queue()
        processes=[context.Process(target=claim_process,args=(str(self.path),oid,barrier,finish,queue)) for oid in oids]
        for process in processes:process.start()
        try:
            results=[queue.get(timeout=15) for _ in processes]
            reopened=AgentJobs(self.app());active=reopened.list_jobs()
            self.assertTrue(all(v['status']=='queued' for v in active))
            self.assertTrue(all(reopened._pid_alive(v['owner_pid']) is True for v in active))
            for v in active:
                with self.assertRaises(ValueError):reopened.cancel(v['id'])
            return results,active
        finally:
            finish.set()
            for process in processes:
                process.join(10)
                if process.is_alive():process.terminate();process.join(5)
            queue.close()

    def test_real_processes_compete_same_object_and_dead_owner_can_recover(self):
        results,active=self.processes(['product:a','product:a'])
        self.assertEqual(sorted(v[0] for v in results),['conflict','queued'])
        reopened=AgentJobs(self.app())
        self.assertEqual(reopened.get_job(active[0]['id'])['status'],'failed')
        self.assertEqual(self.start(reopened)['owner_pid'],os.getpid())

    def test_real_processes_can_claim_different_objects(self):
        results,active=self.processes(['product:a','product:b'])
        self.assertEqual([v[0] for v in results],['queued','queued'])
        self.assertEqual({v['object_id'] for v in active},{'product:a','product:b'})

    def test_live_or_unknown_owner_never_marked_failed_or_resumed(self):
        job=self.start(self.jobs)
        for alive in (True,None):
            with patch.object(AgentJobs,'_pid_alive',return_value=alive):
                reopened=AgentJobs(self.app())
                self.assertEqual(reopened.get_job(job['id'])['status'],'queued')
                with self.assertRaises(ValueError):reopened.resume(job['id'],'Synthetic resume')

    def test_legacy_unknown_active_preserved_terminal_can_explicitly_resume(self):
        self.jobs._save({'id':'legacy','object_id':'product:a','status':'running','events':[],'session_id':'session'})
        reopened=AgentJobs(self.app())
        self.assertEqual(reopened.get_job('legacy')['status'],'running')
        with self.assertRaises(ValueError):self.start(reopened)
        with self.assertRaises(ValueError):reopened.cancel('legacy')
        self.jobs._save({'id':'terminal','object_id':'product:b','status':'failed','events':[],'session_id':'session'})
        with patch('agent_jobs.threading.Thread',HeldThread):job=reopened.resume('terminal','Check prior results then resume')
        self.assertEqual(job['owner_pid'],os.getpid())

    def test_owner_dead_but_child_unknown_or_alive_is_not_recovered(self):
        self.jobs._save({'id':'old','object_id':'product:a','status':'running','events':[],
                        'owner_pid':123,'process_id':456,'session_id':'session'})
        for child in (True,None):
            with patch.object(AgentJobs,'_pid_alive',side_effect=lambda pid:False if pid==123 else child):
                reopened=AgentJobs(self.app())
                self.assertEqual(reopened.get_job('old')['status'],'running')
                with self.assertRaises(ValueError):self.start(reopened)

    def test_terminal_worker_cleanup_blocks_other_instance_and_resume(self):
        job=self.start(self.jobs);job.update(status='failed',session_id='session');self.jobs._save(job)
        other=AgentJobs(self.app())
        with self.assertRaises(ValueError):self.start(other)
        with self.assertRaises(ValueError):other.resume(job['id'],'Synthetic resume')

    def test_competing_resumes_only_one_queues_and_preserves_origin_fields(self):
        self.jobs._save({'id':'old','object_id':'product:a','status':'failed','events':[],
                        'session_id':'session','batch_id':'a'*32,'source_event':{'kind':'gmail_reply','object_id':'product:a','message_id':'mail'}})
        other=AgentJobs(self.app());barrier=threading.Barrier(2);results=[]
        def run(jobs):
            barrier.wait(timeout=5)
            try:
                results.append(jobs.resume('old','Synthetic resume'))
            except ValueError:results.append(None)
        threads=[threading.Thread(target=run,args=(jobs,)) for jobs in (self.jobs,other)]
        with patch('agent_jobs.threading.Thread',HeldThread):
            for t in threads:t.start()
            for t in threads:t.join(10)
        self.assertEqual(sum(v is not None for v in results),1)
        saved=self.jobs.get_job('old')
        self.assertEqual(saved['batch_id'],'a'*32)
        self.assertEqual(saved['source_event']['message_id'],'mail')

    def test_ownerless_legacy_requires_explicit_identified_dead_owner_before_resume(self):
        self.jobs._save({'id':'legacy','object_id':'product:a','status':'running','events':[],'session_id':'session'})
        for alive in (True,None):
            with patch.object(self.jobs,'_pid_alive',return_value=alive):
                with self.assertRaises(ValueError):self.jobs.recover_legacy('legacy',confirmed=True,former_owner_pid=123,
                    evidence='Checked original service log PID 123 and recorded process exit evidence.')
        with patch.object(self.jobs,'_pid_alive',return_value=False):
            for confirmed,evidence in ((False,'Checked old service PID 123 and process exit evidence.'),(True,'waited')):
                with self.assertRaises(ValueError):self.jobs.recover_legacy('legacy',confirmed=confirmed,former_owner_pid=123,evidence=evidence)
            recovered=self.jobs.recover_legacy('legacy',confirmed=True,former_owner_pid=123,
                evidence='Original service logs identify PID 123; OS process list confirms it exited.')
            self.assertEqual(recovered['status'],'failed')
            self.assertEqual(self.jobs.threads,{})
            with patch('agent_jobs.threading.Thread',HeldThread):
                resumed=self.jobs.resume('legacy','核对已有成果后继续原会话')
        self.assertEqual(resumed['status'],'queued')
        self.assertEqual(resumed['session_id'],'session')
        self.assertEqual(resumed['owner_pid'],os.getpid())

    def test_legacy_recovery_never_ignores_unknown_child(self):
        self.jobs._save({'id':'legacy','object_id':'product:a','status':'running','events':[],'process_id':456})
        with patch.object(self.jobs,'_pid_alive',side_effect=lambda pid:False if pid==123 else None):
            with self.assertRaises(ValueError):self.jobs.recover_legacy('legacy',confirmed=True,former_owner_pid=123,
                evidence='Original server log identifies PID 123 and OS confirms the service exited.')
        self.assertEqual(self.jobs.get_job('legacy')['status'],'running')

    def test_owner_dead_running_missing_child_pid_requires_manual_spawn_window_check(self):
        self.jobs._save({'id':'launch','object_id':'product:a','status':'running','events':[],
                        'owner_pid':123,'process_id':None,'session_id':'session'})
        with patch.object(AgentJobs,'_pid_alive',return_value=False):
            reopened=AgentJobs(self.app())
            self.assertEqual(reopened.get_job('launch')['status'],'running')
            with self.assertRaises(ValueError):self.start(reopened)
            recovered=reopened.recover_legacy('launch',confirmed=True,former_owner_pid=123,
                evidence='Logs identify original PID 123; OS confirms it exited and no launch-window child remains.')
            self.assertEqual(recovered['status'],'failed')


if __name__=='__main__':unittest.main()
