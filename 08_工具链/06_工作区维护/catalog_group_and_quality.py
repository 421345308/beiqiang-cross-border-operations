"""Read actual group definitions and quality scores into the current catalog evidence."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import importlib.util
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[2]
AREA=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录'
REGISTRY=ROOT/'02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json'

def main():
    spec=importlib.util.spec_from_file_location('api',ROOT/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py')
    api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)
    cfg=api.load_config(api.DEFAULT_CONFIG)
    data=json.loads(REGISTRY.read_text(encoding='utf-8-sig'))
    groups=set()
    actual={}
    for file in (AREA/'商品').glob('*/formal_get.json'):
        p=json.loads(file.read_text(encoding='utf-8'))['response'].get('product',{})
        actual[file.parent.name]=p
        if p.get('group_id'):groups.add(str(p['group_id']))
    jobs=[('group',gid) for gid in sorted(groups)]+[('score',pid) for pid in data['bq_ease_optimization']['targets']]
    def job(task):
        kind,key=task
        method='alibaba.icbu.product.group.get' if kind=='group' else 'alibaba.icbu.product.score.get'
        params={'group_id':int(key)} if kind=='group' else {'product_id':int(key)}
        response=api.top_call(cfg,method,params)
        folder=AREA/'店内分组' if kind=='group' else AREA/'商品'/key/'穿脱优化'
        folder.mkdir(parents=True,exist_ok=True)
        path=folder/(key+'.json' if kind=='group' else '当前质量评分.json')
        path.write_text(json.dumps({'observed_at_utc':datetime.now(timezone.utc).isoformat(),'method':method,'response':api.redact_tokens(response)},ensure_ascii=False,indent=2),encoding='utf-8')
        return {'kind':kind,'id':key,'file':path.relative_to(ROOT).as_posix(),'response':response}
    result=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(job,task) for task in jobs]):
            try:result.append(future.result())
            except Exception as exc:print(json.dumps({'error':type(exc).__name__}),flush=True)
    # Preserve concurrent registry edits.
    data=json.loads(REGISTRY.read_text(encoding='utf-8-sig'))
    for listing in data['listings']:
        p=actual.get(listing['id'])
        if not p:continue
        gid=str(p.get('group_id') or '')
        listing['platform_group']={'id':gid,'evidence':(AREA/'店内分组'/(gid+'.json')).relative_to(ROOT).as_posix() if gid else None,'scope':'正式商品接口返回店内分组；不等于采购意图分类'}
    data['catalog_reconciliation']['platform_group_definitions_saved']=sum(r['kind']=='group' and not r['response'].get('error_response') for r in result)
    REGISTRY.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{'kind':r['kind'],'id':r['id'],'response_keys':list(r['response'])} for r in result],ensure_ascii=False))

if __name__=='__main__':main()
