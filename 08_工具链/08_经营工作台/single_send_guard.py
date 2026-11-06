"""Explicit single-message preflight and one-use confirmation; no automatic sends.

Server/UI contract: preflight(object_id, version), show its exact recipient,
subject, complete existing draft and attachments, then call send with that
plan_id and confirmed=True. Any meaningful change requires another preflight.
Unknown outcomes remain consumed and require Gmail Message-ID reconciliation.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from email.utils import getaddresses
import hashlib
import json
import re
from uuid import uuid4

from gmail_drafts import SendRejected
from gmail_mailbox import normalize_email
from customer_batches import contact_suppressed
from workspaces import WorkspaceConflict

TTL_SECONDS = 300


def _now():
    return datetime.now(timezone.utc)


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _addresses(value):
    return {a.strip().lower() for _, a in getaddresses([str(value or '')]) if '@' in a}


def _subject(value):
    return re.sub(r'^(?:\s*re\s*:\s*)+', '', value or '', flags=re.I).strip().casefold()


class SingleSendGuard:
    def __init__(self, app, *, clock=_now):
        self.app, self.clock = app, clock
        with app.lock:
            if app.db.in_transaction:
                raise RuntimeError('逐封发送初始化不能嵌入已有事务')
            app.db.execute('CREATE TABLE IF NOT EXISTS single_send_plans (id TEXT PRIMARY KEY,data TEXT NOT NULL)')
            app.db.execute('CREATE TABLE IF NOT EXISTS single_reply_claims (account TEXT,recipient TEXT,reply_message_id TEXT,plan_id TEXT,status TEXT,PRIMARY KEY(account,recipient,reply_message_id))')
            app.db.execute('CREATE TABLE IF NOT EXISTS batch_recipient_claims (account TEXT NOT NULL,recipient TEXT NOT NULL,status TEXT NOT NULL,plan_id TEXT NOT NULL,object_id TEXT NOT NULL,message_id TEXT,gmail_id TEXT,updated_at TEXT NOT NULL,PRIMARY KEY(account,recipient))')
            app.db.commit()

    @contextmanager
    def _write(self):
        with self.app.lock:
            db = self.app.db
            if db.in_transaction:
                raise RuntimeError('逐封发送不能嵌入已有事务')
            db.execute('BEGIN IMMEDIATE')
            try:
                yield
                db.commit()
            except BaseException:
                if db.in_transaction:
                    db.rollback()
                raise

    def _put(self, plan):
        plan['updated_at'] = self.clock().isoformat()
        self.app.db.execute('INSERT OR REPLACE INTO single_send_plans VALUES (?,?)', (plan['id'], json.dumps(plan, ensure_ascii=False)))

    def get(self, plan_id):
        with self.app.lock:
            row = self.app.db.execute('SELECT data FROM single_send_plans WHERE id=?', (plan_id,)).fetchone()
        if not row:
            raise ValueError('逐封发送确认计划不存在')
        return json.loads(row[0])

    def _ids(self):
        return sorted({o['id'] for o in self.app.business.list_objects() if o.get('kind') in {'customer', 'prospect'}})

    def _local(self, oid, version, ids):
        draft = self.app.gmail_drafts._saved(oid)
        if not draft or draft.get('version') != version or draft.get('status') != 'draft':
            raise WorkspaceConflict('当前草稿已变化、已发送或结果未知')
        if any(not str(draft.get(k) or '').strip() for k in ('account','to','subject','body_en','body_zh')):
            raise ValueError('发件账号、收件人、主题和完整中英文正文不能为空')
        pairs = getaddresses([draft['to']])
        if len(pairs) != 1 or not pairs[0][1]:
            raise ValueError('只允许一个准确收件人')
        account, recipient = normalize_email(draft['account']), normalize_email(pairs[0][1])
        with self.app.lock:
            if contact_suppressed(self.app, oid, recipient):
                raise WorkspaceConflict('客户或地址已标记不联系')
        if account != self.app.gmail_drafts._account():
            raise WorkspaceConflict('发件账号已变化')
        obj = self.app.business.get_object(oid)
        profile = self.app.customer_workspace.profile(oid)
        if obj.get('kind') not in {'customer','prospect'} or profile.get('stale'):
            raise WorkspaceConflict('客户身份或分析版本需要重新核对')
        attachments = []
        for a in draft.get('attachments', []):
            raw = self.app.gmail_drafts._attachment_bytes(a)
            if not raw:
                raise ValueError('实际附件不能为空')
            attachments.append({'name':a['name'],'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
        local = self.app.outreach_checks.inspect(oid, draft, refresh=False, batch_ids=ids)
        if any(r.get('status') == 'blocked' for r in local.get('reasons', [])) or local.get('duplicates'):
            raise WorkspaceConflict('客户、退订拒绝、退信或重复检查未通过')
        crm = local.get('crm') or {}
        manual = local.get('crm_manual_review') or {}
        source = {k:profile.get(k) for k in ('source_hash','derived_source_hash','cleaned','analysis','provenance','updated_at','operator_context','translation_zh')}
        binding = {'object_id':oid,'draft_version':version,'account':account,'to':recipient,
            'subject':draft['subject'],'draft_fingerprint':_hash(draft),'attachments':attachments,
            'source_fingerprint':_hash({'object':obj,'profile':source}),
            'customer_revision':profile.get('revision'),'crm_sha256':crm.get('sha256'),
            'crm_review_id':manual.get('review_id') if manual.get('applied') else None}
        binding['fingerprint'] = _hash(binding)
        return binding, draft

    def _reply_proof(self, oid, draft):
        """Read-only proof of a current, unresponded-to human inbound message."""
        if not draft.get('thread_id') or not draft.get('reply_message_id'):
            return None
        known = self.app.outreach_checks.identity_emails(self.app.business.get_object(oid))
        mailbox = getattr(self.app.gmail, '_mailbox', None)
        if not mailbox or not known:
            return None
        context = mailbox.context(sorted(known), force=True)
        status = context.get('status') or {}
        if (status.get('state') not in {'ready','connected'} or not status.get('last_success_at')
            or status.get('history_limited') is not False or status.get('thread_lookup_incomplete') is not False
            or (status.get('shared_observation') or {}).get('state') != 'complete'
            or str(status.get('account_email') or '').lower() != draft['account'].lower()):
            return None
        messages = context.get('messages') or []
        if any(not isinstance(m.get('body'),str) or m.get('body_truncated') for m in messages):
            return None
        thread = [m for m in messages if str(m.get('thread_id') or '') == str(draft['thread_id']) and m.get('mail_kind') == 'conversation']
        if not thread:
            return None
        try:
            dated = [(datetime.fromisoformat(m['sent_at'].replace('Z','+00:00')),m) for m in thread]
            if any(at.tzinfo is None for at,_ in dated):
                return None
            latest = max(at for at,_ in dated)
        except (KeyError,ValueError,TypeError):
            return None
        targets = [m for at,m in dated if at == latest]
        if len(targets) != 1:
            return None
        mail = targets[0]
        if (mail.get('direction') != 'inbound' or mail.get('rfc_message_id') != draft['reply_message_id']
            or not re.fullmatch(r'<[^<>\s]+>',draft['reply_message_id'])
            or not _subject(mail.get('subject')) or _subject(mail.get('subject')) != _subject(draft['subject'])
            or _subject(draft.get('thread_subject')) != _subject(mail.get('subject'))):
            return None
        senders = _addresses(mail.get('from'))
        recipients = set().union(*(_addresses(mail.get(k)) for k in ('to','cc','bcc')))
        associated = set(mail.get('customer_emails') or []) & known
        reply_addresses = _addresses(mail.get('reply_to')) or senders
        if (draft['account'].lower() not in recipients or not (senders & known or associated)
            or _addresses(draft['to']) != _addresses(draft['to']) & reply_addresses):
            return None
        return {'thread_id':str(draft['thread_id']),'reply_message_id':draft['reply_message_id'],
                'message_id':mail.get('id'),'subject':_subject(mail.get('subject'))}

    def _checks(self, oid, draft, ids):
        checks = self.app.outreach_checks.inspect(oid, draft, refresh=True, batch_ids=ids)
        before, _ = self._local(oid, draft['version'], ids)
        need_proof = bool(draft.get('thread_id') or draft.get('reply_message_id'))
        proof = self._reply_proof(oid,draft) if need_proof else None
        after, _ = self._local(oid,draft['version'],ids)
        reasons = list(checks.get('reasons') or [])
        if before != after:
            reasons.append({'code':'mail_changed_during_checks','status':'unknown','message':'核对期间客户或邮箱观察已变化，请重新预检'})
        if need_proof and not proof:
            reasons.append({'code':'reply_context_unverified','status':'unknown','message':'未核到当前草稿所回复的最新完整客户入站邮件'})
        if proof:
            reasons = [r for r in reasons if r.get('code') != 'previously_contacted']
        if not proof and not draft.get('attachments'):
            reasons.append({'code':'attachment_required','status':'unknown','message':'首次商务介绍须准备实际附件'})
        crm, mail, bounce = (checks.get(k) or {} for k in ('crm','mail','bounce'))
        manual = checks.get('crm_manual_review') or {}
        crm_ok = crm.get('stop_state') != '未知' or (manual.get('eligible') is True and manual.get('applied') is True and bool(manual.get('review_id')))
        valid = (checks.get('object_id') == oid and checks.get('draft_version') == draft['version']
            and checks.get('status') in {'clear','unknown'} and not reasons and not checks.get('duplicates')
            and crm.get('status') == '已读取' and bool(crm.get('sha256')) and bool(crm.get('coverage')) and crm_ok
            and mail.get('refreshed') is True and mail.get('state') in {'ready','connected'}
            and bool(mail.get('last_success_at')) and mail.get('history_limited') is False
            and mail.get('thread_lookup_incomplete') is False and bounce.get('status') == 'clear'
            and isinstance(bounce.get('coverage'),dict) and bounce['coverage'].get('complete') is True)
        if not valid and not reasons:
            reasons.append({'code':'coverage_unknown','status':'unknown','message':'实际读取、CRM或退信覆盖未全部确认'})
        return checks, reasons, proof, after

    def _recipient_available(self, binding, proof):
        row = self.app.db.execute('SELECT status FROM batch_recipient_claims WHERE account=? AND recipient=?', (binding['account'],binding['to'])).fetchone()
        if row and (not proof or row[0] != 'sent'):
            raise WorkspaceConflict('该地址已有首次发送或未确认结果，请先对账')
        if proof and self.app.db.execute('SELECT 1 FROM single_reply_claims WHERE account=? AND recipient=? AND reply_message_id=?', (binding['account'],binding['to'],proof['reply_message_id'])).fetchone():
            raise WorkspaceConflict('该客户入站邮件已有回复发送认领，请先对账')

    def preflight(self, object_id, version):
        ids = self._ids()
        result = {'object_id':object_id,'version':version,'can_confirm':False,'plan_id':None,'expires_at':None,'reasons':[]}
        try:
            initial,draft = self._local(object_id,version,ids)
            checks,reasons,proof,binding = self._checks(object_id,draft,ids)
            # Mailbox observations may change during the fresh read; source,
            # actual draft/attachments and CRM must still be the same inputs.
            stable = ('draft_fingerprint','source_fingerprint','crm_sha256','crm_review_id')
            if any(initial[k] != binding[k] for k in stable):
                raise WorkspaceConflict('客户、邮件或CRM在预检期间变化')
            result.update(checks=checks,reasons=reasons,account=binding['account'],to=binding['to'],
                          subject=binding['subject'],attachments=binding['attachments'],reply_proof=proof)
            if reasons:
                return result
            with self._write():
                current,_ = self._local(object_id,version,ids)
                if current != binding:
                    raise WorkspaceConflict('预检资料已变化')
                self._recipient_available(binding,proof)
                now=self.clock();plan={'id':uuid4().hex,'object_id':object_id,'version':version,
                    'status':'ready','binding':binding,'object_ids':ids,'reply_proof':proof,
                    'created_at':now.isoformat(),'expires_at':(now+timedelta(seconds=TTL_SECONDS)).isoformat()}
                self._put(plan)
            return {**result,'can_confirm':True,'plan_id':plan['id'],'expires_at':plan['expires_at']}
        except (ValueError,WorkspaceConflict,OSError,KeyError,TypeError):
            result['reasons'].append({'code':'preflight_failed','status':'unknown','message':'当前客户、草稿、附件或实际只读预检未通过，请重新读取核对'})
            return result

    def _record(self, plan_id, owner, status, draft=None, reason=''):
        with self._write():
            plan=self.get(plan_id)
            if plan.get('owner')!=owner or plan['status'] not in {'checking','sending'}:
                raise WorkspaceConflict('逐封发送计划已变化，请对账')
            plan.update(status=status,reason=reason)
            if draft:
                plan.update(message_id=draft.get('message_id'),gmail_id=draft.get('gmail_id'),sent_at=draft.get('sent_at'))
            self._put(plan)
            self.app.db.execute('UPDATE single_reply_claims SET status=? WHERE plan_id=?',(status,plan_id))
            if status=='not_sent':
                self.app.db.execute("DELETE FROM batch_recipient_claims WHERE plan_id=? AND status='sending'",(plan_id,))
                self.app.db.execute('DELETE FROM single_reply_claims WHERE plan_id=?',(plan_id,))
            else:
                self.app.db.execute('UPDATE batch_recipient_claims SET status=?,message_id=?,gmail_id=?,updated_at=? WHERE plan_id=?', (status,(draft or {}).get('message_id'),(draft or {}).get('gmail_id'),self.clock().isoformat(),plan_id))
        return self.get(plan_id)

    def send(self, object_id, version, plan_id, confirmed):
        if confirmed is not True:
            raise ValueError('须明确确认本封收件人、主题、中英文正文和实际附件')
        owner=uuid4().hex
        with self._write():
            plan=self.get(plan_id)
            if plan['object_id']!=object_id or plan['version']!=version:
                raise WorkspaceConflict('确认计划不属于当前客户或草稿')
            if plan['status']!='ready' or datetime.fromisoformat(plan['expires_at'])<=self.clock():
                raise WorkspaceConflict('确认计划已使用、中断或过期，请先对账')
            plan.update(status='checking',owner=owner);self._put(plan)
        try:
            binding,draft=self._local(object_id,version,plan['object_ids'])
            checks,reasons,proof,current=self._checks(object_id,draft,plan['object_ids'])
            if reasons or binding!=plan['binding'] or current!=plan['binding'] or proof!=plan['reply_proof']:
                return self._record(plan_id,owner,'not_sent',reason='发送前实际检查、版本或回复依据已变化')
            def before_claim(actual):
                active=self.get(plan_id)
                if active.get('owner')!=owner or active['status']!='checking' or datetime.fromisoformat(active['expires_at'])<=self.clock():
                    raise WorkspaceConflict('逐封发送确认已变化或过期')
                final,_=self._local(object_id,version,plan['object_ids'])
                if final!=plan['binding'] or self._ids()!=plan['object_ids']:
                    raise WorkspaceConflict('客户、CRM、邮箱观察、收件人或实际附件已变化')
                self._recipient_available(final,proof)
                if proof:
                    self.app.db.execute('INSERT INTO single_reply_claims VALUES (?,?,?,?,?)',(final['account'],final['to'],proof['reply_message_id'],plan_id,'sending'))
                existing=self.app.db.execute('SELECT 1 FROM batch_recipient_claims WHERE account=? AND recipient=?',(final['account'],final['to'])).fetchone()
                if not existing:
                    self.app.db.execute('INSERT INTO batch_recipient_claims VALUES (?,?,?,?,?,?,?,?)',(final['account'],final['to'],'sending',plan_id,object_id,None,None,self.clock().isoformat()))
                active['status']='sending';self._put(active)
            sent=self.app.gmail_drafts.send(object_id,version,before_claim=before_claim)
            return self._record(plan_id,owner,'sent' if sent and sent.get('status')=='sent' else 'unknown',sent,
                reason='' if sent and sent.get('status')=='sent' else '发送结果未知，须先按Message-ID对账，不能重发')
        except Exception as exc:
            # Trust committed state, not a Python flag set inside a rolled-back
            # before_claim callback. An accepted send can fail during receipt IO.
            active=self.get(plan_id);saved=self.app.gmail_drafts._saved(object_id)
            claimed=active['status']=='sending'
            if claimed and saved and saved.get('status')=='sent':
                return self._record(plan_id,owner,'sent',saved)
            if claimed and isinstance(exc,SendRejected) and saved and saved.get('status')=='draft':
                return self._record(plan_id,owner,'not_sent',saved,reason='Gmail明确拒绝且本地未发送状态已回读')
            return self._record(plan_id,owner,'unknown' if claimed else 'not_sent',saved if claimed else None,
                reason='发送认领后结果不明，须先对账' if claimed else '发送前检查或认领失败，未调用发送')
