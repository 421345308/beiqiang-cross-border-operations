from pathlib import Path
from datetime import datetime,timezone
import json,sys,copy,importlib.util
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'02_Alibaba运营/05_扩品工程/执行记录/HR实源替换';REG=ROOT/'02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json'
sys.path.insert(0,str(Path(__file__).parent));import replace_hr_real_sources as op
sys.path.insert(0,str(ROOT/'08_工具链/06_工作区维护'));import build_product_workspace as workspace
def rel(p):return p.relative_to(ROOT).as_posix()

def public_fields(value):
 if isinstance(value,dict):return {k:public_fields(v)for k,v in value.items()if k not in ('owner_member','owner_member_display_name','owner_member_id')}
 if isinstance(value,list):return [public_fields(v)for v in value]
 return value
def sync():
 d=json.loads(REG.read_text(encoding='utf8'));products={p['id']:p for p in d['products']};listings={p['id']:p for p in d['listings']};summary=[]
 for family,targets in op.TARGETS.items():
  plan=op.PLANS[family];raw=ROOT/op.RAW_PATHS[family];source=op.b.load(raw/'source.json');sid='src-hr-'+family.lower()+'-'+source['artno'].lower()
  existing=next((s for s in d['sources']if s['id']==sid),None)
  src={'id':sid,'url':source['url'],'shop_url':source['url'].split('/detail/')[0],'supplier':source['supplier'],'model':source['artno'],'price':f"{source['price_cny']:.2f}",'currency':'CNY','unit':'双','price_terms':'当前公开来源标价；拿货色码、数量、包装、运税与当日可供条件逐单确认，不代表已采购或固定交期。','observed_at':'2026-10-13','evidence':[rel(raw/'source.json'),rel(BASE/family/'素材清单.json')]}
  if existing:existing.update(src)
  else:d['sources'].append(src)
  states=[]
  for variant,pid in targets.items():
   f=BASE/'商品'/pid;v=op.b.load(f/'verification.json')if(f/'verification.json').exists()else {'state':'SUBMITTED'};state=v['state'];states.append(state)
   l=listings[pid];opt=l.setdefault('optimization',{});evidence=[rel(f/name)for name in ['prepared.json','update_once.json','update_receipt.json','verification.json','after_get.json','after_render.json','score.json']if(f/name).exists()]
   opt['source_replacement']={'state':state,'source_id':sid,'real_artno':source['artno'],'at':op.b.now(),'next_action':'逐ID完成材料/SKU/价格/图库/详情正式回读及实际评分，再作公开页验收。'if state!='FORMAL_FIELDS_SCORE_PASS'else'正式字段和评分通过；正常买家公开页与旧关键词迁移逐ID待验，其他HR款继续实源重建。','evidence':evidence}
   public_file=f/'public_product_verification.json'
   if public_file.exists():
    public=op.b.load(public_file)
    assert public['id']==pid
    opt['source_replacement']['public_product_qa']={'state':public['state'],'at':public['at'],'file':rel(public_file),'scope':'实际六主图、四产品详情、末端颜色EU尺码选择；旧keywords迁移未由此证明'}
    if state=='FORMAL_FIELDS_SCORE_PASS' and public['state']=='PUBLIC_PRODUCT_IMAGE_SKU_PASS':opt['source_replacement']['next_action']='正式字段、实际5.00及公开六主图四详情/EU末端组合通过；旧keywords空值和UI迁移独立待核，继续其他HR实源替换。'
   if state=='FORMAL_FIELDS_SCORE_PASS':
    l['bound_source_id']=sid;l['source_relation']='SAME_ID_REAL_SOURCE_REPLACEMENT_FORMAL_PASS'
    got=op.b.load(f/'after_get.json');p=got['product'];canonical=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'/pid
    canonical.mkdir(parents=True,exist_ok=True);op.b.save(canonical/'formal_get.json',{'requested_product_id':pid,'observed_at_utc':v.get('get_observed_at',v['at']),'method':'alibaba.icbu.product.get','response':public_fields(got),'sanitized_fields':['owner_member','owner_member_display_name','owner_member_id'],'raw_response_file':rel(f/'after_get.json')});op.b.save(canonical/'formal_render.json',op.b.load(f/'after_render.json'))
    l['observation']={'audit':p['status'],'display':p['display'],'at':v['at'],'scope':'Exact-ID current formal product and rendered schema'}
    current={'at':v.get('get_observed_at',v['at']),'title':p['subject'],'keywords':p.get('keywords',[]),'main_images':p['main_image']['images'],'category_id':p['category_id'],'display':p['display'],'status':p['status'],'url':p.get('pc_detail_url')or l['url'],'scope':'Exact-ID whole-shoe replacement formal get; public presentation and legacy keyword migration tracked separately'}
    l['current_platform_fields']=current;l['catalog_fields']={**l.get('catalog_fields',{}),**current};l['formal_fields']={'file':rel(canonical/'formal_get.json'),'at':current['at'],'scope':'完整商品正式字段；本轮实源换款逐ID字段/5.00评分通过，公开与旧关键词迁移证据分列'};l['url']=current['url']
    l['local_sync']={'state':'HR_REAL_SOURCE_FORMAL_PASS','current_fields_file':rel(canonical/'formal_get.json'),'current_schema_file':rel(canonical/'formal_render.json'),'at':v['at']}
   else:l['source_relation']='REAL_SOURCE_CANDIDATE_REPLACEMENT_PENDING_FORMAL_READ'
   summary.append({'family':family,'model':family+'-'+variant,'id':pid,'state':state})
  p=products[family];p['candidate_source_ids']=list(dict.fromkeys([*p.get('candidate_source_ids',[]),sid]));p['local_assets']['current_fields_file']=rel(BASE/family/'事实与页面计划.json');p['local_assets']['state']='REAL_SOURCE_PLAN_SUBMITTED';p['local_assets']['asset_roots']=[f'01_产品资产/02_可发布素材/{family}'];p['raw_packages']=[rel(raw)]
  p['next_action']='实源图文已提交原ID，待完整正式核验；公开呈现分开登记。'
  p['source_state']='CANDIDATE'
  p['classification'].update(state='REAL_SKU_SOURCE_PHOTO_REVIEWED',local_intent_candidates=plan.get('local_intent_candidates',['厚底/时尚帆布休闲鞋'if family=='HR030'else'镂空套脚/夏季休闲乐福鞋']))
  if all(s=='FORMAL_FIELDS_SCORE_PASS'for s in states):p.update(source_state='ADOPTED',adopted_source_id=sid,next_action='实款来源、正式字段及5.00评分已核；公开呈现和旧关键词迁移逐ID核验分开待验；其余缺源HR继续。');p['local_assets']['state']='REAL_SOURCE_FORMAL_PASS'
  for name in ['素材清单.json','事实与页面计划.json','当前状态.json']:
   ref=rel(BASE/family/name)
   if ref not in p['evidence']:p['evidence'].append(ref)
  op.b.save(BASE/family/'事实与页面计划.json',{**plan,'source_id':sid,'source_artno':source['artno'],'source_assets_root':rel(raw),'source_evidence':src['evidence'],'procurement_capability':'CURRENT_REAL_SHOE_AND_PROCUREMENT_ENTRY_VERIFIED_NOT_ORDER_STOCK','materials_evidence':plan.get('materials_evidence',[rel(raw/'09.jpg'),rel(raw/'13.jpg')]if family=='HR030'else[source['url']]),'seasons':plan['seasons'],'feature':plan.get('feature','Fashion Trend'),'target_ids':targets,'page_state':'FORMAL_FIELDS_SCORE_PASS'if all(s=='FORMAL_FIELDS_SCORE_PASS'for s in states)else'REVIEW_PENDING','company_faq_source':'02_Alibaba运营/02_单品优化记录/全店FAQ与产品亮点优化/通用FAQ与公司简介.json','do_not_claim':['physical stock','tested slip resistance','medical comfort','unverified midsole material']})
  op.b.save(BASE/family/'当前状态.json',{'at':op.b.now(),'family':family,'links':[r for r in summary if r['family']==family],'old_concept_images':'NOT_INCLUDED_IN_SUBMITTED_PAYLOAD','public_qa':'PENDING_NORMAL_BUYER_PAGE','source_price':source['price_cny'],'source_currency':'CNY'})
 ws={'name':'HR缺货源实款替换','status':'HR030/HR042优先；原ID实款换图文按逐ID证据登记正式和公开状态。','next_action':'负责人2026-10-13要求先完成HR缺货源商品全量实源替换，再继续路崎宽头鞋上架；已具备真实来源的页面先核实际绑定，不重复换款。','evidence':[rel(BASE/'README.md'),rel(BASE/'当前进度.json')]}
 old=next((w for w in d['workstreams']if w['name']==ws['name']),None)
 if old:old.update(ws)
 else:d['workstreams'].append(ws)
 d['updated_on']='2026-10-13';op.b.save(REG,d)
 remaining=[p['id']for p in d['products']if p['id'].startswith('HR')and p['source_state']in ['MISSING','CANDIDATE','CONFLICT']and p['id']not in op.TARGETS]
 progress_file=BASE/'当前进度.json'
 previous=op.b.load(progress_file)if progress_file.exists()else{}
 op.b.save(progress_file,{**previous,'at':op.b.now(),'priority_links':summary,'other_hr_families_needing_per_family_source_binding_review':remaining,'scope':'Registry source states require link-by-link evidence review; candidates are not automatically missing shoes.','hr030_c':'1601943529885 current official product.get returned only request/trace and no product; no new listing created.'})
 errors=workspace.validate(d);assert not errors,errors
 generated=workspace.build(d)
 for path,raw in generated.items():workspace.write_generated(ROOT/path,raw)
 print('LOCAL_DOUBLE_SYNC',len(summary),'priority links; remaining HR families to review',len(remaining))
if __name__=='__main__':sync()
