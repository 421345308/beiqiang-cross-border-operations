"""Bounded, verified-TLS read-only Alibaba catalog retrieval. Never retry writes."""
from pathlib import Path
import argparse, importlib.util, json, math, time
from datetime import datetime, timezone

READ_METHODS = frozenset({'alibaba.icbu.product.list', 'alibaba.icbu.product.get', 'alibaba.icbu.product.schema.get', 'alibaba.icbu.product.schema.render', 'alibaba.icbu.product.score.get', 'alibaba.icbu.photobank.list'})

def read_only_call(client, config, method, params, attempts=3, evidence=None):
    if method not in READ_METHODS:
        raise ValueError('Read-only transport rejects mutation methods before request')
    for attempt in range(1, attempts+1):
        try:
            result = client.top_call(config, method, params)
            if client.api_error(result):
                raise RuntimeError('API business error; no transport retry')
            if evidence is not None:
                evidence.append({'method': method, 'attempt': attempt, 'page': params.get('current_page'), 'status': 'response', 'request_id':result.get('request_id')})
            return result
        except client.ClientError as exc:
            t=getattr(exc,'transport_evidence',{})
            entry={'method':method,'attempt':attempt,'page':params.get('current_page'),'status':'transport_error','phase':t.get('phase'),'http_status':t.get('http_status'),'error_type':type(exc.__cause__).__name__ if exc.__cause__ else type(exc).__name__}
            # Preserve only controlled classifications, never signed URLs/headers/argv/raw bodies.
            cause=exc.__cause__;reason=getattr(cause,'reason',cause)
            entry['reason_type']=type(reason).__name__
            import ssl
            entry['certificate_error']=isinstance(reason,ssl.SSLCertVerificationError)
            if evidence is not None:evidence.append(entry)
            if entry['certificate_error'] or t.get('http_status') or attempt==attempts:
                raise
            time.sleep(min(attempt,2))

def fetch_catalog(client, config, output, attempts=3):
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    entries=[];products=[];pages_seen=set();total=None; expected_pages=None
    for page in range(1,101):
        try:
            result=read_only_call(client,config,'alibaba.icbu.product.list',{'language':'ENGLISH','current_page':page,'page_size':50},attempts,entries)
            if int(result.get('current_page',page)) != page:raise RuntimeError('Returned page disagrees with request')
            page_products=result.get('products',[])
            identity=tuple(str(x.get('id')) for x in page_products)
            if not identity or identity in pages_seen:raise RuntimeError('Empty or repeated catalog page')
            pages_seen.add(identity)
            if total is None:
                total=int(result['total_item']);size=int(result.get('page_size') or len(page_products));expected_pages=math.ceil(total/size)
            if int(result['total_item']) != total:raise RuntimeError('Catalog total changed during paging; reconcile before claiming completeness')
            products.extend(page_products)
            (output/f'page_{page}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({'page':page,'expected_pages':expected_pages,'saved_rows':len(products)},ensure_ascii=False),flush=True)
            if page>=expected_pages:break
        except Exception:
            (output/'transport_evidence.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2),encoding='utf-8')
            raise
    ids=[str(x['id']) for x in products]
    if len(products)!=total or len(set(ids))!=total:raise RuntimeError('Catalog count/unique-ID mismatch')
    snapshot={'observed_at_utc':datetime.now(timezone.utc).isoformat(),'host':'open-api.alibaba.com','method':'alibaba.icbu.product.list','total_item':total,'saved_rows':len(products),'unique_ids':len(set(ids)),'pages':expected_pages,'complete':True,'tls_verification':'Default platform TLS verification; no trust/proxy overrides','products':products}
    (output/'catalog.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'transport_evidence.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2),encoding='utf-8')
    return snapshot

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    root=Path(__file__).resolve().parents[3]
    path=root/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py'
    spec=importlib.util.spec_from_file_location('alibaba_client',path);client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)
    original_http=client.http_json
    client.http_json=lambda request:original_http(request,timeout=25)
    snap=fetch_catalog(client,client.load_config(client.DEFAULT_CONFIG),args.output)
    print(json.dumps({k:v for k,v in snap.items() if k!='products'},ensure_ascii=False))

if __name__=='__main__':main()
