"""Read-only Alibaba catalog observation; original product records stay authoritative.

This module is a cache and comparison of the existing official API, not a
second editable product store. It never invokes a write or refreshes a token.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile

from connectors.alibaba import adapter

INTERVAL = timedelta(hours=6)
CHANNEL = '02_Alibaba运营/05_扩品工程/数据/国际站商品.json'


def timestamp():
    return datetime.now(timezone.utc)


def parsed_time(value):
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def compact(row, id_key='id'):
    identity = str(row.get(id_key) or '')
    if not re.fullmatch(r'\d{1,32}', identity):
        raise ValueError('INVALID_PRODUCT_ID')
    return {'id': identity, 'status': row.get('status') if isinstance(row.get('status'), str) else None,
            'display': row.get('display') if isinstance(row.get('display'), str) else None}


class CatalogMonitor:
    def __init__(self, root, state, *, fetch=None, clock=timestamp):
        self.root, self.state, self.clock = Path(root).resolve(), Path(state), clock
        self.folder = self.state / 'alibaba'
        self.path = self.folder / 'catalog-monitor.json'
        self.fetch = fetch

    def revision(self):
        def mtime(path):
            try: return path.stat().st_mtime_ns
            except OSError: return 0
        return str(mtime(self.path)) + ':' + str(mtime(self.root / CHANNEL))

    @contextmanager
    def _locked(self):
        self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock = self.folder / '.catalog-monitor.lock'
        if lock.is_symlink(): raise ValueError('INVALID_LOCK')
        with lock.open('a+b') as stream:
            if stream.tell() == 0: stream.write(b'0'); stream.flush()
            stream.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                yield False
                return
            try: yield True
            finally:
                stream.seek(0)
                if os.name == 'nt': msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else: fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _read(self):
        if self.path.is_symlink(): raise ValueError('INVALID_CACHE')
        if not self.path.exists(): return {}
        value = json.loads(self.path.read_text(encoding='utf-8'))
        if not isinstance(value, dict) or value.get('version') != 1 or not isinstance(value.get('records'), list):
            raise ValueError('INVALID_CACHE')
        try:
            identities = [compact(row)['id'] for row in value['records']]
            if len(set(identities)) != len(identities): raise ValueError('INVALID_CACHE')
        except (AttributeError, TypeError, ValueError): raise ValueError('INVALID_CACHE') from None
        return value

    def _write(self, value):
        if self.path.is_symlink(): raise ValueError('INVALID_CACHE')
        fd, temp = tempfile.mkstemp(prefix='.catalog-', dir=self.folder)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as out:
                json.dump(value, out, ensure_ascii=False); out.flush(); os.fsync(out.fileno())
            os.replace(temp, self.path)
        finally: Path(temp).unlink(missing_ok=True)

    def seed(self, snapshot_path):
        """Reuse an existing, complete official readback without another API call."""
        data = json.loads(Path(snapshot_path).read_text(encoding='utf-8-sig'))
        rows = data.get('records') if isinstance(data, dict) else None
        at = parsed_time(data.get('collected_at_utc')) if isinstance(data, dict) else None
        if not at or data.get('complete') is not True or not isinstance(rows, list): raise ValueError('INVALID_BASELINE')
        records = [compact(row, 'platform_id') for row in rows if isinstance(row, dict)]
        if len(records) != len(rows) or len(records) != data.get('platform_total') or len({r['id'] for r in records}) != len(records):
            raise ValueError('INCOMPLETE_BASELINE')
        with self._locked() as acquired:
            if not acquired: return {'state': 'busy'}
            if self.path.exists(): return {'state': 'already_present'}
            value = {'version': 1, 'state': 'ready', 'last_attempt_at': at.isoformat(),
                     'last_success_at': at.isoformat(), 'pages': data.get('pages'),
                     'records': records, 'changes': None, 'error': None}
            self._write(value)
        return self.status()

    def collect(self, *, force=False):
        with self._locked() as acquired:
            if not acquired: return {'state': 'busy'}
            previous = self._read()
            attempted = parsed_time(previous.get('last_attempt_at'))
            now = self.clock()
            due = timedelta(hours=1) if previous.get('state') == 'error' else INTERVAL
            if not force and attempted and timedelta(0) <= now - attempted < due:
                return self.status()
            started = now.isoformat(); rows = []; ids = set(); total = None; page = 1
            old = {r['id']: r for r in previous.get('records', [])}
            client = adapter.ExistingClient() if self.fetch is None else None
            fetch = self.fetch or adapter.execute
            try:
                while page <= 100:
                    response = fetch('products', client=client, page=page, page_size=50)
                    if not isinstance(response, dict) or response.get('ok') is not True:
                        code = ((response or {}).get('error') or {}).get('code') if isinstance(response, dict) else None
                        raise ValueError(code if isinstance(code, str) and re.fullmatch(r'[A-Z_]{1,80}', code) else 'READ_FAILED')
                    pagination, data = response.get('pagination'), response.get('data')
                    if not isinstance(pagination, dict) or not isinstance(data, list) or pagination.get('page') != page:
                        raise ValueError('INVALID_PAGINATION')
                    if type(pagination.get('total')) is not int or pagination['total'] < 0:
                        raise ValueError('INVALID_TOTAL')
                    if total is None: total = pagination['total']
                    if total != pagination['total']: raise ValueError('TOTAL_CHANGED')
                    for raw in data:
                        row = compact(raw)
                        if row['id'] in ids: raise ValueError('DUPLICATE_ID')
                        ids.add(row['id']); rows.append(row)
                    # Alibaba can report the final page's actual row count as
                    # page_size, making the adapter's hasMore overestimate.
                    # A complete set of unique IDs matching total is decisive.
                    if len(rows) > total: raise ValueError('INCOMPLETE_CATALOG')
                    if len(rows) == total: break
                    if pagination.get('hasMore') is False: break
                    if pagination.get('hasMore') is not True or pagination.get('nextPage') != page + 1:
                        raise ValueError('INVALID_PAGINATION')
                    page += 1
                else: raise ValueError('PAGE_LIMIT')
                if len(rows) != total: raise ValueError('INCOMPLETE_CATALOG')
                current = {r['id']: r for r in rows}
                changes = None if not previous.get('last_success_at') else {
                    'added': sorted(current.keys() - old.keys()),
                    'not_seen': sorted(old.keys() - current.keys()),
                    'status_or_display': [{'id': key, 'before': old[key], 'after': current[key]}
                                          for key in sorted(current.keys() & old.keys()) if current[key] != old[key]]}
                self._write({'version': 1, 'state': 'ready', 'last_attempt_at': started,
                             'last_success_at': self.clock().isoformat(), 'pages': page,
                             'records': rows, 'changes': changes, 'error': None})
            except Exception as error:
                code = str(error) if isinstance(error, ValueError) and re.fullmatch(r'[A-Z_]{1,80}', str(error)) else 'READ_FAILED'
                self._write({**previous, 'version': 1, 'records': previous.get('records', []),
                             'state': 'error', 'last_attempt_at': started, 'error': {'code': code}})
            return self.status()

    def status(self):
        try: value = self._read()
        except (OSError, ValueError, TypeError): return {'state': 'error', 'error': {'code': 'INVALID_CACHE'}, 'stale': True}
        if not value: return {'state': 'not_loaded', 'stale': True, 'last_success_at': None}
        records = value['records']; at = parsed_time(value.get('last_success_at'))
        if at is None:
            return {'state':value.get('state'), 'error':value.get('error'), 'stale':True,
                    'last_attempt_at':value.get('last_attempt_at'), 'last_success_at':None,
                    'total':None, 'comparison':None, 'changes':None}
        stale = at is None or not timedelta(0) <= self.clock() - at <= INTERVAL + timedelta(hours=1)
        latest = {r['id']: r for r in records}; comparison = None; observed = {}
        try:
            local = json.loads((self.root / CHANNEL).read_text(encoding='utf-8-sig'))['listings']
            if not isinstance(local, list): raise ValueError('invalid')
            entries = [row for row in local if isinstance(row, dict) and row.get('id') is not None]
            counts = Counter(str(row['id']) for row in entries)
            observed = {str(row['id']): row for row in entries if counts[str(row['id'])] == 1}
            ambiguous = {key for key, count in counts.items() if count > 1}
            different = []
            for identity in sorted(observed.keys() & latest.keys()):
                fields = observed[identity].get('current_platform_fields') or {}; live = latest[identity]
                changed = [key for key in ('status','display') if fields.get(key) is not None and live.get(key) is not None and str(fields[key]) != live[key]]
                if changed:
                    different.append({'id':identity, 'product_id':observed[identity].get('product_id'),
                                      'model':fields.get('model'), 'fields':changed,
                                      'local':{key:fields.get(key) for key in changed},
                                      'platform':{key:live.get(key) for key in changed}})
            comparison = {'matched':len(observed.keys() & latest.keys()), 'different':different,
                          'local_not_seen':len(set(counts) - latest.keys()), 'platform_unmatched':len(latest.keys() - set(counts)),
                          'ambiguous_ids':len(ambiguous & latest.keys())}
        except (OSError, KeyError, TypeError, ValueError, AttributeError): pass
        review_items=[]
        for row in records:
            if row.get('status')=='tbd' or row.get('status') not in ('approved','tbd','new','modified','sketch') or row.get('display') not in ('Y','N'):
                local=observed.get(row['id']) or {};fields=local.get('current_platform_fields') or {}
                if not isinstance(fields,dict):fields={}
                review_items.append({**row,'product_id':local.get('product_id'),'model':fields.get('model')})
        return {'state':value.get('state'), 'error':value.get('error'), 'stale':stale,
                'last_attempt_at':value.get('last_attempt_at'), 'last_success_at':value.get('last_success_at'),
                'pages':value.get('pages'), 'total':len(records),
                'review_required':sum(row.get('status')=='tbd' for row in records),
                'unknown_state':sum(row.get('status') not in ('approved','tbd','new','modified','sketch') or row.get('display') not in ('Y','N') for row in records),
                'review_items':review_items,
                'changes':value.get('changes'), 'comparison':comparison,
                'scope':'官方商品列表只读快照；未出现不等于下架，本机离线时计划任务不会运行。'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--seed',type=Path)
    parser.add_argument('--force',action='store_true')
    args=parser.parse_args()
    monitor=CatalogMonitor(args.root,args.root/'08_工具链/08_经营工作台/.local')
    result=monitor.seed(args.seed) if args.seed else monitor.collect(force=args.force)
    # No product details, signed URLs or credentials go into scheduler output.
    if sys.stdout is not None:
        print(json.dumps({key:result.get(key) for key in ('state','last_attempt_at','last_success_at','total','stale','error')},ensure_ascii=False))
    return 0 if result.get('state') in ('ready','already_present','busy') else 1


if __name__=='__main__': raise SystemExit(main())
