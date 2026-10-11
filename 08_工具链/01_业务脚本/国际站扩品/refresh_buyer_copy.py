"""Exact-ID buyer-copy refresh: read-only collection, minimal update, independent verification.

Business copy must be independently reviewed in copy.json; this tool does not invent it.
Writes are serial and never automatically replayed, including unknown outcomes.
"""
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from xml.etree import ElementTree as E
import argparse, importlib.util, json, hashlib, sys

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT/'02_Alibaba运营/02_单品优化记录/全店FAQ与产品亮点优化'
FIELDS = ['textDesc', 'companyFaqDesc']
def now(): return datetime.now(timezone.utc).isoformat()
def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path): return json.loads(path.read_text(encoding='utf8'))
def api_client():
    spec=importlib.util.spec_from_file_location('alibaba_client', ROOT/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py')
    api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)
    original=api.http_json
    api.http_json=lambda request,timeout=30:original(request,timeout=timeout)
    return api,api.load_config(api.DEFAULT_CONFIG)
def model(product):
    return next((a.get('value_name') for a in product.get('attributes',[]) if str(a.get('attribute_id'))=='3'),None)
def formal_copy(product):
    detail=product.get('struct_detail') or {}
    faq=detail.get('product_faq')
    return {'highlights':detail.get('product_summary'),'faq':None if faq is None else [{'question':f.get('question'),'answers':f.get('answer')} for f in faq]}
def protected(product):
    # Preserve every unsubmitted key, including nested galleries and company copy.
    result=json.loads(json.dumps(product))
    for key in ('gmt_modified','status','display'):result.pop(key,None)
    detail=result.get('struct_detail')
    if isinstance(detail,dict):
        for key in ('product_summary','product_faq'):detail.pop(key,None)
    return result
def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['collect','prepare','submit','verify']);ap.add_argument('--ids');ap.add_argument('--workers',type=int,default=4);args=ap.parse_args()
    sys.stdout.reconfigure(encoding='utf8')
    ids=args.ids.split(',') if args.ids else [str(x['id']) for x in load(BASE/'当前目录/catalog.json')['products']]
    assert len(ids)==len(set(ids)) and all(x.isdigit() for x in ids)
    sys.path.insert(0,str(Path(__file__).parent))
    import publish_hot_rank_hr_a_batch as pub
    from read_only_catalog import read_only_call
    api,cfg=api_client()
    def work(pid):
        folder=BASE/'商品'/pid;folder.mkdir(parents=True,exist_ok=True)
        ledger=folder/'update_once.json'
        def read(method,params):return read_only_call(api,cfg,method,params)
        def get():return read('alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'})
        def render(p):return read('alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US'}})
        if args.mode=='collect':
            # Collect is explicitly read-only and cannot erase write baselines.
            got=get();save(folder/'current_get.json',got);p=got['product']
            return {'product_id':pid,'model':model(p),'status':p.get('status'),'display':p.get('display'),'detail_type':p.get('product_desc_type'),'collected_at':now(),'request_id':got.get('request_id')}
        if args.mode=='prepare':
            if ledger.exists():return {'product_id':pid,'status':'EXISTING_LEDGER_READBACK_ONLY'}
            cp=load(folder/'copy.json')
            assert cp.get('reviewed') is True and cp.get('source_evidence') and cp['product_id']==pid
            assert cp.get('reviewer')=='active_agent' and cp.get('claim_review')
            got=get();save(folder/'before_get.json',got);p=got['product'];assert model(p)==cp['model']
            if p.get('status')!='approved':return {'product_id':pid,'status':'WAIT_CURRENT_REVIEW'}
            if p.get('display')!='Y':return {'product_id':pid,'status':'OFFLINE_COPY_ONLY_PRESERVE_DISPLAY_NO_PUBLISH'}
            response=render(p);save(folder/'before_render.json',response)
            if not response.get('data'):return {'product_id':pid,'status':'WAIT_EDITABLE_SCHEMA'}
            current=folder/'current_schema.xml';current.write_text(response['data'],encoding='utf8');schema=E.fromstring(response['data'])
            deps=['productDescType'] if schema.find("./field[@id='productDescType']") is not None else []
            root=pub.values_only(schema,operation='update',field_ids=FIELDS)
            highlight=root.find("./field[@id='textDesc']");assert highlight is not None
            for child in list(highlight):highlight.remove(child)
            E.SubElement(highlight,'value').text=cp['highlights']
            faq=root.find("./field[@id='companyFaqDesc']");definition=schema.find("./field[@id='companyFaqDesc']");assert faq is not None and definition is not None
            for child in list(faq):faq.remove(child)
            defs={f.get('id'):f for f in definition.findall('./fields/field')}
            for pair in cp['faq']:
                item=E.SubElement(faq,'complex-values')
                for key in ('question','answers'):
                    attrs={'id':key}
                    if defs[key].get('type'):attrs['type']=defs[key].get('type')
                    E.SubElement(E.SubElement(item,'field',attrs),'value').text=pair[key]
            payload=folder/'payload.xml';payload.write_text(E.tostring(root,encoding='unicode'),encoding='utf8')
            manifest={'operation':'update','product_id':pid,'category_id':p['category_id'],'facts_reviewed':True,'source_evidence':['copy.json','before_get.json']+cp['source_evidence'],'current_schema':current.name,'current_schema_sha256':sha(current),'schema_request_id':response['request_id'],'schema_acquired_at':now(),'payload_xml':payload.name,'field_ids':FIELDS,'dependency_ids':deps,'observed_model':cp['model']}
            path=folder/'manifest.json';save(path,manifest);listing=pub.load_submission_manifest(path,'update',pid);save(folder/'prepared.json',listing)
            save(folder/'reviewed_baseline.json',{'prepared_at':now(),'copy_sha256':sha(folder/'copy.json'),'before_get_sha256':sha(folder/'before_get.json'),'protected':protected(p),'scope':FIELDS,'dependency_ids':deps,'unchanged_dependency_values':pub.field_snapshot(schema).get('productDescType')})
            return {'product_id':pid,'status':'PREPARED','faq_count':len(cp['faq'])}
        if args.mode=='submit':
            if ledger.exists():return {'product_id':pid,'status':'EXISTING_LEDGER_READBACK_ONLY'}
            baseline=load(folder/'reviewed_baseline.json');assert baseline['copy_sha256']==sha(folder/'copy.json')
            listing=pub.load_submission_manifest(folder/'manifest.json','update',pid)
            got=get();save(folder/'immediate_prewrite_get.json',got)
            before=load(folder/'before_get.json')['product'];current=got['product']
            if current!=before:return {'product_id':pid,'status':'CURRENT_CHANGED_REPREPARE_NO_WRITE'}
            with ledger.open('x',encoding='utf8') as f:json.dump({'product_id':pid,'status':'STARTED_OUTCOME_UNKNOWN','started_at':now()},f)
            result=pub.api_submit(api,cfg,listing,False,update_product_id=pid);save(folder/'update_receipt.json',result);save(ledger,{'product_id':pid,'status':result['status'],'attempted_at':result['attempted_at'],'refs':result.get('refs')})
            return {'product_id':pid,'status':result['status']}
        if not ledger.exists():return {'product_id':pid,'status':'NO_WRITE_LEDGER'}
        got=get();save(folder/'after_get.json',got);p=got['product'];before=load(folder/'before_get.json')['product'];cp=load(folder/'copy.json')
        actual=formal_copy(p);expected={'highlights':cp['highlights'],'faq':cp['faq']}
        preserve=protected(p)==protected(before)
        report={'product_id':pid,'observed_at':now(),'request_id':got.get('request_id'),'product_status':p.get('status'),'display':p.get('display'),'display_preserved_after_review':p.get('display')==before.get('display') if p.get('status')=='approved' else None,'formal_highlights_match':actual['highlights']==expected['highlights'],'formal_faq_match':actual['faq']==expected['faq'],'unsubmitted_fields_preserved':preserve,'public_status':'PENDING_APPLICABLE_TEXT_VERIFICATION'}
        report['status']='FORMAL_PASS' if p.get('status')=='approved' and all(report[k] for k in ('formal_highlights_match','formal_faq_match','unsubmitted_fields_preserved','display_preserved_after_review')) else 'PENDING_REVIEW' if p.get('status')!='approved' else 'MISMATCH_DIAGNOSE_NO_REPLAY'
        if report['status']=='FORMAL_PASS':
            response=render(p);save(folder/'after_render.json',response)
            if response.get('data'):
                (folder/'after_schema.xml').write_text(response['data'],encoding='utf8')
                fields=pub.field_snapshot(E.fromstring(response['data']));listing=load(folder/'prepared.json')
                report['schema_target_fields_match']=all(fields.get(k)==v for k,v in listing['expected_fields'].items())
                if not report['schema_target_fields_match']:report['status']='SCHEMA_MISMATCH_DIAGNOSE'
            else:report['status']='PENDING_EDITABLE_SCHEMA'
        public_evidence=folder/'public_text_verification.json'
        if public_evidence.exists():
            observed=load(public_evidence)
            if observed.get('copy_sha256')==sha(folder/'copy.json') and observed.get('status')=='PUBLIC_TRANSLATED_TEXT_SEMANTIC_PASS':
                report['public_status']=observed['status']
                report['public_evidence']=public_evidence.name
        save(folder/'verification.json',report);return report
    rows=[]
    def collect(pid):
        try:return work(pid)
        except Exception as exc:
            # Error details stay controlled; no raw signed request or credentials.
            result={'product_id':pid,'status':'ERROR_OBJECT_EVIDENCE','exception_type':type(exc).__name__,'observed_at':now()}
            save(BASE/'商品'/pid/(args.mode+'_error.json'),result)
            return result
    if args.mode=='submit':
        for pid in ids:
            row=collect(pid);rows.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
    else:
        with ThreadPoolExecutor(max_workers=max(1,min(args.workers,4))) as ex:
            for f in as_completed([ex.submit(collect,pid) for pid in ids]):
                row=f.result();rows.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
    summary_name=args.mode+'_summary.json' if not args.ids else args.mode+'_subset_'+hashlib.sha256(','.join(ids).encode()).hexdigest()[:10]+'.json'
    save(BASE/summary_name,{'observed_at':now(),'scope_count':len(ids),'rows':rows})
    if any(row['status']=='ERROR_OBJECT_EVIDENCE' for row in rows):sys.exit(1)
if __name__=='__main__':main()
