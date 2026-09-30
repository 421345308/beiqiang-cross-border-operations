"""Extend the editable HR018 gallery layouts using exact supplier photos.
No generative shoe pixels, recoloring, new view, or geometric shoe transformation.
"""
from pathlib import Path
import json,hashlib,shutil,argparse
from PIL import Image,ImageDraw,ImageFont,ImageOps
ROOT=Path(__file__).resolve().parents[3]
RAW=ROOT/'99_临时区/HR018_候选核验'
OLD=ROOT/'02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21/06_确定性图稿/HR018_036'
OUT=OLD/'ABC_buyer_roles_v2';OUT.mkdir(parents=True,exist_ok=True)
INK='#1f3039';MUTED='#53666b';GREEN='#155b4d';BG='#fafaf8'
records=[]
parser=argparse.ArgumentParser();parser.add_argument('--revise-unuploaded',action='store_true');args=parser.parse_args()
def font(n,b=False):return ImageFont.truetype('C:/Windows/Fonts/'+('arialbd.ttf' if b else 'arial.ttf'),n)
def src(name):return RAW/name
photos={
 'studio':src('路崎036_图2.jpg'),'black_side':src('路崎036_图4_大.jpg'),
 'black_top':src('路崎036_图5.jpg'),'beige_front':src('路崎036_图3.jpg'),
 'beige_side':src('路崎036_详情原图/2z99grc3lges08jbm0bcdgr72ycf5pqk.jpg'),
 'beige_close':src('路崎036_详情原图/h47530w2y5v9dfo69448btlgt4s1y6sp.jpg'),
 'beige_top':src('路崎036_详情原图/uy77d2iil8pvdll91eqcmnpu94pwc96c.jpg'),
 'black_pair':src('路崎036_详情原图/xftxhws02nck38ob5eapqrdk8qgsv6qk.jpg'),
 'black_sku':src('路崎036_详情原图/ll40450zz76rj9y5qc6jn8x88knz9xas.jpg'),'beige_sku':src('路崎036_详情原图/ll40450zz76rj9y5qc6jn8x88knz9xas.jpg'),
 'upper':src('路崎036_详情原图/es4kmcjclgjv1vv08q0a7zdci7b5k1tq.jpg'),
 'tread':OLD/'HR018_036_M4_outsole.png'}
def image(key):
 im=Image.open(photos[key]).convert('RGB')
 # Existing editable native panel's source crop; excludes source marketing text.
 if key=='upper':im=im.crop((0,340,790,1102))
 if key=='tread':im=im.crop((50,170,950,990))
 if key=='black_sku':im=im.crop((20,340,390,558))
 if key=='beige_sku':im=im.crop((400,340,780,558))
 return im
def fitted(canvas,key,box):
 x,y,w,h=box;im=ImageOps.contain(image(key),(w,h),Image.Resampling.LANCZOS)
 canvas.paste(im,(x+(w-im.width)//2,y+(h-im.height)//2))
def text(draw,xy,s,size=32,b=False,color=INK,maxwidth=1104):
 assert draw.textbbox((0,0),s,font=font(size,b))[2]<=maxwidth,(s,size)
 draw.text(xy,s,font=font(size,b),fill=color)
def save(role,canvas,keys,question,title):
 path=OUT/(role+'.png');assert not path.exists() or args.revise_unuploaded,'Do not overwrite reviewed assets'
 canvas.save(path,optimize=True)
 records.append({'role':role,'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'buyerQuestion':question,'headline':title,'sources':[{'key':k,'path':str(photos[k]),'sha256':hashlib.sha256(photos[k].read_bytes()).hexdigest()} for k in keys],'shoePixels':'exact source pixels with proportional placement only; upper uses previously verified native crop'})
def hero(role,key,question):
 p=photos[key];target=OUT/(role+p.suffix);assert not target.exists() or args.revise_unuploaded;shutil.copyfile(p,target)
 records.append({'role':role,'path':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'buyerQuestion':question,'headline':'No added text','sources':[{'key':key,'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}],'shoePixels':'byte-identical unaltered source photo'})
def main(role,title,sub,keys,footer,question):
 im=Image.new('RGB',(1200,1200),BG);d=ImageDraw.Draw(im)
 text(d,(48,28),title,43,True);text(d,(49,88),sub,28,color=MUTED)
 if role=='C_M5':
  fitted(im,'black_sku',(35,190,550,320));fitted(im,'beige_sku',(615,190,550,320))
  text(d,(52,555),'YOUR QUANTITY BY COLOR AND EU SIZE',31,True)
  for col,size in enumerate(range(39,49)):
   x=190+col*94;d.rounded_rectangle((x,640,x+85,710),radius=8,fill='#edf4f1')
   text(d,(x+19,658),str(size),30,True,maxwidth=70)
  for row,label in enumerate(['BLACK','BEIGE']):
   y=755+row*120;text(d,(45,y+26),label,28,True,maxwidth=140)
   for col in range(10):
    x=190+col*94;d.rounded_rectangle((x,y,x+85,y+88),radius=8,outline='#92aaa3',width=2)
    text(d,(x+20,y+28),'___',26,color=MUTED,maxwidth=65)
  text(d,(52,1015),'Fill in target pairs for each cell when sending your inquiry.',27,color=MUTED)
 elif len(keys)==1:fitted(im,keys[0],(30,155,1140,930))
 else:
  for k,x in zip(keys,[25,615]):fitted(im,k,(x,180,560,845))
 if role=='A_M3':
  text(d,(235,820),'BLACK',33,True);text(d,(830,820),'BEIGE',33,True)
  text(d,(95,935),'EU 39   40   41   42   43   44   45   46   47   48',34,True)
 text(d,(48,1130),footer,27,color=MUTED)
 save(role,im,keys,question,title)
def detail(role,title,sub,keys,rows,footer,question):
 im=Image.new('RGB',(1200,1400),BG);d=ImageDraw.Draw(im)
 text(d,(48,33),title,43,True);text(d,(49,96),sub,28,color=MUTED)
 if len(keys)==1:fitted(im,keys[0],(25,155,1150,710))
 else:
  for k,x in zip(keys,[25,615]):fitted(im,k,(x,170,560,695))
 for n,(head,body) in enumerate(rows):
  y=905+n*97;d.rounded_rectangle((45,y-12,1155,y+74),radius=12,fill='#edf4f1')
  text(d,(65,y),head,27,True,color=GREEN,maxwidth=350)
  text(d,(400,y),body,28,maxwidth=725)
 text(d,(48,1345),footer,25,color=MUTED)
 save(role,im,keys,question,title)
hero('A_M1','studio','What exact casual sneaker is being offered?')
hero('B_M1','black_side','How does the actual shoe sit on the foot in side view?')
hero('C_M1','beige_front','Does the actual low-top sneaker suit a casual outfit?')
main('A_M2','MESH UPPER + LACE-UP','Actual upper view',['upper'],'Upper texture, lace path and toe shape shown.','Can I see upper construction clearly?')
main('A_M3','BLACK OR BEIGE','Two photographed color options',['black_sku','beige_sku'],'EU 39–48 | Send pairs per color and size.','Which actual colors and sizes can I select?')
main('A_M4','ACTUAL OUTSOLE VIEW','Photographed underside of this shoe',['tread'],'Review tread layout and outsole shape before ordering.','What does the real outsole look like?')
main('A_M5','MATERIAL SPECIFICATION','Mesh upper | Mesh lining | EVA midsole',['beige_top'],'Specify required outsole compound in your order brief.','Which material layers are confirmed?')
main('A_M6','BUILD YOUR QUOTE REQUEST','Color mix + EU size ratio + quantity',['black_pair'],'Add destination and packing preference for a matched quote.','What should I include in an inquiry?')
main('B_M2','SIDE PROFILE ON FOOT','Actual lace-up shoe and sole sidewall',['beige_side'],'EVA midsole | Compare the actual collar and sidewall profile.','How does the collar and sole profile sit on the foot?')
main('B_M3','TWO COLORS IN WEAR VIEWS','Black / Beige | Same sourced style',['black_pair','beige_close'],'EU 39–48 | Color-size availability confirmed per order.','How do both real colors look when worn?')
main('B_M4','LACING AND COLLAR VIEW','Actual pair photographed from above',['black_top'],'Share fitting requirements and preferred EU size.','What fit-related construction is visible?')
main('B_M5','SOLE CONSTRUCTION TO REVIEW','Actual side and underside photos',['black_side','tread'],'Specify required tests if you need verified performance data.','What sole evidence is available before requesting tests?')
main('B_M6','PLAN YOUR SIZE RATIO','EU 39 40 41 42 43 44 45 46 47 48',['beige_top'],'Send quantity per EU size to confirm your chosen assortment.','How should I submit a size assortment?')
main('C_M2','LOW-TOP CASUAL PROFILE','Actual shoe with casual trousers',['beige_close'],'Lace-up closure and complete side silhouette shown.','How does the shoe look with a casual outfit?')
main('C_M3','COMPARE YOUR COLOR ASSORTMENT','Black studio view / Beige wear view',['studio','beige_front'],'Both photographed colors are available in the listed EU size range.','Which color presentation suits my assortment?')
main('C_M4','UPPER AND LACE DETAILS','Actual Black side view',['black_side'],'Mesh upper texture and lace-up closure are visible.','Can I inspect the details beyond the hero?')
main('C_M5','COLOR-SIZE ASSORTMENT','Black / Beige | EU 39–48',['black_sku','beige_sku'],'Specify pairs for each color and size, not just a total.','How do I build the full assortment order?')
main('C_M6','PREPARE A RETAIL ORDER BRIEF','Quantity + destination + packing request',['beige_side'],'Final quotation and packing are confirmed for the actual order.','What procurement information is needed for my retail order?')
detail('A_D1','CONFIRMED MATERIAL LAYERS','Source-listed specification, illustrated by actual shoes',['studio','upper'],[('UPPER','Mesh'),('LINING','Mesh'),('MIDSOLE','EVA'),('OUTSOLE','Confirm compound in order specification')],'Confirm final material specifications for the actual order.','Which layers are source-confirmed, and what remains to confirm?')
detail('A_D2','COLOR AND SIZE MATRIX','Black and Beige product views',['black_sku','beige_sku'],[('COLORS','Black / Beige'),('EU SIZES','39 40 41 42 43 44 45 46 47 48'),('ORDER INPUT','Pairs per color and EU size'),('CONFIRM','Availability against the actual order')],'Confirm the color-size allocation for your actual order.','Can I specify every color-size line in my order?')
detail('A_D3','OUTSOLE AND UPPER EVIDENCE','Actual construction photos of the same shoe',['tread','upper'],[('UNDERSIDE','Photographed tread pattern'),('CLOSURE','Lace-up'),('UPPER','Mesh construction'),('TESTING','Required test method and target result')],'Use these photographs as a construction reference.','What structure is visible without relying on unverified marketing?')
detail('A_D4','REQUEST AN ORDER-SPECIFIC QUOTE','Use the exact photographed shoe as your reference',['studio'],[('ASSORTMENT','Black / Beige and EU 39–48 size ratio'),('VOLUME','Target pairs per order'),('PACKING','Bag / box request, if needed'),('DELIVERY','Destination and preferred trade terms')],'Price, packing, availability and dispatch terms confirmed per order.','How can I obtain a quote that matches my requirements?')
detail('B_D1','ACTUAL ON-FOOT SIDE VIEWS','Compare actual Black and Beige side profiles',['black_pair','beige_side'],[('PROFILE','Low collar and layered sole sidewall'),('MIDSOLE','Supplier-listed EVA'),('CLOSURE','Lace adjustment visible'),('FIT CHECK','Assess against the actual pair')],'Confirm fitting and sole specifications against the actual pair.','What can I judge from genuine wear photographs?')
detail('B_D2','LACE PATH AND SHOE OPENING','Actual top views in both colors',['black_top','beige_top'],[('CLOSURE','Lace-up'),('UPPER','Mesh'),('LINING','Mesh'),('FIT INPUT','Usual EU size and fitting requirements')],'Include fitting requirements when discussing your size assortment.','What fitting information should I request?')
detail('B_D3','WRITE A SIZE ASSORTMENT','EU range and photographed color choices',['beige_close'],[('EU RANGE','39–48'),('COLORS','Black / Beige'),('SIZE RATIO','Pairs for each EU size'),('VALIDATION','Confirm chosen sizes against actual pairs')],'Quantity by size helps match the quotation to the actual assortment.','How can I avoid an unclear size order?')
detail('B_D4','PACKING AND DESTINATION BRIEF','Share packing and delivery requirements',['black_side'],[('PACKING','Specify bag or box preference'),('SHIP TO','Country and destination'),('VOLUME','Total pairs and color-size mix'),('CONFIRM','Packing cost and dispatch terms per order')],'Packing format and cost are confirmed per order.','What order information is needed to confirm packing and dispatch?')
detail('C_D1','CASUAL OUTFIT AND SILHOUETTE','Front and side wear views of the actual Beige shoe',['beige_front','beige_close'],[('STYLE','Low-top casual sneaker'),('CLOSURE','Lace-up'),('DETAIL','Visible mesh upper and sidewall profile'),('ORDER REF','Use the actual photographed color')],'Front and side views show the same photographed shoe.','Does this shape suit the intended casual assortment?')
detail('C_D2','BLACK AND BEIGE ASSORTMENT','Actual studio and wear photographs',['studio','beige_side'],[('COLORS','Black / Beige'),('EU SIZES','39–48'),('COLOR MIX','Specify pairs for each color'),('SIZE MIX','Specify pairs for each EU size')],'Confirm the complete assortment when requesting a quotation.','How do I specify a retail-ready color and size mix?')
detail('C_D3','VISIBLE CONSTRUCTION DETAILS','Top and side views of the actual low-top shoe',['beige_top','black_side'],[('UPPER','Mesh'),('LINING','Mesh'),('MIDSOLE','EVA'),('CLOSURE','Lace-up')],'Outsole compound and any required tests belong in the order specification.','Which construction details support the product description?')
detail('C_D4','SEND YOUR ASSORTMENT BRIEF','Keep product, quantity and delivery requirements together',['beige_front'],[('PRODUCT','Photographed style and selected colors'),('ASSORTMENT','EU 39–48 size ratio and total pairs'),('PACKING','Requested format and requirements'),('DESTINATION','Country and preferred trade terms')],'Final commercial and packing terms are confirmed for the actual order.','What brief lets the supplier quote a usable retail assortment?')
assert len(records)==30 and len({r['sha256'] for r in records})==30
(OUT/'asset_manifest.json').write_text(json.dumps({'status':'ROOT_VISUAL_REVIEW_REQUIRED_NOT_UPLOADED','sourceModel':'Luqi 036','records':records,'sameModelDisclosure':'All ABC remain the same actual source shoe; different presentation is not proof of independent products or duplicate-listing immunity.'},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'count':len(records),'out':str(OUT)},ensure_ascii=False))


