"""Customer-specific Gmail drafts. Only an explicit reviewed action sends mail."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
import hashlib
import json
import os
from contextlib import contextmanager
import mimetypes
from pathlib import Path, PureWindowsPath
import re
import threading
from customer_batches import backfill_contact_suppressions, contact_suppressed
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from gmail_mailbox import normalize_email
from gmail_oauth import GMAIL_URL, GmailOAuth, _request, parse_addresses
from gmail_send_authorization import READ_SCOPE, SEND_SCOPE, REQUIRED_SCOPES, _read, _scopes, access_token, save_grant
from gmail_sync import customer_emails

MAX_ATTACHMENTS = 18 * 1024 * 1024


def now():
    return datetime.now(timezone.utc).isoformat()


class SendRejected(ValueError):
    """Google explicitly rejected the message before accepting it."""


def gmail_send(token, payload):
    request = Request(GMAIL_URL + 'messages/send', data=json.dumps(payload).encode(),
                      headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    try:
        with urlopen(request, timeout=45) as response:
            return json.load(response)
    except HTTPError as exc:
        if 400 <= exc.code < 500:
            raise SendRejected('Google 未接受邮件（HTTP %s），请检查授权、收件地址和附件。' % exc.code) from None
        raise


class GmailDrafts:
    def __init__(self, app, *, token_provider=access_token, sender=gmail_send, request=_request, grant_reader=_read):
        self.app = app
        self.token_provider, self.sender, self.request, self.grant_reader = token_provider, sender, request, grant_reader
        self.lock = threading.RLock()
        self._transaction = False
        self.directory = Path(app.state) / 'gmail-attachments'
        self.oauth = GmailOAuth(scope=READ_SCOPE+' '+SEND_SCOPE, grant_handler=self._save_grant)
        with app.lock:
            app.db.execute('CREATE TABLE IF NOT EXISTS gmail_drafts (object_id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            app.db.execute('CREATE TABLE IF NOT EXISTS gmail_sent_receipts (message_id TEXT PRIMARY KEY, object_id TEXT NOT NULL, data TEXT NOT NULL)')
            backfill_contact_suppressions(app)
            # Another worker may still own a live send. Reopening never changes
            # its claim; interrupted sends are reconciled explicitly by Message-ID.
            app.db.commit()

    @contextmanager
    def _write(self):
        with self.lock, self.app.lock:
            if self.app.db.in_transaction:
                raise RuntimeError('邮件保存不能嵌入已有事务')
            self.app.db.execute('BEGIN IMMEDIATE')
            self._transaction = True
            try:
                yield
                self.app.db.commit()
            except BaseException:
                self.app.db.rollback()
                raise
            finally:
                self._transaction = False

    def _put(self, draft):
        with self.app.lock:
            self.app.db.execute('INSERT OR REPLACE INTO gmail_drafts VALUES (?,?)',
                                (draft['object_id'], json.dumps(draft, ensure_ascii=False)))
            if not self._transaction:
                self.app.db.commit()
        return draft

    def _saved(self, object_id):
        with self.app.lock:
            row = self.app.db.execute('SELECT data FROM gmail_drafts WHERE object_id=?', (object_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def _object(self, object_id):
        obj = self.app.business.get_object(object_id)
        if obj.get('kind') not in ('customer', 'prospect'):
            raise ValueError('请在客户页面处理邮件')
        return obj

    def _account(self):
        return self.app.gmail.status().get('account_email') or ''

    def _save_grant(self, account, client, tokens):
        if account != self._account():
            raise ValueError('请选择工作台当前连接的 Gmail 账号')
        save_grant(account, client, tokens)

    def start_oauth(self, redirect_uri):
        account = self._account()
        if not account:
            raise ValueError('请先连接用于收信的 Gmail 账号')
        return self.oauth.start(None, redirect_uri, account)

    def finish_oauth(self, state, code):
        return self.oauth.finish(state, code)

    def _can_send(self, account):
        if not account:
            return False
        try:
            grant = self.grant_reader(account) or {}
            return bool(grant.get('refresh_token') and REQUIRED_SCOPES.issubset(_scopes(grant.get('scopes'))))
        except Exception:
            return False

    def _new(self, obj):
        object_id = obj['id']
        account = self._account()
        messages = self.app.gmail.peek(object_id).get('messages') or []
        messages = sorted(messages, key=lambda item: item.get('sent_at') or '', reverse=True)
        latest = next((m for m in messages if m.get('thread_id') and m.get('mail_kind') != 'automatic'), None)
        inbound = next((m for m in messages if m.get('direction') == 'inbound' and m.get('mail_kind') != 'automatic'
                        and (not latest or m.get('thread_id') == latest.get('thread_id'))), None)
        addresses = parse_addresses([(inbound or {}).get('reply_to', ''), (inbound or {}).get('from', '')])
        if not addresses:
            addresses = customer_emails(obj)
        subject = (latest or {}).get('subject') or ''
        if subject and not re.match(r'^\s*re\s*:', subject, re.I):
            subject = 'Re: ' + subject
        return {'object_id': object_id, 'account': account, 'to': addresses[0] if addresses else '',
                'subject': subject, 'body_en': '', 'body_zh': '', 'attachments': [], 'status': 'draft',
                'version': uuid4().hex, 'updated_at': now(),
                'thread_id': (latest or {}).get('thread_id') or '', 'thread_subject': (latest or {}).get('subject') or '',
                'reply_message_id': (latest or {}).get('rfc_message_id') or '', 'reply_references': (latest or {}).get('references') or ''}

    def get(self, object_id):
        obj = self._object(object_id)
        with self._write():
            draft = self._saved(object_id)
            if draft is None:
                draft = self._put(self._new(obj))
        return {**draft, 'can_send': self._can_send(self._account())}

    def new(self, object_id):
        obj = self._object(object_id)
        with self._write():
            old = self._saved(object_id)
            if old and old.get('status') != 'sent':
                raise ValueError('当前邮件尚未发送或发送结果未确认，请继续处理原草稿')
            draft = self._put(self._new(obj))
        return {**draft, 'can_send': self._can_send(self._account())}

    def _editable(self, object_id, version):
        self._object(object_id)
        draft = self._saved(object_id)
        if not draft or draft.get('version') != version:
            raise ValueError('草稿已更新，请刷新后继续')
        if draft.get('status') != 'draft':
            raise ValueError('这封邮件已发送或发送结果尚未确认，不能直接修改')
        return draft

    def _changed(self, draft):
        draft.update(version=uuid4().hex, updated_at=now())
        return self._put(draft)

    def save(self, object_id, version, fields):
        if not isinstance(fields, dict) or set(fields) - {'to', 'subject', 'body_en', 'body_zh'}:
            raise ValueError('邮件内容格式不正确')
        with self._write():
            draft = self._editable(object_id, version)
            for key, value in fields.items():
                if not isinstance(value, str) or '\x00' in value or len(value) > (100000 if key.startswith('body') else 500):
                    raise ValueError('邮件内容过长或格式不正确')
                if key in ('to', 'subject') and ('\n' in value or '\r' in value):
                    raise ValueError('收件地址和主题不能换行')
                draft[key] = value
            return self._changed(draft)

    def _attachment_bytes(self, attachment):
        if attachment['source'] == 'upload':
            path = self.directory / attachment['id']
        else:
            path = self.app.library.locate(attachment['path'])
        try:
            raw = path.read_bytes()
        except OSError:
            raise ValueError('附件无法读取，请重新选择：' + attachment['name']) from None
        if len(raw) != attachment['size'] or hashlib.sha256(raw).hexdigest() != attachment['sha256']:
            raise ValueError('附件内容已改变，请重新添加后审核：' + attachment['name'])
        return raw

    def attachment(self, object_id, attachment_id):
        draft = self.get(object_id)
        item = next((x for x in draft['attachments'] if x['id'] == attachment_id), None)
        if not item:
            raise ValueError('附件不存在')
        return item, self._attachment_bytes(item)

    def add_attachment(self, object_id, version, *, filename='', data='', resource_id=''):
        with self._write():
            draft = self._editable(object_id, version)
            if resource_id:
                item = next((r for r in self.app.library.list() if r['id'] == resource_id), None)
                if not item:
                    raise ValueError('资料不存在，请刷新资料列表')
                path = self.app.library.locate(item['path'])
                filename, raw, source = path.name, path.read_bytes(), 'library'
            else:
                filename = PureWindowsPath(str(filename or '')).name
                if not filename or filename in ('.', '..') or any(c in filename for c in '\r\n\x00'):
                    raise ValueError('请选择附件文件')
                try:
                    raw = base64.b64decode(data, validate=True)
                except (ValueError, TypeError):
                    raise ValueError('附件读取失败，请重新选择') from None
                source = 'upload'
            if not raw:
                raise ValueError('附件为空，请重新选择')
            if len(raw) + sum(a['size'] for a in draft['attachments']) > MAX_ATTACHMENTS:
                raise ValueError('附件合计请控制在 18 MB 以内')
            attachment = {'id': uuid4().hex, 'name': filename, 'size': len(raw),
                          'sha256': hashlib.sha256(raw).hexdigest(), 'source': source}
            if source == 'library':
                attachment['path'] = item['path']
            else:
                self.directory.mkdir(parents=True, exist_ok=True)
                (self.directory / attachment['id']).write_bytes(raw)
            draft['attachments'].append(attachment)
            return self._changed(draft)

    def remove_attachment(self, object_id, version, attachment_id):
        with self._write():
            draft = self._editable(object_id, version)
            item = next((x for x in draft['attachments'] if x['id'] == attachment_id), None)
            if not item:
                raise ValueError('附件不存在')
            draft['attachments'].remove(item)
            result = self._changed(draft)
        if item['source'] == 'upload':
            (self.directory / item['id']).unlink(missing_ok=True)
        return result

    def _message(self, draft):
        recipient = normalize_email(draft.get('to'))
        subject, body = draft.get('subject', '').strip(), draft.get('body_en', '').strip()
        if not subject or not body:
            raise ValueError('请填写邮件主题和英文正文后审核')
        if '\n' in subject or '\r' in subject:
            raise ValueError('邮件主题不能换行')
        msg = EmailMessage()
        msg['From'], msg['To'], msg['Subject'] = draft['account'], recipient, subject
        msg['Date'], msg['Message-ID'] = formatdate(localtime=True), make_msgid(domain='beiqiang.online')
        reference = draft.get('reply_message_id') or ''
        normalize_subject = lambda value: re.sub(r'^(?:\s*re\s*:\s*)+', '', value or '', flags=re.I).strip().casefold()
        same_subject = bool(draft.get('thread_subject') and normalize_subject(subject) == normalize_subject(draft['thread_subject']))
        if reference and same_subject and re.fullmatch(r'<[^<>\s]+>', reference):
            prior = re.findall(r'<[^<>\s]+>', draft.get('reply_references') or '')
            msg['In-Reply-To'], msg['References'] = reference, ' '.join((prior + [reference])[-50:])
        else:
            reference = ''
        msg.set_content(body)
        for item in draft['attachments']:
            raw = self._attachment_bytes(item)
            kind = mimetypes.guess_type(item['name'])[0] or 'application/octet-stream'
            maintype, subtype = kind.split('/', 1)
            msg.add_attachment(raw, maintype=maintype, subtype=subtype, filename=item['name'])
        payload = {'raw': base64.urlsafe_b64encode(msg.as_bytes()).decode().rstrip('=')}
        if draft.get('thread_id') and reference:
            try:
                payload['threadId'] = format(int(draft['thread_id']), 'x')
            except ValueError:
                raise ValueError('原邮件线程无效，请更新邮件往来后重新起草') from None
        return msg['Message-ID'], payload

    def send(self, object_id, version, *, before_claim=None):
        # Prepare bytes and credentials before taking the short database claim.
        with self.lock:
            draft = self._editable(object_id, version)
            with self.app.lock:
                if contact_suppressed(self.app,object_id,draft.get('to','')):
                    raise ValueError('客户或收件地址已标记不联系，不能发送')
            if not draft.get('account') or draft['account'] != self._account():
                raise ValueError('邮箱连接已变化，请重新连接并检查草稿')
            message_id, payload = self._message(draft)
            token = self.token_provider(draft['account'])
        with self._write():
            draft = self._editable(object_id, version)
            if draft['account'] != self._account():
                raise ValueError('邮箱连接已变化，请重新连接并检查草稿')
            if before_claim is not None:
                before_claim(draft)
            # Shared across every batch, UI, MCP and direct single-mail call.
            # This runs in the same write transaction as the send claim, so a
            # concurrent DNC commit cannot be bypassed by an older draft view.
            backfill_contact_suppressions(self.app)
            if contact_suppressed(self.app,object_id,draft.get('to','')):
                raise ValueError('客户或收件地址已标记不联系，不能发送；更改批次审核状态不会解除抑制')
            draft.update(status='sending', message_id=str(message_id), sender_pid=os.getpid(), error='', updated_at=now())
            self._put(draft)
        try:
            result = self.sender(token, payload)
            if not isinstance(result, dict) or not result.get('id'):
                raise OSError('missing Gmail message id')
        except SendRejected as exc:
            self._send_result(draft, 'draft', str(exc))
            raise
        except Exception:
            return self._send_result(draft, 'unknown', '发送结果尚未确认，请先核对 Gmail 已发送邮件。')
        return self._sent(draft, result)

    def _send_result(self, snapshot, status, error):
        with self._write():
            current = self._saved(snapshot['object_id'])
            if not current or current.get('message_id') != snapshot.get('message_id') or current.get('status') not in ('sending', 'unknown'):
                return current
            current.update(status=status, error=error, updated_at=now())
            return self._put(current)

    def _sent(self, draft, result):
        with self._write():
            current = self._saved(draft['object_id'])
            if not current or current.get('message_id') != draft.get('message_id'):
                return current
            if current.get('status') == 'sent':
                return current
            if current.get('status') not in ('sending', 'unknown'):
                return current
            draft = current
            thread = result.get('threadId') or ''
            draft.update(status='sent', gmail_id=str(result['id']), gmail_thread_id=str(thread), sent_at=now(), error='',
                         gmail_url=('https://mail.google.com/mail/u/?authuser=' + draft['account'] + '#all/' + str(thread)) if thread else '')
            self._put(draft)
            with self.app.lock:
                self.app.db.execute('INSERT OR REPLACE INTO gmail_sent_receipts VALUES (?,?,?)',
                                    (draft['message_id'], draft['object_id'], json.dumps(draft, ensure_ascii=False)))
        self._after_send(draft)
        return draft

    def _after_send(self, draft):
        oid = draft['object_id']
        problems = []
        try:
            self.app.gmail.link_sent_address(oid, draft['to'])
            if self.app.gmail.peek(oid).get('reply_pending'):
                self.app.gmail.acknowledge(oid)
            flow = self.app.customer_workspace.workflow(oid)
            if flow.get('state') != 'waiting_customer' and not any(x.get('state') == 'waiting_customer' for x in flow.get('allowed_transitions', [])):
                flow = self.app.customer_workspace.save_workflow(oid, {'revision':flow['revision'], 'state': 'preparing', 'bucket': 'active'})
            self.app.customer_workspace.save_workflow(oid, {'revision':flow['revision'], 'state': 'waiting_customer', 'bucket': 'active', 'next_action': '等待客户回复，收到后继续处理'})
            if oid.startswith('prospect:'):
                self.app.customer_workspace.update_discovery(oid[len('prospect:'):],
                    {'contact_status_label': '邮件已发送，等待客户回复', 'next_action': '等待客户回复，收到后继续处理'})
        except Exception:
            problems.append('客户状态暂未更新')
        try:
            result = self.app.gmail.customer(oid, force=True)
            if result.get('status', {}).get('state') != 'connected':
                problems.append('邮件回读暂未完成')
        except Exception:
            problems.append('邮件回读暂未完成')
        if problems:
            with self._write():
                current = self._saved(oid)
                if current and current.get('message_id') == draft.get('message_id') and current.get('status') == 'sent':
                    current['sync_note'] = '；'.join(problems) + '，可稍后刷新。'
                    self._put(current)
                    draft.update(current)

    def reconcile(self, object_id):
        with self.lock:
            draft = self._saved(object_id)
            if not draft or draft.get('status') not in ('unknown', 'sending'):
                raise ValueError('当前没有需要核对的发送结果')
        token = self.token_provider(draft['account'])
        query = urlencode({'q': 'in:sent rfc822msgid:' + draft['message_id'], 'maxResults': 5})
        result = self.request(GMAIL_URL + 'messages?' + query, token=token)
        found = result.get('messages') or []
        if found:
            return self._sent(draft, found[0])
        status = draft['status']
        if status == 'sending' and not self._sender_alive(draft):
            status = 'unknown'
        return self._send_result(draft, status, '暂未在已发送邮件中找到，请稍后再次核对；不要重复发送。')

    @staticmethod
    def _sender_alive(draft):
        pid = draft.get('sender_pid')
        if not isinstance(pid, int) or pid <= 0:
            return False
        if pid == os.getpid():
            return True
        try:
            # On Windows os.kill(pid, 0) is not a harmless liveness probe.
            if os.name == 'nt':
                import ctypes
                kernel = ctypes.WinDLL('kernel32', use_last_error=True)
                kernel.OpenProcess.restype = ctypes.c_void_p
                handle = kernel.OpenProcess(0x1000, False, pid)
                if not handle:
                    return ctypes.get_last_error() != 87
                try:
                    code = ctypes.c_ulong()
                    if not kernel.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code)):
                        return True
                    return code.value == 259
                finally:
                    kernel.CloseHandle(ctypes.c_void_p(handle))
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except (PermissionError, OSError):
            return True

    def resume_unsent(self, object_id, confirmed):
        with self._write():
            draft = self._saved(object_id)
            if not confirmed or not draft or draft.get('status') != 'unknown':
                raise ValueError('请先在 Gmail 已发送邮件中核对实际结果')
            draft.update(status='draft', error='')
            return self._changed(draft)
