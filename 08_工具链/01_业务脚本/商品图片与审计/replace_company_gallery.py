"""Exact-ID company gallery updates; serial single attempts, independent readback.

Reuse current-Schema preparation and the existing official client. Never replay
an existing ledger or silently alter any non-company field. Public QA is separate.
"""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
from xml.etree import ElementTree as E
from concurrent.futures import ThreadPoolExecutor,as_completed
import argparse,json,sys,hashlib,subprocess,copy
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'02_Alibaba运营/06_图片与检查记录/共享工厂详情'
sys.path.insert(0,str(ROOT/'08_工具链/01_业务脚本/国际站扩品'))
import refresh_buyer_copy as b
import publish_hot_rank_hr_a_batch as pub
from read_only_catalog import read_only_call
from prepare_company_gallery import ROLES

def now():return datetime.now(timezone.utc).isoformat()
def load(p):return b.load(p)
def save(p,x):b.save(p,x)
def preserve(p):
 x=copy.deepcopy(p)
 for k in ('gmt_modified','status','display'):x.pop(k,None)
 if isinstance(x.get('struct_detail'),dict):x['struct_detail'].pop('company_image',None)
 return x
def company_pairs(p):
 rows=(p.get('struct_detail',{}).get('company_image')or{}).get('images',[])
 return Counter((str(x['image_set']['id']),x['image_url'].replace('https:','').replace('http:',''))for x in rows)
def expected_pairs(bank):
 return Counter((str(role),bank['items'][key]['url'].replace('https:',''))for key,role,_ in ROLES)
def verified_aliases(bank):
 proof=load(BASE/'正式图链像素核对.json')
 assert proof['asset_version']==6 and proof['status']=='FIVE_EXACT_FORMAL_URL_IDENTITIES_VERIFIED'
 assert len(proof['items'])==5
 aliases={}
 for key,role,_ in ROLES:
  row=next(x for x in proof['items']if x['asset']==key)
  assert row['gallery_id']==role and row['status']=='EXACT_SOURCE_BYTES_AND_PIXELS'
  assert row['source_sha256']==row['download_sha256']
  assert bank['items'][key]['url']==row['accepted_urls'][0]
  assert str(bank['items'][key]['file_id'])==row['file_id']
  for url in row['accepted_urls']:
   token=url.removeprefix('https:')
   assert token not in aliases
   aliases[token]=(str(role),key)
 return aliases
def gallery_identity_match(p,bank):
 aliases=verified_aliases(bank);found=[]
 for (role,url),count in company_pairs(p).items():
  if count!=1 or url not in aliases or aliases[url][0]!=role:return False
  found.append(aliases[url])
 return Counter(found)==Counter((str(role),key)for key,role,_ in ROLES)
def schema_identity_match(xml,bank):
 root=E.fromstring(xml);field=root.find(".//field[@id='companyImage']")
 if field is None:return False
 aliases=verified_aliases(bank);found=[]
 for row in field.findall('./complex-values'):
  role=row.find("./field[@id='gallery']/value")
  urls=row.findall("./field[@id='images']/complex-values/field[@id='imageURL']/value")
  if role is None or len(urls)!=1:return False
  if row.find(".//field[@id='generalText']/value") is not None:return False
  token=(urls[0].text or '').removeprefix('https:')
  if token not in aliases or aliases[token][0]!=role.text:return False
  found.append(aliases[token])
 return Counter(found)==Counter((str(role),key)for key,role,_ in ROLES)
def prepare(pid):
 return subprocess.run([sys.executable,str(Path(__file__).with_name('prepare_company_gallery.py')),'--ids',pid],cwd=ROOT,capture_output=True,text=True,encoding='utf8')
def aggregate():
 prep=load(BASE/'替换准备.json');rows=[]
 for pid in prep['eligible_ids']:
  f=BASE/'商品'/pid
  v=load(f/'verification.json') if(f/'verification.json').exists()else{}
  receipt=load(f/'update_receipt.json') if(f/'update_receipt.json').exists()else{}
  public=load(f/'public_verification.json')if(f/'public_verification.json').exists()else{}
  rows.append({'product_id':pid,'historical_company_only':pid in prep['historical_company_only_ids'],'submission_status':receipt.get('status')or('STARTED_OUTCOME_UNKNOWN'if(f/'update_once.json').exists()else'NOT_SUBMITTED'),'status':v.get('status')or receipt.get('status')or('STARTED_OUTCOME_UNKNOWN'if(f/'update_once.json').exists()else'NOT_SUBMITTED'),'public_status':public.get('status')or v.get('public_status','NOT_CHECKED')})
 counts=Counter(x['status']for x in rows)
 excluded=prep['excluded_ids']
 out={'at':now(),'asset_version':6,'authorized_count':len(rows),'historical_company_only_count':len(prep['historical_company_only_ids']),'excluded_ids':sorted(set(excluded['readonly_source']+excluded['offline_duplicates'])),'counts':dict(counts),'items':rows,'scope':'companyImage only; source and shoe-copy states unchanged; public QA separately counted'}
 out['positive_submission_count']=sum(x['submission_status']=='submitted_needs_readback'for x in rows)
 out['formal_pass_count']=sum(x['status']=='FORMAL_PASS'for x in rows)
 out['public_pass_count']=sum(x['public_status']=='PUBLIC_FIVE_FACTORY_IMAGES_LOADED'for x in rows)
 out['original_offline_display_preserved_count']=sum(x['public_status']=='NOT_APPLICABLE_OFFLINE_DISPLAY_PRESERVED'and x['status']=='FORMAL_PASS'for x in rows)
 manifest=load(BASE/'制作档案.json');manifest['online_state'].update(bound_product_count=out['formal_pass_count'],bound=out['formal_pass_count']==len(rows),state='ALL_FORMAL_BOUND_PUBLIC_SEPARATE'if out['formal_pass_count']==len(rows)else'BATCH_API_REPLACEMENT_IN_PROGRESS',authorized_product_count=len(rows),positive_submission_count=out['positive_submission_count'],public_pass_count=out['public_pass_count'],current_state_evidence='当前替换.json',scope='Only companyImage; historical source/copy not resolved')
 save(BASE/'制作档案.json',manifest)
 prep['online_state']=manifest['online_state'];save(BASE/'替换准备.json',prep)
 save(BASE/'当前替换.json',out);return out
def main():
 ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','submit','verify','aggregate']);ap.add_argument('--ids');ap.add_argument('--workers',type=int,default=4);a=ap.parse_args();sys.stdout.reconfigure(encoding='utf8')
 prep=load(BASE/'替换准备.json');bank=load(BASE/'当前上传回执.json');ids=a.ids.split(',')if a.ids else prep['eligible_ids']
 assert len(ids)==len(set(ids))and all(x in prep['eligible_ids']and x not in b.PROTECTED_IDS for x in ids)
 if a.mode=='aggregate':print(json.dumps(aggregate()['counts']),flush=True);return
 api,cfg=b.api_client()
 def get(pid):return read_only_call(api,cfg,'alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'})
 def work(pid):
  f=BASE/'商品'/pid;ledger=f/'update_once.json'
  if a.mode=='prepare':
   if ledger.exists():return {'product_id':pid,'status':'EXISTING_LEDGER_READBACK_ONLY'}
   result=prepare(pid)
   if result.returncode:
    failure={'product_id':pid,'at':now(),'status':'PREPARATION_FAILED_NO_WRITE','exit_code':result.returncode,'reason':(result.stderr.splitlines()[-1]if result.stderr else'Unknown local preparation failure')[:250]}
    save(f/'preparation_error.json',failure);return failure
   return {'product_id':pid,'status':'PREPARED_NO_WRITE'}
  if a.mode=='submit':
   if ledger.exists():return {'product_id':pid,'status':'EXISTING_LEDGER_READBACK_ONLY'}
   canary=BASE/'商品/1601976084873'
   assert load(canary/'verification.json')['status']=='FORMAL_PASS'
   assert load(canary/'public_verification.json')['status']=='PUBLIC_FIVE_FACTORY_IMAGES_LOADED'
   assert(f/'prepared.json').exists()
   before=load(f/'before_get.json')['product'];got=get(pid);save(f/'immediate_prewrite_get.json',got)
   if got['product']!=before:return {'product_id':pid,'status':'CURRENT_CHANGED_REPREPARE_NO_WRITE'}
   listing=pub.load_submission_manifest(f/'manifest.json','update',pid)
   assert set(listing['field_ids'])=={'companyImage'}and set(listing['dependency_ids'])<={'productDescType'}
   assert load(f/'readiness.json')['asset_version']==6
   assert preserve(before)==preserve(got['product'])
   with ledger.open('x',encoding='utf8')as h:json.dump({'product_id':pid,'status':'STARTED_OUTCOME_UNKNOWN','at':now(),'prepared_sha256':b.sha(f/'prepared.json'),'scope':['companyImage']},h)
   receipt=pub.api_submit(api,cfg,listing,False,update_product_id=pid);save(f/'update_receipt.json',receipt)
   save(ledger,{'product_id':pid,'status':receipt['status'],'at':receipt['attempted_at'],'refs':receipt.get('refs'),'scope':['companyImage']})
   return {'product_id':pid,'status':receipt['status']}
  if not ledger.exists():return {'product_id':pid,'status':'NO_WRITE_LEDGER'}
  got=get(pid);save(f/'after_get.json',got);p=got['product'];old=load(f/'before_get.json')['product'];same=preserve(p)==preserve(old)
  matches=gallery_identity_match(p,bank)
  report={'product_id':pid,'at':now(),'request_id':got.get('request_id'),'product_status':p.get('status'),'display':p.get('display'),'company_gallery_match':matches,'company_image_count':sum(company_pairs(p).values()),'unsubmitted_fields_preserved':same,'display_preserved':p.get('display')==old.get('display'),'public_status':'PENDING_EXACT_ID_FACTORY_PRESENTATION','historical_company_only':pid in prep['historical_company_only_ids']}
  report['status']=('PENDING_REVIEW'if p.get('status')in ('new','modified')else'REVIEW_NOT_APPROVED_DIAGNOSE_NO_REPLAY')if p.get('status')!='approved'else'FORMAL_PASS'if matches and same and report['display_preserved']else'MISMATCH_DIAGNOSE_NO_REPLAY'
  report['company_url_exact_match']=company_pairs(p)==expected_pairs(bank)
  report['company_alias_proof']='正式图链像素核对.json'
  if old.get('display')=='N' and p.get('display')=='N':report['public_status']='NOT_APPLICABLE_OFFLINE_DISPLAY_PRESERVED'
  if p.get('status')=='approved':
   res=read_only_call(api,cfg,'alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US'}});save(f/'after_render.json',res)
   if res.get('data'):
    snapshot=pub.field_snapshot(E.fromstring(res['data']));listing=load(f/'prepared.json');report['schema_company_exact_match']=snapshot.get('companyImage')==listing['expected_fields']['companyImage'];report['schema_available']=True
    report['schema_company_identity_match']=schema_identity_match(res['data'],bank)
   else:report['schema_available']=False
   if report['status']=='FORMAL_PASS' and not report.get('schema_company_identity_match'):report['status']='SCHEMA_MISMATCH_DIAGNOSE_NO_REPLAY'
  public=f/'public_verification.json'
  if public.exists():
   evidence=load(public)
   if evidence.get('asset_version')==6:report['public_status']=evidence['status']
  save(f/'verification.json',report);return report
 if a.mode=='submit':
  for pid in ids:
   try:result=work(pid)
   except Exception as e:result={'product_id':pid,'status':'LOCAL_OR_TRANSPORT_ERROR_NO_REPLAY','error_type':type(e).__name__}
   print(json.dumps(result,ensure_ascii=False),flush=True)
 else:
  with ThreadPoolExecutor(max_workers=a.workers)as pool:
   fs={pool.submit(work,p):p for p in ids}
   for future in as_completed(fs):
    try:result=future.result()
    except Exception as e:result={'product_id':fs[future],'status':'READBACK_ERROR','error_type':type(e).__name__}
    print(json.dumps(result,ensure_ascii=False),flush=True)
 aggregate()
if __name__=='__main__':main()
