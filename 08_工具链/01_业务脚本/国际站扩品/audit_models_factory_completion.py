"""Read-only catalog plus offline exact-ID final double-sync acceptance."""
from collections import Counter
from decimal import Decimal
import argparse,json,sys
import normalize_models_factory_gallery as n
from read_only_catalog import fetch_catalog

def main():
 sys.stdout.reconfigure(encoding='utf8');ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--refresh-catalog',action='store_true');args=ap.parse_args()
 folder=n.BASE/'完成目录'
 if args.refresh_catalog:
  api,cfg=n.b.api_client();api.http_json=api.native_http_json;fetch_catalog(api,cfg,folder)
 catalog=n.load(folder/'catalog.json');scope=n.load(n.BASE/'范围.json');registry=n.load(n.REG);links={l['id']:l for l in registry['listings']};observed={str(p['id']):p for p in catalog['products']};initial=n.load(n.BASE/'当前目录/catalog.json');original={str(p['id']):p for p in initial['products']};issues=[];reissued={};counts=Counter();platform_exceptions=[]
 def check(ok,label,pid=None):
  if not ok:issues.append({'id':pid,'check':label})
 check(catalog['complete']and catalog['total_item']==len(observed),'complete_unique_catalog')
 check(set(observed)==set(original),'same_complete_catalog_ID_set_no_recreation')
 for z in scope['targets']:
  pid=z['id'];f=n.BASE/'商品'/pid;v=n.load(f/'verification.json');proof=n.load(f/'双改核验.json');local=n.load(n.CURRENT/pid/'formal_get.json')['response']['product'];p=observed.get(pid,{});l=links[pid];counts[v['state']]+=1
  if v['state']=='PLATFORM_REJECTED_TARGET_VALUES_RETURNED':
   check(p.get('status')==local['status']==v['status']=='tbd'and p.get('display')==local['display']==v['display']=='N'and all(v['readback_checks'].values()),'exact_ID_rejection_and_returned_target_values',pid)
   platform_exceptions.append({'id':pid,'model':z['new_model'],'status':'tbd','display':'N','state':v['state'],'reason':'Official get/list omit rejection reason; normal seller editor requires login. No guessed resubmission.','evidence':n.rel(f/'verification.json')})
  else:
   check(v['state']=='FORMAL_FIELDS_SCORE_PASS'and Decimal(str(v['actual_score']))>=5 and all(v['checks'].values()),'formal_target_non_target_schema_and_actual_score',pid)
   check(p.get('status')=='approved'and p.get('display')=='Y','fresh_catalog_approved_and_displayed',pid)
  check(p.get('red_model')==l['model']==z['new_model']==n.b.model(local),'fresh_model_and_local_identity',pid)
  check(list(map(n.pub.image_key,p.get('main_image',{}).get('images',[])))==list(map(n.pub.image_key,local['main_image']['images'])),'fresh_gallery_matches_local_formal',pid)
  expected_sync='CURRENT_API_VALUES_SYNCED_ACCEPTANCE_PENDING'if v['state']=='PLATFORM_REJECTED_TARGET_VALUES_RETURNED'else'MODEL_FACTORY_GALLERY_DOUBLE_SYNC_PASS'
  check(proof['state']==expected_sync and all(proof['checks'].values()),'local_double_sync',pid)
  check(l.get('bound_source_id')==z['source_id']and l['product_id']==z['product_key'],'source_binding_and_product_key_preserved',pid)
  if v.get('sku_reissue_mapping'):
   mapping=n.verified_sku_reissue(pid);reissued[pid]={'count':len(mapping['items']),'mapping':v['sku_reissue_mapping'],'original_platform_SKU_ids_preserved':False}
 for z in scope['excluded']:
  pid=z['id'];check(preserved_excluded(original[pid],observed.get(pid,{})),'excluded_state_model_and_gallery_preserved',pid)
 migrations=scope['model_migrations'];check(len(migrations)==175,'expected_model_migration_count');check(all(observed[z['id']]['red_model']==z['new_model']for z in migrations),'all175_HR_models_changed');check(all(not observed[z['id']]['red_model'].startswith('HR')for z in migrations),'no_current_HR_models_in_migrated_scope')
 report={'at':n.now(),'state':'CONTENT_DOUBLE_SYNC_COMPLETE_WITH_PLATFORM_REJECTIONS'if platform_exceptions and not issues else'COMPLETE_API_AND_LOCAL_DOUBLE_SYNC_PASS'if not issues else'FAIL','catalog_ids':len(observed),'updated_ids':len(scope['targets']),'model_migration_ids':len(migrations),'formal_states':dict(counts),'current_platform_exceptions':platform_exceptions,'all_updated_listings_currently_approved':not platform_exceptions and not issues,'SKU_reissued_IDs':reissued,'SKU_reissued_count':sum(x['count']for x in reissued.values()),'excluded_ids':len(scope['excluded']),'issues':issues,'catalog':n.rel(folder/'catalog.json'),'catalog_sha256':n.sha(folder/'catalog.json'),'registry_sha256':n.sha(n.REG),'public_qa':'未逐商品浏览器实测；按负责人API闭环验收','scope':'Exact frozen original IDs; no source identity or inventory claim inferred from platform status'};n.save(n.BASE/'完成核验.json',report);print(json.dumps(report,ensure_ascii=False));assert not issues

def preserved_excluded(before,after):
 return all(before.get(k)==after.get(k)for k in ('id','red_model','status','display','main_image'))

if __name__=='__main__':main()
