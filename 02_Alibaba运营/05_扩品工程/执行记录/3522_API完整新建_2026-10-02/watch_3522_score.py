from pathlib import Path
import json,sys,datetime,time,importlib.util
sys.dont_write_bytecode=True
W=Path(__file__).parent;O=W/'3522_execution';P=Path(r'C:\Users\spq\Desktop\贝强')
s=importlib.util.spec_from_file_location('sdk3522scorewatch',P/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py');sdk=importlib.util.module_from_spec(s);s.loader.exec_module(sdk);config=sdk.load_config(Path.home()/'.config/beiqiang/alibaba-openapi.json')
secret=json.loads((O/'formal_get.flat.json').read_text(encoding='utf-8'))['product']['product_id'];H=O/'read_history';H.mkdir(exist_ok=True)
for attempt in range(20):
 if datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime(2026,10,2,18,0,tzinfo=datetime.timezone.utc):
  print('Explicit user stop deadline reached; no automatic resume',flush=True);break
 try:
  j=sdk.top_call(config,'alibaba.icbu.product.score.get',{'product_id':secret});stamp=datetime.datetime.now(datetime.timezone.utc);tag=stamp.strftime('%Y%m%dT%H%M%S%fZ');(H/(tag+'_formal_score.response.json')).write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8');d=j.get('alibaba_icbu_product_score_get_response',j)
  for name in ['formal_score.response.json','formal_score.flat.json']:(O/name).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
  (O/'score_timestamp.json').write_text(json.dumps({'observed_at':stamp.isoformat(),'score_source':'alibaba.icbu.product.score.get','response':d},ensure_ascii=False,indent=2),encoding='utf-8');v=d.get('result',{}).get('final_score');m=json.loads(d.get('result',{}).get('problem_map','{}'));active=[k for k,x in m.get('extendProblemMap',{}).items() if x is True];print('3522 score',stamp.isoformat(),v,'active',active,'error',d.get('error_response',{}).get('code'),flush=True)
  if v is not None and float(v)>=5.0:break
 except Exception as e:print('Read-only score transport',type(e).__name__,'no mutation',flush=True)
 if attempt<19:
  for _ in range(4):time.sleep(30)
print('Score observer ended; inspect real evidence',flush=True)
