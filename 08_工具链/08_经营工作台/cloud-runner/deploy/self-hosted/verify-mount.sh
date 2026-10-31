#!/bin/bash
# Run on target before login/start. Uses exactly the service's bind namespace.
set -euo pipefail
[[ $EUID == 0 ]] || exit 1
runner_release=$(cd -- "$(dirname -- "$0")/../.." && pwd -P)
systemd-run --quiet --wait --pipe --collect --unit="beiqiang-mount-check-$$" \
  -p User=beiqiang-runner -p Group=beiqiang-runner \
  -p "WorkingDirectory=$runner_release" \
  -p BindPaths=/var/lib/beiqiang/runner:/var/data \
  -p ProtectSystem=strict -p ReadWritePaths=/var/data \
  /usr/bin/python3 -c 'import os,tempfile; from pathlib import Path; from preflight import is_mountpoint; root=Path("/var/data"); assert os.geteuid()!=0 and is_mountpoint(root,expected_root="/var/lib/beiqiang/runner",require_persistent=True) and not root.is_symlink(); paths=[root/"codex",root/"state"]; assert all(p.is_dir() and not p.is_symlink() and p.stat().st_uid==os.geteuid() and not p.stat().st_mode&0o077 for p in paths); [(lambda fd,name:(os.close(fd),os.unlink(name)))(*tempfile.mkstemp(dir=p)) for p in paths]; print("PASS: kernel mountinfo confirms exact persistent bind source, nonroot ownership, private permissions and writes")'
