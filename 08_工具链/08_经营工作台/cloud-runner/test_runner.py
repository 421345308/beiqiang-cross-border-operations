"""Offline contract checks; never invokes Codex or the network."""
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch, Mock
import tempfile
import json
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

    def test_combined_owner_control_preserves_maximum_user_instruction(self):
        user = 'u' * 12000
        control = '\n\n负责人当前执行要求（版本 123；只在既有权限内执行）：\n' + '\n\n'.join(label + '：\n' + 'c' * 4000 for label in ('当前重点', '执行优先级', '补充要求'))
        self.job['instruction'] = user + control
        self.assertGreater(len(self.job['instruction']), 24000)
        self.assertLess(len(self.job['instruction']), runner.MAX_JOB_INSTRUCTION)
        self.assertGreater(runner.validate_job(self.job), 0)
        self.assertTrue(self.job['instruction'].startswith(user))
        for source_free in (False, True):
            if source_free:
                self.job.update(source=None, document=None)
            self.job['instruction'] = 'x' * (runner.MAX_JOB_INSTRUCTION + 1)
            with self.assertRaises(ValueError):
                runner.validate_job(self.job)

    def test_queue_endpoint_keeps_secret_off_urls(self):
        for url in ('http://host/api','https://user:secret@host/api','https://host/api?key=x'):
            with self.assertRaises(ValueError):runner.Queue(url,'fake-test-token')

    def test_service_does_not_auto_retry(self):
        unit=Path(__file__).with_name('beiqiang-workbench-runner.service.example').read_text()
        self.assertIn('Restart=no',unit)
        self.assertIn('KillMode=control-group',unit)
        self.assertIn('EnvironmentFile=%h/',unit)
        self.assertNotIn('OPENAI_API_KEY=',unit)

    def test_automatic_execution_failure_persists_pause_and_stops_claiming(self):
        queue=Mock()
        queue.call.side_effect=lambda action, **fields: {'job':self.job} if action=='claim' else {}
        with tempfile.TemporaryDirectory() as directory:
            env={'WORKBENCH_RUNNER_URL':'https://www.beiqiang.online/api/workbench-runner',
                 'WORKBENCH_RUNNER_SECRET':'synthetic-test-secret-only',
                 'WORKBENCH_RUNNER_STATE':directory}
            with patch.dict(runner.os.environ,env), patch('sys.argv',['runner.py']), \
                    patch.object(runner.shutil,'which',return_value='/fixture/codex'), \
                    patch('preflight.preflight',return_value={'ok':True}), \
                    patch.object(runner,'Queue',return_value=queue), \
                    patch.object(runner,'execute',side_effect=RuntimeError('fixture failure')):
                with self.assertRaises(RuntimeError):runner.main()
            pause=json.loads((Path(directory)/'blocked.json').read_text())
            self.assertEqual(pause['run_id'],self.job['id'])
            self.assertEqual(pause['reason'],'execution_or_report_failed')
            self.assertEqual([call.args[0] for call in queue.call.call_args_list],
                             ['heartbeat','claim','fail','heartbeat'])
            self.assertFalse(queue.call.call_args.kwargs['capabilities']['ready'])


if __name__=='__main__':unittest.main()
