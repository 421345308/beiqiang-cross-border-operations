"""Repair local image references from existing official upload receipts only.

No API calls, uploads, generated pictures, copied media or live product edits.
Exact current Luqi IDs and source-map SHA proofs bound the local mutation.
"""
from pathlib import Path
from PIL import Image
import argparse,copy,json,sys
sys.path.insert(0,str(Path(__file__).parent))
import publish_reviewed_luqi as p
ROOT=p.ROOT;BASE=p.BASE;CACHE=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前素材清单.json'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    reg_hash=p.sha(p.REG);cache_hash=p.sha(CACHE);data=p.load(p.REG);before=copy.deepcopy(data);cache=p.load(CACHE);rows=p.load(BASE/'本批正式商品汇总.json');listings={x['id']:x for x in data['listings']};products={x['id']:x for x in data['products']};targets=[];url_keys={}
    for url,item in cache['assets'].items():
        if item.get('state')=='SAVED':url_keys.setdefault(p.contract._created_image_identity(url),[]).append(item)
    for row in rows:
        pid=str(row['product_id']);listing=listings[pid];snapfile=ROOT/listing['formal_fields']['file'];snap=p.load(snapfile);actual=snap['response']['product'];assert str(snap['requested_product_id'])==pid and p.shared.attributes(actual)['Model Number']==[listing['model']]
        sd=actual['struct_detail'];roles={'main':actual['main_image']['images'],'details':[x['image_url']for x in sd['detail_image']['images']],'company':[x['image_url']for x in sd['company_image']['images']],'sku':[v['image_url']for a in actual['product_sku']['sku_attributes']for v in a['values']if v.get('image_url')],'html':[]};urls=list(dict.fromkeys(u for group in roles.values()for u in group));missing=[]
        for url in urls:
            saved=cache['assets'].get(url);aliased=url_keys.get(p.contract._created_image_identity(url),[])
            if saved and saved.get('state')=='SAVED':continue
            if aliased and len({a.get('sha256')for a in aliased})==1:continue
            missing.append(url)
        if not missing:continue
        bankfile=BASE/(row['style']+'准备')/'正式图片银行映射.json';bank=p.load(bankfile);assert isinstance(bank,list);mapping={}
        for b in bank:
            if not b.get('url'):continue
            key=p.contract._created_image_identity(b['url']);mapping.setdefault(key,[]).append(b)
        bindings={}
        for url in missing:
            candidates=mapping.get(p.contract._created_image_identity(url),[]);assert len(candidates)==1,(pid,url,'Missing/ambiguous exact official bank binding');b=candidates[0];assert b['status']=='VERIFIED'and str(b['file_id']).isdigit()and int(b['file_id'])>0
            file=Path(b['local_file']);file=file if file.is_absolute()else ROOT/file
            assert file.is_relative_to(ROOT)and file.is_file()and p.sha(file)==b['sha256'],(pid,b['role'],'Original upload file/SHA mismatch')
            w,h=Image.open(file).size;bindings[url]={'state':'SAVED','file':p.rel(file),'sha256':b['sha256'],'bytes':file.stat().st_size,'width':w,'height':h,'pixel_qa':'Previously reviewed original upload file; exact official CDN asset identity and positive bank fileID bound to current formal snapshot. Local SHA verified, no new remote pixel/UI claim.','at':p.now(),'bank_file_id':str(b['file_id']),'bank_evidence':p.rel(bankfile)}
        targets.append({'id':pid,'style':row['style'],'product_id':listing['product_id'],'formal_snapshot':p.rel(snapfile),'formal_snapshot_at':snap['observed_at_utc'],'bank_evidence':p.rel(bankfile),'roles':roles,'bindings':bindings})
    print('LOCAL_MEDIA_PLAN_PASS',len(targets),'IDs',sum(len(x['bindings'])for x in targets),'missing URL bindings; NO_NETWORK_OR_MEDIA_MUTATION',flush=True)
    if not args.apply or not targets:return
    assert p.sha(p.REG)==reg_hash and p.sha(CACHE)==cache_hash,'Shared registry/cache changed; rebase exact local mutation'
    for target in targets:
        pid=target['id'];cache['assets'].update(copy.deepcopy(target['bindings']));cache['products'][pid]=target['roles'];proof=ROOT/listings[pid]['formal_fields']['file'];proof=proof.parent/'本地素材绑定核验.json'
        p.save(proof,{'at':p.now(),'id':pid,'state':'CURRENT_FORMAL_URL_TO_REVIEWED_UPLOAD_FILE_SHA_MATCH','scope':'Existing upload receipt and current formal snapshot mapping repaired locally only; no product change, upload, download or generation.','formal_snapshot':target['formal_snapshot'],'formal_snapshot_at':target['formal_snapshot_at'],'bank_evidence':target['bank_evidence'],'reconciled_bindings':target['bindings'],'current_roles':target['roles']})
        listing=listings[pid];listing.setdefault('local_sync',{})['media_cache_evidence']=p.rel(proof);product=products[listing['product_id']];product['local_assets']['current_image_map']=p.rel(proof)
        for obj in (product,listing):obj['evidence']=list(dict.fromkeys(obj.get('evidence',[])+[p.rel(proof)]))
    cache['urls']=len(cache['assets']);cache['saved_urls']=sum(x.get('state')=='SAVED'for x in cache['assets'].values());cache['unique_files']=len({x['sha256']for x in cache['assets'].values()if x.get('state')=='SAVED'});cache['errors']=sum(x.get('state')!='SAVED'for x in cache['assets'].values())
    sys.path.insert(0,str(ROOT/'08_工具链/06_工作区维护'));import build_product_workspace as workspace
    assert set(workspace.validate(data))<=set(workspace.validate(before))
    assert p.sha(p.REG)==reg_hash and p.sha(CACHE)==cache_hash,'Shared data changed during validation'
    workspace.write_generated(CACHE,(json.dumps(cache,ensure_ascii=False,indent=2)+'\n').encode('utf8'));workspace.write_generated(p.REG,(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    for path,body in workspace.build(data).items():workspace.write_generated(ROOT/path,body)
    p.save(ROOT/'99_临时区/路崎2569/local_media_reconciliation.json',{'at':p.now(),'state':'EXACT_LOCAL_BINDINGS_RECONCILED','ids':[x['id']for x in targets],'bindings':sum(len(x['bindings'])for x in targets),'evidence_files':[listings[x['id']]['local_sync']['media_cache_evidence']for x in targets],'registry_and_source_fields_preserved':True,'external_writes':0,'new_media_files':0});print('LOCAL_MEDIA_APPLIED',len(targets),'IDs',flush=True)


if __name__=='__main__':main()
