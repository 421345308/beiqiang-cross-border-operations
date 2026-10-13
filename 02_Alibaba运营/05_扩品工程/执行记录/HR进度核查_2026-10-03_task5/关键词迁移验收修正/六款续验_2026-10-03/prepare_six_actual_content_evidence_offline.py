from pathlib import Path
import json,re,hashlib,xml.etree.ElementTree as E,sys
sys.stdout.reconfigure(encoding='utf8')
b=Path(__file__).parent;o=b/'six_version_acceptance_resume';norm=lambda s:re.sub(r'\s+',' ',s).strip()
name=sys.argv[1];assert name in ['2627BSK','805','H219','F2888','936'];d=o/name
old_record=json.loads((b/'hr_public_readonly_20261003'/f'{name}_get.json').read_text(encoding='utf8'));old_response=old_record.get('response') or old_record;old=old_response['product'];check=json.loads((b/'hr_public_readonly_20261003'/f'{name}_minimal_checklist.json').read_text(encoding='utf8'));fresh_recheck=None
if name in ['2627BSK','H219']:
 get=json.loads((d/'current_formal_get.json').read_text(encoding='utf8'));product=get['response'].get('product') or {};error=get['error'];get_source=d/'current_formal_get.json';get_request=get['response'].get('request_id')
else:
 rec=json.loads((b/'four_content_mapping_readonly'/f'{name}.json').read_text(encoding='utf8'));product=old;error=rec['get_error'];get_source=b/'hr_public_readonly_20261003'/f'{name}_get.json';get_request=old_response.get('request_id');get={'at_utc':old_record.get('at_utc') or old_record.get('observed_at_utc') or check['observed_at_utc']};fresh_recheck={'source':str((b/'four_content_mapping_readonly'/f'{name}.json').relative_to(b)),'at_utc':rec['at_utc'],'request_id':rec['get_request_id'],'summary':rec['product_summary'],'status':rec['status'],'display':rec['display'],'error':rec['get_error']}
if name=='2627BSK':
 schema_source=d/'current_schema.xml';schema=E.parse(schema_source).getroot();render_request=json.loads((d/'current_render.json').read_text(encoding='utf8'))['response'].get('request_id')
else:
 schema_source=b/'four_content_mapping_readonly'/f'{name}_textDesc.xml';schema=E.Element('itemSchema');schema.append(E.parse(schema_source).getroot());render_request=json.loads((b/'four_content_mapping_readonly'/f'{name}.json').read_text(encoding='utf8'))['render_request_id']
summary=product.get('struct_detail',{}).get('product_summary');desc=schema.findtext("./field[@id='textDesc']/value")
pub=[]
if isinstance(summary,str) and summary.strip():
 for file in list((b/'hr_public_readonly_20261003/visible'/name).glob('description*.json'))+list((d/'public').glob('description*.json')):
  ui=json.loads(file.read_text(encoding='utf-8-sig'));text=' '.join(str(x.get('name','')) for x in ui.get('rows',[]) if not x.get('offscreen'))
  if norm(summary) in norm(text):pub.append({'path':str(file.relative_to(b)),'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'at_utc':ui.get('atUTC')})
notice_sources=sorted(d.glob('*.json'));notices=[]
for file in notice_sources:
 if file.name in ['current_formal_get.json','current_render.json','prepared_evidence.json']:continue
 ui=json.loads(file.read_text(encoding='utf-8-sig'))
 for n in ui.get('notice',[]):
  if n.get('titleBound'):notices.append({'path':str(file.relative_to(b)),'notice':n['text'],'at_utc':ui['atUTC'],'address':ui['address']})
selling=d/'selling.json';ui_match=False;ui_time=None
if selling.exists() and isinstance(summary,str):
 ui=json.loads(selling.read_text(encoding='utf-8-sig'));ui_time=ui['atUTC'];ui_match=any(norm(summary) in norm(x.get('pageText','')) for x in ui.get('documents',[]))
equal=bool(summary) and summary==desc and not error
if fresh_recheck:equal=equal and fresh_recheck['summary']==summary and fresh_recheck['status']=='approved' and fresh_recheck['display']=='Y'
proof={'candidate':name,'product_id':str(check['product_id']),'category_id':str(check['category_id']),'encrypted_product_id':product.get('product_id'),'formal_get_request':get_request,'render_request':render_request,'formal_get_source':str(get_source.relative_to(b)),'render_source':str(schema_source.relative_to(b)),'formal_get_at_utc':get['at_utc'],'fresh_formal_recheck':fresh_recheck,'UI_at_utc':ui_time,'product_get':{'request_id':get_request,'product':product},'schema_xml':E.tostring(schema,encoding='unicode'),'summary':summary,'summary_characters':len(summary or ''),'formal_error':error,'formal_render_equal':equal,'current_UI_full_text_equal':ui_match,'current_UI_notices':notices,'public_matches':pub,'platform_writes':0}
proof['content_ready']=bool(notices) and ui_match and proof['formal_render_equal'] and bool(pub) and product.get('status')=='approved' and product.get('display')=='Y'
(d/'prepared_evidence.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:proof[k] for k in ['candidate','summary_characters','formal_render_equal','current_UI_full_text_equal','content_ready']}|{'notices':len(notices),'public_matches':len(pub),'get_request':get_request,'render_request':render_request},ensure_ascii=False))
