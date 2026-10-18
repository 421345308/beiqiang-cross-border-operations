"""Read current official leaf categories; save public category evidence only."""
import sys
from concurrent.futures import ThreadPoolExecutor
import refresh_buyer_copy as b
from read_only_catalog import read_only_call
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'02_Alibaba运营/05_扩品工程/执行记录/HR实源替换/类目核验'
def main():
    api,cfg=b.api_client();OUT.mkdir(exist_ok=True)
    def one(cid):
        result=read_only_call(api,cfg,'alibaba.icbu.category.get.new',{'cat_id':int(cid)})
        category=result['category'];assert category['category_id']==int(cid)
        b.save(OUT/(str(cid)+'.json'),{'method':'alibaba.icbu.category.get.new','request':{'cat_id':int(cid)},'observed_at':b.now(),'official_parameter_documentation':'https://developer.alibaba.com/docs/api.htm?apiId=50064','response':result})
        print(cid,category['name'],'LEAF',category['leaf_category'],'CHILDREN',category.get('child_ids'),flush=True)
    with ThreadPoolExecutor(max_workers=3)as pool:list(pool.map(one,sys.argv[1:]))
if __name__=='__main__':main()
