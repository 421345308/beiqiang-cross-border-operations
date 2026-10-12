"""Owner-approved company images, introduction and general FAQ, exact-ID batches.

Reuses the official client and scoped Schema publisher. Each mutation has an
exclusive ledger. Prior V6 evidence remains intact; V8 evidence lives by ID.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from xml.etree import ElementTree as E
from urllib.request import Request, urlopen
from urllib.parse import urlparse
import argparse, copy, hashlib, io, json, sys
from PIL import Image

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'02_Alibaba运营/06_图片与检查记录/共享工厂详情'
COPY=ROOT/'02_Alibaba运营/02_单品优化记录/全店FAQ与产品亮点优化'
PHASE=BASE/'V8'
sys.path.insert(0,str(ROOT/'08_工具链/01_业务脚本/国际站扩品'))
import refresh_buyer_copy as b
import publish_hot_rank_hr_a_batch as pub
from read_only_catalog import read_only_call
from prepare_company_gallery import ROLES as OLD_ROLES
ROLES=OLD_ROLES+[('C6',700,'Packaging & shipping specifications')]
FIELDS=['companyImage','companyDesc','companyFaqDesc','productTitle']
CANARY='1601976084873'

def now():return datetime.now(timezone.utc).isoformat()
def load(p):return b.load(p)
def save(p,x):b.save(p,x)
def sha(p):return b.sha(p)
def folder(pid):return BASE/'商品'/pid/'V8'
def ledger_file(pid):
    f=folder(pid);proof=f/'unknown_reconciliation.json'
    if proof.exists():
        x=load(proof)
        assert x['status']=='TWO_FRESH_READS_CONFIRM_NO_EFFECT'
        assert x['product_id']==pid and len(x['readback_request_ids'])==2
        assert load(f/'update_once.json')['status']=='write_outcome_unknown'
        return f/'recovery_update_once.json'
    return f/'update_once.json'
def approval():
    m=load(BASE/'制作档案.json');c=load(COPY/'通用FAQ与公司简介.json')
    assert m['version']==8 and m['status']=='APPROVED_FOR_BATCH_REPLACEMENT'
    assert c['status']=='APPROVED_FOR_BATCH_REPLACEMENT'
    assert load(PHASE/'scope.json')['owner_approval']=='这个版本可以，与faq一起分批对商品进行全量替换'
    return m,c
def preserved(p):
    x=copy.deepcopy(p)
    for k in ('gmt_modified','status','display'):x.pop(k,None)
    d=x.get('struct_detail')
    if isinstance(d,dict):
        for k in ('company_image','company_summary','product_faq'):d.pop(k,None)
    return x
def pairs(p):
    return Counter((str(x['image_set']['id']),x['image_url'].removeprefix('https:').removeprefix('http:')) for x in (p.get('struct_detail',{}).get('company_image') or {}).get('images',[]))
def schema_pairs(xml):
    r=E.fromstring(xml);f=r.find("./field[@id='companyImage']");out=[]
    for row in f.findall('./complex-values'):
        role=row.find("./field[@id='gallery']/value").text
        for url in row.findall("./field[@id='images']/complex-values/field[@id='imageURL']/value"):
            out.append((role,(url.text or '').removeprefix('https:')))
    return Counter(out)
def aliases():
    proof=load(PHASE/'url_identity.json');assert proof['status']=='SIX_EXACT_FORMAL_IDENTITIES_VERIFIED'
    return {u.removeprefix('https:'):(str(x['gallery_id']),x['asset']) for x in proof['items'] for u in x['accepted_urls']}
def image_match(actual):
    a=aliases();found=[]
    for (role,url),count in actual.items():
        if count!=1 or url not in a or a[url][0]!=role:return False
        found.append(a[url])
    return Counter(found)==Counter((str(role),key)for key,role,_ in ROLES)
def bank_upload(api,cfg):
    m,c=approval();path=PHASE/'bank.json'
    bank=load(path)if path.exists()else{'asset_version':8,'items':{},'status':'IN_PROGRESS'}
    for key,asset in m['assets'].items():
        local=ROOT/asset['path'];assert sha(local)==asset['sha256'] and local.stat().st_size<=5*1024*1024
        previous=bank['items'].get(key)
        if previous and previous['status']=='UPLOADED_OFFICIAL_BANK':
            assert previous['sha256']==sha(local)
            continue
        if previous:
            assert previous['status']=='RECONCILED_NOT_UPLOADED_NORMAL_NETWORK_RETRY_AUTHORIZED'
            assert previous.get('independent_bank_evidence') and previous.get('original_attempt_preserved')
        row={'path':asset['path'],'sha256':sha(local),'at':now(),'status':'STARTED_OUTCOME_UNKNOWN'}
        if previous:row['reconciled_previous_attempt']=previous
        bank['items'][key]=row;save(path,bank)
        response=api.upload_image(cfg,local,None);row['response']=response;save(path,bank)
        item=response.get('upload_image_response')or{}
        assert not api.api_error(response)and item.get('file_id')and item.get('photobank_url')
        url=item['photobank_url'].replace('http:','https:');url='https:'+url if url.startswith('//')else url
        assert urlparse(url).hostname=='sc04.alicdn.com'
        row.update(status='UPLOADED_OFFICIAL_BANK',url=url,file_id=str(item['file_id']));save(path,bank)
        print(key,'UPLOADED_OFFICIAL_BANK',flush=True)
    rows=[]
    for key,asset in bank['items'].items():
        with urlopen(Request(asset['url'],headers={'User-Agent':'Mozilla/5.0'}),timeout=30)as response:raw=response.read()
        actual=Image.open(io.BytesIO(raw)).convert('RGB');original=Image.open(ROOT/asset['path']).convert('RGB')
        assert hashlib.sha256(raw).hexdigest()==asset['sha256'] and actual.size==original.size and actual.tobytes()==original.tobytes()
        rows.append({'asset':key,'file_id':asset['file_id'],'source_sha256':asset['sha256'],'download_sha256':hashlib.sha256(raw).hexdigest(),'dimensions':list(actual.size),'status':'BANK_PIXELS_EXACT_PASS'})
    bank['status']='SIX_OFFICIAL_BANK_ASSETS_VERIFIED';save(path,bank)
    save(PHASE/'bank_pixels.json',{'asset_version':8,'at':now(),'status':'SIX_BANK_PIXELS_EXACT_PASS','items':rows})
def establish_aliases(pid,p,xml,bank):
    rows=[];actual=pairs(p);schema=schema_pairs(xml)
    for key,role,_ in ROLES:
        asset=bank['items'][key];long=asset['url'];token=urlparse(long).path.split('/')[2]
        formal=[u for (r,u)in actual if r==str(role)and token in u];editor=[u for (r,u)in schema if r==str(role)and token in u]
        assert len(formal)==len(editor)==1
        url='https:'+formal[0]if formal[0].startswith('//')else formal[0]
        with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=30)as response:raw=response.read()
        assert hashlib.sha256(raw).hexdigest()==asset['sha256']
        rows.append({'asset':key,'gallery_id':role,'file_id':asset['file_id'],'source_sha256':asset['sha256'],'download_sha256':hashlib.sha256(raw).hexdigest(),'accepted_urls':list(dict.fromkeys([long,url,'https:'+editor[0]if editor[0].startswith('//')else editor[0]])),'status':'EXACT_SOURCE_BYTES_AND_PIXELS'})
    save(PHASE/'url_identity.json',{'asset_version':8,'at':now(),'product_id':pid,'status':'SIX_EXACT_FORMAL_IDENTITIES_VERIFIED','items':rows})
def work(mode,pid,api,cfg):
    m,c=approval();scope=load(PHASE/'scope.json');assert pid in scope['eligible_ids'] and pid not in scope['excluded_ids']
    f=folder(pid);f.mkdir(parents=True,exist_ok=True);ledger=ledger_file(pid);bank=load(PHASE/'bank.json')
    assert bank['status']=='SIX_OFFICIAL_BANK_ASSETS_VERIFIED'
    def get():return read_only_call(api,cfg,'alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'})
    def render(p):return read_only_call(api,cfg,'alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US'}})
    if mode=='prepare':
        if ledger.exists():return {'product_id':pid,'status':'EXISTING_LEDGER_READBACK_ONLY'}
        got=get();save(f/'before_get.json',got);p=got['product']
        if p['status']!='approved':return {'product_id':pid,'status':'WAIT_CURRENT_REVIEW'}
        old=load(BASE/'商品'/pid/'before_get.json')['product'];assert p['display']==old['display'],'Original display must be preserved'
        response=render(p);save(f/'before_render.json',response)
        if not response.get('data'):return {'product_id':pid,'status':'WAIT_EDITABLE_SCHEMA'}
        schema=E.fromstring(response['data']);root=pub.values_only(schema,operation='update',field_ids=FIELDS)
        options={int(x.get('value')):x.get('displayName')for x in schema.findall("./field[@id='companyImage']/fields/field[@id='gallery']/options/option")}
        assert all(options.get(role)==name for _,role,name in ROLES)
        assert root.find("./field[@id='productTitle']/value").text==p['subject']
        pub.set_gallery(root,'companyImage',[bank['items'][k]for k,_,_ in ROLES],[(r,n)for _,r,n in ROLES])
        # Merge C5/C6 into the same official packing/shipping group.
        field=root.find("./field[@id='companyImage']");seen={}
        for row in list(field.findall('./complex-values')):
            role=row.find("./field[@id='gallery']/value").text
            if role in seen:
                dst=seen[role].find("./field[@id='images']")
                for image in row.find("./field[@id='images']").findall('./complex-values'):dst.append(image)
                field.remove(row)
            else:seen[role]=row
        desc=root.find("./field[@id='companyDesc']")
        for child in list(desc):desc.remove(child)
        E.SubElement(desc,'value').text=c['companyDesc']
        faq=root.find("./field[@id='companyFaqDesc']");definition=schema.find("./field[@id='companyFaqDesc']")
        for child in list(faq):faq.remove(child)
        defs={x.get('id'):x for x in definition.findall('./fields/field')}
        for pair in c['companyFaqDesc']:
            row=E.SubElement(faq,'complex-values')
            for k in ('question','answers'):
                E.SubElement(E.SubElement(row,'field',{'id':k,'type':defs[k].get('type')}),'value').text=pair[k]
        (f/'current_schema.xml').write_text(response['data'],encoding='utf8');(f/'payload.xml').write_text(E.tostring(root,encoding='unicode'),encoding='utf8')
        deps=['productDescType']if schema.find("./field[@id='productDescType']")is not None else[]
        manifest={'operation':'update','product_id':pid,'category_id':p['category_id'],'facts_reviewed':True,'source_evidence':[(PHASE/'scope.json').relative_to(ROOT).as_posix(),(COPY/'通用FAQ与公司简介.json').relative_to(ROOT).as_posix(),(PHASE/'bank_pixels.json').relative_to(ROOT).as_posix()],'current_schema':'current_schema.xml','current_schema_sha256':sha(f/'current_schema.xml'),'schema_request_id':response['request_id'],'schema_acquired_at':now(),'payload_xml':'payload.xml','field_ids':FIELDS,'dependency_ids':deps,'copy_sha256':sha(COPY/'通用FAQ与公司简介.json')}
        save(f/'manifest.json',manifest);save(f/'prepared.json',pub.load_submission_manifest(f/'manifest.json','update',pid))
        return {'product_id':pid,'status':'PREPARED'}
    if mode=='submit':
        if ledger.exists():return {'product_id':pid,'status':'EXISTING_LEDGER_READBACK_ONLY'}
        if pid!=CANARY:
            assert load(folder(CANARY)/'verification.json')['status']=='FORMAL_PASS'
            assert load(folder(CANARY)/'public_verification.json')['status']=='PUBLIC_SIX_IMAGES_INTRO_FAQ_PASS'
        listing=pub.load_submission_manifest(f/'manifest.json','update',pid)
        assert set(listing['field_ids'])==set(FIELDS)
        assert load(f/'manifest.json')['copy_sha256']==sha(COPY/'通用FAQ与公司简介.json')
        got=get();save(f/'immediate_prewrite_get.json',got)
        if got['product']!=load(f/'before_get.json')['product']:return {'product_id':pid,'status':'CURRENT_CHANGED_REPREPARE_NO_WRITE'}
        with ledger.open('x',encoding='utf8')as h:json.dump({'product_id':pid,'status':'STARTED_OUTCOME_UNKNOWN','at':now()},h)
        receipt=pub.api_submit(api,cfg,listing,False,update_product_id=pid);save(f/('recovery_update_receipt.json' if ledger.name=='recovery_update_once.json' else 'update_receipt.json'),receipt);save(ledger,{'product_id':pid,'status':receipt['status'],'at':receipt['attempted_at'],'refs':receipt.get('refs')})
        return {'product_id':pid,'status':receipt['status']}
    if not ledger.exists():return {'product_id':pid,'status':'NO_WRITE_LEDGER'}
    got=get();save(f/'after_get.json',got);p=got['product'];old=load(f/'before_get.json')['product']
    v={'product_id':pid,'asset_version':8,'at':now(),'request_id':got.get('request_id'),'product_status':p['status'],'display':p['display'],'display_preserved':p['display']==old['display'],'status':'PENDING_REVIEW'}
    if p['status']=='approved':
        response=render(p);save(f/'after_render.json',response)
        if not response.get('data'):v['status']='PENDING_EDITABLE_SCHEMA'
        else:
            xml=response['data'];(f/'after_schema.xml').write_text(xml,encoding='utf8')
            if pid==CANARY and not(PHASE/'url_identity.json').exists():establish_aliases(pid,p,xml,bank)
            actual=b.formal_copy(p);expected=[{k:x[k]for k in ('question','answers')}for x in c['companyFaqDesc']]
            snap=pub.field_snapshot(E.fromstring(xml));want=load(f/'prepared.json')['expected_fields']
            before_snap=pub.field_snapshot(E.parse(f/'current_schema.xml').getroot())
            schema_differences=[k for k in set(before_snap)|set(snap) if k not in FIELDS and before_snap.get(k)!=snap.get(k)]
            a,z=preserved(old),preserved(p);differences=[k for k in set(a)|set(z)if a.get(k)!=z.get(k)]
            v.update(company_images_match=image_match(pairs(p)),schema_images_match=image_match(schema_pairs(xml)),faq_match=b.faq_pairs_equivalent(actual['faq'],expected),company_intro_match=p.get('struct_detail',{}).get('company_summary')==c['companyDesc'],schema_copy_match=snap.get('companyDesc')==want['companyDesc']and b.faq_snapshot_content_equivalent(snap.get('companyFaqDesc'),want['companyFaqDesc']),non_target_changed_fields=differences,unsubmitted_fields_preserved=not differences,company_image_count=sum(pairs(p).values()))
            v.update(non_target_schema_changed_fields=schema_differences,unsubmitted_schema_fields_preserved=not schema_differences)
            passed=all(v[k]for k in ('company_images_match','schema_images_match','faq_match','company_intro_match','schema_copy_match','unsubmitted_fields_preserved','unsubmitted_schema_fields_preserved','display_preserved'))
            v['status']='FORMAL_PASS'if passed else'MISMATCH_DIAGNOSE_NO_REPLAY'
    public=f/'public_verification.json'
    v['public_status']=load(public)['status']if public.exists()else'NOT_APPLICABLE_OFFLINE_DISPLAY_PRESERVED'if v['status']=='FORMAL_PASS'and old['display']=='N'else'PENDING_PUBLIC'
    save(f/'verification.json',v);return v
def aggregate():
    scope=load(PHASE/'scope.json');rows=[]
    for pid in scope['eligible_ids']:
        f=folder(pid);v=load(f/'verification.json')if(f/'verification.json').exists()else{}
        ledger=ledger_file(pid);l=load(ledger)if ledger.exists()else{}
        if v.get('at','')<l.get('at',''):v={}
        rows.append({'product_id':pid,'status':v.get('status',l.get('status','NOT_SUBMITTED')),'submission_status':l.get('status','NOT_SUBMITTED'),'public_status':v.get('public_status','NOT_CHECKED')})
    counts=dict(Counter(x['status']for x in rows));public=dict(Counter(x['public_status']for x in rows))
    formal_complete=counts.get('FORMAL_PASS',0)==len(rows)
    public_expected=len(rows)-len(scope['original_offline_ids'])
    public_complete=public.get('PUBLIC_SIX_IMAGES_INTRO_FAQ_PASS',0)==public_expected and public.get('NOT_APPLICABLE_OFFLINE_DISPLAY_PRESERVED',0)==len(scope['original_offline_ids'])
    out={'asset_version':8,'at':now(),'authorized_count':len(rows),'counts':counts,'public_counts':public,'items':rows,'scope':['companyImage','companyDesc','companyFaqDesc'],'productTitle':'same original value explicitly preserved','historical_source_and_highlight_holds_unchanged':True}
    out.update(formal_scope_complete=formal_complete,public_expected_count=public_expected,public_scope_complete=public_complete,completed_this_scope=formal_complete and public_complete)
    save(PHASE/'当前替换.json',out)
    m=load(BASE/'制作档案.json')
    if m.get('published_version')!=8:
        m['previous_completed_online_state']=m['online_state']
        m['previous_published_assets']={'asset_version':m.get('published_version',6),'assets':m['published_assets']}
        m['published_version']=8;m['published_assets']=copy.deepcopy(m['assets'])
    state='COMPLETE_THIS_SCOPE' if formal_complete and public_complete else 'FORMAL_COMPLETE_PUBLIC_VERIFY_PENDING' if formal_complete else 'BATCH_REPLACEMENT_IN_PROGRESS'
    m['online_state']={'asset_version':8,'state':state,'uploaded':True,'bank_evidence':'V8/bank.json','bank_pixels_evidence':'V8/bank_pixels.json','bound_product_count':counts.get('FORMAL_PASS',0),'authorized_product_count':len(rows),'public_pass_count':public.get('PUBLIC_SIX_IMAGES_INTRO_FAQ_PASS',0),'original_offline_display_preserved_count':public.get('NOT_APPLICABLE_OFFLINE_DISPLAY_PRESERVED',0),'current_state_evidence':'V8/当前替换.json','scope':'Six company images, introduction and general FAQ only; per-shoe highlights and sources preserved'}
    save(BASE/'制作档案.json',m)
    return {'counts':counts,'public_counts':public}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['upload','prepare','submit','verify','aggregate']);ap.add_argument('--ids');ap.add_argument('--workers',type=int,default=4);a=ap.parse_args();sys.stdout.reconfigure(encoding='utf8')
    if a.mode=='aggregate':print(json.dumps(aggregate()));return
    api,cfg=b.api_client()
    if a.mode=='upload':bank_upload(api,cfg);return
    ids=a.ids.split(',')if a.ids else load(PHASE/'scope.json')['eligible_ids'];assert len(ids)==len(set(ids))
    def safe(pid):
        try:return work(a.mode,pid,api,cfg)
        except Exception as e:
            result={'product_id':pid,'status':'ERROR_NO_REPLAY','error_type':type(e).__name__,'reason':str(e)[:200]}
            save(folder(pid)/(a.mode+'_error.json'),result);return result
    if a.mode=='submit':
        for pid in ids:print(json.dumps(safe(pid)),flush=True)
    else:
        with ThreadPoolExecutor(max_workers=a.workers)as pool:
            jobs={pool.submit(safe,pid):pid for pid in ids}
            for future in as_completed(jobs):print(json.dumps(future.result()),flush=True)
    print(json.dumps(aggregate()),flush=True)
if __name__=='__main__':main()
