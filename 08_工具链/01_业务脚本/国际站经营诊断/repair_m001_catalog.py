"""Repair M001 on its original ID: reviewed imagery, copy and one omitted color.

Preserves all twelve existing SKU IDs/codes, existing price tiers and every
unsubmitted field. A write ledger prevents replay of uploads or updates.
"""

import sys as _registry_sys
from pathlib import Path as _RegistryPath
_registry_sys.path.insert(0, str(_RegistryPath(__file__).resolve().parents[3]/"08_工具链/06_工作区维护"))
from product_registry import ProductRegistry
from pathlib import Path
from xml.etree import ElementTree as E
from collections import Counter
from decimal import Decimal
import argparse,json,copy,sys,shutil
sys.path.insert(0,str(Path(__file__).parent));import revise_catalog_content as shared
ROOT=shared.ROOT;load,save,rel,now,sha=shared.load,shared.save,shared.rel,shared.now,shared.sha
import publish_hot_rank_hr_a_batch as pub
import schema_publish_contract as contract
from read_only_catalog import read_only_call
PID='1601970169467';BASE=shared.BASE/'M001';RAW=shared.RAW/PID;ASSET=ROOT/'01_产品资产/02_可发布素材/00_最终上传/BQ-M001'
FIELDS=['saleProp','sku','productTitle','textDesc','scImages','detailImage','ladderPrice','scPrice']
SIZES=['35-36','37-38','39-40','40-41','42-43','44-45']
TITLE='M001 EVA Closed Toe Slip-On Mules with Raised Footbed Nodes and Open Heel for Casual Wear Wholesale'
HIGHLIGHTS='Easy slip-on entry: The open heel lets the foot slide in from the back, while the closed toe covers the forefoot.\n\nSoft EVA upper: The moulded EVA body provides soft coverage around the foot, with ribbed sidewalls and a textured front panel.\n\nTextured underfoot feel: Individual raised footbed nodes form distinct contact points beneath the foot.'
ROLES={'M1':'M1_black.png','M2':'M2_colors.png','M3':'M4_entry.png','M4':'M3_sole.png','M5':'M5_wear.png'}
def inspect_plan():
    p=load(BASE/'事实与页面计划.json');assert p['product_id']==PID and p['reviewed']is True and p['title']==TITLE and p['highlights']==HIGHLIGHTS
    assert p['colors']==['Red','Grey','Black']and p['paired_EU']==SIZES
    for role,filename in ROLES.items():
        f=ASSET/'05_AI候选'/filename;assert f.exists()and sha(f)==p['image_review'][role]['sha256']and p['image_review'][role]['state']=='PASS'
    return p
def bank(api,cfg):
    inspect_plan();file=BASE/'图片银行.json';data=load(file)if file.exists()else{'items':{}}
    for role,filename in ROLES.items():
        f=ASSET/'05_AI候选'/filename;assert f.stat().st_size<4*1024*1024
        if role in data['items']:
            assert data['items'][role]['state']=='UPLOADED'and data['items'][role]['sha256']==sha(f),'Unknown upload: reconcile, never replay'
            continue
        data['items'][role]={'state':'UPLOAD_OUTCOME_UNKNOWN_NO_REPLAY','sha256':sha(f),'file':rel(f),'at':now()};save(file,data)
        result=api.upload_image(cfg,f,None);save(RAW/('upload_'+role+'.json'),result);r=result.get('upload_image_response',{});assert not api.api_error(result)and r.get('file_id')and r.get('photobank_url')
        url=r['photobank_url'];url='https:'+url if url.startswith('//')else url.replace('http:','https:');assert url.startswith('https://sc04.alicdn.com/')
        data['items'][role].update(state='UPLOADED',url=url,file_id=str(r['file_id']));save(file,data);print('BANK',role,'UPLOADED',flush=True)
    data['state']='COMPLETE';save(file,data)
def prepare(api,cfg):
    assert not(BASE/'update_once.json').exists();plan=inspect_plan();banks=load(BASE/'图片银行.json');assert banks['state']=='COMPLETE';banks=banks['items']
    got=read_only_call(api,cfg,'alibaba.icbu.product.get',{'product_id':PID,'language':'ENGLISH'});save(RAW/'before_get.json',got);p=got['product'];assert p['status']=='approved'and p['display']=='Y'
    assert len(p['product_sku']['skus'])==12
    rr=read_only_call(api,cfg,'alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(PID),'cat_id':int(p['category_id']),'language':'en_US'}});assert rr.get('data');save(RAW/'before_render.json',rr);current=RAW/'current_schema.xml';current.write_text(rr['data'],encoding='utf8')
    schema=E.fromstring(rr['data']);root=pub.values_only(schema,operation='update',field_ids=FIELDS)
    pub.set_direct_value(root,'productTitle',TITLE);pub.set_direct_value(root,'textDesc',HIGHLIGHTS)
    color=root.find("./field[@id='saleProp']/complex-value/field[@id='p-191288010']/values");size=root.find("./field[@id='saleProp']/complex-value/field[@id='p-222038415']/values")
    assert [x.get('inputValue')for x in color]==['Red','Grey'];sizes={x.get('inputValue'):x.text for x in size};assert set(sizes)==set(SIZES)
    black='3327837';assert schema.find("./field[@id='saleProp']/fields/field[@id='p-191288010']/options/option[@value='3327837']").get('displayName')=='Black'
    E.SubElement(color,'value',{'inputValue':'Black','img':banks['M1']['url']}).text=black
    skus=root.find("./field[@id='sku']");old=list(skus.findall('./complex-values'));assert len(old)==12
    for eu in SIZES:
        row=copy.deepcopy(old[0])
        for fid in ('skuId','outerSupplyId'):
            field=row.find("./field[@id='%s']"%fid)
            for child in list(field):field.remove(child)
        pub.set_direct_value(row,'skuOuterId','BQ-M001-BLACK-'+eu)
        values=row.find("./field[@id='props']/values");values.clear()
        for prop,label,marker in [('191288010','Black',black),('222038415',eu,sizes[eu])]:E.SubElement(values,'value',{'propValueId':marker,'propId':prop,'propName':'p-'+prop,'propValueName':label}).text=prop+':'+marker
        skus.append(row)
    assert all(E.tostring(a)==E.tostring(b)for a,b in zip(old,skus.findall('./complex-values')[:12]));contract.validate_sku_property_pairs(root)
    factory=p['main_image']['images'][5];assert 'Hea3fc4c6da4b46e0bb75c003260875120' in factory
    pub.set_main_images(root,[banks[k]for k in ('M1','M2','M3','M4','M5')]+[{'url':factory,'file_id':'0'}])
    pub.set_gallery(root,'detailImage',[banks[k]for k in ('M3','M4','M5','M2')],[(300,'Detail shot'),(300,'Detail shot'),(200,'Scene image'),(150,'Product dimensions')])
    payload=RAW/'payload.xml';payload.write_text(E.tostring(root,encoding='unicode'),encoding='utf8')
    manifest={'operation':'update','product_id':PID,'category_id':p['category_id'],'facts_reviewed':True,'source_evidence':[rel(BASE/'事实与页面计划.json'),rel(BASE/'图片银行.json')],'current_schema':'current_schema.xml','current_schema_sha256':sha(current),'schema_request_id':rr['request_id'],'schema_acquired_at':now(),'payload_xml':'payload.xml','field_ids':FIELDS,'dependency_ids':[]};save(RAW/'manifest.json',manifest);listing=pub.load_submission_manifest(RAW/'manifest.json','update',PID)
    save(BASE/'prepared.json',{'id':PID,'state':'PREPARED','at':now(),'fields':FIELDS,'old_SKUs':12,'target_SKUs':18,'title':TITLE,'highlights':HIGHLIGHTS,'old_price_tiers_preserved':True,'old_sku_rows_preserved':True,'payload_sha256':sha(payload),'source_evidence':manifest['source_evidence'],'raw_evidence':rel(RAW)})
    print('M001_PREPARED_18_SKUS_ORIGINAL_ID',flush=True)
def submit(api,cfg):
    ledger=BASE/'update_once.json';assert not ledger.exists(),'Existing attempt: read only'
    plan=inspect_plan();prepared=load(BASE/'prepared.json');assert prepared['payload_sha256']==sha(RAW/'payload.xml');listing=pub.load_submission_manifest(RAW/'manifest.json','update',PID)
    got=read_only_call(api,cfg,'alibaba.icbu.product.get',{'product_id':PID,'language':'ENGLISH'});save(RAW/'immediate_prewrite_get.json',got);assert got['product']==load(RAW/'before_get.json')['product'],'Current changed: prepare again without write'
    with ledger.open('x',encoding='utf8')as f:json.dump({'id':PID,'at':now(),'state':'WRITE_OUTCOME_UNKNOWN_NO_REPLAY'},f)
    receipt=pub.api_submit(api,cfg,listing,False,update_product_id=PID);save(RAW/'update_receipt.json',receipt);save(BASE/'update_receipt.json',shared.sanitized(receipt));save(ledger,{'id':PID,'at':receipt['attempted_at'],'state':receipt['status'],'refs':receipt.get('refs')});print('M001',receipt['status'],flush=True)
def verify(api,cfg):
    assert(BASE/'update_once.json').exists();before=load(RAW/'before_get.json')['product'];got=read_only_call(api,cfg,'alibaba.icbu.product.get',{'product_id':PID,'language':'ENGLISH'});save(RAW/'after_get.json',got);p=got['product'];banks=load(BASE/'图片银行.json')['items'];report={'id':PID,'at':now(),'state':'REVIEW_PENDING','status':p['status'],'display':p['display'],'score':None,'public_status':'NOT_PER_ID_VISUALLY_RETESTED_API_POLICY'}
    axes={str(x['attribute_id']):{str(v['value_id']):v['system_value_name']for v in x['values']}for x in p['product_sku']['sku_attributes']};pairs=Counter();bindings={};tiers=[]
    for r in p['product_sku']['skus']:
        a=json.loads(r['attr2_value']);pairs[(axes['191288010'][str(a['191288010'])],axes['222038415'][str(a['222038415'])])]+=1;bindings[r['sku_code']]=str(r['sku_id']);tiers.append(r.get('bulk_discount_prices'))
    checks={'title':p['subject']==TITLE,'highlights':p['struct_detail']['product_summary']==HIGHLIGHTS,'exact_18_pairs':pairs==Counter((c,s)for c in ('Red','Grey','Black')for s in SIZES),'unique_sku_ids':len(bindings)==18 and len(set(bindings.values()))==18 and '0'not in bindings.values(),'original_12_ids_codes':all(bindings.get(r['sku_code'])==str(r['sku_id'])for r in before['product_sku']['skus']),'all_tiers_preserved':all(t==before['product_sku']['skus'][0].get('bulk_discount_prices')for t in tiers),'general_faq':p['struct_detail'].get('product_faq')==before['struct_detail'].get('product_faq'),'company':{k:v for k,v in p['struct_detail'].items()if k not in ('product_summary','detail_image')}=={k:v for k,v in before['struct_detail'].items()if k not in ('product_summary','detail_image')},'attributes':p['attributes']==before['attributes'],'trade':p['sourcing_trade']==before['sourcing_trade'],'main_image_count':len(p['main_image']['images'])==6,'detail_count':len(p['struct_detail']['detail_image']['images'])==4}
    excluded={'subject','main_image','product_sku','struct_detail','pc_detail_url','gmt_modified','status','display'};checks['other_product_fields']=all(p.get(k)==v for k,v in before.items()if k not in excluded)
    if p['status']=='approved':
        checks['display']=p['display']==before['display'];rr=read_only_call(api,cfg,'alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(PID),'cat_id':int(p['category_id']),'language':'en_US'}});save(RAW/'after_render.json',rr)
        if rr.get('data'):
            current=contract.field_snapshot(E.fromstring(rr['data']));wanted=contract.field_snapshot(E.parse(RAW/'payload.xml').getroot());old=contract.field_snapshot(E.fromstring(load(RAW/'before_render.json')['data']));checks['target_schema']=all(contract.created_field_equivalent(k,v,current.get(k))for k,v in wanted.items()if k!='sku');checks['other_schema']=all(contract.created_field_equivalent(k,v,current.get(k))for k,v in old.items()if k not in wanted)
        else:checks['target_schema']=False
        enc=api.top_call(cfg,'alibaba.icbu.product.id.encrypt',{'product_id':PID,'language':'ENGLISH'});assert enc.get('secret_id');score=read_only_call(api,cfg,'alibaba.icbu.product.score.get',{'product_id':enc['secret_id']});save(RAW/'score.json',score);report['score']=score.get('result',{}).get('final_score');checks['score']=report['score']is not None and Decimal(str(report['score']))>=5
        report['state']='FORMAL_FIELDS_SCORE_PASS'if all(v is True for v in checks.values())else'FORMAL_DIFFERENCE_DIAGNOSE_NO_REPLAY'
    report.update(checks=checks,failed=[k for k,v in checks.items()if v is False],sku_count=len(bindings),colors=sorted(axes['191288010'].values()),sku_bindings=bindings);save(BASE/'verification.json',report);print(json.dumps({k:report[k]for k in ('id','state','score','failed','sku_count')},ensure_ascii=False),flush=True)
def sync(api=None,cfg=None):
    from PIL import Image
    report=load(BASE/'verification.json');assert report['state']=='FORMAL_FIELDS_SCORE_PASS';plan=inspect_plan();got=load(RAW/'after_get.json');p=got['product'];file=ProductRegistry(ROOT);data=load(file);listing=next(x for x in data['listings']if x['id']==PID);product=next(x for x in data['products']if x['id']==listing['product_id']);source=next(x for x in data['sources']if x['id']==plan['source_id'])
    canonical=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'/PID
    save(canonical/'formal_get.json',{'requested_product_id':PID,'observed_at_utc':report['at'],'method':'alibaba.icbu.product.get','response':shared.sanitized(got),'sanitized_fields':['owner_member','owner_member_display_name','owner_member_id'],'raw_response_file':rel(RAW/'after_get.json')});save(canonical/'formal_render.json',shared.sanitized(load(RAW/'after_render.json')))
    refs=[rel(BASE/n)for n in ('事实与页面计划.json','图片银行.json','prepared.json','update_receipt.json','verification.json')]
    phase={'at':report['at'],'state':report['state'],'scope':'M001 originalID title/highlights, five product gallery assets, four product details and Black six paired-EU combinations; original12SKU IDs/codes/prices and generalFAQ/company preserved.','next_action':'M001 completed by formal API. Do not replay; continue other source colour gaps and image remakes.','evidence':refs}
    listing.setdefault('optimization',{})['content_quality_revision']=phase;product['content_quality_revision']=copy.deepcopy(phase)
    for obj in (listing,product):
        obj.setdefault('evidence',[])
        for r in refs:
            if r not in obj['evidence']:obj['evidence'].append(r)
    listing['formal_fields']={'file':rel(canonical/'formal_get.json'),'at':report['at'],'scope':phase['scope']};listing.setdefault('current_platform_fields',{}).update(at=report['at'],title=p['subject'],highlights=p['struct_detail']['product_summary'],status=p['status'],display=p['display'],category_id=p['category_id'],main_images=p['main_image']['images'],sku_count=18,colour_EU={c:SIZES for c in ('Red','Grey','Black')});listing.setdefault('catalog_fields',{}).update(listing['current_platform_fields']);listing.setdefault('observation',{}).update(at=report['at'],audit=p['status'],display=p['display'],score=report['score'],sku_count=18);listing.setdefault('local_sync',{}).update(state=report['state'],current_fields_file=rel(canonical/'formal_get.json'),current_schema_file=rel(canonical/'formal_render.json'),current_family_plan=rel(BASE/'事实与页面计划.json'),content_verification=rel(BASE/'verification.json'),observed_at=report['at'])
    product['next_action']='M001原ID三色18个并码SKU、标题、功能亮点及全组图片已正式核验5.0；继续其他问题款，不重复提交。';product.setdefault('local_assets',{}).update(current_fields_file=rel(BASE/'事实与页面计划.json'),asset_roots=[rel(ASSET)],state='CURRENT_SOURCE_AND_PLATFORM_VERIFIED');product['raw_packages']=list(dict.fromkeys(product.get('raw_packages',[])+[rel(ASSET/'01_来源原图')]));product['local_assets'].setdefault('current_gallery_by_id',{})[PID]=rel(BASE/'当前图库与货号.json')
    source.update(observed_at=plan['observed_at'],colors=['Red','Grey','Black'],paired_EU=SIZES,current_assortment={'state':'SOURCE_THREE_COLORS_PLATFORM18EU_VERIFIED','evidence':rel(BASE/'verification.json'),'source_evidence':rel(BASE/'事实与页面计划.json'),'inventory':'Not physical stock proof; availability per order'})
    source.setdefault('evidence',[])
    if rel(BASE/'事实与页面计划.json')not in source['evidence']:source['evidence'].append(rel(BASE/'事实与页面计划.json'))
    save(BASE/'当前图库与货号.json',{'id':PID,'at':report['at'],'model':'BQ-M001','main_images':p['main_image']['images'],'detail_images':p['struct_detail']['detail_image']['images'],'SKU':{'Red':SIZES,'Grey':SIZES,'Black':SIZES},'source':source['url'],'verification':rel(BASE/'verification.json'),'image_reviews':rel(BASE/'事实与页面计划.json')})
    cachefile=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前素材清单.json';cache=load(cachefile);banks=load(BASE/'图片银行.json')['items']
    for role,row in banks.items():
        f=ROOT/row['file'];im=Image.open(f);cache.setdefault('assets',{})[row['url']]={'state':'SAVED','file':row['file'],'sha256':sha(f),'width':im.width,'height':im.height,'at':report['at'],'origin':'SOURCE_ANCHORED_AI_ENHANCEMENT_VISUALLY_REVIEWED','source_review':rel(BASE/'事实与页面计划.json')}
    cache.setdefault('products',{}).setdefault(PID,{})['current_content_revision']={'at':report['at'],'verification':rel(BASE/'verification.json'),'images':{k:v['url']for k,v in banks.items()}};save(cachefile,cache)
    data['updated_on']=report['at'][:10];data.setdefault('content_quality_revision',{}).update(at=report['at'],entry=rel(shared.ENTRY));save(file,data)
    sys.path.insert(0,str(ROOT/'08_工具链/06_工作区维护'));import build_product_workspace as workspace
    errors=workspace.validate(data,ROOT);assert not errors,errors
    for path,body in workspace.build(data).items():workspace.write_generated(ROOT/path,body)
    print('M001_SOURCE_REGISTRY_DOSSIER_MEDIA_SYNCHRONIZED',flush=True)
if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf8');p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['bank','prepare','submit','verify','sync']);a=p.parse_args();api,cfg=shared.client()if a.mode!='sync'else(None,None);globals()[a.mode](api,cfg)
