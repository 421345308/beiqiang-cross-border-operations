from pathlib import Path
import json,hashlib,datetime,xml.etree.ElementTree as E,importlib.util,shutil
from decimal import Decimal,ROUND_CEILING
W=Path(__file__).parent;O=W/'9968_execution';P=Path(r'C:\Users\spq\Desktop\贝强');T8=Path(r'C:\Users\spq\Documents\Codex\2026-10-02\task-8')
def save(n,j):(O/n).write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8')
price=[{'minimum_pairs':q,'markup':m,'USD_per_pair':float((Decimal(60)*(1+Decimal(m))/Decimal('6.6987')).quantize(Decimal('.01'),rounding=ROUND_CEILING))} for q,m in [(2,'0.50'),(50,'0.40'),(100,'0.30')]]
facts={'source_model':'9968','source_url':'https://qdnx.sooxie.com/detail/2532759','public_model':'BQ-MJ9968','category':201152005,'source_cost_CNY':60,'colors':['Grey','Green','Blue'],'sizes':list(range(35,41)),'materials':{'upper':'Synthetic leather','lining':'Synthetic leather','outsole':'Rubber','insole':'PU','midsole':'Not specified'},'construction':'Cemented','closure':'Single hook-and-loop strap','title':"Women's Colorblock Mary Jane Flats with Hook-and-Loop Strap",'keywords':['women mary jane shoes'],'pricing':{'CNY_per_USD':'6.6987','rate_basis':'Project frozen quotation exchange rate; source marked procurement price 60 CNY; markup 50/40/30 percent by quantity; cent ceiling','tiers':price,'MOQ_pairs':2,'tier_basis':'2-pair inquiry minimum; 50 and 100 pair mixed color-size wholesale quotation thresholds, not supplier stock promise'},'inventory':'Omit all optional inventory fields; no actual stock assertion','product_summary':"Colorblock women's Mary Jane flats with a single hook-and-loop strap, closed toe and closed heel. Confirmed source materials: synthetic leather upper and lining, rubber outsole and PU insole; cemented construction. Three source colors: Grey, Green and Blue. Listed size labels: 35, 36, 37, 38, 39 and 40; measured fit and international size conversion are confirmed for the order. The midsole composition is not specified. Send your color-size quantities, destination, packing requirements and requested dispatch date for an order-specific quotation. Availability and supply terms are confirmed during inquiry; the listing does not guarantee ready stock.",'FAQ':[
{'question':'What materials are used?','answer':'The source specifies synthetic leather for the upper and lining, rubber for the outsole, PU for the insole and cemented construction. Midsole composition is not specified. Send any additional material requirements with your inquiry.'},
{'question':'Which colors and sizes can I request?','answer':'Listed source colors are Grey, Green and Blue, with size labels 35-40. Please provide a quantity for every requested color and size. Measurements, fit and any international size conversion are confirmed for your order.'},
{'question':'How does this shoe close?','answer':'The actual photos show a single hook-and-loop strap across the instep, a closed toe and a closed heel. Review the pictured shape and opening for your intended assortment.'},
{'question':'What are the minimum and quantity prices?','answer':'The listing minimum is 2 pairs. Indicative unit prices are USD 13.44 for 2-49 pairs, USD 12.54 for 50-99 pairs and USD 11.65 for 100 or more pairs. Final quotation depends on the color-size mix, packing, destination and agreed order terms; freight and any taxes are confirmed separately.'},
{'question':'Can I order samples or request customization?','answer':'Send your sample quantity or customization requirements with the color-size mix. Feasibility, sample charges, logo or packing options and any applicable minimums are assessed before quotation.'},
{'question':'Is stock or a dispatch date guaranteed?','answer':'No ready-stock or fixed dispatch promise is made. Provide your total quantity, destination, packing requirements and requested dispatch date. Supply, per-size availability, payment terms and the dispatch arrangement are confirmed for your inquiry.'}
]}
save('facts_and_copy.json',facts)
for n in ['source_attributes.json','published_manifest.json']:shutil.copyfile(W/'MaryJane_selection/9968'/n,O/n)
bankpath=O/'upload_ledger.json'
if not bankpath.exists():print('Frozen facts and pricing',price);raise SystemExit
bank=json.loads(bankpath.read_text(encoding='utf-8'))['uploads'];assert len(bank)==13 and all(x['status']=='VERIFIED' for x in bank);assets={x['name']:dict(url=x['official_url'],file_id=x['file_id']) for x in bank}
company=json.loads((T8/'5998/company_v3_manifest.json').read_text());save('company_v3_manifest.json',company);co={x['role']:dict(url=x['official_url'],file_id=x['file_id']) for x in company}
B=P/'08_工具链/01_业务脚本/国际站扩品';s=importlib.util.spec_from_file_location('publisher9968',B/'publish_hot_rank_hr_a_batch.py');pub=importlib.util.module_from_spec(s);s.loader.exec_module(pub)
schema=E.parse(O/'schema.xml').getroot();defs={x.get('id'):x for x in schema.findall('./field')};props={x.get('id'):x for x in defs['icbuCatProp'].findall('./fields/field')};r=E.Element('itemSchema')
def f(parent,k,t,v=None):
 n=E.SubElement(parent,'field',id=k,type=t)
 if v is not None:E.SubElement(n,'value').text=str(v)
 return n
f(r,'catId','input',201152005);ic=E.SubElement(f(r,'icbuCatProp','complex'),'complex-value')
def prop(k,label,vid):
 d=props[k];n=f(ic,k,d.get('type'));p=E.SubElement(n,'values') if d.get('type')=='multiCheck' else n;v=E.SubElement(p,'value');v.text=str(vid)
 custom=any(x.get('name')=='valueAttributeRule' and x.get('value')=='inputValue' for x in d.findall('./rules/rule'))
 if custom:v.set('inputValue',label)
 if int(vid)<0:assert int(vid)!=-1 and custom
 else:assert str(vid) in [x.get('value') for x in d.findall('./options/option')]
prop('p-1','China',100000458);prop('p-210194982','Synthetic',16369367);prop('p-20700','Not specified',-2);prop('p-191290430','Synthetic leather',-2);prop('p-191290426','Rubber',3338114);prop('p-200000388','Hook & Loop',159296723)
sp=E.SubElement(f(r,'saleProp','complex'),'complex-value');cols=E.SubElement(f(sp,'p-191288010','multiCheck'),'values');colors=[('Grey','3483425'),('Green','216016296'),('Blue','123085')]
for col,vid in colors:E.SubElement(cols,'value',inputValue=col,img=assets[col]['url']).text=vid
sizes=E.SubElement(f(sp,'p-222038415','multiCheck'),'values')
for z in range(35,41):E.SubElement(sizes,'value',inputValue='Size '+str(z)).text='-'+str(z)
sku=f(r,'sku','multiComplex')
for col,vid in colors:
 for z in range(35,41):
  cv=E.SubElement(sku,'complex-values');f(cv,'skuOuterId','input',f'BQ-MJ9968-{col}-{z}');v=E.SubElement(f(cv,'props','multiInput'),'values')
  for pid,pvid,pname in [('191288010',vid,col),('222038415','-'+str(z),'Size '+str(z))]:E.SubElement(v,'value',propId=pid,propName='p-'+pid,propValueId=pvid,propValueName=pname).text=pid+':'+pvid
f(r,'productTitle','input',facts['title']);f(r,'productKeywords','complex');pub.set_keywords(r,' '.join(facts['keywords']));f(r,'scImages','complex');pub.set_main_images(r,[assets['M'+str(i)] for i in range(1,7)])
for k,t,v in [('priceUnit','singleCheck',5),('saleType','singleCheck','normal'),('scPrice','singleCheck',1),('minOrderQuantity','input',2)]:f(r,k,t,v)
lad=E.SubElement(f(r,'ladderPrice','complex'),'complex-value')
for i,t in enumerate(price):
 cv=E.SubElement(f(lad,'ladderPrice_'+str(i),'complex'),'complex-value');f(cv,'quantity','input',t['minimum_pairs']);f(cv,'price','input',f"{t['USD_per_pair']:.2f}")
# Source gross weight is directly recorded as 0.50 kg; volume unknown omitted.
f(r,'pkgWeight','input',.5);f(r,'productDescType','singleCheck',4)
for key,names,roles in [('detailImage',['D1','D2','D3','D4'],[350,300,350,350]),('companyImage',['C1','C2','C3','C4','C5'],[400,550,600,750,700])]:
 f(r,key,'multiComplex');opts={x.get('value'):x.get('displayName') for x in defs[key].findall("./fields/field[@id='gallery']/options/option")};assert all(str(q) in opts for q in roles);pub.set_gallery(r,key,[(assets if key=='detailImage' else co)[n] for n in names],[(q,opts[str(q)]) for q in roles])
f(r,'textDesc','input',facts['product_summary']);f(r,'companyDesc','input','Quanzhou Beiqiang Footwear & Apparel Co., Ltd. supports footwear wholesale inquiries. The company capability images below describe general business capabilities. Product-specific supply, samples, customization, packing and dispatch are assessed against your order requirements before quotation.')
faq=f(r,'companyFaqDesc','multiComplex')
for q in facts['FAQ']:
 cv=E.SubElement(faq,'complex-values');f(cv,'question','input',q['question']);f(cv,'answers','input',q['answer']);assert len(q['question'])<=150 and len(q['answer'])<=500
for d in props.values():
 if any(x.get('name')=='requiredRule' and x.get('value')=='true' for x in d.findall('./rules/rule')):assert ic.find("./field[@id='%s']"%d.get('id')) is not None
for d in defs.values():
 if any(x.get('name')=='requiredRule' and x.get('value')=='true' for x in d.findall('./rules/rule')):assert r.find("./field[@id='%s']"%d.get('id')) is not None,d.get('id')
fields=[x.get('id') for x in r];listing=pub.prepare_scoped_listing(schema,r,operation='create',category_id=201152005,field_ids=fields,expected_model='BQ-MJ9968')
# Persist the exact prepared payload, including official product model inputValue.
(O/'intended_payload.xml').write_text(listing['xml'],encoding='utf-8');save('prepared_listing.json',listing)
source=json.loads((O/'schema.response.json').read_text(encoding='utf-8'));manifest={'operation':'create','category_id':201152005,'facts_reviewed':True,'source_evidence':['facts_and_copy.json','source_attributes.json','asset_manifest.json','visual_gate.json','dedup_gate.json'],'current_schema':'schema.xml','current_schema_sha256':hashlib.sha256((O/'schema.xml').read_bytes()).hexdigest(),'schema_request_id':source['request_id'],'schema_acquired_at':datetime.datetime.fromtimestamp((O/'schema.xml').stat().st_mtime,datetime.timezone.utc).isoformat(),'payload_xml':'intended_payload.xml','field_ids':fields,'dependency_ids':[],'expected_model':'BQ-MJ9968'};save('publish_manifest.json',manifest)
assert listing['inventory_input']['status']=='omitted_all' and listing['inventory_input']['sku_count']==18
print('Prepared 6/4/5 images; 18 SKU; 6 FAQ; official model; all optional stock omitted')
