"""Apply reviewed per-family copy to exact original IDs with independent readback.

Only productTitle/textDesc are submitted. Images, FAQ, SKU and trade terms
remain protected. Unknown writes are reconciled by reads, never replayed.
"""
from pathlib import Path
from datetime import datetime,timezone
from xml.etree import ElementTree as E
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import argparse,json,hashlib,importlib.util,sys,copy,traceback
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'02_Alibaba运营/02_单品优化记录/全店FAQ与产品亮点优化/内容质量复核'
RAW=ROOT/'99_临时区/商品质量全店复核/文案执行'
PLAN_FILE=BASE/'逐款文案.json'
ENTRY=BASE/'README.md'
sys.path.insert(0,str(ROOT/'08_工具链/01_业务脚本/国际站扩品'))
import publish_hot_rank_hr_a_batch as pub
import schema_publish_contract as contract
from read_only_catalog import read_only_call
PROTECTED={'1601825074604','1601943574507','1601943545775'}
def now():return datetime.now(timezone.utc).isoformat()
def load(p):return json.loads(p.read_text(encoding='utf8'))
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def rel(p):return p.relative_to(ROOT).as_posix()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def client():
    s=importlib.util.spec_from_file_location('api',ROOT/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a);a.http_json=a.native_http_json;return a,a.load_config(a.DEFAULT_CONFIG)
def protected(p):
    d=copy.deepcopy(p)
    for k in ('gmt_modified','status','display','subject','pc_detail_url'):d.pop(k,None)
    d.get('struct_detail',{}).pop('product_summary',None)
    return d
def sanitized(x):
    if isinstance(x,dict):return {k:sanitized(v)for k,v in x.items()if k not in ('owner_member','owner_member_display_name','owner_member_id')}
    if isinstance(x,list):return [sanitized(v)for v in x]
    return x
def main():
    global BASE,RAW
    sys.stdout.reconfigure(encoding='utf8');ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','submit','verify','sync']);ap.add_argument('--ids');ap.add_argument('--correction',action='store_true',help='Reviewed follow-up correction of explicit IDs; preserves the original attempt evidence.');ap.add_argument('--followup-phase',choices=['正式差异收尾']);a=ap.parse_args()
    if a.correction:
        assert a.ids,'Follow-up corrections require exact IDs'
        BASE=BASE/(a.followup_phase or '结构与标题纠正');RAW=RAW/(a.followup_phase or '结构与标题纠正')
    else:assert not a.followup_phase,'A named follow-up requires explicit correction scope'
    plan=load(PLAN_FILE);targets={pid:p for p in plan['items']if p.get('reviewed')and p.get('reviewer')=='active_agent'and not p.get('handled_by_specific_revision')for pid in p['ids']if pid not in p['exclusions']}
    ids=a.ids.split(',')if a.ids else list(targets);assert len(ids)==len(set(ids))and all(pid in targets for pid in ids)
    api,cfg=client()if a.mode!='sync'else(None,None)
    def read(m,p):return read_only_call(api,cfg,m,p)
    def get(pid):return read('alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'})
    def render(pid,p):return read('alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US'}})
    def work(pid):
        assert pid not in PROTECTED;cp=targets[pid];folder=RAW/pid;public=BASE/'商品'/pid;ledger=public/'update_once.json'
        if a.mode=='prepare':
            if ledger.exists():return {'id':pid,'state':'EXISTING_ATTEMPT_READ_ONLY'}
            got=get(pid);save(folder/'before_get.json',got);p=got['product']
            if p['status']!='approved'or p['display']!='Y':return {'id':pid,'state':'PRESERVE_CURRENT_STATE_NO_WRITE','status':p['status'],'display':p['display']}
            title=cp['title_by_id'].get(pid,p['subject']);assert cp['highlights']and len(title)<=128
            rr=render(pid,p);save(folder/'before_render.json',rr)
            if not rr.get('data'):return {'id':pid,'state':'SCHEMA_UNAVAILABLE_NO_WRITE'}
            schema=E.fromstring(rr['data']);current=folder/'current_schema.xml';current.write_text(rr['data'],encoding='utf8')
            fields=['productTitle','textDesc']+(['icbuCatProp']if cp.get('carry_current_attributes')is True else []);payload=pub.values_only(schema,operation='update',field_ids=fields)
            pub.set_direct_value(payload,'productTitle',title);pub.set_direct_value(payload,'textDesc',cp['highlights'])
            out=folder/'payload.xml';out.write_text(E.tostring(payload,encoding='unicode'),encoding='utf8')
            refs=cp['source_evidence']+[rel(PLAN_FILE)];assert all((ROOT/v).exists()for v in refs)
            manifest={'operation':'update','product_id':pid,'category_id':p['category_id'],'facts_reviewed':True,'source_evidence':refs,'current_schema':'current_schema.xml','current_schema_sha256':sha(current),'schema_request_id':rr['request_id'],'schema_acquired_at':now(),'payload_xml':'payload.xml','field_ids':fields,'dependency_ids':[]}
            save(folder/'manifest.json',manifest);listing=pub.load_submission_manifest(folder/'manifest.json','update',pid)
            save(public/'prepared.json',{'id':pid,'family':cp['family'],'at':now(),'state':'PREPARED','title':title,'highlights':cp['highlights'],'fields':fields,'source_evidence':refs,'plan_sha256':sha(PLAN_FILE),'payload_sha256':sha(out),'original_state':{'status':p['status'],'display':p['display']},'raw_evidence':rel(folder)})
            return {'id':pid,'state':'PREPARED'}
        if a.mode=='submit':
            if ledger.exists():return {'id':pid,'state':'EXISTING_ATTEMPT_READ_ONLY'}
            expected=load(public/'prepared.json');assert expected['payload_sha256']==sha(folder/'payload.xml')
            assert expected['highlights']==cp['highlights']and expected['title']==cp['title_by_id'].get(pid,load(folder/'before_get.json')['product']['subject'])
            listing=pub.load_submission_manifest(folder/'manifest.json','update',pid);got=get(pid);save(folder/'immediate_prewrite_get.json',got)
            if got['product']!=load(folder/'before_get.json')['product']:return {'id':pid,'state':'CURRENT_CHANGED_NO_WRITE'}
            with ledger.open('x',encoding='utf8')as f:json.dump({'id':pid,'at':now(),'state':'WRITE_OUTCOME_UNKNOWN_NO_REPLAY'},f)
            receipt=pub.api_submit(api,cfg,listing,False,update_product_id=pid);save(folder/'update_receipt.json',receipt)
            save(public/'update_receipt.json',sanitized(receipt));save(ledger,{'id':pid,'at':receipt['attempted_at'],'state':receipt['status'],'refs':receipt.get('refs')})
            return {'id':pid,'state':receipt['status']}
        if not ledger.exists():return {'id':pid,'state':'NO_WRITE_ATTEMPT'}
        if a.mode=='verify':
            got=get(pid);save(folder/'after_get.json',got);p=got['product'];before=load(folder/'before_get.json')['product'];expected=load(public/'prepared.json')
            checks={'title':p['subject']==expected['title'],'highlights':p.get('struct_detail',{}).get('product_summary','').replace('\u2019',"'")==expected['highlights'].replace('\u2019',"'"),'other_formal_fields':protected(p)==protected(before),'display':p['display']==before['display']if p['status']=='approved'else None}
            report={'id':pid,'at':now(),'state':'REVIEW_PENDING','status':p['status'],'display':p['display'],'checks':checks,'score':None,'public_status':'NOT_PER_ID_VISUALLY_RETESTED_API_POLICY','request_id':got.get('request_id')}
            if p['status']=='approved':
                rr=render(pid,p);save(folder/'after_render.json',rr)
                if rr.get('data'):
                    current=contract.field_snapshot(E.fromstring(rr['data']));wanted=contract.field_snapshot(E.parse(folder/'payload.xml').getroot());old=contract.field_snapshot(E.fromstring(load(folder/'before_render.json')['data']))
                    checks['schema_targets']=all(current.get(k)==v or(k=='textDesc'and json.dumps(current.get(k),ensure_ascii=False).replace('\u2019',"'")==json.dumps(v,ensure_ascii=False).replace('\u2019',"'"))for k,v in wanted.items())
                    checks['other_schema_values']=all(contract.created_field_equivalent(k,v,current.get(k))for k,v in old.items()if k not in wanted)
                else:checks['schema_targets']=False
                # Existing official score workflow uses this read-only ID lookup;
                # the generic catalog reader intentionally has a smaller allowlist.
                enc=read('alibaba.icbu.product.id.encrypt',{'product_id':pid,'language':'ENGLISH'})
                assert not api.api_error(enc),'Official score-ID lookup failed'
                if enc.get('secret_id'):
                    score=read('alibaba.icbu.product.score.get',{'product_id':enc['secret_id']});save(folder/'score.json',score);report['score']=score.get('result',{}).get('final_score')
                    diagnostics=score.get('result',{}).get('problem_map')or{};diagnostics=json.loads(diagnostics)if isinstance(diagnostics,str)else diagnostics
                    report['score_diagnostics']=diagnostics;checks['score']=report['score']is not None and Decimal(str(report['score']))>=5 and not diagnostics.get('errorReasonList')and not any((diagnostics.get('extendProblemMap')or{}).values())
                report['state']='FORMAL_FIELDS_SCORE_PASS'if checks and all(v is True for v in checks.values())else'FORMAL_DIFFERENCE_DIAGNOSE_NO_REPLAY'
            report['failed']=[k for k,v in checks.items()if v is False];save(public/'verification.json',report)
            return {'id':pid,'state':report['state'],'failed':report['failed'],'score':report['score']}
        return {'id':pid,'state':'SYNC_REQUIRED'}
    if a.mode=='sync':
        sync(ids);return
    def guarded(pid):
        try:return work(pid)
        except Exception as e:
            row={'id':pid,'state':'ERROR_NO_AUTOMATIC_WRITE_RETRY','type':type(e).__name__,'frames':[{'file':Path(x.filename).name,'line':x.lineno,'function':x.name}for x in traceback.extract_tb(e.__traceback__)]}
            if getattr(e,'api_evidence',None):row['api_evidence']=e.api_evidence
            save(RAW/pid/(a.mode+'_error.json'),row);return row
    if a.mode=='submit':
        result=[]
        for pid in ids:
            row=guarded(pid);result.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
    else:
        with ThreadPoolExecutor(max_workers=3)as pool:
            result=[]
            for row in pool.map(guarded,ids):result.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
    save(BASE/(a.mode+'_summary.json'),{'at':now(),'rows':result})
def sync(ids):
    file=ROOT/'02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json';data=load(file);listings={l['id']:l for l in data['listings']};products={p['id']:p for p in data['products']};synced=[]
    for pid in ids:
        public=BASE/'商品'/pid;v=public/'verification.json'
        if not v.exists():continue
        report=load(v);l=listings[pid];p=products[l['product_id']];state=report['state']
        priority={'结构与标题纠正':1,'正式差异收尾':2}.get(BASE.name,0)
        previous=l.get('optimization',{}).get('content_quality_revision',{})
        old_priority=previous.get('phase_priority',max([2 if '正式差异收尾/'in e else 1 if '结构与标题纠正/'in e else 0 for e in previous.get('evidence',[])]or[0]))
        if old_priority>priority or(old_priority==priority and previous.get('at','')>report['at']):continue
        phase={'at':report['at'],'state':state,'phase_priority':priority,'scope':'Original ID productTitle/textDesc only; SKU, images, generalFAQ, company and trade preserved','next_action':'Image/source colour audit continues independently. Do not replay historical copy.','evidence':[rel(public/n)for n in ('prepared.json','update_receipt.json','verification.json')if(public/n).exists()]}
        l.setdefault('optimization',{})['content_quality_revision']=phase;p['content_quality_revision']={'state':state,'at':report['at'],'evidence':phase['evidence']}
        for obj in (l,p):
            obj.setdefault('evidence',[])
            for e in phase['evidence']:
                if e not in obj['evidence']:obj['evidence'].append(e)
        if state=='FORMAL_FIELDS_SCORE_PASS':
            folder=RAW/pid;got=load(folder/'after_get.json');actual=got['product'];canonical=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'/pid
            save(canonical/'formal_get.json',{'requested_product_id':pid,'observed_at_utc':report['at'],'method':'alibaba.icbu.product.get','response':sanitized(got),'sanitized_fields':['owner_member','owner_member_display_name','owner_member_id'],'raw_response_file':rel(folder/'after_get.json')})
            save(canonical/'formal_render.json',sanitized(load(folder/'after_render.json')))
            l['formal_fields']={'file':rel(canonical/'formal_get.json'),'at':report['at'],'scope':phase['scope']};l.setdefault('current_platform_fields',{}).update(at=report['at'],title=actual['subject'],highlights=actual['struct_detail']['product_summary'],status=actual['status'],display=actual['display'],category_id=actual['category_id'])
            l.setdefault('catalog_fields',{}).update(l['current_platform_fields']);l.setdefault('observation',{}).update(at=report['at'],audit=actual['status'],display=actual['display'],score=report['score'])
            l.setdefault('local_sync',{}).update(state=state,observed_at=report['at'],current_fields_file=rel(canonical/'formal_get.json'),content_verification=rel(v));synced.append(pid)
    reviewed=load(PLAN_FILE)
    for cp in reviewed['items']:
        family_ids=[pid for pid in cp['ids']if pid not in cp['exclusions']]
        if cp.get('handled_by_specific_revision')or not family_ids:continue
        p=products[cp['family']];phases={pid:listings[pid].get('optimization',{}).get('content_quality_revision',{})for pid in family_ids}
        if not any(phases.values()):continue
        passed=[pid for pid,v in phases.items()if v.get('state')=='FORMAL_FIELDS_SCORE_PASS'];p['content_quality_revision']={'at':max(v.get('at','')for v in phases.values()),'state':'FORMAL_FIELDS_SCORE_PASS'if len(passed)==len(family_ids)else'PARTIAL_COPY_VERIFICATION','verified_ids':passed,'pending_ids':[pid for pid in family_ids if pid not in passed],'evidence':list(dict.fromkeys(e for v in phases.values()for e in v.get('evidence',[])))};p.setdefault('local_assets',{})['current_buyer_copy']=rel(PLAN_FILE);p['next_action']='本轮标题与功能亮点已正式核验 %s/%s 条；余项按当前核验处理，图像和来源色码单列继续，不重放旧文案。'%(len(passed),len(family_ids))
    data['updated_on']=datetime.now().date().isoformat();data['content_quality_revision']={'at':now(),'entry':rel(ENTRY),'verified_ids':sorted(l['id']for l in data['listings']if l.get('optimization',{}).get('content_quality_revision',{}).get('state')=='FORMAL_FIELDS_SCORE_PASS'),'scope':'Exact formal content revision; image inspection and colour expansion tracked separately.'};save(file,data)
    sys.path.insert(0,str(ROOT/'08_工具链/06_工作区维护'));import build_product_workspace as workspace
    errors=workspace.validate(data,ROOT);assert not errors,errors
    for path,body in workspace.build(data).items():workspace.write_generated(ROOT/path,body)
    print('LOCAL_SOURCE_AND_DOSSIER_SYNC',len(synced),flush=True)
if __name__=='__main__':main()
