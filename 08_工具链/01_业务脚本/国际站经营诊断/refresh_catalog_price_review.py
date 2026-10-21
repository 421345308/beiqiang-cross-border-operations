"""Build a complete, dated price review from exact-ID API and public-source evidence.

This report is derived; the product/source/channel registry remains canonical.
No platform mutations. --sync-sources updates public quote observations and
links to existing price verification, never asserts manufacturing/net costs.
"""
from pathlib import Path
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
import html
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / '08_工具链/06_工作区维护'))
from product_registry import ProductRegistry


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def rel(path):
    return path.resolve().relative_to(ROOT).as_posix()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--sync-sources', action='store_true')
    args = parser.parse_args()
    catalog = load(args.catalog)
    assert catalog['complete'] and len(catalog['products']) == catalog['unique_ids'] == catalog['total_item']
    registry = ProductRegistry(ROOT)
    data = load(registry)
    listings = {x['id']: x for x in data['listings']}
    products = {x['id']: x for x in data['products']}
    sources = {x['id']: x for x in data['sources']}
    observations = {x['source_id']: x for x in load(args.evidence / '来源现价.json')['items']}
    fx_check = load(args.evidence / '汇率复算.json')
    fx_reference = Decimal(fx_check['usd_cny_reference'])
    quotes = {}
    for o in observations.values():
        if o['state'] == 'CURRENT_SOURCE_PRICE_OBSERVED':
            quotes[o['source_id']] = {'source_id': o['source_id'], 'at': o['observed_at'],
                'currency': 'CNY', 'unit': 'Pair', 'tiers': [[None, None, str(o['price_cny'])]],
                'scope': '页面单价；未证明采购数量折扣或当日库存', 'model': o['supplier_model'],
                'evidence': rel(args.evidence / '来源' / o['source_id'] / 'observation.json')}
    for o in load(args.evidence / 'MIC公开数量报价.json'):
        tiers = o['parsed_pricing_tiers']
        quotes[o['source_id']] = {'source_id': o['source_id'], 'at': o['observed_at'], 'currency': 'USD',
            'unit': 'Pair' if all(t['unit'].lower() == 'pairs' for t in tiers) else 'Piece',
            'tiers': [[t['start_quantity'], t['end_quantity'], t['price']] for t in tiers],
            'scope': '供方公开数量报价；样品价已排除；不代表订单采购成本或完整履约费用',
            'model': o['supplier_model'], 'evidence': rel(args.evidence / '来源' / o['source_id'] / 'observation.json')}
    for o in load(args.evidence / 'Alibaba供方现价.json'):
        quotes[o['source_id']] = {**o, 'scope': '原采用供方公开数量报价；非已确认订单采购成本'}
    cost_path = ROOT / '00_总控台/产品中心/数据/.local/生产成本基线.json'
    costs = load(cost_path) if cost_path.exists() else {}
    plans, folders = {}, {}
    for name in ('降价计划.json', '其余供方降价计划.json', 'BQ036同源链接降价计划.json', '原包成本续核/降价计划.json'):
        manifest_path = args.evidence / name
        if not manifest_path.exists():
            continue
        manifest = load(manifest_path)
        execution = ROOT / manifest['execution_directory'] if manifest.get('execution_directory') else args.evidence / '降价执行'
        for p in manifest['products']:
            assert p['id'] not in plans
            plans[p['id']] = p
            folders[p['id']] = execution / p['id']
    rows = []
    at = datetime.now(timezone.utc).isoformat()
    for entry in catalog['products']:
        pid = str(entry['id'])
        listing = listings[pid]
        product = products[listing['product_id']]
        source_id = listing.get('bound_source_id') or product.get('adopted_source_id')
        source = sources.get(source_id, {})
        quote = quotes.get(source_id)
        folder = folders.get(pid, args.evidence / '降价执行' / pid)
        initial = load(args.evidence / '商品' / pid / 'current_get.json')
        actual, observed_at = initial['response']['product'], initial['at']
        assert actual['product_id'] == entry['product_id'], 'Opaque identity mismatch'
        verification = load(folder / 'verification.json') if (folder / 'verification.json').exists() else None
        if verification:
            actual = load(folder / 'after_get.json')['product']
            observed_at = verification['at']
        skus = actual.get('product_sku', {}).get('skus', [])
        tier_sets = []
        for sku in skus:
            tiers = sorted((int(t['start_quantity']), str(t['price'])) for t in sku.get('bulk_discount_prices', []))
            if tiers not in tier_sets:
                tier_sets.append(tiers)
        trade = actual.get('sourcing_trade', {})
        supplement_path = args.evidence / '商品' / pid / 'trade_supplement.json'
        supplement = load(supplement_path) if supplement_path.exists() else None
        issues = []
        if len(tier_sets) != 1 or not tier_sets[0]:
            issues.append('SKU数量价不唯一或缺失')
        else:
            ts = tier_sets[0]
            if not all(q > 0 and Decimal(p) > 0 for q, p in ts):
                issues.append('非正价格/数量')
            if not all(ts[i][0] < ts[i+1][0] and Decimal(ts[i][1]) > Decimal(ts[i+1][1]) for i in range(len(ts)-1)):
                issues.append('数量/价格阶梯异常')
            if trade.get('min_order_quantity') and int(trade['min_order_quantity']) != ts[0][0]:
                issues.append('MOQ与首档不一致')
        if not trade:
            if supplement and supplement['currency'] == 'USD' and supplement['unit'] == 'Pair':
                original_match = len(tier_sets) == 1 and [(int(q), Decimal(v)) for q, v in supplement['tiers']] == [(q, Decimal(v)) for q, v in tier_sets[0]]
                revised_match = verification and verification.get('state') == 'FORMAL_PRICE_PASS_API' and verification.get('schema_prices_match') and verification.get('prices_match') and verification.get('trade_basis') == 'SCHEMA_PAIR_AND_EXACT_ID_PUBLIC_CURRENCY_SUPPLEMENT'
                if not (original_match or revised_match):
                    issues.append('贸易字段未返回；修订价格待当前Schema核验')
            else:
                issues.append('get未返回贸易字段；币种/单位需独立补证')
        elif trade.get('fob_currency') != 'USD' or trade.get('fob_unit_type') != 'Pair':
            issues.append('币种/计价单位待核')
        floor_rows = []
        if quote and quote['unit'] == 'Pair' and len(tier_sets) == 1:
            for q, price in tier_sets[0]:
                cost = next((Decimal(v) for lo, hi, v in quote['tiers'] if (lo is None or q >= lo) and (hi is None or q <= hi)), None)
                if cost is None:
                    floor_rows.append({'quantity': q, 'source_quote': None})
                    continue
                reference = cost / fx_reference if quote['currency'] == 'CNY' else cost
                markup = Decimal('1.5') if q < 50 else Decimal('1.4') if q < 100 else Decimal('1.3')
                floor_rows.append({'quantity': q, 'source_quote': str(cost), 'reference_markup_price_usd': str((reference*markup).quantize(Decimal('.01'), rounding=ROUND_CEILING)),
                    'current_price': price, 'not_net_profit': True})
        # Collected supplier photos are also stored as raw_packages. They do not
        # turn an externally sourced shoe into a factory-manufactured product.
        own = bool(product.get('raw_packages')) and not source_id
        cost_basis = costs.get('families', {}).get(product['id']) if own and pid in costs.get('listing_ids', []) else None
        if cost_basis and len(tier_sets) == 1:
            for q, price in tier_sets[0]:
                cost = Decimal(cost_basis['cost_cny'])
                markup = Decimal('1.5') if q < 50 else Decimal('1.4') if q < 100 else Decimal('1.3')
                floor_rows.append({'quantity': q, 'production_cost_cny': str(cost),
                    'reference_markup_price_usd': str((cost / fx_reference * markup).quantize(Decimal('.01'), rounding=ROUND_CEILING)),
                    'current_price': price, 'spread_before_other_expenses_cny': str(Decimal(price) * fx_reference - cost),
                    'not_net_profit': True})
        confirmed_knit = listing.get('price_adjustment', {}).get('cny_targets') == [50, 48, 45]
        if confirmed_knit:
            assert len(tier_sets) == 1 and [Decimal(v) for q, v in tier_sets[0]] == [Decimal('7.48'), Decimal('7.18'), Decimal('6.73')], 'Owner-confirmed knit baseline differs'
        observed_source_state = observations.get(source_id, {}).get('state')
        if verification:
            state = {'FORMAL_PRICE_PASS_API': '降价已审核通过', 'PRICE_FIELDS_PASS_REVIEW_PENDING': '降价已回读待审核'}.get(verification['state'], '降价差异待处理')
        elif pid in plans:
            state = '下架链接保留拟价' if actual.get('display') == 'N' else '已拟降价未提交'
        elif pid == '1601825074604':
            state = '保护源保持只读；生产成本已核' if cost_basis else '保护源保持只读'
        elif own:
            state = ('已确认针织售价保留；生产成本已核' if confirmed_knit else '生产成本已核；现价无降价项') if cost_basis else '原包成本待核'
        elif observed_source_state == 'SOURCE_PAGE_OFFLINE':
            state = '货源已下架待核'
        elif quote and quote['unit'] != 'Pair':
            state = '供方计价单位待核'
        elif quote:
            state = '现价无基线降价项；同条件竞品待核'
        else:
            state = '货源现价待核'
        rows.append({'id': pid, 'family': product['id'], 'model': listing['model'], 'title': actual.get('subject'),
            'url': actual.get('pc_detail_url') or listing['url'], 'state': state, 'audit': actual.get('status'), 'display': actual.get('display'),
            'at': observed_at, 'tiers': tier_sets, 'trade': trade, 'trade_supplement': supplement,
            'price_field_issues': issues, 'sku_count': len(skus),
            'source_id': source_id, 'source_model': source.get('model'), 'source_url': source.get('url'), 'own_cost_unverified': own and not cost_basis,
            'production_cost_confirmed': bool(cost_basis), 'production_cost_reference': rel(cost_path) if cost_basis else None,
            'verification_reference': rel(folder / 'verification.json') if verification else None,
            'execution_directory': rel(folder),
            'source_observation_state': observed_source_state, 'public_quote': quote, 'source_quote_markup_reference': floor_rows,
            'plan': plans.get(pid), 'verification': verification,
            'same_condition_competitor_verified': False, 'net_profit_verified': False})
    assert len(rows) == catalog['total_item'] and len({x['id'] for x in rows}) == len(rows)
    summary = {'at': at, 'catalog_ids': len(rows), 'families': len({x['family'] for x in rows}),
        'source_ids_read': len(observations),
        'source_states': dict(Counter(('PUBLIC_QUOTE_OBSERVED_PAIR' if quotes[sid]['unit'] == 'Pair' else 'PUBLIC_QUOTE_UNIT_UNRESOLVED')
            if sid in quotes else x['state'] for sid, x in observations.items())),
        'public_quotes': len(quotes), 'per_pair_public_quotes': sum(x['unit'] == 'Pair' for x in quotes.values()),
        'quote_covered_links': sum(x['public_quote'] is not None for x in rows),
        'production_cost_confirmed_links': sum(x['production_cost_confirmed'] for x in rows),
        'states': dict(Counter(x['state'] for x in rows)), 'price_field_issue_ids': [x['id'] for x in rows if x['price_field_issues']],
        'scope': '全目录价格字段与货源报价基线复核；不代表全店同条件竞品比价或净利润均已验证。',
        'fx': {'usd_cny': str(fx_reference), 'published_at': fx_check['published_at'],
            'source': fx_check['source'], 'evidence': rel(args.evidence / '汇率复算.json')}}
    output = ROOT / '02_Alibaba运营/01_店铺与全店诊断'
    save(output / '价格复核.json', {'summary': summary, 'products': rows})
    save(args.evidence / '当前价格复核汇总.json', summary)
    table = []
    esc = lambda v: html.escape(str(v or ''))
    for p in rows:
        text = json.dumps(p, ensure_ascii=False).lower()
        shown_tiers = ' / '.join(f'{q}双：${v}' for q, v in p['tiers'][0]) if len(p['tiers']) == 1 else '待核'
        prior = ''
        f = ROOT / p['execution_directory'] / 'plan.json'
        if f.exists():
            prior = '原价 ' + ' / '.join(f'{q}双：${v}' for q, v in load(f)['old_tiers'])
        source_info = '原包实际生产成本待核' if p['own_cost_unverified'] else '暂无已核现价'
        if p['production_cost_confirmed']:
            source_info = '负责人已确认生产成本基线；适用履约费用另核'
        if p['public_quote']:
            q = p['public_quote']
            source_info = f"{q['currency']} {q['tiers'][0][2]}起/{q['unit']}；" + str(q['at'])[:10]
        table.append(f'<tr data-search="{esc(text)}" data-state="{esc(p["state"])}"><td><a href="{esc(p["url"])}">{esc(p["model"])}</a><small>{p["id"]}</small></td><td>{esc(p["state"])}<small>{esc(p["audit"])} / display {esc(p["display"])}</small></td><td>{esc(shown_tiers)}<small>{esc(prior)}</small></td><td><a href="{esc(p["source_url"])}">{esc(p["source_model"] or "原包")}</a><small>{esc(source_info)}</small></td><td>{esc("；".join(p["price_field_issues"]) or "数量、价格梯度一致")}</td></tr>')
    options = ''.join(f'<option>{esc(s)}</option>' for s in summary['states'])
    content = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>全店价格复核</title><style>body{{font:15px/1.6 system-ui;margin:30px;color:#213047;background:#f5f7fa}}main{{max-width:1450px;margin:auto}}table{{width:100%;border-collapse:collapse;background:white}}td,th{{padding:13px;text-align:left;border-bottom:1px solid #e0e7ef}}small{{display:block;color:#6a7686}}input,select{{padding:10px;margin:8px 10px 20px 0;min-width:240px}}a{{color:#1b5792}}.note{{background:#eaf0f8;padding:18px;border-radius:10px}}th{{position:sticky;top:0;background:#e2eaf3}}</style><main><h1>全店价格复核</h1><p>当前目录 {len(rows)} 条 / {summary['families']} 个款式家族 · 更新 {at[:19]} UTC</p><p class="note">核对全部商品价格字段，并按适用货源报价与既有加价基线识别降价项。供方公开标价不是已成交采购成本，加价也不是净利润。审核中价格与正式通过价格分别显示；已确认生产成本只适用于对应原包款；未知报价、适用履约费用、包装/贸易条件及同款竞品仍分别待核，不能理解为全店已实现最低价。</p><input id="q" placeholder="搜索货号、商品ID、供方或状态"><select id="s"><option value="">全部状态</option>{options}</select><span id="n"></span><table><thead><tr><th>商品</th><th>本次状态</th><th>API返回数量价</th><th>货源现价依据</th><th>字段检查</th></tr></thead><tbody>{''.join(table)}</tbody></table></main><script>let q=document.querySelector('#q'),s=document.querySelector('#s'),rs=[...document.querySelectorAll('tbody tr')];function filter(){{let n=0;for(let r of rs){{let yes=r.dataset.search.includes(q.value.toLowerCase())&&(!s.value||r.dataset.state===s.value);r.hidden=!yes;if(yes)n++;}}document.querySelector('#n').textContent=n+'条';}}q.oninput=filter;s.onchange=filter;filter();</script></html>'''
    (output / '价格复核.html').write_text(content, encoding='utf-8')
    if args.sync_sources:
        for sid, o in observations.items():
            source = sources[sid]
            source['price_review'] = {'at': o['observed_at'], 'state': o['state'],
                'evidence': rel(args.evidence / '来源' / sid / 'observation.json'), 'order_cost_confirmed': False}
            if sid in quotes:
                q = quotes[sid]
                source['latest_public_quote'] = q
                source['price_review']['state'] = 'PUBLIC_QUOTE_OBSERVED_PAIR' if q['unit'] == 'Pair' else 'PUBLIC_QUOTE_UNIT_UNRESOLVED'
                source['price_review'].update(at=q['at'], evidence=q['evidence'])
                if q['unit'] == 'Pair':
                    source.update(price=q['tiers'][0][2], currency=q['currency'], unit='双', observed_at=str(q['at'])[:10],
                        price_basis='PUBLIC_SUPPLIER_QUOTE_NOT_CONFIRMED_ORDER_COST')
                    source['price_terms'] = '供方公开单价/数量档见latest_public_quote；不是已确认订单采购成本。适用包装、检验、服务、运税等费用逐单核，不从样品费反推。'
        for p in rows:
            if p['production_cost_confirmed']:
                products[p['family']]['production_cost_reference'] = {'file': p['production_cost_reference'],
                    'family_key': p['family'], 'confirmed_on': '2026-10-21', 'scope': '负责人确认的生产成本基线；内部文件，不包含完整订单履约费用'}
            if not p['verification']:
                continue
            products[p['family']].setdefault('local_assets', {}).setdefault('current_prices_by_id', {})[p['id']] = p['verification_reference']
            if p['source_id'] in sources:
                sources[p['source_id']].setdefault('current_price_by_listing', {})[p['id']] = {
                    'at': p['at'], 'state': p['verification']['state'], 'tiers': p['tiers'],
                    'verification': p['verification_reference']}
        data['updated_on'] = at[:10]
        registry.write_registry(data)
    print(json.dumps(summary, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
