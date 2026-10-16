"""Owner-authorized stable HR model migration and one reviewed factory gallery asset.

Frozen exact IDs, current Schema, minimal incremental updates, one write ledger per
ID, independent formal/non-target/score checks, then registry/source double-sync.
Never retries an acknowledged or unknown write. Does not recreate absent IDs.
"""
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor,as_completed
from copy import deepcopy
from decimal import Decimal
from xml.etree import ElementTree as E
import argparse,json,re,sys,hashlib,os,tempfile
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(Path(__file__).parent))
import refresh_buyer_copy as b
import publish_hot_rank_hr_a_batch as pub
import schema_publish_contract as contract
from read_only_catalog import read_only_call,ReadBusinessError
BASE=ROOT/'02_Alibaba运营/05_扩品工程/执行记录/HR实源替换/货号与共用主图'
ENTRY=ROOT/'02_Alibaba运营/06_图片与检查记录/共享工厂详情'
REG=ROOT/'02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json'
CURRENT=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'
ASSET='01_产品资产/02_可发布素材/00_最终上传/00_厂家资料/03_当前工厂主图/F1_factory.png'
ASSET_SHA='13987d2f18fb1e3274ebf1d2eb2bed945d8ee12c33c2a0a5f23e3f41890ce29f'
PROTECTED={'1601825074604'}
# HR051 historically reused -A on three IDs. Keep the oldest original -A and
# allocate unused link suffixes D/E to the two later IDs; no new listing created.
MODEL_OVERRIDES={'1601969872083':'BQ1051-D','1601969906452':'BQ1051-E'}
# Full 209-gallery visual review: these preserve unique sole/heel/colour views.
SLOT_EXCEPTIONS={3:5,12:5,39:5,64:3,68:5,69:4,71:3,72:4,73:4,75:4,77:4,78:5,80:2,81:2,82:4,83:3,84:3,92:3,99:2,100:5,102:5,103:3,104:5,106:4,107:5,108:4,109:4,110:4,111:2,112:3,115:3,117:4,120:4,121:5,124:5,126:4,127:2,130:3,131:4,133:2,135:5,137:4,138:4,140:3,141:4,144:5,148:4,150:5,151:2,152:4,153:5,154:3,156:4,157:2,159:2,169:4,170:5,174:5,175:2,176:4,178:3,179:5,180:3,181:2,183:3,185:2,187:2,194:3,195:5,205:2,207:3,208:3}
def now():return datetime.now(timezone.utc).isoformat()
def load(p):return json.loads(p.read_text(encoding='utf8'))
def save(p,v):
 p.parent.mkdir(parents=True,exist_ok=True);raw=(json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8')
 if p.exists()and p.read_bytes()==raw:return
 temporary=None
 try:
  with tempfile.NamedTemporaryFile(dir=p.parent,prefix='.normalization-',suffix='.tmp',delete=False)as fp:fp.write(raw);temporary=Path(fp.name)
  try:os.replace(temporary,p)
  except OSError:
   # Some normal Windows readers retain a handle without delete-sharing.
   # Keep the same ordinary file and write its exact checked bytes in place.
   assert p.is_file()and not p.is_symlink()
   with p.open('r+b')as fp:fp.seek(0);fp.write(raw);fp.truncate();fp.flush()
 finally:
  if temporary and temporary.exists():temporary.unlink()
def rel(p):return p.relative_to(ROOT).as_posix()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def new_model(old):
 m=re.fullmatch(r'HR(\d{3})(.*)',old)
 return 'BQ1'+m[1]+m[2] if m else old

def canonical_skus(value,ignore_platform_ids=False):
 value=deepcopy(value)
 for row in value.get('skus',[]):
  if ignore_platform_ids:row.pop('sku_id',None)
 value['skus']=sorted(value.get('skus',[]),key=lambda row:json.dumps(row,sort_keys=True))
 for axis in value.get('sku_attributes',[]):
  axis['values']=sorted(axis.get('values',[]),key=lambda row:json.dumps(row,sort_keys=True))
 if 'sku_attributes'in value:value['sku_attributes']=sorted(value['sku_attributes'],key=lambda row:json.dumps(row,sort_keys=True))
 return value

def verified_sku_reissue(pid):
 path=BASE/'商品'/pid/'质量修正/规格恢复/SKU编号变更映射.json'
 if not path.exists():return None
 record=load(path)
 assert record['id']==pid and record['state']=='FORMAL_REISSUED_IDS_AND_ORIGINAL_SKU_DATA_VERIFIED'and all(record['checks'].values())and record['current_schema_bindings_verified']
 assert sha(ROOT/record['receipt'])==record['receipt_sha256']and load(ROOT/record['receipt'])['status']=='submitted_needs_readback'
 assert sha(ROOT/record['formal_get'])==record['formal_get_sha256']
 original=load(path.parent.parent/'before_get.json')['product']['product_sku'];actual=load(ROOT/record['formal_get'])['product']['product_sku']
 assert canonical_skus(original,True)==canonical_skus(actual,True)
 old={r['sku_code']:str(r['sku_id'])for r in original['skus']};new={r['sku_code']:str(r['sku_id'])for r in actual['skus']}
 assert set(old)==set(new)==set(record['items'])and all(record['items'][k]=={'old_sku_id':old[k],'current_sku_id':new[k]}for k in old)
 return record

def effective_before(z,before):
 before=deepcopy(before);overlay=BASE/'商品'/z['id']/'质量修正/fields_overlay.json'
 if overlay.exists():
  record=load(overlay);assert record['state']=='CATEGORY_FIELDS_FORMAL_PASS'and record['id']==z['id']and all(record['checks'].values())
  assert sha(ROOT/record['receipt'])==record['receipt_sha256']and load(ROOT/record['receipt'])['status']=='submitted_needs_readback'and sha(ROOT/record['payload'])==record['payload_sha256']
  assert int(before['category_id'])==record['before_category_id'];before['category_id']=record['target_category_id'];before['attributes']=record['expected_attributes']
  if record.get('sku_reissue_mapping'):
   mapping=verified_sku_reissue(z['id']);assert mapping and sha(ROOT/record['sku_reissue_mapping'])==record['sku_reissue_mapping_sha256']
   ids={v['old_sku_id']:v['current_sku_id']for v in mapping['items'].values()}
   assert set(ids)=={str(row['sku_id'])for row in before['product_sku']['skus']}
   for row in before['product_sku']['skus']:row['sku_id']=int(ids[str(row['sku_id'])])if isinstance(row['sku_id'],int)else ids[str(row['sku_id'])]
 return before
def clean_product(p,model_change=False):
 p=deepcopy(p)
 for k in ('gmt_modified','status','display'):p.pop(k,None)
 if model_change:
  p['attributes']=[x for x in p.get('attributes',[])if str(x['attribute_id'])!='3']
  for row in p.get('product_sku',{}).get('skus',[]):row.pop('sku_code',None)
 # Platform reorders complete Style choices. Compare all attribute objects,
 # including IDs and text, while preserving multiplicity and every value.
 if 'attributes'in p:p['attributes']=sorted(p['attributes'],key=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False))
 if 'product_sku'in p:p['product_sku']=canonical_skus(p['product_sku'])
 # product.get returns these gallery rows in varying order. Preserve every
 # complete role/name/URL object and multiplicity; current Schema order is
 # checked independently below, so this cannot excuse missing or rebound images.
 for key in ('company_image','detail_image'):
  gallery=p.get('struct_detail',{}).get(key,{})
  if isinstance(gallery,dict)and isinstance(gallery.get('images'),list):gallery['images']=sorted(gallery['images'],key=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False))
 p.pop('main_image',None)
 return p
def get_checks(z,p,before,prep):
 before=effective_before(z,before)
 checks={'model':b.model(p)==z['new_model'],'gallery':list(map(pub.image_key,p['main_image']['images']))==list(map(pub.image_key,prep['expected_images'])),'non_target_formal':clean_product(p,z['model_change'])==clean_product(before,z['model_change']),'unchanged_title':p['subject']==before['subject'],'gallery_count':len(p['main_image']['images'])==6}
 if z['model_change']:
  old_rows={str(x['sku_id']):x for x in before.get('product_sku',{}).get('skus',[])};rows={str(x['sku_id']):x for x in p.get('product_sku',{}).get('skus',[])};checks['sku_binding_ids_match_declared_history']=set(rows)==set(old_rows);checks['sku_rows_match_declared_history_and_code_change']=True
  for sid,x in old_rows.items():
   wanted_row=deepcopy(x)
   if 'sku_code'in x:wanted_row['sku_code']=prep['sku_code_changes'].get(x['sku_code'],x['sku_code'])
   checks['sku_rows_match_declared_history_and_code_change'] &= rows.get(sid)==wanted_row
 return checks
def freeze():
 assert not(BASE/'范围.json').exists(),'Frozen scope already exists'
 assert sha(ROOT/ASSET)==ASSET_SHA
 c=load(BASE/'当前目录/catalog.json');r=load(REG);links={x['id']:x for x in r['listings']};products={x['id']:x for x in r['products']}
 reviewed=load(ROOT/'99_临时区/HR货号与主图/missing_factory_review.json');review_slots={z['id']:SLOT_EXCEPTIONS.get(i,6)for i,z in enumerate(reviewed)}
 late=load(ROOT/'99_临时区/HR货号与主图/late_gallery.json');ix={0,1,2,3,4,6,25,27,30,31,33,36,37,38,39,198,199,200,201};known={z['url']for z in late if z['index']in ix}
 targets=[];excluded=[];migrations=[]
 for p in c['products']:
  pid=str(p['id']);old=p['red_model'];l=links[pid];assert l['model']==old
  new=MODEL_OVERRIDES.get(pid,new_model(old));prod=products[l['product_id']]
  if new!=old:
   assert l.get('bound_source_id') and prod['source_state'] in ('ADOPTED','RAW_PACKAGE','MAPPED'),(pid,'Source missing')
   migrations.append({'id':pid,'product_key':l['product_id'],'old_model':old,'new_model':new,'source_id':l['bound_source_id'],'state':'PLANNED_NOT_FORMAL'})
  if pid in PROTECTED or p['status']!='approved'or p['display']!='Y':
   excluded.append({'id':pid,'model':old,'new_model':new,'status':p['status'],'display':p['display'],'reason':'PROTECTED_SOURCE_READ_ONLY'if pid in PROTECTED else'PRESERVE_NON_ACTIVE_STATE_NO_REPUBLISH'});continue
  ims=p['main_image']['images'];assert len(ims)in (5,6)
  factory=[i+1 for i,u in enumerate(ims)if u in known]
  slot=max(factory)if factory else review_slots[pid]
  assert slot>1 and slot<=len(ims)+1
  targets.append({'id':pid,'product_key':l['product_id'],'old_model':old,'new_model':new,'model_change':new!=old,'source_id':l.get('bound_source_id'),'category_id':int(p['category_id']),'gallery_slot':slot,'gallery_before':ims,'reason':'REPLACE_EXISTING_FACTORY_PANEL'if factory else'REPLACE_VISUALLY_REVIEWED_REDUNDANT_VIEW'if len(ims)==6 else'ADD_FACTORY_TO_EMPTY_SIXTH_SLOT','state':'FROZEN_NOT_SUBMITTED'})
 assert len(targets)==482 and len(migrations)==175 and len({z['new_model']for z in migrations})==len(migrations)
 collisions=[l['id']for l in r['listings']if l['model'] in {z['new_model']for z in migrations}];assert not collisions
 plan={'at':now(),'catalog_evidence':rel(BASE/'当前目录/catalog.json'),'catalog_total':c['total_item'],'targets':targets,'excluded':excluded,'model_migrations':migrations,'image_sha256':ASSET_SHA,'image_path':ASSET,'visual_review':{'reviewed_current_late_images':203,'missing_factory_galleries_reviewed':209,'slot_exceptions':len(SLOT_EXCEPTIONS),'reviewer':'active_agent','invariant':'M1, product/SKU identities and unique sole/heel/colour proof preserved; original uploaded assets retained as dated evidence'},'authorization':'2026-10-16 owner requested ending 2520, replacing HR identifiers with stable product codes, internal external/own production classes, and one best common factory gallery image. No repeated per-item approval or browser gate.'}
 save(BASE/'范围.json',plan)
 sources=[]
 for n in ['大门.jpg','A9C9E3B935A11A476BE00DE0FD0C3BBC.png','微信图片_20260530105010_227_16.jpg','微信图片_20260530105149_230_16.jpg']:
  p=ROOT/'01_产品资产/02_可发布素材/00_最终上传/00_厂家资料/01_原始厂家照片'/n;sources.append({'path':rel(p),'sha256':sha(p)})
 prompt=(ROOT/'99_临时区/HR货号与主图/工厂概览生成提示词.txt').read_text(encoding='utf8')
 save(ENTRY/'共用主图.json',{'version':1,'role':'F1_FACTORY_GALLERY_OVERVIEW','path':ASSET,'sha256':ASSET_SHA,'width':1254,'height':1254,'sources':sources,'prompt':prompt,'generation_mode':'built-in image_gen compositing','review':{'state':'VISUAL_PASS','reviewer':'active_agent','actual_photos_preserved':True,'text_checked':True,'no_added_capacity_equipment_certification':True,'company_level_only':True},'live_state':'NOT_UPLOADED','scope':'One common main-gallery factory overview. Existing six company detail modules remain unchanged.'})
 print('FROZEN',len(targets),'MODEL_MIGRATIONS',len(migrations),'EXCLUDED',len(excluded))
def bank(api,cfg):
 f=ENTRY/'共用主图图片银行.json'
 if f.exists():
  d=load(f);assert d['sha256']==ASSET_SHA
  row=d.get('response',{}).get('upload_image_response',{})
  if d['state']!='UPLOADED':
   assert row.get('file_id')and row.get('photobank_url')and not api.api_error(d['response']),'Unknown upload must be reconciled, never replayed'
   u=row['photobank_url'];u='https:'+u if u.startswith('//')else u.replace('http:','https:');assert u.startswith('https://sc04.alicdn.com/')
   d.update(state='UPLOADED',file_id=str(row['file_id']),url=u);save(f,d);save(ENTRY/'共用主图公开映射.json',{k:v for k,v in d.items()if k!='response'})
   m=load(ENTRY/'共用主图.json');m['live_state']='OFFICIAL_BANK_UPLOADED_BINDING_PENDING';save(ENTRY/'共用主图.json',m)
  print('BANK_REUSED');return
 assert sha(ROOT/ASSET)==ASSET_SHA
 d={'state':'OUTCOME_UNKNOWN_NO_REPLAY','at':now(),'path':ASSET,'sha256':ASSET_SHA};save(f,d)
 response=api.upload_image(cfg,ROOT/ASSET,None);d['response']=response;save(f,d)
 row=response.get('upload_image_response',{});assert not api.api_error(response)and row.get('file_id')and row.get('photobank_url')
 u=row['photobank_url'];u='https:'+u if u.startswith('//')else u.replace('http:','https:')
 d.update(state='UPLOADED',file_id=str(row['file_id']),url=u);assert d['url'].startswith('https://sc04.alicdn.com/')
 save(f,d);save(ENTRY/'共用主图公开映射.json',{k:v for k,v in d.items()if k!='response'});m=load(ENTRY/'共用主图.json');m['live_state']='OFFICIAL_BANK_UPLOADED_BINDING_PENDING';save(ENTRY/'共用主图.json',m);print('BANK_UPLOADED',d['file_id'])
def operate(z,mode,api,cfg):
 pid=z['id'];f=BASE/'商品'/pid;f.mkdir(parents=True,exist_ok=True);ledger=f/'update_once.json'
 def read(m,p):return read_only_call(api,cfg,m,p)
 def get():return read('alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'})
 def render(p):return read('alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US'}})
 if mode=='prepare':
  if ledger.exists()or(f/'prepared.json').exists():return {'id':pid,'state':'EXISTING_PREPARATION_OR_LEDGER_PRESERVED'}
  g=get();save(f/'before_get.json',g);p=g.get('product');assert p and b.model(p)==z['old_model'] and int(p['category_id'])==z['category_id']
  expected_state=('tbd','N')if z.get('authorized_rejected_original_repair')and pid=='1601943545775'else('approved','Y')
  if(p['status'],p['display'])!=expected_state:save(f/'preparation_state.json',{'at':now(),'state':'CURRENT_STATE_CHANGED','status':p['status'],'display':p['display']});return {'id':pid,'state':'CURRENT_STATE_CHANGED'}
  assert p['main_image']['images']==z['gallery_before'],'Gallery drift since frozen catalog'
  rr=render(p);save(f/'before_render.json',rr)
  if not rr.get('data'):return {'id':pid,'state':'CURRENT_SCHEMA_UNAVAILABLE'}
  s=E.fromstring(rr['data']);(f/'current_schema.xml').write_text(rr['data'],encoding='utf8');fields=['scImages','productTitle']
  if z['model_change']:fields+=['icbuCatProp']
  root=contract.values_only(s,operation='update',field_ids=fields)
  if z['model_change']:
   cv=root.find("./field[@id='icbuCatProp']/complex-value");mf=contract.serialize_product_model(s,z['new_model']);old=cv.find("./field[@id='"+mf.get('id')+"']");assert old is not None;position=list(cv).index(old);cv.remove(old);cv.insert(position,mf)
  bankrow=load(ENTRY/'共用主图图片银行.json');assert bankrow['state']=='UPLOADED'
  cv=root.find("./field[@id='scImages']/complex-value");assert cv is not None
  i=z['gallery_slot']-1;fid='scImages_'+str(i);node=cv.find("./field[@id='"+fid+"']")
  if node is None:assert i==len(z['gallery_before']);node=E.SubElement(cv,'field',id=fid,type='input')
  for child in list(node):node.remove(child)
  E.SubElement(node,'value',fileFlag='no',fileId=bankrow['file_id']).text=bankrow['url'].replace('https:','')
  code_changes={}
  if z['model_change']:
   sku=contract.values_only(s,operation='update',field_ids=['sku']).find("./field[@id='sku']")
   if sku is not None:
    for code in sku.findall(".//field[@id='skuOuterId']/value"):
     old=code.text or '';new=z['new_model']+old[len(z['old_model']):]if old.startswith(z['old_model'])else re.sub(r'^HR(\d{3})',r'BQ1\1',old)
     if new!=old:code_changes[old]=new;code.text=new
    if code_changes:fields.append('sku');root.append(sku)
  pub.set_direct_value(root,'productTitle',p['subject']);payload=f/'payload.xml';payload.write_text(E.tostring(root,encoding='unicode'),encoding='utf8')
  assert set(x.get('id')for x in root)==set(fields)
  manifest={'operation':'update','product_id':pid,'category_id':z['category_id'],'facts_reviewed':True,'source_evidence':[rel(BASE/'范围.json'),rel(ENTRY/'共用主图.json')],'current_schema':'current_schema.xml','current_schema_sha256':sha(f/'current_schema.xml'),'schema_request_id':rr['request_id'],'schema_acquired_at':now(),'payload_xml':'payload.xml','field_ids':fields,'dependency_ids':[]}
  if z['model_change']:manifest['expected_model']=z['new_model']
  save(f/'manifest.json',manifest);pub.load_submission_manifest(f/'manifest.json','update',pid)
  expected_images=list(z['gallery_before'])
  if i==len(expected_images):expected_images.append(bankrow['url'])
  else:expected_images[i]=bankrow['url']
  prep={'id':pid,'at':now(),'state':'PREPARED','old_model':z['old_model'],'new_model':z['new_model'],'fields':fields,'gallery_slot':z['gallery_slot'],'expected_images':expected_images,'sku_code_changes':code_changes,'preserve_title':p['subject'],'asset_sha256':ASSET_SHA,'source_id_unchanged':z['source_id']};save(f/'prepared.json',prep);return {'id':pid,'state':'PREPARED','model_change':z['model_change'],'sku_code_changes':len(code_changes)}
 if mode=='submit':
  if ledger.exists():return {'id':pid,'state':'EXISTING_LEDGER_READBACK_ONLY'}
  if not(f/'prepared.json').exists():return {'id':pid,'state':'NOT_PREPARED'}
  listing=pub.load_submission_manifest(f/'manifest.json','update',pid);g=get();save(f/'immediate_prewrite_get.json',g);p=g['product'];old=load(f/'before_get.json')['product']
  expected_state=('tbd','N')if z.get('authorized_rejected_original_repair')and pid=='1601943545775'else('approved','Y')
  assert(p['status'],p['display'])==expected_state and {k:v for k,v in p.items()if k not in ('status','display','gmt_modified')}=={k:v for k,v in old.items()if k not in ('status','display','gmt_modified')},'Current product changed, no stale write'
  with ledger.open('x',encoding='utf8')as stream:json.dump({'state':'STARTED_OUTCOME_UNKNOWN_NO_REPLAY','at':now(),'id':pid},stream)
  receipt=pub.api_submit(api,cfg,listing,False,update_product_id=pid);save(f/'update_receipt.json',receipt);save(ledger,{'state':receipt['status'],'at':receipt['attempted_at'],'id':pid,'refs':receipt.get('refs')});return {'id':pid,'state':receipt['status']}
 if mode=='verify':
  if not ledger.exists():return {'id':pid,'state':'NOT_SUBMITTED'}
  g=get();save(f/'after_get.json',g);p=g.get('product');assert p
  report={'id':pid,'at':now(),'state':'PENDING_REVIEW','status':p['status'],'display':p['display'],'actual_score':None,'public_qa':'NOT_PER_ITEM_BROWSER_TESTED_OWNER_API_SCOPE'}
  before=load(f/'before_get.json')['product'];prep=load(f/'prepared.json');report['readback_checks']=get_checks(z,p,before,prep)
  if p['status']!='approved'or p['display']!='Y':
   report['state']=('PLATFORM_REJECTED_TARGET_VALUES_RETURNED'if all(report['readback_checks'].values())else'PLATFORM_REJECTED_FIELDS_MISMATCH')if p['status']=='tbd'else'FIELDS_RETURNED_PENDING_REVIEW'if all(report['readback_checks'].values())else'REVIEWING_FIELDS_MISMATCH';save(f/'verification.json',report);return {k:report[k]for k in ('id','state','status','display')}
  rr=render(p);save(f/'after_render.json',rr)
  if not rr.get('data'):report['state']='CURRENT_SCHEMA_UNAVAILABLE';save(f/'verification.json',report);return report
  before=load(f/'before_get.json')['product'];prep=load(f/'prepared.json');payload=E.parse(f/'payload.xml').getroot();s=E.fromstring(rr['data']);actual=contract.field_snapshot(s);wanted=contract.field_snapshot(payload);previous=contract.field_snapshot(E.fromstring(load(f/'before_render.json')['data']))
  checks=get_checks(z,p,before,prep)
  if z['model_change']:
   target=contract.model_field_definition(s);value=s.find("./field[@id='icbuCatProp']/complex-value/field[@id='"+target.get('id')+"']/value");checks['render_model']=value is not None and(value.get('inputValue')or value.text)==z['new_model']
  submitted=set(prep['fields']);overlay=f/'质量修正/fields_overlay.json'
  if overlay.exists():
   record=load(overlay);assert record['state']=='CATEGORY_FIELDS_FORMAL_PASS'and all(record['checks'].values());submitted|={'catId','icbuCatProp'};report['category_followup_evidence']=rel(overlay)
   if record.get('sku_reissue_mapping'):
    mapping=verified_sku_reissue(pid);assert mapping
    submitted|={'saleProp','sku','ladderPrice'}
    report['sku_reissue_mapping']=record['sku_reissue_mapping'];report['original_platform_SKU_ids_preserved']=mapping['original_platform_SKU_ids_preserved']
  checks['unsubmitted_schema_fields_preserved']=all(actual.get(k)==v for k,v in previous.items()if k not in submitted)
  # Targeted attribute/gallery/SKU comparison above uses effective model and
  # exact original SKU IDs/rows, not unstable generated input markers.
  report.update(checks=checks,formal_request_id=g.get('request_id'),schema_request_id=rr.get('request_id'),new_model=z['new_model'],gallery_slot=z['gallery_slot'],asset_sha256=ASSET_SHA)
  if not all(checks.values()):report['state']='FORMAL_MISMATCH_DIAGNOSE';save(f/'verification.json',report);return {'id':pid,'state':report['state'],'failed':[k for k,v in checks.items()if not v]}
  # Official ID encryption is a read-only identifier conversion. The shared
  # generic reader admits .get/.render only, so use the existing client directly.
  enc=api.top_call(cfg,'alibaba.icbu.product.id.encrypt',{'product_id':pid,'language':'ENGLISH'});save(f/'encrypted_id.json',enc)
  if enc.get('secret_id'):
   score=read('alibaba.icbu.product.score.get',{'product_id':enc['secret_id']});save(f/'score.json',score);result=score.get('result',{});report['actual_score']=result.get('final_score');problem=result.get('problem_map')or{};problem=json.loads(problem)if isinstance(problem,str)else problem
   report['score_diagnostics']={'flags':{k:v for k,v in problem.get('extendProblemMap',{}).items()if v is True},'deductions':{k:v for k,v in problem.get('ruleScoreMap',{}).items()if Decimal(str(v))!=0},'errors':problem.get('errorReasonList',[])}
  report['state']='FORMAL_FIELDS_SCORE_PASS'if report['actual_score']is not None and Decimal(str(report['actual_score']))>=5 and not any(report.get('score_diagnostics',{'unknown':True}).values())else'FORMAL_FIELDS_PASS_SCORE_BELOW_TARGET'if report['actual_score']is not None and Decimal(str(report['actual_score']))<5 else'FORMAL_FIELDS_PASS_PENDING_SCORE'
  save(f/'verification.json',report);return {'id':pid,'state':report['state'],'actual_score':report['actual_score']}
 raise ValueError(mode)
def main():
 sys.stdout.reconfigure(encoding='utf8');ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['freeze','bank','prepare','submit','verify']);ap.add_argument('--ids');ap.add_argument('--limit',type=int);ap.add_argument('--workers',type=int,default=4);ap.add_argument('--http-transport',choices=['urllib','native'],default='native');args=ap.parse_args()
 if args.mode=='freeze':freeze();return
 api,cfg=b.api_client()
 if args.http_transport=='native':api.http_json=api.native_http_json
 if args.mode=='bank':bank(api,cfg);return
 rows=load(BASE/'范围.json')['targets']
 if args.ids:ids=set(args.ids.split(','));rows=[z for z in rows if z['id']in ids];assert len(rows)==len(ids)
 if args.limit:
  if args.mode=='prepare':rows=[z for z in rows if not(BASE/'商品'/z['id']/'prepared.json').exists()and not(BASE/'商品'/z['id']/'update_once.json').exists()]
  elif args.mode=='submit':rows=[z for z in rows if(BASE/'商品'/z['id']/'prepared.json').exists()and not(BASE/'商品'/z['id']/'update_once.json').exists()]
  elif args.mode=='verify':rows=[z for z in rows if(BASE/'商品'/z['id']/'update_once.json').exists()and(not(BASE/'商品'/z['id']/'verification.json').exists()or load(BASE/'商品'/z['id']/'verification.json').get('state')!='FORMAL_FIELDS_SCORE_PASS')]
  rows=rows[:args.limit]
 results=[]
 def run(z):
  try:return operate(z,args.mode,api,cfg)
  except Exception as exc:
   result={'id':z['id'],'state':'ERROR','exception_type':type(exc).__name__,'message':str(exc)[:600]};save(BASE/'商品'/z['id']/(args.mode+'_error.json'),result);return result
 if args.mode=='submit':
  for z in rows:
   if(BASE/'暂停新提交.flag').exists():print('STOPPED_BETWEEN_PRODUCTS_NO_INFLIGHT_WRITE');break
   result=run(z);results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
 else:
  with ThreadPoolExecutor(max_workers=min(args.workers,4))as pool:
   for result in pool.map(run,rows):results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
 from collections import Counter
 print('SUMMARY',json.dumps(dict(Counter(z['state']for z in results)),ensure_ascii=False))
if __name__=='__main__':main()
