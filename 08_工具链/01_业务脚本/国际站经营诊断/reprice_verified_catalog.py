"""Apply reviewed, price-only reductions; retain quantities and every other field.

The input is an explicit per-ID manifest, not a rule that reprices a whole store.
Read-only phases may retry transient reads. Writes are reserved once and never
replayed by this controller. Procurement observations are not net-profit proof.
"""
from pathlib import Path
import argparse
import copy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import importlib.util
import json
import sys
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / '08_工具链/01_业务脚本/国际站扩品'))
sys.path.insert(0, str(ROOT / '08_工具链/06_工作区维护'))
import schema_publish_contract as contract
from read_only_catalog import read_only_call
from product_registry import ProductRegistry

FIELDS = ('scPrice', 'ladderPrice', 'productTitle')
PROTECTED = {'1601825074604'}


def now():
    return datetime.now(timezone.utc).isoformat()


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def rel(path):
    return path.resolve().relative_to(ROOT).as_posix()


def stable(product):
    value = copy.deepcopy(product)
    for key in ('gmt_modified', 'status', 'display'):
        value.pop(key, None)
    for key in ('fob_min_price', 'fob_max_price'):
        value.get('sourcing_trade', {}).pop(key, None)
    for sku in value.get('product_sku', {}).get('skus', []):
        sku.pop('bulk_discount_prices', None)
    for key in ('company_image', 'detail_image'):
        images = value.get('struct_detail', {}).get(key, {})
        if isinstance(images, dict) and isinstance(images.get('images'), list):
            images['images'].sort(key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False))
    return value


def schema_tiers(root):
    return sorted((int(row.find("./field[@id='quantity']/value").text),
                   Decimal(row.find("./field[@id='price']/value").text))
                  for row in root.findall("./field[@id='ladderPrice']/complex-value/field/complex-value"))


def wanted_tiers(plan):
    return [(int(q), Decimal(str(price))) for q, price in plan['new_tiers']]


def formal_prices_match(product, expected):
    skus = product.get('product_sku', {}).get('skus', [])
    return bool(skus) and all(sorted((int(t['start_quantity']), Decimal(str(t['price'])))
        for t in sku.get('bulk_discount_prices', [])) == expected for sku in skus)


def validate_reduction(old, new):
    assert len(old) >= 2 and [q for q, _ in old] == [q for q, _ in new], 'Quantity tiers changed'
    assert len({q for q, _ in new}) == len(new)
    assert all(q > 0 and p > 0 and p == p.quantize(Decimal('.01')) for q, p in new)
    assert all(new[i][0] < new[i+1][0] and new[i][1] > new[i+1][1] for i in range(len(new)-1))
    assert all(n <= o for (_, o), (_, n) in zip(old, new)), 'Price increase forbidden'
    assert any(n < o for (_, o), (_, n) in zip(old, new)), 'No reduction'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'submit', 'verify', 'sync'))
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ids', nargs='*')
    args = parser.parse_args()
    manifest = load(args.manifest)
    assert manifest['authorization'] and manifest['purpose'] == 'PRICE_ONLY_REDUCTION'
    plans = manifest['products']
    assert len({p['id'] for p in plans}) == len(plans)
    assert not ({p['id'] for p in plans} & PROTECTED), 'Protected IDs'
    assert all(p['family'] != 'HR030' for p in plans), 'Owner-reported infringement returns'
    if args.ids:
        assert set(args.ids) <= {p['id'] for p in plans}
        plans = [p for p in plans if p['id'] in args.ids]
    if args.mode == 'sync':
        registry = ProductRegistry(ROOT)
        data = load(registry)
        by_id = {x['id']: x for x in data['listings']}
        for plan in plans:
            folder = args.output / plan['id']
            if not (folder / 'verification.json').exists():
                continue
            report = load(folder / 'verification.json')
            if not report['prices_match'] or not report['non_price_formal_preserved']:
                continue
            listing = by_id[plan['id']]
            assert listing['product_id'] == plan['family']
            reference = ROOT / '02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品' / plan['id']
            actual = load(folder / 'after_get.json')
            save(reference / 'formal_get.json', {'requested_product_id': plan['id'],
                'observed_at_utc': report['at'], 'method': 'alibaba.icbu.product.get', 'response': actual})
            if (folder / 'after_render.json').exists():
                save(reference / 'formal_render.json', {'requested_product_id': plan['id'],
                    'observed_at_utc': report['at'], 'response': load(folder / 'after_render.json')})
            listing['price_review'] = {**plan, 'at': report['at'], 'state': report['state'],
                'verification': rel(folder / 'verification.json'), 'public': 'NOT_REQUESTED_API_ACCEPTANCE'}
            listing['formal_fields'] = {'file': rel(reference / 'formal_get.json'), 'at': report['at'],
                'scope': '本次价格正式回读；不代表公开验收'}
            listing.setdefault('local_sync', {}).update(state=report['state'],
                current_fields_file=listing['formal_fields']['file'], at=report['at'])
            listing['observation'] = {'audit': report['status'], 'display': report['display'],
                'at': report['at'], 'scope': '价格API闭环；公开呈现未核'}
            for key in ('catalog_fields', 'current_platform_fields'):
                if key in listing:
                    listing[key].update(status=report['status'], display=report['display'], at=report['at'])
        data['updated_on'] = now()[:10]
        registry.write_registry(data)
        print('SYNCED', sum('price_review' in x for x in data['listings']))
        return

    spec = importlib.util.spec_from_file_location('price_api', ROOT / '.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py')
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    cfg = api.load_config(api.DEFAULT_CONFIG)
    api.http_json = lambda request, timeout=25: api.native_http_json(request, timeout=timeout)

    def read(method, params):
        return read_only_call(api, cfg, method, params)

    def render(pid, category):
        return read('alibaba.icbu.product.schema.render', {'param_product_top_publish_request': {
            'product_id': int(pid), 'cat_id': int(category), 'language': 'en_US'}})

    results = []
    for plan in plans:
        pid = plan['id']
        folder = args.output / pid
        folder.mkdir(parents=True, exist_ok=True)
        try:
            if args.mode == 'prepare':
                assert not (folder / 'write_once.json').exists(), 'Existing write; read back only'
                g = read('alibaba.icbu.product.get', {'product_id': int(pid), 'language': 'ENGLISH'})
                save(folder / 'before_get.json', g)
                p = g['product']
                # product.get returns an opaque product_id, not the numeric catalog id.
                assert ('_' + pid + '.html') in p['pc_detail_url'], 'Returned detail URL identity differs'
                assert p['status'] == 'approved' and p['display'] == 'Y'
                assert p['sourcing_trade']['fob_currency'] == 'USD' and p['sourcing_trade']['fob_unit_type'] == 'Pair'
                r = render(pid, p['category_id'])
                save(folder / 'before_render.json', r)
                root = ET.fromstring(r['data'])
                payload = contract.values_only(root, operation='update', field_ids=FIELDS)
                assert set(e.get('id') for e in payload) == set(FIELDS)
                assert payload.find("./field[@id='scPrice']/value").text == '1'
                assert payload.find("./field[@id='productTitle']/value").text == p['subject']
                old, wanted = schema_tiers(payload), wanted_tiers(plan)
                validate_reduction(old, wanted)
                assert formal_prices_match(p, old), 'Formal and editable price mismatch'
                prices = dict(wanted)
                for row in payload.findall("./field[@id='ladderPrice']/complex-value/field/complex-value"):
                    q = int(row.find("./field[@id='quantity']/value").text)
                    row.find("./field[@id='price']/value").text = format(prices[q], '.2f')
                xml = ET.tostring(payload, encoding='unicode')
                (folder / 'payload.xml').write_text(xml, encoding='utf-8')
                save(folder / 'plan.json', {**plan, 'at': now(), 'category_id': p['category_id'],
                    'old_tiers': [[q, str(v)] for q, v in old], 'fields': list(FIELDS),
                    'video_fields_inspected': [k for k in ('imageVideo', 'detailVideo') if root.find('./field[@id="'+k+'"]') is not None],
                    'payload_sha256': hashlib.sha256(xml.encode()).hexdigest()})
                result = {'id': pid, 'state': 'PREPARED'}
            elif args.mode == 'submit':
                assert not (folder / 'write_once.json').exists(), 'Existing reservation; read back only'
                prepared = load(folder / 'plan.json')
                assert prepared['new_tiers'] == plan['new_tiers'] and prepared['basis'] == plan['basis']
                xml = (folder / 'payload.xml').read_text(encoding='utf-8')
                assert hashlib.sha256(xml.encode()).hexdigest() == prepared['payload_sha256']
                g = read('alibaba.icbu.product.get', {'product_id': int(pid), 'language': 'ENGLISH'})
                save(folder / 'immediate_prewrite_get.json', g)
                before, current = load(folder / 'before_get.json')['product'], g['product']
                assert current['status'] == 'approved' and current['display'] == 'Y'
                assert stable(current) == stable(before) and current['product_sku'] == before['product_sku']
                assert current['sourcing_trade'] == before['sourcing_trade']
                with (folder / 'write_once.json').open('x', encoding='utf-8') as stream:
                    json.dump({'id': pid, 'at': now(), 'state': 'STARTED_UNKNOWN_NO_REPLAY',
                        'sha256': prepared['payload_sha256']}, stream)
                receipt = api.top_call(cfg, 'alibaba.icbu.product.schema.update', {'param_product_top_publish_request': {
                    'product_id': int(pid), 'cat_id': prepared['category_id'], 'language': 'en_US', 'xml': xml}})
                save(folder / 'update_receipt.json', api.redact_tokens(receipt))
                result = {'id': pid, 'at': now(), 'state': 'SUBMITTED_PENDING_READBACK'
                    if receipt.get('biz_success') is True else 'REJECTED_OR_UNKNOWN', 'request_id': receipt.get('request_id')}
                save(folder / 'write_once.json', result)
            else:
                assert (folder / 'write_once.json').exists(), 'Not submitted'
                g = read('alibaba.icbu.product.get', {'product_id': int(pid), 'language': 'ENGLISH'})
                save(folder / 'after_get.json', g)
                p = g['product']
                expected = wanted_tiers(plan)
                result = {'id': pid, 'at': now(), 'state': 'PENDING',
                    'prices_match': formal_prices_match(p, expected),
                    'trade_range_matches': (Decimal(p['sourcing_trade']['fob_min_price']) == min(v for q, v in expected)
                        and Decimal(p['sourcing_trade']['fob_max_price']) == max(v for q, v in expected)),
                    'non_price_formal_preserved': stable(p) == stable(load(folder / 'before_get.json')['product']),
                    'status': p['status'], 'display': p['display'], 'public': 'NOT_REQUESTED_API_ACCEPTANCE'}
                if p['status'] == 'approved':
                    r = render(pid, p['category_id'])
                    save(folder / 'after_render.json', r)
                    old = contract.field_snapshot(ET.fromstring(load(folder / 'before_render.json')['data']))
                    new = contract.field_snapshot(ET.fromstring(r['data']))
                    result['schema_preservation_failures'] = [k for k, v in old.items()
                        if k != 'ladderPrice' and not contract.created_field_equivalent(k, v, new.get(k))]
                    result['schema_prices_match'] = schema_tiers(ET.fromstring(r['data'])) == expected
                    score = read('alibaba.icbu.product.score.get', {'product_id': int(pid)})
                    save(folder / 'score.json', score)
                    result['actual_score'] = score.get('result', {}).get('final_score')
                    if (result['prices_match'] and result['trade_range_matches'] and result['non_price_formal_preserved']
                            and result['schema_prices_match'] and not result['schema_preservation_failures']
                            and p['display'] == 'Y'):
                        result['state'] = 'FORMAL_PRICE_PASS_API'
                elif p['status'] in ('modified', 'new') and result['prices_match'] and result['trade_range_matches'] and result['non_price_formal_preserved']:
                    result['state'] = 'PRICE_FIELDS_PASS_REVIEW_PENDING'
                elif p['status'] == 'tbd':
                    result['state'] = 'AUDIT_REJECTED_REQUIRES_DIAGNOSIS'
                save(folder / 'verification.json', result)
        except Exception as exc:
            result = {'id': pid, 'state': 'DIAGNOSE_NO_REPLAY', 'error_type': type(exc).__name__}
            if isinstance(exc, AssertionError):
                result['detail'] = str(exc)
            save(folder / (args.mode + '_error.json'), result)
        results.append(result)
        print(json.dumps(result, ensure_ascii=True), flush=True)
    save(args.output / (args.manifest.stem + '_' + args.mode + '_results.json'), {'at': now(), 'results': results})


if __name__ == '__main__':
    main()
