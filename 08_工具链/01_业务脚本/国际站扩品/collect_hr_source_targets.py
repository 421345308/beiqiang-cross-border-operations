"""Collect fresh official inputs for exact, source-reviewed HR drafts only."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(Path(__file__).parent))
import refresh_buyer_copy as b
from read_only_catalog import read_only_call
BASE=ROOT/'02_Alibaba运营/05_扩品工程/执行记录/HR实源替换'
def main():
    families=sys.argv[1:];api,cfg=b.api_client()
    def collect(family):
        plan=b.load(BASE/family/'事实与页面计划.json')
        assert (BASE/family/'来源事实.json').exists()
        for variant,pid in plan['target_ids'].items():
            folder=BASE/'商品'/pid
            if (folder/'update_once.json').exists():
                print(pid,'ALREADY_WRITTEN_INPUTS_PRESERVED',flush=True);continue
            got=read_only_call(api,cfg,'alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'})
            product=got.get('product');assert product and product['status']=='approved',(pid,'Not an approved editable original target')
            assert b.model(product)==family+'-'+variant,(pid,b.model(product),'identity mismatch')
            rendered=read_only_call(api,cfg,'alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(product['category_id']),'language':'en_US'}})
            assert rendered.get('data')
            b.save(folder/'before_get.json',got);b.save(folder/'before_render.json',rendered)
            print(pid,'FRESH_APPROVED_INPUTS_SAVED',flush=True)
        schema=read_only_call(api,cfg,'alibaba.icbu.product.schema.get',{'param_product_top_publish_request':{'cat_id':plan['category_id'],'language':'en_US'}})
        assert schema.get('data')
        b.save(BASE/family/'目标类目Schema.json',schema)
    with ThreadPoolExecutor(max_workers=min(3,len(families))) as pool:list(pool.map(collect,families))
if __name__=='__main__':main()
