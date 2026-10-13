"""Upload reviewed 725 assets once; stop on unknown outcome, no product write."""
from pathlib import Path
from datetime import datetime,timezone
import importlib.util,json,hashlib,sys,os
R=Path(r'C:\Users\spq\Desktop\贝强');O=Path(__file__).parent/'725_next_preparation_20261003'
selected=json.loads((O/'selected_assets_complete.json').read_text(encoding='utf-8'))
checks=json.loads((O/'completion_checks.json').read_text(encoding='utf-8'));assert checks['offline']=='PASS' and checks['model']=='BQ-CS063C'
assert len(selected)==16 and all(a['review']=='PASS_ACTUAL_STRUCTURE_AND_MARKS_VISUALLY_REVIEWED' for a in selected)
ledger=O/'upload_once_ledger.json'
def save(p,v):
 tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(tmp,p)
entries=json.loads(ledger.read_text())['uploads'] if ledger.exists() else []
assert all(e['status']=='UPLOADED_BUSINESS_VERIFIED' for e in entries),'Prior unverified upload: stop; do not retry'
for a in selected:
 assert hashlib.sha256(Path(a['path']).read_bytes()).hexdigest()==a['sha256'] and Path(a['path']).stat().st_size<=4*1024*1024
spec=importlib.util.spec_from_file_location('sdk',R/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py');sdk=importlib.util.module_from_spec(spec);spec.loader.exec_module(sdk)
config=sdk.load_config(sdk.DEFAULT_CONFIG);sdk.http_json=lambda request,timeout=60:sdk.native_http_json(request,timeout=45)
sys.path.insert(0,str(R/'08_工具链/01_业务脚本/国际站扩品'));from schema_publish_contract import safe_exception_evidence
for a in selected:
 existing=next((e for e in entries if e['role']==a['role']),None)
 if existing:assert existing['sha256']==a['sha256'];continue
 same=next((e for e in entries if e['sha256']==a['sha256'] and e['status']=='UPLOADED_BUSINESS_VERIFIED'),None)
 if same:
  e=dict(a,status='UPLOADED_BUSINESS_VERIFIED',official_url=same['official_url'],file_id=same['file_id'],request_id=same['request_id'],reused_role=same['role']);entries.append(e);save(ledger,{'model':'BQ-CS063C','uploads':entries,'product_create_calls':0});continue
 e=dict(a,status='STARTED_OUTCOME_UNKNOWN_DO_NOT_RETRY',started_at=datetime.now(timezone.utc).isoformat());entries.append(e);save(ledger,{'model':'BQ-CS063C','uploads':entries,'product_create_calls':0})
 try:response=sdk.redact_tokens(sdk.upload_image(config,Path(a['path']),None));error=sdk.api_error(response)
 except Exception as exc:response=None;error=safe_exception_evidence(exc,config)
 save(O/(a['role']+'_upload.json'),{'response':response,'error':error})
 result=(response or {}).get('upload_image_response') or {}
 if not error and result.get('photobank_url') and result.get('file_id'):
  url=result['photobank_url'];url='https:'+url if url.startswith('//') else url
  e.update(status='UPLOADED_BUSINESS_VERIFIED',official_url=url,file_id=str(result['file_id']),request_id=response.get('request_id'))
 else:e.update(status='OUTCOME_UNKNOWN_STOP_NO_RETRY' if response is None else 'BUSINESS_NOT_VERIFIED_STOP',error=error)
 save(ledger,{'model':'BQ-CS063C','uploads':entries,'product_create_calls':0})
 print(json.dumps({'role':a['role'],'status':e['status'],'file_id':e.get('file_id'),'request_id':e.get('request_id')},ensure_ascii=True),flush=True)
 if e['status']!='UPLOADED_BUSINESS_VERIFIED':raise SystemExit(2)
