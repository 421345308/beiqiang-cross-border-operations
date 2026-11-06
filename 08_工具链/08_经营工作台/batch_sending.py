"""Explicit, expiring, single-use batch confirmations over existing Gmail sends.

Plans contain references, reviewed fingerprints and receipts, never copied email
bodies. All network checks happen outside SQLite transactions. Interrupted plans
remain non-replayable and require manual reconciliation of their Gmail records.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from email.utils import getaddresses
from uuid import uuid4

from gmail_drafts import SendRejected
from gmail_mailbox import normalize_email
from workspaces import WorkspaceConflict

PLAN_TTL_SECONDS = 300


def _now():
    return datetime.now(timezone.utc)


class BatchSending:
    def __init__(self, app):
        self.app = app
        with app.lock:
            app.db.execute('CREATE TABLE IF NOT EXISTS batch_send_plans (id TEXT PRIMARY KEY,data TEXT NOT NULL)')
            app.db.execute('CREATE TABLE IF NOT EXISTS batch_recipient_claims '
                '(account TEXT NOT NULL, recipient TEXT NOT NULL, status TEXT NOT NULL, '
                'plan_id TEXT NOT NULL, object_id TEXT NOT NULL, message_id TEXT, gmail_id TEXT, '
                'updated_at TEXT NOT NULL, PRIMARY KEY(account,recipient))')
            self._backfill_recipient_claims()
            app.db.commit()
        # Do not mutate another live worker's plan at startup. running/sending
        # always block replay, including after a process interruption.

    @staticmethod
    def _recipient_key(draft):
        pairs = getaddresses([str(draft.get('to') or '')])
        if len(pairs) != 1 or not pairs[0][1]:
            raise ValueError('批次发送仅允许一个准确收件地址')
        return normalize_email(draft.get('account')), normalize_email(pairs[0][1])

    def _backfill_recipient_claims(self):
        """Preserve pre-migration sent/uncertain plan facts; never reopen them."""
        for raw, in self.app.db.execute('SELECT data FROM batch_send_plans').fetchall():
            plan = json.loads(raw)
            for item in plan.get('items', []):
                if item.get('status') not in {'sending','sent','unknown'}:
                    continue
                draft = self.app.gmail_drafts._saved(item['object_id']) or {}
                account = item.get('account') or draft.get('account')
                try:
                    account, recipient = self._recipient_key({'account':account,'to':item.get('to')})
                except ValueError:
                    continue
                self.app.db.execute('INSERT OR IGNORE INTO batch_recipient_claims VALUES (?,?,?,?,?,?,?,?)',
                    (account,recipient,item['status'],plan['id'],item['object_id'],
                     item.get('message_id'),item.get('gmail_id'),_now().isoformat()))

    def _recipient_claim(self, account, recipient):
        with self.app.lock:
            return self.app.db.execute('SELECT status,plan_id,object_id FROM batch_recipient_claims '
                                       'WHERE account=? AND recipient=?',(account,recipient)).fetchone()

    def _claim_recipient(self, draft, plan_id, object_id):
        """Caller is inside Gmail's final SQLite claim transaction."""
        account, recipient = self._recipient_key(draft)
        if self._recipient_claim(account,recipient):
            raise WorkspaceConflict('同一发件账号已对该地址认领过批次发送，请先核对已有发送结果')
        self.app.db.execute('INSERT INTO batch_recipient_claims VALUES (?,?,?,?,?,?,?,?)',
                           (account,recipient,'sending',plan_id,object_id,None,None,_now().isoformat()))

    @contextmanager
    def _write(self):
        with self.app.lock:
            if self.app.db.in_transaction:
                raise RuntimeError('批次发送不能嵌入已有事务')
            self.app.db.execute('BEGIN IMMEDIATE')
            try:
                yield
                self.app.db.commit()
            except BaseException:
                self.app.db.rollback()
                raise

    def _put(self, plan):
        plan['updated_at'] = _now().isoformat()
        self.app.db.execute('INSERT OR REPLACE INTO batch_send_plans VALUES (?,?)',
                            (plan['id'], json.dumps(plan, ensure_ascii=False)))

    def get(self, plan_id):
        with self.app.lock:
            row = self.app.db.execute('SELECT data FROM batch_send_plans WHERE id=?', (plan_id,)).fetchone()
        if not row:
            raise ValueError('发送确认计划不存在')
        return json.loads(row[0])

    def _local(self, batch_id, snapshot, batch_version=None):
        """Local-only equality guard, also safe inside Gmail's claim transaction."""
        batch = self.app.customer_batches._load(batch_id)
        if batch_version is not None and batch['version'] != batch_version:
            raise WorkspaceConflict('批次审查已变化，请重新预检和确认')
        entry = next((e for e in batch['items'] if e['object_id'] == snapshot['object_id']), None)
        if not entry or entry.get('review_state') != 'approved' or not entry.get('review_fingerprint'):
            raise WorkspaceConflict('客户尚未通过逐封审核')
        oid = snapshot['object_id']
        profile = self.app.customer_workspace.profile(oid)
        draft = self.app.gmail_drafts._saved(oid)
        if not draft or draft.get('status') != 'draft':
            raise WorkspaceConflict('邮件已发送、在发送中或结果未知')
        if not draft.get('attachments') or any(not str(draft.get(k) or '').strip() for k in ('to','subject','body_en','body_zh')):
            raise WorkspaceConflict('邮件正文、中文对照、收件人或附件不完整')
        # The canonical item fingerprint includes the current local CRM SHA,
        # cached mail events and reread attachment bytes. _item calls only
        # inspect(refresh=False): no Gmail network in this transaction.
        live = self.app.customer_batches._item(entry,[e['object_id'] for e in batch['items']])
        fingerprint = live['fingerprint']
        if live['quality']['status'] == 'blocked':
            raise WorkspaceConflict('本地资料或实际附件检查未通过')
        if (fingerprint != entry['review_fingerprint'] or fingerprint != snapshot['fingerprint'] or
                draft.get('version') != snapshot['draft_version'] or draft.get('to') != snapshot['to'] or
                draft.get('subject') != snapshot['subject']):
            raise WorkspaceConflict('客户、邮件、收件人或附件已变化，请重新审核')
        if profile.get('stale'):
            raise WorkspaceConflict('客户分析已过期')
        return batch, draft

    def _checks(self, oid, draft, ids):
        try:
            checks = self.app.outreach_checks.inspect(oid, draft, refresh=True, batch_ids=ids)
            if not isinstance(checks, dict):
                raise ValueError('invalid checks')
            crm = checks.get('crm') or {}
            mail = checks.get('mail') or {}
            bounce = checks.get('bounce') or {}
            valid = (checks.get('status') == 'clear' and checks.get('can_auto_send') is True and
                     checks.get('object_id') == oid and checks.get('draft_version') == draft['version'] and
                     not checks.get('reasons') and not checks.get('duplicates') and
                     crm.get('status') == '已读取' and bool(crm.get('sha256')) and bool(crm.get('coverage')) and
                     mail.get('refreshed') is True and mail.get('state') in {'ready','connected'} and
                     bool(mail.get('last_success_at')) and mail.get('history_limited') is False and
                     mail.get('thread_lookup_incomplete') is False and bounce.get('status') == 'clear' and
                     isinstance(bounce.get('coverage'),dict) and bounce['coverage'].get('complete') is True)
            return checks, valid
        except Exception:
            return {'status':'unknown','reasons':[{'code':'check_failed','message':'本次真实发送防护检查未完成','status':'unknown'}]}, False

    def preflight(self, batch_id, body):
        if not isinstance(body, dict) or set(body) - {'revision','object_ids'}:
            raise ValueError('预检参数无效')
        ids = body.get('object_ids')
        if not isinstance(ids, list) or not ids or len(ids) > 500 or any(not isinstance(i,str) for i in ids) or len(set(ids)) != len(ids):
            raise ValueError('请选择1至500个不同的已审核客户')
        view = self.app.customer_batches.get(batch_id)
        if not body.get('revision') or body['revision'] != view['revision']:
            raise WorkspaceConflict('批次已变化，请刷新后预检')
        batch = self.app.customer_batches._load(batch_id)
        all_ids = [e['object_id'] for e in batch['items']]
        rows = {e['object_id']:e for e in view['items']}
        if any(oid not in rows for oid in ids):
            raise ValueError('所选客户不在本批次内')
        items, snapshots = [], []
        for oid in ids:
            row = rows[oid]
            draft = row.get('draft') or {}
            snapshot = {'object_id':oid,'fingerprint':row.get('fingerprint'),
                        'draft_version':draft.get('version'),'to':draft.get('to'),'subject':draft.get('subject')}
            reasons = []
            checks = {'status':'unknown','reasons':[]}
            try:
                if row.get('review_state') != 'approved' or row.get('review_stale') is not False:
                    raise WorkspaceConflict('客户尚未通过当前版本的逐封审核')
                _, saved = self._local(batch_id, snapshot, batch['version'])
                account, recipient = self._recipient_key(saved)
                snapshot.update(account=account,recipient=recipient)
                if self._recipient_claim(account,recipient):
                    reasons.append('同一发件账号已对该地址认领批次发送，需先人工核对')
                checks, valid = self._checks(oid, saved, all_ids)
                if not valid:
                    reasons.append('CRM、邮件、退信或重复检查尚未全部通过')
                # Network reads may overlap a local edit. Verify again afterwards.
                self._local(batch_id, snapshot, batch['version'])
            except (ValueError, WorkspaceConflict, OSError, KeyError):
                reasons.append('客户审核、邮件或实际附件已变化或不完整')
            item = {k:v for k,v in snapshot.items() if k != 'fingerprint'}
            item.update(checks=checks, can_confirm=not reasons, reasons=reasons)
            items.append(item)
            snapshots.append(snapshot)
        can_confirm = all(e['can_confirm'] for e in items)
        result = {'batch_id':batch_id,'revision':view['revision'],'object_ids':ids,'items':items,
                  'can_confirm':can_confirm,'plan_id':None,'expires_at':None}
        if can_confirm:
            now = _now()
            plan = {'id':uuid4().hex,'batch_id':batch_id,'batch_version':batch['version'],
                    'object_ids':ids,'batch_object_ids':all_ids,'status':'ready','created_at':now.isoformat(),
                    'expires_at':(now+timedelta(seconds=PLAN_TTL_SECONDS)).isoformat(),
                    'items':[{**s,'status':'pending'} for s in snapshots]}
            plan['plan_id'] = plan['id']
            with self._write():
                for snapshot in snapshots:
                    self._local(batch_id, snapshot, batch['version'])
                self._put(plan)
            result.update(plan_id=plan['id'],expires_at=plan['expires_at'])
        return result

    def _record(self, plan_id, owner, oid, status, *, release_recipient=False, **values):
        with self._write():
            plan = self.get(plan_id)
            if plan.get('owner') != owner or plan['status'] != 'running':
                raise WorkspaceConflict('发送计划已变化，请人工核对')
            entry = next(e for e in plan['items'] if e['object_id'] == oid)
            entry.update(status=status, **values)
            if status in {'sent','unknown'}:
                self.app.db.execute('UPDATE batch_recipient_claims SET status=?,message_id=?,gmail_id=?,updated_at=? '
                    'WHERE plan_id=? AND object_id=?',
                    (status,values.get('message_id'),values.get('gmail_id'),_now().isoformat(),plan_id,oid))
            elif release_recipient:
                # Only an explicit provider rejection can free this plan's
                # still-sending key. A normal pre-claim skip cannot free others.
                self.app.db.execute("DELETE FROM batch_recipient_claims WHERE plan_id=? AND object_id=? AND status='sending'",
                                    (plan_id,oid))
            self._put(plan)

    def send(self, batch_id, body):
        if not isinstance(body, dict) or set(body) - {'plan_id','confirmed'} or body.get('confirmed') is not True or not isinstance(body.get('plan_id'),str):
            raise ValueError('请明确确认本次收件人、主题、正文及实际附件后再发送')
        owner = uuid4().hex
        with self._write():
            plan = self.get(body['plan_id'])
            if plan['batch_id'] != batch_id:
                raise ValueError('发送计划不属于本批次')
            if plan['status'] != 'ready':
                raise WorkspaceConflict('发送计划已被使用或中断，请先对账；不能重复发送')
            if datetime.fromisoformat(plan['expires_at']) <= _now():
                raise WorkspaceConflict('发送确认已过期，请重新预检')
            plan.update(status='running',owner=owner,started_at=_now().isoformat())
            self._put(plan)
        stopped = False
        for snapshot in plan['items']:
            oid = snapshot['object_id']
            claimed = False
            try:
                _, draft = self._local(batch_id,snapshot,plan['batch_version'])
                checks, valid = self._checks(oid,draft,plan['batch_object_ids'])
                if not valid:
                    self._record(plan['id'],owner,oid,'not_sent',reason='本次发送防护检查未通过',checks=checks)
                    continue
                def before_claim(current):
                    nonlocal claimed
                    active = self.get(plan['id'])
                    if active.get('owner') != owner or active['status'] != 'running':
                        raise WorkspaceConflict('发送计划已变化')
                    # Expiry limits when the user may confirm, not how long
                    # fresh per-recipient safety checks may take after claim.
                    self._local(batch_id,snapshot,plan['batch_version'])
                    item = next(e for e in active['items'] if e['object_id'] == oid)
                    if item['status'] != 'pending':
                        raise WorkspaceConflict('本客户已认领发送，请先对账')
                    self._claim_recipient(current,plan['id'],oid)
                    item.update(status='sending',claimed_at=_now().isoformat())
                    self._put(active)  # Same SQLite transaction as Gmail's claim.
                    claimed = True
                sent = self.app.gmail_drafts.send(oid,snapshot['draft_version'],before_claim=before_claim)
                if sent and sent.get('status') == 'sent':
                    self._record(plan['id'],owner,oid,'sent',gmail_id=sent.get('gmail_id'),message_id=sent.get('message_id'),sent_at=sent.get('sent_at'))
                else:
                    self._record(plan['id'],owner,oid,'unknown',reason='发送结果未知，请先人工对账',
                                 message_id=(sent or {}).get('message_id'))
                    stopped = True
            except SendRejected:
                current = self.app.gmail_drafts._saved(oid)
                if claimed and current and current.get('status') == 'draft':
                    self._record(plan['id'],owner,oid,'not_sent',release_recipient=True,reason='Gmail明确拒绝，未接受邮件')
                elif claimed:
                    self._record(plan['id'],owner,oid,'unknown',reason='拒绝回读未确认，请先人工对账',message_id=(current or {}).get('message_id'))
                    stopped = True
                else:
                    self._record(plan['id'],owner,oid,'not_sent',reason='发送认领前被拒绝，未调用发送')
            except Exception:
                # A claimed send can fail after Google accepted it or after a
                # local receipt commit; never infer unsent from an exception.
                current = self.app.gmail_drafts._saved(oid)
                if claimed and current and current.get('status') == 'sent':
                    self._record(plan['id'],owner,oid,'sent',gmail_id=current.get('gmail_id'),message_id=current.get('message_id'),sent_at=current.get('sent_at'))
                elif claimed:
                    self._record(plan['id'],owner,oid,'unknown',reason='发送认领后结果不明，请先人工对账',message_id=(current or {}).get('message_id'))
                    stopped = True
                else:
                    self._record(plan['id'],owner,oid,'not_sent',reason='发送前资料或审核已变化，未调用发送')
            if stopped:
                break
        with self._write():
            current = self.get(plan['id'])
            if current.get('owner') != owner or current['status'] != 'running':
                raise WorkspaceConflict('发送计划已变化，请人工核对')
            current.update(status='stopped_unknown' if stopped else 'completed',finished_at=_now().isoformat())
            self._put(current)
        return self.get(plan['id'])
