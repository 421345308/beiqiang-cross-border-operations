"""Read-through work index over AgentJobs and the existing cloud queue.

No independent task status or business facts are persisted here. Routing is a
read-only preview; explicit plans/dispatches still use AgentJobs' safeguards.
"""
import re
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


class TaskWorkspace:
    def __init__(self, app):
        self.app = app

    def overview(self):
        tasks = []
        jobs = self.app.agent_jobs.list_jobs()
        for job in jobs:
            row = {key: job.get(key) for key in (
                'object_id', 'title', 'instruction', 'status', 'summary', 'error',
                'updated_at', 'artifact_id', 'session_id', 'attempt', 'task_kind',
                'parent_job_id', 'depends_on')}
            row.update(id='local:' + job['id'], job_id=job['id'], origin='local')
            if job.get('task_kind') == 'group':
                row['graph'] = self.app.agent_jobs.get_graph(job['id'])
            tasks.append(row)
        sources = {'local': {'state': 'ok', 'observed_at': now()}}
        inbox = []
        for job in jobs:
            if job.get('status') in ('failed', 'needs_input') and job.get('task_kind') != 'group':
                inbox.append({'id':'local:'+job['id'], 'kind':'agent_job', 'group':'act',
                    'title':job.get('title') or '本机工作',
                    'judgment':job.get('error') or job.get('summary') or '请核对成果与中断原因。',
                    'severity':'normal', 'object_id':job.get('object_id'),
                    'action':{'type':'open_task','job_id':job['id'],'task_id':'local:'+job['id'],'label':'核对任务'},
                    'updated_at':job.get('updated_at')})
        try:
            cloud = self.app.cloud_review.workspace_status()
            sources['cloud'] = {'state': 'ok', 'observed_at': cloud.get('observed_at'),
                                'dispatch': cloud.get('dispatch'), 'truncated': cloud.get('truncated', False)}
            for run in cloud['runs']:
                row = {key: run.get(key) for key in ('title', 'instruction', 'status', 'summary', 'error',
                       'updated_at', 'task_id', 'version', 'source', 'source_version', 'model', 'next_steps')}
                row.update(id='cloud:' + run['id'], run_id=run['id'], origin='cloud',
                           object_id=None, job_id=None)
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
        return {'tasks': tasks, 'sources': sources, 'inbox': inbox, 'observed_at': now(),
                'scope': '本机 AgentJobs 与已配对云队列；未登记的桌面聊天和其他数据库不在此列表。'}

    def route(self, instruction, object_id=None):
        if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 12000:
            raise ValueError('请填写1至12000字的目标。')
        instruction = instruction.strip()
        objects = self.app.business.list_objects()
        if object_id is not None:
            obj = self.app.business.get_object(object_id)
            matches = [obj]
        else:
            # Exact identifiers/titles only. Substrings such as BQ01/BQ010 must
            # never silently route work to a different product.
            matches = []
            for obj in objects:
                keys = [obj['id'], obj.get('current_model')]
                if obj.get('kind') == 'product':
                    keys.append(obj['id'].removeprefix('product:'))
                if obj.get('title') == instruction:
                    matches.append(obj)
                    continue
                if any(isinstance(key, str) and key and re.search(
                        r'(?<![A-Za-z0-9:_-])' + re.escape(key) + r'(?![A-Za-z0-9:_-])', instruction, re.I)
                       for key in keys):
                    matches.append(obj)
        candidates = [{key: obj.get(key) for key in ('id', 'title', 'kind')} for obj in matches]
        if len(matches) != 1:
            return {'action': 'choose', 'instruction': instruction, 'candidates': candidates,
                    'jobs': [], 'reason': '请选择明确的业务对象，尚未创建或执行任务。'}
        oid = matches[0]['id']
        jobs = [job for job in self.app.agent_jobs.list_jobs() if job.get('object_id') == oid
                and job.get('task_kind') != 'group' and job.get('status') != 'cancelled']
        # Existing work is shown, never resumed or duplicated by text similarity.
        return {'action': 'continue' if jobs else 'create', 'object_id': oid,
                'instruction': instruction, 'candidates': candidates, 'jobs': jobs,
                'reason': '已有工作请先查看上下文；不会自动重复执行。' if jobs else '对象已确认，可保存为现有任务系统中的计划。'}
