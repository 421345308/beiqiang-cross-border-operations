"""Upload and bind an exact reviewed gallery plan on existing original IDs."""

import sys as _registry_sys
from pathlib import Path as _RegistryPath
_registry_sys.path.insert(0, str(_RegistryPath(__file__).resolve().parents[3]/"08_工具链/06_工作区维护"))
from product_registry import ProductRegistry
from pathlib import Path
from xml.etree import ElementTree as E
from decimal import Decimal
import json,argparse,sys,copy
sys.path.insert(0,str(Path(__file__).parent));import revise_catalog_content as s
import publish_hot_rank_hr_a_batch as pub
import schema_publish_contract as c
from read_only_catalog import read_only_call
ROOT=s.ROOT;BASE=s.BASE/'图库重做';RAW=s.RAW/'图库重做'
load,save,now,rel,sha=s.load,s.save,s.now,s.rel,s.sha

def canonical_detail_url(value,originals):
    url='https:'+value if value.startswith('//')else value
    matches=[original for original in originals if url in (original,original+'_350x350.jpg',original+'_350x350.png')]
    assert len(matches)==1,'Unrecognized or ambiguous detail identity'
    return matches[0]

def remove_reviewed_detail_images(payload,canonical,deletions):
    assert len(deletions)==len(set(deletions))
    assert len(canonical)-len(deletions)>=4,'Reviewed product details must retain at least four useful images'
    values=payload.findall("./field[@id='detailImage']//field[@id='imageURL']/value")
    assert len(values)==len(canonical)
    for url in deletions:
        assert canonical.count(url)==1,'Removal identity missing or ambiguous'
        index=canonical.index(url);node=values[index];parents={child:parent for parent in payload.iter()for child in parent}
        field=parents[node];row=parents[field];images=parents[row]
        assert field.get('id')=='imageURL'and row.tag=='complex-values'and images.get('id')=='images'
        images.remove(row)
        if not images.findall('./complex-values'):
            group=parents[images];assert group.tag=='complex-values';parents[group].remove(group)
        canonical.pop(index);values.pop(index)
    return canonical

def protected(p,change_main=True,change_detail=True):
    out=copy.deepcopy(p)
    for k in ('gmt_modified','status','display'):out.pop(k,None)
    if change_main:out.pop('main_image',None)
    if change_detail:out['struct_detail'].pop('detail_image',None)
    out['attributes']=sorted(out.get('attributes',[]),key=lambda row:json.dumps(row,sort_keys=True))
    return out

def main():
    sys.stdout.reconfigure(encoding='utf8');ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['bank','prepare','submit','verify','sync']);ap.add_argument('--family',required=True);ap.add_argument('--ids');a=ap.parse_args();folder=BASE/a.family;plan=load(folder/'计划.json');assert plan['reviewed']is True and plan['reviewer']=='active_agent';slot_only=plan.get('kind')=='detail_slot'
    if a.ids:
        ids=a.ids.split(',');assert len(ids)==len(set(ids))and set(ids)<=set(plan['ids']);plan={**plan,'ids':ids}
    mixed_slots=plan.get('kind')=='mixed_slots';main_slot=plan.get('kind')=='main_slot';main_only=plan.get('kind')=='main_only'or main_slot
    if not(slot_only or main_slot or mixed_slots):assert len(plan['gallery_roles'])==5 and(main_only or len(plan['detail_roles'])==4)
    for role,row in plan['assets'].items():assert row['state']=='PASS'and sha(ROOT/row['file'])==row['sha256']
    api,cfg=s.client()if a.mode!='sync'else(None,None)
    def read(m,p):return read_only_call(api,cfg,m,p)
    def get(pid):return read('alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'})
    def render(pid,p):return read('alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US'}})
    if a.mode=='bank':
        bankfile=folder/'图片银行.json';bank=load(bankfile)if bankfile.exists()else{'items':{}}
        for role,row in plan['assets'].items():
            f=ROOT/row['file'];assert f.stat().st_size<4*1024*1024
            if role in bank['items']:assert bank['items'][role]['state']=='UPLOADED'and bank['items'][role]['sha256']==sha(f);continue
            bank['items'][role]={'state':'UPLOAD_UNKNOWN_NO_REPLAY','file':row['file'],'sha256':sha(f),'at':now()};save(bankfile,bank)
            result=api.upload_image(cfg,f,None);save(RAW/a.family/('upload_'+role+'.json'),result);r=result.get('upload_image_response',{});assert not api.api_error(result)and r.get('file_id')and r.get('photobank_url');u=r['photobank_url'];u='https:'+u if u.startswith('//')else u.replace('http:','https:');assert u.startswith('https://sc04.alicdn.com/');bank['items'][role].update(state='UPLOADED',url=u,file_id=str(r['file_id']));save(bankfile,bank);print('UPLOADED',role,flush=True)
        bank['state']='COMPLETE';save(bankfile,bank);return
    if a.mode=='sync':return sync(plan,folder)
    banks=load(folder/'图片银行.json');assert banks['state']=='COMPLETE';banks=banks['items']
    for pid in plan['ids']:
        assert pid not in s.PROTECTED;public=folder/'商品'/pid;raw=RAW/a.family/pid;ledger=public/'update_once.json'
        if a.mode=='prepare':
            assert not ledger.exists();got=get(pid);p=got['product'];assert p['status']=='approved'and p['display']=='Y';save(raw/'before_get.json',got);rr=render(pid,p);assert rr.get('data');save(raw/'before_render.json',rr);schema=raw/'current_schema.xml';schema.write_text(rr['data'],encoding='utf8');fields=['detailImage']if slot_only else['scImages']if main_only else['scImages','detailImage'];payload=pub.values_only(E.fromstring(rr['data']),operation='update',field_ids=fields)
            expected_main=p['main_image']['images'];expected_detail=[r['image_url']for r in p['struct_detail']['detail_image']['images']]
            if slot_only or mixed_slots:
                values=payload.findall("./field[@id='detailImage']//field[@id='imageURL']/value")
                # Current render returns the observed CDN thumbnail suffix;
                # bind it against each exact original URL, never a loose match.
                assert len(values)==len(expected_detail)
                canonical=[]
                for value in values:
                    original=canonical_detail_url(value.text,expected_detail)
                    canonical.append(original);value.text=original.replace('https:','')
                assert sorted(canonical)==sorted(expected_detail)and expected_detail==plan['expected_old_by_id'][pid],'Unexpected current detail set'
                detail_replacements=plan['detail_replacements_by_id'][pid]if plan.get('detail_replacements_by_id')else plan['detail_replacements_by_url']
                for old_url,role in detail_replacements.items():
                    assert canonical.count(old_url)==1;index=canonical.index(old_url);values[index].text=banks[role]['url'].replace('https:','');canonical[index]=banks[role]['url']
                deletions=plan.get('detail_deletions_by_id',{}).get(pid,[])
                assert not set(deletions)&set(detail_replacements),'A picture cannot be both replaced and removed'
                if deletions:canonical=remove_reviewed_detail_images(payload,canonical,deletions)
                expected_detail=canonical
            if main_slot or mixed_slots:
                values=payload.findall("./field[@id='scImages']/complex-value/field/value");assert len(values)==len(expected_main)
                replacements=plan['main_replacements_by_id'][pid]if plan.get('main_replacements_by_id')else plan['main_replacements_by_url']
                for old_url,role in replacements.items():
                    identity=c._created_image_identity(old_url);indexes=[i for i,u in enumerate(expected_main)if c._created_image_identity(u)==identity];nodes=[v for v in values if c._created_image_identity(v.text)==identity];assert len(indexes)==len(nodes)==1,'Main image identity is missing or ambiguous';value=nodes[0];value.text=banks[role]['url'].replace('https:','');value.set('fileId',banks[role]['file_id']);value.set('fileFlag','no');expected_main[indexes[0]]=banks[role]['url']
            elif not slot_only:
                assert len(p['main_image']['images'])==6 and p['main_image']['images'][-1]==plan['factory_url'],'Gallery reviewed with factory at final slot; do not overwrite blindly'
                expected_main=[banks[r]['url']for r in plan['gallery_roles']]+[plan['factory_url']];pub.set_main_images(payload,[banks[r]for r in plan['gallery_roles']]+[{'url':plan['factory_url'],'file_id':'0'}])
                if not main_only:
                    expected_detail=[banks[r]['url']for r in plan['detail_roles']];pub.set_gallery(payload,'detailImage',[banks[r]for r in plan['detail_roles']],[(150,'Product dimensions'),(300,'Detail shot'),(300,'Detail shot'),(200,'Scene image')])
            out=raw/'payload.xml';out.write_text(E.tostring(payload,encoding='unicode'),encoding='utf8');manifest={'operation':'update','product_id':pid,'category_id':p['category_id'],'facts_reviewed':True,'source_evidence':plan['source_evidence']+[rel(folder/'计划.json'),rel(folder/'图片银行.json')],'current_schema':'current_schema.xml','current_schema_sha256':sha(schema),'schema_request_id':rr['request_id'],'schema_acquired_at':now(),'payload_xml':'payload.xml','field_ids':fields,'dependency_ids':[]};save(raw/'manifest.json',manifest);pub.load_submission_manifest(raw/'manifest.json','update',pid);save(public/'prepared.json',{'id':pid,'at':now(),'fields':fields,'payload_sha256':sha(out),'expected_main':expected_main,'expected_detail':expected_detail,'source_evidence':manifest['source_evidence']});print('PREPARED',pid,flush=True)
        elif a.mode=='submit':
            assert not ledger.exists();prepared=load(public/'prepared.json');assert prepared['payload_sha256']==sha(raw/'payload.xml');listing=pub.load_submission_manifest(raw/'manifest.json','update',pid);got=get(pid);save(raw/'immediate_prewrite_get.json',got);assert got['product']==load(raw/'before_get.json')['product'],'Current changed: no write'
            with ledger.open('x',encoding='utf8')as f:json.dump({'id':pid,'at':now(),'state':'WRITE_UNKNOWN_NO_REPLAY'},f)
            receipt=pub.api_submit(api,cfg,listing,False,update_product_id=pid);save(raw/'update_receipt.json',receipt);save(public/'update_receipt.json',s.sanitized(receipt));save(ledger,{'id':pid,'at':receipt['attempted_at'],'state':receipt['status'],'refs':receipt.get('refs')});print(pid,receipt['status'],flush=True)
        else:
            assert ledger.exists();got=get(pid);save(raw/'after_get.json',got);p=got['product'];old=load(raw/'before_get.json')['product'];expected=load(public/'prepared.json');keys=lambda urls:[c._created_image_identity(u)for u in urls];detail_actual=keys([r['image_url']for r in p['struct_detail']['detail_image']['images']]);detail_expected=keys(expected['expected_detail']);checks={'gallery_urls':keys(p['main_image']['images'])==keys(expected['expected_main']),'detail_urls':sorted(detail_actual)==sorted(detail_expected)if slot_only else detail_actual==detail_expected,'other_formal_fields':protected(p,not slot_only,not main_only)==protected(old,not slot_only,not main_only)};report={'id':pid,'at':now(),'state':'REVIEW_PENDING','status':p['status'],'display':p['display'],'checks':checks,'score':None,'detail_order_equal':detail_actual==detail_expected,'detail_order_scope':'Single same-gallery image identity repair; current API changes image order within gallery150, associations checked independently'if slot_only else'Ordered full-gallery target','public_status':'API_ACCEPTANCE_NO_BROWSER_PER_USER'}
            if slot_only or mixed_slots:
                checks['detail_urls']=sorted(detail_actual)==sorted(detail_expected)
                report['detail_order_scope']='Exact same-gallery image identity repair; order within the same gallery is diagnostic, memberships and all image multiplicities remain protected.'
                detail_replacements=plan['detail_replacements_by_id'][pid]if plan.get('detail_replacements_by_id')else plan['detail_replacements_by_url']
                replacement={c._created_image_identity(u):c._created_image_identity(banks[role]['url'])for u,role in detail_replacements.items()}
                deletions={c._created_image_identity(u)for u in plan.get('detail_deletions_by_id',{}).get(pid,[])}
                expected_associations=sorted((replacement.get(c._created_image_identity(r['image_url']),c._created_image_identity(r['image_url'])),r['image_set']['id'])for r in old['struct_detail']['detail_image']['images']if c._created_image_identity(r['image_url'])not in deletions)
                actual_associations=sorted((c._created_image_identity(r['image_url']),r['image_set']['id'])for r in p['struct_detail']['detail_image']['images'])
                checks['detail_gallery_associations']=actual_associations==expected_associations
            if p['status']=='approved':
                checks['display']=p['display']==old['display'];rr=render(pid,p);save(raw/'after_render.json',rr)
                if rr.get('data'):
                    actual=c.field_snapshot(E.fromstring(rr['data']));wanted=c.field_snapshot(E.parse(raw/'payload.xml').getroot());previous=c.field_snapshot(E.fromstring(load(raw/'before_render.json')['data']));checks['schema_targets']=all(c.created_field_equivalent(k,v,actual.get(k))for k,v in wanted.items());checks['other_schema']=all(c.created_field_equivalent(k,v,actual.get(k))for k,v in previous.items()if k not in wanted)
                else:checks['schema_targets']=False
                enc=read('alibaba.icbu.product.id.encrypt',{'product_id':pid,'language':'ENGLISH'});score=read('alibaba.icbu.product.score.get',{'product_id':enc['secret_id']});save(raw/'score.json',score);report['score']=score.get('result',{}).get('final_score');diag=score.get('result',{}).get('problem_map')or{};diag=json.loads(diag)if isinstance(diag,str)else diag;report['diagnostics']=diag;checks['score']=report['score']is not None and Decimal(str(report['score']))>=5 and not diag.get('errorReasonList')and not any((diag.get('extendProblemMap')or{}).values());report['state']='FORMAL_FIELDS_SCORE_PASS'if all(v is True for v in checks.values())else'FORMAL_DIFFERENCE_DIAGNOSE_NO_REPLAY'
            report['failed']=[k for k,v in checks.items()if v is False];save(public/'verification.json',report);print(json.dumps({k:report[k]for k in ('id','state','score','failed')},ensure_ascii=False),flush=True)

def sync(plan,folder):
    file=ProductRegistry(ROOT);d=load(file)
    for pid in plan['ids']:
        public=folder/'商品'/pid;report=load(public/'verification.json');assert report['state']=='FORMAL_FIELDS_SCORE_PASS';raw=RAW/plan.get('execution_key',plan['family'])/pid;got=load(raw/'after_get.json');p=got['product'];l=next(x for x in d['listings']if x['id']==pid);product=next(x for x in d['products']if x['id']==l['product_id']);canonical=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'/pid
        if l.get('formal_fields',{}).get('at','')>report['at']:continue
        save(canonical/'formal_get.json',{'requested_product_id':pid,'observed_at_utc':report['at'],'method':'alibaba.icbu.product.get','response':s.sanitized(got),'sanitized_fields':['owner_member','owner_member_display_name','owner_member_id'],'raw_response_file':rel(raw/'after_get.json')});save(canonical/'formal_render.json',s.sanitized(load(raw/'after_render.json')));refs=[rel(folder/'计划.json'),rel(folder/'图片银行.json')]+[rel(public/n)for n in ('prepared.json','update_receipt.json','verification.json')];phase={'at':report['at'],'state':report['state'],'scope':plan.get('scope',plan.get('reason','Reviewed gallery and product detail only; all other formal fields protected')),'evidence':refs};l.setdefault('optimization',{})['content_gallery_revision']=phase;product['content_gallery_revision']=phase
        for obj in (l,product):obj['evidence']=list(dict.fromkeys(obj.get('evidence',[])+refs))
        l['formal_fields']={'file':rel(canonical/'formal_get.json'),'at':report['at'],'scope':phase['scope']};l.setdefault('current_platform_fields',{}).update(at=report['at'],main_images=p['main_image']['images'],detail_images=p['struct_detail']['detail_image']['images']);l.setdefault('catalog_fields',{}).update(l['current_platform_fields']);l.setdefault('observation',{}).update(at=report['at'],audit=p['status'],display=p['display'],score=report['score']);l.setdefault('local_sync',{}).update(state=report['state'],current_fields_file=rel(canonical/'formal_get.json'),gallery_verification=rel(public/'verification.json'));asset_key={'detail_slot':'current_detail_image_revision_by_id','main_slot':'current_main_image_revision_by_id','mixed_slots':'current_identity_image_revision_by_id'}.get(plan.get('kind'),'current_gallery_by_id');product.setdefault('local_assets',{}).setdefault(asset_key,{})[pid]=rel(folder/'计划.json')
    save(file,d);sys.path.insert(0,str(ROOT/'08_工具链/06_工作区维护'));import build_product_workspace as w;errors=w.validate(d,ROOT);assert not errors,errors
    for p,body in w.build(d).items():w.write_generated(ROOT/p,body)
    print('GALLERY_SOURCE_DOSSIER_SYNCHRONIZED',plan['family'],flush=True)

if __name__=='__main__':main()
