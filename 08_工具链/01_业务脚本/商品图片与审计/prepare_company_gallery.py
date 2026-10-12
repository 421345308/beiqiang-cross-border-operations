"""Prepare an exact-ID minimal company-image update. No product write endpoint.

Official bank assets must have exact pixel proof. Copy approval and its public
presentation remain separate gates; current field shape is read for this ID.
"""
from pathlib import Path
from datetime import datetime,timezone
from xml.etree import ElementTree as E
import argparse,importlib.util,json,hashlib,sys
ROOT=Path(__file__).resolve().parents[3]
FACTORY=ROOT/'02_Alibaba运营/06_图片与检查记录/共享工厂详情'
COPY=ROOT/'02_Alibaba运营/02_单品优化记录/全店FAQ与产品亮点优化/商品'
ROLES=[('C1',400,'Company overview'),('C2',550,'Customization capabilities'),
       ('C3',600,'Production workflow'),('C4',450,'Competitive advantages'),
       ('C5',700,'Packaging & shipping specifications')]
def load(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--ids',required=True);ap.add_argument('--preserve-title',action='store_true');ap.add_argument('--phase',choices=['未生效修复']);a=ap.parse_args();sys.stdout.reconfigure(encoding='utf8')
 sys.path.insert(0,str(ROOT/'08_工具链/01_业务脚本/国际站扩品'))
 import publish_hot_rank_hr_a_batch as pub
 import refresh_buyer_copy as buyer
 from read_only_catalog import read_only_call
 api,cfg=buyer.api_client();prep=load(FACTORY/'替换准备.json');bank=load(FACTORY/'当前上传回执.json');pixels=load(FACTORY/'图片银行像素核对.json')
 assert bank['asset_version']==pixels['asset_version']==prep['asset_version']==6
 assert pixels['status']=='FIVE_BANK_PIXELS_EXACT_PASS'
 for key,asset in prep['target_assets'].items():
  assert sha(ROOT/asset['path'])==asset['sha256']==bank['items'][key]['sha256']
 ids=a.ids.split(',');assert len(ids)==len(set(ids)) and all(x.isdigit()for x in ids)
 for pid in ids:
  assert pid in prep['eligible_ids'] and pid not in buyer.PROTECTED_IDS
  c=COPY/pid;verification=load(c/'verification.json') if (c/'verification.json').exists() else None
  copy=load(c/'copy.json') if (c/'copy.json').exists() else None
  historical=pid in prep.get('historical_company_only_ids',[])
  assert prep.get('owner_copy_accepted') is True
  assert historical or (verification and (verification.get('status')=='FORMAL_PASS' or verification.get('target_copy_status')=='TARGET_FORMAL_PASS')),'Only owner-accepted real copy or explicitly authorized historical company-only scope'
  folder=FACTORY/'商品'/pid;folder.mkdir(parents=True,exist_ok=True)
  if a.phase:
   assert a.preserve_title and pid in ('1601973808453','1601973854304')
   previous=load(folder/'verification.json');assert previous['product_status']=='approved'and previous['company_gallery_match']is False and previous['unsubmitted_fields_preserved']is True
   assert(folder/'update_once.json').exists();folder=folder/a.phase;folder.mkdir(exist_ok=True);assert not(folder/'update_once.json').exists()
  got=read_only_call(api,cfg,'alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'});p=got['product'];save(folder/'before_get.json',got)
  if a.phase:
   original=load(folder.parent/'before_get.json')['product'];first=load(folder.parent/'after_get.json')['product'];assert p==first==original,'Observed write must remain unapplied with all original values preserved'
   save(folder.parent/'reconciliation.json',{'product_id':pid,'status':'TWO_INDEPENDENT_FORMAL_READS_ORIGINAL_VALUES_UNCHANGED_CORRECTIVE_PREPARED','first_read_at':previous['at'],'second_read_at':datetime.now(timezone.utc).isoformat(),'second_read_file':'未生效修复/before_get.json','original_callback_preserved':True,'original_fields_unchanged':True,'original_company_images_unchanged':True,'new_request_difference':'New current Schema request explicitly preserves original productTitle; original request had companyImage only','allow_single_corrective_attempt':True,'source_state_unchanged':True})
  assert p['status']=='approved' and p['display'] in ('Y','N')
  if not historical:
   assert buyer.apostrophe_equivalent(buyer.formal_copy(p)['highlights'],copy['highlights']) and buyer.faq_pairs_equivalent(buyer.formal_copy(p)['faq'],copy['faq'])
  rendered=read_only_call(api,cfg,'alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US'}});save(folder/'before_render.json',rendered);assert rendered.get('data'),'Wait current editable Schema'
  schema=E.fromstring(rendered['data']);company=schema.find("./field[@id='companyImage']");assert company is not None
  options={int(x.get('value')):x.get('displayName')for x in company.findall("./fields/field[@id='gallery']/options/option")};assert all(options.get(i)==name for _,i,name in ROLES)
  field_ids=['companyImage','productTitle']if a.preserve_title else['companyImage']
  root=pub.values_only(schema,operation='update',field_ids=field_ids)
  if a.preserve_title:
   title=root.find("./field[@id='productTitle']/value");assert title is not None and title.text==p['subject'],'Editable title must equal current formal value before explicit preservation'
  assets=[bank['items'][key]for key,_,_ in ROLES];pub.set_gallery(root,'companyImage',assets,[(i,name)for _,i,name in ROLES])
  deps=['productDescType'] if schema.find("./field[@id='productDescType']") is not None else []
  assert {x.get('id')for x in root.findall('./field')}==set(field_ids)
  current=folder/'current_schema.xml';current.write_text(rendered['data'],encoding='utf8');payload=folder/'payload.xml';payload.write_text(E.tostring(root,encoding='unicode'),encoding='utf8')
  rel=lambda x:x.relative_to(ROOT).as_posix()
  sources=[rel(FACTORY/'制作档案.json'),rel(FACTORY/'当前上传回执.json'),rel(FACTORY/'图片银行像素核对.json'),rel(FACTORY/'替换准备.json')]
  if not historical:sources.append(rel(c/'copy.json'))
  manifest={'operation':'update','product_id':pid,'category_id':p['category_id'],'facts_reviewed':True,'source_evidence':sources,'current_schema':current.name,'current_schema_sha256':sha(current),'schema_request_id':rendered['request_id'],'schema_acquired_at':datetime.now(timezone.utc).isoformat(),'payload_xml':payload.name,'field_ids':field_ids,'dependency_ids':deps,'title_value_preserved':a.preserve_title}
  # The shared scoped preparer copies declared dependency values from this
  # target's current Schema and rejects changes or additional payload fields.
  save(folder/'manifest.json',manifest);prepared=pub.load_submission_manifest(folder/'manifest.json','update',pid)
  assert set(prepared['expected_fields'])==set(field_ids)
  assert {x.get('id')for x in E.fromstring(prepared['xml']).findall('./field')}==set(field_ids+deps)
  save(folder/'prepared.json',prepared)
  save(folder/'readiness.json',{'at':datetime.now(timezone.utc).isoformat(),'status':'MINIMAL_SCHEMA_PREPARED_NOT_SUBMITTED','copy_status':verification['status'] if verification else 'HISTORICAL_COPY_DEFERRED','copy_public_status':verification['public_status'] if verification else 'HISTORICAL_COPY_DEFERRED','copy_sha256':sha(c/'copy.json') if copy else None,'historical_company_only':historical,'source_status_unchanged':True,'asset_version':6,'bank_file_ids':[x['file_id']for x in assets],'field_scope':field_ids,'title_value_preserved':a.preserve_title,'dependency_ids':deps,'requires_fresh_prewrite_compare':True,'requires_first_update_formal_and_public_diagnosis_before_bulk':True,'product_fields_written':False})
  error=folder/'preparation_error.json'
  if error.exists():error.unlink()
  print(json.dumps({'product_id':pid,'status':'MINIMAL_SCHEMA_PREPARED_NOT_SUBMITTED','images':5,'unrelated_fields_in_payload':0},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
