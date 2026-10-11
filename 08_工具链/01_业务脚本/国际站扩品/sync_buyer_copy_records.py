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
        public_pass=verification['public_status']=='PUBLIC_TRANSLATED_TEXT_SEMANTIC_PASS'
        next_action='审核后核对应公开亮点FAQ；不重放已有提交' if state=='PENDING_REVIEW' else '本轮亮点FAQ正式字段与当前中文公开正文已核；其他字段未纳入本次验收' if public_pass else '核对应公开亮点FAQ；其他商品字段未纳入本次修改'
        listing.setdefault('optimization',{})['buyer_copy']={'state':state,'at':verification['observed_at'],'scope':['textDesc','companyFaqDesc'],'draft':rel(f/'copy.json'),'formal_readback':rel(f/'after_get.json'),'public_status':verification['public_status'],'evidence':evidence,'next_action':next_action}
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
        # Include this field-level stage in the existing generated dossier navigation.
        entries=[]
        for listing in selected['listings']:
            if listing['product_id']==relpath.parent.name and listing.get('optimization',{}).get('buyer_copy'):
                cp=listing['optimization']['buyer_copy'];entries.append(f"- {listing['id']}：{cp['state']}；{cp['next_action']}。改稿与正式回读见下方按ID证据。")
        if entries:text=text.replace('## 其他原始/正式证据','## 本轮亮点与 FAQ\n\n'+'\n'.join(entries)+'\n\n## 其他原始/正式证据')
        path.write_text(text,encoding='utf8')
    prior_sync=json.loads((BASE/'双改同步.json').read_text(encoding='utf8')) if (BASE/'双改同步.json').exists() else {}
    prior_states=prior_sync.get('states',{})
    proof={'at':now,'scope_ids':sorted(set(prior_sync.get('scope_ids',[])+ids)),'synced_ids':sorted(set(prior_sync.get('synced_ids',[])+list(states))),'states':{**prior_states,**states},'touched_dossiers':sorted(set(prior_sync.get('touched_dossiers',[]))|touched),'registry_before_sha256':hashlib.sha256(original).hexdigest(),'no_platform_writes':True}
    (BASE/'双改同步.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('BUYER_COPY_LOCAL_SYNC',len(states),len(touched))

if __name__=='__main__':main()
