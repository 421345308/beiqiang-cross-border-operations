"""Explicit, read-only Google Search Console connection; credentials stay in keyring.

Official API: https://developers.google.com/webmaster-tools/v1/searchanalytics/query
No network requests are made by snapshot(). No Gmail authorization is reused.
"""
from __future__ import annotations

import copy
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import secrets
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from gmail_oauth import GmailOAuth, TOKEN_URL

SCOPE = 'https://www.googleapis.com/auth/webmasters.readonly'
SERVICE = 'Beiqiang.Workdesk.SearchConsole'
API = 'https://www.googleapis.com/webmasters/v3/sites'


class SearchConsoleAPIError(ValueError):
    """Safe, structured reason; raw provider responses never reach the UI."""
    def __init__(self, message, reason, status):
        super().__init__(message)
        self.reason, self.status = reason, status


def _api_error(status, payload, url):
    error = payload.get('error', {}) if isinstance(payload, dict) else {}
    if not isinstance(error, dict):
        error = {}
    reasons = {item.get('reason') for item in error.get('errors', []) if isinstance(item, dict)}
    reasons.update(item.get('reason') for item in error.get('details', []) if isinstance(item, dict))
    if status == 403 and reasons.intersection({'SERVICE_DISABLED', 'accessNotConfigured', 'API_DISABLED'}):
        return SearchConsoleAPIError('此 OAuth 客户端所属 Google Cloud 项目尚未启用 Search Console API；启用后刷新站点列表即可，无需重新授权', 'api_disabled', status)
    if status == 403 and reasons.intersection({'ACCESS_TOKEN_SCOPE_INSUFFICIENT', 'insufficientPermissions'}):
        return SearchConsoleAPIError('Google 搜索授权缺少只读搜索权限，请重新授权', 'insufficient_scope', status)
    if status == 403 and '/searchAnalytics/' in url and reasons.intersection({'forbidden', 'PERMISSION_DENIED'}):
        return SearchConsoleAPIError('当前 Google 账号没有此 Search Console 站点的读取权限，请选择有权访问的站点', 'site_permission_denied', status)
    messages = {400: 'Google 授权或查询参数无效，请重新授权或调整日期',
                401: 'Google 搜索授权已失效，请重新授权',
                403: 'Google 拒绝此搜索接口请求，具体原因尚未识别；请检查项目 API 启用状态和账号权限',
                429: 'Google 查询额度暂时用尽，请稍后刷新'}
    return SearchConsoleAPIError(messages.get(status, 'Google 搜索接口暂不可用（HTTP %s）' % status),
                                 'unauthorized' if status == 401 else 'rate_limited' if status == 429 else 'request_rejected', status)


def _read(_account='default'):
    import keyring
    raw = keyring.get_password(SERVICE, 'default')
    return json.loads(raw) if raw else None


def _save(_account, value):
    import keyring
    keyring.set_password(SERVICE, 'default', json.dumps(value))


def _request(url, *, token=None, form=None, body=None):
    headers = {'Accept': 'application/json'}
    data = None
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if form is not None:
        data = urlencode(form).encode()
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    elif body is not None:
        data = json.dumps(body).encode()
        headers['Content-Type'] = 'application/json'
    try:
        with urlopen(Request(url, data=data, headers=headers), timeout=25) as response:
            return json.load(response)
    except HTTPError as exc:
        try:
            payload = json.loads(exc.read(65536))
        except (ValueError, OSError):
            payload = {}
        raise _api_error(exc.code, payload, url) from None
    except (URLError, TimeoutError):
        raise ValueError('Google 搜索服务暂时无法连接，请稍后刷新') from None


class SearchConsoleOAuth(GmailOAuth):
    """Reuse desktop-client validation, PKCE, consent URL and pending-state lock."""
    def finish(self, state, code):
        with self.lock:
            pending = self.pending
            if not pending or not secrets.compare_digest(str(state or ''), pending['state']):
                raise ValueError('Google 登录已过期，请重新发起搜索授权')
            self.pending = None
        if self.clock() - pending['started_at'] > 900 or not code:
            raise ValueError('Google 搜索授权未完成，请重新发起')
        client = pending['client']
        tokens = self.request(TOKEN_URL, form={**client, 'code': code,
            'code_verifier': pending['verifier'], 'grant_type': 'authorization_code',
            'redirect_uri': pending['redirect_uri']})
        if not tokens.get('access_token') or not tokens.get('refresh_token') or SCOPE not in tokens.get('scope', '').split():
            raise ValueError('Google 未授予完整的只读搜索离线权限')
        # Consent and API availability are separate. Preserve the approved grant
        # even when sites.list is unavailable, so enabling the API needs no new consent.
        self.saver('default', {**client, 'refresh_token': tokens['refresh_token'],
            'scopes': [SCOPE], 'authorized_at': datetime.now(timezone.utc).isoformat()})
        return {'state': 'authorized', 'scope': SCOPE}


class SearchConsole:
    def __init__(self, local_dir, *, request=_request, reader=_read, saver=_save, clock=time.time):
        self.path = Path(local_dir) / 'search-console.json'
        self.request, self.reader, self.clock = request, reader, clock
        self.lock = threading.RLock()
        self.refresh_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self.oauth = SearchConsoleOAuth(request=request, reader=reader, saver=saver, clock=clock, scope=SCOPE)
        try:
            self.state = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self.state = {}

    def _persist(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.state, ensure_ascii=False), encoding='utf-8')
        tmp.replace(self.path)

    def start(self, config, redirect_uri):
        if not config:
            saved = self.reader('default')
            if not saved:
                raise ValueError('请先选择 Google Cloud 下载的桌面应用客户端 JSON')
            config = {'installed': {k: saved.get(k, '') for k in ('client_id', 'client_secret')}}
        return self.oauth.start(config, redirect_uri)

    def finish(self, state, code):
        result = self.oauth.finish(state, code)
        with self.lock:
            # A new authorization may be for a different Google account.
            self.state = {'state': 'select_site'}
            self._persist()
        return result

    def _token(self):
        saved = self.reader('default')
        if not saved or SCOPE not in saved.get('scopes', []):
            raise ValueError('请先连接 Google Search Console，只读邮件授权不能读取搜索数据')
        form = {k: saved[k] for k in ('client_id', 'client_secret', 'refresh_token') if saved.get(k)}
        result = self.request(TOKEN_URL, form={**form, 'grant_type': 'refresh_token'})
        if not result.get('access_token'):
            raise ValueError('Google 搜索授权已失效，请重新授权')
        return result['access_token']

    def sites(self):
        result = self.request(API, token=self._token())
        return {'items': [r for r in result.get('siteEntry', []) if r.get('permissionLevel') != 'siteUnverifiedUser']}

    def select_site(self, site_url):
        if site_url not in [s.get('siteUrl') for s in self.sites()['items']]:
            raise ValueError('请选择当前 Google 账号有权读取的 Search Console 站点')
        with self.lock:
            self.state = {'state': 'not_loaded', 'site_url': site_url}
            self._persist()
        return self.snapshot()

    def snapshot(self):
        with self.lock:
            return copy.deepcopy({'source': 'Google Search Console', 'state': 'not_connected',
                'scope': SCOPE, 'available': False, **self.state,
                'notice': 'Google 自然搜索数据；不是网站总访问或成交。日期按太平洋时间；查询因隐私可能省略，API只返回主要行，不能将查询行相加充当总量。'})

    def start_auto(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        def run():
            while not self._stop.is_set():
                state = self.snapshot()
                last = state.get('last_success_at')
                try:
                    age = self.clock() - datetime.fromisoformat(last.replace('Z', '+00:00')).timestamp()
                except (AttributeError, TypeError, ValueError):
                    age = float('inf')
                if state.get('site_url') and age >= 24 * 60 * 60:
                    self.refresh()
                self._stop.wait(60 * 60)
        self._thread = threading.Thread(target=run, daemon=True, name='search-console-sync')
        self._thread.start()

    def stop(self):
        self._stop.set()

    def refresh(self, start_date=None, end_date=None):
        # Leave a 3-day lag by default and request finalized data only.
        end = date.fromisoformat(end_date) if end_date else date.today() - timedelta(days=3)
        start = date.fromisoformat(start_date) if start_date else end - timedelta(days=27)
        if start > end or (end - start).days > 480 or end > date.today():
            raise ValueError('请选择有效日期范围（最多481天，结束不晚于今天）')
        with self.refresh_lock:
            with self.lock:
                site = self.state.get('site_url')
            if not site:
                raise ValueError('请先连接 Google 并选择本站 Search Console 站点')
            try:
                token = self._token()
                url = API + '/' + quote(site, safe='') + '/searchAnalytics/query'
                tables = {}
                for name, dimensions in [('totals', []), ('dates', ['date']), ('queries', ['query']),
                                         ('pages', ['page']), ('countries', ['country'])]:
                    raw = self.request(url, token=token, body={'startDate': start.isoformat(),
                        'endDate': end.isoformat(), 'type': 'web', 'dataState': 'final',
                        'dimensions': dimensions, 'rowLimit': 1000})
                    tables[name] = raw.get('rows', [])
                now = datetime.fromtimestamp(self.clock(), timezone.utc).isoformat()
                updated = {'state': 'ready', 'available': True, 'site_url': site,
                    'last_success_at': now, 'period': {'start': start.isoformat(), 'end': end.isoformat(),
                    'timezone': 'America/Los_Angeles', 'data_state': 'final', 'search_type': 'web'},
                    'tables': tables, 'row_limit': 1000, 'rows_may_be_incomplete': True}
            except ValueError as exc:
                updated = {'state':'error', 'error':str(exc), 'available':False}
            with self.lock:
                if self.state.get('site_url') == site:
                    if updated['state']=='ready':self.state = updated
                    else:self.state.update(updated)
                    self._persist()
                return self.snapshot()
