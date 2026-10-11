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
 ap=argparse.ArgumentParser();ap.add_argument('--ids',required=True);a=ap.parse_args();sys.stdout.reconfigure(encoding='utf8')
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
  c=COPY/pid;verification=load(c/'verification.json');copy=load(c/'copy.json')
  assert verification['status']=='FORMAL_PASS','Current copy must pass before preparing replacement for this ID'
  folder=FACTORY/'商品'/pid;folder.mkdir(parents=True,exist_ok=True)
  got=read_only_call(api,cfg,'alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'});p=got['product'];save(folder/'before_get.json',got)
  assert p['status']=='approved' and p['display']=='Y'
  assert buyer.apostrophe_equivalent(buyer.formal_copy(p)['highlights'],copy['highlights']) and buyer.faq_pairs_equivalent(buyer.formal_copy(p)['faq'],copy['faq'])
  rendered=read_only_call(api,cfg,'alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US'}});save(folder/'before_render.json',rendered);assert rendered.get('data'),'Wait current editable Schema'
  schema=E.fromstring(rendered['data']);company=schema.find("./field[@id='companyImage']");assert company is not None
  options={int(x.get('value')):x.get('displayName')for x in company.findall("./fields/field[@id='gallery']/options/option")};assert all(options.get(i)==name for _,i,name in ROLES)
  root=pub.values_only(schema,operation='update',field_ids=['companyImage'])
  assets=[bank['items'][key]for key,_,_ in ROLES];pub.set_gallery(root,'companyImage',assets,[(i,name)for _,i,name in ROLES])
  deps=['productDescType'] if schema.find("./field[@id='productDescType']") is not None else []
  assert {x.get('id')for x in root.findall('./field')}=={'companyImage'}
  current=folder/'current_schema.xml';current.write_text(rendered['data'],encoding='utf8');payload=folder/'payload.xml';payload.write_text(E.tostring(root,encoding='unicode'),encoding='utf8')
  rel=lambda x:x.relative_to(ROOT).as_posix()
  manifest={'operation':'update','product_id':pid,'category_id':p['category_id'],'facts_reviewed':True,'source_evidence':[rel(FACTORY/'制作档案.json'),rel(FACTORY/'当前上传回执.json'),rel(FACTORY/'图片银行像素核对.json'),rel(c/'copy.json')],'current_schema':current.name,'current_schema_sha256':sha(current),'schema_request_id':rendered['request_id'],'schema_acquired_at':datetime.now(timezone.utc).isoformat(),'payload_xml':payload.name,'field_ids':['companyImage'],'dependency_ids':deps}
  # The shared scoped preparer copies declared dependency values from this
  # target's current Schema and rejects changes or additional payload fields.
  save(folder/'manifest.json',manifest);prepared=pub.load_submission_manifest(folder/'manifest.json','update',pid)
  assert set(prepared['expected_fields'])=={'companyImage'}
  assert {x.get('id')for x in E.fromstring(prepared['xml']).findall('./field')}==set(['companyImage']+deps)
  save(folder/'prepared.json',prepared)
  save(folder/'readiness.json',{'at':datetime.now(timezone.utc).isoformat(),'status':'MINIMAL_SCHEMA_PREPARED_NOT_SUBMITTED','copy_status':verification['status'],'copy_public_status':verification['public_status'],'copy_sha256':sha(c/'copy.json'),'asset_version':6,'bank_file_ids':[x['file_id']for x in assets],'field_scope':['companyImage'],'dependency_ids':deps,'requires_fresh_prewrite_compare':True,'requires_first_update_formal_and_public_diagnosis_before_bulk':True,'product_fields_written':False})
  print(json.dumps({'product_id':pid,'status':'MINIMAL_SCHEMA_PREPARED_NOT_SUBMITTED','images':5,'unrelated_fields_in_payload':0},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
