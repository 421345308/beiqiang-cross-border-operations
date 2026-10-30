"""Offline preview and explicit, optimistic single-source proposal application.

The local lock coordinates this tool only. Other editors must respect the shared
workspace's single-writer rule; byte rechecks cannot provide a filesystem CAS.
"""
from __future__ import annotations
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parents[3]
SOURCE_PATHS = frozenset((
    '00_总控台/当前状态.md', '00_总控台/全渠道增长总控.md',
    '04_客户开发/获客研究与送达率治理.md',
    '02_Alibaba运营/02_单品优化记录/BQ系列持续优化_2026-09-14/主推采购承接.md',
))

def normalize(value):
    return value.replace('\r\n', '\n').replace('\r', '\n')

def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()

def inside(root, path):
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError('Path escapes the project root')
    return resolved

def validate(p):
    if not isinstance(p, dict) or type(p.get('schema_version')) is not int or p['schema_version'] != 1:
        raise ValueError('Unsupported proposal schema_version')
    if not isinstance(p.get('run_id'), str) or not re.fullmatch('[0-9a-f]{32}', p['run_id']):
        raise ValueError('Invalid run_id')
    if p.get('status') != 'awaiting_review':
        raise ValueError('Proposal is not awaiting_review')
    if not isinstance(p.get('summary'), str) or not isinstance(p.get('next_steps'), list) or not all(isinstance(x,str) for x in p['next_steps']):
        raise ValueError('Invalid summary or next_steps')
    if not isinstance(p.get('changes'), list) or len(p['changes']) > 30:
        raise ValueError('Invalid changes')
    if p.get('source') in (None,'') and not p['changes']:
        if p.get('source_hash') is not None or p.get('source_version') is not None:
            raise ValueError('Source-free proposal has source metadata')
        return
    if not isinstance(p.get('source'),str) or p['source'] not in SOURCE_PATHS:
        raise ValueError('Source is outside SOURCE_PATHS')
    if not isinstance(p.get('source_hash'),str) or not re.fullmatch('[0-9a-f]{64}',p['source_hash']):
        raise ValueError('Invalid source_hash')
    if type(p.get('source_version')) is not int or p['source_version'] < 1:
        raise ValueError('Invalid source_version')
    for c in p['changes']:
        if not isinstance(c,dict) or any(not isinstance(c.get(k),str) for k in ('path','before','after','reason')):
            raise ValueError('Invalid change')
        if c['path'] != p['source']:
            raise ValueError('Cross-source change rejected')
        if not c['before'] or len(c['before']) > 12000 or len(c['after']) > 16000:
            raise ValueError('Replacement exceeds supported scope')

def patched(raw, changes):
    # Map normalized characters back to original character offsets, retaining all
    # untouched bytes, UTF-8 BOM, and even mixed newline styles.
    bom = b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b''
    original = raw[len(bom):].decode('utf-8')
    text = normalize(original)
    spans = []; staged = text
    for c in changes:
        before, after = normalize(c['before']), normalize(c['after'])
        if not before or text.count(before) != 1:
            raise ValueError('before must occur exactly once in original source')
        start = text.index(before); end = start + len(before)
        if any(start < b and end > a for a,b,_ in spans):
            raise ValueError('Overlapping replacements rejected')
        if staged.count(before) != 1:
            raise ValueError('Replacement becomes ambiguous after an earlier change')
        spans.append((start,end,after))
        staged = staged.replace(before,after,1)
    offsets = [0]; i = 0
    while i < len(original):
        i += 2 if original[i:i+2] == '\r\n' else 1
        offsets.append(i)
    result = original
    for start,end,after in sorted(spans, reverse=True):
        fragment = original[offsets[start]:offsets[end]]
        match = re.search(r'\r\n|\r|\n',fragment) or re.search(r'\r\n|\r|\n',original)
        newline = match.group() if match else '\n'
        result = result[:offsets[start]] + after.replace('\n',newline) + result[offsets[end]:]
    return bom + result.encode('utf-8')

def atomic_write(path, data):
    fd, name = tempfile.mkstemp(prefix='.'+path.name+'.', dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        if path.exists(): os.chmod(name,path.stat().st_mode)
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)

def review(p, root=ROOT, apply=False):
    validate(p)
    root = Path(root).resolve(strict=True)
    if not p.get('source'):
        if apply: raise ValueError('Read-only proposal has no source to apply')
        return {'status':'preview','run_id':p['run_id'],'summary':p['summary'],'diff':''}
    target = inside(root, root/p['source'])
    state = inside(root, root/'08_工具链/08_经营工作台/.local/proposal-review')
    receipt = inside(root,state/(p['run_id']+'.json'))
    fingerprint = digest(json.dumps(p,sort_keys=True,ensure_ascii=False,separators=(',',':')))
    def prepare():
        if inside(root,root/p['source']) != target: raise ValueError('Source path changed')
        raw = target.read_bytes()
        old_hash = digest(normalize(raw.decode('utf-8-sig')))
        if receipt.exists():
            saved = json.loads(receipt.read_text(encoding='utf-8'))
            if saved.get('proposal_hash') != fingerprint: raise ValueError('run_id already used for another proposal')
            if old_hash == saved['new_hash']: return raw,None,saved
            raise ValueError('Previously applied source has since changed')
        if old_hash != p['source_hash']: raise ValueError('Source hash conflict; obtain a fresh proposal')
        output = patched(raw,p['changes'])
        return raw,output,None
    def execute():
        raw,output,saved = prepare()
        if saved: return dict(saved,status='already_applied')
        result = {'status':'preview','run_id':p['run_id'],'path':p['source'],
                  'old_hash':p['source_hash'],'new_hash':digest(normalize(output.decode('utf-8-sig'))),
                  'source_version':p['source_version'],'proposal_hash':fingerprint}
        result['diff'] = ''.join(difflib.unified_diff(normalize(raw.decode('utf-8-sig')).splitlines(True),normalize(output.decode('utf-8-sig')).splitlines(True),fromfile=p['source'],tofile=p['source']))
        if not apply: return result
        if not p['changes']: raise ValueError('Read-only proposal has no changes to apply')
        if inside(root,root/p['source']) != target or target.read_bytes() != raw:
            raise ValueError('Source changed during review')
        atomic_write(target,output)
        result['status'] = 'applied'
        record = {k:v for k,v in result.items() if k != 'diff'}
        try: atomic_write(receipt,json.dumps(record,ensure_ascii=False,indent=2).encode('utf-8'))
        except OSError as error:
            raise RuntimeError('SOURCE WAS APPLIED but receipt could not be saved; inspect source before any retry') from error
        return result
    if not apply: return execute()
    state.mkdir(parents=True,exist_ok=True)
    lock = inside(root,state/'apply.lock')
    try: fd = os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError: raise ValueError('Another apply is active, or a stale apply.lock requires inspection')
    try:
        os.close(fd)
        return execute()
    finally: lock.unlink()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('proposal',type=Path)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--apply',action='store_true',help='Apply after local review; default only previews')
    args = parser.parse_args()
    try:
        proposal = json.loads(args.proposal.read_text(encoding='utf-8-sig'))
        print(json.dumps(review(proposal,args.root,args.apply),ensure_ascii=False,indent=2))
    except (ValueError,OSError,RuntimeError) as error:
        parser.exit(1,str(error)+'\n')

if __name__ == '__main__': main()
