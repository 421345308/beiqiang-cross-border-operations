"""Recover exact same-product SKU snapshots after observed category-induced reset.

The generic incremental checker cannot describe a platform reset to one empty SKU.
This narrow recovery validates both official before/after snapshots, all original
SKU IDs/codes, the unchanged product identity, current target axes and exact prices.
It uses the existing signed official client; no guard/schema evidence is fabricated.
"""
from copy import deepcopy
from xml.etree import ElementTree as E
import argparse,sys,json
import normalize_models_factory_gallery as n
from repair_model_factory_quality import FIXES
IDS=('1601943711519','1601970118386')
def canonical_skus(value,*,ignore_platform_ids=False):
 v=deepcopy(value)
 if ignore_platform_ids:
  for row in v.get('skus',[]):row.pop('sku_id',None)
 v['skus']=sorted(v.get('skus',[]),key=lambda r:str(r['sku_code']))
 for axis in v.get('sku_attributes',[]):axis['values']=sorted(axis.get('values',[]),key=lambda r:json.dumps(r,sort_keys=True))
 if 'sku_attributes'in v:v['sku_attributes']=sorted(v['sku_attributes'],key=lambda r:str(r['attribute_id']))
 return v
def stable(p):
 value=n.clean_product(p);value['main_image']=deepcopy(p['main_image']);value.pop('product_sku',None);return value
def run(pid,mode,api,cfg):
 parent=n.BASE/'商品'/pid/'质量修正';folder=parent/'规格恢复';ledger=folder/'update_once.json';folder.mkdir(parents=True,exist_ok=True)
 def read(method,params):return n.read_only_call(api,cfg,method,params)
 def get():return read('alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'})
 def render(p):return read('alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US'}})
 if mode=='prepare':
  if ledger.exists():return {'id':pid,'state':'EXISTING_LEDGER_READBACK_ONLY'}
  original=n.load(parent/'before_get.json')['product'];reference=n.load(parent/'before_render.json');category_receipt=n.load(parent/'update_receipt.json');assert category_receipt['status']=='submitted_needs_readback'
  g=get();p=g['product'];assert p['status']=='approved'and p['display']=='Y'and p['product_id']==original['product_id'];assert int(p['category_id'])==FIXES[pid]['category_id'];n.save(folder/'before_get.json',g)
  assert not p['product_sku'].get('sku_attributes')and len(p['product_sku'].get('skus',[]))==1,'Exact observed reset state required; do not overwrite another SKU repair'
  old_rows=original['product_sku']['skus'];assert len(old_rows)==(60 if pid==IDS[0]else 27)and len({str(r['sku_id'])for r in old_rows})==len(old_rows)and all(int(r['sku_id'])>0 for r in old_rows)
  rr=render(p);assert rr.get('data');n.save(folder/'before_render.json',rr);current=E.fromstring(rr['data']);before=E.fromstring(reference['data']);axes=lambda s:{(f.get('id'),f.get('type'),f.get('name'))for f in s.findall("./field[@id='saleProp']/fields/field")};assert axes(current)==axes(before),'Colour/EUR axes must be identical'
  fields=['saleProp','sku','ladderPrice','productTitle'];root=n.contract.values_only(before,operation='update',field_ids=fields);n.pub.set_direct_value(root,'productTitle',p['subject']);assert {x.get('id')for x in root}==set(fields)
  ids=[x.text for x in root.findall("./field[@id='sku']//field[@id='skuId']/value")];assert set(ids)=={str(r['sku_id'])for r in old_rows}and len(ids)==len(old_rows)
  codes=[x.text for x in root.findall("./field[@id='sku']//field[@id='skuOuterId']/value")];assert set(codes)=={r['sku_code']for r in old_rows}and len(codes)==len(set(codes))
  (folder/'payload.xml').write_text(E.tostring(root,encoding='unicode'),encoding='utf8');n.save(folder/'prepared.json',{'id':pid,'at':n.now(),'state':'PREPARED_EXACT_SAME_PRODUCT_HISTORICAL_SKU_RECOVERY','category_id':int(p['category_id']),'fields':fields,'original_SKUs':len(old_rows),'original_SKU_ids':ids,'original_SKU_codes':codes,'current_schema_request_id':rr['request_id'],'current_schema_sha256':n.sha(folder/'before_render.json'),'original_get_reference':n.rel(parent/'before_get.json'),'original_get_sha256':n.sha(parent/'before_get.json'),'original_schema_reference':n.rel(parent/'before_render.json'),'original_schema_sha256':n.sha(parent/'before_render.json'),'category_reset_receipt':n.rel(parent/'update_receipt.json'),'category_reset_receipt_sha256':n.sha(parent/'update_receipt.json'),'payload_sha256':n.sha(folder/'payload.xml'),'scope':'Restore old same-product SKU IDs/codes, colour/EU bindings and exact quantity tiers after documented category reset; no invented stock, product change or new listing.'});return {'id':pid,'state':'PREPARED','original_SKUs':len(old_rows)}
 if mode=='submit':
  if ledger.exists():return {'id':pid,'state':'EXISTING_LEDGER_READBACK_ONLY'}
  prep=n.load(folder/'prepared.json');assert prep['id']==pid and n.sha(folder/'payload.xml')==prep['payload_sha256']and n.sha(n.ROOT/prep['original_get_reference'])==prep['original_get_sha256']
  g=get();n.save(folder/'immediate_prewrite_get.json',g);p=g['product'];before=n.load(folder/'before_get.json')['product'];assert n.clean_product(p)==n.clean_product(before)and p['main_image']==before['main_image']and p['status']=='approved'and p['display']=='Y'
  with ledger.open('x',encoding='utf8')as fp:json.dump({'id':pid,'at':n.now(),'state':'STARTED_OUTCOME_UNKNOWN_NO_REPLAY'},fp)
  response=api.top_call(cfg,'alibaba.icbu.product.schema.update',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':prep['category_id'],'language':'en_US','xml':(folder/'payload.xml').read_text(encoding='utf8')}});status=n.pub.classify_result('update',response);n.save(folder/'update_receipt.json',{'id':pid,'at':n.now(),'status':status,'method':'alibaba.icbu.product.schema.update','response':response,'prepared_file':n.rel(folder/'prepared.json')});n.save(ledger,{'id':pid,'at':n.now(),'state':status});return {'id':pid,'state':status}
 assert ledger.exists();g=get();n.save(folder/'after_get.json',g);p=g['product'];original=n.load(parent/'before_get.json')['product'];baseline=n.load(folder/'before_get.json')['product'];old={r['sku_code']:r for r in original['product_sku']['skus']};new={r.get('sku_code'):r for r in p['product_sku']['skus']};checks={'all_original_SKU_codes_prices_props_and_colour_images':canonical_skus(p['product_sku'],ignore_platform_ids=True)==canonical_skus(original['product_sku'],ignore_platform_ids=True),'unique_positive_current_SKU_ids':len({str(r['sku_id'])for r in new.values()})==len(new)and all(int(r['sku_id'])>0 for r in new.values()),'non_target_fields_preserved':stable(p)==stable(baseline),'same_product_encrypted_identity':p['product_id']==original['product_id']};ids_preserved=bool(set(old)==set(new))and all(old[k]['sku_id']==new[k]['sku_id']for k in old);report={'id':pid,'at':n.now(),'state':'RESTORED_WITH_REISSUED_IDS_PENDING_REVIEW'if all(checks.values())else'SKU_RECOVERY_MISMATCH','status':p['status'],'display':p['display'],'checks':checks,'original_platform_SKU_ids_preserved':ids_preserved,'actual_SKUs':len(p['product_sku'].get('skus',[])),'original_SKUs':len(original['product_sku']['skus']),'actual_score':None}
 if p['status']=='approved'and p['display']=='Y'and all(checks.values()):
  report['state']='SKU_DATA_RESTORED_PLATFORM_IDS_REISSUED_FORMAL_PASS'if not ids_preserved else'ORIGINAL_SKU_RECOVERY_FORMAL_PASS';rr=render(p);n.save(folder/'after_render.json',rr)
  assert rr.get('data');root=E.fromstring(rr['data']);bindings={x.find("./field[@id='skuOuterId']/value").text:x.find("./field[@id='skuId']/value").text for x in root.findall("./field[@id='sku']/complex-values")};assert bindings=={k:str(v['sku_id'])for k,v in new.items()}
  mapping={'id':pid,'at':n.now(),'state':'FORMAL_REISSUED_IDS_AND_ORIGINAL_SKU_DATA_VERIFIED','original_platform_SKU_ids_preserved':ids_preserved,'items':{k:{'old_sku_id':str(old[k]['sku_id']),'current_sku_id':str(new[k]['sku_id'])}for k in old},'checks':checks,'receipt':n.rel(folder/'update_receipt.json'),'receipt_sha256':n.sha(folder/'update_receipt.json'),'formal_get':n.rel(folder/'after_get.json'),'formal_get_sha256':n.sha(folder/'after_get.json'),'current_schema_bindings_verified':True};n.save(folder/'SKU编号变更映射.json',mapping)
 n.save(folder/'verification.json',report);return report
def main():
 sys.stdout.reconfigure(encoding='utf8');ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['prepare','submit','verify']);args=ap.parse_args();api,cfg=n.b.api_client();api.http_json=api.native_http_json
 for pid in IDS:print(json.dumps(run(pid,args.mode,api,cfg),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
