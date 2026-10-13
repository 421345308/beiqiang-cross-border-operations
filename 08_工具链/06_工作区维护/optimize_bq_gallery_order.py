"""Reorder individually matched, visually reviewed BQ images; no video or claim changes."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
REGISTRY=ROOT/'02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json'
AREA=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录'
# One-based visually reviewed preferred order. Unmatched variant images stay
# in their original slot; family identity alone never authorizes replacing them.
ORDERS={'BQ001':[1,4,2,3,5,6],'BQ002':[1,4,2,5,3,6],
        'BQ011':[1,5,6,4,2,3],'BQ013':[3,2,1,4,5,6],
        'BQ014':[3,5,1,2,4,6],'BQ016':[2,6,1,3,4,5],
        'BQ039':[1,4,2,3,5,6],'BQ047':[4,3,1,2,6,5],
        'BQ051':[1,4,3,6,2,5],'BQ053':[1,3,4,6,2,5],
        'BQ059':[3,6,2,4,1,5]}
# These variants were then individually inspected in links_1..10 contact sheets.
LINK_ORDERS={'1601939572948':[5,2,1,3,4,6],'1601939707196':[1,6,2,5,3,4],
 '1601939635505':[1,4,2,5,3,6],'1601939654418':[1,4,2,5,3,6],
 '1601939606803':[1,4,3,5,6,2],'1601939634522':[1,6,5,2,3,4],
 '1601939736061':[1,3,2,4,5,6],'1601939619687':[3,2,1,4,5,6],
 '1601939608686':[3,5,1,2,4,6],'1601939669411':[3,5,1,2,6,4],
 '1601939633580':[1,2,6,3,4,5],'1601939608691':[4,6,1,2,3,5],
 '1601939711161':[1,6,2,3,4,5],'1601939701201':[1,6,2,3,4,5],
 '1601939585913':[1,6,2,3,4,5]}

def key(url):
    name=Path(urlparse('https:'+url if url.startswith('//') else url).path).name
    return re.sub(r'_\d+x\d+\.jpg$','',name,flags=re.I).rsplit('.',1)[0]
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def stamp():return datetime.now(timezone.utc).isoformat()
def invariant(p):
    out=deepcopy({k:v for k,v in p.items() if k not in {'main_image','status','display','gmt_modified','pc_detail_url'}})
    # Platform readback reorders named company sections without changing roles.
    company=(out.get('struct_detail') or {}).get('company_image') or {}
    if isinstance(company.get('images'),list):company['images'].sort(key=lambda x:json.dumps(x,sort_keys=True))
    return out

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['plan','submit','verify'])
    args=parser.parse_args()
    data=json.loads(REGISTRY.read_text(encoding='utf-8-sig'))
    targets=data['bq_ease_optimization']['targets']
    by_id={l['id']:l for l in data['listings']}
    visual=json.loads((ROOT/'99_临时区/商品对应/图审/slot_urls.json').read_text(encoding='utf-8'))
    link_visual=json.loads((ROOT/'99_临时区/商品对应/图审/link_slot_urls.json').read_text(encoding='utf-8'))
    bank={}
    for file in (AREA/'图片银行').glob('photobank_page*_500.json'):
        for row in json.loads(file.read_text(encoding='utf-8')).get('pagination_query_list',{}).get('list',[]):bank[key(row['url'])]=row
    if args.mode!='plan':
        spec=importlib.util.spec_from_file_location('api',ROOT/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py')
        api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)
        cfg=api.load_config(api.DEFAULT_CONFIG)
        def call(method,params):return api.top_call(cfg,method,params)
    results=[]
    for pid in targets:
        family=by_id[pid]['product_id']
        if family not in ORDERS and pid not in LINK_ORDERS:continue
        folder=AREA/'商品'/pid/'穿脱优化'
        planfile=folder/'图库拟改字段.json'
        if args.mode=='plan':
            if planfile.exists():
                results.append({'id':pid,'state':'EXISTING_PLAN_PRESERVED'});continue
            original=json.loads((AREA/'商品'/pid/'formal_get.json').read_text(encoding='utf-8'))['response']['product']['main_image']['images']
            reviewed={x['slot']:key(x['url']) for x in visual['images'] if x['family']==family}
            order=ORDERS.get(family)
            if pid in LINK_ORDERS:
                reviewed={x['slot']:key(x['url']) for x in link_visual['images'] if x['id']==pid}
                order=LINK_ORDERS[pid]
            # Individually matched reviewed images may move. Unreviewed variant
            # artwork stays in its exact original slot, including the hero.
            if set(map(key,original))!=set(reviewed.values()):
                positions=[i for i,u in enumerate(original) if i>0 and key(u) in reviewed.values()]
                if len(positions)<2:
                    results.append({'id':pid,'state':'VARIANT_GALLERY_REQUIRES_INDIVIDUAL_REVIEW'});continue
                ranked=[original[i] for slot in order for i in positions if key(original[i])==reviewed[slot]]
                expected=list(original)
                for position,url in zip(positions,ranked):expected[position]=url
            else:expected=[original[next(i for i,u in enumerate(original) if key(u)==reviewed[slot])] for slot in order]
            if list(map(key,expected))==list(map(key,original)):continue
            matched=[bank.get(key(url)) for url in expected]
            if any(not row or not row.get('id') for row in matched):
                results.append({'id':pid,'state':'CURRENT_IMAGE_BANK_ID_MISSING'});continue
            plan={'id':pid,'family':family,'before_images':original,'expected_images':expected,'image_bank_ids':[str(row['id']) for row in matched],
                  'source':'已逐图检查本轮19款图库；只移动身份匹配的已图审图片，未图审变体图片原位保留，全部原图仍在',
                  'purpose':'提高鞋口、套脚上脚/穿鞋动作的前排可见性；BQ013/014/016/047/059采用更清楚的已有主图',
                  'reviewed_order':order,'state':'LOCAL_DRAFT_PENDING_TITLE_APPROVAL'}
            save(planfile,plan);results.append({'id':pid,'state':plan['state']});continue
        if not planfile.exists():continue
        plan=json.loads(planfile.read_text(encoding='utf-8'))
        if args.mode=='submit':
            ledger=folder/'图库单次提交账本.json'
            if ledger.exists():results.append({'id':pid,'state':'EXISTING_GALLERY_RESERVATION_READBACK_ONLY'});continue
            got=call('alibaba.icbu.product.get',{'product_id':int(pid),'language':'ENGLISH'})
            p=got.get('product',{})
            title=plan.get('preserve_actual_title') or json.loads((folder/'拟改字段.json').read_text(encoding='utf-8'))['title']
            if p.get('status')!='approved' or p.get('display')!='Y':results.append({'id':pid,'state':'WAIT_TITLE_APPROVAL'});continue
            if p.get('subject')!=title or list(map(key,p.get('main_image',{}).get('images',[])))!=list(map(key,plan['before_images'])):
                results.append({'id':pid,'state':'CURRENT_FIELDS_CHANGED_REVIEW_REQUIRED'});continue
            schema=call('alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US'}})
            save(folder/'图库当前Schema回执.json',schema)
            if not schema.get('data'):results.append({'id':pid,'state':'SCHEMA_UNAVAILABLE'});continue
            root=ET.fromstring(schema['data'])
            gallery=root.find("./field[@id='scImages']")
            if gallery is None or gallery.get('type')!='complex' or gallery.find('complex-value') is None:
                results.append({'id':pid,'state':'SCHEMA_GALLERY_SHAPE_UNVERIFIED'});continue
            save(folder/'图库写前正式商品.json',got)
            save(folder/'图库写前视频字段.json',{f.get('id'):ET.tostring(f,encoding='unicode') for f in root.findall('./field') if f.get('id') in {'imageVideo','detailVideo'}})
            payload=ET.Element('itemSchema');field=ET.SubElement(payload,'field',{'id':'scImages','type':'complex'});values=ET.SubElement(field,'complex-value')
            for slot,(url,file_id) in enumerate(zip(plan['expected_images'],plan['image_bank_ids'])):
                node=ET.SubElement(values,'field',{'id':f'scImages_{slot}','type':'input'})
                ET.SubElement(node,'value',{'fileId':file_id}).text=url.replace('https:','').replace('http:','')
            xml=ET.tostring(payload,encoding='unicode');(folder/'图库增量载荷.xml').write_text(xml,encoding='utf-8')
            sha=hashlib.sha256(xml.encode('utf-8')).hexdigest()
            save(ledger,{'id':pid,'state':'RESERVED_WRITE_OUTCOME_PENDING','reserved_at':stamp(),'payload_sha256':sha})
            response=call('alibaba.icbu.product.schema.update',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US','xml':xml}})
            save(folder/'图库更新回执.json',api.redact_tokens(response))
            state='GALLERY_SUBMITTED_PENDING_READBACK' if response.get('biz_success') is True else 'GALLERY_API_REJECTED'
            save(ledger,{'id':pid,'state':state,'submitted_at':stamp(),'payload_sha256':sha,'request_id':response.get('request_id')})
            results.append({'id':pid,'state':state});print(json.dumps(results[-1]),flush=True)
        else:
            if not (folder/'图库单次提交账本.json').exists():continue
            got=call('alibaba.icbu.product.get',{'product_id':int(pid),'language':'ENGLISH'});p=got.get('product',{})
            save(folder/'图库写后正式商品.json',got)
            before=json.loads((folder/'图库写前正式商品.json').read_text(encoding='utf-8'))['product']
            matches=list(map(key,p.get('main_image',{}).get('images',[])))==list(map(key,plan['expected_images']))
            unchanged=invariant(p)==invariant(before)
            state='GALLERY_FORMAL_VERIFIED_PUBLIC_PENDING' if matches and unchanged and p.get('status')=='approved' and p.get('display')=='Y' else 'GALLERY_PENDING_APPROVAL' if matches and unchanged and p.get('status')=='modified' else 'GALLERY_DIFFERENCE_REVIEW_REQUIRED'
            result={'id':pid,'state':state,'at':stamp(),'images_match':matches,'unrelated_fields_unchanged':unchanged,'status':p.get('status'),'display':p.get('display'),'public_qa':'PENDING'}
            save(folder/'图库字段验收.json',result);results.append(result)
            if matches and unchanged:save(AREA/'商品'/pid/'formal_get.json',{'requested_product_id':pid,'observed_at_utc':stamp(),'method':'alibaba.icbu.product.get','response':api.redact_tokens(got)})
    current=json.loads(REGISTRY.read_text(encoding='utf-8-sig'));by_id={l['id']:l for l in current['listings']}
    for result in results:
        by_id[result['id']].setdefault('optimization',{})['gallery']={**result,'evidence':[(AREA/'商品'/result['id']/'穿脱优化'/name).relative_to(ROOT).as_posix() for name in ['图库拟改字段.json','图库更新回执.json','图库字段验收.json'] if (AREA/'商品'/result['id']/'穿脱优化'/name).exists()]}
    current['bq_ease_optimization']['gallery_review']={'families':19,'planned':sum((AREA/'商品'/pid/'穿脱优化/图库拟改字段.json').exists() for pid in targets),'results':results,'scope':'原图身份逐条匹配，其他未改图库保留；审核及公开验收分别记录'}
    save(REGISTRY,current);print(json.dumps({'mode':args.mode,'results':results},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
