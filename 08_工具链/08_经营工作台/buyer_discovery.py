"""Bounded read-only bridge to the existing buyer discovery tool."""
import json
from pathlib import Path
import subprocess
import sys
SOURCE=Path(__file__).resolve().parents[1]/'01_业务脚本/客户发现助手/discover.py'

def search_buyers(keyword='footwear',limit=10,timeout_seconds=45):
    if not isinstance(keyword,str) or not keyword.strip() or len(keyword)>120:raise ValueError('请输入120字以内的关键词')
    if type(limit) is not int or not 1<=limit<=30:raise ValueError('每次查看1至30个候选')
    try:
        proc=subprocess.run([sys.executable,'-X','utf8',str(Path(__file__).resolve()),'--worker',keyword,str(limit)],capture_output=True,text=True,encoding='utf-8',timeout=max(1,min(60,timeout_seconds)))
    except subprocess.TimeoutExpired:return {'status':'timeout','records':[],'error':'买家搜索超时'}
    if proc.returncode:return {'status':'failed','records':[],'error':'现有买家发现数据源暂不可用'}
    try:return json.loads(proc.stdout)
    except ValueError:return {'status':'failed','records':[],'error':'数据源返回格式无效'}

def _worker(keyword,limit):
    import importlib.util
    spec=importlib.util.spec_from_file_location('existing_discovery',SOURCE)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    progress=[]
    records=module.discover([keyword],pages=1,limit=limit,enrich=False,pause=0,progress=progress.append)
    errors=[line for line in progress if '暂停：' in line]
    return {'status':'partial' if errors and records else 'failed' if errors else 'success','records':records,'errors':errors,'keyword':keyword,'source':'ImportYeti 美国海运进口记录','current_demand_confirmed':False,'notice':'进口行为仅作为候选线索，官网及采购需求须研究；不自动加入CRM。'}

if __name__=='__main__':print(json.dumps(_worker(sys.argv[2],int(sys.argv[3])),ensure_ascii=False))
