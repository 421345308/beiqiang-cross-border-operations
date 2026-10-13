"""Generated per-product navigation. Registry and referenced originals stay editable sources."""
import json
import os
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
DETAILS = Path('02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品')
AREA = Path('02_Alibaba运营/02_单品优化记录/商品档案')


def builds(data):
    output = {}
    cache_path=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前素材清单.json'
    cache=json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {}
    sources = {s['id']: s for s in data['sources']}
    links = {}
    for listing in data['listings']:
        links.setdefault(listing['product_id'], []).append(listing)
    def ref(path, parent, label=None):
        url = quote(Path(os.path.relpath(ROOT/path, ROOT/parent)).as_posix(), safe='/.:_-')
        return f'[{label or Path(path).name}]({url})'
    for product in data['products']:
        parent = AREA / product['id']
        lines = [f"# {' / '.join(product['aliases'])} 商品档案", '',
                 '此页由唯一台账生成，是本款唯一资料入口；修改事实到下方唯一字段文件或台账，平台正式值到按ID保存的回读原件。原始包只读，候选/历史材料不当当前线上素材。', '',
                 f"来源状态：`{product['source_state']}`。下一步：{product['next_action']}", '',
                 '## 当前资料与实物证据', '']
        assets = product.get('local_assets', {})
        current = assets.get('current_fields_file')
        lines += [f"- 本地事实/准备字段：{ref(current,parent)}" if current else '- 本地事实/准备字段：尚未指定；不从线上页面证明自产或实物能力。']
        for path in assets.get('asset_roots', []):
            lines.append(f'- 当前素材目录：{ref(path,parent,Path(path).name)}')
        for path in product.get('raw_packages', []):
            lines.append(f'- 原始包：{ref(path,parent,Path(path).name)}')
        for path in product.get('historical_asset_roots', []):
            lines.append(f'- 历史准备素材（禁止直接上传）：{ref(path,parent,Path(path).name)}')
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
        lines += ['', '## 国际站链接与本地正式字段', '']
        for listing in sorted(links.get(product['id'], []), key=lambda x:x['id']):
            pid = listing['id']
            path = DETAILS / pid / 'formal_get.json'
            lines += [f"### {listing['model']} · {pid}", '', f"- 平台链接：[{pid}]({listing['url']})" if listing.get('url') else '- 平台直链：待补']
            if (ROOT/path).exists():
                snap = json.loads((ROOT/path).read_text(encoding='utf-8'))
                actual = snap['response']['product']
                lines += [f"- 正式回读：{ref(path,parent,'完整商品字段')}；UTC {snap['observed_at_utc']}。", f"- 当前正式标题：{actual.get('subject','')}", f"- 审核/展示：{actual.get('status','')} / {actual.get('display','')}；平台类目ID：{actual.get('category_id','')}。", f"- 正式字段原件包含：{', '.join(sorted(actual))}。", '- SKU、材料、价格/数量档、包装、交期、图库、详情及FAQ按接口返回原文留存；接口未返回的字段仍待核，未做公开视觉验收不记通过。']
                group_id=str(actual.get('group_id') or '')
                group_file=DETAILS.parent/'店内分组'/(group_id+'.json')
                if group_id and (ROOT/group_file).exists():
                    group=json.loads((ROOT/group_file).read_text(encoding='utf-8'))['response'].get('product_group',{})
                    lines.append(f"- 店内分组：{group.get('group_name','')} · {group_id}；{ref(group_file,parent,'平台分组回执')}。")
                roles=cache.get('products',{}).get(pid,{})
                if roles:
                    lines.append('- 本地平台素材：'+ref(cache_path.relative_to(ROOT),parent,'唯一素材索引')+'；图片按内容哈希保存一份，图库/详情/SKU通过索引引用。')
                    for slot,url in enumerate(actual.get('main_image',{}).get('images',[]),1):
                        asset=cache.get('assets',{}).get(url,{})
                        lines.append(f"  - M{slot}：{ref(asset['file'],parent,'本地原图')} · {asset.get('width','')}×{asset.get('height','')}" if asset.get('state')=='SAVED' else f'  - M{slot}：本地图片待补；官方来源 {url}')
                else:lines.append('- 本地平台图片缓存：待补；正式字段中的官方原URL已保留。')
            else:
                lines.append('- 当前完整正式回读：待补；历史ID未检出不自动判定删除。')
            lines.append(f"- 本地同步状态：`{listing.get('local_sync',{}).get('state','UNVERIFIED')}`。")
            if listing.get('optimization'):
                opt = listing['optimization']
                lines += [f"- 本轮优化：`{opt.get('state','')}`；{opt.get('next_action','')}"]
                for path in opt.get('evidence', []):
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
