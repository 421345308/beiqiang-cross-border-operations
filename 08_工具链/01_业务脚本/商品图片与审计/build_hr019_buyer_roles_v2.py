"""Extend HR019's editable native layouts with exact, proportionally placed photos.
No shoe retouching, recoloring, generated angles, cutouts or fabricated outsole.
"""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageOps
import hashlib,json,shutil,argparse
ROOT=Path(__file__).resolve().parents[3]
RAW=ROOT/'99_临时区/HR019_230630_2026-09-28/原始公开图'
OUT=ROOT/'02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21/06_确定性图稿/HR019_230630/ABC_buyer_roles_v2'
OUT.mkdir(parents=True,exist_ok=True)
FILES={'black':'ee8d4f62cdbc6520.png','angle':'76458ee812373bee.png','black_hand':'0fcd86b2d18ac9a6.png','red':'4a23f9cd5e5ac950.png','purple':'abd6d5f4d8638f95.png'}
INK='#243742';BLUE='#285d87';GRAY='#556575';BG='#fafbfd';PANEL='#eef3f7'
records=[]
parser=argparse.ArgumentParser();parser.add_argument('--revise-unuploaded',action='store_true');args=parser.parse_args()
if args.revise_unuploaded:
 assert not (ROOT/'99_临时区/HR019_完整实款重核_2026-09-29/ROOT_images_approved.json').exists(),'Do not revise approved or uploaded images.'
def font(n,b=False):return ImageFont.truetype('C:/Windows/Fonts/'+('arialbd.ttf' if b else 'arial.ttf'),n)
def txt(d,xy,s,n=30,b=False,color=INK,width=1104):
 assert d.textbbox((0,0),s,font=font(n,b))[2]<=width,(s,n,width)
 d.text(xy,s,font=font(n,b),fill=color)
def photo(im,key,box):
 x,y,w,h=box;src=Image.open(RAW/FILES[key]).convert('RGB');p=ImageOps.contain(src,(w,h),Image.Resampling.LANCZOS)
 im.paste(p,(x+(w-p.width)//2,y+(h-p.height)//2))
def save(role,im,keys,question,title):
 p=OUT/(role+'.png');assert not p.exists() or args.revise_unuploaded,'Version outputs are immutable; choose a new version for revisions.'
 im.save(p,optimize=True)
 records.append({'role':role,'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'buyerQuestion':question,'headline':title,'sources':[{'key':k,'path':str(RAW/FILES[k]),'sha256':hashlib.sha256((RAW/FILES[k]).read_bytes()).hexdigest()} for k in keys],'shoePixels':'exact full source photos with proportional placement; no crop or retouch'})
def hero(role,key,question):
 p=RAW/FILES[key];target=OUT/(role+p.suffix);assert not target.exists() or args.revise_unuploaded;shutil.copyfile(p,target)
 records.append({'role':role,'path':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'buyerQuestion':question,'headline':'Unaltered real photo','sources':[{'key':key,'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}],'shoePixels':'byte-identical original'})
def base(title,sub,h=1200):
 im=Image.new('RGB',(1200,h),BG);d=ImageDraw.Draw(im)
 txt(d,(48,32),title,43,True);txt(d,(48,96),sub,28,color=GRAY);d.line((48,144,1152,144),fill=BLUE,width=4)
 return im,d
def main(role,title,sub,keys,notes,question,mode='photo'):
 im,d=base(title,sub)
 if mode=='colors':
  for k,x,label in zip(keys,[30,425,820],['BLACK','RED','PURPLE']):
   photo(im,k,(x,210,350,600));txt(d,(x+95,825),label,29,True,width=300)
  txt(d,(105,990),'EU 36   37   38   39   40   41   42',38,True)
 elif mode=='grid':
  for k,x,label in zip(keys,[40,435,830],['BLACK','RED','PURPLE']):
   photo(im,k,(x,170,330,310));txt(d,(x+80,480),label,27,True,width=300)
  for i,size in enumerate(range(36,43)):
   x=265+i*124;d.rounded_rectangle((x,565,x+110,635),radius=8,fill=PANEL);txt(d,(x+30,582),str(size),30,True,width=100)
  for i,label in enumerate(['BLACK','RED','PURPLE']):
   y=685+i*117;txt(d,(52,y+24),label,28,True,width=200)
   for col in range(7):
    x=265+col*124;d.rounded_rectangle((x,y,x+110,y+82),radius=8,outline='#9bb3c5',width=2);txt(d,(x+25,y+27),'___',27,width=100)
 elif mode=='notes':
  photo(im,keys[0],(30,190,580,820))
  for i,(head,body) in enumerate(notes):
   y=230+i*205;d.rounded_rectangle((635,y,1150,y+155),radius=12,fill=PANEL)
   txt(d,(665,y+25),head,26,True,color=BLUE,width=450);txt(d,(665,y+75),body,30,width=450)
 elif mode=='prices':
  photo(im,keys[0],(30,185,560,810))
  for i,(head,body) in enumerate(notes):
   y=235+i*220;d.rounded_rectangle((625,y,1150,y+175),radius=12,fill=PANEL)
   txt(d,(655,y+30),head,28,True,color=BLUE,width=450);txt(d,(655,y+88),body,42,True,width=450)
 else:
  if len(keys)==1:photo(im,keys[0],(30,170,1140,760))
  else:
   for k,x in zip(keys,[25,615]):photo(im,k,(x,190,560,745))
  for i,(head,body) in enumerate(notes):
   y=945+i*75;txt(d,(55,y),head,28,True,color=BLUE,width=400);txt(d,(460,y),body,28,width=690)
 footer='Send pairs per color and EU size.' if mode=='grid' else ('Product prices in USD/pair. Freight quoted separately.' if mode=='prices' else 'Send selected color, EU size mix and quantity for a matched quote.')
 txt(d,(48,1135),footer,26,color=GRAY)
 save(role,im,keys,question,title)
def detail(role,title,sub,keys,rows,question):
 im,d=base(title,sub,1400)
 if len(keys)==1:photo(im,keys[0],(35,165,1130,665))
 else:
  for k,x in zip(keys,[25,615]):photo(im,k,(x,170,560,660))
 for i,(head,body) in enumerate(rows):
  y=880+i*104;d.rounded_rectangle((45,y,1155,y+90),radius=10,fill=PANEL)
  txt(d,(64,y+25),head,27,True,color=BLUE,width=325);txt(d,(410,y+25),body,28,width=725)
 txt(d,(48,1336),'Send color, EU size mix, pair quantity and destination for a quote.',25,color=GRAY)
 save(role,im,keys,question,title)

hero('A_M1','black','Does this exact casual sneaker suit my collection?')
hero('B_M1','red','Which slip-on walking-style shoe is being quoted?')
hero('C_M1','angle','What is the actual low-top shoe shape in three-quarter view?')
main('A_M2','THREE REAL COLOR OPTIONS','Actual product photos',['black','red','purple'],[],'Which actual colors and EU sizes are listed?','colors')
main('A_M3','SLIP-ON UPPER STRUCTURE','Actual three-quarter product view',['angle'],[('UPPER','Visible knit texture'),('CLOSURE','Pull-on opening'),('HEEL','Rear pull tab')],'What construction defines the casual style?','notes')
main('A_M4','MATERIAL SPECIFICATION','Product layers listed for this style',['red'],[('LINING','Cotton Fabric'),('MIDSOLE','PVC'),('OUTSOLE','PVC')],'Which confirmed material layers can I request?','notes')
main('A_M5','PLAN YOUR COLOR AND SIZE MIX','Fill in target pairs for each available combination',['black','red','purple'],[],'How can I send a precise 21-option assortment?','grid')
main('A_M6','REQUEST AN ASSORTMENT QUOTE','Your order inputs',['black_hand'],[('PRODUCT','Selected color'),('ASSORTMENT','EU size quantities'),('DELIVERY','Quantity + destination')],'What inputs are needed for an assortment quotation?','notes')
main('B_M2','ACTUAL SOLE SIDE PROFILE','Real hand-held view of the selected style',['black_hand'],[('MIDSOLE','PVC'),('OUTSOLE','PVC')],'Can I review the actual sidewall before specifying a sole requirement?')
main('B_M3','OPENING AND HEEL TAB','Actual slip-on shoe construction',['angle'],[('OPENING','Pull-on construction'),('HEEL TAB','Visible rear loop'),('SIZE REVIEW','Choose your EU size')],'What visible features should I review when selecting a size?','notes')
main('B_M4','COMPARE THE LISTED COLORS','Black / Red / Purple photographed',['black','red','purple'],[],'How do the actual color choices compare for my order?','colors')
main('B_M5','LINING AND SOLE REQUESTS','Confirmed layers for your specification brief',['red'],[('LINING','Cotton Fabric'),('MIDSOLE','PVC'),('OUTSOLE','PVC')],'Which layers should I include in my procurement specification?','notes')
main('B_M6','SEND YOUR EU SIZE RATIO','EU 36 37 38 39 40 41 42',['black_hand'],[('SIZE BREAKDOWN','Pairs per EU size'),('COLOR MIX','Pairs per color'),('TOTAL ORDER','Target pair quantity')],'How should I submit the size distribution for a quote?','notes')
main('C_M2','CASUAL COLOR PRESENTATION','Actual hand-held pair and side view',['purple','black_hand'],[('PURPLE / BLACK','Two photographed colors'),('CLOSURE','Slip-on design')],'How do selected colors look in real product photographs?')
main('C_M3','LOW-TOP SHAPE AND SIDEWALL','Complete product side view',['black'],[('PROFILE','Low-top slip-on shape'),('STRUCTURE','Layered sole sidewall')],'What silhouette will my buyers see?')
main('C_M4','CONFIRMED PRODUCT LAYERS','Lining and sole materials for this style',['black_hand'],[('LINING','Cotton Fabric'),('MIDSOLE','PVC'),('OUTSOLE','PVC')],'What exact confirmed material fields are available for my brief?','notes')
main('C_M5','RETAIL ASSORTMENT INPUTS','Black / Red / Purple | EU 36-42',['purple'],[('COLOR RATIO','Pairs per color'),('SIZE RATIO','Pairs per EU size'),('ORDER BRIEF','Quantity + destination')],'What assortment details let us quote my retail collection?','notes')
main('C_M6','QUANTITY PRICE TIERS','Current product prices for this listing',['red'],[('2+ PAIRS','USD 9.57'),('50+ PAIRS','USD 9.27'),('100+ PAIRS','USD 9.17')],'Which unit price applies to my target quantity?','prices')
for L,keys,kind in [('A',['black','red'],'CASUAL ASSORTMENT'),('B',['angle','black_hand'],'SLIP-ON SPECIFICATION'),('C',['purple','black'],'RETAIL COLLECTION')]:
 detail(L+'_D1',kind+' PROFILE','Real photos and visible product structure',keys,[('SHOE TYPE','Women\'s casual sneaker'),('CLOSURE','Slip-on / pull-on opening'),('UPPER LOOK','Visible knit texture'),('HEEL DETAIL','Rear pull tab')],'Can I identify the exact shoe and its visible construction?')
 if L=='A':
  detail(L+'_D2','COLOR AND EU SIZE CHOICES','Actual color options for your assortment',keys[::-1],[('COLOR OPTIONS','Black / Red / Purple'),('EU SIZE RANGE','36 37 38 39 40 41 42'),('ASSORTMENT','Send pairs per color and size'),('ORDER CHECK','Selected mix confirmed per order')],'Which choices should I include in my assortment request?')
  detail(L+'_D3','LINING AND SOLE MATERIALS','Confirmed product layers',keys[:1],[('LINING','Cotton Fabric'),('MIDSOLE','PVC'),('OUTSOLE','PVC'),('SPECIFICATION','Share additional material needs')],'Which source-confirmed layers are relevant to the order?')
 elif L=='B':
  detail(L+'_D2','EU SIZE AND FIT REVIEW','Include your fitting requirements in the inquiry',['angle'],[('LISTED EU SIZES','36 37 38 39 40 41 42'),('SIZE BREAKDOWN','Send target pairs per EU size'),('FIT REQUIREMENTS','Share fitting specifications'),('SAMPLE REVIEW','Confirm availability and cost')],'Which size and fitting inputs should be checked before ordering?')
  detail(L+'_D3','MATERIAL AND TEST BRIEF','Specify requirements before an order',['black_hand'],[('LINING','Cotton Fabric'),('SOLE LAYERS','PVC midsole + PVC outsole'),('TEST REQUESTS','Share required test standards'),('ORDER REVIEW','Results and costs to be confirmed')],'What materials and required tests should the buyer specify?')
 else:
  detail(L+'_D2','BUILD YOUR RETAIL ASSORTMENT','Selected colors, size ratios and order quantity',['red','purple'],[('LISTED COLORS','Black / Red / Purple'),('COLOR RATIO','Send target pairs per color'),('EU SIZE RATIO','Send pairs per size, EU 36-42'),('TOTAL QUANTITY','Add your target pair quantity')],'How should I describe a retail assortment?')
  detail(L+'_D3','QUANTITY PRICES FOR YOUR ORDER','Product prices in USD per pair',['black'],[('2+ PAIRS','USD 9.57 per pair'),('50+ PAIRS','USD 9.27 per pair'),('100+ PAIRS','USD 9.17 per pair'),('FREIGHT','Quoted for your destination')],'Which product price applies and what freight input is needed?')
 if L=='C':
  detail(L+'_D4','PRE-ORDER REVIEW CHECKLIST','Share your order and presentation requirements',['purple'],[('STYLE BRIEF','Color + EU size mix + pairs'),('PACKING NEEDS','Share bag, box or label needs'),('DESTINATION','Country and delivery requirements'),('SAMPLE REQUEST','Confirm availability and cost')],'Which order and packing inputs need review before quotation?')
 else:
  detail(L+'_D4',kind+' QUOTATION','Quantity prices in USD/pair and inquiry inputs',keys[1:],[('PRICE TIERS','2+: 9.57 | 50+: 9.27 | 100+: 9.17'),('ORDER INPUTS','Color + EU size mix + pairs'),('DESTINATION','Country and delivery requirements'),('SAMPLE REQUEST','Confirm availability and cost')],'What price tiers and order inputs are needed before quotation?')
assert len(records)==30 and len({r['sha256'] for r in records})==30
(OUT/'asset_manifest.json').write_text(json.dumps({'sourceModel':'230630','actor':'Root','stage':'PREPARED_NOT_REVIEWED_NOT_UPLOADED','records':records,'companyFive':'Existing approved v3 images unchanged','sameModelDecision':'MERGE_REVIEW','independentProductsProven':False,'sourcePhotoCount':5,'noOutsoleBottomPhoto':True,'priceEvidence':'99_临时区/HR019_完整实款重核_2026-09-29/A/current24_unwrapped.json'},ensure_ascii=False,indent=2),encoding='utf-8')
print('30 native layout assets prepared for full-frame Root review; no upload or product gallery write.')
