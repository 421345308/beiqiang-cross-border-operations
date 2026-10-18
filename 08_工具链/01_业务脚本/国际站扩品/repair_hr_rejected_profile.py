"""One evidenced correction for an explicit custom-value-length business rejection."""
from pathlib import Path
from xml.etree import ElementTree as E
import argparse,copy,hashlib
import replace_hr_real_sources as o


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','submit']);parser.add_argument('pid');args=parser.parse_args()
    matches=[(family,variant)for family,targets in o.TARGETS.items()for variant,pid in targets.items()if pid==args.pid]
    assert len(matches)==1
    family,variant=matches[0];folder=o.BASE/'商品'/args.pid
    receipt=o.b.load(folder/'update_receipt.json');ledger=o.b.load(folder/'update_once.json')
    assert receipt.get('biz_success')is False and 'PUB_BIZCHECK_PROPERTY_CUSTOM_VALUE_LENGTH_LIMIT'in receipt.get('msg_code','')
    assert ledger['state']=='BUSINESS_REJECTED'
    correction=folder/'business_correction_once.json'
    assert not correction.exists(),'Correction already attempted; read back only'
    if args.mode=='prepare':
        original=o.b.load(folder/'prepared.json');fixed=copy.deepcopy(original)
        value=o.PLANS[family]['custom'][1];assert 0<len(value)<=70
        xml=E.fromstring(original['request']['param_product_top_publish_request']['xml'])
        target=xml.find("./field[@id='customMoreProperty']/complex-value/field[@id='customMoreProperty_0']/complex-value/field[@id='valueName']/value")
        assert target is not None and len(target.text)>70
        target.text=value;expected=o.contract.field_snapshot(xml)
        assert {k for k in expected if expected[k]!=original['expected_schema'].get(k)}=={'customMoreProperty'}
        fixed['request']['param_product_top_publish_request']['xml']=E.tostring(xml,encoding='unicode')
        fixed['xml_sha256']=hashlib.sha256(fixed['request']['param_product_top_publish_request']['xml'].encode()).hexdigest()
        fixed['expected_schema']=expected
        fixed['correction_reason']='Explicit biz_success=false rejection: custom value max70 ASCII characters. Only shorten the current source-supported Shoe Profile; do not replay the rejected payload.'
        fixed['original_request_file']='prepared.json';fixed['original_rejection_file']='update_receipt.json'
        o.b.save(folder/'business_correction_prepared.json',fixed)
        print(args.pid,'VALIDATED_DIFFERENT_PROFILE_CORRECTION_PREPARED');return
    prepared=o.b.load(folder/'business_correction_prepared.json');api,cfg=o.b.api_client()
    fresh=o.read_only_call(api,cfg,'alibaba.icbu.product.get',{'product_id':args.pid,'language':'ENGLISH'})
    o.b.save(folder/'business_correction_before_get.json',fresh)
    assert fresh['product']==o.b.load(folder/'before_get.json')['product'],'Rejected initial write must be confirmed unchanged before correction'
    o.b.save(correction,{'id':args.pid,'state':'OUTCOME_UNKNOWN','at':o.b.now(),'request_sha256':o.b.sha(folder/'business_correction_prepared.json'),'original_business_rejection':'update_receipt.json','authorization':'Owner2026-10-13 remaining HR full replacement; normal evidence-based correction of explicit rejected payload'})
    result=api.top_call(cfg,'alibaba.icbu.product.schema.update',prepared['request']);o.b.save(folder/'business_correction_receipt.json',result)
    if api.api_error(result)or result.get('biz_success')is False:
        o.b.save(correction,{'id':args.pid,'state':'BUSINESS_REJECTED','at':o.b.now(),'response_file':'business_correction_receipt.json','request_id':result.get('request_id')});print(args.pid,'CORRECTION_BUSINESS_REJECTED');return
    assert result.get('biz_success')is True,result
    o.b.save(correction,{'id':args.pid,'state':'SUBMITTED','at':o.b.now(),'request_id':result.get('request_id'),'trace_id':result.get('_trace_id_')})
    print(args.pid,'DIFFERENT_CORRECTED_REQUEST_SUBMITTED')


if __name__=='__main__':main()
