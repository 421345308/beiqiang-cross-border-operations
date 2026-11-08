"""Evidence-scoped checks and private, narrowly bound manual CRM reviews.

Reads external sources only; never authorizes or sends mail.
"""
from __future__ import annotations

import copy
import hashlib
import importlib
import json
from pathlib import Path
import re
import sys
import threading
from datetime import datetime, timezone
from email.utils import getaddresses
from uuid import uuid4

from gmail_sync import customer_emails
from gmail_mailbox import normalize_email
from workspaces import WorkspaceConflict


def _crm_module():
    directory = Path(__file__).resolve().parents[1] / '01_业务脚本/客户发现助手'
    # Reuse the canonical reader, including workbook hashing and exact identities.
    old = sys.modules.get('core')
    if old is not None and Path(getattr(old, '__file__', '')).resolve() != (directory / 'core.py').resolve():
        raise RuntimeError('CRM dependency name is occupied')
    sys.path.insert(0, str(directory))
    try:
        module = importlib.import_module('crm')
        if Path(module.__file__).resolve() != (directory / 'crm.py').resolve():
            raise RuntimeError('CRM reader name is occupied')
        return module
    finally:
        sys.path.remove(str(directory))


def _record(obj):
    try:
        value = json.loads(obj.get('content') or '{}')
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


def _addresses(value):
    return {address.strip().lower() for _, address in getaddresses([str(value or '')]) if '@' in address}


def _unquoted(body):
    lines = []
    for line in str(body or '').splitlines():
        if re.match(r'\s*(On .{0,200}wrote:|在.{0,200}写道[:：]|-{2,}\s*(Original Message|原始邮件)|From:|发件人[:：])', line, re.I):
            break
        if not line.lstrip().startswith('>'):
            lines.append(line)
    return '\n'.join(lines)


STOP = re.compile(r'\b(?:unsubscribe[ds]?|opt[ -]?out|do not (?:contact|email)|don[’\']t (?:contact|email)|remove (?:me|us|my email)|not interested|stop (?:contacting|emailing|sending))\b|退订|停止联系|不要再(?:联系|发送)|不感兴趣|拒绝联系', re.I)
BOUNCE = re.compile(r'\b(?:EMAIL_INVALID|invalid (?:email|address)|undeliver(?:able|ed)|delivery (?:failed|failure)|user unknown|mailbox (?:unavailable|not found)|hard[ -]?bounce)\b|退信|地址无效', re.I)
STOP_STATES = {'do_not_contact', 'unsubscribed', 'rejected', 'complaint', 'bounced', 'blocked', 'suppressed', '停止联系', '退订', '拒绝联系', '拒绝', '不联系', 'EMAIL_INVALID', 'invalid', 'undeliverable'}


def _crm_stop_text(value):
    """Ignore explicit negative check results, preserving other stop evidence.

    Apply only to CRM operator records, never to a buyer's incoming message.
    Each field is normalized separately so one field cannot negate another.
    """
    return re.sub(r'未发现退信|未停止联系|未拒绝联系|未退订|无退信|'
                  r'\bnot unsubscribed\b|\bno opt[ -]out\b', '', str(value or ''), flags=re.I)


class OutreachChecks:
    def __init__(self, app, *, crm_reader=None):
        self.app = app
        self._reader = crm_reader
        self._module = None
        self._lock = threading.RLock()
        if hasattr(app,'db') and hasattr(app,'lock'):
            with app.lock:
                app.db.execute('CREATE TABLE IF NOT EXISTS outreach_crm_reviews (object_id TEXT PRIMARY KEY,data TEXT NOT NULL)')
                app.db.commit()

    @staticmethod
    def _manual_eligible(crm):
        return (crm.get('status') == '已读取' and bool(crm.get('sha256')) and bool(crm.get('coverage')) and
                crm.get('match_status') == '未匹配' and crm.get('stop_state') == '未知' and
                not crm.get('local_stop') and not crm.get('matches') and not crm.get('match_count'))

    def _manual_binding(self, object_id, draft, crm):
        obj=self.app.business.get_object(object_id)
        profile={}
        if getattr(self.app,'customer_workspace',None):
            profile=self.app.customer_workspace.profile(object_id)
        # Mailbox observations belong to the separate email-review fingerprint.
        # Unrelated mail must not invalidate a human CRM identity/source review.
        source=hashlib.sha256(json.dumps({'object':obj,
            'source_hash':profile.get('source_hash'),'cleaned':profile.get('cleaned'),
            'provenance':profile.get('provenance')},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        pairs=getaddresses([str(draft.get('to') or '')])
        if len(pairs)!=1 or not pairs[0][1]:
            raise ValueError('请先核对准确的单个收件地址')
        binding={'object_id':object_id,'source_fingerprint':source,
            'account':normalize_email(draft.get('account')),'recipient':normalize_email(pairs[0][1]),
            'crm_sha256':crm['sha256']}
        binding['fingerprint']=hashlib.sha256(json.dumps(binding,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        return binding

    def _manual_review(self, object_id, draft, crm):
        result={'eligible':self._manual_eligible(crm),'applied':False,'recorded_at':None}
        if not result['eligible'] or not hasattr(self.app,'db'):
            return result
        try:
            binding=self._manual_binding(object_id,draft,crm)
        except (ValueError,KeyError):
            return result
        with self.app.lock:
            row=self.app.db.execute('SELECT data FROM outreach_crm_reviews WHERE object_id=?',(object_id,)).fetchone()
        if not row:return result
        saved=json.loads(row[0])
        if saved.get('binding')!=binding:
            return {**result,'stale':True,'recorded_at':saved.get('recorded_at')}
        return {**result,'applied':True,'stale':False,'recorded_at':saved['recorded_at'],
                'review_id':saved['review_id'],'evidence':saved['evidence'],
                'note':'CRM原停止状态仍为未知；仅未匹配范围已由负责人按所列依据人工核对。'}

    @staticmethod
    def _review_evidence(evidence):
        if not isinstance(evidence,dict) or set(evidence)!={'aliases','independent_sends','stop_records'}:
            raise ValueError('请分别填写品牌别名、独立发送和停止联系记录的具体核对依据')
        generic=re.compile(r'^(?:ok|done|checked|confirmed|no issues?|all clear|已核对|核对通过|无问题|确认无误|已确认|无记录)[.!。！\s]*$',re.I)
        def text(value,minimum):
            if not isinstance(value,str) or len(value.strip())<minimum or len(value)>4000 or '\x00' in value or generic.fullmatch(value.strip()):
                raise ValueError('核对依据须包含具体查询位置、查询词和结果，不能仅写已核对或无问题')
            return value.strip()
        result={}
        for key in ('aliases','independent_sends','stop_records'):
            item=evidence[key]
            allowed={'checked','locations','findings'} | ({'terms'} if key=='aliases' else set())
            if not isinstance(item,dict) or set(item)!=allowed or item.get('checked') is not True:
                raise ValueError('请明确确认已完成三项核对，并填写其具体依据')
            locations=item.get('locations')
            if not isinstance(locations,list) or not 1<=len(locations)<=10:
                raise ValueError('请列出实际核对的资料或查询位置')
            result[key]={'checked':True,'locations':[text(v,6) for v in locations],
                         'findings':text(item.get('findings'),16)}
            if key=='aliases':
                terms=item.get('terms')
                if not isinstance(terms,list) or not 1<=len(terms)<=20:
                    raise ValueError('请列出实际核对的品牌或法律实体别名')
                result[key]['terms']=[text(v,2) for v in terms]
        return result

    def record_crm_review(self,batch_id,object_id,item_revision,evidence,confirmed):
        """Record a scoped human CRM review, never a send or global exemption."""
        if confirmed is not True:
            raise ValueError('请明确确认已核对品牌别名、独立发送及停止联系记录')
        evidence=self._review_evidence(evidence)
        if not isinstance(item_revision,str) or not item_revision:
            raise ValueError('请先读取本客户的当前审核版本')
        with self.app.lock:
            if self.app.db.in_transaction:raise RuntimeError('人工核对不能嵌入已有事务')
            self.app.db.execute('BEGIN IMMEDIATE')
            try:
                batch=self.app.customer_batches._load(batch_id)
                entry=next((v for v in batch['items'] if v['object_id']==object_id),None)
                if entry is None:raise ValueError('客户不在该批次内')
                live=self.app.customer_batches._item(entry,[v['object_id'] for v in batch['items']])
                if live.get('item_revision')!=item_revision:
                    raise WorkspaceConflict('客户、草稿或CRM已变化，请重新读取后核对')
                draft=self.app.gmail_drafts._saved(object_id)
                if not draft:raise ValueError('请先保存当前邮件草稿')
                checks=self.inspect(object_id,draft,batch_ids=[v['object_id'] for v in batch['items']],refresh=False)
                crm=checks['crm']
                if not self._manual_eligible(crm) or not checks['crm_manual_review']['eligible']:
                    raise ValueError('仅CRM已成功读取且未匹配、停止状态未知时可记录人工核对')
                binding=self._manual_binding(object_id,draft,crm)
                # Source files/workbooks may change outside SQLite. Re-read the
                # exact item after CRM and binding reads; never acknowledge a
                # newer workbook the user did not see in their item snapshot.
                final_item=self.app.customer_batches._item(entry,[v['object_id'] for v in batch['items']])
                if final_item.get('item_revision')!=item_revision:
                    raise WorkspaceConflict('核对期间客户或CRM已变化，请重新读取后确认')
                previous=self.app.db.execute('SELECT data FROM outreach_crm_reviews WHERE object_id=?',(object_id,)).fetchone()
                if previous and json.loads(previous[0]).get('binding')==binding:
                    raise WorkspaceConflict('此版本已有人工核对记录，不能用另一份意见覆盖')
                saved={'object_id':object_id,'binding':binding,'evidence':evidence,
                       'review_id':uuid4().hex,'recorded_at':datetime.now(timezone.utc).isoformat()}
                self.app.db.execute('INSERT OR REPLACE INTO outreach_crm_reviews VALUES (?,?)',
                                    (object_id,json.dumps(saved,ensure_ascii=False)))
                self.app.db.commit()
            except BaseException:
                self.app.db.rollback()
                raise
        return self._manual_review(object_id,draft,crm)

    def identity_emails(self, obj):
        """Use the same registered and source-backed profile contacts on both sides.

        A profile address is additional identity evidence, not deliverability or
        permission. Never add an address merely because it is in a draft.
        """
        emails = set(customer_emails(obj))
        try:
            profile = self.app.customer_workspace.profile(obj['id'])
            cleaned_email = str((profile.get('cleaned') or {}).get('email') or '').strip().lower()
            evidence = (profile.get('provenance') or {}).get('evidence') or []
            if cleaned_email and _addresses(cleaned_email) == {cleaned_email}:
                # An address embedded in another address/domain is not an exact
                # publication of this contact.
                boundary = r"[A-Za-z0-9_.!#$%&'*+/=?^`{|}~@-]"
                exact = re.compile(r'(?<!' + boundary + ')' + re.escape(cleaned_email) +
                                   r'(?!' + boundary + ')', re.I)
                if any(exact.search(str(e.get('text') or '')) and
                       str(e.get('url') or '').startswith(('https://', 'http://')) and
                       e.get('observed_at') for e in evidence if isinstance(e, dict)):
                    emails.add(cleaned_email)
        except (AttributeError, ValueError, KeyError, TypeError):
            pass
        return emails

    def inspect(self, object_id, draft, *, batch_ids=None, refresh=False):
        reasons, duplicates = [], []
        def reason(code, message, state='unknown'):
            if not any(item['code'] == code for item in reasons):
                reasons.append({'code': code, 'message': message, 'status': state})
        obj = self.app.business.get_object(object_id)
        if obj.get('kind') not in {'customer', 'prospect'}:
            raise ValueError('请选择已有客户或候选')
        record = _record(obj)
        source = record.get('source_record') if isinstance(record.get('source_record'), dict) else {}
        emails = self.identity_emails(obj)
        recipients = _addresses(draft.get('to'))
        if len(recipients) != 1 or not recipients.issubset(emails):
            reason('recipient_identity_unknown', '草稿收件人不是原客户已登记的单一邮箱')
        for value in (record, source):
            review = value.get('review') or {}
            states = [value.get(k) for k in ('suppression_state', 'status', 'stop_state', 'stop_reason', 'email_verification', 'contact_verification')]
            states.append(review.get('state') if isinstance(review, dict) else review)
            if any(str(state) in STOP_STATES for state in states) or any(value.get(k) is True for k in ('unsubscribed', 'do_not_contact', 'complaint', 'bounced')):
                reason('local_suppressed', '客户原记录已标记停止、拒绝、不联系或地址无效', 'blocked')
        website = record.get('website') or obj.get('website') or source.get('website') or ''
        verified = (record.get('website_verification') == 'verified' or record.get('source_verification') == 'verified')
        if not website:
            website = next((item.get('url') for item in obj.get('links', []) if item.get('label') == '企业官网'), '')
        try:
            candidate = {**source, **record, 'website': website, 'contacts': [{'kind': 'email', 'value': email} for email in sorted(emails)]}
            with self._lock:
                if self._module is None:self._module=_crm_module()
                module=self._module
                if self._reader is None:
                    workbook=Path(self.app.root)/'04_客户开发/01_线索与CRM/outputs/01a0a569-4d14-7a43-b384-bdd1bb8d08a2/主动获客_规模化流水线_2026-09-17.xlsx'
                    self._reader=module.CRMReader(workbook)
                crm=self._reader.check(candidate)
            hosts = module.domains(website) if verified else set()
        except Exception:
            crm = {'status': '读取失败', 'coverage': 'CRM读取不可用', 'matches': []}
            hosts = set()
        if crm.get('status') != '已读取':
            reason('crm_unavailable', '原CRM未成功读取，历史停止状态未知')
        elif not crm.get('sha256') or not crm.get('coverage'):
            reason('crm_coverage_unknown', 'CRM未提供工作簿指纹或读取覆盖范围')
        if crm.get('local_stop') or crm.get('stop_state') == '明确停止':
            reason('crm_suppressed', '原CRM存在明确停止联系记录', 'blocked')
        elif crm.get('match_status') in {'冲突待核', '读取失败'} or crm.get('stop_state') == '未知':
            reason('crm_scope_unknown', 'CRM身份或停止范围尚未核清')
        for match in crm.get('matches', []):
            raw = ' '.join(_crm_stop_text(match.get(k)) for k in ('stop_raw', 'stage', 'next_action_raw'))
            history = match.get('history') or []
            history_text = [' '.join(_crm_stop_text(h.get(k)) for k in ('status', 'outcome', 'notes')) for h in history]
            if any(STOP.search(text) or BOUNCE.search(text) for text in [raw, *history_text]):
                reason('crm_history_suppressed', 'CRM历史中存在明确退订、拒绝或退信', 'blocked')
        # batch_ids denotes object IDs in this batch, never company-name guesses.
        for other_id in sorted(set(batch_ids or [])):
            if other_id == object_id:
                continue
            try:
                other = self.app.business.get_object(other_id)
                other_record = _record(other)
                hit = recipients & self.identity_emails(other)
                other_verified = other_record.get('website_verification') == 'verified' or other_record.get('source_verification') == 'verified'
                domain_hit = hosts & module.domains(other_record.get('website') or other.get('website') or '') if other_verified else set()
                if hit or domain_hit:
                    duplicates.append({'object_id': other_id, 'methods': (['email_exact'] if hit else []) + (['verified_domain_exact'] if domain_hit else [])})
            except Exception:
                reason('batch_identity_unknown', '批次内部分客户身份无法读取')
        if duplicates:
            reason('batch_duplicate', '同批次存在相同邮箱或已核实域名，请先确认归属', 'blocked')
        gmail = getattr(self.app, 'gmail', None)
        try:
            if refresh:
                mailbox = getattr(gmail, '_mailbox', None)
                if not mailbox or not emails:
                    raise ValueError('mailbox unavailable')
                # context only reads mailbox and updates its memory cache; unlike
                # GmailSync.customer it never creates events or dispatches Agents.
                context = mailbox.context(sorted(emails), force=True)
            else:
                context = gmail.peek(object_id)
        except Exception:
            context = {'status': {'state': 'error'}, 'messages': []}
        status = context.get('status') or {}
        observation=status.get('shared_observation')
        if refresh and (not isinstance(observation,dict) or observation.get('state')!='complete'):
            reason('mail_shared_observation_unknown','本次邮箱历史观察未完整提交，发送期间的新事件范围未知')
        messages = context.get('messages') or []
        # Existing mailbox queries target from/to, so mailer-daemon DSNs
        # mentioning a failed address only in the body are outside coverage.
        bounce={'status':'unknown','coverage':'尚未执行本次退信查询'}
        if refresh and len(recipients)==1:
            try:
                from gmail_bounce_check import check_bounces
                bounce=check_bounces(getattr(gmail,'_mailbox',None),next(iter(recipients)))
            except Exception:
                bounce={'status':'unknown','coverage':'退信查询不可用'}
        if bounce.get('status')=='blocked':
            reason('mail_bounce', '本邮箱有与该地址对应的明确退信', 'blocked')
        elif bounce.get('status')!='clear':
            reason('bounce_coverage_unknown', '本次未能完整检查该邮箱的相关退信')
        if not refresh:
            reason('mail_not_refreshed', '仅缓存邮件；发送前须进行本次真实只读同步')
        if status.get('state') not in {'ready', 'connected'} or not status.get('last_success_at'):
            reason('mail_unavailable', '本次邮箱连接或读取未确认成功')
        if status.get('history_limited') or status.get('thread_lookup_incomplete'):
            reason('mail_history_incomplete', '邮件历史或线程未完整读取')
        if 'history_limited' not in status:
            reason('mail_coverage_unknown', '邮箱未报告历史读取覆盖范围')
        events, inbound, outbound = [], 0, 0
        account = str(status.get('account_email') or getattr(gmail, '_account', '')).lower()
        if not account or not draft.get('account') or str(draft.get('account')).lower() != account:
            reason('sender_identity_unknown', '草稿发件邮箱与本次只读同步邮箱未明确一致')
        for mail in messages:
            direction = mail.get('direction')
            senders = _addresses(mail.get('from'))
            to = set().union(*(_addresses(mail.get(k)) for k in ('to', 'cc', 'bcc')))
            associated = set(mail.get('customer_emails') or []) & emails
            ours = bool(account and account in to and (senders & emails or associated))
            sent = bool(account and account in senders and to & emails)
            if direction == 'outbound' and sent:
                outbound += 1
            elif direction == 'inbound' and ours:
                inbound += 1
                if mail.get('body_truncated'):
                    reason('mail_body_incomplete', '客户入站邮件正文被截断，停止状态可能未完整读取')
                if not isinstance(mail.get('body'), str):
                    reason('mail_body_missing', '客户入站邮件缺少完整正文')
                body = _unquoted(mail.get('body'))
                kind = 'bounce' if BOUNCE.search(body) or mail.get('mail_kind') in {'bounce', 'bounced'} else 'stop' if STOP.search(body) else None
                if kind:
                    reason('mail_' + kind, '客户相关入站邮件包含退信' if kind == 'bounce' else '客户入站邮件包含明确退订或拒绝', 'blocked')
                    events.append({'id': mail.get('id'), 'sent_at': mail.get('sent_at'), 'kind': kind})
            else:
                reason('mail_association_unknown', '同步邮件的客户或发件身份无法核实')
        if outbound or any(match.get('latest_touch') or match.get('undated_touches') for match in crm.get('matches', [])):
            reason('previously_contacted', '已有触达记录，须确认后续联系范围，不能作为首次批量开发自动发送')
        if draft.get('status') not in {'draft'}:
            reason('draft_state_unknown', '当前草稿状态不可用于自动批量发送')
        manual_review=self._manual_review(object_id,draft,crm)
        if manual_review['applied']:
            reasons=[r for r in reasons if r['code']!='crm_scope_unknown']
        final = 'blocked' if any(r['status'] == 'blocked' for r in reasons) else 'unknown' if reasons else 'clear'
        # No raw CRM rows, addresses of other objects, subjects or message bodies.
        crm_view = {k: copy.deepcopy(crm.get(k)) for k in ('status', 'sha256', 'file_modified_at', 'loaded_at', 'coverage', 'match_status', 'stop_state')}
        crm_view['match_count'] = len(crm.get('matches', []))
        return {'object_id': object_id, 'draft_version': draft.get('version'), 'checked_at': datetime.now(timezone.utc).isoformat(), 'status': final, 'reasons': reasons, 'duplicates': duplicates, 'crm': crm_view,'crm_manual_review':manual_review, 'mail': {'refreshed': bool(refresh), 'state': status.get('state'), 'last_success_at': status.get('last_success_at'), 'history_limited': status.get('history_limited'), 'thread_lookup_incomplete': status.get('thread_lookup_incomplete'), 'visible_count': len(messages), 'inbound_count': inbound, 'outbound_count': outbound, 'events': events, 'coverage': '仅当前客户精确地址查询及已关联线程；不覆盖未登记别名、其他邮箱、垃圾箱及已删除邮件'}, 'bounce':bounce, 'can_auto_send': final=='clear'}
