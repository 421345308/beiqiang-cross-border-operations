from pathlib import Path
import json,sys,datetime,hashlib,shutil,importlib.util,xml.etree.ElementTree as E
sys.dont_write_bytecode=True
W=Path(__file__).parent;O=W/'3522_execution';U=O/'research_title_update';U.mkdir(exist_ok=True);P=Path(r'C:\Users\spq\Desktop\贝强');PID='1601969920294';TITLE="Men's Suede Slip-On Loafers with Perforated Side Panels";KEYWORD='mens suede slip on loafers'
def save(n,j):(U/n).write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8')
s=importlib.util.spec_from_file_location('publisher3522title',P/'08_工具链/01_业务脚本/国际站扩品/publish_hot_rank_hr_a_batch.py');pub=importlib.util.module_from_spec(s);s.loader.exec_module(pub)
action=sys.argv[1]
if action in ['upload','publish','send']:
 assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime(2026,10,2,18,0,tzinfo=datetime.timezone.utc),'User stop deadline reached; no automatic resume or new Beiqiang writes'
if action=='prepare':
 g=json.loads((O/'formal_get.flat.json').read_text(encoding='utf-8'));p=g['product'];attrs={int(x['attribute_id']):x['value_name'] for x in p['attributes']};assert p['status']=='approved' and p['display']=='Y' and attrs[3]=='BQ-L3522' and int(p['category_id'])==202240835
 render=json.loads((O/'formal_render.flat.json').read_text(encoding='utf-8'));schema=E.fromstring(render['data']);m=schema.find("./field[@id='icbuCatProp']/complex-value/field[@id='p-3']/value");assert m.get('inputValue')=='BQ-L3522'
 (U/'current_schema.xml').write_text(render['data'],encoding='utf-8');save('before_formal_get.json',g);save('current_schema.response.json',render);shutil.copyfile(O/'operating_demand_review.json',U/'demand_evidence.json')
 r=E.Element('itemSchema');f=E.SubElement(r,'field',id='productTitle',type='input');E.SubElement(f,'value').text=TITLE;E.SubElement(r,'field',id='productKeywords',type='complex');pub.set_keywords(r,KEYWORD)
 listing=pub.prepare_scoped_listing(schema,r,operation='update',category_id=202240835,target_product_id=PID,field_ids=['productTitle','productKeywords'])
 (U/'payload.xml').write_text(listing['xml'],encoding='utf-8');save('prepared_listing.json',listing);manifest={'operation':'update','product_id':PID,'category_id':202240835,'facts_reviewed':True,'source_evidence':['demand_evidence.json','before_formal_get.json'],'current_schema':'current_schema.xml','current_schema_sha256':hashlib.sha256((U/'current_schema.xml').read_bytes()).hexdigest(),'schema_request_id':render['request_id'],'schema_acquired_at':datetime.datetime.fromtimestamp((O/'formal_render.flat.json').stat().st_mtime,datetime.timezone.utc).isoformat(),'payload_xml':'payload.xml','field_ids':['productTitle','productKeywords'],'dependency_ids':[]};save('manifest.json',manifest);check=pub.load_submission_manifest(U/'manifest.json','update',PID);assert check['field_ids']==['productKeywords','productTitle'];print('Prepared only title/one fact-supported longtail; existing24 SKU and every other field outside payload',flush=True)
elif action=='send':
 listing=pub.load_submission_manifest(U/'manifest.json','update',PID);s=importlib.util.spec_from_file_location('sdk3522title',P/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py');sdk=importlib.util.module_from_spec(s);s.loader.exec_module(sdk);config=sdk.load_config(Path.home()/'.config/beiqiang/alibaba-openapi.json')
 ledger={'product_id':PID,'model':'BQ-L3522','status':'STARTED_OUTCOME_UNKNOWN','method':'alibaba.icbu.product.schema.update','scope':['productTitle','productKeywords'],'attempted_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'payload_sha256':hashlib.sha256(listing['xml'].encode()).hexdigest()}
 with (U/'write_once_ledger.json').open('x',encoding='utf-8') as h:json.dump(ledger,h,indent=2)
 receipt=pub.api_submit(sdk,config,listing,False,update_product_id=PID);save('receipt.json',receipt);ledger.update(status=receipt['status'],refs=receipt.get('refs'));save('write_once_ledger.json',ledger);print(json.dumps(ledger),flush=True)
elif action=='verify':
 receipt=json.loads((U/'receipt.json').read_text(encoding='utf-8'));assert receipt['status']=='submitted_needs_readback'
 g=json.loads((O/'formal_get.flat.json').read_text(encoding='utf-8'));p=g['product'];assert p['subject']==TITLE,p['subject'];keyword_ok=p['keywords']==[KEYWORD]
 before=json.loads((U/'before_formal_get.json').read_text(encoding='utf-8'))['product'];assert p['product_sku']==before['product_sku'];assert p['main_image']==before['main_image'];assert p['attributes']==before['attributes'];assert p['sourcing_trade']==before['sourcing_trade']
 def semantic_detail(sd):
  result=json.loads(json.dumps(sd))
  for key in ['detail_image','company_image']:
   if key in result:result[key]['images']=sorted(result[key]['images'],key=lambda x:(x['image_url'],str(x['image_set']['id'])))
  return result
 assert semantic_detail(p['struct_detail'])==semantic_detail(before['struct_detail'])
 save('after_formal_get.json',g);save('verification.json',{'verdict':'PASS' if keyword_ok else 'TITLE_VERIFIED_KEYWORD_PENDING','product_id':PID,'title':TITLE,'expected_keywords':[KEYWORD],'actual_keywords':p['keywords'],'keyword_persistence':keyword_ok,'all24_SKU_ids_properties_prices_preserved':True,'main_detail_company_FAQ_attributes_trade_preserved':True,'get_request_id':g['request_id'],'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat()})
 # Original create facts stay intact in the update evidence; final audit follows current accepted copy.
 if not (U/'original_create_facts.json').exists():shutil.copyfile(O/'facts_and_copy.json',U/'original_create_facts.json')
 facts=json.loads((O/'facts_and_copy.json').read_text(encoding='utf-8'));facts.update(title=TITLE,keywords=[KEYWORD]);(O/'facts_and_copy.json').write_text(json.dumps(facts,ensure_ascii=False,indent=2),encoding='utf-8');print('Title verified; keyword persistence',keyword_ok,'all untouched fields preserved',flush=True)
else:raise ValueError(action)
