"""Exact three post-update exceptions: restore one title, migrate two compatible leaves.
Real score diagnostics, current target Schema and once-only per-ID receipts.
"""
from copy import deepcopy
from xml.etree import ElementTree as E
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
import sys,json,argparse
import normalize_models_factory_gallery as n
FIXES={'1601943670945':{'kind':'title'},'1601943711519':{'kind':'category','category_id':201153804,'name':'Clogs & Mules'},'1601970118386':{'kind':'category','category_id':201334413,'name':'Walking Style Shoes'}}
def preserve(p,kind):
 result=n.clean_product(p,False);result['main_image']=deepcopy(p['main_image'])
 result.pop('subject'if kind=='title'else'category_id',None)
 if kind=='category':result.pop('attributes',None)
 return result
def run(pid,mode,api,cfg):
 fix=FIXES[pid];folder=n.BASE/'商品'/pid/'质量修正';folder.mkdir(parents=True,exist_ok=True);ledger=folder/'update_once.json'
 def call(method,params):return n.read_only_call(api,cfg,method,params)
 def get():return call('alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'})
 def render(p):return call('alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US'}})
 if mode=='prepare':
  if ledger.exists():return {'id':pid,'state':'EXISTING_LEDGER_READBACK_ONLY'}
  if fix['kind']=='category':raise ValueError('Retired partial category route: a category change resets SKU bindings. Requires a separately reviewed complete category/SKU migration.')
  g=get();p=g['product'];assert p['status']=='approved'and p['display']=='Y';n.save(folder/'before_get.json',g);rr=render(p);assert rr.get('data');n.save(folder/'before_render.json',rr);source=E.fromstring(rr['data']);category=int(p['category_id']);fields=['productTitle'];schema=source;schema_ref=rr
  title=n.load(n.BASE/'商品'/pid/'before_get.json')['product']['subject']
  compatibility={};expected_attributes=deepcopy(p['attributes']);remaps=[]
  if fix['kind']=='category':
   scored=n.load(n.BASE/'商品'/pid/'score.json');problem=scored['result']['problem_map'];problem=json.loads(problem)if isinstance(problem,str)else problem;assert problem['extendProblemMap']['category']is True and problem['errorReasonCategoryMap']['en']==str(fix['category_id'])
   category=fix['category_id'];meta=call('alibaba.icbu.category.get.new',{'cat_id':category});n.save(folder/'target_category.json',meta);assert meta['category']['leaf_category']and meta['category']['name']==fix['name']
   schema_ref=call('alibaba.icbu.product.schema.get',{'param_product_top_publish_request':{'cat_id':category,'language':'en_US'}});assert schema_ref.get('data');n.save(folder/'target_schema.json',schema_ref);schema=E.fromstring(schema_ref['data']);defs={f.get('id'):f for f in schema.findall("./field[@id='icbuCatProp']/fields/field")};actual={f.get('id'):f for f in source.findall("./field[@id='icbuCatProp']/complex-value/field")}
   # Preserve the same evidence when category vocabularies use different codes.
   changes={'p-191288243':('Slip On',None),'p-191290428':('Knit',-701)}if pid=='1601943711519'else{'p-20700':('EVA',None)}
   expected_old={'p-191288243':{'Mules','Casual'},'p-191290428':{'Knit'},'p-20700':{'EVA'}}
   for key,(label,custom_marker)in changes.items():
    node=actual[key];old_labels={v.get('inputValue')or v.text for v in node.iter('value')};assert old_labels==expected_old[key],(pid,key,'Source values changed')
    opts={o.get('displayName').casefold():o.get('value')for o in defs[key].findall('./options/option')};native=opts.get(label.casefold())
    if custom_marker is not None:assert native is None and any(r.get('name')=='tipRule'and'负数'in r.get('value','')for r in defs[key].findall('./rules/rule'))
    else:assert native is not None
    for child in list(node):node.remove(child)
    values=E.SubElement(node,'values')if node.get('type')=='multiCheck'else node;E.SubElement(values,'value',inputValue=label).text=str(custom_marker)if custom_marker is not None else native
    attr_id=int(key.removeprefix('p-'));prior=next(a for a in expected_attributes if int(a['attribute_id'])==attr_id);expected_attributes=[a for a in expected_attributes if int(a['attribute_id'])!=attr_id];expected_attributes.append({**prior,'value_id':-1 if custom_marker is not None else int(native),'value_name':label});remaps.append({'field_id':key,'source_values':sorted(old_labels),'target_text':label,'target_value':str(custom_marker)if custom_marker is not None else native,'meaning':'Knit/EVA facts retained; Slip On is the source-evidenced open-heel mule construction, with Mules expressed by the actual leaf category.'})
   for key,node in actual.items():
    assert key in defs and defs[key].get('type')==node.get('type'),(pid,key,'incompatible category attribute')
    options={o.get('value')for o in defs[key].findall('./options/option')}
    for value in node.iter('value'):
     if options and value.text and not value.text.startswith('-'):assert value.text in options,(pid,key,'unmapped selected value')
   required=[key for key,f in defs.items()if any(r.get('name')=='requiredRule'and r.get('value')=='true'for r in f.findall('./rules/rule'))];assert all(key in actual and any(v.text for v in actual[key].iter('value'))for key in required),'Missing factual required attribute'
   old_axes={(f.get('id'),f.get('name'),f.get('type'))for f in source.findall("./field[@id='saleProp']/fields/field")};new_axes={(f.get('id'),f.get('name'),f.get('type'))for f in schema.findall("./field[@id='saleProp']/fields/field")};assert old_axes==new_axes,'SKU axes differ; never migrate through this minimal route'
   compatibility={'all_selected_attribute_ids_and_types_match':True,'all_native_values_match_target_options':True,'all_required_properties_already_evidenced':True,'sale_axes_exact':True,'before_category_id':int(p['category_id']),'target_category_id':category,'SKU_not_submitted':True,'category_vocabulary_remaps':remaps};fields=['catId','icbuCatProp','productTitle']
  root=n.contract.values_only(schema,operation='update',field_ids=fields);n.pub.set_direct_value(root,'productTitle',title)
  if fix['kind']=='category':
   n.pub.set_direct_value(root,'catId',str(category));n.pub.replace_complex_value(n.pub.direct_field(root,'icbuCatProp'),deepcopy(source.find("./field[@id='icbuCatProp']/complex-value")))
  (folder/'current_schema.xml').write_text(schema_ref['data'],encoding='utf8');(folder/'payload.xml').write_text(E.tostring(root,encoding='unicode'),encoding='utf8');manifest={'operation':'update','product_id':pid,'category_id':category,'facts_reviewed':True,'source_evidence':[n.rel(n.BASE/'范围.json'),n.rel(n.BASE/'商品'/pid/'verification.json')],'current_schema':'current_schema.xml','current_schema_sha256':n.sha(folder/'current_schema.xml'),'schema_request_id':schema_ref['request_id'],'schema_acquired_at':n.now(),'payload_xml':'payload.xml','field_ids':fields,'dependency_ids':[]}
  if fix['kind']=='category':manifest['expected_model']=n.b.model(p)
  n.save(folder/'manifest.json',manifest);n.pub.load_submission_manifest(folder/'manifest.json','update',pid)
  n.save(folder/'prepared.json',{'id':pid,'kind':fix['kind'],'at':n.now(),'state':'PREPARED','expected_title':title,'expected_attributes':expected_attributes,'before_category_id':int(p['category_id']),'target_category_id':category,'compatibility':compatibility,'scope':'Restore originally requested title or platform-recommended source-compatible leaf with evidenced vocabulary remaps; no product identity/source/SKU/trade changes'});return {'id':pid,'state':'PREPARED','kind':fix['kind']}
 if mode=='submit':
  if ledger.exists():return {'id':pid,'state':'EXISTING_LEDGER_READBACK_ONLY'}
  listing=n.pub.load_submission_manifest(folder/'manifest.json','update',pid);g=get();n.save(folder/'immediate_prewrite_get.json',g);p=g['product'];before=n.load(folder/'before_get.json')['product'];assert p['status']=='approved'and p['display']=='Y'and n.clean_product(p)==n.clean_product(before)and p['main_image']==before['main_image']
  with ledger.open('x',encoding='utf8')as fp:json.dump({'id':pid,'state':'STARTED_OUTCOME_UNKNOWN_NO_REPLAY','at':n.now()},fp)
  rec=n.pub.api_submit(api,cfg,listing,False,update_product_id=pid);n.save(folder/'update_receipt.json',rec);n.save(ledger,{'id':pid,'state':rec['status'],'at':rec['attempted_at'],'refs':rec.get('refs')});return {'id':pid,'state':rec['status']}
 assert ledger.exists();g=get();n.save(folder/'after_get.json',g);p=g['product'];report={'id':pid,'at':n.now(),'state':'PENDING_REVIEW','status':p['status'],'display':p['display'],'kind':fix['kind'],'actual_score':None}
 if p['status']!='approved'or p['display']!='Y':n.save(folder/'verification.json',report);return report
 rr=render(p);n.save(folder/'after_render.json',rr);assert rr.get('data');prep=n.load(folder/'prepared.json');before=n.load(folder/'before_get.json')['product'];expected=deepcopy(before);mapping=n.verified_sku_reissue(pid)
 if mapping:
  for row in expected['product_sku']['skus']:
   entry=mapping['items'][row['sku_code']];assert str(row['sku_id'])==entry['old_sku_id'];row['sku_id']=int(entry['current_sku_id'])if isinstance(row['sku_id'],int)else entry['current_sku_id']
  report['original_platform_SKU_ids_preserved']=mapping['original_platform_SKU_ids_preserved'];report['sku_reissue_mapping']=n.rel(folder/'规格恢复/SKU编号变更映射.json')
 checks={'target_title_exact':p['subject']==prep['expected_title'],'target_category_exact':int(p['category_id'])==prep['target_category_id'],'all_non_target_fields_preserved':preserve(p,fix['kind'])==preserve(expected,fix['kind']),'main_images_all_preserved':p['main_image']==before['main_image'],'all_SKU_data_and_declared_identity_mapping_match':n.canonical_skus(p['product_sku'])==n.canonical_skus(expected['product_sku'])};report['checks']=checks
 if fix['kind']=='category':checks['category_attributes_exact']=sorted(p['attributes'],key=lambda x:json.dumps(x,sort_keys=True))==sorted(prep['expected_attributes'],key=lambda x:json.dumps(x,sort_keys=True))
 if all(checks.values())and fix['kind']=='category':
  n.save(folder/'fields_overlay.json',{'state':'CATEGORY_FIELDS_FORMAL_PASS','id':pid,'at':n.now(),'before_category_id':prep['before_category_id'],'target_category_id':prep['target_category_id'],'expected_attributes':prep['expected_attributes'],'receipt':n.rel(folder/'update_receipt.json'),'receipt_sha256':n.sha(folder/'update_receipt.json'),'payload':n.rel(folder/'payload.xml'),'payload_sha256':n.sha(folder/'payload.xml'),'checks':checks,'compatibility':prep['compatibility'],**({'sku_reissue_mapping':report['sku_reissue_mapping'],'sku_reissue_mapping_sha256':n.sha(n.ROOT/report['sku_reissue_mapping'])}if mapping else{})})
 enc=api.top_call(cfg,'alibaba.icbu.product.id.encrypt',{'product_id':pid,'language':'ENGLISH'});n.save(folder/'encrypted_id.json',enc);sc=call('alibaba.icbu.product.score.get',{'product_id':enc['secret_id']});n.save(folder/'score.json',sc);result=sc.get('result',{});report['actual_score']=result.get('final_score');problem=result.get('problem_map')or{};problem=json.loads(problem)if isinstance(problem,str)else problem;report['diagnostics']={k:v for k,v in problem.get('extendProblemMap',{}).items()if v};report['state']='FORMAL_FIELDS_SCORE_PASS'if all(checks.values())and report['actual_score']is not None and Decimal(str(report['actual_score']))>=5 and not report['diagnostics']else'FIELDS_OR_SCORE_PENDING';n.save(folder/'verification.json',report);return {'id':pid,'state':report['state'],'actual_score':report['actual_score'],'failed':[k for k,v in checks.items()if not v],'diagnostics':report['diagnostics']}
def main():
 sys.stdout.reconfigure(encoding='utf8');ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['prepare','submit','verify']);ap.add_argument('--ids');args=ap.parse_args();ids=args.ids.split(',')if args.ids else list(FIXES);assert set(ids)<=set(FIXES);api,cfg=n.b.api_client();api.http_json=api.native_http_json
 for pid in ids:print(json.dumps(run(pid,args.mode,api,cfg),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
