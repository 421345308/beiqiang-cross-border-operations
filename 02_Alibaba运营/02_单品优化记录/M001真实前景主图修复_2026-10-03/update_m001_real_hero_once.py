from pathlib import Path
import json,sys,importlib.util,datetime,os,hashlib,xml.etree.ElementTree as E,re
sys.dont_write_bytecode=True;sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path('C:/Users/spq/Desktop/贝强');OUT=Path(__file__).resolve().parent/'single_agent_resume_2310/slipper_publish/M001/real_foreground_composite'
sys.path.insert(0,str(ROOT/'08_工具链/01_业务脚本/国际站扩品'))
import publish_hot_rank_hr_a_batch as pub
from schema_publish_contract import prepare_scoped_listing,safe_exception_evidence
spec=importlib.util.spec_from_file_location('sdk',ROOT/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py');sdk=importlib.util.module_from_spec(spec);spec.loader.exec_module(sdk)
config=sdk.load_config(sdk.DEFAULT_CONFIG);sdk.http_json=lambda request,timeout=60:sdk.native_http_json(request,timeout=60)
PID='1601970169467';ENC='AAGpjmk4AOWGex-cDVm8WuGY'
def save(name,value):
 p=OUT/name;t=p.with_suffix('.tmp');t.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(t,p)
def read(name,method,params):
 assert not (OUT/name).exists()
 try:r=sdk.redact_tokens(sdk.top_call(config,method,params));err=sdk.api_error(r)
 except Exception as exc:r=None;err=safe_exception_evidence(exc,config)
 v={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'response':r,'error':err};save(name,v);assert not err and r;return r
def reserve(name):
 with (OUT/name).open('x',encoding='utf-8') as f:json.dump({'status':'STARTED_UNKNOWN_NO_RETRY','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},f);f.flush();os.fsync(f.fileno())
phase=sys.argv[1]
if phase=='prepare':
 before=read('before_get.json','alibaba.icbu.product.get',{'product_id':ENC,'language':'ENGLISH'})['product'];assert before['status']=='approved' and before['display']=='Y'
 render=read('before_render.json','alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(PID),'language':'en_US'}})
 xml=E.fromstring(render['data']);fields=[{'id':f.get('id'),'type':f.get('type'),'values':[v.text for v in f.findall('values/value')]} for f in xml.findall('field') if 'image' in f.get('id','').lower()]
 save('image_fields.json',fields);print(json.dumps(fields,ensure_ascii=False))
elif phase=='upload':
 proof=json.loads((OUT/'provenance.json').read_text(encoding='utf-8'));assert proof['qa']=='PASS' and proof['opaque_foreground_pixel_equality'] and proof['background_generated']
 photo=OUT/'M001_real_composite.jpg';assert hashlib.sha256(photo.read_bytes()).hexdigest()==proof['output_sha256'];reserve('upload_once.json')
 try:r=sdk.redact_tokens(sdk.upload_image(config,photo,None));err=sdk.api_error(r)
 except Exception as exc:r=None;err=safe_exception_evidence(exc,config)
 asset=(r or {}).get('upload_image_response') or {};ok=not err and asset.get('file_id') and asset.get('photobank_url')
 save('upload_once.json',{'status':'UPLOADED_BUSINESS_VERIFIED' if ok else 'STOP_NO_RETRY','response':r,'error':err});assert ok;print(json.dumps({'file_id':asset['file_id'],'url':asset['photobank_url'],'request_id':r.get('request_id')}))
elif phase.startswith('submit'):
 before=json.loads((OUT/'before_get.json').read_text(encoding='utf-8'))['response']['product'];render=json.loads((OUT/'before_render.json').read_text(encoding='utf-8'))['response']['data']
 fresh=read(phase+'_presubmit_get.json','alibaba.icbu.product.get',{'product_id':ENC,'language':'ENGLISH'})['product'];assert fresh==before,'Concurrent product change requires re-review'
 asset=json.loads((OUT/'upload_once.json').read_text(encoding='utf-8'));assert asset['status']=='UPLOADED_BUSINESS_VERIFIED';url=asset['response']['upload_image_response']['photobank_url'];url='https:'+url if url.startswith('//') else url
 current=E.fromstring(render);field=current.find("./field[@id='scImages']");assert field is not None
 old=before['main_image']['images'];assert len(old)==6 and len(field.findall('complex-value/field'))==6
 intended=E.Element('itemSchema');E.SubElement(intended,'field',id='scImages',type='complex')
 pub.set_main_images(intended,[{'url':url,'file_id':asset['response']['upload_image_response']['file_id']}]+[{'url':u,'file_id':field.find("./complex-value/field[@id='scImages_"+str(i)+"']/value").get('fileId','0')} for i,u in enumerate(old) if i>0])
 listing=prepare_scoped_listing(current,intended,operation='update',category_id=int(before['category_id']),target_product_id=PID,field_ids=['scImages'],dependency_ids=[])
 save('prepared_listing.json',listing);(OUT/'reviewed_payload.xml').write_text(listing['xml'],encoding='utf-8');reserve('update_once_receipt.json')
 result=pub.api_submit(sdk,config,listing,draft=False,update_product_id=PID);save('update_once_receipt.json',sdk.redact_tokens(result));print(json.dumps(result,ensure_ascii=False))
elif phase.startswith('review'):
 p=read(phase+'_get.json','alibaba.icbu.product.get',{'product_id':ENC,'language':'ENGLISH'})['product'];score=read(phase+'_score.json','alibaba.icbu.product.score.get',{'product_id':ENC})
 before=json.loads((OUT/'before_get.json').read_text(encoding='utf-8'))['response']['product'];asset=json.loads((OUT/'upload_once.json').read_text(encoding='utf-8'))['response']['upload_image_response'];url=asset['photobank_url'];url='https:'+url if url.startswith('//') else url
 preserved={k:p.get(k)==v for k,v in before.items() if k not in ['main_image','modified_time','gmt_modified','status','display','struct_detail']}
 detail={k:p['struct_detail'].get(k)==v for k,v in before['struct_detail'].items() if k!='detail_image'}
 # Alibaba may reorder detail image entries despite no detailImage field in payload.
 old_details=before['struct_detail']['detail_image']['images'];new_details=p['struct_detail']['detail_image']['images'];detail['detail_image_same_items']=sorted(json.dumps(x,sort_keys=True) for x in old_details)==sorted(json.dumps(x,sort_keys=True) for x in new_details)
 token=lambda u:re.findall(r'/kf/(H[^/]+)',u)[0].split('.')[0]
 row={'product_id':PID,'status':p['status'],'display':p['display'],'actual_score':score.get('result'),'first_image_matches':token(p['main_image']['images'][0])==token(url),'other_images_unchanged':p['main_image']['images'][1:]==before['main_image']['images'][1:],'all_other_business_content_unchanged':all(preserved.values()) and all(detail.values()),'field_comparison':preserved,'detail_comparison':detail,'detail_image_order_unchanged':old_details==new_details,'get_request_id':json.loads((OUT/(phase+'_get.json')).read_text(encoding='utf-8'))['response'].get('request_id'),'score_request_id':score.get('request_id')};save(phase+'_summary.json',row);print(json.dumps(row,ensure_ascii=False))
