"""Private review queues referencing existing customers; no CRM copies or sends.

Only membership, review notes and version fingerprints are persisted in the
application's local SQLite database. Customer facts and drafts are read live.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import re
from email.utils import getaddresses
from uuid import uuid4

from workspaces import WorkspaceConflict

REVIEW_STATES = {'pending', 'approved', 'changes_requested', 'deferred', 'do_not_contact'}


def _suppression_emails(value):
    return {address.lower() for _, address in getaddresses([str(value or '')])
            if re.fullmatch(r'[^\s<>"\\@]+@[^\s<>"\\@]+\.[^\s<>"\\@]+', address)}


def suppress_contact(app, object_id, batch_id):
    """Caller owns the write transaction. Suppression is append-only.

    Object identity always applies, even if its recipient changes later. Exact
    saved recipient addresses also apply to aliases represented by other objects.
    """
    keys = {'object:' + object_id}
    try:
        from gmail_sync import customer_emails
        obj = app.business.get_object(object_id)
        keys.update('email:' + email.lower() for email in customer_emails(obj))
    except (AttributeError, ValueError, KeyError):
        # Original source may be unavailable; object-level suppression remains.
        pass
    try:
        profile = app.customer_workspace.profile(object_id)
        keys.update('email:' + email for email in _suppression_emails((profile.get('cleaned') or {}).get('email')))
    except (AttributeError, ValueError, KeyError):
        pass
    tables = {r[0] for r in app.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'gmail_drafts' in tables:
        row = app.db.execute('SELECT data FROM gmail_drafts WHERE object_id=?', (object_id,)).fetchone()
        if row:
            draft = json.loads(row[0])
            keys.update('email:' + email for email in _suppression_emails(draft.get('to')))
    for key in keys:
        app.db.execute('INSERT OR IGNORE INTO customer_contact_suppressions VALUES (?,?,?,?)',
                       (key, object_id, batch_id, _now()))


def backfill_contact_suppressions(app):
    """Same DB transaction as its caller; legacy batch DNC is never discarded."""
    app.db.execute('CREATE TABLE IF NOT EXISTS customer_contact_suppressions '
                   '(key TEXT PRIMARY KEY, object_id TEXT NOT NULL, batch_id TEXT NOT NULL, created_at TEXT NOT NULL)')
    tables = {r[0] for r in app.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'customer_batches' in tables:
        for batch_id, value in app.db.execute('SELECT id,data FROM customer_batches').fetchall():
            batch = json.loads(value)
            for item in batch.get('items', []):
                if item.get('review_state') == 'do_not_contact':
                    suppress_contact(app, item['object_id'], batch_id)


def contact_suppressed(app, object_id, recipient=''):
    """Read shared suppression; callers serialize with their app/SQLite lock."""
    keys = ['object:' + object_id] + ['email:' + email for email in sorted(_suppression_emails(recipient))]
    placeholders = ','.join('?' for _ in keys)
    return app.db.execute('SELECT 1 FROM customer_contact_suppressions WHERE key IN (' + placeholders + ') LIMIT 1', keys).fetchone() is not None


def _now():
    return datetime.now(timezone.utc).isoformat()


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def _text(value, limit):
    if not isinstance(value, str) or len(value) > limit or '\x00' in value:
        raise ValueError('批次文字格式无效或过长')
    return value


class CustomerBatches:
    def __init__(self, app):
        self.app = app
        with app.lock:
            app.db.execute('CREATE TABLE IF NOT EXISTS customer_batches (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            backfill_contact_suppressions(app)
            app.db.commit()

    @contextmanager
    def _write(self):
        with self.app.lock:
            if self.app.db.in_transaction:
                raise RuntimeError('批次修改不能嵌入已有事务')
            self.app.db.execute('BEGIN IMMEDIATE')
            try:
                yield
                self.app.db.commit()
            except BaseException:
                self.app.db.rollback()
                raise

    def _load(self, batch_id):
        if not isinstance(batch_id, str):
            raise ValueError('批次编号无效')
        with self.app.lock:
            row = self.app.db.execute('SELECT data FROM customer_batches WHERE id=?', (batch_id,)).fetchone()
        if not row:
            raise ValueError('客户开发批次不存在')
        return json.loads(row[0])

    def _put(self, batch):
        batch['updated_at'] = _now()
        batch['version'] = uuid4().hex
        self.app.db.execute('INSERT OR REPLACE INTO customer_batches VALUES (?,?)',
                            (batch['id'], json.dumps(batch, ensure_ascii=False)))

    def _customer(self, oid):
        obj = self.app.business.get_object(oid)
        if obj.get('kind') not in {'customer', 'prospect'}:
            raise ValueError('批次只能包含已有客户或候选')
        return obj

    def _item(self, entry, batch_ids=None):
        oid = entry['object_id']
        reasons = []
        try:
            obj = self._customer(oid)
            profile = self.app.customer_workspace.profile(oid)
        except ValueError:
            return {**entry, 'review_stale': bool(entry.get('review_fingerprint')),
                    'customer': {'title': '原客户暂不可读取', 'kind': 'unknown'},
                    'draft': None, 'fingerprint': _digest({'unavailable': oid}),
                    'item_revision':_digest({'entry':entry,'unavailable':oid}),
                    'quality': {'status': 'blocked', 'reasons': ['原客户资料暂不可读取'],
                                'source_state': 'unknown', 'contact_state': 'unknown',
                                'suppression_state': 'unknown', 'send_ready': False}}
        try:
            record = json.loads(obj.get('content') or '{}')
        except (ValueError, TypeError):
            record = {}
        if not isinstance(record, dict):
            record = {}
        # Reading a queue must never create a Gmail draft or contact the network.
        drafts = getattr(self.app, 'gmail_drafts', None)
        draft = drafts._saved(oid) if drafts else None
        provenance = profile.get('provenance') or {}
        evidence = []
        for source in (record.get('evidence') or []) + (provenance.get('evidence') or []):
            if isinstance(source,dict) and source not in evidence:evidence.append(source)
        source_available = any(isinstance(e.get('url'),str) and e['url'].startswith(('https://','http://'))
                               and e.get('observed_at') for e in evidence)
        blockers = []
        source_state = (provenance.get('source_verification') or {}).get('state', 'unknown')
        contact_state = record.get('contact_verification') or record.get('email_verification') or 'unknown'
        if not isinstance(contact_state, str):
            contact_state = 'unknown'
        suppression = record.get('suppression_state') or 'unknown'
        if not isinstance(suppression, str):
            suppression = 'unknown'
        shared_suppressed = contact_suppressed(self.app,oid,(draft or {}).get('to',''))
        suppressed = (shared_suppressed or entry['review_state'] == 'do_not_contact' or
                      any(record.get(k) is True for k in ('unsubscribed', 'do_not_contact', 'complaint', 'bounced')) or
                      suppression in {'suppressed', 'unsubscribed', 'rejected', 'complaint', 'bounced', 'blocked'})
        if source_state != 'verified':
            reasons.append('客户来源尚未核实')
        if not source_available:
            blockers.append('缺少带观察时间的来源链接')
        if contact_state not in {'verified', 'deliverable'}:
            reasons.append('收件地址验证状态未知或未通过')
        if suppressed:
            blockers.append('客户已标记不联系或存在抑制记录')
        elif suppression not in {'clear', 'not_suppressed'}:
            reasons.append('尚无已核实的抑制检查结果')
        if profile.get('stale'):
            blockers.append('客户分析已过期')
        attachments = []
        if not draft:
            blockers.append('尚无已保存邮件草稿')
        else:
            if draft.get('status') != 'draft':
                blockers.append('邮件不是可审核草稿，或发送结果尚未确认')
            for key, label in [('to', '收件人'), ('subject', '主题'), ('body_en', '英文正文'), ('body_zh', '中文对照')]:
                if not str(draft.get(key) or '').strip():
                    blockers.append('缺少' + label)
            if not draft.get('attachments'):
                blockers.append('缺少实际附件')
            for attachment in draft.get('attachments') or []:
                try:
                    data = drafts._attachment_bytes(attachment)
                    sha = hashlib.sha256(data).hexdigest()
                    attachments.append({'metadata': attachment, 'sha256': sha})
                    if not data or (attachment.get('sha256') and attachment['sha256'] != sha):
                        blockers.append('附件内容已变化或为空')
                except (ValueError, OSError, KeyError):
                    attachments.append({'metadata': attachment, 'unavailable': True})
                    blockers.append('实际附件无法读取')
        checks = None
        checker = getattr(self.app,'outreach_checks',None)
        if checker and draft:
            checks=checker.inspect(oid,draft,batch_ids=batch_ids,refresh=False)
            reasons.extend(item['message'] for item in checks.get('reasons',[]))
            if checks.get('status')=='blocked':
                blockers.extend(item['message'] for item in checks.get('reasons',[]) if item.get('status')=='blocked')
        guard = {'crm_sha':(checks.get('crm') or {}).get('sha256'),
                 'codes':sorted(item.get('code','') for item in checks.get('reasons',[])),
                 'duplicates':checks.get('duplicates',[]),
                 'mail_state':(checks.get('mail') or {}).get('state'),
                 'mail_events':(checks.get('mail') or {}).get('events',[]),
                 'inbound':(checks.get('mail') or {}).get('inbound_count'),
                 'outbound':(checks.get('mail') or {}).get('outbound_count')} if checks else {}
        guard['shared_suppressed'] = shared_suppressed
        fingerprint = _digest({'object': obj, 'profile_revision': profile.get('revision'),
                               'draft': draft, 'attachments': attachments,'checks':guard})
        stale = bool(entry.get('review_fingerprint')) and entry['review_fingerprint'] != fingerprint
        if stale:
            reasons.append('客户资料、邮件或实际附件已变化，请重新审核')
        item_revision=_digest({'entry':entry,'fingerprint':fingerprint})
        return {**entry, 'review_stale': stale, 'fingerprint': fingerprint,'item_revision':item_revision,
                'customer': {'title': obj.get('title', ''), 'kind': obj['kind'],
                             'source': obj.get('source', ''), 'source_type': obj.get('source_type', 'local'),
                             'customer_type':record.get('business_category') or '',
                             'summary': record.get('business_summary') or obj.get('summary', ''),
                             'country': (profile.get('cleaned') or {}).get('country') or record.get('country') or ''},
                'evidence':evidence,'recommended_products':(profile.get('analysis') or {}).get('product_fit') or [],
                'checks':checks,
                'draft': ({k: draft.get(k) for k in ('version', 'status', 'to', 'subject')} |
                          {'has_body_en': bool(draft.get('body_en')), 'has_body_zh': bool(draft.get('body_zh')),
                           'attachment_count': len(draft.get('attachments') or [])}) if draft else None,
                'quality': {'status': 'blocked' if blockers else 'reviewable', 'reasons': blockers+reasons,
                            'source_state': source_state, 'contact_state': contact_state,
                            'suppression_state': 'suppressed' if suppressed else suppression,
                            'send_ready': False}}

    def _view(self, batch, q='', review_state=''):
        _text(q, 300)
        if review_state and review_state not in REVIEW_STATES:
            raise ValueError('审核筛选无效')
        ids = [e['object_id'] for e in batch['items']]
        items = [self._item(e,ids) for e in batch['items']]
        revision = _digest({'version': batch['version'], 'items': [(e['object_id'], e['fingerprint']) for e in items]})
        counts = {'total': len(items), **{s: sum(e['review_state'] == s for e in items) for s in sorted(REVIEW_STATES)},
                  'stale': sum(e['review_stale'] for e in items),
                  'blocked': sum(e['quality']['status'] == 'blocked' for e in items)}
        selected = [e for e in items if (not review_state or e['review_state'] == review_state) and
                    (not q.strip() or q.strip().casefold() in json.dumps(e, ensure_ascii=False).casefold())]
        return {k: v for k, v in batch.items() if k not in {'items', 'version'}} | {
            'revision': revision, 'counts': counts, 'items': selected}

    def get(self, batch_id, q='', review_state=''):
        with self.app.lock:
            return self._view(self._load(batch_id), q, review_state)

    def list_batches(self):
        with self.app.lock:
            batches = [json.loads(r[0]) for r in self.app.db.execute('SELECT data FROM customer_batches ORDER BY rowid DESC')]
            return {'items': [{k: v for k, v in self._view(b).items() if k != 'items'} for b in batches]}

    def workstream_links(self):
        """Read only batch identity and membership for the workstream projection."""
        with self.app.lock:
            rows = self.app.db.execute('SELECT id,data FROM customer_batches ORDER BY rowid DESC').fetchall()
        items = []
        for batch_id, raw in rows:
            batch = json.loads(raw)
            if not isinstance(batch, dict) or batch.get('id') != batch_id or not isinstance(batch.get('items'), list):
                raise ValueError('客户批次关联资料不可读')
            ids = [entry.get('object_id') if isinstance(entry, dict) else None for entry in batch['items']]
            if (not isinstance(batch_id, str) or not batch_id or
                    any(not isinstance(oid, str) or not oid for oid in ids) or len(set(ids)) != len(ids)):
                raise ValueError('客户批次关联资料不明确')
            items.append({'id':batch_id, 'title':batch.get('title'), 'updated_at':batch.get('updated_at'),
                          'object_ids':ids})
        return items

    def _ids(self, body):
        ids = body.get('object_ids', [])
        if not isinstance(ids, list) or len(ids) > 500 or any(not isinstance(i, str) or len(i) > 300 for i in ids):
            raise ValueError('每次最多添加500个已有客户')
        ids = list(ids)
        filters = body.get('filters')
        if filters is not None:
            if not isinstance(filters, dict) or set(filters) - {'kind', 'q', 'source_type'}:
                raise ValueError('客户筛选字段无效')
            kind = filters.get('kind', '')
            if kind not in {'', 'customer', 'prospect'}:
                raise ValueError('客户类型筛选无效')
            q = _text(filters.get('q', ''), 300)
            source = _text(filters.get('source_type', ''), 100)
            rows = self.app.business.list_objects(kind=kind, q=q)
            ids += [r['id'] for r in rows if r.get('kind') in {'customer', 'prospect'} and
                    (not source or r.get('source_type', 'unknown') == source)]
        ids = list(dict.fromkeys(ids))
        if len(ids) > 500:
            raise ValueError('每批最多500个客户，请缩小筛选范围')
        for oid in ids:
            self._customer(oid)
        return ids

    @staticmethod
    def _entry(oid):
        return {'object_id': oid, 'review_state': 'pending', 'notes': '', 'change_request': '',
                'review_fingerprint': '', 'reviewed_at': None, 'added_at': _now()}

    def create(self, body):
        if not isinstance(body, dict) or set(body) - {'title', 'target', 'object_ids'}:
            raise ValueError('批次字段无效')
        title = _text(body.get('title', ''), 200).strip()
        if not title:
            raise ValueError('请填写批次名称')
        target = _text(body.get('target', ''), 2000)
        with self._write():
            batch = {'id': uuid4().hex, 'title': title, 'target': target, 'created_at': _now(),
                     'items': [self._entry(oid) for oid in self._ids(body)]}
            self._put(batch)
        return self.get(batch['id'])

    def _current(self, batch_id, revision):
        batch = self._load(batch_id)
        if not isinstance(revision, str) or not revision or revision != self._view(batch)['revision']:
            raise WorkspaceConflict('批次、客户或草稿已变化，请刷新后重新审核')
        return batch

    def add_items(self, batch_id, body):
        if not isinstance(body, dict) or set(body) - {'revision', 'object_ids', 'filters'}:
            raise ValueError('批次成员字段无效')
        with self._write():
            batch = self._current(batch_id, body.get('revision'))
            existing = {e['object_id'] for e in batch['items']}
            batch['items'] += [self._entry(oid) for oid in self._ids(body) if oid not in existing]
            if len(batch['items']) > 500:
                raise ValueError('每批最多500个客户')
            self._put(batch)
        return self.get(batch_id)

    def remove_items(self, batch_id, body):
        """Remove batch references only; original customers and suppressions remain."""
        if not isinstance(body,dict) or set(body)!={'revision','object_ids'}:
            raise ValueError('移除批次客户的字段无效')
        ids=body.get('object_ids')
        if not isinstance(ids,list) or not ids or len(ids)>500 or any(not isinstance(i,str) for i in ids) or len(set(ids))!=len(ids):
            raise ValueError('请选择要从本批次移除的客户')
        with self._write():
            batch=self._current(batch_id,body.get('revision'))
            existing={item['object_id'] for item in batch['items']}
            if not set(ids).issubset(existing):raise ValueError('所选客户不在本批次内')
            batch['items']=[item for item in batch['items'] if item['object_id'] not in set(ids)]
            self._put(batch)
        return self.get(batch_id)

    def review_item(self, batch_id, object_id, body):
        if not isinstance(body, dict) or set(body) - {'revision', 'item_revision', 'review_state', 'notes', 'change_request', 'draft_version'}:
            raise ValueError('审核字段无效')
        state = body.get('review_state')
        if state not in REVIEW_STATES:
            raise ValueError('审核状态无效')
        with self._write():
            batch = self._load(batch_id)
            entry = next((e for e in batch['items'] if e['object_id'] == object_id), None)
            if entry is None:
                raise ValueError('客户不在该批次中')
            if 'item_revision' in body:
                actual=self._item(entry,[item['object_id'] for item in batch['items']])['item_revision']
                if not isinstance(body['item_revision'],str) or body['item_revision']!=actual:
                    raise WorkspaceConflict('本客户或其草稿已变化，请重新读取后审核')
            elif not isinstance(body.get('revision'),str) or body['revision']!=self._view(batch)['revision']:
                raise WorkspaceConflict('批次、客户或草稿已变化，请刷新后重新审核')
            # A refreshed review deliberately replaces an old fingerprint.
            live = self._item({**entry, 'review_fingerprint': ''},[item['object_id'] for item in batch['items']])
            if state == 'approved':
                if live['quality']['status'] != 'reviewable':
                    raise ValueError('尚不能通过审核：' + '；'.join(live['quality']['reasons']))
                if body.get('draft_version') != live['draft']['version']:
                    raise WorkspaceConflict('请先读取当前邮件版本，再确认审核')
            for key in ('notes', 'change_request'):
                if key in body:
                    entry[key] = _text(body[key], 10000)
            entry.update(review_state=state, reviewed_at=_now(),
                         review_fingerprint=live['fingerprint'] if state == 'approved' else '')
            if state == 'do_not_contact':
                suppress_contact(self.app,object_id,batch_id)
            self._put(batch)
        return self.get(batch_id)
