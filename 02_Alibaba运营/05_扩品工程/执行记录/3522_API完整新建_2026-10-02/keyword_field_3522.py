from pathlib import Path
import json,sys,datetime,hashlib,importlib.util
sys.dont_write_bytecode=True
W=Path(__file__).parent;O=W/'3522_execution';D=O/'keyword_field_repair';D.mkdir(exist_ok=True);P=Path(r'C:\Users\spq\Desktop\贝强');PID='1601969920294';KW='mens suede slip on loafers'
def save(n,j):(D/n).write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8')
action=sys.argv[1]
if action in ['upload','publish','send']:
 assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime(2026,10,2,18,0,tzinfo=datetime.timezone.utc),'User stop deadline reached; no automatic resume or new Beiqiang writes'
if action=='prepare':
 g=json.loads((O/'formal_get.flat.json').read_text(encoding='utf-8'));p=g['product'];attrs={int(x['attribute_id']):x['value_name'] for x in p['attributes']};assert attrs[3]=='BQ-L3522' and p['product_type']=='sourcing';assert p['subject']=="Men's Suede Slip-On Loafers with Perforated Side Panels"
 params={'product_id':p['product_id'],'product_type':'sourcing','language':'ENGLISH','keywords':[KW]};assert set(params)=={'product_id','product_type','language','keywords'}
 save('params.json',params);save('before_formal_get.json',g);save('review.json',{'target_id':PID,'model':'BQ-L3522','scope':['keywords'],'expected_keywords':[KW],'business_context_only':['product_id encrypted from same formal get','product_type sourcing from same product','language ENGLISH'],'official_api_reference':'https://developer.alibaba.com/docs/api.htm?apiId=27010','schema_diagnosis_reference':'../keyword_protocol/official_keyword_shape_evidence.json','state_requirement_before_write':'approved/Y fresh formal get','single_attempt_no_retry':True,'evidence_basis':'Parent-reviewed factual longtail for real suede slip-on loafer; no market-volume or performance claim'});print('Prepared official field-update keywords only; no SKU/material/gallery/trade fields',flush=True)
elif action=='send':
 params=json.loads((D/'params.json').read_text(encoding='utf-8'));g=json.loads((O/'formal_get.flat.json').read_text(encoding='utf-8'));p=g['product'];assert p['status']=='approved' and p['display']=='Y';assert p['product_id']==params['product_id'];assert (datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromtimestamp((O/'formal_get.flat.json').stat().st_mtime,datetime.timezone.utc)).total_seconds()<300
 assert set(params)=={'product_id','product_type','language','keywords'} and params['keywords']==[KW];s=importlib.util.spec_from_file_location('sdk3522kwfield',P/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py');sdk=importlib.util.module_from_spec(s);s.loader.exec_module(sdk);config=sdk.load_config(Path.home()/'.config/beiqiang/alibaba-openapi.json');log={'product_id':PID,'model':'BQ-L3522','method':'alibaba.icbu.product.update.field','scope':['keywords'],'status':'STARTED_OUTCOME_UNKNOWN','attempted_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'params_sha256':hashlib.sha256(json.dumps(params,sort_keys=True).encode()).hexdigest()}
 with (D/'write_once_ledger.json').open('x',encoding='utf-8') as h:json.dump(log,h,indent=2)
 try:
  j=sdk.top_call(config,'alibaba.icbu.product.update.field',params);save('response.json',j);d=j.get('alibaba_icbu_product_update_field_response',j)
  if j.get('error_response'):log.update(status='BUSINESS_REJECTED',error=j['error_response'])
  elif str(d.get('product_id'))==params['product_id']:log.update(status='BUSINESS_ACCEPTED_PENDING_READBACK',request_id=d.get('request_id'),returned_encrypted_id=d.get('product_id'))
  else:log.update(status='UNESTABLISHED_RESPONSE_STOP',response_keys=list(j))
 except Exception as e:
  s=importlib.util.spec_from_file_location('contractkwfield',P/'08_工具链/01_业务脚本/国际站扩品/schema_publish_contract.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c);log.update(status='WRITE_OUTCOME_UNKNOWN_STOP_NO_RETRY',failure_evidence=c.safe_exception_evidence(e,config))
 save('write_once_ledger.json',log);print(json.dumps(log),flush=True)
else:raise ValueError(action)
