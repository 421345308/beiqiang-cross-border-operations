"""Prepare exact-target incremental BQ changes; serial writes, independent readback.

Only prepared title/main-gallery fields may be submitted. A durable per-ID
write reservation prevents blind retries after unknown outcomes.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
REGISTRY=ROOT/'02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json'
DETAILS=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'


def save(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')


def now():
    return datetime.now(timezone.utc).isoformat()


def invariant(p):
    # Preserve all business/identity/content fields beyond explicitly edited gallery/title.
    keys=['keywords','category_id','attributes','product_sku','sourcing_trade','price_type','struct_detail','product_type','sub_market_type','rts']
    out=deepcopy({key:p.get(key) for key in keys})
    # Alibaba may return company roles in a different array order; compare the
    # exact role/image pairs while still detecting any actual content change.
    company=(out.get('struct_detail') or {}).get('company_image') or {}
    if isinstance(company.get('images'),list):
        company['images'].sort(key=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False))
    return out


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['prepare','submit','verify'])
    parser.add_argument('--ids',nargs='*')
    args=parser.parse_args()
    data=json.loads(REGISTRY.read_text(encoding='utf-8-sig'))
    ids=args.ids or data['bq_ease_optimization']['targets']
    # Select only registry-authorized exact target IDs; source links are absent.
    if set(ids)-set(data['bq_ease_optimization']['targets']):
        raise ValueError('ID not in evidence-scoped target set')
    spec=importlib.util.spec_from_file_location('api',ROOT/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py')
    api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)
    cfg=api.load_config(api.DEFAULT_CONFIG)
    original=api.http_json;api.http_json=lambda request:original(request,timeout=25)
    def call(method,params):
        return api.top_call(cfg,method,params)
    def job(pid):
        folder=DETAILS/pid/'穿脱优化'
        request=json.loads((folder/'拟改字段.json').read_text(encoding='utf-8'))
        if args.mode=='prepare':
            got=call('alibaba.icbu.product.get',{'product_id':int(pid),'language':'ENGLISH'})
            save(folder/'写前正式商品.json',got)
            p=got.get('product',{})
            if p.get('status')!='approved' or p.get('display')!='Y' or p.get('subject')!=request['before_title']:
                return {'id':pid,'state':'BEFORE_STATE_CHANGED_REVIEW_REQUIRED'}
            response=call('alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US'}})
            save(folder/'当前Schema回执.json',response)
            if not response.get('data'):
                return {'id':pid,'state':'SCHEMA_UNAVAILABLE'}
            root=ET.fromstring(response['data'])
            title_field=root.find("./field[@id='productTitle']")
            if title_field is None or title_field.get('type')!='input':
                return {'id':pid,'state':'TITLE_FIELD_UNVERIFIED'}
            video_fields={field.get('id'):ET.tostring(field,encoding='unicode') for field in root.findall('./field') if field.get('id') in {'imageVideo','detailVideo'}}
            save(folder/'当前视频字段.json',video_fields)
            if len(request['title'])>128 or 'Hands Free' in request['title']:
                raise ValueError('Unsupported title')
            payload=ET.Element('itemSchema')
            field=ET.SubElement(payload,'field',{'id':'productTitle','name':title_field.get('name','Product name'),'type':'input'})
            ET.SubElement(field,'value').text=request['title']
            order=request.get('image_order')
            if order is not None:
                gallery=root.find("./field[@id='scImages']")
                if gallery is None:
                    return {'id':pid,'state':'GALLERY_FIELD_UNVERIFIED'}
                original_gallery=deepcopy(gallery)
                nodes=gallery.find('complex-value')
                if nodes is None:
                    return {'id':pid,'state':'GALLERY_SHAPE_UNVERIFIED'}
                images=sorted(list(nodes),key=lambda x:int(x.get('id').rsplit('_',1)[1]))
                if sorted(order)!=list(range(len(images))) or len(images)!=6:
                    raise ValueError('Gallery order must preserve all six images')
                for node in list(nodes):nodes.remove(node)
                for slot,index in enumerate(order):
                    images[index].set('id',f'scImages_{slot}')
                    nodes.append(images[index])
                payload.append(gallery)
                save(folder/'图库变更.json',{'before':ET.tostring(original_gallery,encoding='unicode'),'after':ET.tostring(gallery,encoding='unicode'),'order':order})
            xml=ET.tostring(payload,encoding='unicode')
            (folder/'增量载荷.xml').write_text(xml,encoding='utf-8')
            return {'id':pid,'state':'PAYLOAD_READY','video_fields_inspected':list(video_fields),'fields':[field.get('id') for field in payload]}
        if args.mode=='submit':
            reservation=folder/'单次提交账本.json'
            if reservation.exists():return {'id':pid,'state':'EXISTING_RESERVATION_READBACK_ONLY'}
            file=folder/'增量载荷.xml'
            if not file.exists():return {'id':pid,'state':'NO_VALIDATED_PAYLOAD'}
            # Recheck the exact write-before title and status. No blind retry on changed data.
            live=call('alibaba.icbu.product.get',{'product_id':int(pid),'language':'ENGLISH'})
            p=live.get('product',{})
            before=json.loads((folder/'写前正式商品.json').read_text(encoding='utf-8')).get('product',{})
            if p.get('subject')!=request['before_title'] or p.get('status')!='approved' or invariant(p)!=invariant(before):
                return {'id':pid,'state':'CURRENT_FIELDS_CHANGED_REVIEW_REQUIRED'}
            save(reservation,{'product_id':pid,'reserved_at':now(),'payload_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'state':'RESERVED_WRITE_OUTCOME_PENDING'})
            response=call('alibaba.icbu.product.schema.update',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US','xml':file.read_text(encoding='utf-8')}})
            save(folder/'更新回执.json',api.redact_tokens(response))
            state='SUBMITTED_PENDING_READBACK' if response.get('biz_success') is True else 'API_REJECTED_OR_NO_BUSINESS_SUCCESS'
            save(reservation,{'product_id':pid,'submitted_at':now(),'payload_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'state':state,'request_id':response.get('request_id')})
            return {'id':pid,'state':state,'request_id':response.get('request_id')}
        response=call('alibaba.icbu.product.get',{'product_id':int(pid),'language':'ENGLISH'})
        save(folder/'写后正式商品.json',response)
        actual=response.get('product',{})
        before=json.loads((folder/'写前正式商品.json').read_text(encoding='utf-8')).get('product',{}) if (folder/'写前正式商品.json').exists() else {}
        unchanged=invariant(actual)==invariant(before)
        title_matches=actual.get('subject')==request['title']
        state='FORMAL_VERIFIED_PUBLIC_PENDING' if title_matches and unchanged and actual.get('status')=='approved' and actual.get('display')=='Y' else 'PENDING_APPROVAL' if actual.get('status')=='modified' else 'FORMAL_DIFFERENCE_REVIEW_REQUIRED'
        result={'id':pid,'state':state,'at':now(),'title_matches':title_matches,'related_fields_unchanged':unchanged,'status':actual.get('status'),'display':actual.get('display'),'public_qa':'PENDING','request_id':response.get('request_id')}
        save(folder/'字段验收.json',result)
        # The current archive always reflects the actual returned fields, even
        # when review changed the requested title. The draft stays separate.
        if actual:
            save(DETAILS/pid/'formal_get.json',{'requested_product_id':pid,'observed_at_utc':result['at'],'method':'alibaba.icbu.product.get','response':api.redact_tokens(response)})
        return result
    results=[]
    if args.mode=='submit':
        for pid in ids:
            try:result=job(pid)
            except Exception as exc:result={'id':pid,'state':'UNKNOWN_OR_ERROR_READBACK_ONLY','error_type':type(exc).__name__}
            results.append(result)
            print(json.dumps(result,ensure_ascii=False),flush=True)
    else:
        with ThreadPoolExecutor(max_workers=4) as pool:
            for future in as_completed({pool.submit(job,pid):pid for pid in ids}):
                try:results.append(future.result())
                except Exception as exc:results.append({'state':'READ_ERROR','error_type':type(exc).__name__})
        print(json.dumps({'mode':args.mode,'results':results},ensure_ascii=False),flush=True)
    # Re-read the registry to preserve updates from other tasks during network requests.
    current=json.loads(REGISTRY.read_text(encoding='utf-8-sig'))
    by_id={listing['id']:listing for listing in current['listings']}
    for result in results:
        pid=result.get('id')
        if pid not in by_id:continue
        folder=DETAILS/pid/'穿脱优化'
        state=result['state']
        evidence=[(folder/name).relative_to(ROOT).as_posix() for name in ['拟改字段.json','当前Schema回执.json','更新回执.json','字段验收.json'] if (folder/name).exists()]
        gallery=by_id[pid].get('optimization',{}).get('gallery')
        by_id[pid]['optimization']={'state':state,'scope':'标题及明确登记的图库顺序；未完成公开验收不报整款完成','next_action':'核公开标题/图库呈现及本次实际评分；正式标题差异先查原因，不重复同稿提交；其余未改字段保持原样','evidence':evidence}
        if gallery:by_id[pid]['optimization']['gallery']=gallery
    current['bq_ease_optimization']['state']=args.mode.upper()+'_RESULTS_RECORDED'
    save(REGISTRY,current)


if __name__=='__main__':
    main()
