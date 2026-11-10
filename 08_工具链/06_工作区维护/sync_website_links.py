"""Audit the website against product identities and cautiously project selected links.

The product centre, supplier store and Alibaba listing store remain authoritative.
This tool never writes any of them, never calls Alibaba and never publishes a site.
It consumes a dated complete official list snapshot. A plan requires explicit IDs;
apply rechecks all input fingerprints and target identity/status before writing only
the website's public link projection. Product text and media require separate review.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SITE = Path('03_独立站/03_网站源码')
PRODUCTS = Path('00_总控台/产品中心/数据/产品.json')
SOURCES = Path('00_总控台/产品中心/数据/供应来源.json')
ASSETS = Path('00_总控台/产品中心/数据/素材索引.json')
LISTINGS = Path('02_Alibaba运营/05_扩品工程/数据/国际站商品.json')
OVERRIDES = SITE / 'app/data/product-link-overrides.json'
TOOL = Path('08_工具链/06_工作区维护/sync_website_links.py')
SITE_INPUTS = [
    SITE / 'app/data/products.ts', SITE / 'app/data/catalog-extension.ts',
    SITE / 'app/data/verified-products.ts', SITE / 'app/data/reviewed-catalog.json',
    SITE / 'app/data/catalog-images.json', SITE / 'app/data/product-colour-media.json',
    OVERRIDES,
]
BLOCKED_DISPOSITIONS = {'PLATFORM_IP_REJECTED_NO_RESUBMIT', 'OWNER_EXCLUDED_NOT_PUBLISHED'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def checked_snapshot(snapshot):
    rows = snapshot.get('products')
    if not snapshot.get('complete') or not isinstance(rows, list):
        raise ValueError('A complete official product.list snapshot is required')
    if snapshot.get('host') != 'open-api.alibaba.com' or snapshot.get('method') != 'alibaba.icbu.product.list' or not snapshot.get('observed_at_utc'):
        raise ValueError('Snapshot method or observation time is missing')
    ids = [str(row['id']) for row in rows]
    if len(ids) != len(set(ids)) or snapshot.get('total_item') != len(ids) or snapshot.get('saved_rows') != len(ids):
        raise ValueError('Snapshot count or unique IDs do not agree')
    datetime.fromisoformat(snapshot['observed_at_utc'].replace('Z', '+00:00'))
    return {str(row['id']): row for row in rows}


def identity_index(products):
    index = defaultdict(set)
    for product in products:
        for code in [product['id'], *product.get('aliases', []), product.get('current_model')]:
            if code:
                index[code].add(product['id'])
    return index


def website_rows(root, node):
    js = "const {products}=await import('./app/data/products.ts');const {productNameZh}=await import('./app/data/products-zh.ts');const {productTitle}=await import('./app/data/europe-products.ts'); console.log(JSON.stringify(products.map(p=>({code:p.code,name:p.name,alibabaProductId:p.alibabaProductId||null,colors:p.colors,images:p.images,zhName:productNameZh(p),localNames:Object.fromEntries(['de','fr','es'].map(l=>[l,productTitle(p,l)]))}))))"
    result = subprocess.run([node, '--experimental-strip-types', '--input-type=module', '-e', js],
                            cwd=root / SITE, capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        raise RuntimeError('Cannot read the website catalogue with the selected Node runtime: ' + result.stderr[-1200:])
    rows = json.loads(result.stdout)
    if len({row['code'] for row in rows}) != len(rows):
        raise ValueError('Duplicate website product codes')
    return rows


def load_inputs(root, snapshot_path, node):
    root = Path(root).resolve()
    snapshot_path = Path(snapshot_path).resolve()
    try:
        relative_snapshot = snapshot_path.relative_to(root)
    except ValueError as exc:
        raise ValueError('Snapshot must be inside the workspace') from exc
    paths = [PRODUCTS, SOURCES, ASSETS, LISTINGS, TOOL, *SITE_INPUTS, relative_snapshot]
    before = {str(path): digest((root / path).read_bytes()) for path in paths}
    product_data = read_json(root / PRODUCTS)
    source_data = read_json(root / SOURCES)
    asset_data = read_json(root / ASSETS)
    listing_data = read_json(root / LISTINGS)
    snapshot = read_json(snapshot_path)
    official = checked_snapshot(snapshot)
    site = website_rows(root, node)
    after = {str(path): digest((root / path).read_bytes()) for path in paths}
    if before != after:
        raise RuntimeError('An input changed during the read; retry with a consistent snapshot')
    products = {p['id']: p for p in product_data['products']}
    listings = {str(l['id']): l for l in listing_data['listings']}
    sources = {s['id']: s for s in source_data['sources']}
    if len(products) != len(product_data['products']) or len(listings) != len(listing_data['listings']):
        raise ValueError('Duplicate product or listing IDs in the source records')
    return {'root': root, 'snapshot_path': relative_snapshot, 'fingerprints': before,
            'products': products, 'sources': sources, 'assets': asset_data['files'], 'listings': listings,
            'index': identity_index(products.values()), 'snapshot': snapshot,
            'official': official, 'website': {p['code']: p for p in site}}


def source_evidence(product, sources, root):
    source_id = product.get('adopted_source_id')
    source = sources.get(source_id) if source_id else None
    raw = [path for path in product.get('raw_packages', []) if (root / path).exists()]
    return bool(source and source.get('url')), bool(raw)


def confirmed_factory_evidence(product, root):
    """Recognise an explicit owner-confirmed factory identity, not just a missing source."""
    supply = product.get('supply_mode') or {}
    if (product.get('source_state') != 'OWNER_CONFIRMED'
            or supply.get('current') != 'OWN_FACTORY'
            or not str(supply.get('state', '')).startswith('OWNER_CONFIRMED_')
            or not supply.get('at')):
        return False
    try:
        datetime.fromisoformat(str(supply['at']).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return False
    for evidence in supply.get('evidence') or []:
        path = (root / evidence).resolve()
        if path.is_relative_to(root.resolve()) and path.is_file():
            return True
    return False


def resolve_site_product(inputs, code):
    ids = inputs['index'].get(code, set())
    if len(ids) != 1:
        raise ValueError(f'{code}: product identity is missing or ambiguous')
    return inputs['products'][next(iter(ids))]


def newer_field_problem(listing, official, observed_at):
    observed = datetime.fromisoformat(observed_at.replace('Z', '+00:00'))
    for key in ('current_platform_fields', 'catalog_fields'):
        fields = listing.get(key) or {}
        if not fields.get('at'):
            continue
        if datetime.fromisoformat(fields['at'].replace('Z', '+00:00')) > observed:
            if fields.get('status') != 'approved' or fields.get('display') != 'Y':
                return 'newer local formal readback changed status or display'
            if fields.get('model') and official.get('red_model') and fields['model'] != official['red_model']:
                return 'newer local formal readback changed the model'
    return None


def validate_target(inputs, code, listing_id):
    if code not in inputs['website']:
        raise ValueError(f'{code}: not in the website catalogue')
    product = resolve_site_product(inputs, code)
    listing = inputs['listings'].get(str(listing_id))
    if not listing or listing.get('product_id') != product['id']:
        raise ValueError(f'{code}: listing does not belong to this explicit product identity')
    disposition = (product.get('publication_disposition') or {}).get('state')
    if disposition in BLOCKED_DISPOSITIONS:
        raise ValueError(f'{code}: product disposition prevents publication')
    adopted = product.get('adopted_source_id')
    bound = listing.get('bound_source_id')
    if adopted and bound and adopted != bound:
        raise ValueError(f'{code}: listing is bound to a different adopted source')
    if not any(source_evidence(product, inputs['sources'], inputs['root'])) and not confirmed_factory_evidence(product, inputs['root']):
        raise ValueError(f'{code}: no recorded adopted source URL or accessible raw package or owner-confirmed factory evidence')
    official = inputs['official'].get(str(listing_id))
    if not official or official.get('display') != 'Y' or official.get('status') != 'approved':
        raise ValueError(f'{code}: selected listing was not approved and displayed in the snapshot')
    problem = newer_field_problem(listing, official, inputs['snapshot']['observed_at_utc'])
    if problem:
        raise ValueError(f'{code}: {problem}')
    return {'code': code, 'product_id': product['id'], 'from': inputs['website'][code]['alibabaProductId'],
            'to': str(listing_id), 'snapshot_status': 'approved/Y'}


def plan(inputs, choices):
    if not choices or len(set(code for code, _ in choices)) != len(choices):
        raise ValueError('Provide one distinct explicit listing choice for each website code')
    changes = [validate_target(inputs, code, listing_id) for code, listing_id in choices]
    return {'schema_version': 1, 'snapshot_path': inputs['snapshot_path'].as_posix(),
            'snapshot_observed_at_utc': inputs['snapshot']['observed_at_utc'],
            'fingerprints': inputs['fingerprints'], 'changes': changes}


def apply_plan(inputs, proposed):
    choices = [(x['code'], x['to']) for x in proposed['changes']]
    if plan(inputs, choices) != proposed:
        raise RuntimeError('Plan or inputs changed; create and review a fresh plan')
    target = inputs['root'] / OVERRIDES
    current = read_json(target)
    if not isinstance(current, dict):
        raise ValueError('Website link projection must be an object')
    for change in proposed['changes']:
        current[change['code']] = change['to']
    data = (json.dumps(dict(sorted(current.items())), ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    # Recheck immediately before the atomic file replacement. No other file is written.
    for path, expected in inputs['fingerprints'].items():
        if digest((inputs['root'] / path).read_bytes()) != expected:
            raise RuntimeError(f'Input changed before write: {path}')
    if target.read_bytes() == data:
        return False
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
    try:
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def audit(inputs):
    mapped_site = {}
    issues = []
    for code, row in inputs['website'].items():
        ids = inputs['index'].get(code, set())
        if len(ids) != 1:
            issues.append({'code': code, 'issue': 'IDENTITY_MISSING_OR_AMBIGUOUS'})
            continue
        product_id = next(iter(ids)); mapped_site[product_id] = code
        product = inputs['products'][product_id]
        disposition = (product.get('publication_disposition') or {}).get('state')
        if disposition in BLOCKED_DISPOSITIONS:
            issues.append({'code': code, 'issue': 'BLOCKED_PRODUCT_DISPOSITION', 'disposition': disposition})
        linked = row['alibabaProductId']
        if not linked:
            issues.append({'code': code, 'issue': 'NO_WEBSITE_ALIBABA_LINK'})
        else:
            listing = inputs['listings'].get(linked)
            official = inputs['official'].get(linked)
            if not listing:
                issues.append({'code': code, 'id': linked, 'issue': 'LINK_NOT_IN_LOCAL_REGISTRY'})
            elif listing.get('product_id') != product_id:
                issues.append({'code': code, 'id': linked, 'issue': 'LINK_POINTS_TO_ANOTHER_PRODUCT', 'actual_product_id': listing.get('product_id')})
            elif product.get('adopted_source_id') and listing.get('bound_source_id') and product['adopted_source_id'] != listing['bound_source_id']:
                issues.append({'code': code, 'id': linked, 'issue': 'LINK_BOUND_TO_DIFFERENT_SOURCE'})
            elif not official:
                issues.append({'code': code, 'id': linked, 'issue': 'LINK_NOT_IN_SNAPSHOT'})
            elif official.get('display') != 'Y' or official.get('status') != 'approved':
                issues.append({'code': code, 'id': linked, 'issue': 'LINK_NOT_APPROVED_AND_DISPLAYED_IN_SNAPSHOT'})
            elif newer_field_problem(listing, official, inputs['snapshot']['observed_at_utc']):
                issues.append({'code': code, 'id': linked, 'issue': 'NEWER_FORMAL_READBACK_DIFFERS'})
        adopted, raw = source_evidence(product, inputs['sources'], inputs['root'])
        if not (adopted or raw or confirmed_factory_evidence(product, inputs['root'])):
            issues.append({'code': code, 'issue': 'NO_ADOPTED_SOURCE_URL_OR_ACCESSIBLE_RAW_PACKAGE'})
        if len(row['images']) < 4 or not row['colors']:
            issues.append({'code': code, 'issue': 'WEBSITE_MEDIA_OR_COLOUR_GAP'})
        if row.get('zhName') == row.get('name'):
            issues.append({'code': code, 'issue': 'CHINESE_NAME_FALLBACK'})
        for locale, name in row.get('localNames', {}).items():
            if name == code:
                issues.append({'code': code, 'issue': 'LOCALIZED_NAME_FALLBACK', 'locale': locale})
    approved = [r for r in inputs['official'].values() if r.get('display') == 'Y' and r.get('status') == 'approved']
    groups = defaultdict(list); unmapped = []
    for row in approved:
        listing = inputs['listings'].get(str(row['id']))
        if listing and listing.get('product_id') in inputs['products']:
            groups[listing['product_id']].append(str(row['id']))
        else:
            unmapped.append(str(row['id']))
    asset_by_product = defaultdict(set)
    for item in inputs.get('assets', []):
        for code in item.get('products', []):
            if item.get('file'):
                asset_by_product[code].add(item['file'])
    missing = []
    for pid in sorted(set(groups) - set(mapped_site)):
        product = inputs['products'][pid]
        adopted, raw = source_evidence(product, inputs['sources'], inputs['root'])
        reference = inputs['sources'].get(product.get('reference_source_id')) or {}
        asset_paths = set()
        for code in [product['id'], *product.get('aliases', []), product.get('current_model')]:
            asset_paths.update(asset_by_product.get(code, set()))
        missing.append({'product_id': pid, 'current_model': product.get('current_model') or pid,
                        'listing_ids': groups[pid], 'source_state': product.get('source_state'),
                        'adopted_source_url_recorded': adopted, 'accessible_raw_package': raw,
                        'owner_factory_confirmed': confirmed_factory_evidence(product, inputs['root']),
                        'reference_source_url_recorded': bool(reference.get('url')),
                        'indexed_asset_files': len(asset_paths),
                        'accessible_indexed_asset_files': sum((inputs['root'] / path).is_file() for path in asset_paths),
                        'website_locales_missing': ['en', 'zh', 'de', 'fr', 'es'],
                        'disposition': (product.get('publication_disposition') or {}).get('state')})
    return {'snapshot_observed_at_utc': inputs['snapshot']['observed_at_utc'],
            'snapshot_sha256': inputs['fingerprints'][str(inputs['snapshot_path'])],
            'scope': 'Dated product.list, local identities, indexed asset paths and current website projection; not live availability, source adoption, usable-media proof or a field-by-field product verification.',
            'counts': {'snapshot_listings': len(inputs['official']), 'approved_displayed_listings': len(approved),
                       'approved_not_displayed_listings': sum(r.get('status') == 'approved' and r.get('display') == 'N' for r in inputs['official'].values()),
                       'other_status_listings': sum(not (r.get('status') == 'approved' and r.get('display') in ('Y', 'N')) for r in inputs['official'].values()),
                       'local_listing_ids_not_seen_in_snapshot': len(set(inputs['listings']) - set(inputs['official'])),
                       'unmapped_approved_listings': len(unmapped), 'approved_identities': len(groups),
                       'website_products': len(inputs['website']), 'website_matched_identities': len(mapped_site),
                       'approved_identities_on_website': len(set(groups) & set(mapped_site)),
                       'approved_identities_not_on_website': len(missing)},
            'website_issues': issues, 'issue_counts': dict(Counter(x['issue'] for x in issues)),
            'unmapped_approved_listing_ids': unmapped,
            'local_listing_ids_not_seen_in_snapshot': sorted(set(inputs['listings']) - set(inputs['official'])),
            'missing_website_identities': missing}


def default_node():
    bundled = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
    return str(bundled) if bundled.is_file() else shutil.which('node') or 'node'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, help='Complete dated Alibaba product.list snapshot inside workspace')
    parser.add_argument('--node', default=default_node(), help='Node supporting TypeScript stripping')
    sub = parser.add_subparsers(dest='action', required=True)
    audit_cmd = sub.add_parser('audit'); audit_cmd.add_argument('--output', required=True)
    plan_cmd = sub.add_parser('plan'); plan_cmd.add_argument('--link', action='append', required=True, help='Explicit CODE=LISTING_ID'); plan_cmd.add_argument('--output', required=True)
    apply_cmd = sub.add_parser('apply'); apply_cmd.add_argument('--plan', required=True)
    args = parser.parse_args()
    inputs = load_inputs(ROOT, args.snapshot, args.node)
    if args.action == 'audit':
        report = audit(inputs); Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'counts': report['counts'], 'issue_counts': report['issue_counts'], 'snapshot_observed_at_utc': report['snapshot_observed_at_utc']}, ensure_ascii=False))
    elif args.action == 'plan':
        choices = []
        for value in args.link:
            if value.count('=') != 1:
                raise ValueError('Each --link must be CODE=LISTING_ID')
            choices.append(tuple(value.split('=', 1)))
        proposal = plan(inputs, choices); Path(args.output).write_text(json.dumps(proposal, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'snapshot_observed_at_utc': proposal['snapshot_observed_at_utc'], 'changes': proposal['changes']}, ensure_ascii=False))
    else:
        proposed = read_json(Path(args.plan)); changed = apply_plan(inputs, proposed)
        print(json.dumps({'projection_updated': changed, 'changes': proposed['changes']}, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        sys.exit(1)
