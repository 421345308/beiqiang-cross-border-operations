"""Repair a title-only formal mismatch after an authorized whole-shoe replacement."""
import sys,hashlib
from xml.etree import ElementTree as E
import replace_hr_real_sources as o
def main():
    pid=sys.argv[1];matches=[(f,v)for f,t in o.TARGETS.items()for v,i in t.items()if i==pid];assert len(matches)==1
    family,variant=matches[0];folder=o.BASE/'商品'/pid;proof=o.b.load(folder/'verification.json')
    assert proof['state']=='FORMAL_MISMATCH'and proof['failed']==['productTitle']
    ledger=folder/'title_repair_once.json';assert not ledger.exists(),'Existing title repair must only be read back'
    title=o.PLANS[family]['titles'][variant];api,cfg=o.b.api_client()
    got=o.read_only_call(api,cfg,'alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'})
    assert got['product']==o.b.load(folder/'after_get.json')['product'] and got['product']['status']=='approved'
    rendered=o.read_only_call(api,cfg,'alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(got['product']['category_id']),'language':'en_US'}})
    schema=E.fromstring(rendered['data']);root=o.pub.values_only(schema,operation='update',field_ids=['productTitle']);value=root.find('./field/value');assert value is not None and value.text==got['product']['subject'] and value.text!=title
    value.text=title;xml=E.tostring(root,encoding='unicode');request={'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(got['product']['category_id']),'language':'en_US','xml':xml}}
    o.b.save(folder/'title_repair_before_get.json',got);o.b.save(folder/'title_repair_before_render.json',rendered)
    o.b.save(folder/'title_repair_prepared.json',{'request':request,'reason':'Formal title differs from reviewed source-specific submitted product title. Correct only title; cause of later change unconfirmed, not attributed to a person or platform automation.','expected_title':title,'observed_title':got['product']['subject'],'expected_schema':o.contract.field_snapshot(root),'xml_sha256':hashlib.sha256(xml.encode()).hexdigest()})
    o.b.save(ledger,{'id':pid,'at':o.b.now(),'state':'OUTCOME_UNKNOWN','authorization':'Owner full HR title/image/detail optimization; one observed title-only mismatch correction, no SKU/material/price or source changes'})
    result=api.top_call(cfg,'alibaba.icbu.product.schema.update',request);o.b.save(folder/'title_repair_receipt.json',result)
    success=result.get('biz_success')is True and not api.api_error(result)
    o.b.save(ledger,{'id':pid,'at':o.b.now(),'state':'SUBMITTED'if success else'BUSINESS_REJECTED','request_id':result.get('request_id')})
    print(pid,'TITLE_ONLY_REPAIR_SUBMITTED'if success else'TITLE_REPAIR_REJECTED',flush=True)
if __name__=='__main__':main()
