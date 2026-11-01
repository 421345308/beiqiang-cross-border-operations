"""Gmail IMAP read-only customer correspondence. Secrets stay in OS keyring.

An app password grants mailbox access; read-only is enforced by this module's
EXAMINE and BODY.PEEK usage, not by a scoped credential. No send/modify API.
"""
from __future__ import annotations
import copy
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from html import unescape
import imaplib
import re
import ssl
import threading
import time
from urllib.parse import urlparse, unquote
from urllib.request import getproxies

SERVICE = 'Beiqiang.Workdesk.Gmail'
HOST = 'imap.gmail.com'


def normalize_email(value):
    value = str(value or '').strip().lower()
    if not re.fullmatch(r'[^\s<>"\\@]+@[^\s<>"\\@]+\.[^\s<>"\\@]+', value):
        raise ValueError('请输入有效邮箱地址')
    return value


def save_password(account_email, password):
    """User-supplied app password only; never return it to callers."""
    import keyring
    account = normalize_email(account_email)
    password = str(password or '').replace(' ', '')
    if not re.fullmatch(r'[A-Za-z0-9]{16}', password):
        raise ValueError('请输入Google生成的16位应用专用密码')
    keyring.set_password(SERVICE, account, password)


def credential_available(account_email):
    return bool(_read_password(normalize_email(account_email)))


def test_credentials(account_email, password, *, imap_factory=None):
    """Check supplied credentials without saving; no mailbox is selected."""
    account = normalize_email(account_email)
    password = str(password or '').replace(' ', '')
    if not re.fullmatch(r'[A-Za-z0-9]{16}', password):
        raise ValueError('请输入Google生成的16位应用专用密码')
    client = None
    try:
        client = (imap_factory or connect_imap)()
        client.login(account, password)
        return True
    except Exception as exc:
        raise ValueError('Gmail连接或登录失败（' + type(exc).__name__ + '），未保存凭证') from None
    finally:
        if client is not None:
            try:
                client.logout()
            except Exception:
                pass


def _read_password(account):
    import keyring
    return keyring.get_password(SERVICE, account)


class ProxyIMAP(imaplib.IMAP4_SSL):
    def __init__(self, proxy_url=None, timeout=15):
        self.proxy_url = proxy_url
        super().__init__(HOST, 993, ssl_context=ssl.create_default_context(), timeout=timeout)

    def _create_socket(self, timeout):
        if not self.proxy_url:
            return super()._create_socket(timeout)
        import socks
        proxy = urlparse(self.proxy_url)
        kind = {'http': socks.HTTP, 'socks5': socks.SOCKS5, 'socks5h': socks.SOCKS5, 'socks4': socks.SOCKS4}.get(proxy.scheme)
        if not kind or not proxy.hostname:
            raise ValueError('不支持当前邮件代理类型')
        sock = socks.socksocket()
        try:
            sock.set_proxy(kind, proxy.hostname, proxy.port or (8080 if kind == socks.HTTP else 1080),
                           rdns=True, username=unquote(proxy.username) if proxy.username else None,
                           password=unquote(proxy.password) if proxy.password else None)
            sock.settimeout(timeout)
            sock.connect((HOST, 993))
            return self.ssl_context.wrap_socket(sock, server_hostname=HOST)
        except Exception:
            sock.close()
            raise


def connect_imap(proxy_url=None):
    # None discovers the existing system proxy; empty string explicitly uses direct.
    if proxy_url is None:
        proxies = getproxies()
        proxy_url = proxies.get('https') or proxies.get('all') or proxies.get('http')
    return ProxyIMAP(proxy_url)


def _addresses(message, header):
    return {address.lower() for _, address in getaddresses(message.get_all(header, [])) if address}


def parse_message(raw, metadata, uid, account, customers):
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    senders = _addresses(msg, 'From')
    recipients = _addresses(msg, 'To') | _addresses(msg, 'Cc') | _addresses(msg, 'Bcc')
    if account in senders:
        direction = 'outbound'
        associated = recipients & customers
    elif account in recipients:
        direction = 'inbound'
        associated = senders & customers
    else:
        return None
    if not associated:
        return None
    text_parts, html_parts, attachments = [], [], []
    for part in msg.walk():
        filename=part.get_filename()
        if filename and part.get_content_disposition()!='inline':
            attachments.append({'filename':str(filename),'content_type':part.get_content_type()})
        if part.get_content_disposition() == 'attachment' or part.get_filename() or part.is_multipart():
            continue
        if part.get_content_type() in ('text/plain', 'text/html'):
            try:
                value = part.get_content()
            except (LookupError, UnicodeError):
                value = (part.get_payload(decode=True) or b'').decode('utf-8', errors='replace')
            if isinstance(value, str):
                (text_parts if part.get_content_type() == 'text/plain' else html_parts).append(value)
    body = '\n'.join(text_parts)
    if not body:
        body = unescape(re.sub('<[^>]+>', ' ', re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', '\n'.join(html_parts), flags=re.S | re.I)))
    try:
        date = parsedate_to_datetime(str(msg.get('Date', '')))
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        sent_at = date.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        match = re.search(rb'INTERNALDATE "([^"]+)"', metadata)
        try:
            date = datetime.strptime(match[1].decode(), '%d-%b-%Y %H:%M:%S %z')
            sent_at = date.astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError):
            sent_at = None
    mid = re.search(rb'X-GM-MSGID (\d+)', metadata)
    tid = re.search(rb'X-GM-THRID (\d+)', metadata)
    ident = mid[1].decode() if mid else 'uid:' + uid.decode()
    thread = tid[1].decode() if tid else None
    size = re.search(rb'RFC822.SIZE (\d+)', metadata)
    return {'id': ident, 'thread_id': thread, 'direction': direction, 'sent_at': sent_at,
            'from': str(msg.get('From', '')), 'to': str(msg.get('To', '')),
            'cc': str(msg.get('Cc', '')), 'bcc': str(msg.get('Bcc', '')),
            'subject': str(msg.get('Subject', '')), 'snippet': ' '.join(body.split())[:240],
            'body': body.strip(), 'translation_zh': None,
            'attachments':attachments,
            'body_truncated': bool(size and int(size[1]) > len(raw)),
            'url': 'https://mail.google.com/mail/u/?authuser=' + account + '#all/' + format(int(thread), 'x') if thread else None,
            'customer_emails': sorted(associated)}


class GmailMailbox:
    def __init__(self, account_email='', *, imap_factory=connect_imap, password_reader=_read_password,
                 ttl=120, clock=time.time, max_messages=500):
        self.account_email = normalize_email(account_email) if account_email else ''
        self.imap_factory = imap_factory
        self.password_reader = password_reader
        self.ttl = ttl
        self.clock = clock
        self.max_messages = max_messages
        self.lock = threading.RLock()
        self._cache = {}

    def context(self, customer_emails, *, force=False):
        customers = {normalize_email(x) for x in customer_emails}
        customers.discard(self.account_email)
        key = tuple(sorted(customers))
        with self.lock:
            old = self._cache.get(key)
            if old and not force and self.clock() - old['last_poll'] < self.ttl:
                return copy.deepcopy(old['result'])
            status = {'state': 'not_configured' if not self.account_email else 'ready',
                      'account_email': self.account_email, 'last_success_at': old['result']['status']['last_success_at'] if old else None,
                      'error': None}
            messages = old['result']['messages'] if old else []
            try:
                if self.account_email and customers:
                    password = self.password_reader(self.account_email)
                    if not password:
                        status['state'] = 'not_configured'
                    else:
                        messages, total = self._fetch(customers, password)
                        status['matched_total'] = total
                        status['loaded_count'] = len(messages)
                        status['history_limited'] = total > self.max_messages
                        status['history_note'] = '仅显示最近' + str(self.max_messages) + '封匹配邮件' if total > self.max_messages else None
                        status['last_success_at'] = datetime.fromtimestamp(self.clock(), timezone.utc).isoformat()
                elif self.account_email:
                    messages = []
                if status['state'] == 'not_configured':
                    status['error'] = '请配置Gmail账号与应用专用密码'
            except Exception as exc:
                # Do not include exception text: providers can echo credentials or command arguments.
                status['state'] = 'error'
                status['error'] = ('Gmail服务器拒绝读取或登录，请检查账号设置及连接状态' if isinstance(exc, imaplib.IMAP4.error)
                                   else 'Gmail连接或读取失败（' + type(exc).__name__ + '），请检查网络与代理')
            dated = [m for m in messages if m['sent_at']]
            latest = max(dated, key=lambda m: (m['sent_at'], m['id']), default=None)
            pending = bool(latest and latest['direction'] == 'inbound') if status['state'] == 'ready' else None
            result = {'status': status, 'messages': messages, 'reply_pending': pending,
                      'next_action': '邮件同步尚未成功，请恢复连接后确认客户回复' if pending is None else '查看客户新回复并准备答复' if pending else '等待客户回复' if latest else '暂无已同步邮件'}
            # Failed polling keeps the last successful data and is retried on the next request.
            self._cache[key] = {'result': result, 'last_poll': self.clock() if status['state'] == 'ready' else float('-inf')}
            return copy.deepcopy(result)

    def _fetch(self, customers, password):
        client = self.imap_factory()
        try:
            client.login(self.account_email, password)
            ok, boxes = client.list()
            if ok != 'OK':
                raise OSError('mailbox list failed')
            mailbox = None
            for box in boxes or []:
                if isinstance(box, bytes) and re.search(rb'\\All\b', box, re.I):
                    match = re.search(rb' "(?:[^"\\]|\\.)*" (.+)$', box)
                    if match:
                        mailbox = match[1].decode('ascii')
                        break
            if not mailbox:
                raise OSError('Gmail All Mail unavailable')
            if client.select(mailbox, readonly=True)[0] != 'OK':
                raise OSError('readonly mailbox unavailable')
            terms = ' '.join('from:' + x + ' to:' + x for x in sorted(customers))
            query = '-in:drafts -in:spam -in:trash {' + terms + '}'
            ok, data = client.uid('SEARCH', None, 'X-GM-RAW', '"' + query + '"')
            if ok != 'OK':
                raise OSError('mail search failed')
            uids = (data[0] or b'').split() if data else []
            total = len(uids)
            uids = uids[-max(1, self.max_messages):]
            messages = []
            for uid in uids:
                ok, rows = client.uid('FETCH', uid, '(X-GM-MSGID X-GM-THRID INTERNALDATE RFC822.SIZE BODY.PEEK[]<0.524288>)')
                if ok != 'OK':
                    raise OSError('mail fetch failed')
                for row in rows or []:
                    if isinstance(row, tuple) and len(row) == 2:
                        message = parse_message(row[1], row[0], uid, self.account_email, customers)
                        if message:
                            messages.append(message)
            return sorted(messages, key=lambda m: (m['sent_at'] or '', m['id'])), total
        finally:
            try:
                client.logout()
            except Exception:
                pass
