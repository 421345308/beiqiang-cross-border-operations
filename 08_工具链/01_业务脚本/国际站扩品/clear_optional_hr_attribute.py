"""One precise correction after a formal read proves omission retained an old value."""
import sys,hashlib,copy
from xml.etree import ElementTree as E
import replace_hr_real_sources as o

def main():
    family=sys.argv[1];plan=o.PLANS[family]
    assert plan.get('category_attribute_omissions')==['Closure Type']
    api,cfg=o.b.api_client()
    for pid in o.TARGETS[family].values():
        folder=o.BASE/'商品'/pid;ledger=folder/'optional_attribute_clear_once.json'
        assert not ledger.exists(),'Already attempted: formal read only'
        got=o.read_only_call(api,cfg,'alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'})
        p=got['product'];assert p['status']=='approved'
        assert next(a['value_name']for a in p['attributes']if a['attribute_name']=='Closure Type')=='Lace-up'
        response=o.read_only_call(api,cfg,'alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US'}})
        schema=E.fromstring(response['data']);definition=next(f for f in schema.findall("./field[@id='icbuCatProp']/fields/field")if f.get('name')=='Closure Type')
        assert definition.get('type')=='singleCheck' and not any(r.get('name')=='requiredRule' and r.get('value')=='true'for r in definition.findall('./rules/rule'))
        root=o.pub.values_only(schema,operation='update',field_ids=['icbuCatProp'])
        target=root.find("./field[@id='icbuCatProp']/complex-value/field[@id='"+definition.get('id')+"']")
        assert target is not None
        for child in list(target):target.remove(child)
        E.SubElement(target,'value').text=''
        xml=E.tostring(root,encoding='unicode')
        request={'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US','xml':xml}}
        o.b.save(folder/'optional_attribute_clear_before_get.json',got)
        o.b.save(folder/'optional_attribute_clear_before_render.json',response)
        o.b.save(folder/'optional_attribute_clear_prepared.json',{'request':request,'xml_sha256':hashlib.sha256(xml.encode()).hexdigest(),'reason':'Omitting the optional Closure Type retained old Lace-up in formal get. Explicit empty value clears that optional stale enum; actual Dial Closure remains in title, source-specific highlight and Shoe Profile. Other current category attributes copied literally.'})
        o.b.save(ledger,{'id':pid,'at':o.b.now(),'state':'OUTCOME_UNKNOWN','authorization':'Owner exact-ID whole-shoe optimization and evidence-based attribute repair; no SKU/media/price mutation'})
        res=api.top_call(cfg,'alibaba.icbu.product.schema.update',request);o.b.save(folder/'optional_attribute_clear_receipt.json',res)
        success=res.get('biz_success')is True and not api.api_error(res)
        o.b.save(ledger,{'id':pid,'at':o.b.now(),'state':'SUBMITTED'if success else'BUSINESS_REJECTED','request_id':res.get('request_id'),'response_file':'optional_attribute_clear_receipt.json'})
        print(pid,'OPTIONAL_ATTRIBUTE_CLEAR_SUBMITTED'if success else'CLEAR_BUSINESS_REJECTED',flush=True)
if __name__=='__main__':main()
