"""Reconcile sequential R1811 repairs against the latest approved formal image read.

Earlier score-pending reports remain historical. No live write is performed here.
"""

import sys as _registry_sys
from pathlib import Path as _RegistryPath
_registry_sys.path.insert(0, str(_RegistryPath(__file__).resolve().parents[3]/"08_工具链/06_工作区维护"))
from product_registry import ProductRegistry
from pathlib import Path
from collections import Counter
import sys
sys.path.insert(0,str(Path(__file__).parent))
import revise_catalog_content as s
import schema_publish_contract as contract
from repair_source_assortment import axes,key
from repair_added_sku_marker import IDS,CONFIRMATION

def main():
    sys.stdout.reconfigure(encoding='utf8')
    cp=next(p for p in s.load(s.PLAN_FILE)['items'] if p['family']=='BQ015')
    base=s.BASE/'配色与尺码修正/BQ015'
    plan=s.load(base/'计划.json');bank=s.load(base/'图片银行.json')['items']
    bindings=s.load(s.BASE/'配色与尺码修正/BQ015_颜色图纠正/计划.json')['rebind_images']
    bindings={**bindings,**{label:row['url'] for label,row in bank.items()}}
    report={'at':s.now(),'state':'FORMAL_FIELDS_SCORE_PASS','scope':'Current title/highlights, six-colour/EU matrix, colour-image binding, retained SKU identities and 999 marker after sequential approved repairs. Not all-catalog image acceptance.','rows':[]}
    for pid in IDS:
        gallery=s.BASE/'图库重做/BQ015_六色总览/商品'/pid/'verification.json'
        g=s.load(gallery); assert g['state']=='FORMAL_FIELDS_SCORE_PASS'
        p=s.load(s.RAW/'图库重做/BQ015_六色总览'/pid/'after_get.json')['product']
        added=s.load(base/'商品'/pid/'prepared.json')
        marker=base/'库存标记'/pid/'verification.json';m=s.load(marker)
        bound={v['system_value_name']:v.get('image_url')for a in p['product_sku']['sku_attributes'] if str(a['attribute_id'])=='191288010'for v in a['values']}
        checks={'title':p['subject']==cp['title_by_id'][pid],
            'highlights':p['struct_detail']['product_summary'].replace('\u2019',"'")==cp['highlights'].replace('\u2019',"'"),
            'six_colour_EU_matrix':Counter(key(r,axes(p))for r in p['product_sku']['skus'])==Counter(tuple(x)for x in added['expected_pairs']),
            'colour_images':all(contract._created_image_identity(bound.get(label))==contract._created_image_identity(url)for label,url in bindings.items()),
            'all66_marker999':len(p['product_sku']['skus'])==66 and all(len(r.get('inventory_dto_list',[]))==1 and int(r['inventory_dto_list'][0]['inventory'])==999 for r in p['product_sku']['skus']),
            'marker_preserved_other_values':all(v is True for k,v in m['checks'].items()if k!='score'),
            'latest_main_and_all_other_fields':all(g['checks'].values()),'approved_visible':p['status']=='approved' and p['display']=='Y'}
        assert all(checks.values()),(pid,checks)
        report['rows'].append({'id':pid,'at':g['at'],'state':'FORMAL_FIELDS_SCORE_PASS','score':g['score'],'checks':checks,
            'inventory_scope':CONFIRMATION,'physical_stock_claim':False,
            'evidence':[s.rel(gallery),s.rel(marker),s.rel(base/'商品'/pid/'verification.json'),s.rel(s.BASE/'正式差异收尾/商品'/pid/'verification.json')]})
    s.save(base/'综合核验.json',report)
    registry=ProductRegistry(s.ROOT);d=s.load(registry)
    for row in report['rows']:
        listing=next(x for x in d['listings'] if x['id']==row['id'])
        assert listing['formal_fields']['at']==row['at'],'Latest canonical snapshot must match accepted gallery observation'
        phase={'at':row['at'],'state':row['state'],'score':row['score'],'scope':report['scope'],'evidence':[s.rel(base/'综合核验.json')]}
        listing.setdefault('optimization',{})['current_content_reconciliation']=phase
        listing.setdefault('local_sync',{}).update(state=row['state'],observed_at=row['at'],reconciliation=s.rel(base/'综合核验.json'))
    product=next(x for x in d['products']if x['id']=='BQ015')
    product['current_content_reconciliation']={'at':report['at'],'state':report['state'],'evidence':[s.rel(base/'综合核验.json')]}
    product['next_action']='三条均六色EU35–45、66SKU、正确颜色图、999可询货标记及六色主图总览已核验5.0；继续独立检查其他详情图与属性。'
    source=next(x for x in d['sources']if x['id']=='src-2064f015e244')
    source.setdefault('current_assortment',{}).update(at=report['at'],state='EXACT_COLOR_EU_AND_MARKER_VERIFIED',score='5.00',inventory=CONFIRMATION,reconciliation=s.rel(base/'综合核验.json'))
    s.save(registry,d)
    sys.path.insert(0,str(s.ROOT/'08_工具链/06_工作区维护'));import build_product_workspace as w
    assert not w.validate(d,s.ROOT)
    for path,body in w.build(d).items():w.write_generated(s.ROOT/path,body)
    print('R1811_CURRENT_COPY_MATRIX_IMAGES_MARKER_SCORE_PASS',len(report['rows']),flush=True)

if __name__=='__main__':main()
