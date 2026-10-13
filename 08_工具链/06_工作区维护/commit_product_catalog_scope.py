"""Create a reviewable product-only Git branch without touching the shared index.

Uses a separate temporary index and an explicit file manifest. No push, reset,
force update or customer/credential export. Caller reviews and pushes normally.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True)
    parser.add_argument('--branch', default='codex/product-catalog-sync')
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--message', required=True)
    args = parser.parse_args()
    if not args.branch.startswith('codex/'):
        raise ValueError('Use a dedicated Codex branch')
    files = json.loads(Path(args.manifest).read_text(encoding='utf-8'))['files']
    for name in files:
        path = Path(name)
        if path.is_absolute() or '..' in path.parts or not (ROOT/path).is_file():
            raise ValueError('Invalid export path')
        if any(x in name for x in ['04_客户开发/', '.config/', '.aws/', '.workbuddy/', '.codex/', 'alibaba-openapi.json']):
            raise ValueError('Sensitive or unrelated scope rejected')
        if path.suffix.lower() not in {'.md','.py','.json','.html','.csv','.gitignore'}:
            raise ValueError('Media/credentials/dependencies are not exported')
    def git(*cmd, env=None, input=None):
        return subprocess.check_output(['git',*cmd],cwd=ROOT,env=env,input=input)
    base = git('rev-parse',args.base+'^{commit}').decode().strip()
    ref = 'refs/heads/'+args.branch
    exists = subprocess.run(['git','show-ref','--verify','--quiet',ref],cwd=ROOT).returncode == 0
    if exists:
        existing = git('rev-parse',ref).decode().strip()
        if existing != base:
            raise ValueError('Branch exists at another base; no overwrite')
    with tempfile.TemporaryDirectory(prefix='beiqiang-product-index-') as tmp:
        env = os.environ.copy()
        env['GIT_INDEX_FILE'] = str(Path(tmp)/'index')
        git('read-tree',base,env=env)
        git('add','--',*files,env=env)
        git('diff','--cached','--check',env=env)
        names = git('diff','--cached','--name-only','-z',base,env=env).decode().split('\0')
        if set(x for x in names if x) - set(files):
            raise ValueError('Export unexpectedly includes another task')
        tree = git('write-tree',env=env).decode().strip()
        commit = git('commit-tree',tree,'-p',base,input=(args.message+'\n').encode()).decode().strip()
        git('update-ref',ref,commit,base if exists else '0'*40)
        print(json.dumps({'branch':args.branch,'base':base,'commit':commit,'files_changed':len([n for n in names if n]),'manifest':args.manifest},ensure_ascii=False))


if __name__ == '__main__':
    main()
