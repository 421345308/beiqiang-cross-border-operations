"""Task-scoped adaptation of the approved 9968 preparation; mature pub contract."""
from pathlib import Path
import json,hashlib,datetime,xml.etree.ElementTree as E,importlib.util,sys
from decimal import Decimal,ROUND_CEILING
sys.dont_write_bytecode=True
W=Path(__file__).resolve().parent;O=W/'F2888_execution';P=Path.home()/'Desktop'/'贝强'
def save(n,j):(O/n).write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
facts=json.loads((O/'facts_and_copy.json').read_text(encoding='utf-8'))
price=[{'minimum_pairs':q,'markup_percent':m,'USD_per_pair':float((Decimal(53)*(1+Decimal(m)/100)/Decimal('6.6987')).quantize(Decimal('.01'),rounding=ROUND_CEILING))} for q,m in [(2,50),(50,40),(100,30)]]
facts['price_policy']['tiers']=price;save('facts_and_copy.json',facts)
bank=json.loads((O/'upload_ledger.json').read_text(encoding='utf-8'))['uploads'];assert len(bank)==13 and all(x['status']=='VERIFIED' for x in bank)
assets={x['name']:dict(url=x['official_url'],file_id=x['file_id']) for x in bank}
company=json.loads((O/'company_v3_manifest.json').read_text(encoding='utf-8'));co={x['role']:dict(url=x['official_url'],file_id=x['file_id']) for x in company};assert len(co)==5
s=importlib.util.spec_from_file_location('publisher_F2888',P/'08_工具链/01_业务脚本/国际站扩品/publish_hot_rank_hr_a_batch.py');pub=importlib.util.module_from_spec(s);s.loader.exec_module(pub)
schema=E.parse(O/'schema.xml').getroot();defs={x.get('id'):x for x in schema.findall('./field')};props={x.get('id'):x for x in defs['icbuCatProp'].findall('./fields/field')};r=E.Element('itemSchema')
def f(parent,k,t,v=None):
 n=E.SubElement(parent,'field',id=k,type=t)
 if v is not None:E.SubElement(n,'value').text=str(v)
 return n
f(r,'catId','input',201339011);ic=E.SubElement(f(r,'icbuCatProp','complex'),'complex-value')
def prop(k,label,vid):
 d=props[k];n=f(ic,k,d.get('type'));p=E.SubElement(n,'values') if d.get('type')=='multiCheck' else n;v=E.SubElement(p,'value');v.text=str(vid)
 custom=any(x.get('name')=='valueAttributeRule' and x.get('value')=='inputValue' for x in d.findall('./rules/rule'))
 if custom:v.set('inputValue',label)
 if int(vid)<0:assert int(vid)!=-1 and custom
 else:assert str(vid) in [x.get('value') for x in d.findall('./options/option')]
prop('p-1','China',100000458);prop('p-191284187','Women',3374293);prop('p-191288212','Winter',3254739);prop('p-191290428','Not specified',-2);prop('p-191290426','Not specified',-2);prop('p-191290430','Plush',4141322);prop('p-20700','Not specified',-2)
prop('p-200000486','Round Toe',556500746)
sp=E.SubElement(f(r,'saleProp','complex'),'complex-value');cols=E.SubElement(f(sp,'p-191288010','multiCheck'),'values');colors=[('Khaki','-2'),('Black','3327837'),('Cream','-3')]
for col,vid in colors:
 d=defs['saleProp'].find("./fields/field[@id='p-191288010']");assert (int(vid)<-1 and any(x.get('value')=='inputValue' for x in d.findall('./rules/rule'))) or vid in [x.get('value') for x in d.findall('./options/option')]
 E.SubElement(cols,'value',inputValue=col,img=assets[col]['url']).text=vid
sizes=E.SubElement(f(sp,'p-222038415','multiCheck'),'values')
for z in range(35,43):E.SubElement(sizes,'value',inputValue='Size '+str(z)).text='-'+str(z)
sku=f(r,'sku','multiComplex')
for col,vid in colors:
 for z in range(35,43):
  cv=E.SubElement(sku,'complex-values');f(cv,'skuOuterId','input',f'BQ-WBF2888-{col}-{z}');v=E.SubElement(f(cv,'props','multiInput'),'values')
  for pid,pvid,pname in [('191288010',vid,col),('222038415','-'+str(z),'Size '+str(z))]:E.SubElement(v,'value',propId=pid,propName='p-'+pid,propValueId=pvid,propValueName=pname).text=pid+':'+pvid
f(r,'productTitle','input',facts['title']);f(r,'productKeywords','complex');pub.set_keywords(r,' '.join(facts['keywords']));f(r,'scImages','complex');pub.set_main_images(r,[assets['M'+str(i)] for i in range(1,7)])
for k,t,v in [('priceUnit','singleCheck',5),('saleType','singleCheck','normal'),('scPrice','singleCheck',1),('minOrderQuantity','input',2)]:f(r,k,t,v)
lad=E.SubElement(f(r,'ladderPrice','complex'),'complex-value')
for i,t in enumerate(price):
 cv=E.SubElement(f(lad,'ladderPrice_'+str(i),'complex'),'complex-value');f(cv,'quantity','input',t['minimum_pairs']);f(cv,'price','input',f"{t['USD_per_pair']:.2f}")
f(r,'pkgWeight','input',.5);f(r,'productDescType','singleCheck',4)
for key,names,roles in [('detailImage',['D1','D2','D3','D4'],[350,300,350,350]),('companyImage',['C1','C2','C3','C4','C5'],[400,550,600,750,700])]:
 f(r,key,'multiComplex');opts={x.get('value'):x.get('displayName') for x in defs[key].findall("./fields/field[@id='gallery']/options/option")};assert all(str(q) in opts for q in roles);pub.set_gallery(r,key,[(assets if key=='detailImage' else co)[n] for n in names],[(q,opts[str(q)]) for q in roles])
f(r,'textDesc','input',facts['product_summary']);f(r,'companyDesc','input','Quanzhou Beiqiang Footwear & Apparel Co., Ltd. supports footwear wholesale inquiries. These company capability images describe general business capabilities. Product-specific supply, samples, customization, packing and dispatch are assessed against your order requirements before quotation.')
faq=f(r,'companyFaqDesc','multiComplex');questions=list(facts['FAQ'])+[{'question':'What are the minimum and quantity prices?','answer':'The listing minimum is 2 pairs. Indicative prices are USD 11.87 for 2-49 pairs, USD 11.08 for 50-99 pairs and USD 10.29 for 100 or more pairs. Final quotation depends on the color-size mix, packing and agreed order terms; freight and taxes are confirmed separately.'}]
for q in questions:
 cv=E.SubElement(faq,'complex-values');f(cv,'question','input',q['question']);f(cv,'answers','input',q['answer']);assert len(q['question'])<=150 and len(q['answer'])<=500
for d in props.values():
 if any(x.get('name')=='requiredRule' and x.get('value')=='true' for x in d.findall('./rules/rule')):assert ic.find("./field[@id='%s']"%d.get('id')) is not None,d.get('id')
fields=[x.get('id') for x in r]
ctx=json.loads((O/'differentiation_review.json').read_text(encoding='utf-8'));ctx['candidate']['hero_review'].update(url=assets['M1']['url'],sha256=next(x['sha256'] for x in bank if x['name']=='M1'))
ctx['candidate']['hero_review']['aliases']=[assets['M1']['url'],assets['M1']['url'].replace('https:','')]
pack=json.loads((O/'task_pack.json').read_text(encoding='utf-8'));pack['hero_review']=ctx['candidate']['hero_review'];save('task_pack.json',pack)
# Fresh latest page and exact old formal snapshot are source evidence too.
ctx['evidence_files']=[x for x in ctx['evidence_files'] if x['path'] not in ['recent_catalog.flat.json','old_catalog_projection.json']]
for name in ['recent_catalog.flat.json','old_catalog_projection.json']:
 ctx['evidence_files'].append({'path':name,'sha256':sha(O/name),'kind':'catalog_snapshot'})
save('differentiation_review.json',ctx)
(O/'intended_payload.xml').write_text(E.tostring(r,encoding='unicode'),encoding='utf-8')
stamp=json.loads((O/'schema_timestamp.json').read_text(encoding='utf-8'))
manifest={'operation':'create','category_id':201339011,'facts_reviewed':True,'source_evidence':['facts_and_copy.json','asset_manifest.json','visual_gate.json','task_pack.json'],'current_schema':'schema.xml','current_schema_sha256':sha(O/'schema.xml'),'schema_request_id':stamp['request_id'],'schema_acquired_at':stamp['observed_at'],'payload_xml':'intended_payload.xml','field_ids':fields,'dependency_ids':[],'expected_model':'BQ-WBF2888','differentiation_review':'differentiation_review.json','differentiation_review_sha256':sha(O/'differentiation_review.json'),'task_pack':'task_pack.json','task_pack_sha256':sha(O/'task_pack.json')}
save('publish_manifest.json',manifest)
listing=pub.load_submission_manifest(O/'publish_manifest.json','create',None)
assert listing['differentiation_review']['status']=='PASS',listing['differentiation_review']
assert listing['inventory_input']['status']=='omitted_all' and listing['inventory_input']['sku_count']==24
(O/'intended_payload.xml').write_text(listing['xml'],encoding='utf-8');save('prepared_listing.json',listing)
print('Validated current-schema F2888: 24 SKU, 6/4/5 images, 6 FAQ, no inventory; ordinary HR056-A binding; ready for one create.',flush=True)
