from pathlib import Path
import json,sys,datetime,time,importlib.util
sys.dont_write_bytecode=True
W=Path(__file__).parent;O=W/'3522_execution';P=Path(r'C:\Users\spq\Desktop\贝强')
s=importlib.util.spec_from_file_location('sdk3522watch',P/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py');sdk=importlib.util.module_from_spec(s);s.loader.exec_module(sdk);config=sdk.load_config(Path.home()/'.config/beiqiang/alibaba-openapi.json')
secret=json.loads((O/'formal_get.flat.json').read_text(encoding='utf-8'))['product']['product_id'];pid='1601969920294';H=O/'read_history';H.mkdir(exist_ok=True)
def call(method,params,name):
 assert method in ['alibaba.icbu.product.get','alibaba.icbu.product.schema.render','alibaba.icbu.product.score.get','alibaba.icbu.product.sku.inventory.get']
 j=sdk.top_call(config,method,params);stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');(H/(stamp+'_'+name+'.response.json')).write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8');keys=[k for k in j if k.endswith('_response') and k!='error_response'];d=j[keys[0]] if len(keys)==1 else j
 (O/(name+'.response.json')).write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8');(O/(name+'.flat.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');return d
for attempt in range(20):
 try:
  g=call('alibaba.icbu.product.get',{'product_id':secret,'language':'ENGLISH'},'formal_get');p=g['product'];print('3522 observation',datetime.datetime.now(datetime.timezone.utc).isoformat(),p['status'],p['display'],flush=True)
  if p['status']=='approved' and p['display']=='Y':
   r=call('alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'language':'en_US'}},'formal_render');iv=call('alibaba.icbu.product.sku.inventory.get',{'product_id':pid,'language':'en_US'},'formal_inventory');sc=call('alibaba.icbu.product.score.get',{'product_id':secret},'formal_score');score={'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'score_source':'alibaba.icbu.product.score.get','response':sc};(O/'score_timestamp.json').write_text(json.dumps(score,ensure_ascii=False,indent=2),encoding='utf-8')
   print('render',len(r.get('data','')),'score',sc.get('result',{}).get('final_score'),'error',sc.get('error_response',{}).get('code'),flush=True)
   if r.get('data'):break
 except Exception as e:print('Read transport/error:',type(e).__name__,'no mutation attempted',flush=True)
 if attempt<19:
  for _ in range(4):time.sleep(30)
print('Read-only watch ended; root will inspect actual saved state',flush=True)
