"""Synchronize approved company-bundle results with the unique registry/dossiers.
No platform writes; no source facts or product-specific highlights are changed.
"""
from pathlib import Path
import argparse, copy, importlib.util, json, sys, tempfile, os
sys.path.insert(0,str(Path(__file__).resolve().parent))
import replace_company_bundle as op
sys.path.insert(0,str(op.ROOT/'08_工具链/01_业务脚本/国际站扩品'))
from field_stage_navigation import annotate
REG=op.ROOT/'02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json'
DETAILS=op.ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--ids');a=ap.parse_args()
    scope=op.load(op.PHASE/'scope.json');ids=a.ids.split(',')if a.ids else scope['eligible_ids']
    raw=REG.read_bytes();data=json.loads(raw);ls={x['id']:x for x in data['listings']};ps={x['id']:x for x in data['products']}
    source=copy.deepcopy(data['sources']);source_states={x['id']:x['source_state']for x in data['products']};touched=set();states={}
    rel=lambda p:p.relative_to(op.ROOT).as_posix()
    for pid in ids:
        f=op.folder(pid)
        ledger=op.ledger_file(pid)
        if not ledger.exists():continue
        assert pid in scope['eligible_ids']and pid not in scope['excluded_ids']
        listing=ls[pid];product=ps[listing['product_id']];touched.add(product['id'])
        receipt=op.load(ledger);v=op.load(f/'verification.json')if(f/'verification.json').exists()else{}
        if v.get('at','')<receipt.get('at',''):v={}
        public=op.load(f/'public_verification.json')if(f/'public_verification.json').exists()else{}
        state=v.get('status',receipt['status']);public_status=public.get('status',v.get('public_status','NOT_CHECKED'))
        complete=state=='FORMAL_PASS'and public_status in ('PUBLIC_SIX_IMAGES_INTRO_FAQ_PASS','NOT_APPLICABLE_OFFLINE_DISPLAY_PRESERVED')
        evidence=[rel(p)for p in f.glob('*.json')if p.name not in ('submit_error.json','prepare_error.json')]
        stage={'asset_version':8,'at':v.get('at',receipt.get('at')),'state':state,'scope':['companyImage','companyDesc','companyFaqDesc'],'formal_binding_verified':state=='FORMAL_PASS','public_status':public_status,'evidence':evidence,'source_state_unchanged':True,'product_highlights_preserved':v.get('unsubmitted_fields_preserved'),'historical_source_and_highlights_deferred':pid in scope['historical_ids'],'completed_this_scope':complete,'next_action':'本轮六图、通用FAQ与公司简介已核；鞋款来源与其他问题按各自状态继续'if complete else'等待审核并核正式与公开结果；不重放未知写入'}
        opt=listing.setdefault('optimization',{});opt['company_bundle']=stage
        opt['factory_gallery']={**stage,'scope':['companyImage'],'company_target_verified':v.get('company_images_match',False),'scope_formal_accepted':state=='FORMAL_PASS'}
        # Earlier per-shoe FAQ reads remain historical; highlights retain their own acceptance.
        if 'buyer_copy'in opt:
            opt['buyer_copy']['current_faq_phase']=rel(op.PHASE/'当前替换.json')
            opt['buyer_copy']['faq_superseded_by_general_template']=state=='FORMAL_PASS'
            opt['buyer_copy']['faq_new_template_state']=state
        if v and(f/'after_get.json').exists():
            got=op.load(f/'after_get.json');p=got['product'];formal=DETAILS/pid/'formal_get.json'
            prior=op.load(formal)if formal.exists()else{}
            if v['at']>=prior.get('observed_at_utc',''):
                op.save(formal,{'requested_product_id':pid,'observed_at_utc':v['at'],'method':'alibaba.icbu.product.get','response':got})
                listing['formal_fields']={'file':rel(formal),'at':v['at'],'scope':'完整正式字段；公司六图、简介、通用FAQ单独验收'}
                listing['current_platform_fields']={**listing.get('current_platform_fields',{}),'at':v['at'],'title':p.get('subject',''),'keywords':p.get('keywords',[]),'main_images':p.get('main_image',{}).get('images',[]),'category_id':p.get('category_id'),'display':p.get('display'),'status':p.get('status'),'url':p.get('pc_detail_url',''),'scope':'同ID正式回读；与公开验收分开'}
                listing['local_sync']={**listing.get('local_sync',{}),'state':'COMPANY_BUNDLE_'+state,'current_fields_file':rel(formal),'next_action':stage['next_action']}
        for ref in evidence:
            if ref not in product['evidence']:product['evidence'].append(ref)
        states[pid]=state
    assert data['sources']==source and all(x['source_state']==source_states[x['id']]for x in data['products'])
    assert REG.read_bytes()==raw,'Registry changed during sync; start with fresh input'
    data['updated_on']=op.now()[:10];op.save(REG,data)
    spec=importlib.util.spec_from_file_location('dossiers',op.ROOT/'08_工具链/06_工作区维护/product_dossiers.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    selected={**data,'products':[x for x in data['products']if x['id']in touched],'listings':[x for x in data['listings']if x['product_id']in touched]}
    for path,content in m.builds(selected).items():
        target=op.ROOT/path;assert target.resolve().is_relative_to(op.ROOT.resolve())
        target.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent,prefix='.bundle-',suffix='.tmp',delete=False)as h:
            h.write(annotate(content,selected,path,op.ROOT));temporary=h.name
        os.replace(temporary,target)
    op.save(op.PHASE/'双改同步.json',{'at':op.now(),'asset_version':8,'synced_ids':sorted(states),'states':states,'touched_dossiers':sorted(touched),'source_states_unchanged':True,'no_platform_writes':True})
    print('COMPANY_BUNDLE_LOCAL_SYNC',len(states),len(touched))
if __name__=='__main__':main()
