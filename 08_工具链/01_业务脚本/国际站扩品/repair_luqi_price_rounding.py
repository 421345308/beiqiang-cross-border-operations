"""Exact-source cent rounding repair; once-only price update, full readback.

Preserves original creation manifests and receipts. A positive price-only
receipt permits a narrowly scoped current ladderPrice expectation overlay.
"""
from pathlib import Path
from decimal import Decimal,ROUND_CEILING
from xml.etree import ElementTree as E
import argparse,copy,importlib.util,json
import publish_reviewed_luqi as p
STYLES=('2418','868','822','2579','2575','2505','931','02412','0922')
FIELDS=('scPrice','ladderPrice','productTitle')

def stable(product):
    d=copy.deepcopy(product)
    for k in ('gmt_modified','status','display'):d.pop(k,None)
    for k in ('fob_min_price','fob_max_price'):d.get('sourcing_trade',{}).pop(k,None)
    for row in d.get('product_sku',{}).get('skus',[]):row.pop('bulk_discount_prices',None)
    # product.get may reorder whole company-image records across image sets.
    # Keep every role/CDN/metadata value and multiplicity; only normalize the
    # observed array order. Current Schema equivalence is checked separately.
    company=d.get('struct_detail',{}).get('company_image',{})
    if isinstance(company.get('images'),list):company['images']=sorted(company['images'],key=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False))
    return d

def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=('prepare','submit','verify','finalize-saved'));ap.add_argument('--style',required=True,choices=STYLES);a=ap.parse_args();p.configure(a.style)
    F=p.FOLDER;D=F/'价格取整修正';D.mkdir(exist_ok=True);pid=p.pub.extract_product_id(p.load(F/'create_receipt.json')['response']);assert pid
    spec=importlib.util.spec_from_file_location('api',p.ROOT/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py');client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client);cfg=client.load_config(client.DEFAULT_CONFIG)
    original=client.http_json;client.http_json=lambda request,timeout=25:original(request,timeout=timeout)
    ledger=D/'update_once.json'
    if a.mode=='submit':
        assert not ledger.exists(),'Existing price write: verify only; never replay'
        listing=p.pub.load_submission_manifest(D/'manifest.json','update',pid)
        got=p.read_only_call(client,cfg,'alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'});p.save(D/'immediate_prewrite_get.json',got)
        before=p.load(D/'before_get.json')['product'];assert got['product']['status']=='approved' and got['product']['display']=='Y';assert p.shared.stable_product(got['product'])==p.shared.stable_product(before)
        with ledger.open('x',encoding='utf-8')as f:json.dump({'id':pid,'state':'STARTED_OUTCOME_UNKNOWN_NO_REPLAY','at':p.now()},f)
        receipt=p.pub.api_submit(client,cfg,listing,False,update_product_id=pid);p.save(D/'update_receipt.json',receipt);p.save(ledger,{'id':pid,'state':receipt['status'],'at':receipt['attempted_at'],'refs':receipt.get('refs')});assert receipt['status']=='submitted_needs_readback',receipt['status']
        plan=p.load(D/'prepared.json');facts=p.load(F/'当前来源与色码核对.json');assert facts['pricing_draft']['tiers']==plan['old_tiers'];facts['pricing_draft'].update(tiers=plan['new_tiers'],rounding='ROUND_CEILING_TO_USD_CENT',current_price_repair=p.rel(D/'update_receipt.json'));facts['price_rounding_correction']={'state':'SUBMITTED_NEEDS_FULL_READBACK','id':pid,'evidence':p.rel(D/'prepared.json')};p.save(F/'当前来源与色码核对.json',facts)
        p.save(D/'current_expected_overlay.json',{'product_id':pid,'operation':'price_rounding_only','receipt':p.rel(D/'update_receipt.json'),'payload_sha256':p.sha(D/'payload.xml'),'expected_schema':plan['expected_schema']});print(a.style,'PRICE_SUBMITTED_ONCE',pid,flush=True);p.verify(client,cfg);p.sync();return
    if a.mode=='prepare':
        assert not ledger.exists(),'Existing write: verify only'
        facts=p.load(F/'当前来源与色码核对.json');old=facts['pricing_draft']['tiers'];fx=Decimal(str(facts['pricing_draft'].get('fx','6.6837')));cost=Decimal(facts['source_price_cny']);new=[[n,str((cost*m/fx).quantize(Decimal('.01'),rounding=ROUND_CEILING))]for n,m in ((2,Decimal('1.5')),(50,Decimal('1.4')),(100,Decimal('1.3')))];assert old!=new
        assert all(Decimal(b)-Decimal(a)in (Decimal(0),Decimal('.01'))and n==q for (n,a),(q,b)in zip(old,new))
        got=p.read_only_call(client,cfg,'alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'});before=got['product'];assert before['status']=='approved' and before['display']=='Y';assert p.shared.attributes(before)['Model Number']==[p.MODEL];p.save(D/'before_get.json',got)
        assert all(sorted((int(x['start_quantity']),Decimal(x['price']))for x in row['bulk_discount_prices'])==[(n,Decimal(v))for n,v in old]for row in before['product_sku']['skus'])
        rendered=p.read_only_call(client,cfg,'alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':p.CATEGORY,'language':'en_US'}});assert rendered.get('data');p.save(D/'before_render.json',rendered);schema=E.fromstring(rendered['data']);(D/'current_schema.xml').write_text(rendered['data'],encoding='utf-8');root=p.pub.values_only(schema,operation='update',field_ids=FIELDS)
        wanted=dict(new);seen=set()
        for row in root.findall("./field[@id='ladderPrice']/complex-value/field/complex-value"):
            n=int(row.find("./field[@id='quantity']/value").text);assert n in wanted;row.find("./field[@id='price']/value").text=wanted[n];seen.add(n)
        assert seen==set(wanted);assert root.find("./field[@id='scPrice']/value").text=='1';assert root.find("./field[@id='productTitle']/value").text==before['subject'];(D/'payload.xml').write_text(E.tostring(root,encoding='unicode'),encoding='utf-8')
        p.save(D/'manifest.json',{'operation':'update','product_id':pid,'category_id':p.CATEGORY,'facts_reviewed':True,'source_evidence':[p.rel(F/'当前来源与色码核对.json'),'02_Alibaba运营/00_运营SOP/国际站商品全生命周期SOP.md'],'current_schema':'current_schema.xml','current_schema_sha256':p.sha(D/'current_schema.xml'),'schema_request_id':rendered['request_id'],'schema_acquired_at':p.now(),'payload_xml':'payload.xml','field_ids':list(FIELDS),'dependency_ids':[],'unchanged_model_checked_before_write':p.MODEL})
        snap=p.contract.field_snapshot(root);p.save(D/'prepared.json',{'id':pid,'style':a.style,'at':p.now(),'old_tiers':old,'new_tiers':new,'state':'PREPARED_CURRENT_EXACT_PRICE_ROUNDING','expected_schema':{'ladderPrice':snap['ladderPrice']},'source_facts_sha256':p.sha(F/'当前来源与色码核对.json'),'scope':'Only 0.01 USD upward cent corrections, unchanged tier quantities/title/scPrice; no SKU ID, media, source or inventory write.'});p.pub.load_submission_manifest(D/'manifest.json','update',pid);print(a.style,'PRICE_PREPARED',new);return
    assert ledger.exists()
    if a.mode=='verify':p.verify(client,cfg)
    report=p.load(F/'verification.json')
    if a.mode=='finalize-saved':
        from datetime import datetime,timezone
        assert (datetime.now(timezone.utc)-datetime.fromisoformat(report['get_observed_at'])).total_seconds()<3600
        assert report['state']=='FORMAL_FIELDS_SCORE_PASS' and not report['failed']
    if report['state']not in ('FORMAL_FIELDS_SCORE_PASS','FORMAL_FIELDS_PASS_PENDING_SCORE','FORMAL_FIELDS_PASS_SCORE_BELOW_TARGET'):p.sync();print('PRICE_READBACK',report['state']);return
    before=p.load(D/'before_get.json')['product'];after=p.load(F/'after_get.json')['product'];assert stable(before)==stable(after),'Non-price formal field changed'
    snap=p.contract.field_snapshot(E.fromstring(p.load(F/'after_render.json')['data']));old=p.contract.field_snapshot(E.fromstring(p.load(D/'before_render.json')['data']));checks={k:p.contract.created_field_equivalent(k,v,snap.get(k))for k,v in old.items()if k!='ladderPrice'}
    assert all(checks.values()),[k for k,v in checks.items()if not v]
    p.save(D/'verification.json',{'id':pid,'at':p.now(),'state':report['state'],'full_current_verification':p.rel(F/'verification.json'),'protected_formal_product_except_exact_prices':True,'all_other_schema_fields_preserved':checks,'actual_score':report['actual_score'],'tiers':p.load(D/'prepared.json')['new_tiers']});facts=p.load(F/'当前来源与色码核对.json');facts['price_rounding_correction']['state']=report['state'];p.save(F/'当前来源与色码核对.json',facts);p.sync();print(a.style,'PRICE_FULL_FIELDS_AND_NON_TARGETS_PASS')

if __name__=='__main__':main()
