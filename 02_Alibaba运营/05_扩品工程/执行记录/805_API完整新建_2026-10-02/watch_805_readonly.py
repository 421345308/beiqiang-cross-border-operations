from pathlib import Path
import json,sys,datetime,time,importlib.util
sys.dont_write_bytecode=True
W=Path(__file__).parent;O=W/'805_execution';P=Path(r'C:\Users\spq\Desktop\贝强');H=O/'read_history';H.mkdir(exist_ok=True)
s=importlib.util.spec_from_file_location('sdk805readonlywatch',P/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py');sdk=importlib.util.module_from_spec(s);s.loader.exec_module(sdk);config=sdk.load_config(Path.home()/'.config/beiqiang/alibaba-openapi.json');default_http=sdk.http_json
sys.path.insert(0,str(Path(r'C:\Users\spq\Documents\Codex\2026-10-02\task-8')));from sdk_runtime_5998 import load;native_http=load().http_json
secret=json.loads((O/'formal_encrypt.flat.json').read_text(encoding='utf-8'))['secret_id'];pid='1601969877983';stop=datetime.datetime(2026,10,2,18,tzinfo=datetime.timezone.utc)
def call(method,params,name):
 assert method in ['alibaba.icbu.product.get','alibaba.icbu.product.schema.render','alibaba.icbu.product.score.get']
 j=sdk.top_call(config,method,params);stamp=datetime.datetime.now(datetime.timezone.utc);tag=stamp.strftime('%Y%m%dT%H%M%S%fZ');(H/(tag+'_'+name+'.response.json')).write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8');keys=[k for k in j if k.endswith('_response') and k!='error_response'];d=j[keys[0]] if len(keys)==1 else j
 if not d.get('error_response'):
  (O/(name+'.response.json')).write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8');(O/(name+'.flat.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
 if name=='formal_score' and d.get('result',{}).get('final_score') is not None:(O/'score_timestamp.json').write_text(json.dumps({'observed_at':stamp.isoformat(),'score_source':method,'response':d},ensure_ascii=False,indent=2),encoding='utf-8')
 return d
attempt=0
while datetime.datetime.now(datetime.timezone.utc)<stop:
 attempt+=1;sdk.http_json=default_http if attempt%2 else native_http
 try:
  g=call('alibaba.icbu.product.get',{'product_id':secret,'language':'ENGLISH'},'formal_get');p=g.get('product',{});print('805 formal',datetime.datetime.now(datetime.timezone.utc).isoformat(),p.get('status'),p.get('display'),'error',g.get('error_response',{}).get('code'),flush=True)
  if p.get('status')=='approved' and p.get('display')=='Y':
   if datetime.datetime.now(datetime.timezone.utc)>=stop:break
   time.sleep(2);r=call('alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'language':'en_US'}},'formal_render')
   if datetime.datetime.now(datetime.timezone.utc)>=stop:break
   time.sleep(2);sc=call('alibaba.icbu.product.score.get',{'product_id':secret},'formal_score');v=sc.get('result',{}).get('final_score');m=json.loads(sc.get('result',{}).get('problem_map','{}'));active=[k for k,x in m.get('extendProblemMap',{}).items() if x is True];print('805 render',len(r.get('data','')),'actual score',v,'active',active,'error',sc.get('error_response',{}).get('code'),flush=True)
   if r.get('data') and v is not None and float(v)>=5:print('805 approved nonempty render and actual5 core gates reached',flush=True);break
 except Exception as e:print('805 read transport',type(e).__name__,'no mutation',flush=True)
 if '--once' in sys.argv:break
 # 2-minute read cadence; small waits let root continue commentary and handle steering.
 for _ in range(4):
  if datetime.datetime.now(datetime.timezone.utc)>=stop:break
  time.sleep(min(30,max(0,(stop-datetime.datetime.now(datetime.timezone.utc)).total_seconds())))
print('805 read-only observer stopped; no automatic resume or writes',flush=True)
