"""Read products and scores directly from authorized Alibaba APIs, without Accio."""
from pathlib import Path
import argparse,json,sys,time,math,re
r=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(r/'.agents/skills/alibaba-openapi-operator/scripts'))
import alibaba_openapi as api
def business_fields(kind,response,pid):
 if api.api_error(response):return {kind+'BusinessPass':False}
 if kind=='product':
  product=response.get('product')
  if not isinstance(product,dict):return {'productBusinessPass':False}
  skus=product.get('product_sku',{}).get('skus',[])
  url=product.get('pc_detail_url','')
  valid=bool(product.get('subject') and product.get('status') and skus and re.fullmatch(r'https://www\.alibaba\.com/product-detail/[^/?]+_'+str(pid)+r'\.html',url))
  return {'productBusinessPass':valid,'status':product.get('status'),'display':product.get('display'),'title':product.get('subject'),'SKUCount':len(skus)}
 score=response.get('result')
 if not isinstance(score,dict):return {'scoreBusinessPass':False}
 try:
  value=float(score['final_score']);problems=score['problem_map']
  if isinstance(problems,str):problems=json.loads(problems)
  valid=math.isfinite(value) and 0<=value<=5 and isinstance(problems,dict) and isinstance(problems.get('extendProblemMap'),dict)
 except (KeyError,ValueError,TypeError):return {'scoreBusinessPass':False}
 return {'scoreBusinessPass':valid,'qualityScore':score['final_score'],'qualityProblemFlags':[k for k,v in problems['extendProblemMap'].items() if v] if valid else []}
def run():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--product-ids',required=True,help='Comma separated current product IDs')
 p.add_argument('--output',required=True,type=Path)
 args=p.parse_args();ids=[int(x.strip()) for x in args.product_ids.split(',')]
 assert len(ids)==len(set(ids)) and ids
 out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
 if any((out/f'{pid}_{kind}.json').exists() for pid in ids for kind in ['product','score']) or (out/'direct_audit_summary.json').exists():raise RuntimeError('Existing evidence: use a fresh output directory instead of overwriting')
 cfg=api.load_config(api.DEFAULT_CONFIG);results=[]
 for pid in ids:
  result={'productId':pid,'execution':'Alibaba OpenAPI directly; no Accio/WorkBuddy invocation'}
  for kind,method in [('product','alibaba.icbu.product.get'),('score','alibaba.icbu.product.score.get')]:
   file=out/f'{pid}_{kind}.json'
   if file.exists():raise RuntimeError('Existing evidence: use a fresh output directory instead of overwriting')
   params={'product_id':pid}
   if kind=='product':params['language']='ENGLISH'
   response=api.top_call(cfg,method,params)
   file.write_text(json.dumps(api.redact_tokens(response),ensure_ascii=False,indent=2),encoding='utf-8')
   result[kind+'ResponseReceived']=not bool(api.api_error(response))
   result[kind+'Evidence']=str(file)
   result.update(business_fields(kind,response,pid))
   time.sleep(1)
  results.append(result)
  (out/'direct_audit_summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(results,ensure_ascii=False))
 if not all(x.get('productBusinessPass') and x.get('scoreBusinessPass') for x in results):raise RuntimeError('Incomplete business responses; inspect saved evidence')
if __name__=='__main__':run()
