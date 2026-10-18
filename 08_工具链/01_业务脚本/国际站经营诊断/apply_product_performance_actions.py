"""Scoped, once-only product dispositions; no ad settings, category or SKU writes."""
from copy import deepcopy
from xml.etree import ElementTree as E
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal
import argparse,json,hashlib,sys,re
import diagnose_product_performance as d
sys.path.insert(0,str(d.ROOT/'08_工具链/01_业务脚本/国际站扩品'))
import normalize_models_factory_gallery as n
ROOT=d.ROOT;BASE=d.BASE;PLAN=BASE/'处置计划.json'
def now():return datetime.now(timezone.utc).isoformat()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stable(p):
 value=n.clean_product(p);value['main_image']=deepcopy(p['main_image']);return value
def same_custom_target(p):return [a for a in p['attributes']if a['attribute_id']==-1 and a['attribute_name']=='Shoe Profile'and a['value_name']=='Low-top platform sneaker']
def operate(row,mode,api,cfg):
 pid=row['id'];kind=row['kind'];folder=BASE/'商品'/pid/{'pause_duplicate':'重复弱链接下架','repair_custom_attribute':'退回属性修复','title_clarity':'标题识别优化'}[kind];folder.mkdir(parents=True,exist_ok=True);ledger=folder/'update_once.json'
 if mode in('prepare','submit')and row.get('execution_hold')=='PLATFORM_IP_REJECTED_OWNER_CONFIRMED':return {'id':pid,'state':'IP_REJECTION_HOLD_NO_RESUBMIT'}
 def get(i=pid):return n.read_only_call(api,cfg,'alibaba.icbu.product.get',{'product_id':i,'language':'ENGLISH'})
 def render(p):return n.read_only_call(api,cfg,'alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US'}})
 if mode=='prepare':
  if ledger.exists():return {'id':pid,'state':'EXISTING_WRITE_READBACK_ONLY'}
  g=get();p=g['product'];assert n.b.model(p)==row['model']and pid not in d.PROTECTED;n.save(folder/'before_get.json',g)
  if kind=='pause_duplicate':
   s=get(row['retained_id']);sp=s['product'];n.save(folder/'retained_before_get.json',s);assert p['status']==sp['status']=='approved'and p['display']==sp['display']=='Y';r=n.load(n.REG);links={l['id']:l for l in r['listings']};l=links[pid];sl=links[row['retained_id']];assert l['product_id']==sl['product_id']and l['bound_source_id']==sl['bound_source_id']and not d.source_change(l)and not d.source_change(sl)
   m=d.sku_matrix(p);sm=d.sku_matrix(sp);assert m and m.keys()<=sm.keys()and all(m[k]==sm[k]for k in m)
   details=lambda z:{d.image_key(x['image_url'])for x in z['struct_detail']['detail_image']['images']};assert details(p)==details(sp)and len(details(p))>=4
   shared=len(set(map(d.image_key,p['main_image']['images']))&set(map(d.image_key,sp['main_image']['images'])));assert shared>=5
   metrics={x['id']:x for x in d.load(d.AREA/'商品诊断数据.json')['products']};weak=metrics[pid]['periods'];strong=metrics[row['retained_id']]['periods'];assert all(weak[period][k]==0 for period in('september','week40')for k in('inquiries','tm_buyers'));assert any(strong[period][k]>0 for period in('september','week40','oct14')if strong.get(period)for k in('inquiries','tm_buyers'));assert all(weak[period][k]==0 for period in('oct13','oct14')if weak.get(period)for k in('inquiries','tm_buyers'))
   n.save(folder/'prepared.json',{'id':pid,'at':now(),'kind':kind,'reason':row['reason'],'retained_id':row['retained_id'],'shared_main_images':shared,'checks':{'same_real_family_and_source':True,'all_weak_SKUs_and_prices_retained':True,'same_all_product_details':True,'no_recent_weak_consultation_evidence':True,'strong_entry_has_consultation':True},'method':'alibaba.icbu.product.batch.update.display','params':{'new_display':'off','product_id_list':[int(pid)]},'official_reference':'https://open.alibaba.com/doc/api.htm#/api?cid=20966&path=alibaba.icbu.product.batch.update.display&methodType=GET/POST','before_sha256':sha(folder/'before_get.json')});return {'id':pid,'state':'PREPARED_PAUSE_DUPLICATE'}
  if kind=='title_clarity':
   assert p['status']=='approved'and p['display']=='Y'and p['subject']==row['before_title']
   assert 60<=len(row['title'])<=128 and row['title']!=p['subject']
  else:assert p['status']=='tbd'and p['display']=='N'and len(same_custom_target(p))==1
  rr=render(p);assert rr.get('data');n.save(folder/'before_render.json',rr);(folder/'current_schema.xml').write_text(rr['data'],encoding='utf8');source=E.fromstring(rr['data']);field=source.find("./field[@id='customMoreProperty']");assert field is not None and field.get('type')=='complex'
  fields=['productTitle']if kind=='title_clarity'else['customMoreProperty','productTitle'];root=n.contract.values_only(source,operation='update',field_ids=fields)
  if kind=='repair_custom_attribute':
   entries=field.findall('./complex-value/field');assert len(entries)==1 and entries[0].find("./complex-value/field[@id='propName']/value").text=='Shoe Profile'
   target=root.find("./field[@id='customMoreProperty']");target.clear();target.set('id','customMoreProperty');target.set('type','complex');E.SubElement(target,'complex-value')
  n.pub.set_direct_value(root,'productTitle',row['title']if kind=='title_clarity'else p['subject']);(folder/'payload.xml').write_text(E.tostring(root,encoding='unicode'),encoding='utf8')
  manifest={'operation':'update','product_id':pid,'category_id':int(p['category_id']),'facts_reviewed':True,'source_evidence':[d.rel(PLAN)]+row.get('source_evidence',[d.rel(BASE/'自定义属性页面证据.json')]),'current_schema':'current_schema.xml','current_schema_sha256':sha(folder/'current_schema.xml'),'schema_request_id':rr['request_id'],'schema_acquired_at':now(),'payload_xml':'payload.xml','field_ids':fields,'dependency_ids':[]};n.save(folder/'manifest.json',manifest);n.pub.load_submission_manifest(folder/'manifest.json','update',pid);n.save(folder/'prepared.json',{'id':pid,'at':now(),'kind':kind,'reason':row['reason'],'fields':fields,'empty_custom_property_is_request_not_inferred_result':kind=='repair_custom_attribute','before_sha256':sha(folder/'before_get.json')});return {'id':pid,'state':'PREPARED_TITLE'if kind=='title_clarity'else'PREPARED_CUSTOM_PROPERTY_CLEAR'}
 if mode=='submit':
  if ledger.exists():return {'id':pid,'state':'EXISTING_WRITE_READBACK_ONLY'}
  prep=n.load(folder/'prepared.json');before=n.load(folder/'before_get.json')['product'];g=get();n.save(folder/'immediate_prewrite_get.json',g);assert stable(g['product'])==stable(before)and(g['product']['status'],g['product']['display'])==(before['status'],before['display']);assert sha(folder/'before_get.json')==prep['before_sha256']
  if kind=='pause_duplicate':
   sg=get(row['retained_id']);assert stable(sg['product'])==stable(n.load(folder/'retained_before_get.json')['product'])and sg['product']['status']=='approved'and sg['product']['display']=='Y'
  else:listing=n.pub.load_submission_manifest(folder/'manifest.json','update',pid)
  with ledger.open('x',encoding='utf8')as fp:json.dump({'id':pid,'at':now(),'state':'STARTED_OUTCOME_UNKNOWN_NO_REPLAY'},fp)
  if kind=='pause_duplicate':
   response=api.top_call(cfg,prep['method'],prep['params']);error=api.api_error(response);receipt={'id':pid,'at':now(),'status':'business_rejected'if error else'RECEIPT_RECORDED_NEEDS_EXACT_FORMAL_READBACK','response':response,'method':prep['method']}
  else:receipt=n.pub.api_submit(api,cfg,listing,False,update_product_id=pid)
  n.save(folder/'receipt.json',receipt);n.save(ledger,{'id':pid,'at':now(),'state':receipt['status']});return {'id':pid,'state':receipt['status']}
 assert ledger.exists();g=get();n.save(folder/'after_get.json',g);p=g['product'];before=n.load(folder/'before_get.json')['product'];expected=deepcopy(before)
 if kind=='repair_custom_attribute':expected['attributes']=[a for a in expected['attributes']if a not in same_custom_target(before)]
 if kind=='title_clarity':
  expected['subject']=row['title']
  # A title update regenerates the public URL slug. Admit only the same
  # official HTTPS product ID, and keep the exact old/new URLs in evidence.
  assert re.fullmatch(r'https://www\.alibaba\.com/product-detail/[^/]+_'+re.escape(pid)+r'\.html',p['pc_detail_url'])
  expected['pc_detail_url']=p['pc_detail_url']
 comparison=deepcopy(p)
 if kind=='repair_custom_attribute':comparison['attributes']=[x for x in comparison['attributes']if x not in same_custom_target(comparison)]
 if kind=='title_clarity':comparison['subject']=expected['subject']
 checks={'all_non_target_fields_preserved':stable(comparison)==stable(expected),'model_exact':n.b.model(p)==row['model'],'all_SKU_IDs_codes_colour_sizes_prices_inventory_preserved':n.canonical_skus(p['product_sku'])==n.canonical_skus(before['product_sku']),'all_main_images_preserved':p['main_image']==before['main_image']}
 if kind=='pause_duplicate':
  s=get(row['retained_id']);n.save(folder/'retained_after_get.json',s);checks.update(display_off=p['display']=='N',retained_entry_approved_visible=s['product']['status']=='approved'and s['product']['display']=='Y',retained_entry_all_fields_unchanged=stable(s['product'])==stable(n.load(folder/'retained_before_get.json')['product']));state='FORMAL_OFFLINE_NON_TARGET_PASS'if p['status']=='approved'and all(checks.values())else'OFFLINE_PENDING_OR_MISMATCH'
 elif kind=='repair_custom_attribute':
  checks['unsupported_custom_property_cleared']=not any(a['attribute_id']==-1 for a in p['attributes']);state='FIELDS_RETURNED_REVIEW_PENDING'if all(checks.values())else'FIELD_NOT_CLEARED_OR_MISMATCH'
 else:
  manual=row.get('returned_title_review',{});accepted=manual.get('actual_title')if manual.get('state')=='MANUALLY_REVIEWED_VARIANT_CORE_INTENT_PRESERVED'else row['title'];checks['title_matches_reviewed_target']=p['subject']==accepted;state='TITLE_RETURNED_REVIEW_PENDING'if all(checks.values())else'TITLE_NOT_YET_RETURNED_OR_MISMATCH'
 if kind!='pause_duplicate'and p['status']=='modified':state='FIELDS_MATCH_REVIEW_PENDING'if all(checks.values())else'PLATFORM_REVIEW_PENDING_FORMAL_NOT_MATCHED'
 report={'id':pid,'at':now(),'kind':kind,'state':state,'status':p['status'],'display':p['display'],'checks':checks,'actual_score':None,'reason':row['reason'],'public_qa':'API closure; normal editor used only for specific validation error diagnosis'}
 if kind=='title_clarity':report.update(actual_title=p['subject'],requested_title_exact=p['subject']==row['title'],returned_title_review=row.get('returned_title_review'))
 restored_legacy=kind=='repair_custom_attribute'and not checks['unsupported_custom_property_cleared']and all(v for k,v in checks.items()if k!='unsupported_custom_property_cleared')
 if kind!='pause_duplicate'and p['status']=='approved'and p['display']=='Y'and(all(checks.values())or restored_legacy):
  rr=render(p);n.save(folder/'after_render.json',rr);assert rr.get('data');a=n.contract.field_snapshot(E.fromstring(rr['data']));b=n.contract.field_snapshot(E.fromstring(n.load(folder/'before_render.json')['data']));fields=n.load(folder/'prepared.json')['fields'];checks['non_target_schema_fields_preserved']=all(a.get(k)==v for k,v in b.items()if k not in fields);enc=api.top_call(cfg,'alibaba.icbu.product.id.encrypt',{'product_id':pid,'language':'ENGLISH'});score=n.read_only_call(api,cfg,'alibaba.icbu.product.score.get',{'product_id':enc['secret_id']});n.save(folder/'score.json',score);report['actual_score']=score.get('result',{}).get('final_score');report['state']=('TITLE_FORMAL_SCORE_PASS'if kind=='title_clarity'else'CUSTOM_PROPERTY_REPAIR_FORMAL_SCORE_PASS')if all(checks.values())and report['actual_score']and Decimal(str(report['actual_score']))>=5 else'FORMAL_OR_SCORE_PENDING'
 if restored_legacy and p['status']=='approved'and p['display']=='Y':report['state']='DISPLAY_RESTORED_CUSTOM_PROPERTY_STILL_PRESENT'
 if kind=='repair_custom_attribute'and p['status']=='tbd'and all(value for key,value in checks.items()if key!='unsupported_custom_property_cleared')and not checks['unsupported_custom_property_cleared']:report['state']='CUSTOM_PROPERTY_DELETE_NOOP_PLATFORM_TBD'
 if row.get('execution_hold')=='PLATFORM_IP_REJECTED_OWNER_CONFIRMED':report.update(state='PLATFORM_IP_REJECTED_OWNER_CONFIRMED',rejection_evidence=row['rejection_evidence'],attribute_validation_is_independent=True)
 if kind=='title_clarity'and report['state']=='TITLE_FORMAL_SCORE_PASS'and not report['requested_title_exact']:report['state']='TITLE_REVIEWED_VARIANT_FORMAL_SCORE_PASS'
 n.save(folder/'verification.json',report);return report
def main():
 sys.stdout.reconfigure(encoding='utf8');ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['prepare','submit','verify']);ap.add_argument('--ids');args=ap.parse_args();plan=d.load(PLAN);items=[x for x in plan['items']if not args.ids or x['id']in args.ids.split(',')];api,cfg=n.b.api_client();api.http_json=api.native_http_json
 for item in items:print(json.dumps(operate(item,args.mode,api,cfg),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
