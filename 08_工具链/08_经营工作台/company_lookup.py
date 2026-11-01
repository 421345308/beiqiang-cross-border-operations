"""Read-only website candidates; a source mention never establishes identity.

Existing Firecrawl credits search public company names. ImportYeti's public
company page provides a fallback. Search snippets are discovery evidence only.
No guessed domains, CRM mutation, login or outbound communication.
"""
from __future__ import annotations
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request
import urllib.error
from urllib.parse import urlencode, urlsplit

from prospect_research import _core, _now


def _identity(obj):
    if not isinstance(obj, dict) or obj.get('kind') != 'prospect':
        raise ValueError('请选择主动开发候选对象')
    try:
        body = json.loads(obj.get('content') or '{}')
    except (TypeError, ValueError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    company = obj.get('company') or body.get('company') or obj.get('name') or obj.get('title')
    if not isinstance(company, str) or not company.strip() or len(company) > 250:
        raise ValueError('候选缺少可用公司名称')
    refs = [body.get('company_url'), obj.get('company_url')]
    for row in list(obj.get('links') or []) + list(obj.get('evidence') or []) + list(body.get('evidence') or []):
        refs.append(row.get('url') if isinstance(row, dict) else row)
    source = next((u for u in refs if isinstance(u, str) and
                   urlsplit(u).scheme == 'https' and
                   urlsplit(u).netloc in {'www.importyeti.com', 'importyeti.com'} and
                   re.fullmatch(r'/company/[a-zA-Z0-9-]+/?', urlsplit(u).path) and
                   not urlsplit(u).query), None)
    return company.strip(), source


def _base(obj):
    company, source = _identity(obj)
    query = '"' + company.replace('"', '') + '" official website'
    return {'object_id': obj.get('id'), 'company': company, 'status': 'not_found',
            'checked_at': _now(), 'source_url': source, 'candidates': [], 'attempts': [],
            'manual_search_url': 'https://www.google.com/search?' + urlencode({'q': query}),
            'selection_required': True, 'current_demand_confirmed': False,
            'limitations': ['公司名称和第三方官网字段均不足以确认企业身份；请对照公司名称、地址及业务后选择。',
                            '搜索摘要只作发现线索，不证明官网身份或当前采购意向；未猜测域名。']}


def _firecrawl_search(company):
    key = os.environ.get('FIRECRAWL_API_KEY')
    if not key:
        return {'status': 'unavailable', 'error': '当前运行环境未配置公开搜索服务', 'rows': []}
    headers = {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}
    def call(path, payload=None):
        req = urllib.request.Request('https://api.firecrawl.dev/v2/' + path,
            data=json.dumps(payload).encode() if payload else None, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read(500_000))
    try:
        credit = call('team/credit-usage')
        if credit.get('data', {}).get('remainingCredits', 0) < 2:
            return {'status': 'unavailable', 'error': '现有搜索额度不足，未发起搜索', 'rows': []}
        data = call('search', {'query': '"' + company.replace('"', '') + '" official website',
                              'limit': 5, 'sources': ['web']})
        if not data.get('success'):
            return {'status': 'failed', 'error': '公开搜索服务未成功返回', 'rows': []}
        return {'status': 'read', 'rows': data.get('data', {}).get('web', []),
                'credits_used': data.get('creditsUsed')}
    except urllib.error.HTTPError as exc:
        return {'status': 'failed', 'error': '公开搜索服务 HTTP ' + str(exc.code), 'rows': []}
    except Exception:
        return {'status': 'failed', 'error': '公开搜索服务暂不可用', 'rows': []}


def _search_candidates(result, response):
    result['attempts'].append({'source': 'Firecrawl public search', 'status': response['status'],
                              'error': response.get('error'), 'credits_used': response.get('credits_used')})
    core = _core()
    company_words = set(re.findall(r'[a-z0-9]+', result['company'].lower())) - {'inc', 'llc', 'ltd', 'corp', 'the'}
    directories = {'zoominfo.com', 'bloomberg.com', 'importyeti.com', 'dnb.com', 'panjiva.com', 'importgenius.com'}
    for row in response.get('rows', [])[:5]:
        if not isinstance(row, dict):
            continue
        title, excerpt, source = str(row.get('title') or ''), str(row.get('description') or ''), row.get('url')
        words = set(re.findall(r'[a-z0-9]+', (title + ' ' + excerpt).lower()))
        if not company_words or not company_words.issubset(words) or not isinstance(source, str):
            continue
        try:
            source = core.normalize_url(source)
        except ValueError:
            continue
        mentions = re.findall(r'(?:website\s*(?:is|:)\s*)(https?://[^\s;,<>]+|www\.[a-z0-9.-]+\.[a-z]{2,})', excerpt, re.I)
        host = core.host_key(source)
        distinctive = company_words - {'footwear', 'shoe', 'shoes', 'group', 'company', 'international', 'brands'}
        domain_match = any(len(word) >= 4 and word in host.split('.')[0] for word in distinctive)
        if domain_match and not core.blocked_platform(source) and not any(host == d or host.endswith('.' + d) for d in directories):
            mentions.append(source)
        for mention in mentions:
            try:
                website = core.normalize_url(mention.rstrip('.)'))
            except ValueError:
                continue
            if core.blocked_platform(website) or any(core.host_key(website) == d or core.host_key(website).endswith('.' + d) for d in directories):
                continue
            existing = next((c for c in result['candidates'] if core.host_key(c['website']) == core.host_key(website)), None)
            if existing:
                existing.setdefault('supporting_sources', []).append({'url': source, 'excerpt': excerpt[:500]})
                continue
            result['candidates'].append({'website': website, 'source_url': source, 'source_title': title,
                'evidence': excerpt[:500], 'identity_status': 'unverified', 'requires_confirmation': True,
                'discovery_method': 'public_search'})
    if result['candidates']:
        result['status'] = 'candidates'


def _lookup(obj, transport=None, searcher=None):
    result = _base(obj)
    if searcher is not None or transport is None:
        response = (searcher or _firecrawl_search)(result['company'])
        _search_candidates(result, response)
        if result['candidates']:
            return result
    if not result['source_url']:
        result['attempts'].append({'status': 'missing_source', 'error': '候选未记录可读取的ImportYeti公司页'})
        if result['attempts'][0].get('status') in ('failed', 'unavailable'):
            result['status'] = result['attempts'][0]['status']
        return result
    source = result['source_url']
    try:
        response = (transport or _core().PublicTransport()).get(source, limit=1_000_000)
        attempt = {'url': source, 'final_url': response['url'], 'http_status': response['status']}
        result['attempts'].append(attempt)
        if response['status'] != 200:
            attempt.update(status='failed', error='公开公司页暂不可读取')
            result['status'] = 'failed'
            return result
        if urlsplit(response['url']).hostname not in {'www.importyeti.com', 'importyeti.com'}:
            attempt.update(status='failed', error='来源跳转至其他站点，未采纳官网字段')
            result['status'] = 'failed'
            return result
        attempt['status'] = 'read'
        # Handles ordinary JSON and the escaped JSON string in the public RSC page.
        for text in (response['body'], response['body'].replace('\\"', '"')):
            for value in re.findall(r'"website"\s*:\s*"([^"<>]{1,500})"', text):
                value = html.unescape(value).replace('\\/', '/')
                try:
                    url = _core().normalize_url(value)
                    host = urlsplit(url).hostname
                    if _core().blocked_platform(url) or host in {'importyeti.com', 'www.importyeti.com'}:
                        continue
                    # Validation rejects local/private URLs before showing a selectable candidate.
                    import ipaddress
                    try:
                        if not ipaddress.ip_address(host).is_global:
                            continue
                    except ValueError:
                        if '.' not in host or host.endswith(('.local', '.localhost')):
                            continue
                except (ValueError, TypeError):
                    continue
                if any(c['website'] == url for c in result['candidates']):
                    continue
                result['candidates'].append({'website': url, 'source_url': source,
                    'evidence': '公开公司页 website 字段：' + value,
                    'identity_status': 'unverified', 'requires_confirmation': True})
                if len(result['candidates']) >= 3:
                    break
        if result['candidates']:
            result['status'] = 'candidates'
        else:
            attempt['error'] = '公开页面未提供可用官网字段，可能为空或页面需要交互'
    except Exception as exc:
        result['status'] = 'failed'
        result['attempts'].append({'url': source, 'status': 'failed', 'error': str(exc)[:240]})
    return result


def lookup_company(prospect_object, timeout_seconds=30):
    result = _base(prospect_object)
    if type(timeout_seconds) not in (int, float) or not 1 <= timeout_seconds <= 60:
        raise ValueError('官网查找时限应为1至60秒')
    flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    proc = subprocess.Popen([sys.executable, '-X', 'utf8', str(Path(__file__).resolve()), '--worker'],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding='utf8', **flags)
    try:
        stdout, _ = proc.communicate(json.dumps(prospect_object, ensure_ascii=False), timeout=timeout_seconds)
        if proc.returncode:
            raise ValueError('官网来源查询未返回有效结果')
        return json.loads(stdout)
    except subprocess.TimeoutExpired:
        proc.kill(); proc.communicate()
        result.update(status='timeout', attempts=[{'status': 'timeout', 'error': '已停止超时查询，可人工搜索或输入官网'}])
    except (ValueError, TypeError):
        result.update(status='failed', attempts=[{'status': 'failed', 'error': '官网来源查询未返回有效结果'}])
    return result


if __name__ == '__main__' and sys.argv[1:] == ['--worker']:
    print(json.dumps(_lookup(json.load(sys.stdin)), ensure_ascii=False))
