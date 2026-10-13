"""Register existing local BQ dossiers and exact raw-package source references.

Does not assert publication, stock, OEM capability or material from folder names.
"""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / '02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json'
ASSETS = ROOT / '01_产品资产/02_可发布素材/00_最终上传'
RAW = ROOT / '01_产品资产/01_原始数据包'


def main():
    data = json.loads(REGISTRY.read_text(encoding='utf-8-sig'))
    products = {p['id']: p for p in data['products']}
    sources = {(s['url'], s['model']): s for s in data['sources']}
    raw_records = {}
    for file in RAW.glob('**/source.json'):
        record = json.loads(file.read_text(encoding='utf-8-sig'))
        model = str(record.get('artno', ''))
        if model:
            raw_records.setdefault(model, []).append((file, record))
    created = []
    for folder in sorted(ASSETS.iterdir()):
        if not folder.is_dir() or not re.fullmatch(r'BQ\d{3}_.+', folder.name):
            continue
        pid, model = folder.name.split('_', 1)
        # 116 was an old BQ052 preparation collision; current BQ052 is 9212.
        # Its independently existing current family is BQ062 / 116.
        if folder.name == 'BQ052_116':
            continue
        form = folder / '00_上架填写表.md'
        if not form.exists():
            continue
        if pid not in products:
            product = {'id': pid, 'aliases': [pid], 'source_state': 'RAW_PACKAGE', 'adopted_source_id': None, 'candidate_source_ids': [], 'raw_packages': [], 'evidence': [form.relative_to(ROOT).as_posix()], 'notes': ['本地既有待上架资料补登；不是已发布或已核当前供给。'], 'next_action': '核本款事实、货源入口和独立鞋型；平台未关联ID，不自动创建。'}
            data['products'].append(product)
            products[pid] = product
            created.append(pid)
        product = products[pid]
        records = raw_records.get(model, [])
        # Exact model alone can conflict across suppliers; only bind a unique source.
        urls = {r.get('detail_url') for _, r in records if r.get('detail_url')}
        if len(urls) == 1:
            file, record = records[0]
            raw_path = file.parent.relative_to(ROOT).as_posix()
            if raw_path not in product['raw_packages']:
                product['raw_packages'].append(raw_path)
            key = (record['detail_url'], model)
            source = sources.get(key)
            if not source:
                source = {'id': 'src-' + hashlib.sha256('|'.join(key).encode()).hexdigest()[:12], 'url': key[0], 'shop_url': 'https://' + __import__('urllib.parse',fromlist=['urlsplit']).urlsplit(key[0]).netloc, 'supplier': '贝强工厂店（原source.json标题标注；自产仍需逐款原件）', 'model': model, 'price': record.get('price_cny', ''), 'currency': 'CNY', 'unit': '双', 'price_terms': '保存的来源页参考标价，非当前核价或成交价', 'observed_at': '2026-08-14', 'evidence': [file.relative_to(ROOT).as_posix()]}
                data['sources'].append(source)
                sources[key] = source
            if not product.get('reference_source_id') and not product.get('adopted_source_id'):
                product['reference_source_id'] = source['id']
                product['source_state'] = 'MAPPED'
        product['dossier_path'] = f'02_Alibaba运营/02_单品优化记录/商品档案/{pid}/README.md'
    for product in data['products']:
        product.setdefault('dossier_path', f"02_Alibaba运营/02_单品优化记录/商品档案/{product['id']}/README.md")
    for source in data['sources']:
        if 'detail.1688.com' in source.get('shop_url', ''):
            source['shop_url'] = ''
            source['limits'] = (source.get('limits', '') + ' 采购商品直链已保存；detail.1688.com不是供方店铺直链，店铺URL待核。').strip()
    data['updated_on'] = '2026-10-10'
    REGISTRY.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'new_local_product_records': created, 'products': len(data['products']), 'sources': len(data['sources'])}, ensure_ascii=False))


if __name__ == '__main__':
    main()
