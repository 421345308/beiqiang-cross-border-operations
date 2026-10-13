"""Exact-target brand repair. Prepare/verify use independent reads; writes are serial once.

The input manifest is a business evidence list, not an inventory or source authority.
Current exact-target product.get and render determine all preserved values.
"""
from pathlib import Path
from datetime import datetime,timezone
from xml.etree import ElementTree as E
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor,as_completed
from decimal import Decimal
import argparse,json,sys,importlib.util,hashlib

def main():
 ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','submit','verify']);ap.add_argument('--manifest',required=True);ap.add_argument('--workers',type=int,default=4);args=ap.parse_args()
 r=Path(__file__).resolve().parents[3];mf=Path(args.manifest).resolve();data=json.loads(mf.read_text(encoding='utf8'));targets=[x for x in data['rows'] if x['status']=='NEEDS_TARGET_ATTRIBUTE_REPAIR'];assert len({x['product_id'] for x in targets})==len(targets)
 n=mf.parent.parent;assert n.is_relative_to(r/'02_Alibaba运营')
 sys.path.insert(0,str(Path(__file__).parent));import publish_hot_rank_hr_a_batch as pub
 spec=importlib.util.spec_from_file_location('api',r/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py');api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api);cfg=api.load_config(Path.home()/'.config/beiqiang/alibaba-openapi.json')
 save=lambda f,v:f.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
 now=lambda:datetime.now(timezone.utc).isoformat()
 def work(row):
  st=row['style'];pid=str(row['product_id']);p=n/(st+'准备');o=p/'品牌与中底属性修正';o.mkdir(exist_ok=True);ledger=o/'单次更新账本.json'
  assert row['status']=='NEEDS_TARGET_ATTRIBUTE_REPAIR' and p.is_dir()
  if args.mode=='prepare':
   if ledger.exists():return {'style':st,'status':'EXISTING_WRITE_LEDGER_READBACK_ONLY'}
   got=api.top_call(cfg,'alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'});save(o/'修正前正式商品.json',got);product=got['product'];a={str(x['attribute_id']):x.get('value_name') for x in product['attributes']};assert a.get('3')=='BQ-LQ'+st
   if product['status']!='approved' or product['display']!='Y':return {'style':st,'status':'PENDING_CURRENT_APPROVAL'}
   if a.get('2')=='Beiqiang':save(o/'已有有效品牌核验.json',{'style':st,'product_id':pid,'status':'VERIFIED_EXISTING_NO_WRITE','observed_at':now(),'request_id':got['request_id']});return {'style':st,'status':'VERIFIED_EXISTING_NO_WRITE'}
   response=api.top_call(cfg,'alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(product['category_id']),'language':'en_US'}});save(o/'当前Schema回执.json',response);assert response.get('data');schema=E.fromstring(response['data']);current=o/'当前Schema.xml';current.write_text(response['data'],encoding='utf8')
   definition=schema.find(".//field[@id='p-2']");assert definition is not None and definition.get('type')=='input'
   root=pub.values_only(schema,operation='update',field_ids=['icbuCatProp']);attrs=root.find("./field[@id='icbuCatProp']/complex-value");before_other=[E.tostring(x,encoding='unicode') for x in attrs if x.get('id')!='p-2'];brand=attrs.find("./field[@id='p-2']")
   if brand is None:brand=E.SubElement(attrs,'field',{'id':'p-2','type':'input'})
   else:
    for child in list(brand):brand.remove(child)
   # This exact inputValue representation was formally persisted on2572/2573.
   E.SubElement(brand,'value',{'inputValue':'Beiqiang'}).text='-2'
   assert before_other==[E.tostring(x,encoding='unicode') for x in attrs if x.get('id')!='p-2']
   assert {x.get('id') for x in root}=={'icbuCatProp'}
   payload=o/'单属性载荷.xml';payload.write_text(E.tostring(root,encoding='unicode'),encoding='utf8')
   (o/'修正依据.md').write_text('# 贝强品牌有效文本修正\n\n负责人授权本批统一Beiqiang品牌供货。当前原商品正式属性无有效品牌文本，使用当前目标Schema的input字段和已正式验证的inputValue="Beiqiang"编码补写；不改变真实来源，也不新增该款已在贝强生产的事实。\n\n其余属性全部取本款当次Schema并逐节点保全。只提交icbuCatProp；标题、色码、SKU、主图/详情、交易、库存和视频不提交，修复后以正式商品逐字段核验保护结果。\n',encoding='utf8')
   manifest={'operation':'update','product_id':pid,'category_id':product['category_id'],'facts_reviewed':True,'source_evidence':['修正依据.md','修正前正式商品.json'],'current_schema':current.name,'current_schema_sha256':sha(current),'schema_request_id':response['request_id'],'schema_acquired_at':now(),'payload_xml':payload.name,'field_ids':['icbuCatProp'],'dependency_ids':[],'expected_model':'BQ-LQ'+st}
   mp=o/'单属性提交清单.json';save(mp,manifest);listing=pub.load_submission_manifest(mp,'update',pid);save(o/'本地合同核验.json',listing);save(o/'属性保护核验.json',{'status':'PASS_PREWRITE_ONLY_BRAND_CHANGE','protected_attribute_ids':[x.get('id') for x in attrs if x.get('id')!='p-2'],'before_get_request':got['request_id'],'schema_request':response['request_id'],'observed_at':now()});return {'style':st,'product_id':pid,'status':'PREPARED'}
  if args.mode=='submit':
   if ledger.exists():return {'style':st,'product_id':pid,'status':'EXISTING_WRITE_LEDGER_READBACK_ONLY'}
   if not (o/'单属性提交清单.json').exists():return {'style':st,'status':'NO_PREPARED_PAYLOAD_NO_WRITE'}
   listing=pub.load_submission_manifest(o/'单属性提交清单.json','update',pid)
   with ledger.open('x',encoding='utf8') as f:json.dump({'status':'STARTED_OUTCOME_UNKNOWN','product_id':pid,'attempted_at':now()},f)
   result=pub.api_submit(api,cfg,listing,False,update_product_id=pid);save(o/'正式更新回执.json',result);save(ledger,{'status':result['status'],'product_id':pid,'refs':result.get('refs'),'attempted_at':result['attempted_at']});return {'style':st,'product_id':pid,'status':result['status']}
  if not ledger.exists():return {'style':st,'status':'NO_WRITE_LEDGER'}
  got=api.top_call(cfg,'alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'});save(o/'最新正式回读.json',got);pafter=got['product'];before=json.loads((o/'修正前正式商品.json').read_text(encoding='utf8'))['product'];assert pafter['product_id']==before['product_id'];a={str(x['attribute_id']):x.get('value_name') for x in pafter['attributes']};assert a.get('3')=='BQ-LQ'+st
  protected={k:pafter.get(k)==v for k,v in before.items() if k not in ['attributes','gmt_modified','status','display']};other_before=[x for x in before['attributes'] if str(x['attribute_id'])!='2'];other_after=[x for x in pafter['attributes'] if str(x['attribute_id'])!='2'];preserved=other_before==other_after and all(protected.values());ready=pafter['status']=='approved' and pafter['display']=='Y';passed=ready and a.get('2')=='Beiqiang' and preserved
  report={'style':st,'product_id':pid,'observed_at':now(),'status':pafter['status'],'display':pafter['display'],'scope_result':'MISMATCH_REQUIRES_DIAGNOSIS' if not preserved or a.get('2')!='Beiqiang' else 'PASS' if passed else 'PENDING_REVIEW','brand':a.get('2'),'unsubmitted_product_fields_preserved':protected,'other_attributes_preserved':other_before==other_after,'changed_product_fields':sorted(k for k in set(before)|set(pafter) if before.get(k)!=pafter.get(k)),'source_get_request':got['request_id'],'actual_score':None,'scope':'Only brand text; saved original ID, other attributes and every unsubmitted formal product field compared; no browser PASS inferred'}
  if ready:
   response=api.top_call(cfg,'alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(pafter['category_id']),'language':'en_US'}});save(o/'修正后Schema回执.json',response)
   if response.get('data'):
    (o/'修正后Schema.xml').write_text(response['data'],encoding='utf8');brand=E.fromstring(response['data']).find(".//field[@id='p-2']/value");report['schema_brand_match']=brand is not None and brand.get('inputValue')=='Beiqiang';passed=passed and report['schema_brand_match'];report['scope_result']='PASS' if passed else 'MISMATCH_REQUIRES_DIAGNOSIS'
   else:report['schema_brand_match']=None;report['scope_result']='PENDING_EDITABLE_SCHEMA'
   enc=api.top_call(cfg,'alibaba.icbu.product.id.encrypt',{'product_id':pid,'language':'ENGLISH'});assert enc.get('secret_id');score=api.top_call(cfg,'alibaba.icbu.product.score.get',{'product_id':enc['secret_id']});save(o/'实际评分回读.json',score);res=score.get('result',{});report['actual_score']=res.get('final_score');report['score_source']='alibaba.icbu.product.score.get / '+str(score.get('request_id'));report['score_observed_at']=now();problem=res.get('problem_map');problem=json.loads(problem) if isinstance(problem,str) else problem
   if problem:
    diag={'flags':{k:v for k,v in problem.get('extendProblemMap',{}).items() if v is True},'deductions':{k:v for k,v in problem.get('ruleScoreMap',{}).items() if Decimal(str(v))!=0},'checks_not_run':[k for k,v in problem.get('extendCheckMap',{}).items() if v is False],'error_reasons':problem.get('errorReasonList',[])};diag['status']='clear' if not diag['flags'] and not diag['deductions'] and not diag['error_reasons'] else 'unresolved';report['score_diagnostics']=diag
   report['score_status']='PASS_SCORE_GATE' if report['actual_score'] is not None and Decimal(str(report['actual_score']))>=5 and report.get('score_diagnostics',{}).get('status')=='clear' else 'PENDING_OR_BELOW_TARGET'
  save(o/'修正正式核验.json',report);return {k:report[k] for k in ['style','product_id','scope_result','status','display','brand','actual_score']}
 results=[]
 def collect(row):
  try:return work(row)
  except Exception as exc:
   return {'style':row['style'],'product_id':row['product_id'],'status':'ERROR_CHECK_OBJECT_EVIDENCE','exception_type':type(exc).__name__}
 if args.mode=='submit':
  for row in targets:
   result=collect(row);results.append(result);print(json.dumps(result),flush=True)
 else:
  with ThreadPoolExecutor(max_workers=min(max(args.workers,1),4)) as executor:
   for f in as_completed([executor.submit(collect,row) for row in targets]):result=f.result();results.append(result);print(json.dumps(result),flush=True)
 save(mf.parent/('品牌修复_'+args.mode+'汇总.json'),{'observed_at':now(),'target_manifest_sha256':sha(mf),'mode':args.mode,'scope_count':len(targets),'rows':results})
 if any(x.get('status')=='ERROR_CHECK_OBJECT_EVIDENCE' for x in results):sys.exit(1)

if __name__=='__main__':main()
