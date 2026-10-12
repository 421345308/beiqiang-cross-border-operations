"""Prepare/submit/verify an exact original-title restoration after gallery QA.

Only an observed subject difference qualifies. Never replay a repair ledger.
No new shoe claims; retain original and current raw formal responses.
"""
import argparse,sys,copy
from xml.etree import ElementTree as E
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import replace_company_gallery as op

def main():
 ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','submit','verify']);ap.add_argument('--id',required=True);a=ap.parse_args();pid=a.id
 prep=op.load(op.BASE/'替换准备.json');assert pid in prep['eligible_ids']
 f=op.BASE/'商品'/pid/'标题差异修复';f.mkdir(exist_ok=True)
 api,cfg=op.b.api_client();get=lambda:op.read_only_call(api,cfg,'alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'})
 original=op.load(f.parent/'before_get.json')['product']['subject']
 if a.mode=='prepare':
  assert not(f/'update_once.json').exists();got=get();p=got['product'];assert p['subject']!=original and p['status']=='approved'
  op.save(f/'before_get.json',got)
  r=op.read_only_call(api,cfg,'alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US'}});op.save(f/'before_render.json',r);root=E.fromstring(r['data']);title=root.find("./field[@id='productTitle']");assert title is not None and title.find('./value').text==p['subject']
  payload=op.pub.values_only(root,operation='update',field_ids=['productTitle']);payload.find("./field[@id='productTitle']/value").text=original
  (f/'current_schema.xml').write_text(r['data'],encoding='utf8');(f/'payload.xml').write_text(E.tostring(payload,encoding='unicode'),encoding='utf8')
  op.save(f/'manifest.json',{'operation':'update','product_id':pid,'category_id':p['category_id'],'facts_reviewed':True,'source_evidence':[(f.parent/'before_get.json').relative_to(op.ROOT).as_posix(),(f.parent/'non_target_difference.json').relative_to(op.ROOT).as_posix()],'current_schema':'current_schema.xml','current_schema_sha256':op.b.sha(f/'current_schema.xml'),'schema_request_id':r['request_id'],'schema_acquired_at':op.now(),'payload_xml':'payload.xml','field_ids':['productTitle'],'dependency_ids':[]})
  listing=op.pub.load_submission_manifest(f/'manifest.json','update',pid);assert set(listing['field_ids'])=={'productTitle'};op.save(f/'prepared.json',listing)
  print({'id':pid,'original_title_to_restore':original,'current_title':p['subject'],'write':False});return
 if a.mode=='submit':
  assert not(f/'update_once.json').exists();got=get();op.save(f/'immediate_prewrite_get.json',got);assert got['product']==op.load(f/'before_get.json')['product']
  listing=op.pub.load_submission_manifest(f/'manifest.json','update',pid);assert listing['field_ids']==['productTitle'] and E.fromstring(listing['xml']).find("./field[@id='productTitle']/value").text==original
  with(f/'update_once.json').open('x',encoding='utf8')as h:h.write('{"status":"STARTED_OUTCOME_UNKNOWN"}')
  receipt=op.pub.api_submit(api,cfg,listing,False,update_product_id=pid);op.save(f/'update_receipt.json',receipt);print({'id':pid,'status':receipt['status']});return
 got=get();op.save(f/'after_get.json',got);p=got['product'];old=op.load(f/'before_get.json')['product'];differences=op.field_differences(old,p)
 allowed={'subject','pc_detail_url'};same=set(differences)<=allowed
 result={'product_id':pid,'at':op.now(),'original_title':original,'actual_title':p['subject'],'title_restored':p['subject']==original,'other_fields_preserved':same,'differences':differences,'product_status':p['status'],'display':p['display'],'display_preserved':p['display']==old['display'],'status':'RESTORATION_FORMAL_PASS'if p['status']=='approved'and p['subject']==original and same and p['display']==old['display']else'PENDING_OR_DIAGNOSE_NO_REPLAY'}
 op.save(f/'verification.json',result);print(result)
if __name__=='__main__':main()
