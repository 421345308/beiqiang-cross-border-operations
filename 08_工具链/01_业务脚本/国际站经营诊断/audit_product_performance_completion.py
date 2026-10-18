"""Exact scope audit; restored visibility is distinct from attribute removal."""
from collections import Counter
import sys
import diagnose_product_performance as d
import apply_product_performance_actions as a
from sync_product_performance_actions import FOLDERS,PASS

def main():
 sys.stdout.reconfigure(encoding='utf8');plan=d.load(a.PLAN);ids={x['id']for x in plan['items']};r=d.load(d.REG);links={l['id']:l for l in r['listings']};before=d.load(d.BASE/'当前目录/catalog.json');after=d.load(d.BASE/'处置后目录/catalog.json');old={str(p['id']):p for p in before['products']};current={str(p['id']):p for p in after['products']};issues=[];residual=[];states=Counter();done=[]
 def check(ok,name):
  if not ok:issues.append(name)
 check(after['complete']and after['total_item']==len(current)==len(old)==488 and current.keys()==old.keys(),'complete_same_unique_catalog')
 for pid,p in current.items():
  if pid in ids:continue
  keys=['subject','red_model','category_id','status','display','main_image','gmt_create'];check(all(p.get(k)==old[pid].get(k)for k in keys),'non_target_catalog_drift:'+pid)
 for row in plan['items']:
  pid=row['id'];f=d.BASE/'商品'/pid/FOLDERS[row['kind']];v=d.load(f/'verification.json');p=d.load(f/'after_get.json')['product'];local=d.load(f/'双改核验.json');l=links[pid];state=v['state'];states[state]+=1
  check(all(local['checks'].values()),'double_sync:'+pid);check(l['current_platform_fields']['title']==p['subject']and l['observation']['audit']==p['status']and l['observation']['display']==p['display'],'current_registry_fields:'+pid)
  check(current[pid]['subject']==p['subject']and current[pid]['status']==p['status']and current[pid]['display']==p['display'],'catalog_exact_get_consistency:'+pid)
  check(d.load(f/'update_once.json')['state']in('submitted_needs_readback','RECEIPT_RECORDED_NEEDS_EXACT_FORMAL_READBACK'),'single_positive_write_ledger:'+pid)
  if state in PASS:check(all(v['checks'].values()),'accepted_checks:'+pid);done.append(pid)
  elif state=='DISPLAY_RESTORED_CUSTOM_PROPERTY_STILL_PRESENT':
   check(p['status']=='approved'and p['display']=='Y'and v['actual_score']=='5.00'and all(value for key,value in v['checks'].items()if key!='unsupported_custom_property_cleared'),'restored_live_non_target:'+pid);residual.append({'id':pid,'state':state,'remaining':'旧自定义属性未删除；空complex已证无效，正常编辑表单持续加载，保留正常在架，不重复请求。'})
  elif state=='CUSTOM_PROPERTY_DELETE_NOOP_PLATFORM_TBD':
   check(p['status']=='tbd'and p['display']=='N'and all(value for key,value in v['checks'].items()if key!='unsupported_custom_property_cleared'),'rejected_non_target_preserved:'+pid);residual.append({'id':pid,'state':state,'remaining':'当前退回，不能计在架/修复完成。原属性未清除；无效空complex不重投，正常编辑页持续加载，待可用正常删除入口。'})
  elif state=='PLATFORM_IP_REJECTED_OWNER_CONFIRMED':
   check(p['status']=='tbd'and p['display']=='N'and all(value for key,value in v['checks'].items()if key!='unsupported_custom_property_cleared'),'ip_hold_non_target_preserved:'+pid);residual.append({'id':pid,'state':state,'remaining':'负责人明确平台判定侵权退回，停止原鞋原图重提；具体权利类型/权利人通知尚未读取。属性校验独立，不作为退回主因。'})
  else:residual.append({'id':pid,'state':state,'remaining':'审核或字段仍未验收，不报正式完成。'})
 report={'at':a.now(),'state':'PARTIAL_EXECUTION_WITH_PLATFORM_REJECTIONS'if not issues and len(done)==5 and any(x['state']in('CUSTOM_PROPERTY_DELETE_NOOP_PLATFORM_TBD','PLATFORM_IP_REJECTED_OWNER_CONFIRMED')for x in residual)else'ACTION_BATCH_VERIFIED_WITH_DECLARED_ATTRIBUTE_RESIDUALS'if not issues and len(done)==5 else'INCOMPLETE_OR_MISMATCH','all_seven_actions_completed':len(done)==len(ids),'current_catalog_ids':len(current),'current_catalog_states':dict(Counter(p['status']+'/'+p['display']for p in current.values())),'actions':len(ids),'accepted_optimization_or_offline_ids':done,'states':dict(states),'residuals':residual,'issues':issues,'checks':{'same_complete_catalog':True,'all_untouched_catalog_fields_unchanged':not any(x.startswith('non_target')for x in issues),'original_four_offline_preserved':all(current[i]['display']=='N'and current[i]['status']==old[i]['status']for i in old if old[i]['display']=='N'and old[i]['status']=='approved'),'protected_source_untouched':all(current['1601825074604'].get(k)==old['1601825074604'].get(k)for k in('subject','red_model','category_id','display','status','main_image')),'all_target_current_and_source_records_synced':not issues},'scope':'API exact-ID/catalog/score closure; no per-link public-browser QA; no ad-budget or source identity changes.'};d.save(d.BASE/'最终核验.json',report);print(report);assert not issues,issues

if __name__=='__main__':main()
