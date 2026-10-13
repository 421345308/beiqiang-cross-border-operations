from pathlib import Path
import json
W=Path(__file__).parent;O=W/'805_execution'
base=(W/'build_3522_images.py').read_text(encoding='utf-8').split("im=Image.open(S/'03.jpg')")[0].replace('3522','805')
body=r'''
im=Image.open(S/'04.jpg').convert('RGB');save(im,'M1','Actual red pair and segmented sole',[{'source':str(S/'04.jpg'),'sha256':hashlib.sha256((S/'04.jpg').read_bytes()).hexdigest(),'upscaled':False,'crop':None}])
im=base(1000,'THREE REAL COLOR CHOICES');refs=[]
for i,(label,num) in enumerate([('Red','03'),('Light Brown','01'),('Blue','05')]):
 x=[35,515,275][i];y=[125,125,540][i];refs.append(pic(im,S/(num+'.jpg'),(x,y,x+450,y+345)));text(im,label,x,y+350,32,True,450)
save(im,'M2','Three genuine source colors, no recoloring',refs)
for name,title,num,line,role in [('M3','SEGMENTED RUBBER SOLE','04','Separate pads / rear heel extension','Actual sole layout, no grip claim'),('M4','TASSEL & MOC-TOE DETAILS','01','Visible stitching and embossed texture','Actual Brown tassels, stitching and texture'),('M5','LISTED SIZES: 38-44','05','Send each color and size quantity.','Exact source size labels with actual Blue pair')]:
 im=base(1000,title);refs=[pic(im,S/(num+'.jpg'),(90,135,910,835))];text(im,line,45,880,31,True,910)
 if name=='M5':text(im,'Fit and international size conversion confirmed for your order.',45,939,25,False,910)
 save(im,name,role,refs)
co=json.loads((W/'9968_execution/company_v3_manifest.json').read_text(encoding='utf-8'))
im=base(1000,'BEIQIANG B2B INQUIRIES');refs=[pic(im,S/'03.jpg',(40,135,660,710)),pic(im,Path(co[0]['local_path']),(690,170,975,675))];text(im,'Quanzhou Beiqiang',45,770,36,True);text(im,'Order-specific supply and packing quotation',45,847,29);text(im,'Company images describe general capabilities.',45,917,27);save(im,'M6','True company identity with actual red pair',refs)
im=base(1200,'MATERIAL INFORMATION');refs=[pic(im,S/'01.jpg',(40,160,735,925))]
for y,line in [(190,'Rubber outsole'),(335,'PU lining'),(485,'Upper composition: not specified'),(735,'Midsole and insole composition: not specified')]:text(im,line,770,y,32,True,370)
text(im,'Send additional material requirements for order-specific confirmation.',55,1050,33,False,1090);save(im,'D1','Confirmed Rubber and PU, truthful unknown layers',refs)
im=base(1200,'SOLE LAYOUT & SLIP-ON CONSTRUCTION');refs=[pic(im,S/'04.jpg',(45,150,800,980))]
for y,line in [(200,'Segmented rubber pads'),(405,'Rear heel extension'),(625,'Slip-on opening'),(820,'Visible moc-toe stitching')]:text(im,line,835,y,32,True,310)
text(im,'Review the actual pictured structure for your daily casual assortment.',55,1050,33,False,1090);save(im,'D2','Actual outsole and heel extension, no safety test claim',refs)
im=base(1200,'BUILD YOUR COLOR & SIZE MIX');refs=[]
for i,(label,num) in enumerate([('Red','03'),('Light Brown','01'),('Blue','05')]):
 x=30+i*390;refs.append(pic(im,S/(num+'.jpg'),(x,175,x+380,655)));text(im,label,x+15,700,35,True,365)
text(im,'Listed sizes: 38 39 40 41 42 43 44',55,850,40,True);text(im,'Provide a quantity for every requested color and size.',55,965,35);text(im,'Measurements and size conversion confirmed for your order.',55,1070,31);save(im,'D3','Actual colors, exact source size labels, no stock assertion',refs)
im=base(1200,'SEND YOUR ORDER REQUIREMENTS');refs=[pic(im,S/'05.jpg',(50,150,775,970))];y=200
for line in ['Color and size quantities','Destination and packing','Sample requirements','Required dispatch date']:y=text(im,line,805,y,34,True,340)+55
text(im,'Availability, customization, packing and dispatch are assessed for your order before quotation.',55,1030,34,False,1090);save(im,'D4','Practical procurement inputs with actual Blue pair',refs)
(O/'asset_manifest.json').write_text(json.dumps({'style':'805','public_model':'BQ-D805','assets':rows,'company_manifest':co,'main6':True,'detail4':True,'no_AI_redraw':True,'no_price_labels':True},ensure_ascii=False,indent=2),encoding='utf-8')
sheet=Image.new('RGB',(1500,850),'white');d=ImageDraw.Draw(sheet)
for i,a in enumerate(rows):
 im=Image.open(a['path']);im.thumbnail((285,360));x=i%5*300;y=i//5*420;sheet.paste(im,(x,y));d.text((x+8,y+370),a['name']+' '+a['role'][:28],font=font(17),fill=INK)
sheet.save(O/'production_contact.jpg');print('805 six main/four detail rendered from actual original pixels',flush=True)
'''
(W/'build_805_images.py').write_text(base+body,encoding='utf-8')
facts={'source_model':'805','source_url':'https://yut.sooxie.com/detail/559264','public_model':'BQ-D805','category':202240835,'source_cost_CNY':75,'colors':['Red','Brown','Blue'],'source_color_labels':['Red','Light Brown','Blue'],'sizes':list(range(38,45)),'materials':{'upper':'Not specified','lining':'PU','outsole':'Rubber','midsole':'Not specified','insole':'Not specified (optional omitted)'},'construction':'Glued; source structured attribute','origin':'Not specified','closure':'Slip-On','title':"Men's Tassel Driving Moccasins with Segmented Rubber Soles",'keywords':['mens tassel driving moccasins'],'inventory':'Omit optional inventory; no ready-stock guarantee','product_summary':'Slip-on moc-toe shoes with double tassels, visible toe stitching and embossed surface texture. The actual photographs show five separate rubber contact pads and a small rear heel extension. Rubber outsole, PU lining and glued construction are specified by the source. Upper, midsole and insole compositions are not specified. Source colors are Red, Light Brown and Blue, with listed size labels 38-44; the Brown SKU corresponds to the pictured Light Brown shade. Fit and international size conversion are confirmed for the order. Send color-size quantities, destination, packing requirements and requested dispatch date for an order-specific quotation. No slip-resistance test, driving safety, handmade construction or ready-stock claim is made.','FAQ':[
{'question':'What materials and construction are specified?','answer':'The source specifies a rubber outsole, PU lining and glued construction. Upper, midsole and insole compositions are not specified. Send additional material requirements with your inquiry for order-specific confirmation.'},
{'question':'Which colors and sizes can I request?','answer':'Source colors are Red, Light Brown and Blue, with listed size labels 38-44. The Brown SKU is the pictured Light Brown shade. Specify each color-size quantity; measured fit and international size conversion are confirmed for the order.'},
{'question':'What sole and upper details are shown?','answer':'Actual photos show separate rubber contact pads, a small rear heel extension, a slip-on opening, moc-toe stitching, embossed texture and double tassels. Driving moccasins describes the shoe style; no driving safety or tested grip performance is claimed.'},
{'question':'What are the minimum and quantity prices?','answer':'The listing minimum is 2 pairs. Indicative unit prices are USD 16.80 for 2-49 pairs, USD 15.68 for 50-99 pairs and USD 14.56 for 100 or more pairs. Final quotation depends on color-size mix, packing, destination and agreed terms; freight and taxes are confirmed separately.'},
{'question':'Can I request samples or customization?','answer':'Send the sample quantity, requested colors and any logo or packing requirements. Feasibility, applicable minimums, sample charges and customization options are assessed before quotation.'},
{'question':'Are stock and dispatch guaranteed?','answer':'No ready-stock or fixed dispatch promise is made. Provide quantities, destination, packing and requested dispatch date. Supply, per-size availability, payment terms and dispatch arrangements are confirmed during inquiry.'}]}
prefix=(W/'prepare_3522.py').read_text(encoding='utf-8').split('price=')[0].replace('3522','805')
tail=(W/'prepare_3522.py').read_text(encoding='utf-8').split("bankpath=O/'upload_ledger.json'")[1]
tail="bankpath=O/'upload_ledger.json'"+tail
tail=tail.replace('3522','805').replace('BQ-L805','BQ-D805').replace('range(39,47)','range(38,45)').replace("[('Black','3327837'),('Green','216016296'),('Beige','5715155')]","[(c,next(q.get('value') for q in defs['saleProp'].find(\"./fields/field[@id='p-191288010']\").findall('./options/option') if q.get('displayName','').lower()==c.lower())) for c in ['Red','Brown','Blue']]")
tail=tail.replace("prop('p-20700','Not specified',-2)","prop('p-20700','Rubber',next(q.get('value') for q in props['p-20700'].findall('./options/option') if q.get('displayName','').lower()=='rubber'))")
tail=tail.replace("prop('p-191290428','Genuine Leather',3242875)","prop('p-191290428','Not specified',-2)").replace("f(r,'pkgWeight','input',.9)","f(r,'pkgWeight','input',.8)").replace('sku_count\']==24','sku_count\']==21').replace('24 SKU','21 SKU')
frozen='price=[{\'minimum_pairs\':q,\'markup\':m,\'USD_per_pair\':float((Decimal(75)*(1+Decimal(m))/Decimal(\'6.6987\')).quantize(Decimal(\'.01\'),rounding=ROUND_CEILING))} for q,m in [(2,\'0.50\'),(50,\'0.40\'),(100,\'0.30\')]]\n'
frozen+='facts=json.loads('+repr(json.dumps(facts,ensure_ascii=False))+')\nfacts[\'pricing\']={\'CNY_per_USD\':\'6.6987\',\'rate_basis\':\'Project frozen quotation FX; source marked cost75CNY, 50/40/30% markup, cent ceiling\',\'tiers\':price,\'MOQ_pairs\':2,\'tier_basis\':\'2-pair inquiry minimum, 50/100 mixed color-size wholesale quotation thresholds; supplier minimum and inventory not guaranteed\'}\nassert [x[\'USD_per_pair\'] for x in price]==[16.8,15.68,14.56]\nsave(\'facts_and_copy.json\',facts)\n'
(W/'prepare_805.py').write_text(prefix+frozen+tail,encoding='utf-8')
print('805 implementation reuse only; exact facts and SKU are fresh source data',flush=True)
