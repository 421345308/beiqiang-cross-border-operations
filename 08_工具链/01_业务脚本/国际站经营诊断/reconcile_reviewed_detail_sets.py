"""Check the reviewed four-role detail sets against current exact image bindings.

This joins active-agent visual decisions to formal image identities and SKU axes.
It does not infer visual quality or shoe facts from the API score.
"""
from pathlib import Path
from collections import Counter
import sys
sys.path.insert(0,str(Path(__file__).parent))
import revise_catalog_content as s
import schema_publish_contract as c
from repair_source_assortment import axes,key
from build_current_colour_diagram import eu_number


def main():
    sys.stdout.reconfigure(encoding='utf8')
    index=s.load(s.BASE/'详情图组收尾执行.json');assert index['reviewer']=='active_agent'
    registry=s.load(s.ProductRegistry(s.ROOT));byid={l['id']:l for l in registry['listings']}
    cache=s.load(s.ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前素材清单.json')['assets']
    native={c._created_image_identity(u):r for u,r in cache.items()if r.get('file')}
    results=[]
    for g in index['groups']:
        folder=s.BASE/'图库重做'/g['family'];plan=s.load(folder/'计划.json');assert plan['reviewed']and plan['reviewer']=='active_agent'
        bank=s.load(folder/'图片银行.json')['items']
        for pid in g['ids']:
            l=byid[pid];p=s.load(s.ROOT/l['formal_fields']['file'])['response']['product']
            report=s.load(folder/'商品'/pid/'verification.json')
            urls=[r['image_url']for r in p['struct_detail']['detail_image']['images']]
            targets=s.load(folder/'商品'/pid/'prepared.json');wanted=targets['expected_detail']
            checks={'formal_pass':report['state']=='FORMAL_FIELDS_SCORE_PASS','current_detail_targets':sorted(map(c._created_image_identity,urls))==sorted(map(c._created_image_identity,wanted))}
            if plan['kind']!='main_slot':
                checks['four_distinct_details']=len(urls)==len(set(map(c._created_image_identity,urls)))==4
                bound=set(map(c._created_image_identity,urls));matrices=[]
                for f in plan['source_evidence']:
                    if not Path(f).name.startswith('matrix_'):continue
                    digest=Path(f).stem.removeprefix('matrix_')
                    roles=['colour_'+digest,'eu_'+digest]
                    if all(c._created_image_identity(bank[role]['url'])in bound for role in roles):matrices.append(s.load(s.ROOT/f))
                current={}
                ax=axes(p)
                for row in p['product_sku']['skus']:
                    colour,size=key(row,ax);current.setdefault(colour,set()).add(eu_number(size))
                matching=[m for m in matrices if{r['colour']:set(r['EU'])for r in m['rows']}==current]
                # Several original IDs use different image-bank URLs for the
                # exact same source bytes. Identical colour/EU diagrams are
                # uploaded once; keep all URL records, deduplicate only proven
                # binary-identical matrix content, not arbitrary CDN strings.
                signature=lambda m:tuple((r['colour'],tuple(r['EU']),r['sha256'])for r in m['rows'])
                checks['one_bound_matrix_content']=len({signature(m)for m in matrices})==1
                checks['exact_current_colour_eu_matrix']=len({signature(m)for m in matching})==1
                checks['matrix_photos_unchanged']=all(s.sha(s.ROOT/r['file'])==r['sha256']for m in matching for r in m['rows'])
                photos={v['system_value_name']:native[c._created_image_identity(v['image_url'])]['sha256']for a in p['product_sku']['sku_attributes']if str(a['attribute_id'])=='191288010'for v in a['values']}
                checks['matrix_current_sku_photos']=all(photos.get(r['colour'])==r['sha256']for m in matching for r in m['rows'])
            for old,role in plan.get('main_replacements_by_id',{}).get(pid,{}).items():
                checks['main_target_'+role]=c._created_image_identity(bank[role]['url'])in list(map(c._created_image_identity,p['main_image']['images']))
            checks['all_bound_images_have_native_masters']=all(c._created_image_identity(u)in native for u in urls)
            results.append({'id':pid,'family':plan.get('product_family',plan['family']),'state':'REVIEWED_DETAIL_SET_CURRENT_PASS'if all(checks.values())else'CURRENT_DETAIL_SET_DIFFERENCE','checks':checks,'visual_decision':index['review'],'formal_proof':s.rel(folder/'商品'/pid/'verification.json'),'current_fields':l['formal_fields']['file']})
    findings=s.load(s.BASE/'详情旧图定位.json')
    bad={c._created_image_identity(r['url']):r for r in findings['images']};remaining=[]
    current_items=s.load(s.BASE/'全店图片终检.json')['items']
    for item in current_items:
        pid=item['id'];p=s.load(s.ROOT/byid[pid]['formal_fields']['file'])['response']['product']
        for role,urls in [('main',p['main_image']['images']),('detail',[r['image_url']for r in p['struct_detail']['detail_image']['images']])]:
            for u in urls:
                if c._created_image_identity(u)in bad:remaining.append({'id':pid,'role':role,'url':u})
    out={'at':s.now(),'scope':'Per-ID exact current targets plus human-inspected real-shoe role sets and current SKU matrices. API membership is separate from the active-agent native visual review.','states':dict(Counter(r['state']for r in results)),'items':results,'observed_legacy_images':len(bad),'legacy_images_still_bound':remaining,'catalog_scope_checked':len(current_items)}
    s.save(s.BASE/'详情信息复核.json',out);print(out['states'])
    assert all(r['state']=='REVIEWED_DETAIL_SET_CURRENT_PASS'for r in results)
    assert not remaining,'Known old use/order/sole plates remain bound'


if __name__=='__main__':main()
