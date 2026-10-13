from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import json,hashlib
W=Path(__file__).parent;O=W/'9968_execution';A=O/'assets';A.mkdir(parents=True,exist_ok=True);SOURCE=W/'MaryJane_selection/9968/published';records=[]
BG='#f7f6f1';INK='#203d35'
def font(n,b=False):return ImageFont.truetype(r'C:\Windows\Fonts\arialbd.ttf' if b else r'C:\Windows\Fonts\arial.ttf',n)
def text(im,s,x,y,n=32,b=False,width=None):
 d=ImageDraw.Draw(im);lines=[];line=''
 for word in s.split():
  test=(line+' '+word).strip()
  if width and d.textlength(test,font=font(n,b))>width and line:lines.append(line);line=word
  else:line=test
 lines.append(line)
 for line in lines:d.text((x,y),line,font=font(n,b),fill=INK);y+=n+9
 return y
def base(n,title=None):
 im=Image.new('RGB',(n,n),BG)
 if title:
  ImageDraw.Draw(im).rectangle((0,0,n,10),fill=INK);text(im,title,45,38,38 if n==1000 else 34,True,width=n-90)
 return im
def pic(im,path,box,crop=None):
 source=Image.open(path).convert('RGB');native=source.size
 if crop:source=source.crop(crop)
 size=source.size;factor=min(1,(box[2]-box[0])/source.width,(box[3]-box[1])/source.height);new=(round(source.width*factor),round(source.height*factor));source=source.resize(new,Image.Resampling.LANCZOS);im.paste(source,(round(box[0]+(box[2]-box[0]-source.width)/2),round(box[1]+(box[3]-box[1]-source.height)/2)))
 return {'source':str(path),'native':list(native),'crop':crop,'effective':list(size),'placed':list(new),'upscaled':False,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
def save(im,name,role,refs):
 p=A/(name+'.jpg');im.save(p,quality=96,subsampling=0);(A/'mobile').mkdir(exist_ok=True);im.resize((375,375),Image.Resampling.LANCZOS).save(A/'mobile'/(name+'.png'));records.append({'name':name,'path':str(p),'role':role,'dimensions':list(im.size),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'sources':refs,'product_redraw':False,'price_label':False})
im=base(800);refs=[pic(im,SOURCE/'00.jpg',(25,25,775,775))];save(im,'M1','Actual Grey shoe photograph; complete native scene',refs)
im=base(1000,'REAL COLOR CHOICES');refs=[]
for i,(color,k) in enumerate([('Grey','00'),('Green','01'),('Blue','02')]):
 x=[35,515,275][i];y=[125,125,555][i];refs.append(pic(im,SOURCE/(k+'.jpg'),(x,y,x+450,y+350)));text(im,color,x,y+365,34,True)
save(im,'M2','Three source-mapped Grey Green Blue shoes',refs)
im=base(1000,'SINGLE STRAP / CLOSED HEEL');refs=[pic(im,SOURCE/'04.jpg',(90,135,910,855))];text(im,'On-foot side profile',55,910,33);save(im,'M3','Actual on-foot opening and closed heel',refs)
im=base(1000,'STRAP & PANEL DETAILS');refs=[pic(im,SOURCE/'00.jpg',(40,150,720,730)),pic(im,SOURCE/'00.jpg',(755,260,970,505),(327,497,506,649))];text(im,'Single strap and visible stitching',50,785,36,True,width=900);text(im,'Review the actual shape and opening.',50,865,30,width=900);save(im,'M4','True strap and stitched panel construction; native detail crop',refs)
im=base(1000,'SOURCE SIZES: 35-40');refs=[pic(im,SOURCE/'05.jpg',(100,130,900,830))];text(im,'Send quantities for each color and size.',45,865,34,width=910);text(im,'Size labels; no US/EU conversion.',45,925,28,width=910);save(im,'M5','Size labels and buying inputs with complete Green shoes',refs)
co=json.loads((Path(r'C:\Users\spq\Documents\Codex\2026-10-02\task-8')/'5998/company_v3_manifest.json').read_text(encoding='utf-8'));cp=Path(co[0]['local_path'])
im=base(1000,'BEIQIANG B2B INQUIRIES');refs=[pic(im,SOURCE/'00.jpg',(40,135,660,685)),pic(im,cp,(690,180,975,650))];text(im,'Quanzhou Beiqiang',45,725,36,True);text(im,'Company profile / order-specific quotation',45,805,32,width=910);text(im,'Supply, packing and dispatch confirmed for your order.',45,885,29,width=910);save(im,'M6','Product-led supplier identity, no claim this style is own-factory made',refs)
im=base(1200,'MATERIALS & ASSEMBLY');refs=[pic(im,SOURCE/'01.jpg',(45,135,750,895))];text(im,'Synthetic leather upper',780,190,33,True,width=375);text(im,'Synthetic leather lining',780,320,32,width=375);text(im,'Rubber outsole',780,440,34,True,width=375);text(im,'PU insole',780,550,33,width=375);text(im,'Cemented construction',780,660,33,width=375);text(im,'Send any additional material specifications with your inquiry.',55,980,36,width=1090);save(im,'D1','Confirmed source materials; no guessed midsole or leather grade',refs)
im=base(1200,'OPENING & STRAP CONSTRUCTION');refs=[pic(im,SOURCE/'00.jpg',(60,155,810,925)),pic(im,SOURCE/'00.jpg',(875,280,1140,545),(327,497,506,649))];text(im,'One strap',860,645,36,True,width=290);text(im,'Closed heel',860,735,34,width=290);text(im,'Panel stitching',860,825,34,width=290);text(im,'Review the visible structure for your intended use.',60,1040,37,width=1080);save(im,'D2','Actual opening, heel and strap structure, no performance promise',refs)
im=base(1200,'BUILD YOUR COLOR & SIZE MIX');refs=[pic(im,SOURCE/'03.jpg',(60,150,1140,885))];text(im,'Grey / Green / Blue',60,925,42,True);text(im,'Listed sizes: 35 36 37 38 39 40',60,1010,38);text(im,'Specify a quantity for every requested color and size.',60,1090,32,width=1080);save(im,'D3','Assortment and exact source label matrix; no measured conversions',refs)
im=base(1200,'SEND YOUR ORDER REQUIREMENTS');refs=[pic(im,SOURCE/'02.jpg',(55,150,775,970))];y=220
for line in ['Color and size quantities','Total order quantity','Destination and packing','Required dispatch date']:
 y=text(im,line,805,y,34,True,width=340)+50
text(im,'Availability, samples, customization and dispatch arrangements are assessed for the order before quotation.',60,1020,34,width=1080);save(im,'D4','Practical procurement inputs with actual Blue shoes; no price card',refs)
manifest={'style':'9968','public_model':'BQ-MJ9968','assets':records,'company_manifest':co,'main6':True,'detail4':True,'no_AI_redraw':True,'no_price_labels':True};(O/'asset_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
sheet=Image.new('RGB',(1500,850),'white');d=ImageDraw.Draw(sheet)
for i,a in enumerate(records):
 im=Image.open(a['path']);im.thumbnail((285,360));x=(i%5)*300;y=(i//5)*420;sheet.paste(im,(x,y));d.text((x+8,y+370),a['name']+' '+a['role'][:30],font=font(17),fill=INK)
sheet.save(O/'production_contact.jpg');print('6 main + 4 distinct details; originals only; no inventory/price cards')
