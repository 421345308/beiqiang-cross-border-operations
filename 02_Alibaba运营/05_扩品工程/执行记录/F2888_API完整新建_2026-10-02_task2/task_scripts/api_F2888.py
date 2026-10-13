from pathlib import Path
import sys,json,importlib.util,datetime,hashlib,shutil
sys.dont_write_bytecode=True
P=Path.home()/'Desktop'/'贝强'
W=Path(__file__).resolve().parent
O=W/'F2888_execution';O.mkdir(exist_ok=True)
assert not (O/'PAUSED_USER_2026-10-02.json').exists(),'Explicit user pause; no automatic resume'
s=importlib.util.spec_from_file_location('approved_sdk_boots',P/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py')
sdk=importlib.util.module_from_spec(s);s.loader.exec_module(sdk)
config=None if sys.argv[1] in ['reconcile-D2','publish'] else sdk.load_config(Path.home()/'.config/beiqiang/alibaba-openapi.json')
assert json.loads((O/'resume_authorization.json').read_text(encoding='utf-8'))['authorized'] is True
def save(n,j):(O/n).write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8')
def call(method,params,name):
 save(name+'.params.json',params)
 j=sdk.top_call(config,method,params);save(name+'.response.json',j)
 keys=[k for k in j if k.endswith('_response') and k!='error_response'];d=j[keys[0]] if len(keys)==1 else j
 if j.get('error_response'):raise RuntimeError(j['error_response'])
 save(name+'.flat.json',d);return d
if sys.argv[1] in ['womens-leaves','boots-leaves']:
 from concurrent.futures import ThreadPoolExecutor
 ids=[201768405,201772403,201777004,201769505,201339011] if sys.argv[1]=='boots-leaves' else [201781201,201331710,201153804,202240827,201345410,201337913]
 def inspect(cat):
  d=call('alibaba.icbu.category.get.new',{'cat_id':cat},'category_'+str(cat));print(json.dumps(d,ensure_ascii=False),flush=True)
 with ThreadPoolExecutor(max_workers=2) as ex:list(ex.map(inspect,ids))
elif sys.argv[1]=='category':
 cat=int(sys.argv[2]);d=call('alibaba.icbu.category.get.new',{'cat_id':cat},'category_'+str(cat));print(json.dumps(d,ensure_ascii=False),flush=True)
elif sys.argv[1]=='preflight-read':
 assert not (O/'publish_once_ledger.json').exists(),'Existing create ledger requires reconciliation, never another creation'
 d=call('alibaba.icbu.product.list',{'language':'ENGLISH','current_page':1,'page_size':30},'recent_catalog')
 rows=d.get('products',[]);rows=rows.get('product',[]) if isinstance(rows,dict) else rows
 hits=[r for r in rows if 'BQ-WBF2888' in str(r.get('red_model')) or r.get('subject')=="Women's Quilted Winter Boots with Plush Lining and Side Zipper"]
 save('creation_reconciliation.json',{'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'recent_catalog_count':len(rows),'matches':hits,'scope':'Latest first page only plus original local snapshots; no global identity clearance claimed','no_local_create_ledger':True})
 assert not hits,'Possible prior F2888 creation; reconcile before submit'
 secret=call('alibaba.icbu.product.id.encrypt',{'product_id':'1601943775160','language':'ENGLISH'},'old_encrypt')['secret_id']
 p=call('alibaba.icbu.product.get',{'product_id':secret,'language':'ENGLISH'},'old_formal_get')
 model=p['product'].get('red_model') or next((a.get('value_name') for a in p['product'].get('attributes',[]) if a.get('attribute_name')=='Model Number'),None)
 assert p['product']['product_id']==secret and model=='HR056-A'
 print('Scoped preflight read complete; exact HR056-A retained; no F2888 match in latest page.',flush=True)
elif sys.argv[1]=='reconcile-D2':
 ledger=json.loads((O/'upload_ledger.json').read_text(encoding='utf-8'));item=next(x for x in ledger['uploads'] if x['name']=='D2');assert item['status']=='OUTCOME_UNKNOWN_STOP_NO_RETRY'
 bank=json.loads((O/'bank_reconciliation.flat.json').read_text(encoding='utf-8'));rows=bank['pagination_query_list']['list'];prior=next(x for x in ledger['uploads'] if x['name']=='D1')
 assert any(str(x['id'])==prior['file_id'] for x in rows),'Bank page must cover immediately prior verified D1'
 assert not any(x.get('file_name')==Path(item['path']).name for x in rows),'Possible D2 upload: reconcile actual bytes, no automatic retry'
 digest=hashlib.sha256(Path(item['path']).read_bytes()).hexdigest();assert digest==item['sha256']
 record={'verdict':'RECONCILED_NOT_SENT_ONE_IMAGE_RETRY_ALLOWED','failed_attempt':dict(item),'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'bank_request_id':bank['request_id'],'bank_covers_prior_D1':True,'matching_D2_rows':[],'source_sha256':digest,'transport_evidence':'Original captured failure stack: socket.create_connection -> socket.connect WinError10060, before HTTPS connection and request body; no HTTP upload transmitted','next_action':'Exactly one unchanged hash D2 retry; never retry committed assets or product creation'}
 retry_number=int(item.get('retry_count',0))+1;assert retry_number<=3,'Image retry budget exhausted'
 name='D2_failed_transport_reconciliation_'+str(retry_number)+'.json';save(name,record);item.update(status='RETRY_ALLOWED_AFTER_RECONCILIATION',retry_authorization=name);save('upload_ledger.json',ledger);print('D2 reconciled; one hash-bound retry authorized.',flush=True)
elif sys.argv[1] in ['upload','upload-remaining']:
 gate=json.loads((O/'visual_gate.json').read_text(encoding='utf-8'));assert gate['verdict']=='PASS'
 assert json.loads((O/'creation_reconciliation.json').read_text(encoding='utf-8'))['matches']==[]
 assert json.loads((O/'old_catalog_projection.json').read_text(encoding='utf-8'))['product']['id']=='1601943775160'
 rows=json.loads((O/'asset_manifest.json').read_text(encoding='utf-8'))['assets'];assert len(rows)==13
 lp=O/'upload_ledger.json';ledger=json.loads(lp.read_text(encoding='utf-8')) if lp.exists() else {'style':'F2888','uploads':[]}
 for row in rows:
  assert json.loads((O/'resume_authorization.json').read_text(encoding='utf-8'))['authorized'] is True
  name=row['name'];p=Path(row['path']);digest=hashlib.sha256(p.read_bytes()).hexdigest();assert digest==row['sha256']==gate['image_hashes'][p.name]
  prior=next((x for x in ledger['uploads'] if x['name']==name),None)
  if prior:
   assert prior['sha256']==digest
   if prior['status']=='VERIFIED':continue
   if sys.argv[1]=='upload-remaining' and prior['status']=='OUTCOME_UNKNOWN_STOP_NO_RETRY':print(name,'held for independent bank reconciliation',flush=True);continue
   assert prior['status']=='RETRY_ALLOWED_AFTER_RECONCILIATION' and int(prior.get('retry_count',0))<3,'Unknown previous upload needs bank reconciliation'
   authorization=json.loads((O/prior['retry_authorization']).read_text(encoding='utf-8'));assert authorization['source_sha256']==digest and authorization['verdict']=='RECONCILED_NOT_SENT_ONE_IMAGE_RETRY_ALLOWED'
   item=prior;item.update(status='STARTED_RETRY_OUTCOME_UNKNOWN',retry_count=int(prior.get('retry_count',0))+1,retry_time_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
  else:
   item={'name':name,'path':str(p),'sha256':digest,'status':'STARTED_OUTCOME_UNKNOWN','time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()};ledger['uploads'].append(item)
  save(lp.name,ledger)
  try:
   j=sdk.upload_image(config,p,None);save(name+'.upload.response.json',j);keys=[k for k in j if k.endswith('_response') and k!='error_response'];d=j[keys[0]] if len(keys)==1 else j
   m=d.get('upload_image_response',d.get('model',d));url=m.get('photobank_url');fid=m.get('file_id');assert url and fid and not j.get('error_response') and d.get('biz_success') is not False
   if url.startswith('//'):url='https:'+url
   assert url.startswith('https://sc04.alicdn.com/kf/'),url
   item.update(status='VERIFIED',official_url=url,file_id=str(fid),request_id=d.get('request_id'));save(lp.name,ledger);print(name,'uploaded and verified',flush=True)
  except Exception as exc:
   item.update(status='OUTCOME_UNKNOWN_STOP_NO_RETRY',error_type=type(exc).__name__,transport_evidence=getattr(exc,'transport_evidence',None));save(lp.name,ledger);raise
elif sys.argv[1]=='publish':
 s=importlib.util.spec_from_file_location('publisher_F2888',P/'08_工具链/01_业务脚本/国际站扩品/publish_hot_rank_hr_a_batch.py');pub=importlib.util.module_from_spec(s);s.loader.exec_module(pub)
 listing=pub.load_submission_manifest(O/'publish_manifest.json','create',None)
 assert listing['differentiation_review']['status']=='PASS'
 config=sdk.load_config(Path.home()/'.config/beiqiang/alibaba-openapi.json')
 lp=O/'publish_once_ledger.json';log={'style':'F2888','public_model':'BQ-WBF2888','old_product_id':'1601943775160','status':'STARTED_OUTCOME_UNKNOWN','xml_sha256':hashlib.sha256(listing['xml'].encode()).hexdigest(),'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'old_action':'NOT_SENT'}
 with lp.open('x',encoding='utf-8') as f:json.dump(log,f,indent=2)
 result=pub.api_submit(sdk,config,listing,False);save('publish_receipt.json',result);log.update(status=result['status'],product_id=result.get('product_id'),content_status=result.get('content_status'),refs=result.get('refs'));save(lp.name,log);print(json.dumps(log),flush=True)
elif sys.argv[1]=='read':
 history=O/'readonly_history'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');history.mkdir(parents=True,exist_ok=True)
 for old in list(O.glob('formal_*'))+list(O.glob('score_timestamp.json')):
  if old.is_file():shutil.copyfile(old,history/old.name)
 pid=json.loads((O/'publish_once_ledger.json').read_text(encoding='utf-8')).get('product_id');assert pid,'No confirmed creation ID; reconcile unknown write instead'
 secret=call('alibaba.icbu.product.id.encrypt',{'product_id':str(pid),'language':'ENGLISH'},'formal_encrypt')['secret_id']
 d=call('alibaba.icbu.product.get',{'product_id':secret,'language':'ENGLISH'},'formal_get');p=d['product'];print(json.dumps({'id':pid,'model':p.get('red_model'),'status':p.get('status'),'display':p.get('display'),'url':p.get('pc_detail_url')}),flush=True)
 r=call('alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'language':'en_US'}},'formal_render');print('Formal render length',len(r.get('data','')),flush=True)
 d=call('alibaba.icbu.product.score.get',{'product_id':secret},'formal_score');save('score_timestamp.json',{'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'score_source':'alibaba.icbu.product.score.get','response':d});print(json.dumps(d,ensure_ascii=False),flush=True)
 iv=call('alibaba.icbu.product.sku.inventory.get',{'product_id':str(pid),'language':'en_US'},'formal_inventory');print('Actual SKU inventory read saved; no stock mutation.',flush=True)
elif sys.argv[1]=='bank':
 d=call('alibaba.icbu.photobank.list',{'extra_context':{},'location_type':'ALL_GROUP','current_page':1,'page_size':50},'bank_reconciliation');print('Bank read saved',flush=True)
elif sys.argv[1]=='inventory-read':
 pid=json.loads((O/'publish_once_ledger.json').read_text(encoding='utf-8'))['product_id']
 call('alibaba.icbu.product.sku.inventory.get',{'product_id':str(pid),'language':'en_US'},'formal_inventory');print('Read-only SKU association evidence saved; no stock mutation.',flush=True)
elif sys.argv[1]=='schema':
 cat=int(sys.argv[2]);d=call('alibaba.icbu.product.schema.get',{'param_product_top_publish_request':{'cat_id':cat,'language':'en_US'}},'schema')
 assert d.get('data');(O/'schema.xml').write_text(d['data'],encoding='utf-8');save('schema_timestamp.json',{'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'request_id':d.get('request_id'),'category_id':cat});print('Schema saved',len(d['data']),d.get('request_id'),flush=True)
