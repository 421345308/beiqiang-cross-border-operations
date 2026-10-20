"""Bind current reviewed media to exact CDN identities, without copying masters."""

import sys as _registry_sys
from pathlib import Path as _RegistryPath
_registry_sys.path.insert(0, str(_RegistryPath(__file__).resolve().parents[3]/"08_工具链/06_工作区维护"))
from product_registry import ProductRegistry
from pathlib import Path
from PIL import Image
import json,sys,subprocess
sys.path.insert(0,str(Path(__file__).parent));import revise_catalog_content as s
import schema_publish_contract as c

def main():
    sys.stdout.reconfigure(encoding='utf8');file=ProductRegistry(s.ROOT);data=s.load(file);cachefile=s.ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前素材清单.json';cache=s.load(cachefile);records={}
    for bankfile in s.BASE.rglob('图片银行.json'):
        for role,row in s.load(bankfile).get('items',{}).items():
            if row.get('state')!='UPLOADED'or not row.get('file'):continue
            f=s.ROOT/row['file'];assert f.exists()and s.sha(f)==row['sha256'],row['file'];im=Image.open(f)
            records[c._created_image_identity(row['url'])]={'state':'SAVED','file':row['file'],'sha256':row['sha256'],'width':im.width,'height':im.height,'at':row.get('at',s.now()),'origin':'REVIEWED_CURRENT_MASTER_BOUND_BY_OFFICIAL_BANK_ID','source_review':s.rel(bankfile.parent/'计划.json')if(bankfile.parent/'计划.json').exists()else s.rel(bankfile),'bank_url':row['url']}
    colour_plan=s.load(s.BASE/'配色与尺码修正/BQ015_颜色图纠正/计划.json');local=s.load(s.BASE/'配色与尺码修正/BQ015_颜色图纠正/本地颜色图映射.json');special={}
    for label,url in colour_plan['rebind_images'].items():
        row=local['items'][label];f=s.ROOT/row['file'];assert s.sha(f)==row['sha256'];im=Image.open(f);record={'state':'SAVED','file':row['file'],'sha256':row['sha256'],'width':im.width,'height':im.height,'at':s.now(),'origin':'EXACT_EXISTING_PUBLIC_PHOTO_CORRECTED_COLOUR_BINDING','source_review':s.rel(s.BASE/'配色与尺码修正/BQ015_颜色图纠正/本地颜色图映射.json'),'bank_url':url};records[c._created_image_identity(url)]=record;special[row['sha256']]=record
    aliases=0
    for url,row in list(cache.setdefault('assets',{}).items()):
        identity=c._created_image_identity(url)
        if identity in records:cache['assets'][url]={**records[identity],'source_url':url};aliases+=1
        elif row.get('sha256')in special and row.get('file','').startswith('01_产品资产/02_可发布素材/00_最终上传/BQ015_R1811/03_颜色图/'):
            cache['assets'][url]={**special[row['sha256']],'source_url':url};aliases+=1
    for identity,row in records.items():cache['assets'][row['bank_url']]=row
    for listing in data['listings']:
        formal=listing.get('formal_fields',{}).get('file')
        if not formal or not(s.ROOT/formal).exists():continue
        p=s.load(s.ROOT/formal)['response']['product'];urls=list(p.get('main_image',{}).get('images',[]))+[x['image_url']for x in p.get('struct_detail',{}).get('detail_image',{}).get('images',[])]+[v['image_url']for a in p.get('product_sku',{}).get('sku_attributes',[])for v in a['values']if v.get('image_url')]
        bound={}
        for u in urls:
            identity=c._created_image_identity(u)
            if identity in records:cache['assets'][u]={**records[identity],'source_url':u};bound[u]=records[identity]['file']
        if bound:cache.setdefault('products',{}).setdefault(listing['id'],{})['current_content_media_binding']={'at':listing['formal_fields']['at'],'formal':formal,'assets':bound}
    cache['content_media_revision']={'at':s.now(),'entry':s.rel(s.ENTRY),'master_identities':len(records),'no_master_copies_created':True};s.save(cachefile,cache)
    products={p['id']:p for p in data['products']};p=products['BQ015'];p.setdefault('local_assets',{})['current_colour_images']=s.rel(s.BASE/'配色与尺码修正/BQ015_颜色图纠正/本地颜色图映射.json');p['next_action']='六色66SKU与旧三色错绑已核；新增33色码组合按负责人确认设999可询货标记，独立库存接口与正式SKU已回读；继续六色总览及评分刷新核对。'
    p=products['BQ-NS003'];p['next_action']='七色75SKU与七色主图总览已正式核验5.0；粉色无独立实图，不将紫色冒充粉色；保留原44SKU身份与价格。'
    p=products['BQ018'];assets=p.setdefault('local_assets',{});gallery=assets.setdefault('current_gallery_by_id',{});oldfile='00_总控台/产品中心/数据/产品.json';old=json.loads(subprocess.check_output(['git','show','HEAD:'+oldfile]).decode('utf8'));oldp=next(x for x in old['products']if x['id']=='BQ018');prior=oldp.get('local_assets',{}).get('current_gallery_by_id',{})
    for pid,value in list(gallery.items()):
        if 'BQ018_错误尺码图'in value:
            assets.setdefault('current_detail_image_revision_by_id',{})[pid]=value
            if pid in prior:gallery[pid]=prior[pid]
            else:gallery.pop(pid)
    p['next_action']='四条EU范围、止扣鞋带文案、错误US/脚长详情图及主图色卡均已核5.0；首条完整新主图组，另外三条保留原主图并修正色卡，继续独立审核其他详情。'
    p=products['BQ015']
    if p.get('current_content_reconciliation',{}).get('state')=='FORMAL_FIELDS_SCORE_PASS':p['next_action']='三条均六色EU35–45、66SKU、正确颜色图、999可询货标记及六色主图总览已核验5.0；继续独立检查其他详情图与属性。'
    data['updated_on']=s.now()[:10];s.save(file,data);sys.path.insert(0,str(s.ROOT/'08_工具链/06_工作区维护'));import build_product_workspace as w;errors=w.validate(data,s.ROOT);assert not errors,errors
    for path,body in w.build(data).items():w.write_generated(s.ROOT/path,body)
    print(json.dumps({'reviewed_master_identities':len(records),'updated_existing_aliases':aliases,'registry_and_current_media_index_synced':True}))

if __name__=='__main__':main()
