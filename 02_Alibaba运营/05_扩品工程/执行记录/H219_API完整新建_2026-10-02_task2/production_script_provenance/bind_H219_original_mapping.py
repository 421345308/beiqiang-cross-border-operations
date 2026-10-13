from pathlib import Path
import json,hashlib,os,tempfile
W=Path(__file__).resolve().parent;O=W/'H219_execution';P=Path.home()/'Desktop'/'贝强'
mapping=next((P/'02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21').glob('*一对一*.json'))
raw=mapping.read_bytes();data=json.loads(raw);row=next(x for x in data['rows'] if x.get('candidate')=='H219')
assert row['old_product_id']=='1601943767092' and row['new_product_id'] is None and row['protected'] is False
expected='STRATEGIC_RETIRE_AND_REAL_SOURCE_REPLACEMENT_NOT_IDENTICAL_SHOE'
assert row['match_type'] in ['STRATEGIC_RETIRE_NOT_IDENTICAL_SHOE',expected]
if row['match_type']!=expected:
 before=dict(row);row['match_type']=expected
 # One enum spelling only, same strategic/not-identical semantics. Preserve
 # all other candidates, IDs, protection, authorization and retirement fields.
 assert hashlib.sha256(mapping.read_bytes()).digest()==hashlib.sha256(raw).digest(),'Owner mapping changed; stop instead of overwriting another writer'
 with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=mapping.parent,prefix='H219_mapping_',suffix='.tmp',delete=False) as file:
  json.dump(data,file,ensure_ascii=False,indent=2);target=Path(file.name)
 os.replace(target,mapping)
 (O/'mapping_enum_alignment_receipt.json').write_text(json.dumps({'original_path':str(mapping),'before_row':before,'after_row':row,'changed_fields':['match_type'],'reason':'Align the already assigned strategic-not-identical enum to existing mature manifest bridge; no scope/old-off authorization added'},ensure_ascii=False,indent=2),encoding='utf-8')
pack=json.loads((O/'task_pack.json').read_text(encoding='utf-8'))
pack['evidence_files']=[x for x in pack['evidence_files'] if x['kind']!='replacement_mapping']
pack['evidence_files'].append({'path':str(mapping),'sha256':hashlib.sha256(mapping.read_bytes()).hexdigest(),'kind':'replacement_mapping'})
for evidence in pack['evidence_files']:
 path=O/evidence['path'];evidence['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
(O/'task_pack.json').write_text(json.dumps(pack,ensure_ascii=False,indent=2),encoding='utf-8')
print('Bound exact canonical template and original assigned mapping; only H219 enum spelling aligned; no platform call.')
