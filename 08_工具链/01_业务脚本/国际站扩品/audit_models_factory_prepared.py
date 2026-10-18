"""Offline integration check against every exact-ID saved current Schema.
Checks unchanged gallery slots, category facts, SKU IDs/prices/stock/properties;
this is not a platform acceptance result.
"""
from copy import deepcopy
from collections import Counter
from xml.etree import ElementTree as E
import json,sys
import normalize_models_factory_gallery as n
def fingerprint(x):return E.tostring(x,encoding='unicode')if x is not None else None
def main():
 sys.stdout.reconfigure(encoding='utf8');scope=n.load(n.BASE/'范围.json');checked=[];errors=[]
 for z in scope['targets']:
  f=n.BASE/'商品'/z['id']
  if not(f/'prepared.json').exists():continue
  try:
   prep=n.load(f/'prepared.json');s=E.parse(f/'current_schema.xml').getroot();payload=E.parse(f/'payload.xml').getroot();original=n.contract.values_only(s,operation='update',field_ids=prep['fields'])
   assert set(x.get('id')for x in payload)==set(prep['fields'])<= {'scImages','productTitle','icbuCatProp','sku'}
   for node in original.find("./field[@id='scImages']/complex-value"):
    if node.get('id')!='scImages_'+str(z['gallery_slot']-1):assert fingerprint(node)==fingerprint(payload.find("./field[@id='scImages']/complex-value/field[@id='"+node.get('id')+"']")),'Unrelated gallery slot changed'
   assert fingerprint(original.find("./field[@id='productTitle']"))==fingerprint(payload.find("./field[@id='productTitle']")),'Title changed'
   if z['model_change']:
    mid=n.contract.model_field_definition(s).get('id')
    for node in original.find("./field[@id='icbuCatProp']/complex-value"):
     if node.get('id')!=mid:assert fingerprint(node)==fingerprint(payload.find("./field[@id='icbuCatProp']/complex-value/field[@id='"+node.get('id')+"']")),'Non-target category fact changed'
   if 'sku'in prep['fields']:
    a=deepcopy(original.find("./field[@id='sku']"));b=deepcopy(payload.find("./field[@id='sku']"))
    old=a.findall(".//field[@id='skuOuterId']/value");new=b.findall(".//field[@id='skuOuterId']/value");assert len(old)==len(new)
    for x,y in zip(old,new):assert y.text==prep['sku_code_changes'].get(x.text,x.text),'Unexpected SKU code';y.text=x.text
    assert fingerprint(a)==fingerprint(b),'SKU ID, price, stock or colour/size properties changed'
   n.pub.load_submission_manifest(f/'manifest.json','update',z['id']);checked.append(z['id'])
  except Exception as exc:errors.append({'id':z['id'],'type':type(exc).__name__,'message':str(exc)[:300]})
 result={'at':n.now(),'state':'OFFLINE_TARGET_DIFF_PASS'if not errors else'FAIL','prepared_ids_checked':len(checked),'expected_scope':len(scope['targets']),'errors':errors,'scope':'Saved current Schema versus intended incremental payload only; no live mutation or platform PASS inferred'};n.save(n.BASE/'准备载荷核验.json',result);print(json.dumps(result,ensure_ascii=False));assert not errors
if __name__=='__main__':main()
