"""Explicit Dot metadata observations. Never an execution queue or chat store."""
import json
from datetime import datetime, timezone
from pathlib import Path
from workspaces import WorkspaceConflict

SOURCE = '由 Dot 导入的一次快照，未自动更新'
MAX_THREADS = 500
STALE_SECONDS = 600
FIELDS = {'id','kind','projectId','hostId','status','cwd','updatedAt','title'}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('观测时间必须为带时区的 ISO 时间。')
    try:
        result = datetime.fromisoformat(value.replace('Z','+00:00'))
        if result.tzinfo is None: raise ValueError()
        return result
    except ValueError:
        raise ValueError('观测时间必须为带时区的 ISO 时间。') from None


def forbidden_controls(value, *, title=False):
    # Titles are displayed with DOM textContent, never as HTML or shell input.
    # Preserve ordinary title whitespace while rejecting terminal/bidi controls.
    return any((ord(c)<32 or 0x7f<=ord(c)<=0x9f or c in '\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069')
               and not (title and c in '\r\n\t') for c in value)


class DesktopSnapshot:
    def __init__(self, app):
        self.app = app
        self.root = Path(app.root).resolve()
        with app.lock:
            app.db.execute('CREATE TABLE IF NOT EXISTS desktop_observation (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL)')
            app.db.commit()

    def _stored(self):
        with self.app.lock:
            row = self.app.db.execute('SELECT data FROM desktop_observation WHERE id=1').fetchone()
        return json.loads(row[0]) if row else None

    def import_snapshot(self, payload):
        if not isinstance(payload, dict) or set(payload)-{'observed_at','status','truncated','threads'}:
            raise ValueError('只接收正式工具的会话元信息快照。')
        observed = timestamp(payload.get('observed_at'))
        if (observed - datetime.now(timezone.utc)).total_seconds() > 300:
            raise ValueError('观测时间不能在未来。')
        state = payload.get('status')
        if state not in ('ok','unavailable') or type(payload.get('truncated')) is not bool:
            raise ValueError('快照来源状态或截断标记无效。')
        raw = payload.get('threads')
        if not isinstance(raw, list) or len(raw)>MAX_THREADS or (state=='unavailable' and raw):
            raise ValueError('会话列表最多500条；来源不可用时不得附带新列表。')
        threads, seen, excluded = [], set(), 0
        for item in raw:
            if not isinstance(item, dict) or set(item)-FIELDS:
                raise ValueError('禁止导入摘要、消息或历史正文。')
            for key in ('id','hostId','cwd'):
                if not isinstance(item.get(key),str) or not item[key] or len(item[key])>2000 or forbidden_controls(item[key]):
                    raise ValueError('会话标识或工作区路径无效。')
            path_text = item['cwd']
            if (item['hostId']=='durable' and path_text.startswith('/tmp/codex-cloud-agent-')
                    and any(part in path_text for part in ('/app_servers/threads/', '/app_servers/thread_service/'))
                    and path_text.count('/workspace/')==1):
                path_text = path_text.split('/workspace/',1)[1]
            cwd = Path(path_text)
            if not cwd.is_absolute():
                excluded += 1
                continue
            try:
                if not cwd.resolve().is_relative_to(self.root):
                    excluded += 1
                    continue
            except (OSError, ValueError):
                excluded += 1
                continue
            clean = {}
            for key,value in item.items():
                if key=='updatedAt' and type(value) in (int,float):
                    try: value = datetime.fromtimestamp(value,timezone.utc).isoformat()
                    except (ValueError,OverflowError,OSError): raise ValueError('源更新时间无效。') from None
                if value is not None and (not isinstance(value,str) or len(value)>2000 or forbidden_controls(value, title=key=='title')):
                    raise ValueError('会话元信息必须为有限文本。')
                clean[key] = value
            if path_text != item['cwd']: clean['workspace_cwd'] = str(cwd.resolve())
            identity = (item['hostId'],item['id'])
            if identity in seen: raise ValueError('同一主机的会话标识重复。')
            seen.add(identity)
            threads.append(clean)
        with self.app.lock:
            if self.app.db.in_transaction:
                raise RuntimeError('桌面快照写入不能嵌套事务。')
            self.app.db.execute('BEGIN IMMEDIATE')
            try:
                old = self._stored()
                if old and observed < timestamp(old['observed_at']):
                    raise WorkspaceConflict('已有更新的桌面观测，请重新读取后导入。')
                value = {'observed_at':observed.isoformat(),'imported_at':stamp(),'status':state,
                         'truncated':payload['truncated'],'threads':threads,'excluded_count':excluded}
                if state == 'unavailable' and old:
                    value.update(threads=old['threads'],snapshot_observed_at=old.get('snapshot_observed_at') or old['observed_at'],
                                 truncated=old['truncated'])
                else:
                    value['snapshot_observed_at'] = value['observed_at']
                self.app.db.execute('INSERT OR REPLACE INTO desktop_observation VALUES (1,?)',(json.dumps(value,ensure_ascii=False),))
                self.app.db.commit()
            except BaseException:
                self.app.db.rollback()
                raise
        return self.read()

    def read(self):
        value = self._stored()
        if not value:
            return {'state':'missing','source':SOURCE,'threads':[], 'observed_at':None,
                    'automatic_refresh':False,'reason':'尚未导入；本机后台没有持续读取桌面会话的连接器。'}
        age = max(0,int((datetime.now(timezone.utc)-timestamp(value['snapshot_observed_at'])).total_seconds()))
        return {**value,'state':'unavailable' if value['status']=='unavailable' else 'stale' if age>=STALE_SECONDS else 'ok',
                'stale':age>=STALE_SECONDS or value['status']=='unavailable','age_seconds':age,
                'automatic_refresh':False,'source':SOURCE,'reason':'只读元信息快照；不包含会话正文，也不代表实时执行队列。'}


if __name__ == '__main__':
    import argparse
    import sqlite3
    import threading
    from types import SimpleNamespace
    parser = argparse.ArgumentParser(description=SOURCE)
    parser.add_argument('--root', required=True)
    parser.add_argument('--state', required=True, help='Existing workbench state directory')
    parser.add_argument('--input', help='Explicit JSON metadata snapshot; omitted reads current observation')
    args = parser.parse_args()
    database = Path(args.state)/'runs.sqlite3'
    if not database.is_file(): parser.error('工作台数据库不存在。')
    connection = sqlite3.connect(database, timeout=10)
    service = DesktopSnapshot(SimpleNamespace(root=Path(args.root), db=connection, lock=threading.RLock()))
    try:
        import sys
        raw = sys.stdin.readline(2_000_001) if args.input=='-' else Path(args.input).read_text(encoding='utf-8-sig') if args.input else None
        if raw is not None and len(raw)>2000000: parser.error('快照超过大小上限。')
        result = service.import_snapshot(json.loads(raw)) if raw is not None else service.read()
        if raw is not None: result = {**{k:v for k,v in result.items() if k!='threads'}, 'thread_count':len(result['threads'])}
        print(json.dumps(result,ensure_ascii=False))
    finally:
        connection.close()
