"""Synchronize exact-ID performance actions without altering source identities."""
from copy import deepcopy
from collections import Counter
from pathlib import Path
import sys
import apply_product_performance_actions as a
import diagnose_product_performance as d
sys.path.insert(0,str(d.ROOT/'08_工具链/06_工作区维护'))
import build_product_workspace as views

FOLDERS={'pause_duplicate':'重复弱链接下架','repair_custom_attribute':'退回属性修复','title_clarity':'标题识别优化'}
PASS={'FORMAL_OFFLINE_NON_TARGET_PASS','CUSTOM_PROPERTY_REPAIR_FORMAL_SCORE_PASS','TITLE_FORMAL_SCORE_PASS','TITLE_REVIEWED_VARIANT_FORMAL_SCORE_PASS'}

def main():
 sys.stdout.reconfigure(encoding='utf8');r=d.load(d.REG);baseline=set(views.validate(r));links={l['id']:l for l in r['listings']};products={p['id']:p for p in r['products']};sources={s['id']:s for s in r['sources']};states=Counter();proofs=[];at=a.now();source_docs={}
 for row in d.load(a.PLAN)['items']:
  pid=row['id'];folder=d.BASE/'商品'/pid/FOLDERS[row['kind']];vf=folder/'verification.json'
  if not vf.exists():continue
  v=d.load(vf);l=links[pid];product=products[l['product_id']];identity=(l['product_id'],l.get('bound_source_id'),product['source_state']);p=d.load(folder/'after_get.json')['product'];assert a.n.b.model(p)==row['model'];observed=v['at'];passed=v['state']in PASS;states[v['state']]+=1
  destination=a.n.CURRENT/pid;d.save(destination/'formal_get.json',{'observed_at_utc':observed,'requested_product_id':pid,'response':d.load(folder/'after_get.json'),'scope':'Exact-ID official get; current returned values, review state and scoped acceptance separate.'})
  render=folder/'after_render.json'
  if render.exists()and d.load(render).get('data'):d.save(destination/'formal_render.json',{'observed_at_utc':observed,'requested_product_id':pid,'response':d.load(render)})
  fields={'at':observed,'model':a.n.b.model(p),'title':p['subject'],'keywords':p.get('keywords',[]),'main_images':p['main_image']['images'],'category_id':p['category_id'],'display':p['display'],'status':p['status'],'url':p.get('pc_detail_url'),'scope':'Current official exact-ID get; no inferred public-page QA or physical inventory.'}
  l['current_platform_fields']=fields;l['catalog_fields']=deepcopy(fields);l['formal_fields']={'file':d.rel(destination/'formal_get.json'),'at':observed,'scope':'完整正式回读；审核中get可能仍为旧正式值，拟稿不冒充生效。'};l.setdefault('observation',{}).update(audit=p['status'],display=p['display'],at=observed,scope='商品表现处置精确ID回读');l['url']=p.get('pc_detail_url')or l.get('url')
  next_action=('重复弱链接已下架；保留同源有咨询入口 '+row['retained_id']+'，不重建弱链接。')if row['kind']=='pause_duplicate'and passed else'标题正式通过；按后续完整窗口复核搜索点击与实际采购咨询，不把字段通过当增长。'if row['kind']=='title_clarity'and passed else'不支持的自定义属性已清除且正式通过；保留现款与采购来源。'if passed else'平台审核中或目标尚未正式返回；只回读当前ID，不重投已确认请求。'
  if v['state']=='DISPLAY_RESTORED_CUSTOM_PROPERTY_STILL_PRESENT':next_action='已恢复approved/Y及5.00；原属性仍在，空complex清除未生效。正常编辑页持续加载，遗留删除待正常表单可用或官方明确删除语义后处理，不重复相同请求。'
  if v['state']=='CUSTOM_PROPERTY_DELETE_NOOP_PLATFORM_TBD':next_action='当前tbd/N；曾短暂approved/Y后再次退回，旧Shoe Profile仍在，空complex删除未生效。正常编辑页持续加载，待正常表单或官方明确删除契约处理，禁止重投无效请求。'
  if v['state']=='PLATFORM_IP_REJECTED_OWNER_CONFIRMED':next_action='负责人已明确平台因侵权退回；当前tbd/N，停止原款原图重提。核平台具体权利通知及真实商品标识/外观；自定义属性错误独立记录，不能当退回主因。'
  refs=[d.rel(x)for x in(folder/'prepared.json',folder/'manifest.json',folder/'receipt.json',vf)if x.exists()];l.setdefault('optimization',{})['product_performance_review']={'at':observed,'state':v['state'],'kind':row['kind'],'reason':row['reason'],'actual_score':v.get('actual_score'),'retained_id':row.get('retained_id'),'planned_title':row.get('title'),'evidence':refs,'next_action':next_action}
  l['local_sync']={'at':observed,'state':'PERFORMANCE_ACTION_DOUBLE_SYNC_PASS'if passed else'CURRENT_RETURNED_VALUES_SYNCED_IP_REJECTION_HOLD'if v['state']=='PLATFORM_IP_REJECTED_OWNER_CONFIRMED'else'CURRENT_RETURNED_VALUES_SYNCED_LEGACY_ATTRIBUTE_PENDING'if v['state']in('DISPLAY_RESTORED_CUSTOM_PROPERTY_STILL_PRESENT','CUSTOM_PROPERTY_DELETE_NOOP_PLATFORM_TBD')else'CURRENT_RETURNED_VALUES_SYNCED_PLATFORM_REVIEW_PENDING','current_fields_file':d.rel(destination/'formal_get.json'),'current_schema_file':d.rel(destination/'formal_render.json')if render.exists()else None,'verification':d.rel(vf)}
  # Source record stays unchanged; current lifecycle is synchronized alongside
  # it so an offline listing is never mistaken for a missing physical source.
  source=sources.get(l.get('bound_source_id'))
  if source:source.setdefault('current_listing_dispositions',{})[pid]={'at':observed,'model':l['model'],'status':p['status'],'display':p['display'],'state':v['state'],'evidence':d.rel(vf)}
  facts=product.get('local_assets',{}).get('current_fields_file')
  if facts and facts.endswith('事实与页面计划.json'):
   path=d.ROOT/facts;doc=source_docs.setdefault(path,d.load(path));doc.setdefault('current_platform_dispositions_by_id',{})[pid]={'at':observed,'status':p['status'],'display':p['display'],'state':v['state'],'reason':row['reason'],'retained_id':row.get('retained_id'),'evidence':d.rel(vf)}
   if row.get('execution_hold'):doc.update(page_state='PLATFORM_IP_REJECTED_NO_RESUBMIT',publish_hold=deepcopy(row['rejection_evidence']))
  product.setdefault('local_assets',{}).setdefault('current_performance_by_id',{})[pid]=d.rel(vf)
  if product['id']=='HR030':
   product['next_action']='BQ1030-A/B平台因侵权退回（负责人明确说明），停止原款原图重提。保留实源以追溯，核具体权利通知与鞋上标识/外观，替换合适实款前不恢复发布；属性校验独立记录。';product['publication_disposition']={'state':'PLATFORM_IP_REJECTED_NO_RESUBMIT','source':'负责人2026-10-16本会话明确说明阿里巴巴判定侵权退回','evidence':d.rel(d.BASE/'侵权退回事实.json'),'source_identity_unchanged':True};product['local_assets']['state']='REAL_SOURCE_EVIDENCE_RETAINED_PLATFORM_IP_HOLD'
  proof={'id':pid,'at':at,'state':l['local_sync']['state'],'checks':{'product_and_source_identity_preserved':identity==(l['product_id'],l.get('bound_source_id'),product['source_state']),'current_returned_title_status_display_synced':all(l['current_platform_fields'][k]==fields[k]for k in('title','status','display')),'complete_formal_snapshot_saved':d.load(destination/'formal_get.json')['response']['product']==p,'current_action_state_not_inferred':l['optimization']['product_performance_review']['state']==v['state']},'verification':d.rel(vf)};d.save(folder/'双改核验.json',proof);proofs.append(proof)
 for path,doc in source_docs.items():d.save(path,doc)
 for w in r.get('workstreams',[]):
  if w['name']=='HR缺货源实款替换':w['next_action']='稳定BQ货号与实源保持；两条重复弱入口已下架。BQ1030-A/B因平台判定侵权退回，停止原鞋原图重提，具体权利通知与实鞋标识/外观复核见经营诊断。'
 r['updated_on']='2026-10-16';r['product_performance_review']={'at':at,'entry':d.rel(d.AREA/'店铺经营诊断.md'),'plan':d.rel(a.PLAN),'states':dict(states),'source_identity_unchanged':True};assert set(views.validate(r))<=baseline;d.save(d.REG,r)
 for path,body in views.build(r).items():views.write_generated(d.ROOT/path,body)
 summary={'at':at,'actions':len(proofs),'states':dict(states),'checks':{'all_local_proofs_pass':all(all(p['checks'].values())for p in proofs),'no_new_registry_errors':True},'baseline_validation_issues':sorted(baseline),'public_qa':'API closure; browser used for unavailable latest metrics and exact edit error only.'};d.save(d.BASE/'当前处置状态.json',summary);print(summary)

if __name__=='__main__':main()
