"""Business actions and actual progress for the workbench home page."""
from datetime import datetime, timezone


GROUPS = ('decide', 'act', 'watch')
GROUP_LABELS = {'decide': '需要决定', 'act': '待处理', 'watch': '等待与进行中'}
SEVERITY_ORDER = {'high': 0, 'normal': 1, 'low': 2}


class Today:
    def __init__(self, app, gaps=None):
        self.app = app

    def snapshot(self):
        sources, items = {}, []
        for collect in (self._customers, self._prospects, self._mail, self._changes, self._channels, self._catalog, self._jobs):
            try:
                items.extend(collect(sources))
            except Exception as exc:
                sources[collect.__name__.lstrip('_')] = {'state': 'unavailable', 'reason': str(exc) or type(exc).__name__}
        replies = {item['object_id']: item for item in items if item['kind'] == 'customer_reply'}
        waiting = {item['object_id']: item for item in items if item['kind'] == 'customer_waiting'}
        visible = []
        for item in items:
            if item['kind'] in ('agent_job', 'agent_job_running') and item['object_id'] in replies:
                note = '自动整理未完成，请打开客户继续处理。' if item['kind'] == 'agent_job' else '正在整理回复草稿。'
                replies[item['object_id']]['judgment'] += ' ' + note
                continue
            if item['kind'] == 'agent_job' and item['object_id'] in waiting:
                since, job_at = waiting[item['object_id']].get('updated_at'), item.get('updated_at')
                if since and job_at and datetime.fromisoformat(since) > datetime.fromisoformat(job_at):
                    continue
            visible.append(item)
        items = visible
        items.sort(key=lambda item: (GROUPS.index(item['group']), SEVERITY_ORDER[item['severity']], item['title']))
        grouped = {key: [item for item in items if item['group'] == key] for key in GROUPS}
        return {'generated_at': datetime.now(timezone.utc).isoformat(), 'groups': grouped,
                'labels': GROUP_LABELS, 'counts': {key: len(value) for key, value in grouped.items()},
                'sources': sources}

    @staticmethod
    def _item(group, kind, title, judgment, action, evidence=(), severity='normal', object_id=None, updated_at=None):
        return {'id': kind + ':' + (object_id or title), 'kind': kind, 'group': group, 'title': title,
                'judgment': judgment, 'action': action, 'evidence': list(evidence), 'severity': severity,
                'object_id': object_id, 'updated_at': updated_at}

    def _customers(self, sources):
        queue = self.app.customer_workspace.queue(bucket='active')
        history = self.app.customer_workspace.queue(bucket='history')
        sources['customers'] = {'state': 'ok', 'counts': queue.get('counts')}
        items = []
        active = queue.get('items', [])
        active_ids = {row.get('object_id') for row in active}
        history_replies = [row for row in history.get('items', [])
                           if row.get('object_id') not in active_ids and
                           ((row.get('workflow') or {}).get('gmail_reply_pending') or
                            (row.get('workflow') or {}).get('customer_reply_pending'))]
        for row in [*active, *history_replies]:
            flow, summary = row.get('workflow') or {}, row.get('business_summary') or {}
            oid, title = row.get('object_id'), row.get('title') or '客户'
            action = {'label': '查看客户', 'type': 'open_object', 'object_id': oid}
            if flow.get('gmail_reply_pending') or flow.get('customer_reply_pending'):
                channels = []
                if flow.get('gmail_reply_pending'): channels.append('Gmail 客户有新回复')
                if flow.get('customer_reply_pending'): channels.append('网站站内消息有新回复')
                items.append(self._item('act', 'customer_reply', title + '有新回复',
                    ' · '.join(channels), action, severity='high', object_id=oid))
            elif flow.get('overdue'):
                items.append(self._item('act', 'customer_action', title,
                    flow.get('next_action') or '超过安排时间，请继续处理。', action, severity='high', object_id=oid))
            elif flow.get('pending_party') == 'customer':
                items.append(self._item('watch', 'customer_waiting', '等待回复：' + title,
                    flow.get('next_action') or '等待客户回复。', action, severity='low', object_id=oid,
                    updated_at=flow.get('updated_at')))
            else:
                need = summary.get('core_need') or summary.get('headline') or ''
                next_action = summary.get('next_action') or flow.get('next_action') or '查看需求并安排下一步。'
                items.append(self._item('act', 'customer_action', title,
                    ' · '.join(part for part in (need, next_action) if part), action, object_id=oid))
        return items

    def _prospects(self, sources):
        workspace = self.app.customer_workspace
        if not hasattr(workspace, 'discovery'):
            return []
        candidates = workspace.discovery().get('candidates', [])
        sources['prospects'] = {'state': 'ok'}
        items = []
        for row in candidates:
            oid = row.get('object_id')
            if not oid:
                continue
            action = {'label': '查看客户', 'type': 'open_object', 'object_id': oid}
            if row.get('gmail_reply_pending'):
                context = self.app.gmail.peek(oid)
                incoming = [m for m in context.get('messages', [])
                            if m.get('direction') == 'inbound' and m.get('mail_kind') not in ('automatic', 'promotion')]
                latest = max(incoming, key=lambda m: m.get('sent_at') or '', default={})
                sender = latest.get('from') or ''
                message = ('发件人：' + sender + '。' if sender else '') + '查看新邮件并继续处理。'
                items.append(self._item('act', 'customer_reply', (row.get('title') or '客户') + '有新来信',
                    message, action, severity='high', object_id=oid, updated_at=latest.get('sent_at')))
                continue
            saved = workspace._saved_profile(oid).get('workflow', {}) if hasattr(workspace, '_saved_profile') else {}
            if saved.get('bucket') == 'active' and saved.get('state') == 'waiting_customer':
                items.append(self._item('watch', 'customer_waiting', '等待回复：' + (row.get('title') or '客户'),
                    saved.get('next_action') or '等待客户回复。', action, severity='low', object_id=oid,
                    updated_at=saved.get('updated_at')))
        return items

    def _mail(self, sources):
        status = self.app.gmail.status()
        sources['gmail'] = {'state': status.get('state'), 'last_success_at': status.get('last_success_at')}
        if status.get('state') != 'connected':
            return [self._item('act', 'gmail_link', 'Gmail 暂未连接',
                status.get('error') or '连接后可查看客户邮件和新回复。',
                {'label': '打开客户开发', 'type': 'open_development'}, severity='high')]
        if not hasattr(self.app.gmail, 'buyer_candidates'):
            return []
        inbox = self.app.gmail.buyer_candidates()
        sources['buyer_mail'] = inbox.get('status', {})
        items = []
        for row in inbox.get('items', []):
            if not row.get('is_new') or row.get('answered') is True:
                continue
            item = self._item('act', 'buyer_mail', '新买家来信：' + (row.get('title') or '潜在买家'),
                row.get('summary') or '查看邮件并判断是否加入客户。',
                {'label': '查看来信', 'type': 'open_development'}, severity='high',
                updated_at=row.get('sent_at'))
            # Two unrelated buyers can have the same display name. Keep the
            # actual mailbox message identity when one is available.
            if row.get('id'): item['id'] = 'buyer_mail:' + str(row['id'])
            items.append(item)
        return items

    def _changes(self, sources):
        changes = self.app.product_changes.list_changes()
        pending = [c for c in changes if c.get('state') == 'prepared' and c.get('internalTest') is not True]
        sources['product_changes'] = {'state': 'ok', 'pending': len(pending)}
        products = self.app.business.list_objects(kind='product') if pending and hasattr(self.app.business, 'list_objects') else []
        items = []
        for change in pending:
            platform_id = str(change.get('productId') or '')
            product = next((p for p in products if any(str(listing.get('id')) == platform_id
                            for listing in p.get('channel_listings') or [])), None)
            action = ({'label': '查看商品', 'type': 'open_object', 'object_id': product['id']}
                      if product else {'label': '打开商品', 'type': 'open_catalog'})
            items.append(self._item('decide', 'platform_change', (product or {}).get('title') or '商品标题草稿',
                '商品标题修改已准备，可查看后决定。', action,
                [{'label': '拟修改标题', 'value': (change.get('diff') or {}).get('after') or ''}],
                severity='normal', object_id=(product or {}).get('id')))
        return items

    def _channels(self, sources):
        stale = []
        for name, label in (('alibaba', '国际站'), ('website', '独立站')):
            try:
                status = self.app.business.alibaba.status() if name == 'alibaba' else self.app.business.website_status()
                sources[name] = {'state': status.get('state'), 'observed_at': status.get('observed_at'),
                                 'stale': status.get('stale')}
                if status.get('stale'):
                    stale.append(label)
            except Exception as exc:
                sources[name] = {'state': 'unavailable', 'reason': str(exc) or type(exc).__name__}
        if not stale:
            return []
        return [self._item('act', 'channel_stale', '、'.join(stale) + '数据需要更新',
            '查看渠道状态并按需更新。', {'label': '查看渠道', 'type': 'open_channels'})]

    def _jobs(self, sources):
        jobs = self.app.agent_jobs.list_jobs()
        sources['agent_jobs'] = {'state': 'ok', 'total': len(jobs)}
        latest = {}
        for job in sorted(jobs, key=lambda j: j.get('updated_at') or j.get('created_at') or '', reverse=True):
            # A plan or non-executing group must not hide the latest actual
            # execution for the same business object on the home page.
            if job.get('task_kind') == 'group' or job.get('status') == 'planned':
                continue
            latest.setdefault(job.get('object_id') or job.get('id'), job)
        items = []
        for job in latest.values():
            oid, status = job.get('object_id'), job.get('status')
            action = {'label': '查看工作', 'type': 'open_object', 'object_id': oid}
            if status in ('failed', 'needs_input'):
                items.append(self._item('act', 'agent_job', '工作未完成：' + (job.get('title') or '未命名'),
                    job.get('error') or '查看原因并继续。', action, severity='normal', object_id=oid,
                    updated_at=job.get('updated_at')))
            elif status in ('queued', 'starting', 'running'):
                items.append(self._item('watch', 'agent_job_running', '正在执行：' + (job.get('title') or '工作'),
                    '完成后可在对应页面查看成果。', action, severity='low', object_id=oid,
                    updated_at=job.get('updated_at')))
        return items

    def _catalog(self, sources):
        monitor = getattr(self.app, 'catalog_monitor', None)
        if not monitor: return []
        status = monitor.status()
        sources['alibaba_catalog'] = {key:status.get(key) for key in ('state','stale','last_attempt_at','last_success_at')}
        action = {'label':'查看国际站状态','type':'open_channels'}
        if status.get('state') == 'error':
            return [self._item('act','catalog_status','国际站商品状态采集失败',
                    '保留上次完整结果，请查看连接和采集时间。',action,severity='high')]
        if status.get('state') != 'ready': return []
        comparison=status.get('comparison') or {};changes=status.get('changes') or {}
        parts=[]
        if status.get('stale'):parts.append('上次完整采集已过期')
        if status.get('review_required'):parts.append(str(status['review_required'])+' 条审核状态需核对')
        if status.get('unknown_state'):parts.append(str(status['unknown_state'])+' 条状态未识别')
        if comparison.get('different'):parts.append(str(len(comparison['different']))+' 条与本地记录不同')
        if changes.get('status_or_display'):parts.append(str(len(changes['status_or_display']))+' 条状态较上次变化')
        if not parts:return []
        return [self._item('act','catalog_status','国际站商品状态需核对',
                ' · '.join(parts)+'；不自动修改平台或本地档案。',action)]
