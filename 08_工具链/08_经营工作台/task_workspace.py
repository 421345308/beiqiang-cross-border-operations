"""Read-through work index over AgentJobs and the existing cloud queue.

No independent task status or business facts are persisted here. Routing is a
read-only preview; explicit plans/dispatches still use AgentJobs' safeguards.
"""
import re
from datetime import datetime, timezone
from urllib.parse import quote
from desktop_snapshot import SOURCE as DESKTOP_SOURCE


def now():
    return datetime.now(timezone.utc).isoformat()


class TaskWorkspace:
    def __init__(self, app):
        self.app = app

    def overview(self, filters=None):
        filters = filters or {}
        if set(filters) - {'business_line', 'object_id', 'executor', 'priority'}:
            raise ValueError('不支持的总览筛选字段。')
        tasks = []
        business_items = []
        try:
            jobs = self.app.agent_jobs.list_jobs()
            local_state = 'ok'
        except (ValueError, OSError, RuntimeError):
            jobs = []
            local_state = 'unavailable'
        for job in jobs:
            row = {key: job.get(key) for key in (
                'object_id', 'title', 'instruction', 'status', 'summary', 'error',
                'updated_at', 'artifact_id', 'session_id', 'attempt', 'task_kind',
                'parent_job_id', 'depends_on', 'version', 'priority', 'next_action', 'conversations')}
            row.update(id='local:' + job['id'], job_id=job['id'], origin='local', version=job.get('version', 0))
            if job.get('task_kind') == 'group':
                row['graph'] = self.app.agent_jobs.get_graph(job['id'])
            tasks.append(row)
        sources = {'local': {'state': local_state, 'observed_at': now()}}
        inbox = []
        for job in jobs:
            if job.get('status') in ('failed', 'needs_input') and job.get('task_kind') != 'group':
                inbox.append({'id':'local:'+job['id'], 'kind':'agent_job', 'group':'act',
                    'title':job.get('title') or '本机工作',
                    'judgment':job.get('error') or job.get('summary') or '请核对成果与中断原因。',
                    'severity':'normal', 'object_id':job.get('object_id'),
                    'action':{'type':'open_task','job_id':job['id'],'task_id':'local:'+job['id'],'label':'核对任务'},
                    'updated_at':job.get('updated_at')})
        # Reuse the same business decisions as the home page. These are
        # projections of existing customer records, not new tasks or copies
        # of inquiry/message data. Website open is not itself a local todo.
        try:
            today = self.app.today.snapshot()
            today_sources = today.get('sources') or {}
            for group, items in today.get('groups', {}).items():
                for item in items:
                    if item.get('kind') not in ('agent_job', 'agent_job_running', 'cloud_run'):
                        business_items.append({**item, 'business_group': group})
            for name in ('customers', 'prospects', 'gmail', 'buyer_mail', 'website'):
                sources[name] = today_sources.get(name, {'state': 'unavailable'})
            for item in today.get('groups', {}).get('act', []):
                kind, oid = item.get('kind'), item.get('object_id')
                if kind in ('customer_reply', 'buyer_mail', 'catalog_status') or (
                    kind == 'customer_action' and str(oid or '').startswith('customer:website-')
                ):
                    inbox.append(dict(item))
        except Exception:
            # A missing business source must not make the task list fail or
            # look as though the customer inbox was successfully read.
            for name in ('customers', 'prospects', 'gmail', 'buyer_mail', 'website'):
                sources[name] = {'state': 'unavailable'}
        try:
            cloud = self.app.cloud_review.workspace_status()
            sources['cloud'] = {'state': 'ok', 'observed_at': cloud.get('observed_at'),
                                'dispatch': cloud.get('dispatch'), 'truncated': cloud.get('truncated', False)}
            for run in cloud['runs']:
                row = {key: run.get(key) for key in ('title', 'instruction', 'status', 'summary', 'error',
                       'updated_at', 'task_id', 'version', 'source', 'source_version', 'model', 'next_steps', 'priority')}
                row.update(id='cloud:' + run['id'], run_id=run['id'], origin='cloud',
                           object_id=None, job_id=None, observed_at=cloud.get('observed_at'))
                tasks.append(row)
                if run.get('status') in ('awaiting_review', 'failed', 'interrupted', 'blocked', 'outcome_unknown'):
                    inbox.append({'id': row['id'], 'kind': 'cloud_run', 'group': 'decide',
                        'title': row.get('title') or '云端工作',
                        'judgment': row.get('error') or row.get('summary') or '请核对云端执行结果。',
                        'severity': 'high' if run.get('status') != 'awaiting_review' else 'normal',
                        'action': {'type': 'open_cloud_review', 'run_id': run['id'], 'label': '核对云端成果'},
                        'updated_at': row.get('updated_at')})
        except (ValueError, OSError) as error:
            sources['cloud'] = {'state': 'unavailable', 'reason': str(error), 'observed_at': now()}
        inbox.sort(key=lambda item: (0 if item.get('severity') == 'high' else 1,
                                    0 if item.get('group') == 'decide' else 1,
                                    item.get('updated_at') or ''))
        tasks.sort(key=lambda item: item.get('updated_at') or '', reverse=True)
        observed = now()
        for item in business_items:
            tasks.append({**{k:item.get(k) for k in ('object_id', 'title', 'updated_at', 'action')},
                'id':'business:' + str(item['id']), 'origin':'business',
                'status':item.get('business_group', 'act'), 'summary':item.get('judgment'),
                'priority':'high' if item.get('severity') == 'high' else 'low' if item.get('severity') == 'low' else 'normal',
                'priority_basis':'business_severity', 'priority_source':'severity', 'source_severity':item.get('severity') or 'normal',
                'next_action':item.get('judgment') or (item.get('action') or {}).get('label') or '',
                'kind':item.get('kind')})
        try:
            objects = {obj['id']:obj for obj in self.app.business.list_objects()}
            sources['objects'] = {'state':'ok', 'observed_at':observed}
        except Exception:
            objects = {}
            sources['objects'] = {'state':'unavailable', 'observed_at':observed}
        desktop = getattr(self.app, 'desktop_snapshot', None)
        try:
            snapshot = desktop.read() if desktop else {'state':'missing','threads':[], 'observed_at':None,
                'source':DESKTOP_SOURCE, 'automatic_refresh':False,
                'reason':'尚未导入；本机后台没有持续读取桌面会话的连接器。'}
        except (ValueError, OSError, RuntimeError):
            snapshot = {'state':'unavailable','threads':[], 'observed_at':None, 'source':DESKTOP_SOURCE,
                'automatic_refresh':False,'reason':'无法读取桌面快照。'}
        sources['desktop'] = {k:v for k,v in snapshot.items() if k != 'threads'}
        for thread in snapshot['threads']:
            status = thread.get('status') or 'unknown'
            tasks.append({'id':'desktop:' + quote(thread['hostId'],safe='') + ':' + quote(thread['id'],safe=''),
                'thread_id':thread['id'], 'host_id':thread['hostId'], 'origin':'desktop', 'object_id':None,
                'title':thread.get('title') or '桌面会话', 'status':'unknown' if status=='notLoaded' else status,
                'source_status':status, 'source':DESKTOP_SOURCE, 'updated_at':thread.get('updatedAt'),
                'observed_at':snapshot.get('snapshot_observed_at') or snapshot.get('observed_at'),
                'snapshot_state':snapshot['state'], 'snapshot_imported_at':snapshot.get('imported_at'),
                'conversation_scope':'reference_only',
                'next_action':'请在原桌面会话核对；此处不读取历史或控制执行。'})
        for source in sources.values():
            if source is not sources['desktop']: source.setdefault('observed_at', observed)
        for row in tasks:
            obj = objects.get(row.get('object_id'), {})
            oid = row.get('object_id') or ''
            kind = obj.get('kind') or oid.split(':')[0]
            source_path = str(row.get('source') or obj.get('source') or '').replace('\\','/')
            line = ('other' if row['origin']=='desktop' else
                    'alibaba' if row.get('kind')=='catalog_status' or oid=='channel:alibaba' or source_path.startswith('02_Alibaba运营/') else
                    'website' if oid.startswith('customer:website-') or source_path.startswith('03_独立站/') else
                    'domestic' if oid == 'channel:douyin' else
                    'creation' if kind == 'creation' else
                    'international' if kind in ('customer','prospect') else
                    'products' if kind == 'product' else 'other')
            row.update(business_line=line, object_title=obj.get('title') or row.get('object_id') or '未关联对象',
                executor='codex_cli' if row['origin']=='local' else 'paired_cloud' if row['origin']=='cloud' else 'codex_desktop' if row['origin']=='desktop' else 'business_owner',
                priority=(row.get('priority') or 'normal') if row['origin']=='local' else row.get('priority'),
                priority_basis=row.get('priority_basis') or ('registered' if row.get('priority') else 'local_default' if row['origin']=='local' else 'unregistered'),
                next_action=row.get('next_action') or row.get('next_steps') or
                    ({'planned':'核对计划后显式派发', 'running':'等待执行结果', 'queued':'等待已派发任务启动',
                      'failed':'核对中断原因与已有成果', 'needs_input':'补充所需信息', 'completed':'核对成果'}
                     .get(row.get('status'), '') if row['origin']=='local' else ''),
                blocker=row.get('error') or ('前置任务：' + ', '.join(row['depends_on']) if row.get('depends_on') else ''),
                result=row.get('summary') or '', observed_at=row.get('observed_at', observed),
                source=row.get('source') or ('AgentJobs' if row['origin']=='local' else 'paired_cloud_queue' if row['origin']=='cloud' else 'business_source'),
                capabilities={'adjust':row['origin']=='local', 'scheduling_effect':'display_only',
                    'external_conversation_control':False,
                    'read_only_reason':'' if row['origin']=='local' else '此总览未接入该来源的安全写入。'})
            row['freshness'] = ({'state':snapshot['state'], 'updated_at':row.get('updated_at'),
                'age_seconds':snapshot.get('age_seconds')} if row['origin']=='desktop'
                else self._freshness(row.get('updated_at'), observed))
            row['conversation_scope'] = 'reference_only' if row['origin']=='desktop' or any(c.get('control')=='reference_only' for c in row.get('conversations') or []) else None
        options = {key:[{'value':value, 'label':value} for value in sorted({str(row.get(key)) for row in tasks if row.get(key)})]
                   for key in ('business_line','object_id','executor','priority')}
        tasks = [row for row in tasks if all(str(row.get(key) or '') == value for key,value in filters.items() if value)]
        return {'tasks': tasks, 'sources': sources, 'inbox': inbox, 'observed_at': observed,
                'filters':options, 'applied_filters':filters,
                'scheduling_effect':'display_only',
                'scope': '本机 AgentJobs、已配对云队列、现有业务待办及由 Dot 导入的桌面会话只读快照（非实时、未自动更新）；未导入或未登记的会话和其他数据库不在此列表。'}

    @staticmethod
    def _freshness(updated_at, observed_at):
        try:
            source = datetime.fromisoformat(updated_at.replace('Z','+00:00'))
            if source.tzinfo is None:
                return {'state':'unknown', 'updated_at':updated_at, 'age_seconds':None}
            age = max(0, (datetime.fromisoformat(observed_at) - source).total_seconds())
            return {'state':'recent' if age < 86400 else 'older', 'updated_at':updated_at, 'age_seconds':int(age)}
        except (ValueError, TypeError, AttributeError):
            return {'state':'unknown', 'updated_at':updated_at, 'age_seconds':None}

    def route(self, instruction, object_id=None):
        if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 12000:
            raise ValueError('请填写1至12000字的目标。')
        instruction = instruction.strip()
        objects = self.app.business.list_objects()
        needs_confirmation = False
        if object_id is not None:
            obj = self.app.business.get_object(object_id)
            matches = [obj]
        else:
            # A name/alias hit supplies candidates only. Existing exact object
            # identifiers and a whole-instruction title retain their routing.
            exact, suggested = [], []
            def mentioned(value):
                return isinstance(value, str) and bool(value.strip()) and re.search(
                    r'(?<![A-Za-z0-9:_-])' + re.escape(value.strip()) + r'(?![A-Za-z0-9:_-])', instruction, re.I)
            for obj in objects:
                keys = [obj['id']]
                if obj.get('kind') == 'product':
                    keys.append(obj['id'].removeprefix('product:'))
                if obj.get('title') == instruction or any(mentioned(key) for key in keys):
                    exact.append(obj)
                aliases = obj.get('aliases') or []
                if isinstance(aliases, str): aliases = [aliases]
                if any(mentioned(key) for key in [obj.get('title'), obj.get('current_model'), *aliases]):
                    suggested.append(obj)
            by_id = {obj['id']:obj for obj in [*exact, *suggested]}
            matches = list(by_id.values())
            needs_confirmation = len(exact) != 1 or len(matches) != 1
        candidates = [{key: obj.get(key) for key in ('id', 'title', 'kind')} for obj in matches]
        if needs_confirmation or len(matches) != 1:
            return {'action': 'choose', 'instruction': instruction, 'candidates': candidates,
                    'jobs': [], 'reason': '请选择明确的业务对象，尚未创建或执行任务。'}
        oid = matches[0]['id']
        jobs = [job for job in self.app.agent_jobs.list_jobs() if job.get('object_id') == oid
                and job.get('task_kind') != 'group' and job.get('status') != 'cancelled']
        # Existing work is shown, never resumed or duplicated by text similarity.
        return {'action': 'continue' if jobs else 'create', 'object_id': oid,
                'instruction': instruction, 'candidates': candidates, 'jobs': jobs,
                'reason': '已有工作请先查看上下文；不会自动重复执行。' if jobs else '对象已确认，可保存为现有任务系统中的计划。'}
