#!/bin/sh
set -eu
umask 077

# Never chown recursively, follow a mounted symlink, or alter the user's HOME.
python3 - <<'PY'
import os
from pathlib import Path
import pwd
root = Path('/var/data')
if root.is_symlink() or not root.is_dir() or not os.path.ismount(root):
    raise SystemExit('Worker startup blocked: persistent /var/data mount required')
owner = pwd.getpwnam('node')
for name in ('codex', 'runner'):
    target = root / name
    if target.is_symlink() or (target.exists() and not target.is_dir()):
        raise SystemExit('Worker startup blocked: private directory is not regular')
    target.mkdir(mode=0o700, exist_ok=True)
    os.chown(target, owner.pw_uid, owner.pw_gid)
    os.chmod(target, 0o700)
PY

if [ "${RUNNER_ENABLED:-false}" = "false" ]; then
    printf '%s\n' 'Worker disabled for login/setup; no heartbeat, claim, or model call.'
    exec gosu node sleep infinity
fi
if [ "${RUNNER_ENABLED:-}" != "true" ]; then
    printf '%s\n' 'Worker startup blocked: RUNNER_ENABLED must be true or false.' >&2
    exit 1
fi
# The existing runner performs startup preflight before its first heartbeat.
exec gosu node python3 /opt/worker/runner.py
