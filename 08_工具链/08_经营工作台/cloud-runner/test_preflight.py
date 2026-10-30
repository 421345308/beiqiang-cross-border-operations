import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from preflight import DEFAULT_CODEX_VERSION, QUEUE_URL, preflight


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        for name in ('codex', 'runner'):
            (root / name).mkdir(mode=0o700)
        self.env = {'PATH': 'fixture-only', 'WORKBENCH_RUNNER_URL': QUEUE_URL,
                    'WORKBENCH_RUNNER_SECRET': 'PRIVATE_QUEUE_TOKEN_' + 'x' * 40,
                    'WORKBENCH_RUNNER_PERSISTENT_ROOT': str(root),
                    'CODEX_HOME': str(root / 'codex'), 'WORKBENCH_RUNNER_STATE': str(root / 'runner')}
        self.calls = []

    def command(self, command, env):
        self.calls.append(command)
        if command[-1] == '--version':
            return SimpleNamespace(returncode=0, stdout='codex-cli ' + DEFAULT_CODEX_VERSION + '\n', stderr='')
        return SimpleNamespace(returncode=0, stdout='', stderr='Logged in using ChatGPT\n')

    def invoke(self, **kwargs):
        return preflight(self.env, run_command=kwargs.pop('run_command', self.command),
                         find_executable=kwargs.pop('find_executable', lambda name: '/fixture/codex'),
                         require_non_root=False, require_mount=False, **kwargs)

    def test_auth_check_has_no_exec_or_queue_call_and_does_not_claim_live_ready(self):
        result = self.invoke()
        self.assertTrue(result['ok'])
        self.assertTrue(result['eligible_to_start'])
        self.assertFalse(result['model_access_verified'])
        self.assertFalse(result['queue']['connection_verified'])
        self.assertFalse(result['storage']['persistence_verified'])
        self.assertEqual(result['model'], 'gpt-6.1-sol')
        self.assertEqual(len(self.calls), 2)
        self.assertIn('forced_login_method="chatgpt"', self.calls[1])
        self.assertEqual(self.calls[1][-2:], ['login', 'status'])
        self.assertFalse(any('exec' in call for call in self.calls))

    def test_production_endpoint_is_exact(self):
        for url in ('http://www.beiqiang.online/api/workbench-runner',
                    QUEUE_URL + '?x=y', 'https://localhost/api/workbench-runner',
                    'https://www.beiqiang.online.attacker.invalid/api/workbench-runner'):
            with self.subTest(url=url):
                self.env['WORKBENCH_RUNNER_URL'] = url
                result = self.invoke()
                self.assertFalse(result['ok'])
                self.assertFalse(result['queue']['endpoint_matches'])

    def test_missing_secret_stops_eligibility(self):
        for secret in ('', ' ' * 40, 'unsafe\n' + 'x' * 40):
            self.env['WORKBENCH_RUNNER_SECRET'] = secret
            self.assertFalse(self.invoke()['ok'])

    def test_api_and_provider_overrides_never_fall_back(self):
        for key in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'CODEX_ACCESS_TOKEN', 'OPENAI_BASE_URL'):
            with self.subTest(key=key):
                self.env[key] = 'DO_NOT_OUTPUT_PRIVATE_VALUE'
                self.calls = []
                result = self.invoke()
                self.assertFalse(result['ok'])
                self.assertFalse(result['auth']['authenticated'])
                self.assertEqual(len(self.calls), 1)
                self.assertNotIn(self.env[key], json.dumps(result))
                self.env.pop(key)

    def test_missing_cli_is_failure(self):
        result = self.invoke(find_executable=lambda name: None)
        self.assertFalse(result['ok'])
        self.assertEqual(self.calls, [])

    def test_wrong_version_requires_explicit_pinned_override(self):
        def other(command, env):
            if command[-1] == '--version':
                return SimpleNamespace(returncode=0, stdout='codex-cli 0.165.0\n', stderr='')
            return self.command(command, env)
        self.assertFalse(self.invoke(run_command=other)['ok'])
        self.assertTrue(self.invoke(run_command=other, expected_version='0.165.0')['ok'])
        self.assertFalse(self.invoke(expected_version='latest')['ok'])

    def test_api_auth_or_cached_login_failure_not_ready(self):
        for message, code in (('Logged in using an API key: PRIVATE', 0), ('Not logged in', 1),
                              ('Logged in using ChatGPT\nPRIVATE', 0)):
            def auth(command, env):
                if command[-1] == '--version':
                    return self.command(command, env)
                return SimpleNamespace(returncode=code, stdout=message, stderr='')
            result = self.invoke(run_command=auth)
            self.assertFalse(result['ok'])
            self.assertNotIn('PRIVATE', json.dumps(result))

    def test_exception_diagnostics_are_not_leaked(self):
        def broken(command, env):
            raise RuntimeError('PRIVATE_SECRET https://private.invalid/?token=secret')
        result = self.invoke(run_command=broken)
        self.assertFalse(result['ok'])
        self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertNotIn('private.invalid', json.dumps(result))

    def test_storage_must_be_separate_children_of_declared_volume(self):
        for value in (self.temp.name, str(Path(self.temp.name).parent), self.env['CODEX_HOME']):
            self.env['WORKBENCH_RUNNER_STATE'] = value
            self.assertFalse(self.invoke()['ok'])

    def test_default_host_checks_do_not_claim_ephemeral_temp_is_a_volume(self):
        result = preflight(self.env, run_command=self.command, find_executable=lambda name: '/fixture/codex')
        self.assertFalse(result['ok'])
        self.assertFalse(result['storage']['mount_present'])

    def test_persistent_failure_gate_prevents_restart_from_claiming_ready(self):
        blocked = Path(self.env['WORKBENCH_RUNNER_STATE']) / 'blocked.json'
        blocked.write_text('PRIVATE FAILURE DETAILS ARE NOT READ', encoding='utf-8')
        for _ in range(2):
            result = self.invoke()
            self.assertFalse(result['ok'])
            self.assertFalse(result['eligible_to_start'])
            self.assertIn('EXECUTION_PAUSED_REQUIRES_REVIEW', [x['code'] for x in result['checks']])
            self.assertNotIn('PRIVATE FAILURE', json.dumps(result))
            self.assertTrue(blocked.exists())
        blocked.unlink()  # Explicit test recovery only; production never does this.
        self.assertTrue(self.invoke()['ok'])

    @unittest.skipIf(os.name == 'nt', 'POSIX mode and symlink guarantees')
    def test_private_modes_and_no_symlink_escape(self):
        code = Path(self.env['CODEX_HOME'])
        code.chmod(0o755)
        self.assertFalse(self.invoke()['ok'])
        code.chmod(0o700)
        target = Path(self.env['WORKBENCH_RUNNER_STATE'])
        target.rmdir()
        target.symlink_to(code, target_is_directory=True)
        self.assertFalse(self.invoke()['ok'])

    def test_output_never_contains_credentials_or_storage_paths(self):
        output = json.dumps(self.invoke())
        self.assertNotIn(self.env['WORKBENCH_RUNNER_SECRET'], output)
        self.assertNotIn(self.temp.name.replace('\\', '\\\\'), output)


if __name__ == '__main__':
    unittest.main()
