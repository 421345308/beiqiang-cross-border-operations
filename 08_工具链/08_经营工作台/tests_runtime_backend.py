"""Contract and integration tests for the injected local execution adapter."""
import json
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent_jobs import AgentJobs
from codex_backend import CodexBackend
from tests_agent_jobs import Business, Process, join_job_threads, stop_job_threads


class FakeBackend:
    def __init__(self, usage=True):
        self.commands=[]
        self.parsed=0
        self.usage=usage

    def resolve_executable(self):return 'test-backend'

    def command(self, exe, folder, final, **kwargs):
        self.commands.append(kwargs)
        return [exe,'-o',str(final)]

    def spawn(self, command, *, env, flags):
        process=Process(command)
        original=process.stdout
        include_usage=self.usage
        class Stream:
            def __iter__(self):
                for line in original:
                    if include_usage and 'turn.completed' in line:
                        yield json.dumps({'type':'turn.completed','usage':{'input_tokens':12,'output_tokens':4,'unknown_secret':'private'}})+'\n'
                        yield json.dumps({'type':'turn.completed','usage':{'input_tokens':2,'output_tokens':1}})+'\n'
                    else:yield line
            def close(self):original.close()
        process.stdout=Stream()
        return process

    def parse_event(self,line):
        self.parsed+=1
        return CodexBackend.parse_event(line)


class RuntimeBackendTests(unittest.TestCase):
    def test_usage_mapping_ignores_unknown_or_invalid_fields(self):
        event=CodexBackend.parse_event(json.dumps({'type':'turn.completed','usage':{'input_tokens':0,'output_tokens':7,'cached_input_tokens':-1,'reasoning_output_tokens':True,'secret':'ignored'}}))
        self.assertEqual(event,{'kind':'completed','usage':{'input_tokens':0,'output_tokens':7}})
        self.assertIsNone(CodexBackend.parse_event('{broken'))
        self.assertIsNone(CodexBackend.parse_event(json.dumps({'type':'turn.completed'}))['usage'])

    def test_injected_backend_executes_and_preserves_usage_per_attempt(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            app=SimpleNamespace(root=root,state=root/'.local',lock=threading.RLock(),
                                db=sqlite3.connect(':memory:',check_same_thread=False),business=Business())
            backend=FakeBackend()
            jobs=AgentJobs(app,backend=backend)
            def wait(job):
                deadline=time.monotonic()+5
                while time.monotonic()<deadline:
                    current=jobs.get_job(job['id'])
                    if current['status'] not in ('queued','running'):
                        join_job_threads(jobs,job['id'])
                        return jobs.get_job(job['id'])
                    threading.Event().wait(.01)
                self.fail('backend task timed out')
            try:
                # A substituted backend does not require the default CLI locator.
                with patch('agent_jobs.codex_executable',side_effect=AssertionError('default CLI locator used')):
                    first=wait(jobs.start('product:shoe','检查既有资料'))
                    second=wait(jobs.resume(first['id'],'根据已有成果继续'))
                self.assertEqual(second['status'],'completed')
                self.assertEqual(backend.commands[1]['session_id'],first['session_id'])
                self.assertGreater(backend.parsed,0)
                self.assertEqual(second['attempt_usage'],[
                    {'attempt':1,'turns':[{'tokens':{'input_tokens':12,'output_tokens':4}},{'tokens':{'input_tokens':2,'output_tokens':1}}],'cost':None},
                    {'attempt':2,'turns':[{'tokens':{'input_tokens':12,'output_tokens':4}},{'tokens':{'input_tokens':2,'output_tokens':1}}],'cost':None}])
                self.assertNotIn('private',json.dumps(second))
            finally:
                stop_job_threads(jobs)
                app.db.close()

    def test_no_reported_usage_is_unknown_not_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            app=SimpleNamespace(root=root,state=root/'.local',lock=threading.RLock(),
                                db=sqlite3.connect(':memory:',check_same_thread=False),business=Business())
            jobs=AgentJobs(app,backend=FakeBackend(usage=False))
            try:
                job=jobs.start('product:shoe','核对资料')
                deadline=time.monotonic()+5
                while time.monotonic()<deadline:
                    row=jobs.get_job(job['id'])
                    if row['status'] not in ('queued','running'):break
                    threading.Event().wait(.01)
                join_job_threads(jobs,job['id'])
                self.assertEqual(jobs.get_job(job['id'])['attempt_usage'],[{'attempt':1,'turns':[{'tokens':None}],'cost':None}])
            finally:
                stop_job_threads(jobs)
                app.db.close()

    def test_completed_event_buffered_after_cancel_records_usage_without_publication(self):
        gate=threading.Event()
        class CancelBackend(FakeBackend):
            def spawn(self, command, *, env, flags):
                process=Process(command,gate=gate)
                original=process.stdout
                class Stream:
                    def __iter__(self):
                        for line in original:
                            if 'turn.completed' in line:
                                yield json.dumps({'type':'turn.completed','usage':{'input_tokens':5}})+'\n'
                            else:yield line
                    def close(self):original.close()
                process.stdout=Stream()
                return process
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            app=SimpleNamespace(root=root,state=root/'.local',lock=threading.RLock(),
                                db=sqlite3.connect(':memory:',check_same_thread=False),business=Business())
            jobs=AgentJobs(app,backend=CancelBackend())
            try:
                with patch.object(jobs,'_stop',side_effect=lambda proc:proc.kill()):
                    job=jobs.start('product:shoe','核对资料')
                    deadline=time.monotonic()+5
                    while time.monotonic()<deadline:
                        if jobs.get_job(job['id']).get('session_id'):break
                        threading.Event().wait(.01)
                    self.assertTrue(jobs.get_job(job['id']).get('session_id'))
                    jobs.cancel(job['id'])
                    join_job_threads(jobs,job['id'])
                result=jobs.get_job(job['id'])
                self.assertEqual(result['status'],'cancelled')
                self.assertEqual(result['attempt_usage'],[{'attempt':1,'turns':[{'tokens':{'input_tokens':5}}],'cost':None}])
                self.assertFalse(app.business.artifacts)
            finally:
                gate.set();stop_job_threads(jobs);app.db.close()


if __name__=='__main__':unittest.main()
