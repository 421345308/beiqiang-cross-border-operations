from pathlib import Path
import json,hashlib,datetime,xml.etree.ElementTree as E,importlib.util,sys
from decimal import Decimal,ROUND_CEILING
sys.dont_write_bytecode=True
W=Path(__file__).parent;O=W/'805_execution';P=Path(r'C:\Users\spq\Desktop\贝强')
def save(n,j):(O/n).write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8')
price=[{'minimum_pairs':q,'markup':m,'USD_per_pair':float((Decimal(75)*(1+Decimal(m))/Decimal('6.6987')).quantize(Decimal('.01'),rounding=ROUND_CEILING))} for q,m in [(2,'0.50'),(50,'0.40'),(100,'0.30')]]
facts=json.loads('{"source_model": "805", "source_url": "https://yut.sooxie.com/detail/559264", "public_model": "BQ-D805", "category": 202240835, "source_cost_CNY": 75, "colors": ["Red", "Brown", "Blue"], "source_color_labels": ["Red", "Light Brown", "Blue"], "sizes": [38, 39, 40, 41, 42, 43, 44], "materials": {"upper": "Not specified", "lining": "PU", "outsole": "Rubber", "midsole": "Not specified", "insole": "Not specified (optional omitted)"}, "construction": "Glued; source structured attribute", "origin": "Not specified", "closure": "Slip-On", "title": "Men\'s Tassel Driving Moccasins with Segmented Rubber Soles", "keywords": ["mens tassel driving moccasins"], "inventory": "Omit optional inventory; no ready-stock guarantee", "product_summary": "Slip-on moc-toe shoes with double tassels, visible toe stitching and embossed surface texture. The actual photographs show five separate rubber contact pads and a small rear heel extension. Rubber outsole, PU lining and glued construction are specified by the source. Upper, midsole and insole compositions are not specified. Source colors are Red, Light Brown and Blue, with listed size labels 38-44; the Brown SKU corresponds to the pictured Light Brown shade. Fit and international size conversion are confirmed for the order. Send color-size quantities, destination, packing requirements and requested dispatch date for an order-specific quotation. No slip-resistance test, driving safety, handmade construction or ready-stock claim is made.", "FAQ": [{"question": "What materials and construction are specified?", "answer": "The source specifies a rubber outsole, PU lining and glued construction. Upper, midsole and insole compositions are not specified. Send additional material requirements with your inquiry for order-specific confirmation."}, {"question": "Which colors and sizes can I request?", "answer": "Source colors are Red, Light Brown and Blue, with listed size labels 38-44. The Brown SKU is the pictured Light Brown shade. Specify each color-size quantity; measured fit and international size conversion are confirmed for the order."}, {"question": "What sole and upper details are shown?", "answer": "Actual photos show separate rubber contact pads, a small rear heel extension, a slip-on opening, moc-toe stitching, embossed texture and double tassels. Driving moccasins describes the shoe style; no driving safety or tested grip performance is claimed."}, {"question": "What are the minimum and quantity prices?", "answer": "The listing minimum is 2 pairs. Indicative unit prices are USD 16.80 for 2-49 pairs, USD 15.68 for 50-99 pairs and USD 14.56 for 100 or more pairs. Final quotation depends on color-size mix, packing, destination and agreed terms; freight and taxes are confirmed separately."}, {"question": "Can I request samples or customization?", "answer": "Send the sample quantity, requested colors and any logo or packing requirements. Feasibility, applicable minimums, sample charges and customization options are assessed before quotation."}, {"question": "Are stock and dispatch guaranteed?", "answer": "No ready-stock or fixed dispatch promise is made. Provide quantities, destination, packing and requested dispatch date. Supply, per-size availability, payment terms and dispatch arrangements are confirmed during inquiry."}]}')
facts['pricing']={'CNY_per_USD':'6.6987','rate_basis':'Project frozen quotation FX; source marked cost75CNY, 50/40/30% markup, cent ceiling','tiers':price,'MOQ_pairs':2,'tier_basis':'2-pair inquiry minimum, 50/100 mixed color-size wholesale quotation thresholds; supplier minimum and inventory not guaranteed'}
assert [x['USD_per_pair'] for x in price]==[16.8,15.68,14.56]
save('facts_and_copy.json',facts)
bankpath=O/'upload_ledger.json'
if not bankpath.exists():print('Frozen materials, 21 SKU and price tiers',price);raise SystemExit
bank=json.loads(bankpath.read_text(encoding='utf-8'))['uploads'];assert len(bank)==13 and all(x['status']=='VERIFIED' for x in bank);assets={x['name']:dict(url=x['official_url'],file_id=x['file_id']) for x in bank}
company=json.loads((W/'9968_execution/company_v3_manifest.json').read_text(encoding='utf-8'));save('company_v3_manifest.json',company);co={x['role']:dict(url=x['official_url'],file_id=x['file_id']) for x in company}
B=P/'08_工具链/01_业务脚本/国际站扩品';s=importlib.util.spec_from_file_location('publisher805',B/'publish_hot_rank_hr_a_batch.py');pub=importlib.util.module_from_spec(s);s.loader.exec_module(pub)
schema=E.parse(O/'schema.xml').getroot();defs={x.get('id'):x for x in schema.findall('./field')};props={x.get('id'):x for x in defs['icbuCatProp'].findall('./fields/field')};r=E.Element('itemSchema')
def f(parent,k,t,v=None):
 n=E.SubElement(parent,'field',id=k,type=t)
 if v is not None:E.SubElement(n,'value').text=str(v)
 return n
f(r,'catId','input',202240835);ic=E.SubElement(f(r,'icbuCatProp','complex'),'complex-value')
def prop(k,label,vid):
 d=props[k];n=f(ic,k,d.get('type'));p=E.SubElement(n,'values') if d.get('type')=='multiCheck' else n;v=E.SubElement(p,'value');v.text=str(vid)
 custom=any(x.get('name')=='valueAttributeRule' and x.get('value')=='inputValue' for x in d.findall('./rules/rule'))
 if custom:v.set('inputValue',label)
 if int(vid)<0:assert int(vid)!=-1 and custom
 else:assert str(vid) in [x.get('value') for x in d.findall('./options/option')]
prop('p-1','Not specified',-2);prop('p-20700','Not specified',-2);prop('p-191290426','Rubber',next(q.get('value') for q in props['p-191290426'].findall('./options/option') if q.get('displayName','').lower()=='rubber'));prop('p-191290428','Not specified',-2);prop('p-191290430','PU',3323086);prop('p-200001153','Slip-On',190091228)
sp=E.SubElement(f(r,'saleProp','complex'),'complex-value');cols=E.SubElement(f(sp,'p-191288010','multiCheck'),'values');colors=[(c,next(q.get('value') for q in defs['saleProp'].find("./fields/field[@id='p-191288010']").findall('./options/option') if q.get('displayName','').lower()==c.lower())) for c in ['Red','Brown','Blue']]
for col,vid in colors:E.SubElement(cols,'value',inputValue=col,img=assets[col]['url']).text=vid
sizes=E.SubElement(f(sp,'p-222038415','multiCheck'),'values')
for z in range(38,45):E.SubElement(sizes,'value',inputValue='Size '+str(z)).text='-'+str(z)
sku=f(r,'sku','multiComplex')
for col,vid in colors:
 for z in range(38,45):
  cv=E.SubElement(sku,'complex-values');f(cv,'skuOuterId','input',f'BQ-D805-{col}-{z}');v=E.SubElement(f(cv,'props','multiInput'),'values')
  for pid,pvid,pname in [('191288010',vid,col),('222038415','-'+str(z),'Size '+str(z))]:E.SubElement(v,'value',propId=pid,propName='p-'+pid,propValueId=pvid,propValueName=pname).text=pid+':'+pvid
f(r,'productTitle','input',facts['title']);f(r,'productKeywords','complex');pub.set_keywords(r,' '.join(facts['keywords']));f(r,'scImages','complex');pub.set_main_images(r,[assets['M'+str(i)] for i in range(1,7)])
for k,t,v in [('priceUnit','singleCheck',5),('saleType','singleCheck','normal'),('scPrice','singleCheck',1),('minOrderQuantity','input',2)]:f(r,k,t,v)
lad=E.SubElement(f(r,'ladderPrice','complex'),'complex-value')
for i,t in enumerate(price):
 cv=E.SubElement(f(lad,'ladderPrice_'+str(i),'complex'),'complex-value');f(cv,'quantity','input',t['minimum_pairs']);f(cv,'price','input',f"{t['USD_per_pair']:.2f}")
# Source gross weight 0.80 kg is explicit; source volume has no units and is omitted.
f(r,'pkgWeight','input',.8);f(r,'productDescType','singleCheck',4)
for key,names,roles in [('detailImage',['D1','D2','D3','D4'],[350,300,350,350]),('companyImage',['C1','C2','C3','C4','C5'],[400,550,600,750,700])]:
 f(r,key,'multiComplex');opts={x.get('value'):x.get('displayName') for x in defs[key].findall("./fields/field[@id='gallery']/options/option")};assert all(str(q) in opts for q in roles);pub.set_gallery(r,key,[(assets if key=='detailImage' else co)[n] for n in names],[(q,opts[str(q)]) for q in roles])
f(r,'textDesc','input',facts['product_summary']);f(r,'companyDesc','input','Quanzhou Beiqiang Footwear & Apparel Co., Ltd. supports footwear wholesale inquiries. The company capability images below describe general business capabilities. Product-specific supply, samples, customization, packing and dispatch are assessed against your order requirements before quotation.')
faq=f(r,'companyFaqDesc','multiComplex')
for q in facts['FAQ']:
 cv=E.SubElement(faq,'complex-values');f(cv,'question','input',q['question']);f(cv,'answers','input',q['answer']);assert len(q['question'])<=150 and len(q['answer'])<=500
for d in props.values():
 if any(x.get('name')=='requiredRule' and x.get('value')=='true' for x in d.findall('./rules/rule')):assert ic.find("./field[@id='%s']"%d.get('id')) is not None,d.get('id')
for d in defs.values():
 if any(x.get('name')=='requiredRule' and x.get('value')=='true' for x in d.findall('./rules/rule')):assert r.find("./field[@id='%s']"%d.get('id')) is not None,d.get('id')
fields=[x.get('id') for x in r];listing=pub.prepare_scoped_listing(schema,r,operation='create',category_id=202240835,field_ids=fields,expected_model='BQ-D805')
(O/'intended_payload.xml').write_text(listing['xml'],encoding='utf-8');save('prepared_listing.json',listing)
source=json.loads((O/'schema.response.json').read_text(encoding='utf-8'));manifest={'operation':'create','category_id':202240835,'facts_reviewed':True,'source_evidence':['facts_and_copy.json','source/source_attributes.json','asset_manifest.json','visual_gate.json','dedup_gate.json'],'current_schema':'schema.xml','current_schema_sha256':hashlib.sha256((O/'schema.xml').read_bytes()).hexdigest(),'schema_request_id':source['request_id'],'schema_acquired_at':datetime.datetime.fromtimestamp((O/'schema.xml').stat().st_mtime,datetime.timezone.utc).isoformat(),'payload_xml':'intended_payload.xml','field_ids':fields,'dependency_ids':[],'expected_model':'BQ-D805'};save('publish_manifest.json',manifest)
assert listing['inventory_input']['status']=='omitted_all' and listing['inventory_input']['sku_count']==21
print('Prepared 6/4/5 images; 21 SKU; 6 FAQ; official model; optional stock omitted')
