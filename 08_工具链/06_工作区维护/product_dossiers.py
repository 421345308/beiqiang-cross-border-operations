"""Generated per-product navigation. Registry and referenced originals stay editable sources."""
import json
import os
from pathlib import Path
from urllib.parse import quote, urlsplit
import re
from product_asset_store import ALIASES, read, resolve_legacy_asset

ROOT = Path(__file__).resolve().parents[2]
DETAILS = Path('02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品')
AREA = Path('02_Alibaba运营/02_单品优化记录/商品档案')
ASSET_INDEX = Path('00_总控台/产品中心/数据/素材索引.json')


def official_image_key(url):
    """Identify the same Alibaba image across its short and long CDN paths."""
    parts = urlsplit(url)
    host = (parts.hostname or '').lower()
    if host != 'alicdn.com' and not host.endswith('.alicdn.com'):
        return None
    match = re.match(r'^/kf/([^/]+)', parts.path)
    if not match:
        return None
    return re.sub(r'\.(?:jpe?g|png|webp|gif)$', '', match.group(1), flags=re.I)


def formal_snapshot(listing):
    """A registered receipt is authoritative; missing it never revives an older shoe."""
    registered = listing.get('formal_fields') or {}
    path = Path(registered['file']) if registered.get('file') else DETAILS / listing['id'] / 'formal_get.json'
    if not (ROOT / path).is_file():
        return path, None, None
    snap = read(ROOT / path)
    actual = (snap.get('response') or {}).get('product') or snap.get('product')
    return path, actual, snap.get('observed_at_utc') or snap.get('observed_at') or registered.get('at')


def indexed_image(url, product, index):
    owners = {product['id'], product.get('current_model'), *product.get('aliases', [])}
    candidates = []
    for item in index.get('files', []):
        if not owners.intersection(item.get('products', [])) or not item.get('file'):
            continue
        urls = item.get('official_urls') or []
        if url in urls:
            candidates.append((0, item))
        elif official_image_key(url) and any(official_image_key(u) == official_image_key(url) for u in urls):
            candidates.append((1, item))
    if not candidates:
        return None
    best = min(rank for rank, _ in candidates)
    matches = {item['file']: item for rank, item in candidates if rank == best}
    return next(iter(matches.values())) if len(matches) == 1 else None


def builds(data):
    output = {}
    migration_index = read(ALIASES) if ALIASES.exists() else {}
    cache_path=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前素材清单.json'
    cache=json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {}
    asset_index = read(ROOT / ASSET_INDEX) if (ROOT / ASSET_INDEX).exists() else {}
    sources = {s['id']: s for s in data['sources']}
    links = {}
    for listing in data['listings']:
        links.setdefault(listing['product_id'], []).append(listing)
    def ref(path, parent, label=None):
        target = resolve_legacy_asset(path, migration_index=migration_index)
        # An offline original can live on another drive; relpath cannot cross drives.
        destination = target.as_posix() if target.drive != ROOT.drive else Path(os.path.relpath(target, ROOT/parent)).as_posix()
        url = quote(destination, safe='/.:_-')
        return f'[{label or Path(path).name}]({url})'
    for product in data['products']:
        parent = Path(product['dossier_path']).parent if product.get('dossier_path') else AREA / product['id']
        current_model=product.get('current_model')or product['aliases'][0]
        lines = [f"# {current_model} 商品档案", '',
                 '此页是本款国际站档案，由产品中心及国际站商品数据组合生成；跨渠道共用身份与供应来源回产品中心，渠道正式值回按ID保存的回读原件。原始包只读，候选/历史材料不当当前线上素材。', '',
                 f"来源状态：`{product['source_state']}`。下一步：{product['next_action']}", '',
                 '## 当前资料与实物证据', '']
        route=product.get('supply_mode',{})
        if route:
            label={'EXTERNAL_FACTORY':'外采','OWN_FACTORY':'自产'}.get(route.get('current'),'供货类型待核')
            lines += [f"- 当前供货类型（内部）：{label}；{route.get('state','')}。货号不随供货路径永久绑定，转产后更新证据与生效范围。"]
            for path in route.get('evidence',[]):lines.append('- 供货分类依据：'+ref(path,parent))
        assets = product.get('local_assets', {})
        current = assets.get('current_fields_file')
        lines += [f"- 本地事实/准备字段：{ref(current,parent)}" if current else '- 本地事实/准备字段：尚未指定；不从线上页面证明自产或实物能力。']
        for path in assets.get('asset_roots', []):
            lines.append(f'- 当前素材目录：{ref(path,parent,Path(path).name)}')
        if assets.get('current_gallery_by_id'):
            lines.append('- 当前主图库按商品ID对应（含最新统一工厂图）：')
            for pid,path in assets['current_gallery_by_id'].items():lines.append('  - '+ref(path,parent,pid+' 当前图库与货号'))
        if assets.get('current_image_map'):
            lines.append(('- 商品图制作映射（主图库以逐ID最新记录为准）：'if assets.get('current_gallery_by_id')else'- 当前选图与正式CDN映射：')+ref(assets['current_image_map'],parent))
        for path in product.get('raw_packages', []):
            lines.append(f'- 原始包：{ref(path,parent,Path(path).name)}')
        lines += ['', '## 采购来源（内部使用）', '']
        source_ids = list(dict.fromkeys([x for x in [product.get('adopted_source_id'),product.get('reference_source_id'),*product.get('candidate_source_ids',[])] if x]))
        if not source_ids:
            lines.append('采购商品直链待补；不补造供应商、价格或供给。')
        for sid in source_ids:
            s = sources[sid]
            role = '已采用记录' if sid == product.get('adopted_source_id') else '原款参考映射' if sid == product.get('reference_source_id') else '候选未采用'
            lines += [f"- {role}：[{s.get('supplier') or '供方待核'} / {s.get('model') or '货号待核'}]({s['url']})", f"  - 保存的标价：{s.get('currency') or '币种待核'} {s.get('price') or '价格待核'} / {s.get('unit') or '单位待核'}；原观察日期：{s.get('observed_at') or '待补'}。{s.get('price_terms') or ''}"]
            if s.get('shop_url'):
                lines.append(f"  - 供方店铺入口：[{s['shop_url']}]({s['shop_url']})")
            for path in s.get('evidence', []):
                lines.append(f'  - 来源原件：{ref(path,parent)}')
        routes=product.get('source_routes_by_color',{})
        if routes:
            lines += ['', '### 按颜色采购入口', '', '同一基础鞋款的配色可能来自不同来源页。采购按下表核货号、颜色及EU范围；主来源链接不能代替每色入口。', '', '| 本店颜色 | 供方颜色 / 货号 | EU尺码 | 真实采购入口 |', '| --- | --- | --- | --- |']
            for color,route in routes.items():
                source=sources[route['source_id']]
                assert source['url'].rstrip('/')==route['source'].rstrip('/'), 'Colour route conflicts with registered source'
                sizes=route['EU']
                lines.append(f"| {color} | {route['supplier_color']} / {route['source_artno']} | {', '.join(str(n) for n in sizes)} | [{source['model']}]({source['url']}) |")
            if assets.get('current_family_plan'):
                lines += ['', '- 当前家族与色码计划：'+ref(assets['current_family_plan'],parent)]
        deferred=product.get('deferred_source_options',{})
        if deferred:
            choices=deferred['colours']
            assert deferred['EU_combinations']==sum(len(v) for v in choices.values())
            lines += ['', '### 来源有记录但尚未验收上架的颜色', '', f"下列{deferred['EU_combinations']}个EU组合尚未验收上架，不算作当前已验收SKU；只在本款原ID增补。待办：{deferred.get('reason','核对来源与当前提交状态')}。", '', '| 待完成颜色 | 尚未验收上架的EU尺码 |', '| --- | --- |']
            for colour,sizes in choices.items():lines.append(f"| {colour} | {', '.join(str(n) for n in sizes)} |")
            lines += ['', '- 范围依据：'+ref(deferred['evidence'],parent)]
        lines += ['', '## 国际站链接与本地正式字段', '']
        for listing in sorted(links.get(product['id'], []), key=lambda x:x['id']):
            pid = listing['id']
            path, actual, observed_at = formal_snapshot(listing)
            lines += [f"### {listing['model']} · {pid}", '', f"- 平台链接：[{pid}]({listing['url']})" if listing.get('url') else '- 平台直链：待补']
            if actual:
                lines += [f"- 正式回读：{ref(path,parent,'完整商品字段')}；时间 {observed_at or '待补'}。", f"- 当前正式标题：{actual.get('subject','')}", f"- 审核/展示：{actual.get('status','')} / {actual.get('display','')}；平台类目ID：{actual.get('category_id','')}。", f"- 正式字段原件包含：{', '.join(sorted(actual))}。", '- SKU、材料、价格/数量档、包装、交期、图库、详情及FAQ按接口返回原文留存；接口未返回的字段仍待核，未做公开视觉验收不记通过。']
                group_id=str(actual.get('group_id') or '')
                group_file=DETAILS.parent/'店内分组'/(group_id+'.json')
                if group_id and (ROOT/group_file).exists():
                    group=json.loads((ROOT/group_file).read_text(encoding='utf-8'))['response'].get('product_group',{})
                    lines.append(f"- 店内分组：{group.get('group_name','')} · {group_id}；{ref(group_file,parent,'平台分组回执')}。")
                images = actual.get('main_image', {}).get('images', [])
                if images:
                    lines.append('- 当前正式主图按官方图链匹配本地素材；旧图片不按槽位继承。')
                    for slot, url in enumerate(images, 1):
                        item = indexed_image(url, product, asset_index)
                        asset = cache.get('assets', {}).get(url, {})
                        if item and (ROOT / item['file']).is_file():
                            lines.append(f"  - M{slot}：{ref(item['file'],parent,'本地原图')}；官方来源 {url}")
                        elif asset.get('state') == 'SAVED' and asset.get('file') and resolve_legacy_asset(asset['file'], migration_index=migration_index).is_file():
                            lines.append(f"  - M{slot}：{ref(asset['file'],parent,'本地原图')}；官方来源 {url}")
                        else:
                            lines.append(f'  - M{slot}：本地图片待补；官方来源 {url}')
                else:
                    lines.append('- 当前正式回读未返回主图；不继承旧图库。')
            else:
                if listing.get('formal_fields', {}).get('file'):
                    lines.append(f"- 已登记的正式回读缺失或无商品字段：{ref(path,parent,'登记的回读')}；不回退旧字段。")
                else:
                    lines.append('- 当前完整正式回读：待补；历史ID未检出不自动判定删除。')
            presence=listing.get('observation',{}).get('current_presence')
            if presence:
                lines.append(f"- 较新目录/原ID存在性：`{presence['state']}`；UTC {presence['at']}；{ref(presence['evidence'],parent,'精确回读证据')}。以上正式字段保留原核验日期；未返回原因未知，不重复创建。")
            lines.append(f"- 本地同步状态：`{listing.get('local_sync',{}).get('state','UNVERIFIED')}`。")
            if listing.get('optimization'):
                opt = listing['optimization']
                title_opt = opt.get('title_search')
                if title_opt:
                    lines.append(f"- 标题搜索优化：`{title_opt.get('state','')}`；{title_opt.get('next_action','')}")
                    for evidence in title_opt.get('evidence', []):
                        lines.append(f'  - 标题证据：{ref(evidence,parent)}')
                current_opt=opt.get('content_quality_revision') or opt.get('product_performance_review') or opt.get('model_factory_normalization') or opt.get('family_color_expansion') or opt.get('real_source_creation') or opt
                lines += [f"- 本轮优化：`{current_opt.get('state','')}`；{current_opt.get('next_action','')}"]
                for path in current_opt.get('evidence', []):
                    lines.append(f'  - 变更证据：{ref(path,parent)}')
                if opt.get('gallery'):
                    lines.append(f"- 图库调整：`{opt['gallery'].get('state','')}`。")
                    for path in opt['gallery'].get('evidence',[]):lines.append(f'  - 图库证据：{ref(path,parent)}')
            lines.append('')
        if not links.get(product['id']):
            lines += ['本地已有商品资料，未关联国际站商品ID；保留未发布身份，不冒充线上商品。', '']
        lines += ['## 其他原始/正式证据', '']
        for path in product.get('evidence', []):
            if path != current:
                lines.append(f'- {ref(path,parent)}')
        lines += ['', '原件、正式回执与当前资料通过本页关联，不再复制成第二套商品库。', '']
        output[parent/'README.md'] = '\n'.join(lines).encode('utf-8')
    return output


def sync_formal_references(data):
    seen = 0
    for listing in data['listings']:
        path = DETAILS / listing['id'] / 'formal_get.json'
        registered = (listing.get('formal_fields') or {}).get('file')
        if registered and Path(registered).as_posix() != path.as_posix():
            _, actual, _ = formal_snapshot(listing)
            if actual:
                seen += 1
            continue
        if not (ROOT/path).exists():
            continue
        snap = json.loads((ROOT/path).read_text(encoding='utf-8'))
        actual = snap['response'].get('product') or {}
        if not actual:
            continue
        listing['formal_fields'] = {'file':path.as_posix(), 'at':snap['observed_at_utc'], 'scope':'product.get返回的完整字段；不等于来源或公开视觉验收'}
        listing['current_platform_fields']={'at':snap['observed_at_utc'],'title':actual.get('subject',''),'keywords':actual.get('keywords',[]),'main_images':actual.get('main_image',{}).get('images',[]),'category_id':actual.get('category_id'),'display':actual.get('display'),'status':actual.get('status'),'url':actual.get('pc_detail_url',''),'scope':'按ID完整product.get正式字段；审核与公开验收分开'}
        listing['local_sync'] = {'state':'FORMAL_SNAPSHOT_SAVED', 'current_fields_file':path.as_posix(), 'next_action':'正式字段已保存在本地；逐款核实物事实/当前素材，并验收本次优化公开呈现'}
        seen += 1
    data.setdefault('catalog_reconciliation',{})['formal_snapshots_saved'] = seen
    return seen
