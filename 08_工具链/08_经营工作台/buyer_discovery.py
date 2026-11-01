"""Bounded company discovery through the existing Firecrawl public-search service.

Standard library only; no website scraping, CRM writes or outbound messages.
Search snippets are candidates, never verified buyer identities or import counts.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit, urlencode

API = 'https://api.firecrawl.dev/v2/'


def _base(keyword):
    return {'status': 'success', 'records': [], 'keyword': keyword,
            'source': 'Firecrawl 公开网页搜索', 'current_demand_confirmed': False,
            'notice': '搜索结果仅作公司候选；企业身份、采购角色与当前需求须核实，不自动加入CRM。',
            'manual_search_url': 'https://www.google.com/search?' + urlencode({'q': keyword + ' footwear importer distributor'})}


def _call(path, key, payload=None):
    request = urllib.request.Request(API + path,
        data=json.dumps(payload).encode('utf-8') if payload else None,
        headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    # Never forward the API credential through a redirect.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    with urllib.request.build_opener(NoRedirect).open(request, timeout=15) as response:
        raw = response.read(500_001)
    if len(raw) > 500_000:
        raise ValueError('搜索响应超过读取上限')
    return json.loads(raw)


def _worker(keyword, limit):
    result = _base(keyword)
    key = os.environ.get('FIRECRAWL_API_KEY', '').strip()
    if not key:
        return dict(result, status='unavailable', error='当前运行环境未配置公开搜索服务，可打开搜索链接继续研究。')
    try:
        credits = _call('team/credit-usage', key)
        if credits.get('data', {}).get('remainingCredits', 0) < 2:
            return dict(result, status='unavailable', error='现有公开搜索额度不足，未发起搜索。')
        data = _call('search', key, {'query': keyword + ' footwear importer distributor brand',
                                    'limit': min(limit, 10), 'sources': ['web']})
        if not data.get('success'):
            return dict(result, status='failed', error='公开搜索服务未成功返回。')
        seen = set()
        for row in data.get('data', {}).get('web', [])[:limit]:
            if not isinstance(row, dict):
                continue
            source = row.get('url')
            if not isinstance(source, str):
                continue
            parsed = urlsplit(source)
            if parsed.scheme not in {'https', 'http'} or not parsed.hostname or parsed.username is not None or parsed.password is not None:
                continue
            if source in seen:
                continue
            title = str(row.get('title') or '').strip()
            if not title:
                continue
            seen.add(source)
            result['records'].append({'company': title[:250], 'source_title': title[:500],
                'source_url': source, 'excerpt': str(row.get('description') or '')[:1000],
                'identity_status': 'unverified', 'requires_confirmation': True,
                'discovery_method': 'public_search', 'current_demand_confirmed': False})
        result['credits_used'] = data.get('creditsUsed')
        return result
    except urllib.error.HTTPError as exc:
        return dict(result, status='failed', error='公开搜索服务 HTTP ' + str(exc.code))
    except Exception:
        return dict(result, status='failed', error='公开搜索服务暂不可用。')


def search_buyers(keyword='footwear', limit=10, timeout_seconds=45):
    if not isinstance(keyword, str) or not keyword.strip() or len(keyword) > 120:
        raise ValueError('请输入120字以内的关键词')
    if type(limit) is not int or not 1 <= limit <= 30:
        raise ValueError('每次查看1至30个候选')
    keyword = keyword.strip()
    try:
        proc = subprocess.run([sys.executable, '-X', 'utf8', str(Path(__file__).resolve()), '--worker', keyword, str(limit)],
            capture_output=True, text=True, encoding='utf-8', timeout=max(1, min(60, timeout_seconds)))
    except subprocess.TimeoutExpired:
        return dict(_base(keyword), status='timeout', error='买家搜索超时')
    if proc.returncode:
        return dict(_base(keyword), status='failed', error='公开搜索服务暂不可用')
    try:
        result = json.loads(proc.stdout)
        if not isinstance(result, dict) or not isinstance(result.get('records'), list):
            raise ValueError('invalid result')
        return result
    except ValueError:
        return dict(_base(keyword), status='failed', error='数据源返回格式无效')


if __name__ == '__main__':
    print(json.dumps(_worker(sys.argv[2], int(sys.argv[3])), ensure_ascii=False))
