"""Map current formal CDN identities to unique local selected assets."""
from pathlib import Path
from PIL import Image
import json,os
import replace_hr_real_sources as o
PATH=o.ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前素材清单.json'
def sync():
 d=o.b.load(PATH);assets={}
 for family in o.TARGETS:
  for row in o.b.load(o.BASE/family/'图片银行.json')['items'].values():assets[o.contract._created_image_identity(row['url'])]=row
 for row in o.b.load(o.ROOT/'02_Alibaba运营/06_图片与检查记录/共享工厂详情/V8/bank.json')['items'].values():assets[o.contract._created_image_identity(row['url'])]=row
 for ts in o.TARGETS.values():
  for pid in ts.values():
   verification=o.BASE/'商品'/pid/'verification.json'
   if not verification.exists():continue
   proof=o.b.load(verification)
   if proof['state']!='FORMAL_FIELDS_SCORE_PASS':continue
   p=o.b.load(o.BASE/'商品'/pid/'after_get.json')['product'];sd=p['struct_detail'];roles={'main':p['main_image']['images'],'details':[x['image_url']for x in sd['detail_image']['images']],'company':[x['image_url']for x in sd['company_image']['images']],'sku':[v['image_url']for a in p['product_sku']['sku_attributes']for v in a['values']if v.get('image_url')],'html':[]}
   for urls in roles.values():
    for url in urls:
     row=assets[o.contract._created_image_identity(url)];path=o.ROOT/row['path'];assert o.b.sha(path)==row['sha256'];w,h=Image.open(path).size
     d['assets'][url]={'state':'SAVED','file':row['path'],'sha256':row['sha256'],'bytes':path.stat().st_size,'width':w,'height':h,'pixel_qa':'Selected source-preserving current local image; formal CDN asset identity matched','at':proof['get_observed_at']}
   d['products'][pid]=roles
 d['urls']=len(d['assets']);d['saved_urls']=sum(v.get('state')=='SAVED'for v in d['assets'].values());d['unique_files']=len({v['sha256']for v in d['assets'].values()if v.get('state')=='SAVED'});d['errors']=sum(v.get('state')!='SAVED'for v in d['assets'].values());o.b.save(PATH,d);print('CURRENT_MEDIA_IDENTITY_SYNC')
if __name__=='__main__':sync()
