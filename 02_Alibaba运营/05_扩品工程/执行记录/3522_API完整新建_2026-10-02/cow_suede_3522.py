from pathlib import Path
import json,sys,datetime,hashlib,shutil,importlib.util,xml.etree.ElementTree as E
sys.dont_write_bytecode=True
W=Path(__file__).parent;O=W/'3522_execution';D=O/'cow_suede_attribute_repair';D.mkdir(exist_ok=True);P=Path(r'C:\Users\spq\Desktop\贝强');PID='1601969920294'
def save(n,j):(D/n).write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8')
s=importlib.util.spec_from_file_location('publisher3522suede',P/'08_工具链/01_业务脚本/国际站扩品/publish_hot_rank_hr_a_batch.py');pub=importlib.util.module_from_spec(s);s.loader.exec_module(pub)
action=sys.argv[1]
if action in ['upload','publish','send']:
 assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime(2026,10,2,18,0,tzinfo=datetime.timezone.utc),'User stop deadline reached; no automatic resume or new Beiqiang writes'
if action=='prepare':
 g=json.loads((O/'formal_get.flat.json').read_text(encoding='utf-8'));p=g['product'];a={int(x['attribute_id']):x['value_name'] for x in p['attributes']};assert a[3]=='BQ-L3522' and a[191290428]=='Genuine Leather' and int(p['category_id'])==202240835
 old=json.loads((O/'formal_render.flat.json').read_text(encoding='utf-8'));schema=E.fromstring(old['data']);definition=schema.find("./field[@id='icbuCatProp']/fields/field[@id='p-191290428']");assert definition.get('type')=='multiCheck' and any(x.get('name')=='valueAttributeRule' and x.get('value')=='inputValue' for x in definition.findall('./rules/rule'))
 r=E.Element('itemSchema');field=E.fromstring(E.tostring(schema.find("./field[@id='icbuCatProp']"),encoding='unicode'));r.append(field);n=field.find("./complex-value/field[@id='p-191290428']");assert n is not None
 for child in list(n):n.remove(child)
 E.SubElement(E.SubElement(n,'values'),'value',inputValue='Cow suede').text='-2'
 listing=pub.prepare_scoped_listing(schema,r,operation='update',category_id=202240835,target_product_id=PID,field_ids=['icbuCatProp'],expected_model='BQ-L3522')
 root=E.fromstring(listing['xml']);after=root.find("./field[@id='icbuCatProp']/complex-value/field[@id='p-191290428']/values/value");assert after.get('inputValue')=='Cow suede' and after.text=='-2'
 (D/'current_schema.xml').write_text(old['data'],encoding='utf-8');save('current_schema.response.json',old);save('before_formal_get.json',g);save('score_diagnostic_before.json',json.loads((O/'score_timestamp.json').read_text(encoding='utf-8')));shutil.copyfile(O/'source/source_attributes.json',D/'source_attributes.json');(D/'payload.xml').write_text(listing['xml'],encoding='utf-8');save('prepared_listing.json',listing)
 manifest={'operation':'update','product_id':PID,'category_id':202240835,'facts_reviewed':True,'source_evidence':['source_attributes.json','before_formal_get.json','score_diagnostic_before.json'],'current_schema':'current_schema.xml','current_schema_sha256':hashlib.sha256((D/'current_schema.xml').read_bytes()).hexdigest(),'schema_request_id':old['request_id'],'schema_acquired_at':datetime.datetime.fromtimestamp((O/'formal_render.flat.json').stat().st_mtime,datetime.timezone.utc).isoformat(),'payload_xml':'payload.xml','field_ids':['icbuCatProp'],'dependency_ids':[],'expected_model':'BQ-L3522'};save('manifest.json',manifest);assert pub.load_submission_manifest(D/'manifest.json','update',PID)['field_ids']==['icbuCatProp'];print('Prepared exact source Cow suede custom property; current other product attributes/model preserved; no other top-level fields',flush=True)
elif action=='send':
 listing=pub.load_submission_manifest(D/'manifest.json','update',PID);g=json.loads((O/'formal_get.flat.json').read_text(encoding='utf-8'));assert g['product']['status']=='approved' and g['product']['display']=='Y';s=importlib.util.spec_from_file_location('sdk3522suede',P/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py');sdk=importlib.util.module_from_spec(s);s.loader.exec_module(sdk);config=sdk.load_config(Path.home()/'.config/beiqiang/alibaba-openapi.json');log={'product_id':PID,'model':'BQ-L3522','method':'alibaba.icbu.product.schema.update','scope':'icbuCatProp; only upper material value refined; all other present attributes/model preserved','status':'STARTED_OUTCOME_UNKNOWN','attempted_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'payload_sha256':hashlib.sha256(listing['xml'].encode()).hexdigest()}
 with (D/'write_once_ledger.json').open('x',encoding='utf-8') as h:json.dump(log,h,indent=2)
 receipt=pub.api_submit(sdk,config,listing,False,update_product_id=PID);save('receipt.json',receipt);log.update(status=receipt['status'],refs=receipt.get('refs'));save('write_once_ledger.json',log);print(json.dumps(log),flush=True)
else:raise ValueError(action)
