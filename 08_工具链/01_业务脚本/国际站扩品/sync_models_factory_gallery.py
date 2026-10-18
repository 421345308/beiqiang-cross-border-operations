"""Local-only current record/source synchronization for the exact frozen migration.
No API calls, image generation, original-pack changes or inferred platform passes.
"""
from pathlib import Path
from collections import Counter
from urllib.parse import urlsplit
from copy import deepcopy
import json,sys,re
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(Path(__file__).parent))
import normalize_models_factory_gallery as n
sys.path.insert(0,str(ROOT/'08_工具链/06_工作区维护'))
import build_product_workspace as views
def main():
 sys.stdout.reconfigure(encoding='utf8');plan=n.load(n.BASE/'范围.json');r=n.load(n.REG);baseline=set(views.validate(r));sources={s['id']:s for s in r['sources']};products={p['id']:p for p in r['products']};links={l['id']:l for l in r['listings']};cache_path=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前素材清单.json';cache=n.load(cache_path)
 assert n.sha(ROOT/n.ASSET)==n.ASSET_SHA
 bank=n.load(n.ENTRY/'共用主图图片银行.json');counts=Counter();model_counts=Counter();changed_plans={};proofs=[];at=n.now()
 # Classification is independent of renaming and limited to evidenced routes.
 for p in r['products']:
  src=sources.get(p.get('adopted_source_id'));raw=p.get('raw_packages',[]);mode=None;evidence=[]
  if p['source_state']=='RAW_PACKAGE'and raw and all((ROOT/f).exists()for f in raw):mode='OWN_FACTORY';evidence=raw
  elif src and p['source_state']=='ADOPTED'and urlsplit(src.get('url','')).hostname not in ('bqgcd.sooxie.com',None):mode='EXTERNAL_FACTORY';evidence=src.get('evidence',[])
  if mode:p['supply_mode']={'current':mode,'state':'SOURCE_ROUTE_EVIDENCED','at':at,'evidence':evidence,'conversion_policy':'一定数量可评估转自产；意向不等于已转产，确认实际转产后保留货号并更新证据及适用订单/版本。','scope':'内部采购与履约分类，不改买家承诺或推断实物库存。'}
 for z in plan['targets']:
  pid=z['id'];f=n.BASE/'商品'/pid;p=products[z['product_key']];l=links[pid];v=n.load(f/'verification.json')if(f/'verification.json').exists()else{};prep=n.load(f/'prepared.json')if(f/'prepared.json').exists()else{};once=n.load(f/'update_once.json')if(f/'update_once.json').exists()else{}
  state=v.get('state')or('SUBMITTED_PENDING_FORMAL_VERIFY'if once else'PREPARED_NOT_SUBMITTED'if prep else'FROZEN_NOT_PREPARED');counts[state]+=1
  if z['model_change']:model_counts[state]+=1
  # A later authorized performance disposition supersedes this historical
  # migration snapshot. Never restore an older title or visibility locally.
  newer=l.get('optimization',{}).get('product_performance_review',{})
  if newer.get('at','')>v.get('at',''):continue
  refs=[n.rel(path)for path in [f/'prepared.json',f/'manifest.json',f/'update_once.json',f/'update_receipt.json',f/'verification.json']if path.exists()]
  opt={'state':state,'at':v.get('at')or at,'old_model':z['old_model'],'planned_model':z['new_model'],'actual_score':v.get('actual_score'),'gallery_slot':z['gallery_slot'],'factory_asset_sha256':n.ASSET_SHA,'evidence':refs,'public_qa':'未逐商品浏览器实测；按负责人API闭环范围执行','next_action':'当前正式字段/实际评分通过，来源与本地同步'if state=='FORMAL_FIELDS_SCORE_PASS'else'目标货号和工厂图已回读，当前平台退回；get/list未返回具体原因，需正常后台明确原因后针对性处理，禁止盲目重投。'if state=='PLATFORM_REJECTED_TARGET_VALUES_RETURNED'else'只按原ID继续回读；已有写入账本不重放'}
  if v.get('sku_reissue_mapping'):
   reissued=n.verified_sku_reissue(pid);assert reissued
   opt['sku_reissue_mapping']=v['sku_reissue_mapping'];opt['original_platform_SKU_ids_preserved']=reissued['original_platform_SKU_ids_preserved'];opt['reissued_SKU_count']=len(reissued['items'])
  l.setdefault('optimization',{})['model_factory_normalization']=opt
  if once:l['local_sync']={'state':'PENDING_PLATFORM_VERIFY','current_fields_file':l.get('formal_fields',{}).get('file'),'pending_scope':refs,'at':at}
  if not(f/'after_get.json').exists():continue
  got=n.load(f/'after_get.json');actual=got.get('product')
  if not actual:continue
  observed=v.get('at')or at;n.save(n.CURRENT/pid/'formal_get.json',{'observed_at_utc':observed,'requested_product_id':pid,'response':got,'scope':'Current exact-ID official readback. Review/display and target checks are recorded independently.'})
  rendered=f/'after_render.json'
  if rendered.exists()and n.load(rendered).get('data'):n.save(n.CURRENT/pid/'formal_render.json',{'observed_at_utc':observed,'requested_product_id':pid,'response':n.load(rendered)})
  l['observation'].update(audit=actual['status'],display=actual['display'],at=observed,scope='本轮货号与共用工厂主图精确ID正式回读；公开页未逐项实测')
  l['current_platform_fields']={'at':observed,'model':n.b.model(actual),'title':actual['subject'],'keywords':actual.get('keywords',[]),'main_images':actual['main_image']['images'],'category_id':actual['category_id'],'display':actual['display'],'status':actual['status'],'url':actual.get('pc_detail_url'),'scope':'Current exact-ID official get; scoped target acceptance kept separately'}
  l['formal_fields']={'file':n.rel(n.CURRENT/pid/'formal_get.json'),'at':observed,'scope':'完整正式回读；不冒充公开呈现或来源真实性'}
  # Record the exact returned model even while a separate quality follow-up is
  # under review; this is a field observation, never overall acceptance.
  checks=v.get('checks')or v.get('readback_checks')or{}
  fields_pass=bool(checks)and all(checks.values())
  if n.b.model(actual)!=z['new_model']:continue
  l['model']=z['new_model'];l['catalog_fields']=deepcopy(l['current_platform_fields']);l['url']=actual.get('pc_detail_url')or l.get('url');l['catalog_presence']='OBSERVED'
  if z['model_change']:
   l['legacy_model_aliases']=list(dict.fromkeys([*l.get('legacy_model_aliases',[]),z['old_model']]))
   fam=re.match(r'^BQ1\d{3}',z['new_model'])[0]
   if p['id'].startswith('HR'):p['current_model']=fam;p['aliases']=list(dict.fromkeys([fam,*p['aliases']]))
   elif fam not in p['aliases']:p['aliases'].append(fam)
   facts=p.get('local_assets',{}).get('current_fields_file')
   if facts and facts.endswith('事实与页面计划.json')and(ROOT/facts).exists():
    fp=ROOT/facts;doc=changed_plans.setdefault(fp,n.load(fp));doc.setdefault('current_models_by_id',{})[pid]=z['new_model'];doc['model_migration_evidence']=n.rel(n.BASE/'范围.json')
    for variant,value in doc.get('target_ids',{}).items():
     if str(value)==pid:doc.setdefault('model_numbers',{})[variant]=z['new_model']
  if not fields_pass:continue
  ims=actual['main_image']['images'];u=ims[z['gallery_slot']-1];assert n.pub.image_key(u)==n.pub.image_key(bank['url'])
  for url in [u,bank['url']]:cache['assets'][url]={'state':'SAVED','file':n.ASSET,'sha256':n.ASSET_SHA,'bytes':(ROOT/n.ASSET).stat().st_size,'width':1254,'height':1254,'bank_file_id':bank['file_id'],'bank_evidence':n.rel(n.ENTRY/'共用主图公开映射.json')}
  cache['products'].setdefault(pid,{})['main']=ims
  mapping={'id':pid,'model':z['new_model'],'at':observed,'state':'CURRENT_FORMAL_GALLERY_VERIFIED','main':[{'slot':i+1,'url':url,**({k:cache['assets'][url][k]for k in ('file','sha256','width','height')}if url in cache['assets']else{})}for i,url in enumerate(ims)],'changed_slot':z['gallery_slot'],'source_id_unchanged':z['source_id'],'sku_codes_changed':prep.get('sku_code_changes',{}),'verification':n.rel(f/'verification.json')}
  if v.get('sku_reissue_mapping'):mapping.update(sku_reissue_mapping=v['sku_reissue_mapping'],original_platform_SKU_ids_preserved=False)
  n.save(f/'当前图库与货号.json',mapping);p.setdefault('local_assets',{}).setdefault('current_gallery_by_id',{})[pid]=n.rel(f/'当前图库与货号.json')
  l['local_sync']={'state':'MODEL_FACTORY_GALLERY_DOUBLE_SYNC_PASS'if state=='FORMAL_FIELDS_SCORE_PASS'else'CURRENT_API_VALUES_SYNCED_ACCEPTANCE_PENDING','current_fields_file':n.rel(n.CURRENT/pid/'formal_get.json'),'current_schema_file':n.rel(n.CURRENT/pid/'formal_render.json')if rendered.exists()and n.load(rendered).get('data')else None,'current_gallery':n.rel(f/'当前图库与货号.json'),'at':observed}
  proof={'id':pid,'state':l['local_sync']['state'],'at':at,'checks':{'listing_model_formal':l['model']==n.b.model(actual),'source_binding_unchanged':l.get('bound_source_id')==z['source_id'],'product_key_unchanged':l['product_id']==z['product_key'],'factory_bank_sha_match':cache['assets'][u]['sha256']==n.ASSET_SHA,'sku_ids_and_non_target_fields':all(checks.values())},'verification':n.rel(f/'verification.json')};n.save(f/'双改核验.json',proof);proofs.append(proof)
 for p in r['products']:
  bound=[l for l in r['listings']if l['product_id']==p['id']and l['id']in{z['id']for z in plan['targets']}]
  if not bound:continue
  later_performance=any(l.get('optimization',{}).get('product_performance_review',{}).get('at','')>l.get('optimization',{}).get('model_factory_normalization',{}).get('at','')for l in bound)
  if p.get('current_model')and p['id'].startswith('HR')and not later_performance:
   rejected=[l['id']for l in bound if l.get('optimization',{}).get('model_factory_normalization',{}).get('state')=='PLATFORM_REJECTED_TARGET_VALUES_RETURNED']
   p['next_action']='当前BQ货号、统一工厂图及货源已同步；'+('原ID '+', '.join(rejected)+' 当前平台退回，目标值已返回；取得具体审核原因后针对性修复，不盲目重投。'if rejected else'维持已核实的实鞋与来源，按订单核采购条件；不重复换款或恢复旧HR编号。')
  categories=sorted({int(l['current_platform_fields']['category_id'])for l in bound if l.get('current_platform_fields',{}).get('category_id')})
  if categories:p.setdefault('classification',{})['platform_category_ids']=categories
  facts=p.get('local_assets',{}).get('current_fields_file')
  if facts and facts.endswith('事实与页面计划.json')and(ROOT/facts).exists():
   fp=ROOT/facts;doc=changed_plans.setdefault(fp,n.load(fp));doc['current_platform_category_by_id']={l['id']:int(l['current_platform_fields']['category_id'])for l in bound if l.get('current_platform_fields',{}).get('category_id')};doc['category_scope']='category_id保留初始改造默认；当前平台叶子按current_platform_category_by_id逐ID读取，不把同源链接不同平台分类混成不同实鞋。'
 for fp,doc in changed_plans.items():n.save(fp,doc)
 for work in r.get('workstreams',[]):
  if work['name']=='路崎宽头/户外全分类':work['next_action']='原107来源均有明确处置，2520由负责人排除不发布。本期货号与工厂图结果见HR实源替换当前入口，不重建既有商品。'
  if work['name']=='HR缺货源实款替换'and not r.get('product_performance_review'):
   work['status']='实源替换完成后已进入稳定BQ货号和共用工厂主图维护；当前状态按唯一执行入口逐ID读取。';work['next_action']='175条当前HR型号已改BQ、483条F1已回读并双改；BQ1030-A/B当前退回原因待后台明确，其余481条正式及5.00通过，不重复换款或重投。';work['evidence']=list(dict.fromkeys([n.rel(n.BASE/'当前状态.json'),*work['evidence']]))
 errors=set(views.validate(r));assert errors<=baseline,sorted(errors-baseline)
 r['updated_on']='2026-10-16';r['model_factory_normalization']={'at':at,'scope':n.rel(n.BASE/'范围.json'),'status':dict(counts),'models':dict(model_counts),'double_sync_ids':len(proofs),'factory_asset':n.rel(n.ENTRY/'共用主图.json'),'owner_skipped_source':'2520，保留标识未核证据，不再推进，不发布。'};n.save(n.REG,r)
 cache['urls']=len(cache['assets']);cache['saved_urls']=sum(x.get('state')=='SAVED'for x in cache['assets'].values());cache['unique_files']=len({x.get('sha256')for x in cache['assets'].values()if x.get('sha256')});n.save(cache_path,cache)
 for path,body in views.build(r).items():views.write_generated(ROOT/path,body)
 summary={'at':at,'targets':len(plan['targets']),'states':dict(counts),'model_states':dict(model_counts),'double_sync_ids':len(proofs),'excluded':plan['excluded'],'checks':{'no_new_registry_errors':True,'all_local_proofs_pass':all(all(p['checks'].values())for p in proofs)},'baseline_validation_issues':sorted(baseline),'public_qa':'未逐商品浏览器实测'};n.save(n.BASE/'当前状态.json',summary)
 shared=n.load(n.ENTRY/'共用主图.json');shared['live_state']='ALL_ACTIVE_TARGETS_FORMAL_PASS'if counts.get('FORMAL_FIELDS_SCORE_PASS')==len(plan['targets'])else'ALL_TARGET_IMAGES_RETURNED_TWO_PLATFORM_REJECTIONS'if counts.get('FORMAL_FIELDS_SCORE_PASS',0)+counts.get('PLATFORM_REJECTED_TARGET_VALUES_RETURNED',0)==len(plan['targets'])else'FORMAL_FIRST_TARGETS_PASS_ROLLOUT_IN_PROGRESS'if counts.get('FORMAL_FIELDS_SCORE_PASS')else'BANK_UPLOADED_TARGET_BINDING_PENDING';shared['current_execution']=n.rel(n.BASE/'当前状态.json');shared['formal_pass_ids']=counts.get('FORMAL_FIELDS_SCORE_PASS',0);shared['platform_rejected_with_target_values_returned']=counts.get('PLATFORM_REJECTED_TARGET_VALUES_RETURNED',0);n.save(n.ENTRY/'共用主图.json',shared)
 # Owner-accepted omission is a final source disposition, not permission blockage.
 luqi=ROOT/'02_Alibaba运营/05_扩品工程/执行记录/路崎宽头户外_2026-10-08';issues=n.load(luqi/'待补资料与局部问题.json');held=issues.get('active',{}).pop('2520',None)
 if held:issues.setdefault('owner_excluded',{})['2520']={**held,'state':'OWNER_EXCLUDED_NOT_PUBLISHED','at':at,'decision':'2026-10-16负责人：那就不用做吧；不继续核标识或上架。'}
 n.save(luqi/'待补资料与局部问题.json',issues)
 print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
