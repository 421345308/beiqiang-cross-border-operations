from pathlib import Path
import json,sys,hashlib,datetime,re,importlib.util,xml.etree.ElementTree as E,shutil
sys.dont_write_bytecode=True
W=Path(__file__).parent;O=W/'9968_execution';P=Path(r'C:\Users\spq\Desktop\贝强');T8=Path(r'C:\Users\spq\Documents\Codex\2026-10-02\task-8')
spec=importlib.util.spec_from_file_location('approved_sdk_9968',P/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py');sdk=importlib.util.module_from_spec(spec);spec.loader.exec_module(sdk)
config=sdk.load_config(Path.home()/'.config/beiqiang/alibaba-openapi.json')
if len(sys.argv)>2 and sys.argv[2]=='--native-readonly':
 assert sys.argv[1] in ['read','score'],'Alternate verified transport limited to reads'
 sys.path.insert(0,str(T8));from sdk_runtime_5998 import load
 sdk.http_json=load().http_json
def save(n,j):(O/n).write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8')
def call(method,params,name):
 save(name+'.params.json',params);j=sdk.top_call(config,method,params);save(name+'.response.json',j)
 # SDK CLI flattens TOP envelope; keep the official envelope and a flat evidence copy.
 keys=[k for k in j if k.endswith('_response') and k!='error_response'];d=j[keys[0]] if len(keys)==1 else j
 assert not j.get('error_response'),j
 save(name+'.flat.json',d);return d
def publisher():
 s=importlib.util.spec_from_file_location('publisher9968',P/'08_工具链/01_业务脚本/国际站扩品/publish_hot_rank_hr_a_batch.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
action=sys.argv[1]
if action=='bank':
 d=call('alibaba.icbu.photobank.list',{'extra_context':{},'location_type':'ALL_GROUP','current_page':1,'page_size':50},'bank_reconcile_D4');print(json.dumps(d,ensure_ascii=False)[:1600],flush=True)
elif action=='reconcile':
 receipts=[p.name for p in O.glob('*') if any(q in p.name for q in ['publish_once','publish_receipt','formal_add','upload_ledger'])];print('Existing write artifacts',receipts,flush=True)
 rows=[]
 for page in range(1,20):
  cached=O/('live_catalog_'+str(page)+'.flat.json')
  d=json.loads(cached.read_text(encoding='utf-8')) if cached.exists() else call('alibaba.icbu.product.list',{'language':'ENGLISH','current_page':page,'page_size':30},'live_catalog_'+str(page))
  v=d.get('products',[]);v=v.get('product',[]) if isinstance(v,dict) else v;rows.extend(v);print('Read catalog page',page,flush=True)
  if len(v)<30:break
 save('live_catalog.json',rows);hits=[x for x in rows if any(s in str(x.get('red_model',''))+' '+str(x.get('subject','')) for s in ['BQ-MJ9968','2532759','qdnx','9968'])];save('creation_reconciliation.json',{'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'artifact_names':receipts,'catalog_count':len(rows),'matching_identity_products':hits,'unknown_submit_ledger':bool(receipts),'conclusion':'Do not create if an identity match or unresolved write ledger exists'});print('catalog',len(rows),'identity matches',len(hits),flush=True)
 assert not receipts and not hits,'Existing submission/identity must be reconciled before creation'
 # Formal HR021-C source read: no mutation.
 p=next(x for x in rows if int(x['id'])==1601943577329);d=call('alibaba.icbu.product.get',{'product_id':p['product_id'],'language':'ENGLISH'},'HR021C_formal_get');print('HR021-C formal',d.get('product',{}).get('red_model'),d.get('product',{}).get('status'),flush=True)
elif action=='upload':
 for n in ['visual_gate.json','dedup_gate.json']:assert json.loads((O/n).read_text(encoding='utf-8'))['verdict']=='PASS'
 manifest=json.loads((O/'asset_manifest.json').read_text(encoding='utf-8'));rows=[(x['name'],Path(x['path']),x['sha256']) for x in manifest['assets']]
 for col,num in [('Grey','00'),('Green','01'),('Blue','02')]:
  p=O/'assets'/('9968_'+col+'.jpg');source=W/'MaryJane_selection/9968/published'/(num+'.jpg');shutil.copyfile(source,p);rows.append((col,p,hashlib.sha256(p.read_bytes()).hexdigest()))
 lp=O/'upload_ledger.json';ledger=json.loads(lp.read_text(encoding='utf-8')) if lp.exists() else {'scope':'9968 only','uploads':[]}
 for name,p,digest in rows:
  assert hashlib.sha256(p.read_bytes()).hexdigest()==digest;prior=next((x for x in ledger['uploads'] if x['name']==name),None)
  if prior:
   assert prior['sha256']==digest and prior['status']=='VERIFIED','Unknown previous upload must be reconciled';continue
  # Use style-specific bank filename for every remaining actual upload.
  unique=O/'upload_sources';unique.mkdir(exist_ok=True);q=unique/('9968_'+name+'.jpg');shutil.copyfile(p,q);p=q
  item={'name':name,'path':str(p),'sha256':digest,'status':'STARTED_OUTCOME_UNKNOWN','time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()};ledger['uploads'].append(item);save(lp.name,ledger)
  try:
   j=sdk.upload_image(config,p,None);save(name+'.upload.response.json',j);d=j.get('alibaba_icbu_photobank_upload_response',j);m=d.get('upload_image_response',d.get('model',d));url=m.get('photobank_url');fid=m.get('file_id');assert url and fid and not j.get('error_response') and d.get('biz_success') is not False
   if url.startswith('//'):url='https:'+url
   assert re.fullmatch(r'https://sc04\.alicdn\.com/kf/([^/.]+)/286385890/\1\.(jpg|jpeg|png)',url),url
   item.update(status='VERIFIED',official_url=url,file_id=str(fid),request_id=d.get('request_id',j.get('request_id')));save(lp.name,ledger);print(name,'verified',flush=True)
  except Exception as e:
   item.update(error_type=type(e).__name__,status='OUTCOME_UNKNOWN_STOP_NO_RETRY');save(lp.name,ledger);raise
 assert len(ledger['uploads'])==13
elif action=='publish':
 for n in ['visual_gate.json','dedup_gate.json']:assert json.loads((O/n).read_text(encoding='utf-8'))['verdict']=='PASS'
 v=json.loads((O/'visual_gate.json').read_text(encoding='utf-8'))
 for name,digest in v['image_hashes'].items():assert hashlib.sha256((O/'assets'/name).read_bytes()).hexdigest()==digest
 pub=publisher();listing=pub.load_submission_manifest(O/'publish_manifest.json','create',None);lp=O/'publish_once_ledger.json'
 log={'style':'9968','model':'BQ-MJ9968','status':'STARTED_OUTCOME_UNKNOWN','method':'alibaba.icbu.product.schema.add','time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'xml_sha256':hashlib.sha256(listing['xml'].encode()).hexdigest(),'other_products_written':[]}
 with lp.open('x',encoding='utf-8') as h:json.dump(log,h,indent=2)
 result=pub.api_submit(sdk,config,listing,False);save('publish_receipt.json',result);log.update(status=result['status'],product_id=result.get('product_id'),content_status=result.get('content_status'),refs=result.get('refs'));save(lp.name,log);print(json.dumps(log),flush=True)
elif action in ['read','score']:
 pid=json.loads((O/'publish_once_ledger.json').read_text(encoding='utf-8'))['product_id'];assert pid
 if (O/'formal_get.flat.json').exists():secret=json.loads((O/'formal_get.flat.json').read_text(encoding='utf-8'))['product']['product_id']
 else:secret=call('alibaba.icbu.product.id.encrypt',{'product_id':pid,'language':'ENGLISH'},'formal_encrypt')['secret_id']
 if action=='read':
  d=call('alibaba.icbu.product.get',{'product_id':secret,'language':'ENGLISH'},'formal_get');p=d['product'];print(json.dumps({'id':pid,'model':p.get('red_model'),'status':p.get('status'),'display':p.get('display'),'url':p.get('pc_detail_url'),'request_id':d.get('request_id')}),flush=True)
  r=call('alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'language':'en_US'}},'formal_render');print('render length',len(r.get('data','')),flush=True)
  iv=call('alibaba.icbu.product.sku.inventory.get',{'product_id':pid,'language':'en_US'},'formal_inventory');print('inventory read retained',flush=True)
 d=call('alibaba.icbu.product.score.get',{'product_id':secret},'formal_score');save('score_timestamp.json',{'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'score_source':'alibaba.icbu.product.score.get','response':d});print(json.dumps(d,ensure_ascii=False),flush=True)
