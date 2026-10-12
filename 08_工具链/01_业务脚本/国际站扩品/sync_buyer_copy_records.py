"""Sync this task's exact-ID copy/readbacks into the canonical registry and dossiers.

No platform writes. Preserve unrelated registry fields and other workstreams.
"""
from pathlib import Path
from datetime import datetime,timezone
import importlib.util,json,argparse,hashlib,sys

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'02_Alibaba运营/02_单品优化记录/全店FAQ与产品亮点优化'
REGISTRY=ROOT/'02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--ids',required=True);args=ap.parse_args()
    ids=args.ids.split(',');assert len(ids)==len(set(ids)) and all(x.isdigit() for x in ids)
    data=json.loads(REGISTRY.read_text(encoding='utf8'))
    listings={x['id']:x for x in data['listings']};products={x['id']:x for x in data['products']}
    original=REGISTRY.read_bytes();now=datetime.now(timezone.utc).isoformat();t=ROOT/'99_临时区/全店FAQ与产品亮点优化'
    # Retain only a temporary pre-edit input for a scoped Git patch, never a new business truth.
    stamp=hashlib.sha256(original).hexdigest()[:12]
    backup=t/('registry_before_buyer_sync_'+stamp+'.json');backup.write_bytes(original)
    (t/'registry_before_input.txt').write_text(str(backup),encoding='utf8')
    touched=set();states={}
    for pid in ids:
        f=BASE/'商品'/pid
        if not (f/'verification.json').exists():continue
        verification=json.loads((f/'verification.json').read_text(encoding='utf8'))
        response=json.loads((f/'after_get.json').read_text(encoding='utf8'));actual=response['product']
        listing=listings[pid];product=products[listing['product_id']];touched.add(product['id'])
        rel=lambda p:p.relative_to(ROOT).as_posix()
        evidence=[rel(f/x) for x in ['copy.json','update_receipt.json','after_get.json','verification.json','public_text_verification.json'] if (f/x).exists()]
        state=verification['status'];states[pid]=state
        resolution=f/'关键词差异/resolution.json'
        resolved=json.loads(resolution.read_text(encoding='utf8')) if resolution.exists() else {}
        public_record=f/'public_text_verification.json'
        public_proof=json.loads(public_record.read_text(encoding='utf8')) if public_record.exists() else {}
        public_status=public_proof['status'] if public_proof.get('copy_sha256')==hashlib.sha256((f/'copy.json').read_bytes()).hexdigest() else verification['public_status']
        public_pass=public_status in ('PUBLIC_TRANSLATED_TEXT_SEMANTIC_PASS','PUBLIC_ENGLISH_HIGHLIGHTS_FAQ_EXACT_PASS')
        prior_differences=[rel(p) for p in (f/'revisions').glob('*/non_target_difference.json')]
        if (f/'non_target_difference.json').exists():prior_differences.append(rel(f/'non_target_difference.json'))
        evidence += [rel(f/'revision_history.json')] if (f/'revision_history.json').exists() else []
        evidence += prior_differences
        next_action='核对应公开亮点FAQ；另核精确关联字段差异，不覆盖未知变化' if prior_differences or state=='MISMATCH_DIAGNOSE_NO_REPLAY' else '审核后核对应公开亮点FAQ；不重放已有提交' if state=='PENDING_REVIEW' else '本轮亮点FAQ正式字段与当前中文公开正文已核；其他字段未纳入本次验收' if public_pass else '核对应公开亮点FAQ；其他商品字段未纳入本次修改'
        listing.setdefault('optimization',{})['buyer_copy']={'state':state,'at':verification['observed_at'],'scope':['textDesc','companyFaqDesc'],'draft':rel(f/'copy.json'),'formal_readback':rel(f/'after_get.json'),'public_status':verification['public_status'],'evidence':evidence,'next_action':next_action}
        if prior_differences:listing['optimization']['buyer_copy']['earlier_non_target_differences']=prior_differences
        if resolved.get('status')=='CURRENT_EDIT_VERSION_CONTENT_VERIFIED_LEGACY_EMPTY':
            cp=listing['optimization']['buyer_copy'];cp.update(state='CURRENT_VERSION_COPY_VERIFIED',at=resolved['at'],historical_strict_status=state,associated_fields_resolution=rel(resolution),public_status=public_status,next_action='本轮亮点FAQ在当前编辑版本、正式与英文公开正文一致；旧关键词迁移留空，不声称已恢复旧字段')
            cp['evidence']+= [rel(x)for x in resolution.parent.glob('*.json')if rel(x)not in cp['evidence']]
        else:listing['optimization']['buyer_copy']['public_status']=public_status
        listing['optimization']['buyer_copy']['target_formal_copy_status']=verification.get('target_copy_status','TARGET_FORMAL_PASS' if state=='FORMAL_PASS' else 'PENDING')
        listing['optimization']['buyer_copy']['faq_order_match']=verification.get('formal_faq_order_match',verification['formal_faq_match'])
        # Refresh the existing canonical per-ID snapshot, not a duplicate current platform library.
        formal=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'/pid/'formal_get.json'
        prior=json.loads(formal.read_text(encoding='utf8')) if formal.exists() else {}
        if verification['observed_at']>=prior.get('observed_at_utc',''):
            formal.parent.mkdir(parents=True,exist_ok=True)
            formal.write_text(json.dumps({'requested_product_id':pid,'observed_at_utc':verification['observed_at'],'method':'alibaba.icbu.product.get','response':response},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
            listing['formal_fields']={'file':rel(formal),'at':verification['observed_at'],'scope':'product.get返回的完整字段；不等于来源或公开视觉验收'}
            listing['current_platform_fields']={**listing.get('current_platform_fields',{}),'at':verification['observed_at'],'title':actual.get('subject',''),'keywords':actual.get('keywords',[]),'main_images':actual.get('main_image',{}).get('images',[]),'category_id':actual.get('category_id'),'display':actual.get('display'),'status':actual.get('status'),'url':actual.get('pc_detail_url',''),'scope':'按ID完整product.get正式字段；审核与公开验收分开'}
            listing['local_sync']={**listing.get('local_sync',{}),'state':'FORMAL_SNAPSHOT_SAVED_BUYER_COPY_'+state,'current_fields_file':rel(formal),'next_action':listing['optimization']['buyer_copy']['next_action']}
        for e in evidence:
            if e not in product['evidence']:product['evidence'].append(e)
    data['updated_on']=now[:10]
    # Check freshly loaded input has not changed while preparing the update.
    assert REGISTRY.read_bytes()==original,'Registry changed during sync; rerun from fresh input'
    REGISTRY.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    sp=importlib.util.spec_from_file_location('dossiers',ROOT/'08_工具链/06_工作区维护/product_dossiers.py');module=importlib.util.module_from_spec(sp);sp.loader.exec_module(module)
    selected={**data,'products':[x for x in data['products'] if x['id'] in touched],'listings':[x for x in data['listings'] if x['product_id'] in touched]}
    generated=module.builds(selected)
    for relpath,content in generated.items():
        path=ROOT/relpath;path.parent.mkdir(parents=True,exist_ok=True)
        text=content.decode('utf8')
        # One shared formatter preserves both field stages without duplicated
        # independent sections when copy and factory updates regenerate a page.
        from field_stage_navigation import annotate
        path.write_bytes(annotate(text,selected,relpath,ROOT))
    prior_sync=json.loads((BASE/'双改同步.json').read_text(encoding='utf8')) if (BASE/'双改同步.json').exists() else {}
    prior_states=prior_sync.get('states',{})
    proof={'at':now,'scope_ids':sorted(set(prior_sync.get('scope_ids',[])+ids)),'synced_ids':sorted(set(prior_sync.get('synced_ids',[])+list(states))),'states':{**prior_states,**states},'touched_dossiers':sorted(set(prior_sync.get('touched_dossiers',[]))|touched),'registry_before_sha256':hashlib.sha256(original).hexdigest(),'no_platform_writes':True}
    (BASE/'双改同步.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('BUYER_COPY_LOCAL_SYNC',len(states),len(touched))

if __name__=='__main__':main()
