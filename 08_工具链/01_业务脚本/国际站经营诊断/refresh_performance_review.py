"""Join visible complete-week rows to current catalog; never fill absent rows with 0.

Raw backend pages stay in the ignored evidence directory. This tool performs no
platform writes and makes no causal or profit claims from traffic or list prices.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / '02_Alibaba运营/01_店铺与全店诊断'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def number(value):
    try:
        d = Decimal(str(value))
        return float(d) if d.is_finite() and d > 0 else None
    except (InvalidOperation, ValueError):
        return None


def build(evidence, catalog_path):
    pages = [read(evidence / f'week41_page_{i}.json') for i in range(1, 15)]
    assert [p['page'] for p in pages] == [f'{i}/14' for i in range(1, 15)]
    rows = [r for p in pages for r in p['rows']]
    assert len(rows) == len({r['id'] for r in rows}) == 411
    keys = ['search_impressions', 'search_clicks', 'visitors', 'inquiries', 'tm_buyers', 'marketing_clicks']
    metrics = {}
    for row in rows:
        assert len(row['values']) == len(keys)
        values = [int(v) for v in row['values']]
        assert all(v >= 0 for v in values)
        metrics[row['id']] = dict(zip(keys, values))
    totals = {k: sum(r[k] for r in metrics.values()) for k in keys}
    assert totals['search_impressions'] == 62348
    assert totals['search_clicks'] == 866
    assert totals['visitors'] == 1520
    assert totals['inquiries'] == 24
    catalog = read(catalog_path)
    assert catalog['complete'] and catalog['unique_ids'] == 488
    # list.product_id is an opaque platform token; list.id is the numeric public ID.
    current = {str(p['id']): p for p in catalog['products']}
    assert len(current) == 488
    assert all(pid.isdecimal() for pid in current)
    assert set(metrics) <= set(current), '报表与当前目录身份未完整对应，停止生成'
    listings = {x['id']: x for x in read(ROOT / '02_Alibaba运营/05_扩品工程/数据/国际站商品.json')['listings']}
    products = {x['id']: x for x in read(ROOT / '00_总控台/产品中心/数据/产品.json')['products']}
    sources = {x['id']: x for x in read(ROOT / '00_总控台/产品中心/数据/供应来源.json')['sources']}
    cost_path = ROOT / '00_总控台/产品中心/数据/.local/生产成本基线.json'
    confirmed_costs = read(cost_path) if cost_path.exists() else {}
    old = read(BASE / '商品诊断数据.json')
    previous = {p['id']: p for p in old['products']}
    result = []
    state_overlay_ids = []
    for pid, item in current.items():
        listing = listings.get(pid, {})
        identity = products.get(listing.get('product_id'), {})
        source = sources.get(listing.get('bound_source_id') or identity.get('adopted_source_id'), {})
        prior = previous.get(pid, {})
        metric = metrics.get(pid)
        formal = ROOT / '02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品' / pid / 'formal_get.json'
        formal_record = read(formal) if formal.exists() else {}
        p = formal_record.get('response', {}).get('product', {})
        if p and formal_record.get('observed_at_utc', '') > catalog['observed_at_utc']:
            assert p['product_id'] == item['product_id'], '精确ID回读身份不一致'
            item.update({k: p[k] for k in ('status', 'display', 'subject', 'gmt_modified') if k in p})
            state_overlay_ids.append(pid)
        created = item.get('gmt_create', '')[:10]
        replaced = prior.get('physical_source_changed_on')
        signals = []
        if item.get('status') in ('modified', 'new'):
            action = '平台审核中；保留回执不重复提交'
        elif item.get('display') != 'Y' or item.get('status') != 'approved':
            action = '保留当前下架或退回状态'
        elif created > '2026-10-17':
            action = '晚于报表窗口的新商品'
        elif replaced and replaced >= '2026-10-11':
            action = '换款与统计窗口重叠，先按新鞋核对'
        elif metric is None:
            action = '报表无行，核零效果列表与存续时间'
        elif metric['inquiries'] or metric['tm_buyers']:
            action = '已有咨询，改善有效采购承接'
        elif metric['visitors'] >= 25:
            action = '有访客无咨询，优先核流量与报价'
        elif metric['search_impressions'] >= 250 and metric['search_clicks'] / metric['search_impressions'] < .008:
            action = '有曝光低点击，核关键词与首图'
        elif metric['search_impressions'] <= 10:
            action = '曝光不足，核类目需求与检索覆盖'
        else:
            action = '样本较少，补需求与竞品依据'
        if metric:
            if metric['search_impressions'] >= 250 and metric['search_clicks'] / metric['search_impressions'] < .008:
                signals.append('曝光≥250且搜索点击率<0.8%，复核信号并非原因')
            if metric['visitors'] >= 25 and not (metric['inquiries'] or metric['tm_buyers']):
                signals.append('访客≥25且询盘/TM均为0，不能据此推断价格原因')
        tier_sets = []
        for sku in p.get('product_sku', {}).get('skus', []):
            tiers = sku.get('bulk_discount_prices', [])
            if tiers and tiers not in tier_sets:
                tier_sets.append(tiers)
        cost = number(source.get('price'))
        cost_state = ('自有原包成本需按版本核算，不以零售标价代成本' if identity.get('raw_packages') and not source else
                      '公开来源标价，费用及当天供货仍待核' if cost else
                      '当前采购报价未完整核实')
        if not source and pid in confirmed_costs.get('listing_ids', []) and identity.get('id') in confirmed_costs.get('families', {}):
            cost_state = '负责人已确认生产成本基线；适用履约费用另核'
        result.append({
            'id': pid, 'model': listing.get('model'), 'family': listing.get('product_id'),
            'title': item.get('subject'), 'status': item.get('status'), 'display': item.get('display'),
            'url': item.get('pc_detail_url') or listing.get('url'),
            'created_on': created, 'physical_source_changed_on': replaced,
            'week41': metric, 'current_action': action, 'signals': signals,
            'week40': prior.get('periods', {}).get('week40'),
            'source_id': source.get('id'), 'source_url': source.get('url'),
            'source_model': source.get('model'), 'source_price': source.get('price'),
            'source_currency': source.get('currency'), 'source_observed_on': source.get('observed_at'),
            'cost_state': cost_state, 'current_price_tier_sets': tier_sets,
            'trade': p.get('sourcing_trade'),
            'price_revision': listing.get('price_review'),
            'same_product_price_state': '基线降价状态见price_revision；同条件竞品及完整费用仍需分别核对',
            'current_formal_reference': formal.relative_to(ROOT).as_posix(),
            'attribution_note': '10月17–21日图文/价格修改与本窗口重叠或晚于本窗口，不能判为改后效果',
        })
    now = datetime.now(timezone.utc).isoformat()
    summary = {
        'observed_at': now, 'catalog_observed_at': catalog['observed_at_utc'],
        'period': '2026-10-11~2026-10-17', 'timezone': '平台标示PST，过滤中国大陆',
        'catalog_ids': len(current), 'reported_ids': len(metrics),
        'current_catalog_reported_ids': len(set(current) & set(metrics)),
        'report_rows_outside_current_catalog': sorted(set(metrics) - set(current)),
        'totals': totals,
        'catalog_states': dict(Counter(f"{p.get('status')}/{p.get('display')}" for p in current.values())),
        'newer_exact_id_state_overlay_ids': state_overlay_ids,
        'actions': dict(Counter(x['current_action'] for x in result)),
        'cost_states': dict(Counter(x['cost_state'] for x in result)),
        'scope': '完整当前488条与14页411行匹配；无行保持null；总量跨商品未去重；搜索不减营销点击',
        'report_builder_platform_mutations': 0,
        'linked_price_revision_states': dict(Counter(x['price_revision']['state'] for x in result if x['price_revision'])),
    }
    output = {'schema_version': 1, 'summary': summary, 'products': result}
    write(BASE / '经营复核.json', output)
    old['latest_review'] = {'file': '经营复核.json', 'period': summary['period'], 'observed_at': now,
                            'note': '原分期与处置证据保留；当前经营判断以此完整周复核为准'}
    write(BASE / '商品诊断数据.json', old)
    render(output)
    print(json.dumps(summary, ensure_ascii=False))


def render(data):
    def esc(v):
        return html.escape(str(v if v is not None else '未核'))
    body = []
    for x in sorted(data['products'], key=lambda x: -(x['week41'] or {}).get('search_impressions', -1)):
        m = x['week41']
        ctr = f"{100*m['search_clicks']/m['search_impressions']:.2f}%" if m and m['search_impressions'] else '—'
        nums = [m[k] if m else '无行' for k in ['search_impressions','search_clicks','visitors','inquiries','tm_buyers']]
        price = ' / '.join(', '.join(f"{t['start_quantity']}双 ${t['price']}" for t in ts) for ts in x['current_price_tier_sets']) or '未返回'
        source = ('<br><a href="'+esc(x['source_url'])+'">核对来源 '+esc(x['source_model'])+'</a><small>'+esc(x['source_currency'])+' '+esc(x['source_price'])+' · '+esc(x['source_observed_on'])+'</small>') if x['source_url'] else ''
        body.append('<tr data-action="'+esc(x['current_action'])+'"><td><a href="'+esc(x['url'])+'">'+esc(x['model'])+'</a><small>'+esc(x['id'])+'</small></td>'+''.join('<td>'+esc(n)+'</td>' for n in nums[:2])+'<td>'+ctr+'</td>'+''.join('<td>'+esc(n)+'</td>' for n in nums[2:])+ '<td>'+esc(x['current_action'])+'</td><td>'+esc(price)+'</td><td>'+esc(x['cost_state'])+source+'</td></tr>')
    actions = ''.join('<option>'+esc(a)+'</option>' for a in data['summary']['actions'])
    page = '''<!doctype html><meta charset="utf-8"><title>商品经营复核</title><style>body{font:15px system-ui;margin:28px;background:#f5f7fb;color:#18304a}h1{font-size:26px}p{max-width:1100px;line-height:1.7}input,select{padding:10px;margin:8px}table{border-collapse:collapse;width:100%;background:white;font-size:13px}th,td{padding:10px;text-align:left;border-bottom:1px solid #ddd}th{position:sticky;top:0;background:#dfeafb}small{display:block;color:#607082}a{color:#1550a1}td:nth-child(9){min-width:210px}</style><h1>商品经营复核 · 2026年10月21日</h1><p>完整周：10月11–17日（平台PST，过滤大陆）。当前488条，报表411行。无行不当零；搜索和营销不能相减，询盘和TM不相加当去重买家。最近图文及价格变更尚不能由本窗口评价效果。</p><p>完全同款、同数量、同包装和费用条件下，价格目标不高于竞品并覆盖成本和利润。价格来自同ID当前回读；<a href="价格复核.html">降价执行与审核状态见价格复核</a>。公开供方标价不是订单采购合同，不据本表宣称全店低于同行。10月17日确认的针织鞋50/48/45元基线优先于旧通用算法。</p><input id="q" placeholder="搜索货号或商品ID"><select id="action"><option value="">全部处理方向</option>'''+actions+'''</select><p id="count"></p><table><thead><tr><th>商品</th><th>搜索曝光</th><th>搜索点击</th><th>点击率</th><th>访客</th><th>询盘</th><th>TM</th><th>处理方向</th><th>当前数量价</th><th>成本依据</th></tr></thead><tbody>'''+''.join(body)+'''</tbody></table><script>function filter(){let n=0;document.querySelectorAll('tbody tr').forEach(r=>{let ok=r.innerText.toLowerCase().includes(q.value.toLowerCase())&&(!action.value||r.dataset.action===action.value);r.hidden=!ok;if(ok)n++});count.textContent='当前显示 '+n+' 条'}q.oninput=filter;action.onchange=filter;filter();</script>'''
    (BASE / '经营复核.html').write_text(page, encoding='utf-8')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--evidence', type=Path, required=True)
    ap.add_argument('--catalog', type=Path, required=True)
    args = ap.parse_args()
    build(args.evidence, args.catalog)
