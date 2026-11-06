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
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from gmail_mailbox import normalize_email
from gmail_filter import classify_mail, new_buyer_summary
from gmail_observations import begin_observation, finish_observation, history_id

AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
GMAIL_URL = 'https://gmail.googleapis.com/gmail/v1/users/me/'
SCOPE = 'https://www.googleapis.com/auth/gmail.readonly'
SERVICE = 'Beiqiang.Workdesk.GmailOAuth'
PUBLIC_MAIL_DOMAINS = {'gmail.com','googlemail.com','outlook.com','hotmail.com','live.com','yahoo.com','icloud.com','qq.com','163.com','126.com','88.com','tencent.com'}


class GmailDependencyError(RuntimeError):
    pass


def _keyring():
    try:
        import keyring
    except ModuleNotFoundError as exc:  # pragma: no cover - 环境依赖问题
        raise GmailDependencyError('缺少依赖 keyring，读不到已保存的 Google 授权。'
                                   '请在工作台目录执行 python -m pip install -r requirements-gmail.txt 后重启工作台。') from exc
    return keyring


def load_credentials(account):
    keyring = _keyring()
    value = keyring.get_password(SERVICE, normalize_email(account))
    return json.loads(value) if value else None


def save_credentials(account, value):
    keyring = _keyring()
    keyring.set_password(SERVICE, normalize_email(account), json.dumps(value))


def credentials_available(account):
    value = load_credentials(account)
    return bool(value and value.get('refresh_token') and value.get('client_id'))


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
    client_id, client_secret = installed.get('client_id'), installed.get('client_secret', '')
    if (not isinstance(client_id, str) or not client_id.endswith('.apps.googleusercontent.com')
            or not isinstance(client_secret, str) or len(client_secret) > 500):
        raise ValueError('Google 客户端文件缺少有效的客户端信息')
    return {'client_id': client_id, 'client_secret': client_secret}


class GmailOAuth:
    def __init__(self, *, request=_request, reader=load_credentials, saver=save_credentials, clock=time.time, scope=SCOPE, grant_handler=None):
        self.request, self.reader, self.saver, self.clock = request, reader, saver, clock
        self.scope, self.grant_handler = scope, grant_handler
        self.lock = threading.Lock()
        self.pending = None

    def start(self, config, redirect_uri, account_hint=''):
        if config:
            client = _desktop_client(config)
        else:
            saved = self.reader(account_hint) if account_hint else None
            if not saved:
                raise ValueError('请先选择 Google Cloud 下载的桌面应用客户端 JSON')
            client = {'client_id': saved['client_id'], 'client_secret': saved.get('client_secret', '')}
        state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        with self.lock:
            self.pending = {'state': state, 'verifier': verifier, 'client': client,
                            'redirect_uri': redirect_uri, 'started_at': self.clock()}
        query = {'client_id': client['client_id'], 'redirect_uri': redirect_uri, 'response_type': 'code',
                 'scope': self.scope, 'state': state, 'code_challenge': challenge, 'code_challenge_method': 'S256',
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
        form = {'client_id': client['client_id'], 'code': code, 'code_verifier': pending['verifier'],
                'grant_type': 'authorization_code', 'redirect_uri': pending['redirect_uri']}
        if client['client_secret']:
            form['client_secret'] = client['client_secret']
        tokens = self.request(TOKEN_URL, form=form)
        if not tokens.get('access_token') or not tokens.get('refresh_token'):
            raise ValueError('Google 未提供持续读取授权，请重新连接')
        if tokens.get('scope') and not set(self.scope.split()).issubset(set(tokens['scope'].split())):
            raise ValueError('Google 未授予所需的 Gmail 权限')
        profile = self.request(GMAIL_URL + 'profile', token=tokens['access_token'])
        account = normalize_email(profile.get('emailAddress'))
        if self.grant_handler:
            self.grant_handler(account, client, tokens)
        else:
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


def _headers(value):
    headers={}
    for header in (value.get('payload') or {}).get('headers') or []:
        name=str(header.get('name','')).lower()
        headers[name]=', '.join(filter(None,(headers.get(name),str(header.get('value') or ''))))
    return headers


def parse_addresses(values):
    """Parse email addresses, filtering empty fields before Python 3.13's parser."""
    cleaned = [v for v in values if isinstance(v, str) and v.strip()]
    if not cleaned:
        return []
    found = []
    for _, address in getaddresses(cleaned):
        if not isinstance(address, str):
            continue
        address = address.strip().lower()
        if address and address not in found:
            found.append(address)
    return found


def parse_api_message(value, account, customers, thread_customers=()):
    payload = value.get('payload') or {}
    headers = _headers(value)
    senders = set(parse_addresses([headers.get('from', '')]))
    recipients = set(parse_addresses([headers.get('to', ''), headers.get('cc', ''), headers.get('bcc', '')]))
    if account in senders:
        direction, associated = 'outbound', recipients & customers
    elif account in recipients:
        direction, associated = 'inbound', (senders & customers) or (set(thread_customers) & customers)
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
        'reply_to': headers.get('reply-to', ''), 'rfc_message_id': headers.get('message-id', ''), 'references': headers.get('references', ''),
        'bcc': headers.get('bcc', ''), 'subject': headers.get('subject', ''), 'snippet': str(value.get('snippet') or ''),
        'body': body.strip(), 'translation_zh': None, 'attachments': attachments, 'body_truncated': truncated,
        'mail_kind': classify_mail(headers,direction=direction,labels=value.get('labelIds') or (),subject=headers.get('subject',''),body=body),
        'url': 'https://mail.google.com/mail/u/?authuser=' + account + '#all/' + thread if thread else None,
        'customer_emails': sorted(associated)}


class GmailOAuthMailbox:
    def __init__(self, account_email, *, request=_request, reader=load_credentials, ttl=120, clock=time.time, max_messages=50):
        self.account_email = normalize_email(account_email)
        self.request, self.reader, self.ttl, self.clock = request, reader, ttl, clock
        self.max_messages = max_messages
        self.lock = threading.RLock()
        self.inbox_lock = threading.Lock()
        self.token_lock = threading.Lock()
        self._token, self._token_expires, self._messages, self._cache = None, 0, {}, {}

    def _access_token(self):
        with self.token_lock:
            if self._token and self.clock() < self._token_expires - 30:
                return self._token
            saved = self.reader(self.account_email)
            if not saved:
                raise ValueError('请重新连接 Google 账号')
            form = {'client_id': saved['client_id'], 'refresh_token': saved['refresh_token'], 'grant_type': 'refresh_token'}
            if saved.get('client_secret'):
                form['client_secret'] = saved['client_secret']
            result = self.request(TOKEN_URL, form=form)
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
        observation = begin_observation(self, customers)
        before = after = None
        observation_coverage = True
        status = {'state': 'ready', 'account_email': self.account_email,
                  'last_success_at': old['result']['status'].get('last_success_at') if old else None, 'error': None}
        messages = copy.deepcopy(old['result']['messages']) if old else []
        try:
            token = self._access_token()
            if observation is not None:
                before = self._observation_history(token)
            terms = ' '.join('from:' + x + ' to:' + x for x in sorted(customers))
            query = '-in:drafts -in:spam -in:trash {' + terms + '}'
            listing = self.request(GMAIL_URL + 'messages?' + urlencode({'q': query, 'maxResults': self.max_messages}), token=token)
            found = []
            ids=[str(item.get('id') or '') for item in listing.get('messages') or []]
            observation_coverage = (isinstance(listing.get('messages', []), list)
                and all(re.fullmatch('[0-9a-fA-F]+',mid) for mid in ids)
                and (bool(ids) or not listing.get('resultSizeEstimate', 0)))
            ids=[mid for mid in ids if re.fullmatch('[0-9a-fA-F]+',mid)]
            def fetch_message(mid):
                with self.lock:raw=self._messages.get(mid)
                if force or observation is not None or raw is None:
                    raw=self.request(GMAIL_URL + 'messages/' + mid + '?format=full', token=token)
                    with self.lock:self._messages[mid]=raw
                return raw
            with ThreadPoolExecutor(max_workers=4) as pool:raw_messages=list(pool.map(fetch_message,ids))
            for mid,raw in zip(ids,raw_messages):
                if not isinstance(raw,dict) or raw.get('id')!=mid or not isinstance(raw.get('payload'),dict):
                    observation_coverage=False
                message = parse_api_message(raw, self.account_email, customers)
                if message:
                    found.append(message)
            # A buyer may reply from a colleague's address in the same
            # thread. Expand threads with our sent messages to retain that context.
            threads = {}
            for message in reversed(found):
                if message['direction']=='outbound' and re.fullmatch(r'\d+',str(message.get('thread_id') or '')):
                    threads.setdefault(format(int(message['thread_id']),'x'),set()).update(message.get('customer_emails') or [])
            seen={message['id'] for message in found}
            thread_incomplete=len(threads)>15
            def fetch_thread(item):
                tid,associated=item
                try:return associated,self.request(GMAIL_URL+'threads/'+tid+'?format=full',token=token)
                except Exception:return associated,None
            with ThreadPoolExecutor(max_workers=4) as pool:thread_results=list(pool.map(fetch_thread,list(threads.items())[:15]))
            for associated,thread in thread_results:
                if thread is None:thread_incomplete=True;continue
                if not isinstance(thread.get('messages'),list) or not thread.get('messages'):
                    observation_coverage=False
                sent_ids={}
                for raw in thread.get('messages') or []:
                    if set(raw.get('labelIds') or ()).intersection(('DRAFT','SPAM','TRASH')):continue
                    direct=parse_api_message(raw,self.account_email,customers)
                    if direct and direct['direction']=='outbound':
                        message_id=_headers(raw).get('message-id','').strip()
                        if message_id:sent_ids.setdefault(message_id,set()).update(set(direct['customer_emails']) & associated)
                for raw in thread.get('messages') or []:
                    if set(raw.get('labelIds') or ()).intersection(('DRAFT','SPAM','TRASH')):continue
                    mid=str(raw.get('id') or '')
                    if not re.fullmatch('[0-9a-fA-F]+',mid):continue
                    with self.lock:self._messages[mid]=raw
                    message=parse_api_message(raw,self.account_email,customers)
                    if not message:
                        headers=_headers(raw)
                        refs=re.findall(r'<[^<>]+>',headers.get('in-reply-to') or headers.get('references') or '')
                        matched=sent_ids.get(refs[-1],set()) if refs else set()
                        if not matched:
                            senders={a for a in parse_addresses([headers.get('from','')]) if '@' in a}
                            domains={a.rsplit('@',1)[1] for a in senders}-PUBLIC_MAIL_DOMAINS
                            matched={a for a in associated if a.rsplit('@',1)[-1] in domains}
                        message=parse_api_message(raw,self.account_email,customers,matched)
                    if message and message['id'] not in seen:
                        found.append(message);seen.add(message['id'])
            messages = sorted(found, key=lambda m: (m['sent_at'] or '', m['id']))
            notices=[]
            if listing.get('nextPageToken'):notices.append('仅显示最近 '+str(self.max_messages)+' 封匹配邮件')
            if thread_incomplete:notices.append('部分邮件线程未完整展开，请稍后更新')
            status.update(last_success_at=datetime.fromtimestamp(self.clock(), timezone.utc).isoformat(),
                loaded_count=len(messages), history_limited=bool(listing.get('nextPageToken')),
                thread_lookup_incomplete=thread_incomplete,history_note='；'.join(notices) or None)
            if observation is not None:
                after = self._observation_history(token)
        except Exception as exc:
            status.update(state='error', error=str(exc) if isinstance(exc, ValueError) else 'Google 邮件连接暂不可用，请检查网络后重试')
        complete = (observation_coverage and status['state'] == 'ready' and status.get('history_limited') is False
                    and status.get('thread_lookup_incomplete') is False
                    and all(isinstance(m.get('body'), str) and not m.get('body_truncated') for m in messages))
        status['shared_observation'] = finish_observation(self, observation, before=before, after=after,
            complete=complete, messages=messages, reason='query_failed_or_incomplete')
        dated = [m for m in messages if m['sent_at'] and m.get('mail_kind') not in ('promotion','automatic')]
        latest = max(dated, key=lambda m: (m['sent_at'], m['id']), default=None)
        pending = bool(latest and latest['direction'] == 'inbound') if status['state'] == 'ready' else None
        result = {'status': status, 'messages': messages, 'reply_pending': pending,
                  'next_action': '邮件同步尚未成功，请恢复连接后确认客户回复' if pending is None else
                                 '查看客户新回复并准备答复' if pending else '等待客户回复' if latest else '暂无已同步邮件'}
        with self.lock:
            self._cache[key] = {'result': result, 'last_poll': self.clock() if status['state'] == 'ready' else float('-inf')}
        return copy.deepcopy(result)

    def _observation_history(self, token):
        """A provider watermark, never a message date or local poll timestamp.

        Failure affects only observation certification, not existing sync or
        automatic dispatch behavior. A complete context needs equal endpoints.
        """
        try:
            value = self.request(GMAIL_URL + 'profile', token=token)
            if not isinstance(value, dict) or str(value.get('emailAddress') or '').lower() != self.account_email:
                return None
            return history_id(value.get('historyId'))
        except Exception:
            return None

    def buyer_candidates(self, known_emails, linked_ids=()):
        """Find likely new buyer inquiries; source mail remains in Gmail."""
        known={normalize_email(x) for x in known_emails}|{self.account_email}
        with self.inbox_lock:
            status={'state':'ready','last_success_at':None,'error':None}
            try:
                token=self._access_token()
                query='in:inbox newer_than:90d -in:spam -in:trash -in:drafts {shoe shoes footwear sneaker sneakers slipper sandals boots}'
                listing=self.request(GMAIL_URL+'messages?'+urlencode({'q':query,'maxResults':30}),token=token)
                ids=[str(x.get('id') or '') for x in listing.get('messages') or []]
                ids=[mid for mid in ids if re.fullmatch('[0-9a-fA-F]+',mid)]
                def fetch(mid):
                    with self.lock:raw=self._messages.get(mid)
                    if raw is None:
                        raw=self.request(GMAIL_URL+'messages/'+mid+'?format=full',token=token)
                        with self.lock:self._messages[mid]=raw
                    return raw
                with ThreadPoolExecutor(max_workers=4) as pool:raw_messages=list(pool.map(fetch,ids))
                items=[];seen=set();times={}
                for raw in raw_messages:
                    raw_id=str(raw.get('id') or '')
                    canonical_id=str(int(raw_id,16))
                    if canonical_id in linked_ids:continue
                    headers={str(h.get('name','')).lower():str(h.get('value','')) for h in (raw.get('payload') or {}).get('headers') or []}
                    raw_from=(headers.get('from','') or '').strip()
                    pairs=getaddresses([raw_from]) if raw_from else []
                    if not pairs:continue
                    name,address=pairs[0]
                    try:address=normalize_email(address)
                    except ValueError:continue
                    if address in known or address in seen:continue
                    message=parse_api_message(raw,self.account_email,{address})
                    if not message or message['direction']!='inbound' or message['mail_kind']!='conversation':continue
                    summary=new_buyer_summary(message['subject'],message['body'])
                    if not summary:continue
                    seen.add(address)
                    items.append({'id':message['id'],'thread_id':message['thread_id'],'email':address,
                        'contact_name':name[:200],'title':name[:200] or address.split('@')[-1],
                        'summary':summary,'subject':message['subject'],'sent_at':message['sent_at'],'url':message['url']})
                    times[message['id']]=int(raw.get('internalDate') or 0)
                def already_answered(item):
                    if not item.get('thread_id'):return None
                    try:thread=self.request(GMAIL_URL+'threads/'+format(int(item['thread_id']),'x')+'?format=metadata',token=token)
                    except Exception:return None
                    for raw in thread.get('messages') or []:
                        if set(raw.get('labelIds') or ()).intersection(('DRAFT','SPAM','TRASH')):continue
                        headers={str(h.get('name','')).lower():str(h.get('value','')) for h in (raw.get('payload') or {}).get('headers') or []}
                        senders=set(parse_addresses([headers.get('from','')]))
                        recipients=set(parse_addresses([headers.get(k,'') for k in ('to','cc','bcc')]))
                        if self.account_email in senders and item['email'] in recipients and int(raw.get('internalDate') or 0)>times[item['id']]:return True
                    return False
                with ThreadPoolExecutor(max_workers=4) as pool:answered=list(pool.map(already_answered,items))
                for item,value in zip(items,answered):item['answered']=value
                status.update(last_success_at=datetime.fromtimestamp(self.clock(),timezone.utc).isoformat(),
                              history_limited=bool(listing.get('nextPageToken')))
                return {'status':status,'items':items}
            except Exception as exc:
                status.update(state='error',error=str(exc) if isinstance(exc,ValueError) else '新买家邮件筛选暂未完成')
                return {'status':status,'items':[]}
