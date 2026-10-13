from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import json,hashlib
W=Path(__file__).parent;O=W/'805_execution';A=O/'assets';A.mkdir(exist_ok=True);S=O/'source/published';BG='#f7f6f1';INK='#243c3a';rows=[]
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
