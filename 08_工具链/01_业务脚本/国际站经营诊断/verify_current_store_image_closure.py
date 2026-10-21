"""Read every current original ID and check formal image closure against local truth.

Read-only API operations. Semantic native-image review remains separate evidence;
this verifier never equates an API score or URL count with photographic quality.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import sys,json,argparse
sys.path.insert(0,str(Path(__file__).parent))
import revise_catalog_content as s
import schema_publish_contract as c
from read_only_catalog import read_only_call,fetch_catalog

def identity(value):return c._created_image_identity(value)

def image_fields(p):
    colour=next((a for a in p.get('product_sku',{}).get('sku_attributes',[])if str(a['attribute_id'])=='191288010'),{})
    return {'main':[identity(u)for u in p['main_image']['images']],
            'detail':sorted((identity(r['image_url']),r['image_set']['id'])for r in p['struct_detail']['detail_image']['images']),
            'colours':sorted((v['system_value_name'],identity(v.get('image_url','')))for v in colour.get('values',[]))}


def latest_read_states(folder):
    """A failed fresh read must never inherit a previous successful snapshot."""
    runs=[s.load(folder/name)for name in ('读取结果.json','增量读取结果.json')if(folder/name).exists()]
    latest={}
    for run in sorted(runs,key=lambda r:r['at']):
        for item in run['items']:latest[item['id']]=item
    return latest

def main():
    sys.stdout.reconfigure(encoding='utf8');ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['read','audit']);ap.add_argument('--ids',help='Refresh only these original IDs after an already complete catalog read');a=ap.parse_args();folder=s.RAW/'全店图片续修/最终API回读';folder.mkdir(parents=True,exist_ok=True)
    reg=s.load(s.ProductRegistry(s.ROOT));byid={l['id']:l for l in reg['listings']}
    if a.mode=='read':
        api,cfg=s.client()
        if a.ids:
            catalog=s.load(folder/'catalog.json');scope={str(r['id'])for r in catalog['products']};current=set(a.ids.split(','));assert current and current<=scope,'Only refresh independently enumerated original IDs'
        else:
            catalog=fetch_catalog(api,cfg,folder/'目录');current={str(r['id'])for r in catalog['products']};s.save(folder/'catalog.json',catalog)
        def one(pid):
            try:
                r=read_only_call(api,cfg,'alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'});assert r.get('product');s.save(folder/'商品'/pid/'get.json',{'id':pid,'at':s.now(),'response':r});return {'id':pid,'state':'READ'}
            except Exception as e:return {'id':pid,'state':'READ_FAILED','error_type':type(e).__name__,'api_evidence':getattr(e,'api_evidence',None)}
        results=[]
        with ThreadPoolExecutor(max_workers=4)as pool:
            for r in pool.map(one,sorted(current)):
                results.append(r)
                if len(results)%40==0:print('READ',len(results),'/',len(current),flush=True)
        s.save(folder/('增量读取结果.json'if a.ids else'读取结果.json'),{'at':s.now(),'items':results});print('COMPLETE',len(results),'ERRORS',sum(r['state']!='READ'for r in results),flush=True)
        return
    current={str(r['id'])for r in s.load(folder/'catalog.json')['products']};rows=[];protected=[];read_states=latest_read_states(folder)
    suite=s.load(s.ROOT/'02_Alibaba运营/06_图片与检查记录/共享工厂详情/V8/url_identity.json')
    suite_urls={u:(r['asset'],r['gallery_id'])for r in suite['items']for u in r['accepted_urls']}
    suite_roles=sorted((r['asset'],r['gallery_id'])for r in suite['items'])
    # A submitted item temporarily hidden during review stays in this task's
    # scope; never relabel it as an untouched/offline exclusion.
    eligible_ids={r['id']for r in s.load(s.BASE/'全店图片覆盖.json')['items']}
    frozen={str(r['id'])for r in s.load(s.RAW/'全店图片续修/当前目录/catalog.json')['products']}
    for pid in sorted(current):
        if read_states.get(pid,{}).get('state')!='READ':rows.append({'id':pid,'state':'LATEST_API_READ_FAILED_OR_MISSING','read_state':read_states.get(pid)});continue
        file=folder/'商品'/pid/'get.json'
        if not file.exists():rows.append({'id':pid,'state':'API_READ_MISSING'});continue
        got=s.load(file);p=got['response']['product']
        if pid in s.PROTECTED or(pid not in eligible_ids and(p['status']!='approved'or p['display']!='Y')):protected.append({'id':pid,'status':p['status'],'display':p['display'],'action':'EXCLUDED_FROM_IMAGE_WRITES'});continue
        l=byid.get(pid)
        if not l:rows.append({'id':pid,'state':'LOCAL_ID_MISSING'});continue
        before=s.load(s.ROOT/l['formal_fields']['file'])['response']['product'];actual=image_fields(p);wanted=image_fields(before);minimum=3 if l['product_id']=='BQ-C2627'or l['product_id'].endswith('2627BSK')else 4
        factory=identity('https://sc04.alicdn.com/kf/Hea3fc4c6da4b46e0bb75c003260875120.png')
        checks={'main_exact_local':actual['main']==wanted['main'],'detail_exact_local':actual['detail']==wanted['detail'],'colour_photos_exact_local':actual['colours']==wanted['colours'],'six_main':len(actual['main'])==6,'no_exact_main_duplicate':len(set(actual['main']))==len(actual['main']),'product_detail_minimum':len(actual['detail'])>=minimum,'no_exact_detail_duplicate':len(set(u for u,g in actual['detail']))==len(actual['detail']),'sku_rows_unchanged':p['product_sku']['skus']==before['product_sku']['skus'],'factory_position_unchanged':[(i,u)for i,u in enumerate(actual['main'])if u==factory]==[(i,u)for i,u in enumerate(wanted['main'])if u==factory]}
        checks['one_standard_factory_image']=actual['main'].count(factory)==1
        company=p['struct_detail']['company_image']['images'];previous_company=before['struct_detail']['company_image']['images']
        checks['company_suite_exact_local']=sorted((identity(r['image_url']),r['image_set']['id'])for r in company)==sorted((identity(r['image_url']),r['image_set']['id'])for r in previous_company)
        checks['six_approved_company_images_and_roles']=sorted((suite_urls.get(r['image_url'],('UNKNOWN',None))[0],r['image_set']['id'])for r in company)==suite_roles
        checks['approved_visible']=p['status']=='approved'and p['display']=='Y'
        state='FORMAL_IMAGE_CLOSURE_PASS'if all(checks.values())else'API_REVIEW_PENDING'if not checks['approved_visible']else'FORMAL_DIFFERENCE'
        rows.append({'id':pid,'family':l['product_id'],'at':got['at'],'state':state,'checks':checks,'failed':[k for k,v in checks.items()if not v],'formal_before':l['formal_fields']['file'],'api_evidence_local':s.rel(file),'public_status':'API_ONLY_PER_OWNER_NO_BROWSER'})
    out={'at':s.now(),'method':'alibaba.icbu.product.list + product.get; original-ID full pagination and independent formal readback','actual_catalog_ids':len(current),'added_ids':sorted(current-frozen),'missing_ids':sorted(frozen-current),'eligible':len(rows),'states':dict(Counter(r['state']for r in rows)),'excluded_not_written':protected,'items':rows,'scope_limit':'URL identity, gallery membership, SKU and local synchronization verification. Native photographic review is separately recorded in exact product image plans and source proofs. Does not prove stock, performance, browser public rendering, or universal native-resolution visual acceptance.'}
    s.save(s.BASE/'全店图片终检.json',out);print(json.dumps({k:out[k]for k in ('actual_catalog_ids','eligible','states','added_ids','missing_ids')},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
