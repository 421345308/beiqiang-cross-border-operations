"""Offline contract checks; never invokes Codex or the network."""
import hashlib
from pathlib import Path
import unittest
import runner


class RunnerTests(unittest.TestCase):
    def setUp(self):
        content='one unique phrase'
        self.job={'id':'a'*32,'lease_token':'test','lease_expires_at':'2099-01-01T00:00:00Z',
                  'instruction':'revise','source':'a.md','document':{'path':'a.md','content':content,
                  'hash':hashlib.sha256(content.encode()).hexdigest(),'version':1}}

    def test_readonly_command_preserves_rules(self):
        cmd=runner.command('/opt/codex/bin/codex','/private/schema.json','/private/job')
        self.assertNotIn('--ignore-rules',cmd)
        self.assertIn('read-only',cmd)
        self.assertIn('--ignore-user-config',cmd)
        for name in ('shell_tool','apps','plugins','image_generation'):
            self.assertIn(['--disable',name],[cmd[i:i+2] for i in range(len(cmd)-1)])

    def test_linux_process_is_separate_session(self):
        self.assertEqual(runner.process_flags('posix'),{'start_new_session':True})

    def test_snapshot_conflict_and_cross_source(self):
        self.assertGreater(runner.validate_job(self.job),0)
        proposal={'summary':'test','changes':[{'path':'other.md','before':'unique','after':'exact','reason':'test'}],'next_steps':[]}
        with self.assertRaises(ValueError):runner.validate_result(self.job,proposal)
        self.job['document']['hash']='bad'
        with self.assertRaises(ValueError):runner.validate_job(self.job)

    def test_no_source_requires_no_changes(self):
        self.job.update(source=None,document=None)
        runner.validate_job(self.job)
        runner.validate_result(self.job,{'summary':'test','changes':[],'next_steps':[]})
        with self.assertRaises(ValueError):
            runner.validate_result(self.job,{'summary':'test','changes':[{}],'next_steps':[]})

    def test_queue_endpoint_keeps_secret_off_urls(self):
        for url in ('http://host/api','https://user:secret@host/api','https://host/api?key=x'):
            with self.assertRaises(ValueError):runner.Queue(url,'fake-test-token')

    def test_service_does_not_auto_retry(self):
        unit=Path(__file__).with_name('beiqiang-workbench-runner.service.example').read_text()
        self.assertIn('Restart=no',unit)
        self.assertIn('KillMode=control-group',unit)
        self.assertIn('EnvironmentFile=%h/',unit)
        self.assertNotIn('OPENAI_API_KEY=',unit)


if __name__=='__main__':unittest.main()
