"""Render the expansion workspace from one normalized, offline evidence registry.

No network, publishing, timestamp inference, or source discovery. Edit the registry,
then run this script. --check verifies the registry and committed views without writes.
"""
from __future__ import annotations

import argparse
import csv
import html
import io
import hashlib
import os
import tempfile
import json
from pathlib import Path
from urllib.parse import urlsplit, quote

ROOT = Path(__file__).resolve().parents[2]
AREA = Path('02_Alibaba运营/05_扩品工程')
REGISTRY = AREA / '数据/产品与链接台账.json'
TOTAL = AREA / '国际站合规扩品工程总控.md'
QUERY = AREA / '供应商产品总表/供应商产品查询.html'
CSV = AREA / '供应商产品总表/供应商产品总表.csv'
FIELDS = ['记录类型','本店型号','国际站商品ID','国际站直达链接','供应商','供应商店铺链接','供应商原货号','供应鞋款直达链接','来源页标价','币种','价格单位','价格条件','来源核价日期','本次整理日期','正式来源证据','来源关系状态','最近回读审核','最近回读展示','平台观察时间UTC','缺项与冲突']

def local_link(path: str, base: Path, label: str='证据') -> str:
    import os
    relative = Path(os.path.relpath(ROOT/path, ROOT/base)).as_posix()
    return f'[{label}]({quote(relative, safe="/.:_-#")})'

def clean(value: object) -> str:
    return str(value or '').replace('|',' / ').replace('\n',' ').replace('\r',' ')

def view_matches(path: Path, expected: bytes) -> bool:
    """Git may check text out as CRLF on Windows; that is not a content change."""
    return path.exists() and path.read_bytes().replace(b'\r\n',b'\n')==expected.replace(b'\r\n',b'\n')

def write_generated(path: Path,body: bytes) -> None:
    """Publish a whole derived view atomically while other tasks read it."""
    if view_matches(path,body):return
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.derived-',suffix='.tmp',delete=False) as stream:
            stream.write(body);temporary=Path(stream.name)
        os.replace(temporary,path)
    finally:
        if temporary and temporary.exists():temporary.unlink()

def validate(data: dict, root: Path=ROOT) -> list[str]:
    errors=[]
    if data.get('schema_version') != 1:
        errors.append('unsupported schema_version')
    sets={}
    for section in ('sources','products','listings'):
        ids=[x['id'] for x in data[section]]
        if len(ids)!=len(set(ids)): errors.append(f'{section}: duplicate ID')
        sets[section]=set(ids)
    aliases={}
    for product in data['products']:
        for alias in product['aliases']:
            if alias in aliases: errors.append(f'duplicate product alias: {alias}')
            aliases[alias]=product['id']
        for key in ('adopted_source_id','reference_source_id'):
            ref=product.get(key)
            if ref and ref not in sets['sources']: errors.append(f'{product["id"]}: unknown {key}')
        for ref in product.get('candidate_source_ids',[]):
            if ref not in sets['sources']: errors.append(f'{product["id"]}: unknown candidate {ref}')
        if product.get('source_state')=='CONFLICT' and product.get('adopted_source_id'):
            errors.append(f'{product["id"]}: conflicted source must not be adopted')
    source_keys=[(s['url'],s.get('model','')) for s in data['sources'] if s.get('url')]
    if len(source_keys)!=len(set(source_keys)): errors.append('same source URL and original model must be maintained once')
    for source in data['sources']:
        if source.get('url') and urlsplit(source['url']).scheme not in ('https','http'):
            errors.append(f'{source["id"]}: unsafe URL')
    for listing in data['listings']:
        if listing['product_id'] not in sets['products']: errors.append(f'{listing["id"]}: unknown product')
        if not listing['id'].isdigit(): errors.append(f'{listing["id"]}: invalid Alibaba ID')
        ref=listing.get('bound_source_id')
        if ref and ref not in sets['sources']: errors.append(f'{listing["id"]}: unknown bound source')
        fields=listing.get('local_sync',{}).get('current_fields_file')
        if fields and not (root/fields).is_file(): errors.append(f'{listing["id"]}: missing current fields file')
        # Every sibling shares identity, but formal source binding stays per listing.
        import re
        normalized=re.sub(r'^BQ-(\d{3})(?=[- /]|$)',r'BQ\1',listing['model'])
        match=re.match(r'^(HR\d{3}|BQ\d{3})(?:[- /]|$)',normalized)
        if match and aliases.get(match[1])!=listing['product_id']:
            errors.append(f'{listing["id"]}: sibling is split from its family')
    for section in ('sources','products','listings','workstreams'):
        for item in data[section]:
            for p in item.get('evidence',[]):
                target=root/p
                if '..' in Path(p).parts or Path(p).is_absolute(): errors.append(f'unsafe evidence path: {p}')
                elif not target.exists(): errors.append(f'missing evidence: {p}')
    for item in data.get('imported_evidence',[]):
        target=root/item['path']
        if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest()!=item['sha256']:
            errors.append(f'imported source evidence hash mismatch: {item["path"]}')
    for product in data['products']:
        assets=product.get('local_assets',{})
        for path in assets.get('asset_roots',[])+([assets['current_fields_file']] if assets.get('current_fields_file') else []):
            if Path(path).is_absolute() or '..' in Path(path).parts or not (root/path).exists():
                errors.append(f'{product["id"]}: invalid asset path: {path}')
    return errors

def build(data: dict) -> dict[Path, bytes]:
    products={p['id']:p for p in data['products']}
    sources={s['id']:s for s in data['sources']}
    listings={p:[] for p in products}
    for link in data['listings']: listings[link['product_id']].append(link)
    def source_display(p):
        source=sources.get(p.get('adopted_source_id') or p.get('reference_source_id'))
        if source:
            return f"[{clean(source.get('supplier') or source.get('model') or '原鞋款')}]({source['url']}) · {clean(source.get('model'))}",source
        candidates=[sources[s] for s in p.get('candidate_source_ids',[])]
        if candidates:
            return '；'.join(f"[候选 {clean(s.get('model') or i+1)}]({s['url']})" for i,s in enumerate(candidates)),candidates[0]
        raw=p.get('raw_packages',[])
        if raw: return local_link(raw[0],AREA,'原始包')+'（网上直链待补）',None
        return '缺实鞋/采购证据',None
    adopted=sum(bool(p.get('adopted_source_id')) for p in products.values())
    mapped=sum(bool(p.get('reference_source_id')) for p in products.values())
    candidate=sum(not p.get('adopted_source_id') and not p.get('reference_source_id') and bool(p.get('candidate_source_ids')) for p in products.values())
    missing=sum(not p.get('adopted_source_id') and not p.get('reference_source_id') and not p.get('candidate_source_ids') for p in products.values())
    md=['# 国际站扩品总文件','',f"整理日期：{data['updated_on']}。此日期表示台账整理，货源、价格、平台状态沿用各自证据时间；本次未重新核验线上。",'',
        '**日常只看本文件；需要检索时打开[同数据查询页](供应商产品总表/供应商产品查询.html)。** 款式、原鞋款直链、存量链接和下一动作汇总如下，不要求阅读每次修改记录。','',
        f"登记 {len(products)} 个产品/候选组，关联 {len(data['listings'])} 个历史及正式商品ID；{adopted} 组有已采用的历史来源映射，{mapped} 组补回原款来源但逐链接绑定待核，{candidate} 组只有候选来源，{missing} 组仍缺采购映射。登记组数不代表独立鞋型、在线数量或已确认供给。",'',
        'A/B/C 以及同一 BQ 编号下的存量后缀链接共用产品身份与货源，只做一次款式溯源；各商品ID的提交、审核、展示、关键词及公开验收分别记录。候选不等于已经替换，缺失兄弟链接的正式绑定不靠推断补成通过。','',
        '## 当前任务与下一步','', '| 工作 | 已有结论及边界 | 下一步 | 证据 |','| --- | --- | --- | --- |']
    for work in data['workstreams']:
        refs=' · '.join(local_link(p,AREA) for p in work.get('evidence',[]))
        md.append(f"| {clean(work['name'])} | {clean(work['status'])} | {clean(work['next_action'])} | {refs} |")
    reconciliation=data.get('catalog_reconciliation',{})
    if reconciliation:
        md+=['','## 本地与平台目录对应','',
            f"目录证据时间（UTC）：{reconciliation['observed_at_utc']}；完整分页 {reconciliation['platform_ids']} 个平台ID，台账 {reconciliation['registered_ids']} 个历史/正式ID。平台未登记 {len(reconciliation['platform_without_local_ids'])} 个；历史本地ID本轮未检出 {len(reconciliation['local_not_observed_ids'])} 个。未检出不等于下架。",'',
            '查询页可按采购意图候选分类检索并打开本地当前字段文件。分类来自本轮标题观察，必须逐款核实结构后采用；目录索引不等于全字段双改已完成，平台类目与店内分组分别记录。','',
            '| 本地入口冲突 | 当前文件 | 处理 |','| --- | --- | --- |']
        for conflict in reconciliation.get('local_entry_conflicts',[]):
            md.append(f"| {clean(conflict['product_id'])} | {' · '.join(local_link(p,AREA,'字段文件') for p in conflict['paths'])} | 核真实货号/ID后选唯一入口，不按编号直接删除 |")
    md+=['','## 款式与源头总表','',
        '“已采用待复核”是保存证据中的采用关系；“候选未替换”不得用于该旧商品履约。点击原款进入源头，点击商品编号进入国际站；原始包及正式回执继续作为证据保留。','',
        '| 产品 / 家族 | 原鞋款直链（共用） | 来源层级 | 原页参考价 / 日期 | 关联商品链接 | 下一步 |','| --- | --- | --- | --- | --- | --- |']
    states={'ADOPTED':'已采用待复核','MAPPED':'原款来源已关联；链接绑定待核','CANDIDATE':'候选未替换','MISSING':'缺证','RAW_PACKAGE':'原始包已关联；采购直链待核','CONFLICT':'来源冲突待核'}
    rendered=[]
    for pid,p in sorted(products.items()):
        src,s=source_display(p)
        price='—'
        if s and s.get('price'): price=f"{s.get('currency','')} {s['price']} / {s.get('observed_at') or '日期见证据'}"
        links=[]
        details=[]
        for link in sorted(listings[pid],key=lambda x:(x['model'],x['id'])):
            label=link['model']
            links.append(f"[{clean(label)}]({link['url']})" if link.get('url') else f"{clean(label)} `{link['id']}`（历史未返回）")
            obs=link.get('observation',{})
            current=link.get('current_platform_fields',link.get('catalog_fields',{}))
            details.append({'model':label,'id':link['id'],'url':current.get('url') or link.get('url',''),'status':current.get('status') or obs.get('audit',''),'display':current.get('display') or obs.get('display',''),'observed_at':current.get('at') or obs.get('at',''),'source_bound':bool(link.get('bound_source_id')),'scope':current.get('scope') or obs.get('scope',''),'catalog_presence':link.get('catalog_presence','未核'),'catalog_fields':current,'local_sync':link.get('local_sync',{}).get('state','未核')})
        md.append(f"| {clean(' / '.join(p['aliases']))} | {src} | {states.get(p['source_state'],p['source_state'])} | {clean(price)} | {'<br>'.join(links) or '未关联正式ID'} | {clean(p['next_action'])} |")
        rendered.append({'id':pid,'aliases':p['aliases'],'source_state':p['source_state'],'source_label':states.get(p['source_state'],p['source_state']),'source':sources.get(p.get('adopted_source_id') or p.get('reference_source_id')),'candidates':[sources[x] for x in p.get('candidate_source_ids',[])],'raw_packages':p.get('raw_packages',[]),'next_action':p['next_action'],'notes':p.get('notes',[]),'listings':details,'evidence':p.get('evidence',[])})
        rendered[-1]['classification']=p.get('classification',{})
        assets=p.get('local_assets',{})
        import os
        rendered[-1]['local_assets']={'state':assets.get('state','待补'), 'files':[{'path':path,'url':quote(Path(os.path.relpath(ROOT/path,ROOT/QUERY.parent)).as_posix(),safe='/.:_-')} for path in ([assets['current_fields_file']] if assets.get('current_fields_file') else assets.get('asset_roots',[]))]}
        dossier=p.get('dossier_path')
        if dossier:
            rendered[-1]['local_assets']['files'].insert(0,{'path':'本款统一商品档案','url':quote(Path(os.path.relpath(ROOT/dossier,ROOT/QUERY.parent)).as_posix(),safe='/.:_-')})
    md+=['','## 维护方式','',
        '只修改[产品与链接台账](数据/产品与链接台账.json)，运行[生成与检查工具](../../08_工具链/06_工作区维护/build_product_workspace.py)刷新本页、查询页和兼容CSV；这些展示文件不独立维护。规则只改[唯一商品SOP](../00_运营SOP/国际站商品全生命周期SOP.md)。','',
        '当前结论覆盖原条目；不按修改次数新建报告、队列或“明早验收”。正式写入/拒绝/未知结果及证明验收范围的原始回执按商品ID留存，新证据只更新对应台账并关联回执。历史材料中的旧暂停、线程分工和待授权不自动成为当前指令。','']
    payload=json.dumps(rendered,ensure_ascii=False).replace('<','\\u003c')
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>扩品总表 · 贝强</title><style>
body{font:15px/1.6 system-ui,sans-serif;color:#183139;background:#f5f7f5;margin:0}main{max-width:1400px;margin:auto;padding:32px}h1{font-size:28px}input,select{font:inherit;padding:10px;border:1px solid #b8c8c4;border-radius:8px}input{width:min(520px,70%)}.bar{display:flex;gap:12px;flex-wrap:wrap;position:sticky;top:0;background:#f5f7f5;padding:12px 0}article{background:white;border:1px solid #dce4df;border-radius:12px;padding:18px;margin:12px 0}h2{font-size:19px;margin:0}.tag{color:#4a6056}.sources{display:flex;gap:12px;flex-wrap:wrap}a{color:#066864}table{width:100%;border-collapse:collapse;margin-top:12px}td,th{text-align:left;border-bottom:1px solid #eee;padding:8px}small{color:#5e716a}.missing{color:#a74725}summary{cursor:pointer}ul{padding-left:22px}</style><main><h1>扩品总表</h1><p>一款一份来源，A/B/C 共用。候选未替换；历史审核/展示不代表今天已验收。采购价及条件逐单核实。</p><div class="bar"><input id="q" aria-label="搜索" placeholder="搜索家族、型号、商品ID、原货号、供应商"><select id="state" aria-label="来源层级"><option value="">全部来源</option><option value="ADOPTED">已采用待复核</option><option value="MAPPED">原款来源已关联</option><option value="CANDIDATE">候选未替换</option><option value="MISSING">缺证</option><option value="RAW_PACKAGE">原始包关联</option><option value="CONFLICT">冲突待核</option></select><span id="count"></span></div><div id="rows"></div></main><script>
const data=PAYLOAD;
const $=x=>document.getElementById(x),esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function a(url,label){return /^https?:\\/\\//.test(url)?`<a target="_blank" rel="noopener noreferrer" href="${esc(url)}">${esc(label)}</a>`:esc(label)}
function source(s,label){return `<p>${esc(label)} ${a(s.url,(s.supplier||'供应商待核')+' / '+(s.model||'原货号待核'))}<br><small>${esc(s.currency)} ${esc(s.price||'原价待核')} · 证据时间 ${esc(s.observed_at||'见原证据')} · ${esc(s.price_terms||'采购条件待核')}</small></p>`}
function render(){const q=$('q').value.trim().toLowerCase(),state=$('state').value;const rows=data.filter(p=>(!state||p.source_state===state)&&(!q||JSON.stringify(p).toLowerCase().includes(q)));$('count').textContent=rows.length+' / '+data.length+' 个组';$('rows').innerHTML=rows.map(p=>`<article><h2>${esc(p.aliases.join(' / '))} <small class="tag">${esc(p.source_label)}</small></h2><div class="sources">${p.source?source(p.source,p.source_label):''}${p.candidates.map(s=>source(s,'替换候选')).join('')}${!p.source&&!p.candidates.length?'<p class="missing">'+(p.raw_packages.length?'有原始包关联；采购直链待补':'实鞋/采购证据待补')+'</p>':''}</div><p>下一步：${esc(p.next_action)}</p><details><summary>展开 ${p.listings.length} 条关联链接及证据备注</summary><table><thead><tr><th>型号 / 商品ID</th><th>保存的审核/展示</th><th>观察时间与范围</th><th>逐链接来源绑定</th></tr></thead><tbody>${p.listings.map(l=>`<tr><td>${a(l.url,l.model)}<br>${esc(l.id)}</td><td>${esc(l.status)} / ${esc(l.display)}</td><td>${esc(l.observed_at)}<br>${esc(l.scope)}</td><td>${l.source_bound?'有采用记录':'未证明；不自动继承为通过'}</td></tr>`).join('')}</tbody></table><ul>${p.notes.map(n=>'<li>'+esc(n)+'</li>').join('')}</ul><small>${p.evidence.map(esc).join('<br>')}</small></details></article>`).join('')};$('q').oninput=render;$('state').onchange=render;render();
</script></html>'''.replace('PAYLOAD',payload)
    page=page.replace('<span id="count">','<select id="intent" aria-label="采购意图候选分类"><option value="">全部采购意图候选</option></select><span id="count">')
    page=page.replace('const rows=data.filter(p=>',"const intent=$('intent').value;const rows=data.filter(p=>(!intent||(p.classification.local_intent_candidates||[]).includes(intent))&&")
    page=page.replace('<div class="sources">','<p><small>采购意图（状态 ${esc(p.classification.state)}）：${esc((p.classification.local_intent_candidates||[]).join(" / "))} · 平台类目ID ${esc((p.classification.platform_category_ids||[]).join(" / "))} · 店内分组 ${esc((p.classification.store_groups||[]).map(g=>g.name||g.id).join(" / ")||"接口未返回，待核")}</small></p><p>本地入口：${p.local_assets.files.map(f=>`<a href="${esc(f.url)}">${esc(f.path)}</a>`).join("<br>")||"当前档案待指定"}<br><small>${esc(p.local_assets.state)}</small></p><div class="sources">')
    page=page.replace('${esc(l.scope)}</td>', '${esc(l.scope)}<br>本轮目录：${esc(l.catalog_presence)} · 本地同步：${esc(l.local_sync)}<br>本轮标题：${esc(l.catalog_fields.title||"未检出")}</td>')
    page=page.replace("$('q').oninput=render;", "$('intent').innerHTML+=[...new Set(data.flatMap(p=>p.classification.local_intent_candidates||[]))].sort().map(x=>`<option value=\"${esc(x)}\">${esc(x)}</option>`).join('');$('intent').onchange=render;$('q').oninput=render;")
    output=io.StringIO(newline='')
    writer=csv.DictWriter(output,fieldnames=FIELDS,lineterminator='\n')
    writer.writeheader()
    for link in sorted(data['listings'],key=lambda x:(x['model'],x['id'])):
        p=products[link['product_id']]
        # Export formal per-link bindings only. Candidate URLs never become a supply assertion.
        s=sources.get(link.get('bound_source_id'),{})
        obs=link.get('observation',{})
        writer.writerow(dict(zip(FIELDS,[link.get('record_type',''),link['model'],link['id'],link.get('url',''),s.get('supplier',''),s.get('shop_url',''),s.get('model',''),s.get('url',''),s.get('price',''),s.get('currency',''),s.get('unit',''),s.get('price_terms',''),s.get('observed_at',''),data['updated_on'],';'.join(link.get('evidence',[])),link.get('source_relation',''),obs.get('audit',''),obs.get('display',''),obs.get('at',''),link.get('notes','')])) )
    from product_dossiers import builds
    return {TOTAL:('\n'.join(md)).encode('utf-8'),QUERY:page.encode('utf-8'),CSV:output.getvalue().encode('utf-8-sig'),**builds(data)}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    data=json.loads((ROOT/REGISTRY).read_text(encoding='utf-8-sig'))
    errors=validate(data)
    if errors:
        for e in errors: print(e)
        return 1
    for path,body in build(data).items():
        if args.check:
            if not view_matches(ROOT/path,body): errors.append(f'stale generated view: {path}')
        else:
            write_generated(ROOT/path,body)
    for e in errors: print(e)
    print(f'{"FAIL" if errors else "PASS"}: {len(data["products"])} groups, {len(data["listings"])} IDs, {len(data["sources"])} shared sources')
    return bool(errors)

if __name__=='__main__':
    raise SystemExit(main())
