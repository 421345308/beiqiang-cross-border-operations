"""Google desktop OAuth and read-only Gmail API access for the local workbench."""
from __future__ import annotations

import base64
import copy
from datetime import datetime, timezone
from email.utils import getaddresses
from html import unescape
import hashlib
import json
import re
import secrets
import threading
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from gmail_mailbox import normalize_email

AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
GMAIL_URL = 'https://gmail.googleapis.com/gmail/v1/users/me/'
SCOPE = 'https://www.googleapis.com/auth/gmail.readonly'
SERVICE = 'Beiqiang.Workdesk.GmailOAuth'


def load_credentials(account):
    import keyring
    value = keyring.get_password(SERVICE, normalize_email(account))
    return json.loads(value) if value else None


def save_credentials(account, value):
    import keyring
    keyring.set_password(SERVICE, normalize_email(account), json.dumps(value))


def credentials_available(account):
    value = load_credentials(account)
    return bool(value and value.get('refresh_token') and value.get('client_id') and value.get('client_secret'))


def _request(url, *, token=None, form=None):
    headers = {'Accept': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    data = None
    if form is not None:
        data = urlencode(form).encode('utf-8')
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    try:
        with urlopen(Request(url, data=data, headers=headers), timeout=20) as response:
            return json.load(response)
    except HTTPError as exc:
        if exc.code in (400, 401, 403):
            raise ValueError('Google 授权或 Gmail 接口不可用，请重新授权并确认已启用 Gmail API') from None
        raise ValueError('Google 服务暂时不可用（HTTP %s）' % exc.code) from None


def _desktop_client(config):
    if not isinstance(config, dict) or not isinstance(config.get('installed'), dict):
        raise ValueError('请选择 Google Cloud 下载的“桌面应用”客户端 JSON')
    installed = config['installed']
    client_id, client_secret = installed.get('client_id'), installed.get('client_secret')
    if (not isinstance(client_id, str) or not client_id.endswith('.apps.googleusercontent.com')
            or not isinstance(client_secret, str) or not client_secret or len(client_secret) > 500):
        raise ValueError('Google 客户端文件缺少有效的客户端信息')
    return {'client_id': client_id, 'client_secret': client_secret}


class GmailOAuth:
    def __init__(self, *, request=_request, reader=load_credentials, saver=save_credentials, clock=time.time):
        self.request, self.reader, self.saver, self.clock = request, reader, saver, clock
        self.lock = threading.Lock()
        self.pending = None

    def start(self, config, redirect_uri, account_hint=''):
        if config:
            client = _desktop_client(config)
        else:
            saved = self.reader(account_hint) if account_hint else None
            if not saved:
                raise ValueError('请先选择 Google Cloud 下载的桌面应用客户端 JSON')
            client = {'client_id': saved['client_id'], 'client_secret': saved['client_secret']}
        state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        with self.lock:
            self.pending = {'state': state, 'verifier': verifier, 'client': client,
                            'redirect_uri': redirect_uri, 'started_at': self.clock()}
        query = {'client_id': client['client_id'], 'redirect_uri': redirect_uri, 'response_type': 'code',
                 'scope': SCOPE, 'state': state, 'code_challenge': challenge, 'code_challenge_method': 'S256',
                 'access_type': 'offline', 'prompt': 'consent'}
        if account_hint:
            query['login_hint'] = normalize_email(account_hint)
        return AUTH_URL + '?' + urlencode(query)

    def finish(self, state, code):
        with self.lock:
            pending = self.pending
            if not pending or not secrets.compare_digest(str(state or ''), pending['state']):
                raise ValueError('Google 登录已过期，请从工作台重新发起')
            self.pending = None
        if self.clock() - pending['started_at'] > 900 or not code:
            raise ValueError('Google 登录未完成，请从工作台重新发起')
        client = pending['client']
        tokens = self.request(TOKEN_URL, form={'client_id': client['client_id'], 'client_secret': client['client_secret'],
            'code': code, 'code_verifier': pending['verifier'], 'grant_type': 'authorization_code',
            'redirect_uri': pending['redirect_uri']})
        if not tokens.get('access_token') or not tokens.get('refresh_token'):
            raise ValueError('Google 未提供持续读取授权，请重新连接')
        if tokens.get('scope') and SCOPE not in tokens['scope'].split():
            raise ValueError('Google 未授予 Gmail 读取权限')
        profile = self.request(GMAIL_URL + 'profile', token=tokens['access_token'])
        account = normalize_email(profile.get('emailAddress'))
        self.saver(account, {**client, 'refresh_token': tokens['refresh_token']})
        return account


def _parts(payload):
    yield payload
    for part in payload.get('parts') or []:
        if isinstance(part, dict):
            yield from _parts(part)


def _decode_part(part):
    encoded = (part.get('body') or {}).get('data') or ''
    if not encoded:
        return ''
    raw = base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4))
    headers = {str(h.get('name', '')).lower(): str(h.get('value', '')) for h in part.get('headers') or []}
    match = re.search(r'charset=["\']?([^;"\'\s]+)', headers.get('content-type', ''), flags=re.I)
    try:
        return raw.decode(match[1] if match else 'utf-8', errors='replace')
    except LookupError:
        return raw.decode('utf-8', errors='replace')


def parse_api_message(value, account, customers):
    payload = value.get('payload') or {}
    headers = {}
    for header in payload.get('headers') or []:
        name = str(header.get('name', '')).lower()
        headers[name] = ', '.join(filter(None, (headers.get(name), str(header.get('value') or ''))))
    addresses = lambda names: {a.lower() for _, a in getaddresses([headers.get(n, '') for n in names]) if a}
    senders, recipients = addresses(['from']), addresses(['to', 'cc', 'bcc'])
    if account in senders:
        direction, associated = 'outbound', recipients & customers
    elif account in recipients:
        direction, associated = 'inbound', senders & customers
    else:
        return None
    if not associated:
        return None
    plain, html, attachments, truncated = [], [], [], False
    for part in _parts(payload):
        name, mime = str(part.get('filename') or ''), str(part.get('mimeType') or '')
        if name:
            attachments.append({'filename': name, 'content_type': mime})
        elif mime in ('text/plain', 'text/html'):
            if (part.get('body') or {}).get('attachmentId'):
                truncated = True
            else:
                (plain if mime == 'text/plain' else html).append(_decode_part(part))
    body = '\n'.join(plain)
    if not body:
        body = unescape(re.sub('<[^>]+>', ' ', re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', '\n'.join(html), flags=re.S | re.I)))
    try:
        sent_at = datetime.fromtimestamp(int(value['internalDate']) / 1000, timezone.utc).isoformat()
    except (KeyError, TypeError, ValueError, OverflowError, OSError):
        sent_at = None
    mid, thread = str(value['id']), str(value.get('threadId') or '')
    try:
        canonical_id, canonical_thread = str(int(mid, 16)), str(int(thread, 16)) if thread else None
    except ValueError:
        canonical_id, canonical_thread = mid, thread or None
    return {'id': canonical_id, 'thread_id': canonical_thread, 'direction': direction, 'sent_at': sent_at,
        'from': headers.get('from', ''), 'to': headers.get('to', ''), 'cc': headers.get('cc', ''),
        'bcc': headers.get('bcc', ''), 'subject': headers.get('subject', ''), 'snippet': str(value.get('snippet') or ''),
        'body': body.strip(), 'translation_zh': None, 'attachments': attachments, 'body_truncated': truncated,
        'url': 'https://mail.google.com/mail/u/?authuser=' + account + '#all/' + thread if thread else None,
        'customer_emails': sorted(associated)}


class GmailOAuthMailbox:
    def __init__(self, account_email, *, request=_request, reader=load_credentials, ttl=120, clock=time.time, max_messages=50):
        self.account_email = normalize_email(account_email)
        self.request, self.reader, self.ttl, self.clock = request, reader, ttl, clock
        self.max_messages = max_messages
        self.lock = threading.RLock()
        self._token, self._token_expires, self._messages, self._cache = None, 0, {}, {}

    def _access_token(self):
        if self._token and self.clock() < self._token_expires - 30:
            return self._token
        saved = self.reader(self.account_email)
        if not saved:
            raise ValueError('请重新连接 Google 账号')
        result = self.request(TOKEN_URL, form={'client_id': saved['client_id'], 'client_secret': saved['client_secret'],
            'refresh_token': saved['refresh_token'], 'grant_type': 'refresh_token'})
        if not result.get('access_token'):
            raise ValueError('Google 授权已失效，请重新连接')
        self._token, self._token_expires = result['access_token'], self.clock() + int(result.get('expires_in', 3600))
        return self._token

    def context(self, customer_emails, *, force=False):
        customers = {normalize_email(x) for x in customer_emails} - {self.account_email}
        key = tuple(sorted(customers))
        with self.lock:
            old = self._cache.get(key)
            if old and not force and self.clock() - old['last_poll'] < self.ttl:
                return copy.deepcopy(old['result'])
            status = {'state': 'ready', 'account_email': self.account_email,
                      'last_success_at': old['result']['status'].get('last_success_at') if old else None, 'error': None}
            messages = copy.deepcopy(old['result']['messages']) if old else []
            try:
                token = self._access_token()
                terms = ' '.join('from:' + x + ' to:' + x for x in sorted(customers))
                query = '-in:drafts -in:spam -in:trash {' + terms + '}'
                listing = self.request(GMAIL_URL + 'messages?' + urlencode({'q': query, 'maxResults': self.max_messages}), token=token)
                found = []
                for item in listing.get('messages') or []:
                    mid = str(item.get('id') or '')
                    if not re.fullmatch('[0-9a-fA-F]+', mid):
                        continue
                    if mid not in self._messages:
                        self._messages[mid] = self.request(GMAIL_URL + 'messages/' + mid + '?format=full', token=token)
                    message = parse_api_message(self._messages[mid], self.account_email, customers)
                    if message:
                        found.append(message)
                messages = sorted(found, key=lambda m: (m['sent_at'] or '', m['id']))
                status.update(last_success_at=datetime.fromtimestamp(self.clock(), timezone.utc).isoformat(),
                    loaded_count=len(messages), history_limited=bool(listing.get('nextPageToken')),
                    history_note=('仅显示最近 ' + str(self.max_messages) + ' 封匹配邮件') if listing.get('nextPageToken') else None)
            except Exception as exc:
                status.update(state='error', error=str(exc) if isinstance(exc, ValueError) else 'Google 邮件连接暂不可用，请检查网络后重试')
            dated = [m for m in messages if m['sent_at']]
            latest = max(dated, key=lambda m: (m['sent_at'], m['id']), default=None)
            pending = bool(latest and latest['direction'] == 'inbound') if status['state'] == 'ready' else None
            result = {'status': status, 'messages': messages, 'reply_pending': pending,
                      'next_action': '邮件同步尚未成功，请恢复连接后确认客户回复' if pending is None else
                                     '查看客户新回复并准备答复' if pending else '等待客户回复' if latest else '暂无已同步邮件'}
            self._cache[key] = {'result': result, 'last_poll': self.clock() if status['state'] == 'ready' else float('-inf')}
            return copy.deepcopy(result)
