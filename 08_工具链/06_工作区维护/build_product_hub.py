"""Build cross-channel product navigation from domain stores, without publishing."""
import argparse
import html
import json
import os
from pathlib import Path

from product_registry import PRODUCTS, SUPPLY, ALIBABA, atomic_write

ROOT = Path(__file__).resolve().parents[2]
HUB = Path('00_总控台/产品中心')
DOUYIN = Path('09_国内电商/抖店/数据/渠道产品对应.json')


def load(root, path):
    return json.loads((root / path).read_text(encoding='utf-8-sig'))


def rows_and_errors(root=ROOT):
    product_data, supply, alibaba, douyin = (load(root, p) for p in (PRODUCTS, SUPPLY, ALIBABA, DOUYIN))
    products = {p['id']: p for p in product_data['products']}
    sources = {s['id']: s for s in supply['sources']}
    rows, errors = [], []
    store_names = {s['key']: s['name'] for s in douyin['stores']}
    by_product = {key: [] for key in products}
    seen = set()
    for link in douyin['listings']:
        key = (link['store_key'], link['source_model'])
        if key in seen:
            errors.append(f'duplicate store/model: {key}')
        seen.add(key)
        if link['store_key'] not in store_names:
            errors.append(f'unknown store: {key}')
        if link['product_id'] and link['product_id'] not in products:
            errors.append(f'unknown product: {key}')
        if not (root/link['content_file']).is_file():
            errors.append(f'missing content file: {key}')
        observation = link.get('observation', {})
        item = {**link, 'store': store_names.get(link['store_key'], ''), 'saved_state': observation.get('state', '未核'), 'evidence_date': observation.get('record_updated_on') or '见单款证据'}
        if link['product_id'] in by_product:
            by_product[link['product_id']].append(item)
        else:
            pending = next((r for r in rows if r['id'] == '待绑定 / ' + link['source_model']), None)
            if pending:
                pending['douyin'].append(item)
            else:
                rows.append({'id': '待绑定 / ' + link['source_model'], 'model': link['source_model'], 'supplier': '贝强工厂店', 'supplier_url': 'https://bqgcd.sooxie.com/', 'source_model': link['source_model'], 'source_url': '', 'mode': '产品身份待绑定', 'source_state': link['identity_state'], 'alibaba': [], 'douyin': [item], 'notes': '渠道已有发布档案；共用产品身份待核，未据相似货号合并。'})
    for pid, product in products.items():
        source = sources.get(product.get('adopted_source_id') or product.get('reference_source_id'), {})
        rows.append({'id': pid, 'model': product.get('current_model') or product['aliases'][0], 'aliases': product['aliases'], 'supplier': source.get('supplier', '来源待核'), 'supplier_url': source.get('shop_url', ''), 'source_model': source.get('model', ''), 'source_url': source.get('url', ''), 'mode': {'EXTERNAL_FACTORY': '外部供应商扩品', 'OWN_FACTORY': '自产'}.get(product.get('supply_mode', {}).get('current'), '供货类型待核'), 'source_state': product['source_state'], 'alibaba': [x for x in alibaba['listings'] if x['product_id'] == pid], 'douyin': by_product[pid], 'notes': ' / '.join(product.get('notes', []))})
    return rows, errors


def build(root=ROOT):
    rows, errors = rows_and_errors(root)
    if errors:
        raise ValueError('\n'.join(errors))
    esc = html.escape
    def file_link(path):
        return Path(os.path.relpath(root/path, root/HUB)).as_posix()
    external = ['# 外部供应商扩品', '', '产品身份与供货关系统一由产品中心维护。供应商是产品属性；旧HR编码和路崎批次不再作为并列项目。下表按已保存的供货类型筛选，不把缺证款推断为外采，也不把链接存在当作今天可供。', '', '| 贝强当前型号 | 供应商 | 原货号 / 采购入口 | 来源状态 | 国际站历史及正式ID数 | 抖店档案归属 |', '| --- | --- | --- | --- | --- | --- |']
    for row in rows:
        row['source_state'] = {'ADOPTED':'有采用记录，按证据复核', 'MAPPED':'已关联原款，逐链接绑定另验', 'CANDIDATE':'只有候选，尚未替换', 'MISSING':'缺来源证据', 'CONFLICT':'来源冲突待核', 'RAW_PACKAGE':'有原始包关联', 'PENDING_CANONICAL_BINDING':'共用产品身份待核'}.get(row['source_state'], row['source_state'])
        if row['mode'] != '外部供应商扩品':
            continue
        external.append(f"| {row['model']} | {row['supplier']} | [{row['source_model'] or '待核'}]({row['source_url']}) | {row['source_state']} | {len(row['alibaba'])} | {'、'.join(sorted({x['store'] for x in row['douyin']})) or '本索引未关联'} |")
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>贝强产品与渠道</title><style>body{font:15px/1.7 system-ui;margin:0;background:#f5f6f4;color:#24372e}main{max-width:1380px;margin:auto;padding:32px}h1{margin-bottom:8px}input,select{padding:10px;font:inherit;border:1px solid #bac9bf;border-radius:6px}nav{display:flex;gap:12px;flex-wrap:wrap;position:sticky;top:0;padding:12px 0;background:#f5f6f4}article{background:white;padding:20px;border:1px solid #dce3db;margin:14px 0;border-radius:10px}h2{font-size:19px;margin:0}a{color:#12633f}small{color:#607366}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:8px;border-bottom:1px solid #e5e9e4}details{margin-top:12px}</style><main><h1>贝强产品与渠道</h1><p>先看真实产品与供应来源，再看每个渠道、每家店的商品记录。这里展示已存证据，未实时查询平台。<br>抖店索引覆盖旧店15款、新店9款档案；新店另有9212独立款尚待对应。“未关联”不等于没有上架。</p><nav><input id="q" aria-label="搜索产品" placeholder="型号、旧编码、原货号、供应商、商品ID"><select id="mode"><option value="">全部供货类型</option><option>外部供应商扩品</option><option>自产</option><option>供货类型待核</option><option>产品身份待绑定</option></select><select id="channel"><option value="">全部渠道</option><option value="alibaba">国际站有登记</option><option value="douyin_legacy">抖店旧店</option><option value="douyin_leidansenyang">雷丹森羊品牌专卖店</option></select><span id="count"></span></nav><div id="rows"></div></main><script>
const data=PAYLOAD, $=x=>document.getElementById(x), e=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function a(url,label){const urls=String(url||'').split(/\s+\+\s+/);if(urls.length>1)return urls.map((u,i)=>a(u,label+'（来源'+(i+1)+'）')).join(' / ');return /^https?:\\/\\//.test(url)?`<a href="${e(url)}" target="_blank" rel="noopener">${e(label)}</a>`:e(label)}
function render(){let q=$('q').value.trim().toLowerCase(),channel=$('channel').value;let result=data.filter(p=>(!q||JSON.stringify(p).toLowerCase().includes(q))&&(!$('mode').value||p.mode===$('mode').value)&&(!channel||(channel==='alibaba'?p.alibaba.length:p.douyin.some(l=>l.store_key===channel))));$('count').textContent=result.length+' 条';$('rows').innerHTML=result.map(p=>`<article><h2>${e(p.model)} <small>${e(p.mode)}</small></h2><p>产品身份：${e(p.id)} · 旧编码：${e((p.aliases||[]).filter(x=>x!==p.model).join(' / ')||'无')}<br>供应商：${a(p.supplier_url,p.supplier)} · 原款：${a(p.source_url,p.source_model||'待核')} · 来源：${e(p.source_state)}</p><p>国际站：${p.alibaba.length}条历史/正式ID；抖店：${p.douyin.map(l=>e(l.store+' / '+l.source_model+' / '+l.version)).join('；')||'本索引未关联'}</p><details><summary>各渠道保存的状态及档案</summary><table><tr><th>渠道 / 店铺</th><th>商品对象</th><th>证据范围</th></tr>${p.alibaba.map(l=>{let o=l.current_platform_fields||l.observation||{};return `<tr><td>Alibaba 国际站</td><td>${a(l.url,l.model)}<br>${e(l.id)}</td><td>${e(o.status||o.audit||'未核')} / ${e(o.display||'')}<br>${e(o.at||'时间见原证据')}</td></tr>`}).join('')}${p.douyin.map(l=>`<tr><td>${e(l.store)}</td><td>${e(l.source_model)} / ${e(l.version)}<br><a href="${e(l.file_url)}">渠道内容档案</a></td><td>${e(l.saved_state)}<br>档案维护 ${e(l.evidence_date)}；精确ID/回执留本地</td></tr>`).join('')}</table></details></article>`).join('')}
for(let id of ['q','mode','channel'])$(id).addEventListener('input',render);render();</script></html>'''
    for row in rows:
        # Only navigation and public product state; no private IDs, sessions or raw receipts.
        row.pop('notes', None)
        row['alibaba'] = [{k: x[k] for k in ('id','model','url','observation','current_platform_fields') if k in x} for x in row['alibaba']]
        for link in row['douyin']:
            link['file_url'] = file_link(Path(link['content_file']))
    payload = json.dumps(rows, ensure_ascii=False).replace('<', '\\u003c')
    return {HUB/'外部供应商扩品.md': ('\n'.join(external)+'\n').encode(), HUB/'产品与渠道查询.html': page.replace('PAYLOAD', payload).encode()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    errors = []
    for path, body in build().items():
        target = ROOT/path
        if args.check:
            if not target.exists() or target.read_bytes().replace(b'\r\n', b'\n') != body:
                errors.append(str(path))
        else:
            atomic_write(target, body)
    print('FAIL: '+', '.join(errors) if errors else 'PASS: product, supplier and store views agree')
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
