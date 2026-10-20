"""Owner-approved BQ001–030 prices: exact IDs, current Schema, once-only writes."""

import sys as _registry_sys
from pathlib import Path as _RegistryPath
_registry_sys.path.insert(0, str(_RegistryPath(__file__).resolve().parents[3]/"08_工具链/06_工作区维护"))
from product_registry import ProductRegistry
from pathlib import Path
import argparse, copy, hashlib, importlib.util, json, re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from xml.etree import ElementTree as E
import schema_publish_contract as contract
from read_only_catalog import read_only_call

ROOT=Path(__file__).resolve().parents[3]
REG=ProductRegistry(ROOT)
OUT=ROOT/'02_Alibaba运营/02_单品优化记录/BQ针织鞋价格调整'
DETAILS=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'
FIELDS=('scPrice','ladderPrice','productTitle')
USD=['7.48','7.18','6.73']
def now():return datetime.now(timezone.utc).isoformat()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,v):
    if hasattr(p, 'write_registry'):
        return p.write_registry(v)
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def rel(p):return p.relative_to(ROOT).as_posix()
def stable(p):
    d=copy.deepcopy(p)
    for k in ('gmt_modified','status','display'):d.pop(k,None)
    for k in ('fob_min_price','fob_max_price'):d.get('sourcing_trade',{}).pop(k,None)
    for s in d.get('product_sku',{}).get('skus',[]):s.pop('bulk_discount_prices',None)
    for key in ('company_image','detail_image'):
        images=d.get('struct_detail',{}).get(key,{})
        if isinstance(images,dict) and isinstance(images.get('images'),list):
            images['images'].sort(key=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False))
    return d
def tiers(root):
    return sorted((int(v.find("./field[@id='quantity']/value").text),v.find("./field[@id='price']/value").text) for v in root.findall("./field[@id='ladderPrice']/complex-value/field/complex-value"))
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['prepare','submit','recover-unapplied','verify','sync']);ap.add_argument('--ids',nargs='*');a=ap.parse_args()
    if a.mode=='recover-unapplied':assert a.ids,'Recovery requires explicit reconciled IDs'
    d=load(REG);products={p['id']:p for p in d['products']}
    candidates=[l for l in d['listings'] if re.fullmatch(r'BQ\d{3}',l['product_id']) and 1<=int(l['product_id'][2:])<=30 and l['product_id'] not in ('BQ008','BQ009') and l.get('catalog_presence')=='OBSERVED']
    if a.ids:
        assert set(a.ids)<=set(l['id'] for l in candidates)
        candidates=[l for l in candidates if l['id'] in a.ids]
    if a.mode!='sync':
        spec=importlib.util.spec_from_file_location('client',ROOT/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py');api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api);cfg=api.load_config(api.DEFAULT_CONFIG)
        # Reuse the client's verified-TLS native transport, already verified in
        # the model/gallery controller. Never retry unknown write outcomes.
        transport_timeout=60 if a.mode=='recover-unapplied' else 25
        api.http_json=lambda request,timeout=transport_timeout:api.native_http_json(request,timeout=timeout)
    def read(method,params):return read_only_call(api,cfg,method,params)
    def job(l):
        pid=l['id'];f=OUT/'商品'/pid;f.mkdir(parents=True,exist_ok=True)
        if a.mode=='prepare':
            assert not (f/'write_once.json').exists(),'Existing write: verify only'
            g=read('alibaba.icbu.product.get',{'product_id':int(pid),'language':'ENGLISH'});save(f/'before_get.json',g);p=g['product']
            assert p['status']=='approved' and p['display']=='Y','Not currently approved and displayed'
            assert p['sourcing_trade']['fob_currency']=='USD' and p['sourcing_trade']['fob_unit_type']=='Pair'
            r=read('alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US'}});save(f/'before_render.json',r)
            root=E.fromstring(r['data']);payload=contract.values_only(root,operation='update',field_ids=FIELDS)
            assert set(e.get('id') for e in payload)==set(FIELDS)
            assert payload.find("./field[@id='scPrice']/value").text=='1'
            assert payload.find("./field[@id='productTitle']/value").text==p['subject']
            old=tiers(payload);assert len(old)==3 and len(set(q for q,v in old))==3
            wanted=dict(zip((q for q,v in old),USD))
            for row in payload.findall("./field[@id='ladderPrice']/complex-value/field/complex-value"):
                q=int(row.find("./field[@id='quantity']/value").text);row.find("./field[@id='price']/value").text=wanted[q]
            xml=E.tostring(payload,encoding='unicode');(f/'payload.xml').write_text(xml,encoding='utf-8')
            plan={'id':pid,'family':l['product_id'],'model':l['model'],'at':now(),'state':'PREPARED','category_id':p['category_id'],'old_tiers':old,'new_tiers':tiers(payload),'cny_targets':[50,48,45],'fx':{'usd_cny':'6.6863','date':'2026-10-16','source':'https://www.investing.com/currencies/usd-cny-historical-data','rounding':'nearest USD cent'},'fields':list(FIELDS),'title_unchanged':True,'source_fields':products[l['product_id']]['local_assets']['current_fields_file'],'video_fields_inspected':[k for k in ('imageVideo','detailVideo') if root.find('./field[@id="'+k+'"]') is not None],'payload_sha256':hashlib.sha256(xml.encode()).hexdigest()}
            save(f/'plan.json',plan);return {'id':pid,'state':'PREPARED'}
        if a.mode in ('submit','recover-unapplied'):
            recovery=a.mode=='recover-unapplied'
            if not recovery and (f/'write_once.json').exists():return {'id':pid,'state':'EXISTING_RESERVATION_READBACK_ONLY'}
            plan=load(f/'plan.json')
            xml=(f/'payload.xml').read_text(encoding='utf-8');assert hashlib.sha256(xml.encode()).hexdigest()==plan['payload_sha256']
            current=read('alibaba.icbu.product.get',{'product_id':int(pid),'language':'ENGLISH'});save(f/'immediate_prewrite_get.json',current)
            before=load(f/'before_get.json')['product'];p=current['product'];assert p['status']=='approved' and p['display']=='Y' and stable(p)==stable(before)
            assert p['sourcing_trade']==before['sourcing_trade'] and p['product_sku']==before['product_sku']
            ledger=f/'write_once.json'
            if recovery:
                # A later attempt is allowed only after a fresh formal+Schema
                # reconciliation proves the preceding timed-out write unapplied.
                next_ledger=f/'recovery_once.json'
                for candidate in (f/'recovery_once.json',f/'recovery_2_once.json'):
                    if candidate.exists():ledger=candidate
                if (f/'recovery_once.json').exists():next_ledger=f/'recovery_2_once.json'
                assert not next_ledger.exists(),'Recovery limit reached; diagnose without another write'
                old=load(ledger);v=load(f/'verification.json')
                assert old['state']=='STARTED_UNKNOWN_NO_REPLAY' and (datetime.now(timezone.utc)-datetime.fromisoformat(old['at'])).total_seconds()>60
                assert datetime.fromisoformat(v['at'])>datetime.fromisoformat(old['at']),'Fresh readback after preceding attempt required'
                assert not v['prices_match'] and v['non_price_formal_preserved'] and v['status']=='approved' and v['display']=='Y' and not v.get('schema_preservation_failures') and v.get('schema_prices_match') is False
                r=read('alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':plan['category_id'],'language':'en_US'}});save(f/'reconciled_unapplied_render.json',r)
                old_fields=contract.field_snapshot(E.fromstring(load(f/'before_render.json')['data']));actual_fields=contract.field_snapshot(E.fromstring(r['data']))
                assert set(old_fields)==set(actual_fields) and all(contract.created_field_equivalent(k,x,actual_fields[k]) for k,x in old_fields.items()),'Current Schema differs; no recovery'
                save(f/'reconciled_unapplied.json',{'at':now(),'previous_verification':rel(f/'verification.json'),'current_get':rel(f/'immediate_prewrite_get.json'),'current_render':rel(f/'reconciled_unapplied_render.json'),'conclusion':'Approved current formal and editable fields both still match the prewrite snapshot; original transport outcome reconciled as unapplied. One new scoped attempt permitted; original reservation retained.'})
                ledger=next_ledger
            with ledger.open('x',encoding='utf-8') as h:json.dump({'id':pid,'at':now(),'state':'STARTED_UNKNOWN_NO_REPLAY','sha256':plan['payload_sha256']},h)
            result=api.top_call(cfg,'alibaba.icbu.product.schema.update',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':plan['category_id'],'language':'en_US','xml':xml}});save(f/'update_receipt.json',api.redact_tokens(result))
            state='SUBMITTED_PENDING_READBACK' if result.get('biz_success') is True else 'REJECTED_OR_UNKNOWN'
            save(ledger,{'id':pid,'at':now(),'state':state,'request_id':result.get('request_id'),'sha256':plan['payload_sha256']});return {'id':pid,'state':state}
        if a.mode=='verify':
            if not (f/'write_once.json').exists():return {'id':pid,'state':'NOT_SUBMITTED'}
            plan=load(f/'plan.json');g=read('alibaba.icbu.product.get',{'product_id':int(pid),'language':'ENGLISH'});save(f/'after_get.json',g);p=g['product'];unchanged=stable(p)==stable(load(f/'before_get.json')['product'])
            expected=[(int(q),str(v)) for q,v in plan['new_tiers']];skus=p.get('product_sku',{}).get('skus',[])
            prices_ok=bool(skus) and all(sorted((int(x['start_quantity']),str(x['price'])) for x in s.get('bulk_discount_prices',[]))==expected for s in skus)
            report={'id':pid,'at':now(),'state':'PENDING_PLATFORM_VERIFY','prices_match':prices_ok,'non_price_formal_preserved':unchanged,'status':p['status'],'display':p['display'],'public':'PENDING','request_id':g.get('request_id')}
            if prices_ok and unchanged and p['status'] in ('modified','new'):report['state']='PRICE_FIELDS_PASS_REVIEW_PENDING'
            elif p['status']=='tbd':report['state']='AUDIT_REJECTED_REQUIRES_DIAGNOSIS'
            elif not unchanged:report['state']='NON_PRICE_DIFFERENCE_REQUIRES_DIAGNOSIS'
            elif p['status']=='approved' and not prices_ok:report['state']='PRICE_NOT_APPLIED'
            if p['status']=='approved':
                r=read('alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US'}});save(f/'after_render.json',r)
                if r.get('data'):
                    b=contract.field_snapshot(E.fromstring(load(f/'before_render.json')['data']));n=contract.field_snapshot(E.fromstring(r['data']))
                    checks={k:contract.created_field_equivalent(k,v,n.get(k)) for k,v in b.items() if k!='ladderPrice'}
                    report['schema_preservation_failures']=[k for k,v in checks.items() if not v];report['schema_prices_match']=tiers(E.fromstring(r['data']))==expected
                    if prices_ok and unchanged and all(checks.values()) and report['schema_prices_match'] and p['display']=='Y':report['state']='FORMAL_PRICE_PASS_PUBLIC_PENDING'
                score=read('alibaba.icbu.product.score.get',{'product_id':int(pid)});save(f/'score.json',score);report['score_evidence']=rel(f/'score.json')
                report['actual_score']=score.get('result',{}).get('final_score');report['score_source']='alibaba.icbu.product.score.get';report['score_observed_at']=now();report['target_score']='5.00';report['diagnostics']=score.get('result',{}).get('problem_map')
            save(f/'verification.json',report)
            save(DETAILS/pid/'formal_get.json',{'requested_product_id':pid,'observed_at_utc':report['at'],'method':'alibaba.icbu.product.get','response':g})
            if (f/'after_render.json').exists():save(DETAILS/pid/'formal_render.json',{'requested_product_id':pid,'observed_at_utc':report['at'],'response':load(f/'after_render.json')})
            return {'id':pid,'state':report['state']}
    if a.mode!='sync':
        def safe(l):
            try:return job(l)
            except Exception as ex:
                r={'id':l['id'],'state':'ERROR_READBACK_REQUIRED','error_type':type(ex).__name__,'detail':str(ex)[:160]}
                if getattr(ex,'transport_evidence',None):r['transport']={k:ex.transport_evidence.get(k) for k in ('phase','request_sent','curl_exit_code','http_status')}
                save(OUT/'商品'/l['id']/(a.mode+'_error.json'),r);return r
        if a.mode in ('submit','recover-unapplied'):
            results=[]
            for l in candidates:
                r=safe(l);results.append(r);print(json.dumps(r),flush=True)
        else:
            with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(safe,candidates))
        save(OUT/(a.mode+'_results.json'),{'at':now(),'results':results});print(json.dumps({'mode':a.mode,'counts':{s:sum(r['state']==s for r in results) for s in set(r['state'] for r in results)}}));return
    # Re-read registry after network work; update only this task's fields.
    d=load(REG);families={}
    for l in d['listings']:
        f=OUT/'商品'/l['id']
        if not (f/'plan.json').exists():continue
        plan=load(f/'plan.json');v=load(f/'verification.json') if (f/'verification.json').exists() else {'state':'LOCAL_DRAFT'}
        l['price_adjustment']={'state':v['state'],'at':now(),'plan':rel(f/'plan.json'),'verification':rel(f/'verification.json') if (f/'verification.json').exists() else None,'cny_targets':[50,48,45],'usd_tiers':plan['new_tiers'],'public':'PENDING'}
        if (f/'after_get.json').exists():
            actual=load(f/'after_get.json')['product']
            l['formal_fields']={'file':rel(DETAILS/l['id']/'formal_get.json'),'at':v['at'],'scope':'本次价格正式回读；公开价格待核'}
            l.setdefault('local_sync',{}).update(state=v['state'],current_fields_file=l['formal_fields']['file'],at=v['at'])
            l['observation']={'audit':actual.get('status'),'display':actual.get('display'),'at':v['at'],'scope':'本次精确ID价格正式回读；公开待核'}
            for key in ('catalog_fields','current_platform_fields'):
                if key in l:l[key].update(status=actual.get('status'),display=actual.get('display'),at=v['at'])
        families.setdefault(l['product_id'],[]).append(l['price_adjustment'])
    d['bq_knit_price_adjustment']={'at':now(),'authorization':'负责人2026-10-17确认50/48/45元每双；数量档不变；排除L1009/L1026','families':sorted(families),'entry':rel(OUT/'README.md'),'public':'PENDING'}
    adjusted=[l for l in d['listings'] if l.get('price_adjustment')]
    states={s:sum(l['price_adjustment']['state']==s for l in adjusted) for s in sorted(set(l['price_adjustment']['state'] for l in adjusted))}
    summary={'at':now(),'families':len(families),'links':len(adjusted),'states':states,'cny_targets':[50,48,45],'usd_targets':USD,'excluded_families':['BQ008 / L1009','BQ009 / L1026'],'public':'PENDING','scope':'逐ID价格/原数量门槛与非价格字段回读；审核和公开呈现分开记录'}
    save(OUT/'当前状态.json',summary)
    d['updated_on']='2026-10-17'
    work={'name':'BQ001–BQ030针织鞋价格调整','status':f'{len(families)}款、{len(adjusted)}条链接；'+json.dumps(states,ensure_ascii=False),'next_action':'按逐ID回读继续审核/公开抽检；L1009、L1026的8条链接价格保持不变。','evidence':[rel(OUT/'README.md'),rel(OUT/'当前状态.json')]}
    previous=next((x for x in d['workstreams'] if x['name']==work['name']),None)
    if previous:previous.update(work)
    else:d['workstreams'].append(work)
    for p in d['products']:
        if p['id'] not in families:continue
        p['price_adjustment']={'entry':rel(OUT/'README.md'),'states':sorted(set(x['state'] for x in families[p['id']]))}
        form=ROOT/p['local_assets']['current_fields_file'];t=form.read_text(encoding='utf-8-sig');marker='\n## 当前针织鞋价格调整（2026-10-17）\n'
        if marker in t:t=t.split(marker)[0]
        t+=marker+'\n负责人确认三档人民币目标为50 / 48 / 45元每双，原数量门槛不变。平台美元价为7.48 / 7.18 / 6.73（2026-10-16 USD/CNY 6.6863，四舍五入至美分）。正式生效以逐ID回读为准，定制内容与运费另核。\n\n当前状态：'+ '、'.join(p['price_adjustment']['states'])+'；公开价格待核。唯一执行入口：`'+rel(OUT/'README.md')+'`。\n';form.write_text(t,encoding='utf-8')
    save(REG,d)
    lines=['# BQ针织鞋价格调整','',d['bq_knit_price_adjustment']['authorization'],'',f'当前范围：{len(families)}款、{len(adjusted)}条链接。当前状态：'+json.dumps(states,ensure_ascii=False)+'。审核/公开呈现仍按逐ID证据分开记录。','', '人民币目标50 / 48 / 45元每双；当前美元提交值7.48 / 7.18 / 6.73；参考汇率USD/CNY 6.6863（2026-10-16），按美分四舍五入。L1009、L1026不写入。数量门槛、标题、SKU、图片及其他商业字段保全。','', '[当前状态](当前状态.json) · [排除款8条链接核验](排除款核验.json)；逐ID计划、写前/写后正式原件和单次提交账本保留在商品目录，原始API回执仅本地。','', '| 商品ID | 状态 | 正式证据 |','|---|---|---|']
    for l in d['listings']:
        if l.get('price_adjustment'):lines.append('| '+l['id']+' | '+l['price_adjustment']['state']+' | [证据](商品/'+l['id']+'/verification.json) |')
    (OUT/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');print('LOCAL_SYNC',len(families))
if __name__=='__main__':main()
