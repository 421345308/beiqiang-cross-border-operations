"""Index existing assets and a complete read-only catalog into the sole registry.

No product writes, source inference, directory moves or deletion. Classification
from observed titles is a review candidate, never a verified product claim.
"""
from pathlib import Path
import argparse
import json
import re

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / '02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json'
SNAPSHOT = ROOT / '02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/catalog.json'
ASSETS = ROOT / '01_产品资产/02_可发布素材/00_最终上传'


def relative(path):
    return path.relative_to(ROOT).as_posix()


def candidate_category(title):
    title = title.lower()
    for label, pattern in [
        ('靴类', r'\bboots?\b'),
        ('凉鞋/拖鞋', r'\b(sandals?|slippers?|clogs?)\b'),
        ('套脚/袜套需求', r'\bslip[ -]?on\b|\bsock\b|\beasy on\b'),
        ('系带步行/休闲需求', r'\blace[ -]?up\b'),
        ('步行/休闲需求', r'\b(walking|casual|sneakers?)\b'),
    ]:
        if re.search(pattern, title):
            return label
    return '待分类'


def reconcile(data, snapshot):
    rows = snapshot['products']
    live = {str(p['id']): p for p in rows}
    if not snapshot.get('complete') or len(live) != len(rows) or len(rows) != snapshot['total_item']:
        raise ValueError('Incomplete or duplicate-ID catalog; do not update registry')
    known = {p['id'] for p in data['listings']}
    unknown = sorted(set(live) - known)
    roots = {}
    for path in sorted(ASSETS.iterdir()):
        if path.is_dir() and re.match(r'^BQ\d{3}_', path.name):
            roots.setdefault(path.name.split('_')[0], []).append(path)
    conflicts = []
    by_product = {}
    for listing in data['listings']:
        row = live.get(listing['id'])
        listing['catalog_presence'] = 'OBSERVED' if row else 'NOT_OBSERVED'
        listing['catalog_evidence'] = relative(SNAPSHOT)
        if row:
            listing['catalog_fields'] = {
                'at': snapshot['observed_at_utc'],
                'model': row.get('red_model', ''),
                'title': row.get('subject', ''),
                'keywords': row.get('keywords', []),
                'main_images': row.get('main_image', {}).get('images', []),
                'category_id': row.get('category_id'),
                'display': row.get('display'),
                'status': row.get('status'),
                'url': row.get('pc_detail_url', ''),
                'scope': 'product.list；不是全字段/公开验收',
            }
            # Preserve formal get audit and its original date separately.
            by_product.setdefault(listing['product_id'], []).append(row)
        listing.setdefault('local_sync', {
            'state': 'UNVERIFIED',
            'current_fields_file': None,
            'next_action': '核当前文件与同ID正式字段；目录对应不等于双改已验收',
        })
    for product in data['products']:
        paths = {p for alias in product['aliases'] for p in roots.get(alias, [])}
        ordered = sorted(paths)
        forms = [p / '00_上架填写表.md' for p in ordered if (p / '00_上架填写表.md').exists()]
        product['local_assets'] = {
            'asset_roots': [relative(p) for p in ordered],
            'current_fields_file': relative(forms[0]) if len(forms) == 1 else None,
            'state': 'SINGLE_ENTRY_PENDING_CONTENT_CHECK' if len(forms) == 1 else 'CONFLICT' if len(forms) > 1 else 'NEEDS_CURRENT_ENTRY',
            'scope': '目录身份索引；文件中历史字段仍需与当前平台核对',
        }
        if len(forms) > 1:
            conflicts.append({'product_id': product['id'], 'paths': [relative(p) for p in forms]})
        observed = by_product.get(product['id'], [])
        categories = sorted({candidate_category(p.get('subject', '')) for p in observed})
        product['classification'] = {
            'local_intent_candidates': categories or ['待分类'],
            'state': 'TITLE_OBSERVATION_PENDING_SKU_REVIEW',
            'evidence': relative(SNAPSHOT),
            'platform_category_ids': sorted({p['category_id'] for p in observed if p.get('category_id') is not None}),
            'store_groups': None,
            'store_group_state': 'NOT_RETURNED_BY_PRODUCT_LIST',
        }
    summary = {
        'observed_at_utc': snapshot['observed_at_utc'], 'evidence': relative(SNAPSHOT),
        'scope': '完整product.list分页；未取全店正式get/公开正文',
        'platform_ids': len(live), 'registered_ids': len(known),
        'platform_without_local_ids': unknown,
        'local_not_observed_ids': sorted(known - set(live)),
        'local_entry_conflicts': conflicts,
        'state': 'IDENTITY_INDEXED_CONTENT_SYNC_PENDING' if not unknown else 'UNMAPPED_PLATFORM_IDS',
    }
    data['catalog_reconciliation'] = summary
    work = next((x for x in data['workstreams'] if x['name'] == '本地与国际站对应及BQ穿脱需求优化'), None)
    if work is None:
        work = {'name': '本地与国际站对应及BQ穿脱需求优化'}
        data['workstreams'].append(work)
    work.update({
        'status': f"本轮{len(live)}个平台ID，{len(unknown)}个未登记；{len(known-set(live))}个历史ID未检出；{len(conflicts)}个本地入口冲突；双改全字段待核",
        'next_action': '先核BQ052双货号；逐款确认套脚/袜套结构、当前字段档案和店内分组；按SOP优化标题及穿脱主图并双改验收，清理经校验无独立用途的副本。',
        'evidence': [relative(SNAPSHOT)],
    })
    data['updated_on'] = '2026-10-10'
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Write derived indices to the sole registry')
    args = parser.parse_args()
    data = json.loads(REGISTRY.read_text(encoding='utf-8-sig'))
    snapshot = json.loads(SNAPSHOT.read_text(encoding='utf-8'))
    summary = reconcile(data, snapshot)
    if args.apply:
        REGISTRY.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
