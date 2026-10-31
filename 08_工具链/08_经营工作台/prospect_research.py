"""Bounded public-company research using the existing discovery Crawler.

No login, messages, CRM writes, or model invocation. A short-lived worker gives
the existing network transport a real wall-clock bound including DNS/robots.
"""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

LABELS={'footwear':'鞋类经营','casual':'休闲舒适鞋表述','distribution':'批发或分销表述',
        'private_label':'自有品牌表述','retail':'零售表述','manufacturing':'制造或寻源角色待核',
        'specialist':'专业性能品类待核','supplier_intake':'公开供应商申请入口',
        'active_demand':'公开寻源表述（时效待核）','origin_constraint':'供应链产地范围限制'}


def _now():return datetime.now(timezone.utc).isoformat()


def _core():
    path=Path(__file__).resolve().parents[1]/'01_业务脚本/客户发现助手/core.py'
    spec=importlib.util.spec_from_file_location('prospect_existing_crawler',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def _seed(obj,core):
    if not isinstance(obj,dict) or obj.get('kind')!='prospect':raise ValueError('请选择当前主动开发候选对象')
    try:body=json.loads(obj.get('content') or '{}')
    except (ValueError,TypeError):body={}
    website=obj.get('website') or body.get('website')
    if not website:
        website=next((r.get('url') for r in obj.get('links',[]) if isinstance(r,dict) and r.get('label')=='企业官网'),None)
    if not isinstance(website,str) or not website.strip():raise ValueError('当前候选未记录企业官网，请先核实官网')
    website=core.normalize_url(website)
    if core.blocked_platform(website):raise ValueError('请使用公司官网，不使用社媒或搜索平台')
    urls=[]
    for ref in list(obj.get('evidence')or[])+list(body.get('evidence')or[]):
        value=ref.get('url') if isinstance(ref,dict) else ref
        if not isinstance(value,str):continue
        try:url=core.normalize_url(value)
        except ValueError:continue
        if core.host_key(url)==core.host_key(website) and url!=website and url not in urls:urls.append(url)
    return {'website':website,'pages':urls[:2]}


def _scan(seed,*,core=None,crawler=None):
    core=core or _core();captured={}
    if crawler is None:
        delegate=core.PublicTransport()
        class Capture:
            def get(self,url,**kwargs):
                result=delegate.get(url,**kwargs)
                if result.get('status')==200 and 'html' in result.get('headers',{}).get('content-type','').lower():
                    captured[result['url']]=result['body']
                return result
        crawler=core.Crawler(transport=Capture())
    raw=crawler.scan(seed,max_pages=3)
    pages=[]
    for attempt in raw.get('pages',[])[:3]:
        success=bool(attempt.get('text_sha256')) and attempt.get('http_status')==200 and not attempt.get('error')
        url=attempt.get('final_url')or attempt.get('url')
        text=core.parse_page(captured[url],url).text if success and url in captured else ''
        pages.append({'url':attempt.get('url'),'final_url':url,'fetch_success':success,
                      'http_status':attempt.get('http_status'),'title':attempt.get('title'),
                      'excerpt':text[:1000] if success else '',
                      'checked_at':attempt.get('checked_at'),'error':attempt.get('error'),
                      'warning':attempt.get('warning')})
    successful={p['final_url'] for p in pages if p['fetch_success']}
    analysis=raw.get('analysis')or{};labels=[]
    for key,evidence in (analysis.get('signals')or{}).items():
        url=evidence.get('url')or evidence.get('source_url')
        if url not in successful:continue
        labels.append({'key':key,'label':LABELS.get(key,key),'excerpt':evidence.get('quote')or evidence.get('excerpt')or evidence.get('text')or '',
                       'url':url,'observed_at':raw.get('checked_at')})
    count=len(successful)
    status='success' if count and all(p['fetch_success'] for p in pages) else 'partial' if count else 'failed'
    return {'website':seed['website'],'status':status,'fetched_at':raw.get('checked_at')or _now(),
            'pages':pages,'labels':labels,'risks':analysis.get('risks',[]) if count else [],
            'limitations':['仅最多3个官网公开页面，不代表全站已研究。','规则标签依据公开原文，不证明买家身份、当前采购意向或贝强逐款供货能力。'],
            'current_demand_confirmed':False}


def research_company(prospect_object,timeout_seconds=40):
    if type(timeout_seconds) not in (int,float) or not 1<=timeout_seconds<=60:raise ValueError('研究时限应为1至60秒')
    seed=_seed(prospect_object,_core())
    flags={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
    process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker'],stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf8',**flags)
    try:
        stdout,_=process.communicate(json.dumps(seed,ensure_ascii=False),timeout=timeout_seconds)
        if process.returncode!=0:raise ValueError('抓取进程未正常返回')
        result=json.loads(stdout)
        result['object_id']=prospect_object['id']
        return result
    except subprocess.TimeoutExpired:
        process.kill();process.communicate()
        return {'object_id':prospect_object['id'],'website':seed['website'],'status':'timeout','fetched_at':_now(),
                'pages':[],'labels':[],'risks':[],'current_demand_confirmed':False,
                'limitations':['已达到本次网络研究总时限，抓取进程已停止；没有可验收的页面结果，不视为已研究。']}
    except (ValueError,TypeError):
        return {'object_id':prospect_object['id'],'website':seed['website'],'status':'failed','fetched_at':_now(),
                'pages':[],'labels':[],'risks':[],'current_demand_confirmed':False,
                'limitations':['抓取未成功返回有效结果，不视为已研究；可稍后重试或人工核对官网。']}


if __name__=='__main__':
    for stream in (sys.stdin,sys.stdout):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf8')
    if sys.argv[1:]==['--worker']:
        print(json.dumps(_scan(json.load(sys.stdin)),ensure_ascii=False))
