"""Refresh derived catalog/source/optimization summary without overwriting original evidence."""
from collections import Counter
import json
from pathlib import Path
from product_dossiers import sync_formal_references

ROOT=Path(__file__).resolve().parents[2]
REGISTRY=ROOT/'02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json'
AREA=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账'

def main():
    data=json.loads(REGISTRY.read_text(encoding='utf-8-sig'))
    # Actual post-write readbacks take precedence over submitted drafts. Preserve
    # every before/request/receipt file, including honest title disagreements.
    title_states=Counter();gallery_states=Counter();title_differences=[]
    for listing in data['listings']:
        folder=AREA/'当前平台目录/商品'/listing['id']/'穿脱优化'
        file=folder/'字段验收.json'
        if file.exists():
            result=json.loads(file.read_text(encoding='utf-8'));title_states[result['state']]+=1
            raw=folder/'写后正式商品.json'
            response=json.loads(raw.read_text(encoding='utf-8'))
            if response.get('product'):
                (folder.parent/'formal_get.json').write_text(json.dumps({'requested_product_id':listing['id'],'observed_at_utc':result['at'],'method':'alibaba.icbu.product.get','response':response},ensure_ascii=False,indent=2),encoding='utf-8')
            if not result['title_matches']:title_differences.append(listing['id'])
        file=folder/'图库字段验收.json'
        if file.exists():
            result=json.loads(file.read_text(encoding='utf-8'));gallery_states[result['state']]+=1
            response=json.loads((folder/'图库写后正式商品.json').read_text(encoding='utf-8'))
            # Only use later actual readbacks, not stale title-stage data.
            saved=folder.parent/'formal_get.json'
            prior=json.loads(saved.read_text(encoding='utf-8'))
            if result['at']>prior['observed_at_utc'] and response.get('product'):
                saved.write_text(json.dumps({'requested_product_id':listing['id'],'observed_at_utc':result['at'],'method':'alibaba.icbu.product.get','response':response},ensure_ascii=False,indent=2),encoding='utf-8')
            opt=listing.setdefault('optimization',{})
            opt['gallery']={**result,'evidence':[(folder/name).relative_to(ROOT).as_posix() for name in ['图库拟改字段.json','图库更新回执.json','图库字段验收.json']]}
    formal=sync_formal_references(data)
    links={p['id']:[] for p in data['products']}
    for listing in data['listings']:links[listing['product_id']].append(listing)
    groups={p.stem:json.loads(p.read_text(encoding='utf-8'))['response'].get('product_group',{}) for p in (AREA/'当前平台目录/店内分组').glob('*.json')}
    for product in data['products']:
        names=set()
        for listing in links[product['id']]:
            gid=listing.get('platform_group',{}).get('id')
            if gid:names.add(gid)
        product.setdefault('classification',{})['store_groups']=[{'id':gid,'name':groups.get(gid,{}).get('group_name','')} for gid in sorted(names)]
        product['classification']['store_group_state']='FORMAL_PRODUCT_AND_GROUP_READBACK' if names else 'NOT_RETURNED_PENDING_REVIEW'
        assets=product.get('local_assets',{})
        assets['state']='SINGLE_CURRENT_FACT_ENTRY' if assets.get('current_fields_file') else 'SINGLE_DOSSIER_SOURCE_FACTS_PENDING'
        assets['scope']='商品档案为唯一当前入口；事实准备表与每ID最新正式字段分开维护，历史标题不冒充当前线上标题'
    unresolved=[p['id'] for p in data['products'] if not any(p.get(k) for k in ['raw_packages','adopted_source_id','reference_source_id','candidate_source_ids'])]
    media=json.loads((AREA/'当前素材清单.json').read_text(encoding='utf-8'))
    scores={}
    for path in (AREA/'当前平台目录/商品').glob('*/穿脱优化/当前质量评分.json'):
        result=json.loads(path.read_text(encoding='utf-8'))['response'].get('result',{})
        scores[path.parent.parent.name]=result.get('final_score')
    cleanup=json.loads((AREA/'本地资产唯一性.json').read_text(encoding='utf-8'))
    summary={'formal_snapshots_saved':formal,'product_families':len(data['products']),'registered_links':len(data['listings']),
             'saved_source_records':len(data['sources']),'source_records_without_url':[s['id'] for s in data['sources'] if not s.get('url')],
             'products_without_original_or_source':unresolved,'known_duplicate_identities_consolidated':data.get('identity_consolidation',[]),
             'platform_media':{k:media[k] for k in ['urls','saved_urls','unique_files','errors']},'title_verification_states':dict(title_states),'title_differences':title_differences,
             'gallery_verification_states':dict(gallery_states),'scope':'当前API返回字段已存；视频原文件及公开呈现不在本轮完整图片缓存范围，未核字段不称已完成。',
             'current_quality_score_counts':dict(Counter(scores.values())),
             'exact_duplicate_files_deleted':cleanup['deleted']+cleanup.get('platform_cache_reuse',{}).get('deleted_exact_cache_copies',0),
             'public_qa_issue':'浏览器请求头策略服务不可用，IAB webview连接超时；正常重连未成功，公开视觉验收待恢复；不是缺负责人授权。'}
    data['current_catalog_summary']=summary
    data.setdefault('catalog_reconciliation',{})['formal_snapshots_saved']=formal
    work=next(w for w in data['workstreams'] if w['name']=='本地与国际站对应及BQ穿脱需求优化')
    work['status']=f'{formal}份当前完整字段已存；{len(data["products"])}个产品身份、{len(data["sources"])}条来源；2组同款别名归并，BQ052误编号已迁移，61份精确重复图已删；37条标题提交、{sum(gallery_states.values())}条图库已回读（{gallery_states.get("GALLERY_FORMAL_VERIFIED_PUBLIC_PENDING",0)}条已审核/{gallery_states.get("GALLERY_PENDING_APPROVAL",0)}条待审）；公开终验待恢复。'
    work['next_action']=f'先查{len(title_differences)}条正式标题差异原因，不盲目重复提交；图库审核后正式/公开验收；{len(unresolved)}个旧产品仍缺原件/来源，保留HOLD不冒充供货；视频原件需按关联单独补全。'
    work['evidence']=list(dict.fromkeys(work.get('evidence',[])+[(AREA/name).relative_to(ROOT).as_posix() for name in ['当前素材清单.json','本地资产唯一性.json','素材位置调整.json']]))
    REGISTRY.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':main()
