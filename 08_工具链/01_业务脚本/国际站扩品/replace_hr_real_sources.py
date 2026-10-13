"""Exact-ID authorized whole-shoe migration; serial writes, no write retries."""
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
from xml.etree import ElementTree as E
from collections import Counter
from urllib.parse import urlparse
import sys,json,copy,hashlib
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'02_Alibaba运营/05_扩品工程/执行记录/HR实源替换'
sys.path.insert(0,str(ROOT/'08_工具链/01_业务脚本/国际站扩品'))
import refresh_buyer_copy as b
import publish_hot_rank_hr_a_batch as pub
import schema_publish_contract as contract
from read_only_catalog import read_only_call
SCOPE=b.load(BASE/'scope.json')
TARGETS=SCOPE['targets']
FIELDS=['icbuCatProp','saleProp','sku','productTitle','productKeywords','scImages','detailImage','textDesc','customMoreProperty','scPrice','ladderPrice']
PLANS={family:b.load(BASE/family/'事实与页面计划.json')for family in TARGETS}
RAW_PATHS={family:plan['source_assets_root']for family,plan in PLANS.items()}

def field(parent,fid,typ='input',value=None):
 x=E.SubElement(parent,'field',id=fid,type=typ)
 if value is not None:E.SubElement(x,'value').text=str(value)
 return x
def set_attr(schema,cv,name,texts):
 defs=[f for f in schema.findall("./field[@id='icbuCatProp']/fields/field")if f.get('name')==name];assert len(defs)==1,name
 d=defs[0];typ=d.get('type');assert typ in ['singleCheck','multiCheck']
 x=field(cv,d.get('id'),typ);vs=E.SubElement(x,'values')if typ=='multiCheck' else x
 opts={o.get('displayName').casefold():o.get('value')for o in d.findall('./options/option')}
 for i,t in enumerate(texts):
  val=opts.get(t.casefold())
  if val is None:
   assert any(r.get('name')=='tipRule' and '负数' in r.get('value','')for r in d.findall('./rules/rule'))
   val=str(-701-i)
  E.SubElement(vs,'value',inputValue=t).text=val
def bank(family,api,cfg):
 m=b.load(BASE/family/'素材清单.json');assert m['state']=='VISUAL_PASS'
 f=BASE/family/'图片银行.json';data=b.load(f)if f.exists()else {'family':family,'items':{}}
 for key,a in m['items'].items():
  if key=='审核总览':continue
  p=ROOT/a['path'];assert b.sha(p)==a['sha256'] and p.stat().st_size<4*1024*1024
  old=data['items'].get(key)
  if old:
   assert old['state']=='UPLOADED' and old['sha256']==a['sha256'],'Unknown or changed upload must be reconciled'
   continue
  row={**a,'state':'OUTCOME_UNKNOWN','at':b.now()};data['items'][key]=row;b.save(f,data)
  res=api.upload_image(cfg,p,None);row['response']=res;b.save(f,data)
  r=res.get('upload_image_response',{});assert not api.api_error(res) and r.get('file_id')and r.get('photobank_url')
  url=r['photobank_url'].replace('http:','https:');url='https:'+url if url.startswith('//')else url
  assert urlparse(url).hostname=='sc04.alicdn.com'
  row.update(state='UPLOADED',url=url,file_id=str(r['file_id']));b.save(f,data);print(family,key,'UPLOADED',flush=True)
 data['state']='COMPLETE';b.save(f,data)
def prepare(family):
 p=PLANS[family];assets=b.load(BASE/family/'图片银行.json')['items'];source=b.load(ROOT/RAW_PATHS[family]/'source.json')
 assert source['artno']==p['source_artno'];fx=p.get('fx_cny_per_usd',6.6837);cost=source['price_cny']/fx
 for variant,pid in TARGETS[family].items():
  f=BASE/'商品'/pid;assert not (f/'update_once.json').exists()
  before=b.load(f/'before_get.json')['product'];schema=E.fromstring(b.load(f/'before_render.json')['data'])
  category=p.get('category_id',int(before['category_id']))
  if category!=int(before['category_id']):
   target=E.fromstring(b.load(BASE/family/'目标类目Schema.json')['data'])
   # Preserve each target's non-product values; definitions for rebuilt category
   # attributes come from the current destination schema, never the old category.
   old=schema.find("./field[@id='icbuCatProp']");schema.remove(old)
   schema.append(copy.deepcopy(target.find("./field[@id='icbuCatProp']")))
  root=pub.values_only(schema,operation='update',field_ids=FIELDS)
  cp=root.find("./field[@id='icbuCatProp']")
  for child in list(cp):cp.remove(child)
  cv=E.SubElement(cp,'complex-value')
  for name,texts in [('Place of Origin',['China']),('Midsole Material',[p.get('midsole','Other')]),('Outsole Material',[p.get('outsole','Rubber')]),('Lining Material',[p['lining']]),('Upper Material',[p['upper']]),('Style',p['style']),('Closure Type',[p['closure']]),('Toe Style',[p.get('toe_style','Round Toe')])]:set_attr(schema,cv,name,texts)
  for name,texts in [('Season',p['seasons']),('Feature',[p.get('feature','Fashion Trend')])]:set_attr(schema,cv,name,texts)
  for name,texts in p.get('extra_category_attributes',{}).items():set_attr(schema,cv,name,texts)
  cv.append(contract.serialize_product_model(schema,f'{family}-{variant}'))
  colors=[]
  sp=root.find("./field[@id='saleProp']")
  for child in list(sp):sp.remove(child)
  cv=E.SubElement(sp,'complex-value');c=field(cv,'p-191288010','multiCheck');cs=E.SubElement(c,'values')
  for i,color in enumerate(p['colors'],1):
   key=color.upper().replace(' ','_');vid=str(-500-i);colors.append((color,key,vid))
   E.SubElement(cs,'value',inputValue=color,img=assets['SKU_'+key]['url'],remark=color).text=vid
  sz=field(cv,'p-222038415','multiCheck');vs=E.SubElement(sz,'values')
  for n in p['sizes']:E.SubElement(vs,'value',inputValue=f'EU{n}').text=str(-800-n)
  sku=root.find("./field[@id='sku']")
  for child in list(sku):sku.remove(child)
  for color,key,cid in colors:
   for n in p['sizes']:
    row=E.SubElement(sku,'complex-values');field(row,'skuOuterId',value=f'{family}-{variant}-{key}-EU{n}')
    props=field(row,'props','multiInput');vals=E.SubElement(props,'values')
    for prop,vid,name in [('191288010',cid,color),('222038415',str(-800-n),f'EU{n}')]:E.SubElement(vals,'value',propId=prop,propName='p-'+prop,propValueId=vid,propValueName=name).text=prop+':'+vid
  contract.validate_sku_property_pairs(root)
  title=p['titles'][variant];assert len(title)<=128 and family not in title
  pub.set_direct_value(root,'productTitle',title);old=root.find("./field[@id='productKeywords']");root.remove(old);root.append(contract.serialize_product_keywords(schema,p['keywords']))
  order=['M1','M2','M3','M4','M5','M6']
  if family=='HR030'and variant=='B':order=['M2','M1','M3','M4','M5','M6']
  if family=='HR042'and variant=='B':order=['M2','M1','M3','M4','M5','M6']
  if family=='HR042'and variant=='C':order=['M3','M1','M2','M4','M5','M6']
  pub.set_main_images(root,[assets[k]for k in order]);pub.set_gallery(root,'detailImage',[assets['D'+str(n)]for n in range(1,5)],[(300,'Detail shot'),(350,'Other product images'),(350,'Other product images'),(350,'Other product images')])
  pub.set_direct_value(root,'textDesc',p['highlights']);pub.set_direct_value(root,'scPrice','1')
  more=root.find("./field[@id='customMoreProperty']");v=more.find("./complex-value/field[@id='customMoreProperty_0']/complex-value")
  assert v is not None
  v.find("./field[@id='propName']/value").text=p['custom'][0];v.find("./field[@id='valueName']/value").text=p['custom'][1]
  if 'tiers'in p:
   ladder=root.find("./field[@id='ladderPrice']")
   for child in list(ladder):ladder.remove(child)
   cv=E.SubElement(ladder,'complex-value')
   for i,(q,price)in enumerate(p['tiers']):v=E.SubElement(field(cv,'ladderPrice_'+str(i),'complex'),'complex-value');field(v,'quantity',value=q);field(v,'price',value=price)
  tiers=[(int(row.find("./complex-value/field[@id='quantity']/value").text),float(row.find("./complex-value/field[@id='price']/value").text))for row in root.findall("./field[@id='ladderPrice']/complex-value/field")];tiers.sort()
  assert len(tiers)==3 and tiers[0][0]==2 and tiers[-1][1]>=cost*1.3
  assert all(tiers[i][0]<tiers[i+1][0]and tiers[i][1]>tiers[i+1][1]for i in range(2))
  xml=E.tostring(root,encoding='unicode');assert not root.findall(".//field[@id='skuStock']") and not root.findall(".//field[@id='skuId']")
  if category!=int(before['category_id']):
   root.append(field(E.Element('temporary'),'catId',value=category))
   xml=E.tostring(root,encoding='unicode')
  request={'param_product_top_publish_request':{'product_id':int(pid),'cat_id':category,'language':'en_US','xml':xml}}
  b.save(f/'prepared.json',{'family':family,'variant':variant,'source':source['url'],'source_artno':source['artno'],'title':title,'fields':FIELDS,'sku_count':len(colors)*len(p['sizes']),'colors':p['colors'],'sizes':[f'EU{n}'for n in p['sizes']],'tiers':tiers,'cost_analysis':{'source_cny':source['price_cny'],'fx_cny_per_usd':fx,'fx_source':'https://www.boc.cn/sourcedb/whpj/','fx_observed':'2026-10-13 10:57:20','fx_basis':'USD cashless buying 668.37 CNY per 100 USD','cost_usd':cost,'minimum_markup':min(price/cost-1 for _,price in tiers),'freight_service_tax':'Order-specific, not claimed included'},'inventory':'OMITTED_NOT_PHYSICAL_STOCK','source_truth':'Real current shoe and procurement entry; order availability still unconfirmed','company_bundle':'Approved V8 and canonical general FAQ preserved unchanged','request':request,'xml_sha256':hashlib.sha256(xml.encode()).hexdigest(),'expected_schema':contract.field_snapshot(root),'before_preserved':preserve(before)})
  print(pid,'PREPARED',len(colors)*len(p['sizes']),flush=True)
def preserve(p):
 x=copy.deepcopy(p)
 for k in ['gmt_modified','status','display','attributes','subject','keywords','main_image','product_sku','sourcing_trade','pc_detail_url','category_id']:x.pop(k,None)
 d=x.get('struct_detail')or{}
 for k in ['detail_image','product_summary']:d.pop(k,None)
 return x
def repair_attributes(family,api,cfg):
 for pid in TARGETS[family].values():
  f=BASE/'商品'/pid;ledger=f/'attribute_repair_once.json'
  assert not ledger.exists(),'Attribute repair already attempted: read back only'
  got=read_only_call(api,cfg,'alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'})
  p=got['product'];assert p['status']=='approved'
  rendered=read_only_call(api,cfg,'alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US'}})
  schema=E.fromstring(rendered['data']);root=pub.values_only(schema,operation='update',field_ids=['icbuCatProp']);cv=root.find('./field/complex-value')
  for name,texts in [('Season',['Autumn','Winter']if family=='HR030'else['Summer']),('Feature',['Fashion Trend'])]:
   definition=next(x for x in schema.findall("./field[@id='icbuCatProp']/fields/field")if x.get('name')==name)
   old=cv.find("./field[@id='"+definition.get('id')+"']")
   if old is not None:cv.remove(old)
   set_attr(schema,cv,name,texts)
  xml=E.tostring(root,encoding='unicode');request={'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US','xml':xml}}
  b.save(f/'attribute_repair_before_get.json',got);b.save(f/'attribute_repair_prepared.json',{'request':request,'expected_schema':contract.field_snapshot(root),'reason':'Replace retained concept-era All Seasons / Breathable with current source season and visible fashion profile. No inventory or commercial write.'})
  b.save(ledger,{'state':'OUTCOME_UNKNOWN','at':b.now(),'id':pid})
  res=api.top_call(cfg,'alibaba.icbu.product.schema.update',request);b.save(f/'attribute_repair_receipt.json',res)
  assert res.get('biz_success')is True and not api.api_error(res)
  b.save(ledger,{'state':'SUBMITTED','at':b.now(),'id':pid,'request_id':res.get('request_id')});print(pid,'ATTRIBUTE_REPAIR_SUBMITTED',flush=True)
def repair_gallery(family,api,cfg):
 assert family=='HR042'
 assets=b.load(BASE/family/'图片银行.json')['items']
 for variant,key in [('B','HERO_BLACK'),('C','HERO_WHITE')]:
  pid=TARGETS[family][variant];f=BASE/'商品'/pid;ledger=f/'gallery_repair_once.json';assert not ledger.exists(),'Already attempted: read back only'
  assert assets[key]['state']=='UPLOADED'
  got=read_only_call(api,cfg,'alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'});p=got['product'];assert p['status']=='approved'
  rendered=read_only_call(api,cfg,'alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US'}})
  schema=E.fromstring(rendered['data']);root=pub.values_only(schema,operation='update',field_ids=['scImages']);order=[key,'M2','M3','M4','M5','M6'];pub.set_main_images(root,[assets[k]for k in order])
  request={'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US','xml':E.tostring(root,encoding='unicode')}}
  b.save(f/'gallery_repair_before_get.json',got);b.save(f/'gallery_repair_prepared.json',{'request':request,'expected_schema':contract.field_snapshot(root),'image_roles':order,'reason':'Replace poster/collage primary with faithfully cleaned exact-color single-shoe hero; keep supporting wear/structure/assortment/size/factory images.'})
  b.save(ledger,{'state':'OUTCOME_UNKNOWN','at':b.now(),'id':pid});res=api.top_call(cfg,'alibaba.icbu.product.schema.update',request);b.save(f/'gallery_repair_receipt.json',res);assert res.get('biz_success')is True and not api.api_error(res)
  b.save(ledger,{'state':'SUBMITTED','at':b.now(),'id':pid,'request_id':res.get('request_id')});print(pid,'GALLERY_REPAIR_SUBMITTED',flush=True)
  b.save(f/'verification.json',{'state':'SUBMITTED_AFTER_GALLERY_REPAIR','at':b.now(),'status':'Pending fresh get/render/score','public_qa':'PENDING','reason':'Prior verification precedes latest scImages mutation and cannot be used as current pass.'})
def submit(family,api,cfg):
 for variant,pid in TARGETS[family].items():
  f=BASE/'商品'/pid;ledger=f/'update_once.json';assert not ledger.exists(),'Already submitted: read back only'
  plan=b.load(f/'prepared.json');before=b.load(f/'before_get.json')['product']
  fresh=read_only_call(api,cfg,'alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'});b.save(f/'prewrite_get.json',fresh);assert fresh['product']==before,'Target changed after preparation'
  xml=plan['request']['param_product_top_publish_request']['xml'];assert hashlib.sha256(xml.encode()).hexdigest()==plan['xml_sha256']
  b.save(ledger,{'state':'OUTCOME_UNKNOWN','at':b.now(),'request_sha256':b.sha(f/'prepared.json'),'authorization':'Owner 2026-10-13 explicitly directed source replacement of missing-source HR family, priority HR030/HR042, and title/gallery/detail optimization','id':pid})
  res=api.top_call(cfg,'alibaba.icbu.product.schema.update',plan['request']);b.save(f/'update_receipt.json',res)
  if api.api_error(res):b.save(ledger,{'state':'BUSINESS_REJECTED','response_file':str(f/'update_receipt.json'),'id':pid});print(pid,'REJECTED',flush=True);return
  assert res.get('biz_success') is True,res
  b.save(ledger,{'state':'SUBMITTED','id':pid,'at':b.now(),'request_id':res.get('request_id'),'trace_id':res.get('_trace_id_')});print(pid,'SUBMITTED',flush=True)
def verify(family,api,cfg):
 def one(pid):
  f=BASE/'商品'/pid
  if(f/'verification.json').exists():
   old=b.load(f/'verification.json');last=max((b.load(f/name).get('at','')for name in ['update_once.json','attribute_repair_once.json','gallery_repair_once.json','public_style_once.json','hero_quality_once.json']if(f/name).exists()),default='')
   if old.get('state')=='FORMAL_FIELDS_SCORE_PASS' and old.get('get_observed_at','')>last:print(pid,'UNCHANGED_FORMAL_PASS',flush=True);return
  got=read_only_call(api,cfg,'alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'});b.save(f/'after_get.json',got);p=got['product']
  if p['status']!='approved':b.save(f/'verification.json',{'state':'REVIEWING','at':b.now(),'status':p['status'],'display':p['display']});print(pid,'REVIEWING',flush=True);return
  r=read_only_call(api,cfg,'alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US'}});b.save(f/'after_render.json',r)
  enc=api.top_call(cfg,'alibaba.icbu.product.id.encrypt',{'product_id':pid,'language':'ENGLISH'});b.save(f/'score_product_id.json',{'request_id':enc.get('request_id'),'status':'AVAILABLE'if enc.get('secret_id')else'UNAVAILABLE'})
  assert enc.get('secret_id'),'Actual score requires supported encrypted product ID'
  s=read_only_call(api,cfg,'alibaba.icbu.product.score.get',{'product_id':enc['secret_id']});b.save(f/'score.json',s)
  b.save(f/'verification.json',{'state':'FORMAL_READ_NEEDS_FIELD_REVIEW','at':b.now(),'display':p['display'],'schema_available':bool(r.get('data'))});print(pid,'FORMAL_READ',flush=True)
 with ThreadPoolExecutor(max_workers=3)as pool:list(pool.map(one,TARGETS[family].values()))
if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf8');mode,family=sys.argv[1:]
 if mode=='prepare':prepare(family)
 else:
  api,cfg=b.api_client();{'bank':bank,'submit':submit,'verify':verify,'attributes':repair_attributes,'gallery':repair_gallery}[mode](family,api,cfg)
