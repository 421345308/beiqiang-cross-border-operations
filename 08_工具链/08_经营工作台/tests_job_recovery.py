"""Interrupted object jobs must not be bypassed by starting a new writer."""
import os
import sqlite3
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agent_jobs import AgentJobs


class HeldThread:
    def __init__(self, **kwargs):
        pass

    def start(self):
        pass


class JobRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.app = SimpleNamespace(
            db=sqlite3.connect(':memory:', check_same_thread=False),
            lock=threading.RLock(),
            business=SimpleNamespace(get_object=lambda oid: {'id': oid, 'kind': 'product', 'title': oid}),
        )
        self.jobs = AgentJobs(self.app)
        self.addCleanup(self.app.db.close)

    def record(self, job_id, object_id, status, pid=None):
        self.jobs._save({'id': job_id, 'object_id': object_id, 'status': status,
                         'process_id': pid, 'events': [], 'session_id': '12345678-1234-4234-8234-123456789abc'})

    def test_restart_with_live_child_blocks_same_object_but_not_another(self):
        self.assertTrue(self.jobs._pid_alive(os.getpid()))
        self.record('interrupted', 'product:BQ009', 'running', os.getpid())
        restarted = AgentJobs(self.app)
        self.assertEqual(restarted.get_job('interrupted')['status'], 'failed')
        with self.assertRaisesRegex(ValueError, '先前进程'):
            restarted.start('product:BQ009', '接续商品研究')
        with self.assertRaisesRegex(ValueError, '先前进程'):
            restarted.resume('interrupted', '继续原工作')
        with patch('agent_jobs.threading.Thread', HeldThread):
            job = restarted.start('creation:ZX9507', '准备内容')
        self.assertEqual(job['status'], 'queued')

    def test_unknown_process_blocks_new_and_other_resume_until_exit_confirmed(self):
        self.record('old', 'product:BQ009', 'failed', 81234567)
        self.record('resume', 'product:BQ009', 'failed')
        with patch.object(self.jobs, '_pid_alive', return_value=None):
            with self.assertRaisesRegex(ValueError, '先前进程'):
                self.jobs.start('product:BQ009', '新工作')
            with self.assertRaisesRegex(ValueError, '先前进程'):
                self.jobs.resume('resume', '继续')
        with patch.object(self.jobs, '_pid_alive', return_value=False), patch('agent_jobs.threading.Thread', HeldThread):
            self.assertEqual(self.jobs.resume('resume', '先核对已有成果再继续')['status'], 'queued')

    def test_same_process_worker_in_final_cleanup_blocks_new_job(self):
        self.record('old', 'product:BQ009', 'completed')
        self.jobs.threads['old'] = object()
        with self.assertRaisesRegex(ValueError, '正在收尾'):
            self.jobs.start('product:BQ009', '后续工作')


if __name__ == '__main__':
    unittest.main()
