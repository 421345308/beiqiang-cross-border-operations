"""Apply reviewed, exact-ID image/style corrections once using fresh Schema.

Source facts and correction scope live with the business records. A review in
progress is skipped; an unknown write is only read back, never replayed.
"""
import argparse
from pathlib import Path
from xml.etree import ElementTree as E
import replace_hr_real_sources as o


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True)
    args = parser.parse_args()
    path = (o.ROOT / args.plan).resolve()
    assert path.is_relative_to(o.BASE.resolve())
    plan = o.b.load(path)
    assert plan['authorization'] == o.SCOPE['authorization']
    api, cfg = o.b.api_client()
    allowed = {pid: family for family, ids in o.TARGETS.items() for pid in ids.values()}
    for item in plan['items']:
        pid = item['id']
        assert pid in allowed
        slug = item['slug']
        assert slug in ('public_style', 'hero_quality')
        folder = o.BASE / '商品' / pid
        ledger = folder / (slug + '_once.json')
        if ledger.exists():
            print(pid, 'EXISTING_CORRECTION_READBACK_ONLY', flush=True)
            continue
        got = o.read_only_call(api, cfg, 'alibaba.icbu.product.get', {'product_id':pid,'language':'ENGLISH'})
        product = got['product']
        permitted=item.get('allowed_current_statuses',['approved'])
        rejected_style=product['status']=='tbd'and'tbd'in permitted
        if rejected_style:
            assert slug=='public_style'and allowed[pid]=='HR030'
            assert item['status_definition_source']=='https://developer.alibaba.com/doc2/apiDetail.htm?apiId=25439'
        if product['status'] not in permitted:
            print(pid, 'WAIT_CURRENT_REVIEW'if product['status']in ['new','modified']else'NON_APPROVED_REQUIRES_DIAGNOSIS', flush=True)
            continue
        rendered = o.read_only_call(api,cfg,'alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(product['category_id']),'language':'en_US'}})
        schema = E.fromstring(rendered['data'])
        fields = ['icbuCatProp'] if slug == 'public_style' else ['scImages']
        if rejected_style:fields.append('productTitle')
        root = o.pub.values_only(schema, operation='update', field_ids=fields)
        if rejected_style:assert root.find("./field[@id='productTitle']/value").text==product['subject']
        if slug == 'public_style':
            assert allowed[pid] == 'HR030'
            definition = next(x for x in schema.findall("./field[@id='icbuCatProp']/fields/field") if x.get('name')=='Style')
            cv = root.find('./field/complex-value')
            current = cv.find("./field[@id='"+definition.get('id')+"']")
            cv.remove(current)
            assert item['style'] == ['Platform Sneakers','Lace-up']
            o.set_attr(schema, cv, 'Style', item['style'])
        else:
            assert allowed[pid] == 'HR042'
            bank = o.b.load(o.BASE / 'HR042/图片银行.json')['items']
            assert item['image_roles'] == ['M1','M2','M3','M4','M5','M6']
            o.pub.set_main_images(root, [bank[k] for k in item['image_roles']])
        request = {'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(product['category_id']),'language':'en_US','xml':E.tostring(root,encoding='unicode')}}
        assert not root.findall(".//field[@id='skuStock']")
        o.b.save(folder/(slug+'_before_get.json'),got)
        o.b.save(folder/(slug+'_prepared.json'),{'request':request,'expected_schema':o.contract.field_snapshot(root),'reason':item['reason']})
        with ledger.open('x',encoding='utf8') as file:
            import json
            json.dump({'state':'OUTCOME_UNKNOWN','at':o.b.now(),'id':pid},file)
        result = api.top_call(cfg,'alibaba.icbu.product.schema.update',request)
        o.b.save(folder/(slug+'_receipt.json'),result)
        assert result.get('biz_success') is True and not api.api_error(result)
        o.b.save(ledger,{'state':'SUBMITTED','at':o.b.now(),'id':pid,'request_id':result.get('request_id')})
        o.b.save(folder/'verification.json',{'state':'SUBMITTED_AFTER_QUALITY_CORRECTION','at':o.b.now(),'public_qa':'PENDING','reason':item['reason']})
        print(pid,slug,'SUBMITTED',flush=True)


if __name__ == '__main__':
    main()
