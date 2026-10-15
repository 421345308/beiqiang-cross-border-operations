"""Read observed category IDs for current Luqi product/category matching.

Does not publish, change a company category, or relax material/claim checks.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse
from xml.etree import ElementTree as E
import refresh_buyer_copy as b
from read_only_catalog import read_only_call

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'02_Alibaba运营/05_扩品工程/执行记录/路崎宽头户外_2026-10-08/质量复核_2026-10-09/类目适配核对'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('category_ids',type=int,nargs='+',help='IDs observed in official category responses; do not guess IDs')
    parser.add_argument('--schema',action='store_true',help='Read current publish Schema of each requested leaf')
    args=parser.parse_args();api,cfg=b.api_client();OUT.mkdir(parents=True,exist_ok=True)
    def one(cid):
        result=read_only_call(api,cfg,'alibaba.icbu.category.get.new',{'cat_id':cid})
        category=result['category'];assert category['category_id']==cid
        b.save(OUT/(str(cid)+'.json'),{'method':'alibaba.icbu.category.get.new','request':{'cat_id':cid},'observed_at':b.now(),'response':result})
        if args.schema:
            assert category['leaf_category']
            schema=read_only_call(api,cfg,'alibaba.icbu.product.schema.get',{'param_product_top_publish_request':{'cat_id':cid,'language':'en_US'}})
            assert schema.get('data') and schema.get('request_id');xml=E.fromstring(schema['data'])
            b.save(OUT/(str(cid)+'_schema.json'),schema);(OUT/(str(cid)+'_schema.xml')).write_text(schema['data'],encoding='utf8')
            attrs=[]
            for field in xml.findall("./field[@id='icbuCatProp']/fields/field"):
                attrs.append({'id':field.get('id'),'name':field.get('name'),'type':field.get('type'),'rules':[{k:r.get(k)for k in ('name','value')}for r in field.findall('./rules/rule')],'options':[o.get('displayName')for o in field.findall('./options/option')]})
            b.save(OUT/(str(cid)+'_attributes.json'),attrs)
        return {'id':cid,'name':category['name'],'leaf':category['leaf_category'],'parents':category.get('parent_ids',[]),'children':category.get('child_ids',[])}
    with ThreadPoolExecutor(max_workers=3)as pool:
        for row in pool.map(one,args.category_ids):print(row,flush=True)

if __name__=='__main__':main()
