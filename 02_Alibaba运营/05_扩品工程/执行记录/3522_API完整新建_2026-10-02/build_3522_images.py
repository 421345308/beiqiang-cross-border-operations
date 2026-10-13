from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import json,hashlib
W=Path(__file__).parent;O=W/'3522_execution';A=O/'assets';A.mkdir(exist_ok=True);S=O/'source/published';BG='#f7f6f1';INK='#243c3a';rows=[]
def font(n,b=False):return ImageFont.truetype(r'C:\Windows\Fonts\arialbd.ttf' if b else r'C:\Windows\Fonts\arial.ttf',n)
def text(im,s,x,y,n=32,b=False,width=900):
 d=ImageDraw.Draw(im);line='';lines=[]
 for word in s.split():
  test=(line+' '+word).strip()
  if line and d.textlength(test,font=font(n,b))>width:lines.append(line);line=word
  else:line=test
 lines.append(line)
 for line in lines:d.text((x,y),line,font=font(n,b),fill=INK);y+=n+9
 return y
def base(n,title=None):
 im=Image.new('RGB',(n,n),BG)
 if title:ImageDraw.Draw(im).rectangle((0,0,n,10),fill=INK);text(im,title,45,38,38 if n==1000 else 34,True,n-90)
 return im
def pic(im,path,box,crop=None):
 source=Image.open(path).convert('RGB');native=source.size
 if crop:source=source.crop(crop)
 effective=source.size;factor=min(1,(box[2]-box[0])/source.width,(box[3]-box[1])/source.height);new=(round(source.width*factor),round(source.height*factor));source=source.resize(new,Image.Resampling.LANCZOS);im.paste(source,(round(box[0]+(box[2]-box[0]-source.width)/2),round(box[1]+(box[3]-box[1]-source.height)/2)));return {'source':str(path),'native':list(native),'crop':crop,'effective':list(effective),'placed':list(new),'upscaled':False,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
def save(im,n,role,refs):
 p=A/(n+'.jpg');im.save(p,quality=96,subsampling=0);mobile=A/'mobile';mobile.mkdir(exist_ok=True);im.resize((375,375),Image.Resampling.LANCZOS).save(mobile/(n+'.png'));rows.append({'name':n,'path':str(p),'role':role,'dimensions':list(im.size),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'sources':refs,'product_redraw':False,'price_label':False})
im=Image.open(S/'03.jpg').convert('RGB');save(im,'M1','Complete Beige single loafer, native product photo',[{'source':str(S/'03.jpg'),'native':[800,800],'crop':None,'placed':[800,800],'upscaled':False,'sha256':hashlib.sha256((S/'03.jpg').read_bytes()).hexdigest()}])
im=base(1000,'THREE REAL COLOR CHOICES');refs=[]
for i,(col,num) in enumerate([('Green','00'),('Black','01'),('Beige','03')]):
 x=[35,515,275][i];y=[130,130,550][i];refs.append(pic(im,S/(num+'.jpg'),(x,y,x+450,y+350)));text(im,col,x,y+365,34,True,450)
save(im,'M2','Green Black Beige source-mapped color choice',refs)
im=base(1000,'PLAIN VAMP / CLOSED HEEL');refs=[pic(im,S/'00.jpg',(90,130,910,820))];text(im,'Long U-shaped panel and visible stitching',50,860,33,True,900);text(im,'Review the actual slip-on shape.',50,925,28,False,900);save(im,'M3','Actual Green pair and closed slip-on structure',refs)
im=base(1000,'PERFORATED PANEL DETAILS');refs=[pic(im,S/'03.jpg',(30,145,725,735)),pic(im,S/'03.jpg',(755,260,985,570),(491,348,735,543))];text(im,'Visible holes and stitched edge',45,800,36,True,900);text(im,'A native detail crop; review the surface finish.',45,890,30,False,900);save(im,'M4','Real Beige perforation and stitching detail without performance claim',refs)
im=base(1000,'LISTED SIZES: 39-46');refs=[pic(im,S/'02.jpg',(90,135,910,815))];text(im,'Specify each color and size quantity.',45,865,34,False,910);text(im,'Source size labels; fit confirmed for your order.',45,925,28,False,910);save(im,'M5','Actual three-color wearing scene and exact size inquiry inputs',refs)
co=json.loads((W/'9968_execution/company_v3_manifest.json').read_text(encoding='utf-8'))
im=base(1000,'BEIQIANG B2B INQUIRIES');refs=[pic(im,S/'01.jpg',(40,135,660,695)),pic(im,Path(co[0]['local_path']),(690,160,975,675))];text(im,'Quanzhou Beiqiang',45,750,36,True);text(im,'Company profile / order-specific quotation',45,830,31);text(im,'Supply, packing and dispatch confirmed for your order.',45,910,28);save(im,'M6','Product-led Black pair with truthful company identity',refs)
im=base(1200,'CONFIRMED MATERIAL INFORMATION');refs=[pic(im,S/'00.jpg',(45,140,745,925))];text(im,'Cow suede upper',780,200,34,True,370);text(im,'PU lining',780,340,34,True,370);text(im,'Outsole composition: not specified',780,485,31,False,370);text(im,'Midsole composition: not specified',780,655,31,False,370);text(im,'Send any additional material requirements with your inquiry.',55,1020,36,False,1090);save(im,'D1','Confirmed upper and lining; unknown sole layers stated honestly',refs)
im=base(1200,'SLIP-ON SHAPE & PANEL CONSTRUCTION');refs=[pic(im,S/'03.jpg',(45,160,790,930)),pic(im,S/'03.jpg',(860,270,1160,620),(491,348,735,543))];text(im,'Plain vamp',845,680,35,True,310);text(im,'Closed heel',845,780,34,False,310);text(im,'Perforated surround',845,870,32,False,310);text(im,'Review the actual shape and opening for your assortment.',55,1045,36,False,1090);save(im,'D2','Beige actual side profile and native panel detail',refs)
im=base(1200,'BUILD YOUR COLOR & SIZE MIX');refs=[pic(im,S/'02.jpg',(65,150,1135,855))];text(im,'Black / Green / Beige',55,900,42,True);text(im,'Listed sizes: 39 40 41 42 43 44 45 46',55,990,35);text(im,'Send a quantity for every requested color and size.',55,1080,34);save(im,'D3','Three real colors, source size matrix, no stock promise',refs)
im=base(1200,'SEND YOUR ORDER REQUIREMENTS');refs=[pic(im,S/'01.jpg',(50,145,775,970))];y=200
for line in ['Color and size quantities','Total order quantity','Destination and packing','Required dispatch date']:y=text(im,line,805,y,34,True,340)+55
text(im,'Availability, samples, customization and dispatch arrangements are assessed for your order before quotation.',55,1030,34,False,1090);save(im,'D4','Black pair and practical procurement inputs without price card',refs)
(O/'asset_manifest.json').write_text(json.dumps({'style':'3522','public_model':'BQ-L3522','assets':rows,'company_manifest':co,'main6':True,'detail4':True,'no_AI_redraw':True,'no_price_labels':True},ensure_ascii=False,indent=2),encoding='utf-8')
sheet=Image.new('RGB',(1500,850),'white');d=ImageDraw.Draw(sheet)
for i,a in enumerate(rows):
 im=Image.open(a['path']);im.thumbnail((285,360));x=i%5*300;y=i//5*420;sheet.paste(im,(x,y));d.text((x+8,y+370),a['name']+' '+a['role'][:28],font=font(17),fill=INK)
sheet.save(O/'production_contact.jpg');print('3522 6main4details rendered; native pixels; no price/performance cards')
