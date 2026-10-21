"""Verify current exact SKU photo targets after later authorized gallery edits.

Keep initial submission/full-field reports intact. This separate scoped proof
does not treat a later gallery change as a failed SKU photograph replacement.
"""
from pathlib import Path
from copy import deepcopy
import sys
sys.path.insert(0,str(Path(__file__).parent));import revise_catalog_content as s
import schema_publish_contract as c

def sku_structure(p):
    value=deepcopy(p['product_sku'])
    for axis in value['sku_attributes']:
        for row in axis.get('values',[]):row.pop('image_url',None)
    return value

def main():
    sys.stdout.reconfigure(encoding='utf8');reg=s.load(s.ProductRegistry(s.ROOT));byid={l['id']:l for l in reg['listings']};index=s.load(s.BASE/'规格照片精修执行.json');count=0
    for group in index['groups']:
        folder=s.BASE/'配色与尺码修正'/group['key'];plan=s.load(folder/'计划.json')
        for pid in plan['ids']:
            raw=s.RAW/'配色与尺码修正'/group['key']/pid;before=s.load(raw/'before_get.json')['product'];listing=byid[pid];formal=s.ROOT/listing['formal_fields']['file'];current=s.load(formal)['response']['product'];photos={v['system_value_name']:v.get('image_url')for a in current['product_sku']['sku_attributes']if str(a['attribute_id'])=='191288010'for v in a['values']}
            checks={'exact_colour_photos':all(c._created_image_identity(photos.get(colour))==c._created_image_identity(url)for colour,url in plan['rebind_images'].items()),'all_sku_identity_structure_prices_stock_unchanged':sku_structure(current)==sku_structure(before),'approved_visible':current['status']=='approved'and current['display']=='Y'}
            gallery=listing.get('optimization',{}).get('content_gallery_revision',{});evidence=[s.rel(formal),s.rel(folder/'计划.json'),s.rel(folder/'图片银行.json')]+gallery.get('evidence',[]);score=listing.get('observation',{}).get('score');checks['latest_formal_score']=score is not None and float(score)>=5
            report={'id':pid,'at':s.now(),'state':'FORMAL_FIELDS_SCORE_PASS'if all(checks.values())else'CURRENT_SKU_PHOTO_DIFFERENCE','scope':'Current exact SKU colour photos and unchanged SKU identities, size combinations, prices and stock. Later independently authorized main/detail gallery revisions are outside this SKU-only check; their own formal proof is linked. Does not replace original full-field submission report.','checks':checks,'failed':[k for k,v in checks.items()if not v],'score':score,'evidence':evidence,'formal_observed_at':listing['formal_fields']['at']};s.save(folder/'商品'/pid/'current_colour_verification.json',report);assert all(checks.values()),(pid,report['failed']);count+=1
    print('CURRENT_EXACT_SKU_PHOTOS_PASS',count)

if __name__=='__main__':main()
