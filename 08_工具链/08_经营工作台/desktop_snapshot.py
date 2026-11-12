"""Explicit Dot metadata observations. Never an execution queue or chat store."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from workspaces import WorkspaceConflict

SOURCE = '由 Dot 导入的一次快照，未自动更新'
MAX_THREADS = 500
STALE_SECONDS = 600
FIELDS = {'id','kind','projectId','hostId','status','cwd','updatedAt','title'}
INDIVIDUAL_TOOLS = {'mcp__codex_app__read_thread','mcp__codex_app__wait_threads'}
INDIVIDUAL_FIELDS = {'status','updatedAt'}
WORKSTREAMS = {'tools','alibaba','website','outreach','domestic','creation'}
MAX_LINK_HISTORY = 100


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


def individual_key(host_id, thread_id):
    # JSON tuple encoding is unambiguous even if an ID contains punctuation.
    return json.dumps([host_id,thread_id],ensure_ascii=False,separators=(',',':'))


def individual_metadata(raw):
    if not isinstance(raw,dict) or set(raw)-INDIVIDUAL_FIELDS:
        raise ValueError('单条观测只接收状态和来源更新时间。')
    status = raw.get('status')
    if not isinstance(status,str) or not status or len(status)>2000 or forbidden_controls(status):
        raise ValueError('单条观测必须提供实际状态。')
    value = {'status':status}
    if 'updatedAt' in raw:
        updated = raw['updatedAt']
        if type(updated) in (int,float):
            try: updated = datetime.fromtimestamp(updated,timezone.utc).isoformat()
            except (ValueError,OverflowError,OSError): raise ValueError('源更新时间无效。') from None
        if updated is not None:
            if not isinstance(updated,str) or len(updated)>2000 or forbidden_controls(updated):
                raise ValueError('源更新时间无效。')
            value['updatedAt'] = timestamp(updated).isoformat()
    return value


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
        incomplete = state == 'ok' and payload['truncated']
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
                value = {'observed_at':observed.isoformat(),'imported_at':stamp(),
                         'status':'unavailable' if incomplete else state,
                         'truncated':payload['truncated'],'attempt_truncated':incomplete,
                         'threads':threads,'excluded_count':excluded}
                if (state == 'unavailable' or incomplete) and old:
                    value.update(threads=old['threads'],snapshot_observed_at=old.get('snapshot_observed_at') or old['observed_at'],
                                 truncated=old['truncated'])
                elif incomplete:
                    value.update(threads=[],snapshot_observed_at=value['observed_at'])
                else:
                    value['snapshot_observed_at'] = value['observed_at']
                previous = old.get('individual_observations',{}) if old else {}
                value['workstream_links'] = old.get('workstream_links',{}) if old else {}
                value['workstream_link_history'] = old.get('workstream_link_history',[]) if old else []
                if state == 'unavailable' or incomplete:
                    value['individual_observations'] = previous
                else:
                    identities = {individual_key(row['hostId'],row['id']) for row in value['threads']}
                    retained = {}
                    for key,item in previous.items():
                        if key not in identities or timestamp(item['attempted_at']) <= observed:
                            continue
                        item = dict(item)
                        if timestamp(item['value_observed_at']) <= observed:
                            item.update(value_observed_at=observed.isoformat(),value_source=SOURCE,
                                        value_scope='complete_snapshot',metadata={})
                        retained[key] = item
                    value['individual_observations'] = retained
                self.app.db.execute('INSERT OR REPLACE INTO desktop_observation VALUES (1,?)',(json.dumps(value,ensure_ascii=False),))
                self.app.db.commit()
            except BaseException:
                self.app.db.rollback()
                raise
        return self.read()

    def link_workstream(self, payload):
        """Record an explicit reference to one uniquely registered thread."""
        required = {'workstream','host_id','thread_id','source_note'}
        expected_fields = {'expected_host_id','expected_thread_id','expected_linked_at'}
        if (not isinstance(payload,dict) or not required.issubset(payload)
                or set(payload)-required-expected_fields
                or bool(set(payload)&expected_fields) != expected_fields.issubset(payload)):
            raise ValueError('工作线关联字段无效。')
        line, host_id, thread_id, note = (payload.get(key) for key in ('workstream','host_id','thread_id','source_note'))
        if not isinstance(line,str) or line not in WORKSTREAMS:
            raise ValueError('请选择已支持的工作线。')
        if any(not isinstance(v,str) or not v or len(v)>2000 or forbidden_controls(v) for v in (host_id,thread_id)):
            raise ValueError('必须明确已登记的主机和会话编号。')
        if not isinstance(note,str) or not note.strip() or len(note)>500 or forbidden_controls(note):
            raise ValueError('请提供不超过500字的关联来源说明。')
        expected = None
        if expected_fields.issubset(payload):
            expected = (payload['expected_host_id'],payload['expected_thread_id'],payload['expected_linked_at'])
            if any(not isinstance(v,str) or not v or len(v)>2000 or forbidden_controls(v) for v in expected):
                raise ValueError('请提供完整的原会话主机、编号和关联时间。')
            timestamp(expected[2])
        note = note.strip()
        with self.app.lock:
            if self.app.db.in_transaction:
                raise RuntimeError('工作线关联不能嵌套事务。')
            self.app.db.execute('BEGIN IMMEDIATE')
            try:
                value = self._stored()
                if not value:
                    raise ValueError('尚无完整快照，不能推断会话身份。')
                links = value.setdefault('workstream_links',{})
                old = links.get(line)
                if old:
                    old_identity = (old.get('host_id'),old.get('thread_id'))
                    old_version = (*old_identity,old.get('linked_at'))
                    if old_identity == (host_id,thread_id):
                        if expected is not None and expected != old_version:
                            raise WorkspaceConflict('原关联已变化，请重新读取。')
                        if old.get('source_note')!=note:
                            raise WorkspaceConflict('关联来源说明不同，请先人工核对。')
                        self.app.db.commit()
                        return self._link_result(line)
                    if expected is None or expected != old_version:
                        raise WorkspaceConflict('原关联已变化或未提供预期身份，请先人工核对。')
                elif expected is not None:
                    raise WorkspaceConflict('工作线尚无原关联，请重新读取后登记。')
                if any(key!=line and item.get('host_id')==host_id and item.get('thread_id')==thread_id for key,item in links.items()):
                    raise WorkspaceConflict('该会话已关联其他工作线，不能自动合并。')
                matches = [row for row in value.get('threads',[]) if row.get('hostId')==host_id and row.get('id')==thread_id]
                if len(matches)!=1:
                    raise ValueError('会话未登记或身份不唯一，不能自动关联。')
                at = stamp()
                if old:
                    if timestamp(at) <= timestamp(old['linked_at']):
                        at = (timestamp(old['linked_at']) + timedelta(microseconds=1)).isoformat()
                    history = value.setdefault('workstream_link_history',[])
                    history.append({**old,'replaced_at':at})
                    value['workstream_link_history'] = history[-MAX_LINK_HISTORY:]
                links[line] = {'workstream':line,'host_id':host_id,'thread_id':thread_id,
                               'source_note':note,'linked_at':at,'control':'reference_only'}
                self.app.db.execute('INSERT OR REPLACE INTO desktop_observation VALUES (1,?)',(json.dumps(value,ensure_ascii=False),))
                self.app.db.commit()
            except BaseException:
                self.app.db.rollback()
                raise
        return self._link_result(line)

    def _link_result(self, line):
        value = self.read()
        item = next((link for link in value.get('workstream_links',[]) if link['workstream']==line),None)
        if not item:
            raise WorkspaceConflict('工作线关联已变化，请重新读取。')
        return item

    def import_observation(self, payload):
        """Import a single registered thread's status without changing the full snapshot."""
        if not isinstance(payload,dict) or set(payload)-{'host_id','thread_id','observed_at','status','source_tool','metadata'}:
            raise ValueError('单条观测字段无效。')
        host_id, thread_id = payload.get('host_id'), payload.get('thread_id')
        if any(not isinstance(v,str) or not v or len(v)>2000 or forbidden_controls(v) for v in (host_id,thread_id)):
            raise ValueError('必须明确已登记的主机和会话编号。')
        observed = timestamp(payload.get('observed_at'))
        if (observed-datetime.now(timezone.utc)).total_seconds()>300:
            raise ValueError('观测时间不能在未来。')
        state, tool = payload.get('status'), payload.get('source_tool')
        if state not in ('ok','unavailable') or not isinstance(tool,str) or tool not in INDIVIDUAL_TOOLS:
            raise ValueError('单条观测必须标明支持的正式工具及来源状态。')
        if state == 'ok':
            metadata = individual_metadata(payload.get('metadata'))
        else:
            if payload.get('metadata') not in (None,{}):
                raise ValueError('来源不可用时不能附带新状态。')
            metadata = {}
        request = {'host_id':host_id,'thread_id':thread_id,'observed_at':observed.isoformat(),
                   'status':state,'source_tool':tool,'metadata':metadata}
        key = individual_key(host_id,thread_id)
        with self.app.lock:
            if self.app.db.in_transaction:
                raise RuntimeError('单条观测写入不能嵌套事务。')
            self.app.db.execute('BEGIN IMMEDIATE')
            try:
                value = self._stored()
                if not value:
                    raise ValueError('尚无完整快照，不能推断会话身份。')
                matches = [row for row in value.get('threads',[]) if row.get('hostId')==host_id and row.get('id')==thread_id]
                if len(matches)!=1:
                    raise ValueError('会话未登记或身份不唯一，不能自动关联。')
                snapshot_at = timestamp(value.get('snapshot_observed_at') or value['observed_at'])
                observations = value.setdefault('individual_observations',{})
                previous = observations.get(key)
                if previous:
                    last = timestamp(previous['attempted_at'])
                    if observed < last or (observed == last and previous.get('request') != request):
                        raise WorkspaceConflict('已有更新或同一时刻不同的单条观测，请重新读取。')
                    if observed == last:
                        self.app.db.commit()
                        return self._observation_result(host_id,thread_id)
                if observed <= snapshot_at:
                    raise WorkspaceConflict('单条观测不晚于完整快照，请重新读取。')
                if state == 'ok':
                    item = {'attempted_at':observed.isoformat(),'attempt_source':tool,'attempt_status':state,
                            'value_observed_at':observed.isoformat(),'value_source':tool,
                            'value_scope':'individual','metadata':metadata,'request':request}
                else:
                    item = {'attempted_at':observed.isoformat(),'attempt_source':tool,'attempt_status':state,
                            'value_observed_at':previous.get('value_observed_at') if previous else snapshot_at.isoformat(),
                            'value_source':previous.get('value_source') if previous else SOURCE,
                            'value_scope':previous.get('value_scope') if previous else 'complete_snapshot',
                            'metadata':previous.get('metadata',{}) if previous else {},'request':request}
                observations[key] = item
                self.app.db.execute('INSERT OR REPLACE INTO desktop_observation VALUES (1,?)',(json.dumps(value,ensure_ascii=False),))
                self.app.db.commit()
            except BaseException:
                self.app.db.rollback()
                raise
        return self._observation_result(host_id,thread_id)

    def _observation_result(self, host_id, thread_id):
        value = self.read()
        row = next((item for item in value['threads'] if item.get('hostId')==host_id and item.get('id')==thread_id),None)
        if not row or not row.get('individual_observation'):
            raise WorkspaceConflict('单条观测已被更新的完整快照替代，请重新读取。')
        return {'scope':'individual','host_id':host_id,'thread_id':thread_id,
                'individual_observation':row['individual_observation'],
                'full_snapshot_observed_at':value.get('snapshot_observed_at'),
                'full_snapshot_state':value['state'],'automatic_refresh':False}

    def read(self):
        value = self._stored()
        if not value:
            return {'state':'missing','source':SOURCE,'threads':[], 'observed_at':None,
                    'workstream_links':[],'workstream_link_history':[],'individual_count':0,'automatic_refresh':False,
                    'reason':'尚未导入；本机后台没有持续读取桌面会话的连接器。'}
        age = max(0,int((datetime.now(timezone.utc)-timestamp(value['snapshot_observed_at'])).total_seconds()))
        reason = ('本次列表不完整，保留上一份完整快照；请重试正式来源。' if value.get('attempt_truncated') else
                  '只读元信息快照；不包含会话正文，也不代表实时执行队列。')
        observations = value.get('individual_observations',{})
        rows = []
        for row in value['threads']:
            row = dict(row)
            item = observations.get(individual_key(row['hostId'],row['id']))
            if item:
                value_at = item['value_observed_at']
                individual_age = max(0,int((datetime.now(timezone.utc)-timestamp(value_at)).total_seconds()))
                if item.get('value_scope') == 'individual':
                    row.update(item.get('metadata',{}))
                row['individual_observation'] = {
                    'state':'unavailable' if item['attempt_status']=='unavailable' else 'stale' if individual_age>=STALE_SECONDS else 'ok',
                    'source':item['value_source'],'observed_at':value_at,
                    'attempted_at':item['attempted_at'],'attempt_source':item['attempt_source'],
                    'age_seconds':individual_age,'value_scope':item['value_scope']}
            rows.append(row)
        public = {key:item for key,item in value.items() if key not in ('threads','individual_observations','workstream_links')}
        identities = {(item['hostId'],item['id']) for item in rows}
        links = [{**link,'registration_state':('present_in_snapshot' if (link['host_id'],link['thread_id']) in identities else 'not_in_latest_snapshot')}
                 for _,link in sorted(value.get('workstream_links',{}).items())]
        return {**public,'threads':rows,'individual_count':len(observations),'workstream_links':links,
                'state':'unavailable' if value['status']=='unavailable' else 'stale' if age>=STALE_SECONDS else 'ok',
                'stale':age>=STALE_SECONDS or value['status']=='unavailable','age_seconds':age,
                 'automatic_refresh':False,'source':SOURCE,'reason':reason}


if __name__ == '__main__':
    import argparse
    import sqlite3
    import threading
    from types import SimpleNamespace
    parser = argparse.ArgumentParser(description=SOURCE)
    parser.add_argument('--root', required=True)
    parser.add_argument('--state', required=True, help='Existing workbench state directory')
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument('--input', help='Explicit JSON metadata snapshot; omitted reads current observation')
    inputs.add_argument('--observation-input', help='Explicit JSON observation for one registered thread')
    inputs.add_argument('--link-input', help='Explicit JSON workstream-to-registered-thread reference')
    args = parser.parse_args()
    database = Path(args.state)/'runs.sqlite3'
    if not database.is_file(): parser.error('工作台数据库不存在。')
    connection = sqlite3.connect(database, timeout=10)
    service = DesktopSnapshot(SimpleNamespace(root=Path(args.root), db=connection, lock=threading.RLock()))
    try:
        import sys
        location = args.input or args.observation_input or args.link_input
        raw = sys.stdin.readline(2_000_001) if location=='-' else Path(location).read_text(encoding='utf-8-sig') if location else None
        if raw is not None and len(raw)>2000000: parser.error('快照超过大小上限。')
        if args.observation_input:
            result = service.import_observation(json.loads(raw))
        elif args.link_input:
            result = service.link_workstream(json.loads(raw))
        else:
            result = service.import_snapshot(json.loads(raw)) if raw is not None else service.read()
            if raw is not None: result = {**{k:v for k,v in result.items() if k!='threads'}, 'thread_count':len(result['threads'])}
        print(json.dumps(result,ensure_ascii=False))
    finally:
        connection.close()
