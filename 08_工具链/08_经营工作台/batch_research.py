"""Durable customer research groups using the existing AgentJobs executor."""
import hashlib
import json
import re
import uuid

from customer_batches import contact_suppressed
from workspaces import WorkspaceConflict


class BatchResearch:
    def __init__(self, app):
        self.app = app

    @staticmethod
    def _child_key(request_id, object_id):
        digest = hashlib.sha256(object_id.encode('utf-8')).hexdigest()
        return f'batch-research-child:{request_id}:{digest}'

    def check_dispatch(self, job, obj):
        """Called inside the same SQLite write transaction as the job claim."""
        batch = self.app.customer_batches._load(job['batch_id'])
        entry = next((item for item in batch['items'] if item['object_id'] == job['object_id']), None)
        if entry is None:
            raise ValueError('客户已不在当前批次')
        drafts = getattr(self.app, 'gmail_drafts', None)
        draft = drafts._saved(job['object_id']) if drafts else None
        if entry.get('review_state') == 'do_not_contact' or contact_suppressed(self.app, job['object_id'], (draft or {}).get('to', '')):
            raise ValueError('客户已标记不联系')
        try:
            record = json.loads(obj.get('content') or '{}')
        except (TypeError, ValueError):
            record = {}
        if isinstance(record, dict) and (any(record.get(k) is True for k in ('unsubscribed', 'do_not_contact', 'complaint', 'bounced')) or
                str(record.get('suppression_state') or '') in {'suppressed', 'unsubscribed', 'rejected', 'complaint', 'bounced', 'blocked'}):
            raise ValueError('客户原资料已标记不联系或退信')

    def _record_results(self, group_id, results):
        with self.app.agent_jobs._write():
            group = self.app.agent_jobs.get_job(group_id)
            outcomes = group.setdefault('research_outcomes', {})
            for row in results:
                if row['status'] in ('blocked', 'not_started'):
                    outcomes[row['object_id']] = row.get('reason', '尚未启动')
                else:
                    outcomes.pop(row['object_id'], None)
            self.app.agent_jobs._save(group)

    def begin(self, body):
        if not isinstance(body, dict) or set(body) - {'batch_id', 'revision', 'object_ids', 'instruction', 'request_id'}:
            raise ValueError('批量研究字段无效')
        ids = body.get('object_ids')
        instruction = body.get('instruction') or '结合当前批次目标研究客户并准备个性化邮件。'
        request_id = body.get('request_id') or uuid.uuid4().hex
        if (not isinstance(ids, list) or not 1 <= len(ids) <= 8 or
                any(not isinstance(oid, str) or not oid or len(oid) > 300 for oid in ids) or len(set(ids)) != len(ids)):
            raise ValueError('请选择1至8位不同客户并行研究')
        if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 10000:
            raise ValueError('批次研究要求无效')
        if not isinstance(request_id, str) or not re.fullmatch(r'[0-9a-f]{32}', request_id):
            raise ValueError('研究请求编号无效')
        batch_id = body.get('batch_id')
        spec = {'type': 'customer_batch_research', 'object_ids': ids,
                'instruction': instruction.strip(), 'revision': body.get('revision'), 'request_id': request_id}
        key = f'batch-research:{batch_id}:{request_id}'
        prior = next((j for j in self.app.agent_jobs.list_jobs() if j.get('idempotency_key') == key), None)
        if prior:
            if prior.get('batch_id') != batch_id or prior.get('context') != spec:
                raise ValueError('研究请求编号已用于其他内容，请重新读取工作状态')
            return self.continue_group(prior['id'])
        batch = self.app.customer_batches.get(batch_id)
        if body.get('revision') != batch['revision']:
            raise WorkspaceConflict('批次已变化，请刷新后再开始研究')
        if any(oid not in {item['object_id'] for item in batch['items']} for oid in ids):
            raise ValueError('所选客户不在当前批次')
        # An old batch can retain a reference to an unavailable object.  Anchor
        # the non-writing group to an available member, so that member does not
        # prevent independent customers from being researched.
        anchor = None
        for oid in ids:
            try:
                obj = self.app.business.get_object(oid)
            except ValueError:
                continue
            if isinstance(obj, dict) and obj.get('id') == oid:
                anchor = oid
                break
        if anchor is None:
            raise ValueError('所选客户资料均不可读取，请先核对批次')
        group = self.app.agent_jobs.create_group(anchor, '客户批次研究：' + instruction.strip(),
                                                  batch_id=batch_id, idempotency_key=key, context=spec)
        return self.continue_group(group['id'])

    def continue_group(self, group_id):
        group = self.app.agent_jobs.get_job(group_id)
        spec = group.get('context') or {}
        if group.get('task_kind') != 'group' or spec.get('type') != 'customer_batch_research':
            raise ValueError('不是客户批次研究分组')
        if group.get('status') == 'cancelled':
            raise ValueError('研究分组已取消')
        batch = self.app.customer_batches.get(group['batch_id'])
        by_id = {item['object_id']: item for item in batch['items']}
        results = []
        for oid in spec['object_ids']:
            item = by_id.get(oid)
            if item is None:
                results.append({'object_id': oid, 'status': 'blocked', 'reason': '客户已不在当前批次'}); continue
            if item['review_state'] == 'do_not_contact' or item['quality']['suppression_state'] == 'suppressed':
                results.append({'object_id': oid, 'status': 'blocked', 'reason': '客户已标记不联系'}); continue
            if (item.get('checks') or {}).get('status') == 'blocked':
                results.append({'object_id': oid, 'status': 'blocked', 'reason': '存在停止联系、退信或重复记录，请先核对'}); continue
            try:
                job = self.app.agent_jobs.start(oid, spec['instruction'], mode='outreach_research',
                                                batch_id=batch['id'], parent_job_id=group_id,
                                                idempotency_key=self._child_key(spec['request_id'], oid))
                if job['status'] == 'planned':
                    try:
                        job = self.app.agent_jobs.dispatch(job['id'])
                        state = 'started'
                    except ValueError:
                        current = self.app.agent_jobs.get_job(job['id'])
                        if current['status'] == 'planned':
                            raise
                        job, state = current, 'existing'
                else:
                    state = 'existing'
                results.append({'object_id': oid, 'status': state, 'job': job})
            except ValueError as exc:
                results.append({'object_id': oid, 'status': 'not_started', 'reason': str(exc)})
        self._record_results(group_id, results)
        return {'batch_id': batch['id'], 'group_id': group_id, 'results': results,
                'group': self.describe(group_id)}

    def describe(self, group_id):
        group = self.app.agent_jobs.get_job(group_id)
        spec = group.get('context') or {}
        if group.get('task_kind') != 'group' or spec.get('type') != 'customer_batch_research':
            raise ValueError('不是客户批次研究分组')
        graph = self.app.agent_jobs.get_graph(group_id)
        children = [row for row in graph['jobs'] if row.get('parent_job_id') == group_id]
        planned = {row['object_id'] for row in children}
        not_planned = [oid for oid in spec['object_ids'] if oid not in planned]
        aggregate = dict(graph['aggregate'])
        aggregate.update(requested_total=len(spec['object_ids']), not_planned=len(not_planned))
        if not_planned and aggregate['status'] != 'running':
            aggregate['status'] = 'incomplete'
        return {'id': group_id, 'batch_id': group.get('batch_id'), 'created_at': group.get('created_at'),
                'instruction': spec['instruction'], 'requested': spec['object_ids'], 'jobs': children,
                'not_planned': not_planned, 'last_reasons': group.get('research_outcomes') or {},
                'aggregate': aggregate, 'status': group['status']}

    def list_groups(self, batch_id):
        self.app.customer_batches.get(batch_id)
        groups = [row for row in self.app.agent_jobs.list_jobs()
                  if row.get('batch_id') == batch_id and row.get('task_kind') == 'group'
                  and (row.get('context') or {}).get('type') == 'customer_batch_research']
        return {'items': [self.describe(row['id']) for row in groups[:20]]}
