"""Exact-ID authorized whole-shoe migration; serial writes, no write retries."""
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
from xml.etree import ElementTree as E
from collections import Counter
from urllib.parse import urlparse
import sys,json,copy,hashlib,re
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'02_Alibaba运营/05_扩品工程/执行记录/HR实源替换'
sys.path.insert(0,str(ROOT/'08_工具链/01_业务脚本/国际站扩品'))
import refresh_buyer_copy as b
import publish_hot_rank_hr_a_batch as pub
import schema_publish_contract as contract
from read_only_catalog import read_only_call,ReadBusinessError
SCOPE=b.load(BASE/'scope.json')
TARGETS=SCOPE['targets']
FIELDS=['icbuCatProp','saleProp','sku','productTitle','productKeywords','scImages','detailImage','textDesc','customMoreProperty','scPrice','ladderPrice']
PLANS={family:b.load(BASE/family/'事实与页面计划.json')for family in TARGETS}
RAW_PATHS={family:plan['source_assets_root']for family,plan in PLANS.items()}

def model_number(family,variant):
 return PLANS[family].get('model_numbers',{}).get(variant,f'{family}-{variant}')
def attribute_values(value):
 return value if isinstance(value,list)else[value]

def field(parent,fid,typ='input',value=None):
 x=E.SubElement(parent,'field',id=fid,type=typ)
 if value is not None:E.SubElement(x,'value').text=str(value)
 return x
def set_attr(schema,cv,name,texts):
 defs=[f for f in schema.findall("./field[@id='icbuCatProp']/fields/field")if f.get('name')==name];assert len(defs)==1,name
 d=defs[0];typ=d.get('type');assert typ in ['singleCheck','multiCheck']
 assert len(texts)==len(set(texts))and texts,'Attribute values must be nonempty and distinct'
 assert typ!='singleCheck'or len(texts)==1,'Single category attribute accepts only one reviewed value'
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
  if key=='M6':
   reusable=[]
   for previous in BASE.glob('*/图片银行.json'):
    if previous==f:continue
    candidate=b.load(previous).get('items',{}).get('M6',{})
    if candidate.get('state')=='UPLOADED'and candidate.get('sha256')==a['sha256']and candidate.get('file_id')and candidate.get('url'):
     reusable.append((previous,candidate))
   if reusable:
    previous,candidate=reusable[0]
    data['items'][key]={**a,'state':'UPLOADED','url':candidate['url'],'file_id':candidate['file_id'],'reused_official_upload_from':previous.relative_to(ROOT).as_posix(),'at':b.now()}
    b.save(f,data);print(family,key,'REUSED_OFFICIAL_IMAGE_BANK',flush=True);continue
  row={**a,'state':'OUTCOME_UNKNOWN','at':b.now()};data['items'][key]=row;b.save(f,data)
  res=api.upload_image(cfg,p,None);row['response']=res;b.save(f,data)
  r=res.get('upload_image_response',{});assert not api.api_error(res) and r.get('file_id')and r.get('photobank_url')
  url=r['photobank_url'].replace('http:','https:');url='https:'+url if url.startswith('//')else url
  assert urlparse(url).hostname=='sc04.alicdn.com'
  row.update(state='UPLOADED',url=url,file_id=str(r['file_id']));b.save(f,data);print(family,key,'UPLOADED',flush=True)
 data['state']='COMPLETE';b.save(f,data)
 b.save(BASE/family/'图片银行公开映射.json',{'family':family,'state':'COMPLETE','items':{key:{k:v for k,v in row.items()if k!='response'}for key,row in data['items'].items()},'scope':'Official public CDN asset identities and reviewed local hashes; uploaded images alone do not prove product submission or acceptance.'})
def prepare(family):
 p=PLANS[family];assets=b.load(BASE/family/'图片银行.json')['items'];source=b.load(ROOT/RAW_PATHS[family]/'source.json')
 assert source['artno']==p['source_artno'];fx=p.get('fx_cny_per_usd',6.6837);cost=source['price_cny']/fx
 for variant,pid in TARGETS[family].items():
  f=BASE/'商品'/pid
  if(f/'update_once.json').exists():print(pid,'EXISTING_WRITE_LEDGER_PREPARE_SKIPPED',flush=True);continue
  before=b.load(f/'before_get.json')['product'];schema=E.fromstring(b.load(f/'before_render.json')['data'])
  category=p.get('category_id',int(before['category_id']))
  if category!=int(before['category_id']):
   target=E.fromstring(b.load(BASE/family/'目标类目Schema.json')['data'])
   # Preserve each target's non-product values; definitions for rebuilt category
   # attributes come from the current destination schema, never the old category.
   old=schema.find("./field[@id='icbuCatProp']");schema.remove(old)
   schema.append(copy.deepcopy(target.find("./field[@id='icbuCatProp']")))
   old=schema.find("./field[@id='saleProp']");schema.remove(old)
   schema.append(copy.deepcopy(target.find("./field[@id='saleProp']")))
  fields=FIELDS+(['productGroup']if 'platform_group_id'in p else[])
  root=pub.values_only(schema,operation='update',field_ids=fields)
  if 'platform_group_id'in p:
   group_proof=b.load(BASE/family/'目标店内分组回读.json')['product_group']
   assert str(group_proof['group_id'])==str(p['platform_group_id'])and group_proof['group_name']==p['platform_group_name']and group_proof['parent_id']==-1
   definition=schema.find("./field[@id='productGroup']/fields/field[@id='first_group_id']");assert definition is not None and definition.get('type')=='input'
   group=root.find("./field[@id='productGroup']")
   for child in list(group):group.remove(child)
   field(E.SubElement(group,'complex-value'),'first_group_id','input',p['platform_group_id'])
  cp=root.find("./field[@id='icbuCatProp']")
  for child in list(cp):cp.remove(child)
  cv=E.SubElement(cp,'complex-value')
  for name,texts in [('Place of Origin',['China']),('Midsole Material',attribute_values(p.get('midsole','Other'))),('Outsole Material',attribute_values(p.get('outsole','Rubber'))),('Lining Material',attribute_values(p['lining'])),('Upper Material',attribute_values(p['upper'])),('Style',p['style']),('Closure Type',[p['closure']]),('Toe Style',[p.get('toe_style','Round Toe')])]:
   if name in p.get('category_attribute_omissions',[]):
    definitions=[x for x in schema.findall("./field[@id='icbuCatProp']/fields/field")if x.get('name')==name]
    assert len(definitions)<=1,'Ambiguous category attribute definition'
    if definitions:
     assert not any(r.get('name')=='requiredRule'and r.get('value')=='true'for r in definitions[0].findall('./rules/rule')),'Cannot omit mandatory category attribute'
    else:
     assert name in p.get('category_absent_attributes_reviewed',[]),'Absent attribute needs explicit current-schema review'
    continue
   set_attr(schema,cv,name,texts)
  for name,texts in [('Season',p['seasons']),('Feature',[p.get('feature','Fashion Trend')])]:set_attr(schema,cv,name,texts)
  for name,texts in p.get('extra_category_attributes',{}).items():set_attr(schema,cv,name,texts)
  cv.append(contract.serialize_product_model(schema,model_number(family,variant)))
  colors=[]
  sp=root.find("./field[@id='saleProp']")
  for child in list(sp):sp.remove(child)
  color_defs=[d for d in schema.findall("./field[@id='saleProp']/fields/field")if d.get('name','').casefold()=='color']
  assert len(color_defs)==1
  color_field=color_defs[0].get('id');color_axis=color_field.removeprefix('p-')
  cv=E.SubElement(sp,'complex-value');c=field(cv,color_field,'multiCheck');cs=E.SubElement(c,'values')
  for i,color in enumerate(p['colors'],1):
   key=re.sub(r'[^A-Z0-9]+','_',color.upper()).strip('_');vid=str(-500-i);colors.append((color,key,vid))
   E.SubElement(cs,'value',inputValue=color,img=assets['SKU_'+key]['url'],remark=color).text=vid
  sz=field(cv,'p-222038415','multiCheck');vs=E.SubElement(sz,'values')
  for n in p['sizes']:E.SubElement(vs,'value',inputValue=f'EU{n}').text=str(-800-n)
  sku=root.find("./field[@id='sku']")
  for child in list(sku):sku.remove(child)
  for color,key,cid in colors:
   for n in p['sizes']:
    row=E.SubElement(sku,'complex-values');field(row,'skuOuterId',value=f'{model_number(family,variant)}-{key}-EU{n}')
    props=field(row,'props','multiInput');vals=E.SubElement(props,'values')
    for prop,vid,name in [(color_axis,cid,color),('222038415',str(-800-n),f'EU{n}')]:E.SubElement(vals,'value',propId=prop,propName='p-'+prop,propValueId=vid,propValueName=name).text=prop+':'+vid
  contract.validate_sku_property_pairs(root)
  title=p['titles'][variant];assert len(title)<=128 and family not in title
  pub.set_direct_value(root,'productTitle',title);old=root.find("./field[@id='productKeywords']");root.remove(old)
  keyword_contract=contract.keyword_input_contract(schema)
  reviewed_keywords=[p['keywords']]if isinstance(p['keywords'],str)else p['keywords']
  submitted_keywords=reviewed_keywords[:min(keyword_contract['maximum'],len(keyword_contract['definitions']))]
  assert len(submitted_keywords)>=keyword_contract['minimum']
  root.append(contract.serialize_product_keywords(schema,submitted_keywords))
  order=['M1','M2','M3','M4','M5','M6']
  if family=='HR030'and variant=='B':order=['M2','M1','M3','M4','M5','M6']
  if family=='HR042'and variant=='B':order=['M2','M1','M3','M4','M5','M6']
  if family=='HR042'and variant=='C':order=['M3','M1','M2','M4','M5','M6']
  pub.set_main_images(root,[assets[k]for k in order]);pub.set_gallery(root,'detailImage',[assets['D'+str(n)]for n in range(1,5)],[(300,'Detail shot'),(350,'Other product images'),(350,'Other product images'),(350,'Other product images')])
  pub.set_direct_value(root,'textDesc',p['highlights']);pub.set_direct_value(root,'scPrice','1')
  more=root.find("./field[@id='customMoreProperty']")
  definition=schema.find("./field[@id='customMoreProperty']/fields/field[@id='customMoreProperty_0']")
  assert definition is not None and definition.get('type')=='complex'
  assert len(p['custom'][1])<=70
  for child in list(more):more.remove(child)
  outer=E.SubElement(more,'complex-value');v=E.SubElement(field(outer,definition.get('id'),definition.get('type')),'complex-value')
  for name,value in [('propName',p['custom'][0]),('valueName',p['custom'][1])]:
   attr=definition.find("./fields/field[@id='"+name+"']");assert attr is not None and attr.get('type')=='input'
   field(v,name,attr.get('type'),value)
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
  b.save(f/'prepared.json',{'family':family,'variant':variant,'source':source['url'],'source_artno':source['artno'],'title':title,'fields':fields,'color_axis_id':color_axis,'keyword_submission_selection':submitted_keywords,'keyword_schema_capacity':len(keyword_contract['definitions']),'sku_count':len(colors)*len(p['sizes']),'colors':p['colors'],'sizes':[f'EU{n}'for n in p['sizes']],'tiers':tiers,'cost_analysis':{'source_cny':source['price_cny'],'fx_cny_per_usd':fx,'fx_source':'https://www.boc.cn/sourcedb/whpj/','fx_observed':'2026-10-13 10:57:20','fx_basis':'USD cashless buying 668.37 CNY per 100 USD','cost_usd':cost,'minimum_markup':min(price/cost-1 for _,price in tiers),'freight_service_tax':'Order-specific, not claimed included'},'inventory':'OMITTED_NOT_PHYSICAL_STOCK','source_truth':'Real current shoe and procurement entry; order availability still unconfirmed','company_bundle':'Approved V8 and canonical general FAQ preserved unchanged','request':request,'xml_sha256':hashlib.sha256(xml.encode()).hexdigest(),'expected_schema':contract.field_snapshot(root),'before_preserved':preserve(before,fields)})
  print(pid,'PREPARED',len(colors)*len(p['sizes']),flush=True)
def preserve(p,fields=None):
 x=copy.deepcopy(p)
 for k in ['gmt_modified','status','display','attributes','subject','keywords','main_image','product_sku','sourcing_trade','pc_detail_url','category_id']:x.pop(k,None)
 if fields and 'productGroup'in fields:
  for k in ['group_id','group_name']:x.pop(k,None)
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
  f=BASE/'商品'/pid;ledger=f/'update_once.json'
  if ledger.exists():print(pid,'EXISTING_WRITE_LEDGER_SUBMISSION_SKIPPED',flush=True);continue
  if SCOPE.get('selection_policy')=='BACKEND_DATA_AND_COST_REVIEW':
   assert PLANS[family].get('selection_review',{}).get('state')=='REVIEWED_ADOPT','Latest owner requires backend-data and cost selection review before a new submission'
  plan=b.load(f/'prepared.json');before=b.load(f/'before_get.json')['product']
  fresh=read_only_call(api,cfg,'alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'});b.save(f/'prewrite_get.json',fresh);assert fresh['product']==before,'Target changed after preparation'
  xml=plan['request']['param_product_top_publish_request']['xml'];assert hashlib.sha256(xml.encode()).hexdigest()==plan['xml_sha256']
  b.save(ledger,{'state':'OUTCOME_UNKNOWN','at':b.now(),'request_sha256':b.sha(f/'prepared.json'),'authorization':'Owner 2026-10-13 explicitly directed source replacement of missing-source HR family, priority HR030/HR042, and title/gallery/detail optimization','id':pid})
  res=api.top_call(cfg,'alibaba.icbu.product.schema.update',plan['request']);b.save(f/'update_receipt.json',res)
  if api.api_error(res)or res.get('biz_success')is False:b.save(ledger,{'state':'BUSINESS_REJECTED','at':b.now(),'response_file':str(f/'update_receipt.json'),'id':pid,'request_id':res.get('request_id'),'message_code':res.get('msg_code')});print(pid,'BUSINESS_REJECTED',flush=True);continue
  assert res.get('biz_success') is True,res
  b.save(ledger,{'state':'SUBMITTED','id':pid,'at':b.now(),'request_id':res.get('request_id'),'trace_id':res.get('_trace_id_')});print(pid,'SUBMITTED',flush=True)
def verify(family,api,cfg):
 def one(pid):
  f=BASE/'商品'/pid
  if(f/'verification.json').exists():
   old=b.load(f/'verification.json');last=max((b.load(f/name).get('at','')for name in ['update_once.json','attribute_repair_once.json','gallery_repair_once.json','public_style_once.json','hero_quality_once.json','business_correction_once.json','optional_attribute_clear_once.json','title_repair_once.json']if(f/name).exists()),default='')
   if old.get('state')=='FORMAL_FIELDS_SCORE_PASS' and old.get('get_observed_at','')>last:print(pid,'UNCHANGED_FORMAL_PASS',flush=True);return
  got=read_only_call(api,cfg,'alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'});b.save(f/'after_get.json',got);p=got['product']
  if p['status']!='approved':b.save(f/'verification.json',{'state':'REVIEWING','at':b.now(),'status':p['status'],'display':p['display']});print(pid,'REVIEWING',flush=True);return
  r=read_only_call(api,cfg,'alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':int(p['category_id']),'language':'en_US'}});b.save(f/'after_render.json',r)
  enc=api.top_call(cfg,'alibaba.icbu.product.id.encrypt',{'product_id':pid,'language':'ENGLISH'});b.save(f/'score_product_id.json',{'request_id':enc.get('request_id'),'status':'AVAILABLE'if enc.get('secret_id')else'UNAVAILABLE'})
  assert enc.get('secret_id'),'Actual score requires supported encrypted product ID'
  try:s=read_only_call(api,cfg,'alibaba.icbu.product.score.get',{'product_id':enc['secret_id']})
  except ReadBusinessError as exc:
   evidence={'at':b.now(),'id':pid,**exc.api_evidence,'scope':'Read-only score unavailable; preserved get/render. No product write replay.'}
   b.save(f/'score_read_error.json',evidence)
   b.save(f/'verification.json',{'state':'FORMAL_READ_PENDING_SCORE','at':b.now(),'status':p['status'],'display':p['display'],'score_read_error':evidence})
   print(pid,'FORMAL_READ_PENDING_SCORE',exc.api_evidence.get('code'),exc.api_evidence.get('sub_code'),flush=True);return
  b.save(f/'score.json',s)
  b.save(f/'verification.json',{'state':'FORMAL_READ_NEEDS_FIELD_REVIEW','at':b.now(),'display':p['display'],'schema_available':bool(r.get('data'))});print(pid,'FORMAL_READ',flush=True)
 with ThreadPoolExecutor(max_workers=3)as pool:list(pool.map(one,TARGETS[family].values()))
if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf8');mode,family=sys.argv[1:]
 if mode=='prepare':prepare(family)
 else:
  api,cfg=b.api_client();{'bank':bank,'submit':submit,'verify':verify,'attributes':repair_attributes,'gallery':repair_gallery}[mode](family,api,cfg)
