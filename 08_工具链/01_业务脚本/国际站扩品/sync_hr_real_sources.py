from pathlib import Path
from datetime import datetime,timezone,timedelta
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
 current=BASE/'货号与共用主图'
 if(current/'范围.json').exists()and any((current/'商品'/pid/'update_once.json').exists()for targets in op.TARGETS.values()for pid in targets.values()):
  import sync_models_factory_gallery as latest;latest.main();return
 d=json.loads(REG.read_text(encoding='utf8'));products={p['id']:p for p in d['products']};listings={p['id']:p for p in d['listings']};summary=[]
 for family,targets in op.TARGETS.items():
  plan=op.PLANS[family];raw=ROOT/op.RAW_PATHS[family];source=op.b.load(raw/'source.json');sid=plan.get('registry_source_id','src-hr-'+family.lower()+'-'+source['artno'].lower())
  existing=next((s for s in d['sources']if s['id']==sid),None)
  if 'registry_source_id'in plan:
   assert existing and existing['url'].rstrip('/')==source['url'].rstrip('/')and existing['model']==source['artno'],'Existing source identity must match exact reviewed shoe'
  source_date=source.get('observed_on')
  if not source_date:
   source_date=datetime.fromisoformat(source['observed_at']).astimezone(timezone(timedelta(hours=8))).date().isoformat()
  src={'id':sid,'url':source['url'],'shop_url':source['url'].split('/detail/')[0],'supplier':source['supplier'],'model':source['artno'],'price':f"{source['price_cny']:.2f}",'currency':'CNY','unit':'双','price_terms':'当前公开来源标价；拿货色码、数量、包装、运税与当日可供条件逐单确认，不代表已采购或固定交期。','observed_at':source_date,'evidence':[rel(raw/'source.json'),rel(BASE/family/'素材清单.json')]}
  if existing:existing.update(src)
  else:d['sources'].append(src)
  states=[]
  for variant,pid in targets.items():
   f=BASE/'商品'/pid;v=op.b.load(f/'verification.json')if(f/'verification.json').exists()else {'state':'SUBMITTED'if(f/'update_once.json').exists()else'LOCAL_DRAFT'};state=v['state'];states.append(state)
   l=listings[pid];opt=l.setdefault('optimization',{});evidence=[rel(f/name)for name in ['prepared.json','update_once.json','update_receipt.json','verification.json','after_get.json','after_render.json','score.json']if(f/name).exists()]
   opt['source_replacement']={'state':state,'source_id':sid,'real_artno':source['artno'],'at':op.b.now(),'next_action':'仅回读审核状态，审核通过后核材料/SKU/价格/图文与实际评分；不得重复提交。'if state!='FORMAL_FIELDS_SCORE_PASS'else'本轮API验收及货源双改完成；旧keywords空值照实保留，公开抽检在全量完成后统一进行，继续其他HR款。','evidence':evidence}
   public_file=f/'public_product_verification.json'
   if public_file.exists():
    public=op.b.load(public_file)
    assert public['id']==pid
    opt['source_replacement']['public_product_qa']={'state':public['state'],'at':public['at'],'file':rel(public_file),'scope':'实际六主图、四产品详情、末端颜色EU尺码选择；旧keywords迁移未由此证明'}
    if state=='FORMAL_FIELDS_SCORE_PASS' and public['state']=='PUBLIC_PRODUCT_IMAGE_SKU_PASS':opt['source_replacement']['next_action']='API验收、货源双改及既有公开图文/EU组合核验通过；旧keywords空值照实记录，继续其他HR款。'
   if state in ['FORMAL_FIELDS_SCORE_PASS','FORMAL_FIELDS_PASS_PENDING_SCORE']:
    l['bound_source_id']=sid;l['source_relation']='SAME_ID_REAL_SOURCE_REPLACEMENT_FORMAL_PASS'
    l['record_type']='当前实款正式绑定';l['notes']=f"当前采用{source['supplier']} {source['artno']}，原ID整鞋替换正式字段及评分通过；旧候选、旧鞋型和旧采购价不参与当前执行。来源、当前图文和逐ID证据见本款唯一入口；已提交动作不重放。"
    got=op.b.load(f/'after_get.json');p=got['product'];canonical=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'/pid
    canonical.mkdir(parents=True,exist_ok=True);op.b.save(canonical/'formal_get.json',{'requested_product_id':pid,'observed_at_utc':v.get('get_observed_at',v['at']),'method':'alibaba.icbu.product.get','response':public_fields(got),'sanitized_fields':['owner_member','owner_member_display_name','owner_member_id'],'raw_response_file':rel(f/'after_get.json')});op.b.save(canonical/'formal_render.json',op.b.load(f/'after_render.json'))
    l['observation']={'audit':p['status'],'display':p['display'],'at':v['at'],'scope':'Exact-ID current formal product and rendered schema'}
    current={'at':v.get('get_observed_at',v['at']),'title':p['subject'],'keywords':p.get('keywords',[]),'main_images':p['main_image']['images'],'category_id':p['category_id'],'display':p['display'],'status':p['status'],'url':p.get('pc_detail_url')or l['url'],'scope':'Exact-ID whole-shoe replacement formal get; public presentation and legacy keyword migration tracked separately'}
    l['current_platform_fields']=current;l['catalog_fields']={**l.get('catalog_fields',{}),**current};l['formal_fields']={'file':rel(canonical/'formal_get.json'),'at':current['at'],'scope':'完整商品正式字段；本轮实源换款逐ID字段/5.00评分通过，公开与旧关键词迁移证据分列'};l['url']=current['url']
    l['local_sync']={'state':'HR_REAL_SOURCE_FORMAL_PASS','current_fields_file':rel(canonical/'formal_get.json'),'current_schema_file':rel(canonical/'formal_render.json'),'at':v['at']}
    if state=='FORMAL_FIELDS_PASS_PENDING_SCORE':
     l.update(source_relation='REAL_SOURCE_FORMAL_FIELDS_PASS_PENDING_SCORE',record_type='当前实款正式绑定（最新评分待回读）',notes=f"当前正式实鞋为{source['supplier']} {source['artno']}，全部图文/材料/EU/SKU/交易字段已核并双改；最新评分API未返回，不能报整体完成，不重新换款或重放更新。")
     l['formal_fields']['scope']='完整正式字段已核并同步；最新实际评分待回读，不声称5.00或整体完成'
     l['local_sync']['state']='HR_REAL_SOURCE_FIELDS_PASS_PENDING_SCORE'
     opt['source_replacement']['next_action']='仅回读最新实际评分；正式实鞋和本地来源已一致，不沿用旧评分，不重复换款。'
    if 'platform_group_id'in plan:
     assert str(p['group_id'])==str(plan['platform_group_id'])
     l['platform_group']={'id':str(p['group_id']),'name':plan['platform_group_name'],'evidence':rel(BASE/family/'目标店内分组回读.json'),'scope':'当前正式商品与已核官方店内分组；与本地采购分类分列'}
   else:l['source_relation']='REAL_SOURCE_CANDIDATE_REPLACEMENT_PENDING_FORMAL_READ'
   summary.append({'family':family,'model':op.model_number(family,variant),'id':pid,'state':state})
  p=products[family];p['candidate_source_ids']=[sid];p['local_assets']['current_fields_file']=rel(BASE/family/'事实与页面计划.json');p['local_assets']['state']='REAL_SOURCE_LOCAL_DRAFT'if all(s in ['LOCAL_DRAFT','LOCAL_PREPARATION']for s in states)else'REAL_SOURCE_PLAN_SUBMITTED';p['local_assets']['asset_roots']=[f'01_产品资产/02_可发布素材/{family}'];p['raw_packages']=[rel(raw)]
  p['next_action']='实源图文按逐ID阶段推进，未提交的保留本地草稿，已提交的只作完整正式回读；公开呈现分开登记。'
  p['source_state']='CANDIDATE'
  p['classification'].update(state='REAL_SKU_SOURCE_PHOTO_REVIEWED',local_intent_candidates=plan.get('local_intent_candidates',['厚底/时尚帆布休闲鞋'if family=='HR030'else'镂空套脚/夏季休闲乐福鞋']))
  if all(s=='FORMAL_FIELDS_SCORE_PASS'for s in states):
   p.update(source_state='ADOPTED',adopted_source_id=sid,next_action='当前来源、正式字段及实际评分已核并双改；本轮API验收完成，公开抽检全量后统一进行，继续其余HR。');p['local_assets']['state']='REAL_SOURCE_FORMAL_PASS'
   p['classification']['platform_category_ids']=sorted({listings[pid]['current_platform_fields']['category_id']for pid in targets.values()})
   if 'platform_group_id'in plan:p['classification'].update(store_groups=[{'id':str(plan['platform_group_id']),'name':plan['platform_group_name']}],store_group_state='FORMAL_PRODUCT_AND_GROUP_READBACK')
  elif all(s in ['FORMAL_FIELDS_SCORE_PASS','FORMAL_FIELDS_PASS_PENDING_SCORE']for s in states):
   p.update(source_state='ADOPTED',adopted_source_id=sid,next_action='当前真实来源及正式图文/SKU已核并双改；仅最新实际评分待回读，不沿用旧分、不重放、不重复搜源或换款。')
   p['local_assets']['state']='REAL_SOURCE_FIELDS_PASS_PENDING_SCORE'
   p['classification']['platform_category_ids']=sorted({listings[pid]['current_platform_fields']['category_id']for pid in targets.values()})
  retired=BASE/family/'候选取舍.json'
  if retired.exists():
   for candidate in op.b.load(retired)['retired_candidates']:
    old_sid='src-hr-'+family.lower()+'-'+candidate['source_artno'].lower()
    previous_source=next((s for s in d['sources']if s['id']==old_sid),None)
    if previous_source:
     previous_source['evidence']=[candidate['raw_package_retained']+'/source.json',candidate['archive_documents']+'/素材清单.json',rel(retired)]
     previous_source['source_role']='SUPERSEDED_UNSUBMITTED_CANDIDATE_ALL_EVIDENCE_RETAINED'
  for name in ['素材清单.json','事实与页面计划.json','当前状态.json']:
   ref=rel(BASE/family/name)
   if ref not in p['evidence']:p['evidence'].append(ref)
  if all(s=='FORMAL_FIELDS_SCORE_PASS'for s in states):
   for key in ['group_quality_review','title_quality_review']:
    if key in plan:plan[key].update(state='FORMAL_FIELDS_AND_ACTUAL_SCORE_PASS',observed_at=op.b.now())
  if any((BASE/'商品'/pid/'company_quality_once.json').exists()for pid in targets.values()):
   plan['company_bundle_review']={'state':'FORMAL_PASS'if all(s=='FORMAL_FIELDS_SCORE_PASS'for s in states)else'PENDING_FORMAL','evidence':[rel(BASE/'商品'/pid/'verification.json')for pid in targets.values()],'scope':'Approved V8 exact gallery roles, company intro and general eight FAQs verified separately from product highlights.'}
  page_state='FORMAL_FIELDS_SCORE_PASS'if all(s=='FORMAL_FIELDS_SCORE_PASS'for s in states)else'FORMAL_FIELDS_PASS_PENDING_SCORE'if all(s in ['FORMAL_FIELDS_SCORE_PASS','FORMAL_FIELDS_PASS_PENDING_SCORE']for s in states)else'AUDIT_REJECTED'if'AUDIT_REJECTED'in states else'LOCAL_DRAFT'if all(s in ['LOCAL_DRAFT','LOCAL_PREPARATION']for s in states)else'REVIEW_PENDING'
  op.b.save(BASE/family/'事实与页面计划.json',{**plan,'source_id':sid,'source_artno':source['artno'],'source_assets_root':rel(raw),'source_evidence':src['evidence'],'procurement_capability':'CURRENT_REAL_SHOE_AND_PROCUREMENT_ENTRY_VERIFIED_NOT_ORDER_STOCK','materials_evidence':plan.get('materials_evidence',[rel(raw/'09.jpg'),rel(raw/'13.jpg')]if family=='HR030'else[source['url']]),'seasons':plan['seasons'],'feature':plan.get('feature','Fashion Trend'),'target_ids':targets,'page_state':'FORMAL_FIELDS_SCORE_PASS'if all(s=='FORMAL_FIELDS_SCORE_PASS'for s in states)else'LOCAL_DRAFT'if all(s in ['LOCAL_DRAFT','LOCAL_PREPARATION']for s in states)else'REVIEW_PENDING','company_faq_source':'02_Alibaba运营/02_单品优化记录/全店FAQ与产品亮点优化/通用FAQ与公司简介.json','do_not_claim':list(dict.fromkeys([*plan.get('do_not_claim',[]),'physical stock','tested slip resistance','medical comfort','unverified midsole material']))})
  op.b.save(BASE/family/'当前状态.json',{'at':op.b.now(),'family':family,'links':[r for r in summary if r['family']==family],'old_concept_images':'NOT_INCLUDED_IN_SUBMITTED_PAYLOAD','public_qa':'PENDING_NORMAL_BUYER_PAGE','source_price':source['price_cny'],'source_currency':'CNY'})
  current_plan=op.b.load(BASE/family/'事实与页面计划.json');current_plan['page_state']=page_state;op.b.save(BASE/family/'事实与页面计划.json',current_plan)
 passed=sum(r['state']=='FORMAL_FIELDS_SCORE_PASS'for r in summary)
 ws={'name':'HR缺货源实款替换','status':f'本轮{len(summary)}条原ID目标，{passed}条完整正式字段与实际5.00通过；其余按逐ID真实状态登记。','next_action':'先完成HR缺货源商品全量实源替换，再继续路崎宽头鞋上架；审核中只回读，不重复提交；路崎资料准备可独立推进。已有实源页面保留实鞋，未返回历史ID不新建。','evidence':[rel(BASE/'README.md'),rel(BASE/'当前进度.json')]}
 old=next((w for w in d['workstreams']if w['name']==ws['name']),None)
 if old:old.update(ws)
 else:d['workstreams'].append(ws)
 d['updated_on']=datetime.now(timezone(timedelta(hours=8))).date().isoformat()
 unresolved=[p['id']for p in d['products']if p['id'].startswith('HR')and p['source_state']in ['MISSING','CANDIDATE','CONFLICT']and p['id']not in op.TARGETS]
 catalog=op.b.load(ROOT/'99_临时区/HR实源替换/全量目录复核/catalog.json')
 assert catalog['complete']and len(catalog['products'])==catalog['unique_ids']==catalog['total_item']
 live_ids={str(p['id'])for p in catalog['products']};remaining=[];unreturned=[]
 for family in unresolved:
  links=[l for l in d['listings']if l['product_id']==family]
  if any(l['id']in live_ids for l in links):remaining.append(family);continue
  proofs=[BASE/'商品'/l['id']/'historical_presence_get.json'for l in links]
  if not all(f.exists()and not op.b.load(f).get('product')for f in proofs):remaining.append(family);continue
  for l,f in zip(links,proofs):
   l.update(source_relation='HISTORICAL_NO_CURRENT_WRITABLE_PRODUCT_RETURNED',catalog_presence='NOT_OBSERVED',catalog_evidence=rel(ROOT/'99_临时区/HR实源替换/全量目录复核/catalog.json'))
   l['observation']={'audit':'当前完整目录未返回；精确product.get未返回商品对象','display':'','at':datetime.fromtimestamp(f.stat().st_mtime,timezone.utc).isoformat(),'scope':'不推断已删除；无可写商品对象，不创建重复替代ID'}
   if rel(f)not in l['evidence']:l['evidence'].append(rel(f))
  products[family]['next_action']='当前完整目录及精确product.get未返回可写商品；保留历史身份与缺来源状态，不新建重复ID。只有后续正式返回原ID时再核实源替换。'
  unreturned.append({'family':family,'ids':[l['id']for l in links],'state':'NO_CURRENT_WRITABLE_PRODUCT_RETURNED','evidence':[rel(f)for f in proofs]})
 progress_file=BASE/'当前进度.json'
 previous=op.b.load(progress_file)if progress_file.exists()else{}
 op.b.save(progress_file,{**previous,'at':op.b.now(),'priority_links':summary,'other_hr_families_needing_per_family_source_binding_review':remaining,'historical_unreturned_families':unreturned,'scope':'Current writable targets and unreturned historical IDs are separate; missing history is not claimed repaired or deleted.','hr030_c':'1601943529885 current official product.get returned only request/trace and no product; no new listing created.'})
 errors=workspace.validate(d);assert not errors,errors
 op.b.save(REG,d)
 generated=workspace.build(d)
 for path,raw in generated.items():workspace.write_generated(ROOT/path,raw)
 # A successful platform readback alone is not double-sync completion.
 # Check the source truth and all generated lookup entries before reporting it.
 import audit_hr_source_consistency
 audit_hr_source_consistency.main()
 print('LOCAL_DOUBLE_SYNC',len(summary),'priority links; remaining HR families to review',len(remaining))
if __name__=='__main__':sync()
