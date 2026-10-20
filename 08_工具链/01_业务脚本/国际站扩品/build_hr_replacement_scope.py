"""Reconcile HR scope with a complete official catalog and current registry.

Candidate/missing registry labels do not establish that an existing page lacks
an actual shoe. Preserve every ID's evidence and distinguish unresolved history.
"""

import sys as _registry_sys
from pathlib import Path as _RegistryPath
_registry_sys.path.insert(0, str(_RegistryPath(__file__).resolve().parents[3]/"08_工具链/06_工作区维护"))
from product_registry import ProductRegistry
from pathlib import Path
from collections import Counter
from datetime import datetime
import hashlib,json,argparse

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'02_Alibaba运营/05_扩品工程/执行记录/HR实源替换'
CAT=ROOT/'99_临时区/HR实源替换/全量目录/catalog.json'
REG=ProductRegistry(ROOT)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--catalog',type=Path,default=CAT);args=parser.parse_args();catalog_path=args.catalog
    if not catalog_path.is_absolute():catalog_path=ROOT/catalog_path
    catalog=json.loads(catalog_path.read_text(encoding='utf8'))
    assert catalog['complete'] and len(catalog['products'])==catalog['unique_ids']==catalog['total_item']
    current={str(p['id']):p for p in catalog['products']}
    registry=json.loads(REG.read_text(encoding='utf8'))
    products={p['id']:p for p in registry['products']}
    scope=json.loads((BASE/'scope.json').read_text(encoding='utf8'))
    target_ids={pid for ids in scope['targets'].values()for pid in ids.values()}
    rows=[]
    for l in registry['listings']:
        if not l.get('model','').startswith('HR'):continue
        pid=l['id'];live=current.get(pid);p=products[l['product_id']]
        formal=BASE/'商品'/pid/'verification.json'
        proof=json.loads(formal.read_text(encoding='utf8'))if formal.exists()else{}
        latest=l.get('current_platform_fields',{})
        use_latest=False
        if latest.get('at'):
            row_time=catalog.get('row_observed_at_utc',{}).get(pid,catalog['observed_at_utc'])
            use_latest=datetime.fromisoformat(latest['at'].replace('Z','+00:00'))>datetime.fromisoformat(row_time.replace('Z','+00:00'))
        if not live:state='NOT_FOUND_IN_CURRENT_COMPLETE_CATALOG'
        elif pid in target_ids:state=proof.get('state','PREPARED_OR_SUBMITTED')
        elif l.get('bound_source_id'):state='EXISTING_REAL_SOURCE_BINDING_RECHECK_KEEP_STYLE'
        else:state='CURRENT_SOURCE_AND_FORMAL_BINDING_REVIEW'
        rows.append({'id':pid,'model':l['model'],'family':l['model'].split('-')[0],
                     'product_identity':l['product_id'],'state':state,
                     'current_title':latest.get('title')if use_latest else live.get('subject')if live else None,
                     'current_category_id':latest.get('category_id')if use_latest else live.get('category_id')if live else None,
                     'current_audit':latest.get('status')if use_latest else live.get('status')if live else None,
                     'current_display':latest.get('display')if use_latest else live.get('display')if live else None,
                     'current_field_evidence':l.get('formal_fields',{}).get('file')if use_latest else catalog_path.relative_to(ROOT).as_posix(),
                     'bound_source_id':l.get('bound_source_id'),
                     'registry_source_state':p['source_state'],
                     'candidate_source_ids':p.get('candidate_source_ids',[]),
                     'formal_proof':formal.relative_to(ROOT).as_posix()if formal.exists()else None})
    rows.sort(key=lambda r:(0 if r['family']in ['HR030','HR042','HR054']else 1,r['model'],r['id']))
    target=BASE/'当前进度.json'
    progress=json.loads(target.read_text(encoding='utf8'))if target.exists()else{}
    progress['execution_sequence']=['HR缺货源商品全量实源替换','路崎宽头鞋继续上架']
    progress['acceptance']='官方API完整字段/EU组合/图片身份/approved状态/实际5.00及本地双改；本轮取消逐链接浏览器验收'
    progress['full_hr_scope']={'observed_at_utc':catalog['observed_at_utc'],
        'catalog_file':catalog_path.relative_to(ROOT).as_posix(),
        'catalog_sha256':hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        'current_catalog_count':len(current),'registered_hr_history':len(rows),
        'current_hr_ids_found':sum(r['id']in current for r in rows),
        'states':dict(Counter(r['state']for r in rows)),
        'caution':'本轮未检出不等于下架/删除；旧候选或MISSING不证明现行页面缺实鞋。先核正式绑定，已采用实款保留并修资料。',
        'links':rows}
    target.write_text(json.dumps(progress,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('HR_FULL_SCOPE',progress['full_hr_scope']['current_hr_ids_found'],progress['full_hr_scope']['states'])

if __name__=='__main__':main()
