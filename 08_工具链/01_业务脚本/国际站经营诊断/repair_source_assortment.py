"""Apply exact reviewed colour/range corrections without changing existing SKU identity.

Plan, uploads and each original product update have independent once ledgers.
Only current sale properties, SKU rows and their price dependencies are submitted.
"""
from pathlib import Path
from xml.etree import ElementTree as E
from collections import Counter
from decimal import Decimal
import argparse,copy,json,sys
sys.path.insert(0,str(Path(__file__).parent));import revise_catalog_content as s
import publish_hot_rank_hr_a_batch as pub
import schema_publish_contract as contract
from read_only_catalog import read_only_call
ROOT=s.ROOT;BASE=s.BASE/'配色与尺码修正';RAW=s.RAW/'配色与尺码修正'
load,save,rel,sha,now=s.load,s.save,s.rel,s.sha,s.now
FIELDS=['saleProp','sku','ladderPrice','scPrice']

def axes(p):
    return {str(a['attribute_id']):{str(v['value_id']):v['system_value_name']for v in a['values']}for a in p['product_sku']['sku_attributes']}

def key(row,ax):
    v=json.loads(row['attr2_value']);return tuple(ax[k][str(v[k])].replace('Size ','')for k in ('191288010','222038415'))

def protected_formal(p):
    out={k:copy.deepcopy(v)for k,v in p.items()if k not in ('product_sku','gmt_modified','status','display')}
    out['attributes']=sorted(out.get('attributes',[]),key=lambda row:json.dumps(row,sort_keys=True))
    return out

def main():
    sys.stdout.reconfigure(encoding='utf8');ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['bank','prepare','submit','verify','sync']);ap.add_argument('--family',required=True);ap.add_argument('--ids');a=ap.parse_args()
    folder=BASE/a.family;plan=load(folder/'计划.json');assert plan['reviewed']is True and plan['reviewer']=='active_agent';assert all((ROOT/f).exists()for f in plan['source_evidence'])
    if a.ids:
        ids=a.ids.split(',');assert len(ids)==len(set(ids))and set(ids)<=set(plan['ids']);plan={**plan,'ids':ids}
    api,cfg=s.client()if a.mode!='sync'else(None,None)
    def read(m,p):return read_only_call(api,cfg,m,p)
    def get(pid):return read('alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'})
    def render(pid,p):return read('alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US'}})
    if a.mode=='bank':
        bankfile=folder/'图片银行.json';banks=load(bankfile)if bankfile.exists()else{'items':{}}
        for c,item in {**plan.get('add',{}),**plan.get('image_assets',{})}.items():
            f=ROOT/item['file'];assert sha(f)==item['sha256']and item['image_review']=='PASS'and f.stat().st_size<4*1024*1024
            if c in banks['items']:
                assert banks['items'][c]['state']=='UPLOADED'and banks['items'][c]['sha256']==sha(f);continue
            banks['items'][c]={'state':'UPLOAD_UNKNOWN_NO_REPLAY','sha256':sha(f),'file':rel(f),'at':now()};save(bankfile,banks)
            result=api.upload_image(cfg,f,None);save(RAW/a.family/('upload_'+c.replace(' ','')+'.json'),result);r=result.get('upload_image_response',{});assert not api.api_error(result)and r.get('file_id')and r.get('photobank_url')
            url=r['photobank_url'];url='https:'+url if url.startswith('//')else url.replace('http:','https:');assert url.startswith('https://sc04.alicdn.com/')
            banks['items'][c].update(state='UPLOADED',url=url,file_id=str(r['file_id']));save(bankfile,banks);print('BANK',a.family,c,'UPLOADED',flush=True)
        banks['state']='COMPLETE';save(bankfile,banks)
        if plan.get('rebind_image_roles'):
            assert not any((folder/'商品'/pid/'update_once.json').exists()for pid in plan['ids'])
            plan['rebind_images']={label:banks['items'][role]['url']for label,role in plan['rebind_image_roles'].items()};save(folder/'计划.json',plan)
        return
    if a.mode=='sync':return sync(plan,folder)
    for pid in plan['ids']:
        assert pid not in s.PROTECTED;public=folder/'商品'/pid;raw=RAW/a.family/pid;ledger=public/'update_once.json'
        if a.mode=='prepare':
            assert not ledger.exists(),'Existing attempt: read only'
            got=get(pid);save(raw/'before_get.json',got);p=got['product'];assert p['status']=='approved'and p['display']=='Y';rr=render(pid,p);assert rr.get('data');save(raw/'before_render.json',rr)
            current=raw/'current_schema.xml';current.write_text(rr['data'],encoding='utf8');schema=E.fromstring(rr['data']);rebind_only=bool(plan.get('rebind_images'))and not plan.get('add')and not plan.get('restrict');fields=['saleProp']if rebind_only else FIELDS;out=pub.values_only(schema,operation='update',field_ids=fields)
            colours=out.find("./field[@id='saleProp']/complex-value/field[@id='p-191288010']/values");sizes=out.find("./field[@id='saleProp']/complex-value/field[@id='p-222038415']/values")
            cm={v.text:v.get('inputValue')for v in colours};sm={v.text:v.get('inputValue')for v in sizes};sizeids={v.get('inputValue').replace('Size ',''):v.text for v in sizes};skus=out.find("./field[@id='sku']");original=list(skus.findall('./complex-values'))if skus is not None else[];removed=[]
            for value in colours:
                label=value.get('inputValue')
                if label in plan.get('rebind_images',{}):
                    assert contract._created_image_identity(value.get('img'))==contract._created_image_identity(plan['expected_images_by_id'][pid][label]),'Current colour image differs from reviewed original'
                    value.set('img',plan['rebind_images'][label])
            for row in original:
                vals={v.get('propId'):v.get('propValueId')for v in row.findall("./field[@id='props']/values/value")};c=cm[vals['191288010']];eu=sm[vals['222038415']].replace('Size ','')
                if c in plan.get('restrict',{})and eu not in plan['restrict'][c]:
                    removed.append(row.findtext("./field[@id='skuId']/value"));skus.remove(row)
            kept=list(skus.findall('./complex-values'))if skus is not None else[];assert kept or rebind_only
            bank=load(folder/'图片银行.json')['items']if plan.get('add')else{}
            for index,(c,item)in enumerate(plan.get('add',{}).items()):
                assert c not in cm.values()and bank[c]['state']=='UPLOADED';marker=str(-1001-index);assert marker not in cm
                E.SubElement(colours,'value',{'inputValue':c,'img':bank[c]['url']}).text=marker
                for eu in item['EU']:
                    row=copy.deepcopy(kept[0])
                    for fid in ('skuId','outerSupplyId'):
                        f=row.find("./field[@id='%s']"%fid)
                        for ch in list(f):f.remove(ch)
                    # Existing SKU stock remains untouched. A source colour
                    # label does not supply a quantity for a newly added SKU.
                    stock=row.find("./field[@id='skuStock']")
                    if stock is not None:
                        for ch in list(stock):stock.remove(ch)
                    pub.set_direct_value(row,'skuOuterId',a.family+'-'+pid[-5:]+'-'+c.upper().replace(' ','')+'-'+eu)
                    values=row.find("./field[@id='props']/values");values.clear()
                    for prop,label,v in [('191288010',c,marker),('222038415',sm[sizeids[eu]],sizeids[eu])]:E.SubElement(values,'value',{'propValueId':v,'propId':prop,'propName':'p-'+prop,'propValueName':label}).text=prop+':'+v
                    skus.append(row)
            contract.validate_sku_property_pairs(out);payload=raw/'payload.xml';payload.write_text(E.tostring(out,encoding='unicode'),encoding='utf8')
            manifest={'operation':'update','product_id':pid,'category_id':p['category_id'],'facts_reviewed':True,'source_evidence':plan['source_evidence']+[rel(folder/'计划.json')],'current_schema':'current_schema.xml','current_schema_sha256':sha(current),'schema_request_id':rr['request_id'],'schema_acquired_at':now(),'payload_xml':'payload.xml','field_ids':fields,'dependency_ids':[]}
            if removed:manifest['reviewed_sku_removals']={'ids':removed,'reason':'Exact source restricts Lavender to EU35-40; remove unsupported EU41-45 only.','source_evidence':plan['source_evidence']}
            save(raw/'manifest.json',manifest);pub.load_submission_manifest(raw/'manifest.json','update',pid)
            ax=axes(p);expected=[key(row,ax)for row in p['product_sku']['skus']if str(row['sku_id'])not in removed]+[(c,eu)for c,item in plan.get('add',{}).items()for eu in item['EU']]
            save(public/'prepared.json',{'id':pid,'at':now(),'fields':fields,'before_sku_count':len(p['product_sku']['skus']),'expected_pairs':expected,'removed_unsupported_ids':removed,'payload_sha256':sha(payload),'source_evidence':manifest['source_evidence']});print('PREPARED',pid,len(expected),flush=True)
        elif a.mode=='submit':
            assert not ledger.exists(),'Existing attempt: reconcile by reads';prepared=load(public/'prepared.json');assert prepared['payload_sha256']==sha(raw/'payload.xml');listing=pub.load_submission_manifest(raw/'manifest.json','update',pid)
            got=get(pid);save(raw/'immediate_prewrite_get.json',got);assert got['product']==load(raw/'before_get.json')['product'],'Current changed, no write'
            with ledger.open('x',encoding='utf8')as f:json.dump({'id':pid,'at':now(),'state':'WRITE_UNKNOWN_NO_REPLAY'},f)
            receipt=pub.api_submit(api,cfg,listing,False,update_product_id=pid);save(raw/'update_receipt.json',receipt);save(public/'update_receipt.json',s.sanitized(receipt));save(ledger,{'id':pid,'at':receipt['attempted_at'],'state':receipt['status'],'refs':receipt.get('refs')});print(pid,receipt['status'],flush=True)
        else:
            assert ledger.exists();before=load(raw/'before_get.json')['product'];prepared=load(public/'prepared.json');got=get(pid);save(raw/'after_get.json',got);p=got['product'];ax=axes(p);pairs=Counter(key(r,ax)for r in p['product_sku']['skus']);original={str(r['sku_id']):r for r in before['product_sku']['skus']if str(r['sku_id'])not in prepared['removed_unsupported_ids']};actual={str(r['sku_id']):r for r in p['product_sku']['skus']}
            checks={'exact_colour_EU':pairs==Counter(tuple(x)for x in prepared['expected_pairs']),'retained_sku_identity':all(actual.get(i)==r for i,r in original.items()),'removed_unsupported':not set(prepared['removed_unsupported_ids'])&set(actual),'unique_real_sku_ids':len(actual)==len(p['product_sku']['skus'])and '0'not in actual,'all_price_tiers_preserved':all(r.get('bulk_discount_prices')==before['product_sku']['skus'][0].get('bulk_discount_prices')for r in actual.values()),'other_formal_fields':protected_formal(p)==protected_formal(before)}
            if plan.get('rebind_images'):
                colour_images={v['system_value_name']:v.get('image_url')for axis in p['product_sku']['sku_attributes']if str(axis['attribute_id'])=='191288010'for v in axis['values']};checks['colour_image_bindings']=all(contract._created_image_identity(colour_images.get(label))==contract._created_image_identity(url)for label,url in plan['rebind_images'].items())
            report={'id':pid,'at':now(),'state':'REVIEW_PENDING','status':p['status'],'display':p['display'],'checks':checks,'score':None,'public_status':'API_ACCEPTANCE_NO_BROWSER_PER_USER'}
            if p['status']=='approved':
                checks['display']=p['display']==before['display'];rr=render(pid,p);save(raw/'after_render.json',rr)
                if rr.get('data'):
                    cur=contract.field_snapshot(E.fromstring(rr['data']));wanted=contract.field_snapshot(E.parse(raw/'payload.xml').getroot());old=contract.field_snapshot(E.fromstring(load(raw/'before_render.json')['data']));checks['schema_targets']=all(contract.created_field_equivalent(k,v,cur.get(k))for k,v in wanted.items()if k!='sku');checks['other_schema']=all(contract.created_field_equivalent(k,v,cur.get(k))for k,v in old.items()if k not in wanted)
                else:checks['schema_targets']=False
                enc=read('alibaba.icbu.product.id.encrypt',{'product_id':pid,'language':'ENGLISH'});score=read('alibaba.icbu.product.score.get',{'product_id':enc['secret_id']});save(raw/'score.json',score);report['score']=score.get('result',{}).get('final_score');diag=score.get('result',{}).get('problem_map')or{};diag=json.loads(diag)if isinstance(diag,str)else diag;report['diagnostics']=diag;checks['score']=report['score']is not None and Decimal(str(report['score']))>=5 and not diag.get('errorReasonList')and not any((diag.get('extendProblemMap')or{}).values());report['state']='FORMAL_FIELDS_SCORE_PASS'if all(v is True for v in checks.values())else'FORMAL_DIFFERENCE_DIAGNOSE_NO_REPLAY'
            report.update(failed=[k for k,v in checks.items()if v is False],pairs=[list(k)for k in pairs],sku_count=sum(pairs.values()));save(public/'verification.json',report);print(json.dumps({k:report[k]for k in ('id','state','score','failed','sku_count')},ensure_ascii=False),flush=True)

def sync(plan,folder):
    file=ROOT/'02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json';data=load(file)
    for pid in plan['ids']:
        public=folder/'商品'/pid;report=load(public/'verification.json');assert report['status']=='approved'and all(v is True for k,v in report['checks'].items()if k!='score'),'Only proved formal fields can sync; score pending stays explicit';raw=RAW/plan.get('execution_key',plan['family'])/pid;got=load(raw/'after_get.json');p=got['product'];listing=next(x for x in data['listings']if x['id']==pid);product=next(x for x in data['products']if x['id']==listing['product_id']);canonical=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'/pid
        if listing.get('formal_fields',{}).get('at','')>report['at']:continue
        save(canonical/'formal_get.json',{'requested_product_id':pid,'observed_at_utc':report['at'],'method':'alibaba.icbu.product.get','response':s.sanitized(got),'sanitized_fields':['owner_member','owner_member_display_name','owner_member_id'],'raw_response_file':rel(raw/'after_get.json')});save(canonical/'formal_render.json',s.sanitized(load(raw/'after_render.json')))
        refs=[rel(folder/'计划.json')]+[rel(public/n)for n in ('prepared.json','update_receipt.json','verification.json')];phase={'at':report['at'],'state':report['state'],'scope':'Exact source colour/EU matrix; retained SKU IDs/codes/prices and all unrelated product fields verified.','evidence':refs};listing.setdefault('optimization',{})['source_assortment_revision']=phase;product['source_assortment_revision']=phase
        for obj in (listing,product):obj['evidence']=list(dict.fromkeys(obj.get('evidence',[])+refs))
        listing['formal_fields']={'file':rel(canonical/'formal_get.json'),'at':report['at'],'scope':phase['scope']};listing.setdefault('current_platform_fields',{}).update(at=report['at'],sku_count=report['sku_count'],colour_EU={c:sorted(eu for cc,eu in report['pairs']if cc==c)for c in set(c for c,eu in report['pairs'])});listing.setdefault('catalog_fields',{}).update(listing['current_platform_fields']);listing.setdefault('observation',{}).update(at=report['at'],score=report['score'],audit=p['status'],display=p['display'],sku_count=report['sku_count']);listing.setdefault('local_sync',{}).update(state=report['state'],observed_at=report['at'],current_fields_file=rel(canonical/'formal_get.json'),assortment_verification=rel(public/'verification.json'));product.setdefault('local_assets',{})['current_assortment']=rel(folder/'计划.json')
        source=next((x for x in data['sources']if x['id']==plan.get('source_id')),None)
        if source is not None:source['current_assortment']={'at':report['at'],'state':'EXACT_COLOR_EU_VERIFIED'if report['state']=='FORMAL_FIELDS_SCORE_PASS'else'FORMAL_COLOR_EU_VERIFIED_SCORE_PENDING','score':report['score'],'matrix':listing['current_platform_fields']['colour_EU'],'evidence':refs,'remaining_source_options':plan.get('unmapped_options',[]),'inventory':'Source options are not physical stock proof; newly added variants may have default zero until a quantity is supplied'}
        if plan.get('rebind_images'):
            product.setdefault('local_assets',{})['current_colour_binding_revision']=rel(folder/'计划.json')
    save(file,data);sys.path.insert(0,str(ROOT/'08_工具链/06_工作区维护'));import build_product_workspace as workspace
    errors=workspace.validate(data,ROOT);assert not errors,errors
    for path,body in workspace.build(data).items():workspace.write_generated(ROOT/path,body)
    print('SOURCE_REGISTRY_AND_LOCAL_ASSORTMENT_SYNCHRONIZED',plan['family'],flush=True)

if __name__=='__main__':main()
