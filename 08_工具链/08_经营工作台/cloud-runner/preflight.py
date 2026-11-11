"""Private worker startup checks. Never claims work or invokes a model."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

MODEL = 'gpt-6.1-sol'
DEFAULT_CODEX_VERSION = '0.166.0'
QUEUE_URL = 'https://www.beiqiang.online/api/workbench-runner'


def is_mountpoint(path, *, mountinfo=None, expected_root=None, require_persistent=False):
    """Recognize exact Linux mount entries, including same-device bind mounts.

    os.path.ismount compares devices/inodes and misses same-filesystem binds.
    mountinfo is kernel evidence for this process's own mount namespace.
    An injected text fixture is used only by unit tests.
    """
    target = os.fspath(Path(path).resolve())
    if mountinfo is None:
        try:
            mountinfo = Path('/proc/self/mountinfo').read_text(encoding='utf-8')
        except OSError:
            return not require_persistent and os.path.ismount(path)
    for line in mountinfo.splitlines():
        fields = line.split()
        if len(fields) < 10 or '-' not in fields[6:]:
            continue
        decode = lambda value: re.sub(r'\\([0-7]{3})', lambda match: chr(int(match[1], 8)), value)
        point = decode(fields[4])
        if point == target:
            separator = fields.index('-', 6)
            if len(fields) <= separator + 3:
                continue
            filesystem = fields[separator + 1]
            if require_persistent and filesystem in ('tmpfs', 'ramfs', 'overlay', 'proc', 'sysfs', 'devtmpfs', 'cgroup', 'cgroup2'):
                continue
            if expected_root is not None and decode(fields[3]) != expected_root:
                continue
            return True
    return False


def _run(command, env):
    return subprocess.run(command, env=env, capture_output=True, text=True,
                          encoding='utf-8', errors='replace', timeout=20, check=False)


def read_api_credential(env):
    """Read only the systemd-provided credential; never include its value in errors."""
    directory = Path(env.get('CREDENTIALS_DIRECTORY', ''))
    if not directory.is_absolute() or directory.is_symlink() or not directory.is_dir():
        raise ValueError('Systemd credential directory is unavailable')
    path = directory / 'openai-api-key'
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
        raise ValueError('Systemd API credential is unavailable')
    key = path.read_text(encoding='ascii').strip()
    if not re.fullmatch(r'sk-[A-Za-z0-9_-]{20,}', key):
        raise ValueError('Systemd API credential has an invalid format')
    return key


def preflight(env=None, *, expected_version=None, run_command=None, find_executable=None,
              require_non_root=True, require_mount=True):
    """Return safe evidence; ok means eligible to start, not live/model readiness.

    Tests inject run_command/find_executable and explicitly disable host checks.
    Production callers keep the defaults. No configuration/auth files are read.
    """
    env = dict(os.environ if env is None else env)
    expected_version = expected_version or env.get('WORKBENCH_CODEX_VERSION', DEFAULT_CODEX_VERSION)
    command = run_command or _run
    find = find_executable or shutil.which
    result = {'ok': False, 'eligible_to_start': False, 'model': MODEL,
              'observed_at': datetime.now(timezone.utc).isoformat(),
              'auth': {'method': None, 'authenticated': False},
              'cli': {'available': False, 'version': None, 'expected_version': None},
              'storage': {'writable': False, 'mount_present': False, 'persistence_verified': False},
              'queue': {'endpoint_matches': False, 'secret_configured': False, 'connection_verified': False},
              'model_access_verified': False, 'checks': []}

    def check(name, ok, code):
        result['checks'].append({'name': name, 'ok': bool(ok), 'code': 'OK' if ok else code})
        return bool(ok)

    engine = env.get('WORKBENCH_RUNNER_ENGINE', 'codex')
    engine_ok = check('runner_engine', engine in ('codex', 'responses'), 'INVALID_RUNNER_ENGINE')
    result['engine'] = engine if engine_ok else None
    if engine == 'codex':
        if not check('cli_version_policy', isinstance(expected_version, str) and bool(re.fullmatch(
                r'\d+\.\d+\.\d+(?:-[A-Za-z0-9.]+)?', expected_version)), 'INVALID_EXPECTED_VERSION'):
            return result
        result['cli']['expected_version'] = expected_version
    result['queue']['endpoint_matches'] = env.get('WORKBENCH_RUNNER_URL') == QUEUE_URL
    check('queue_endpoint', result['queue']['endpoint_matches'], 'UNEXPECTED_QUEUE_ENDPOINT')
    secret = env.get('WORKBENCH_RUNNER_SECRET', '')
    result['queue']['secret_configured'] = len(secret.encode()) >= 32 and bool(secret.strip()) and not any(c in secret for c in '\r\n')
    check('queue_secret', result['queue']['secret_configured'], 'MISSING_QUEUE_SECRET')
    # The configured plan is explicit: inherited credentials/provider overrides never
    # silently replace it, including when API authentication is selected.
    auth_method = env.get('WORKBENCH_RUNNER_AUTH', 'chatgpt')
    auth_method_ok = check('auth_method', auth_method in ('chatgpt', 'api'), 'INVALID_AUTH_METHOD')
    check('engine_auth', engine != 'responses' or auth_method == 'api', 'RESPONSES_API_AUTH_REQUIRED')
    forbidden = ('OPENAI_API_KEY', 'CODEX_API_KEY', 'CODEX_ACCESS_TOKEN', 'OPENAI_BASE_URL',
                 'AZURE_OPENAI_ENDPOINT', 'CODEX_OSS_BASE_URL')
    auth_env_ok = not any(env.get(key) for key in forbidden)
    check('auth_environment', auth_env_ok, 'UNEXPECTED_AUTH_OR_PROVIDER_OVERRIDE')
    if auth_method_ok and auth_method == 'api' and auth_env_ok:
        try:
            read_api_credential(env)
            # Existence/format is not proof of API authorization or model access.
            result['auth'] = {'method': 'api', 'authenticated': False, 'credential_configured': True}
            check('api_credential', True, '')
        except (OSError, UnicodeError, ValueError):
            check('api_credential', False, 'API_CREDENTIAL_REQUIRED')
    check('runtime_user', not require_non_root or (hasattr(os, 'geteuid') and os.geteuid() != 0), 'NON_ROOT_POSIX_USER_REQUIRED')

    try:
        raw_root = Path(env.get('WORKBENCH_RUNNER_PERSISTENT_ROOT', '/var/data'))
        raw_code = Path(env.get('CODEX_HOME', ''))
        raw_state = Path(env.get('WORKBENCH_RUNNER_STATE', ''))
        paths = (raw_root, raw_code, raw_state)
        valid = all(p.is_absolute() and p.is_dir() and not p.is_symlink() for p in paths)
        root, code, state = (p.resolve() for p in paths)
        valid = valid and root != Path(root.anchor) and root in code.parents and root in state.parents
        valid = valid and code != state and code not in state.parents and state not in code.parents
        # No intermediate symlink may redirect the declared credential/state path.
        for p in (raw_code, raw_state):
            valid = valid and not any(parent.is_symlink() for parent in [p, *p.parents])
        # A persisted execution fault remains paused across provider restarts.
        # Only explicit recovery removes it; never inspect potentially private text.
        blocked = state / 'blocked.json'
        check('execution_pause', not blocked.exists() and not blocked.is_symlink(), 'EXECUTION_PAUSED_REQUIRES_REVIEW')
        # A crash or lost claim response must be reconciled before another claim.
        pending = [state / 'claiming.json', state / 'active.json']
        check('execution_recovery', not any(p.exists() or p.is_symlink() for p in pending), 'EXECUTION_OUTCOME_REQUIRES_REVIEW')
        if os.name != 'nt':
            valid = valid and all(not (p.stat().st_mode & 0o077) and p.stat().st_uid == os.geteuid() for p in (code, state))
        check('storage_paths', valid, 'PRIVATE_STORAGE_PATHS_REQUIRED')
        mounted = is_mountpoint(root, expected_root=env.get('WORKBENCH_RUNNER_BIND_SOURCE'), require_persistent=True)
        result['storage']['mount_present'] = mounted
        check('persistent_mount', mounted or not require_mount, 'PERSISTENT_MOUNT_REQUIRED')
        if valid:
            for directory in (code, state):
                fd, name = tempfile.mkstemp(prefix='.preflight-', dir=directory)
                os.close(fd)
                os.unlink(name)
            result['storage']['writable'] = True
        check('storage_writable', result['storage']['writable'], 'STORAGE_NOT_WRITABLE')
    except (OSError, ValueError, RuntimeError):
        check('storage_writable', False, 'STORAGE_NOT_WRITABLE')

    executable = None
    if engine == 'codex':
        try:
            executable = find('codex', path=env.get('PATH')) if find_executable is None else find('codex')
        except Exception:
            executable = None
        result['cli']['available'] = bool(executable)
        check('cli_path', bool(executable), 'CODEX_NOT_ON_PATH')
    if engine == 'codex' and executable:
        try:
            version = command([executable, '--version'], env)
            matched = re.fullmatch(r'codex-cli (\d+\.\d+\.\d+(?:-[A-Za-z0-9.]+)?)\s*', version.stdout or '')
            actual = matched.group(1) if matched else None
            result['cli']['version'] = actual
            check('cli_version', version.returncode == 0 and actual == expected_version, 'CODEX_VERSION_MISMATCH')
        except Exception:
            check('cli_version', False, 'CODEX_VERSION_CHECK_FAILED')
        if auth_method_ok and auth_method == 'chatgpt' and auth_env_ok:
            try:
                auth = command([executable, '-c', 'forced_login_method="chatgpt"', 'login', 'status'], env)
                # CLI currently emits this fixed status on stderr. Preserve neither stream.
                message = ((auth.stdout or '') + '\n' + (auth.stderr or '')).strip()
                authenticated = auth.returncode == 0 and message == 'Logged in using ChatGPT'
                result['auth'] = {'method': 'chatgpt' if authenticated else None, 'authenticated': authenticated}
                check('chatgpt_auth', authenticated, 'CHATGPT_LOGIN_REQUIRED')
            except Exception:
                check('chatgpt_auth', False, 'CHATGPT_STATUS_CHECK_FAILED')
    result['ok'] = all(item['ok'] for item in result['checks'])
    result['eligible_to_start'] = result['ok']
    return result


def claim_reconciliation_eligible(result, state):
    """Allow only a pending claim to reach the runner's read-only reconciliation."""
    failed = [check for check in result.get('checks', []) if not check.get('ok')]
    if not failed or any(check.get('name') != 'execution_recovery'
                         or check.get('code') != 'EXECUTION_OUTCOME_REQUIRES_REVIEW' for check in failed):
        return False
    try:
        state = Path(state)
        claiming = state / 'claiming.json'
        if claiming.is_symlink() or not claiming.is_file():
            return False
        return not any((state/name).exists() or (state/name).is_symlink() for name in ('active.json','blocked.json'))
    except (OSError, ValueError, TypeError):
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-codex-version')
    parser.add_argument('--allow-claim-reconciliation', action='store_true',
                        help='permit only read-only reconciliation of a pending claim; not execution readiness')
    args = parser.parse_args(argv)
    value = preflight(expected_version=args.expected_codex_version)
    eligible = bool(args.allow_claim_reconciliation and not value['ok']
                    and claim_reconciliation_eligible(value, os.environ.get('WORKBENCH_RUNNER_STATE', '')))
    if args.allow_claim_reconciliation:
        value['claim_reconciliation_eligible'] = eligible
    print(json.dumps(value, ensure_ascii=False))
    return 0 if value['ok'] or eligible else 1


if __name__ == '__main__':
    raise SystemExit(main())
