"""Build a source-mapped catalogue and photographic cards from verified local inputs.

Contact configuration and customer information stay local. No network calls.
"""
import argparse
import json
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, ImageDraw, ImageFont, ImageChops
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

NAVY = '#152D39'
TEAL = '#167C7B'
INK = '#263D48'
GREY = '#64747C'
PAPER = '#F3F6F4'
FONT_DIR = Path('C:/Windows/Fonts')
pdfmetrics.registerFont(TTFont('Regular', str(FONT_DIR / 'arial.ttf')))
pdfmetrics.registerFont(TTFont('Bold', str(FONT_DIR / 'arialbd.ttf')))


def text(c, x, y, value, size=11, color=INK, bold=False):
    c.setFillColor(HexColor(color))
    c.setFont('Bold' if bold else 'Regular', size)
    c.drawString(x, y, value)


def wrap(c, value, x, y, width, size=11, leading=17, color=INK, bold=False):
    words = value.split()
    line = ''
    for word in words:
        trial = f'{line} {word}'.strip()
        if pdfmetrics.stringWidth(trial, 'Bold' if bold else 'Regular', size) > width and line:
            text(c, x, y, line, size, color, bold)
            y -= leading
            line = word
        else:
            line = trial
    if line:
        text(c, x, y, line, size, color, bold)
        y -= leading
    return y


def photo(c, path, x, y, width, height, crop=False, trim_white=False):
    with Image.open(path) as im:
        im = im.convert('RGB')
        if trim_white:
            diff=ImageChops.difference(im,Image.new('RGB',im.size,'white')).convert('L')
            box=diff.point(lambda p:255 if p>12 else 0).getbbox()
            if box:
                padding=max(6,round(max(box[2]-box[0],box[3]-box[1])*0.03))
                im=im.crop((max(0,box[0]-padding),max(0,box[1]-padding),
                            min(im.width,box[2]+padding),min(im.height,box[3]+padding)))
        if crop:
            im = ImageOps.fit(im, (round(width * 2), round(height * 2)))
        im.thumbnail((1000,900) if width<300 else (1400,1100))
        encoded=BytesIO()
        im.save(encoded,format='JPEG',quality=78 if width<300 else 86,optimize=True)
        encoded.seek(0)
        c.drawImage(ImageReader(encoded), x, y, width, height,
                    preserveAspectRatio=True, anchor='c', mask='auto')


def qr(c, url, x, y, size):
    obj = QrCodeWidget(url, barLevel='M')
    x1, y1, x2, y2 = obj.getBounds()
    drawing = Drawing(size, size, transform=[size/(x2-x1), 0, 0, size/(y2-y1), 0, 0])
    drawing.add(obj)
    renderPDF.draw(drawing, c, x, y)
    c.linkURL(url, (x, y, x+size, y+size), relative=0)


def frame(c, page, section):
    c.setFillColor(HexColor(TEAL))
    c.rect(0, 832, 595, 10, fill=1, stroke=0)
    text(c, 40, 802, 'BEIQIANG', 13, NAVY, True)
    text(c, 355, 803, 'FOOTWEAR COLLECTION  /  2026', 8, GREY)
    c.setStrokeColor(HexColor('#DCE4E2'))
    c.line(40, 45, 555, 45)
    text(c, 40, 28, section, 8, GREY)
    text(c, 528, 28, f'{page:02}', 8, GREY)


def build_catalogue(root, data_dir, out, cfg):
    public = json.loads((data_dir/'catalogue_public_data.json').read_text(encoding='utf-8-sig'))
    mapping = json.loads((data_dir/'source_mapping_internal.json').read_text(encoding='utf-8-sig'))
    ledger = json.loads((root/'02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json').read_text(encoding='utf-8-sig'))
    products = {p['id']: p for p in ledger['products']}
    verified = {}
    for row in mapping:
        if row.get('identity') != 'OWN_FACTORY_ORIGINAL_PACKAGE':
            continue
        code = row['code']
        if not Path(row['original_package']).is_dir():
            raise ValueError(f'Missing original package: {code}')
        if not products.get(code, {}).get('raw_packages'):
            raise ValueError(f'No raw-package ledger mapping: {code}')
        verified[code] = row
    items = {r['code']: r for r in public if r['code'] in verified}
    groups = [
        ('Start your shortlist', ['BQ001','BQ003','BQ004','BQ007','BQ018','BQ020','BQ010','BQ009']),
        ('Knit slip ons', ['BQ011','BQ017','BQ022','BQ023','BQ024','BQ025','BQ028']),
        ('Lace up casual', ['BQ005','BQ006','BQ019','BQ021','BQ026','BQ027','BQ031']),
        ('More silhouettes', ['BQ029','BQ008']),
        ('Junior size styles', ['BQ016','BQ030']),
    ]
    codes = [k for _, group in groups for k in group]
    assert len(codes) == len(set(codes)) == len(items) == 26
    path = out/'Beiqiang_Factory_Collection.pdf'
    c = canvas.Canvas(str(path), pagesize=(595,842))
    c.setTitle('Beiqiang Factory Collection | Brand Development & Factory Visit')
    c.setAuthor(cfg['company'])
    c.setFillColor(HexColor(NAVY)); c.rect(0,0,595,842,fill=1,stroke=0)
    text(c, 40, 792, 'BEIQIANG', 21, '#FFFFFF', True)
    text(c, 40, 742, 'FOOTWEAR', 43, '#FFFFFF', True)
    text(c, 40, 691, 'FACTORY COLLECTION', 29, '#FFFFFF', True)
    text(c, 41, 655, '26 styles. A starting point for your own brand.', 13, '#BCD7D4')
    hero = out/'cover_factory.jpg'
    photo(c, hero, 40, 320, 515, 290, crop=True)
    text(c, 40, 283, 'KNIT  /  CASUAL  /  SLIP ON  /  JUNIOR', 11, '#BCD7D4', True)
    wrap(c, 'Explore model codes, real product photographs, colors and documented size ranges. Bring your shortlist to our factory visit.', 40, 246, 490, 13, 20, '#FFFFFF')
    text(c, 40, 128, cfg['company'], 11, '#FFFFFF')
    text(c, 40, 105, 'Quanzhou, Fujian, China  |  October 2026', 10, '#BCD7D4')
    text(c, 40, 70, 'OEM / ODM discussions for selected models', 10, '#BCD7D4')
    c.showPage()
    page = 2
    frame(c,page,'BUILD YOUR FIRST COLLECTION')
    text(c,40,750,'From an idea to a clear shortlist',25,NAVY,True)
    wrap(c,'You do not need a finished collection to begin the conversation. Choose the shapes you like, then discuss your market and brand requirements with us.',40,714,510,12,19)
    steps = [
        ('01','Choose a direction','Tell us your target customer, sales market and preferred retail price range.'),
        ('02','Shortlist 3-5 models','Use the model codes in this catalogue. Select initial colors and size requirements.'),
        ('03','Review your brand details','Discuss logo placement, materials, colors and packaging for the selected models. Feasibility is reviewed per model.'),
        ('04','Define the sample','Agree sample purpose, specification, cost, timing and review criteria before proceeding.'),
        ('05','Confirm the order plan','Review quantities, size ratios, packing, price and lead time against the agreed sample.'),
    ]
    y = 632
    for n,title,body in steps:
        text(c,40,y,n,22,TEAL,True)
        text(c,90,y+2,title,15,NAVY,True)
        wrap(c,body,90,y-22,452,11,17)
        y-=99
    c.setFillColor(HexColor(PAPER)); c.roundRect(40,65,515,58,7,fill=1,stroke=0)
    wrap(c,'Factory visit: review selected samples, discuss development priorities and agree the next practical step. Visit arrangements are confirmed directly.',54,102,485,10,15)
    c.showPage()
    page += 1
    for title, group in groups:
        for i in range(0,len(group),2):
            frame(c,page,title.upper())
            text(c,40,750,title,28,NAVY,True)
            text(c,40,725,'Use the model code when requesting samples or a quotation.',10,GREY)
            for j,code in enumerate(group[i:i+2]):
                item = items[code]
                top = 695-j*307
                c.setFillColor(HexColor(PAPER)); c.roundRect(40,top-278,515,278,8,fill=1,stroke=0)
                photo(c,data_dir/item['image'],52,top-205,271,192,trim_white=True)
                text(c,340,top-30,code,19,TEAL,True)
                y=wrap(c,item['title'],340,top-59,192,15,20,NAVY,True)
                y=wrap(c,item['size'],340,y-13,190,11,16)
                text(c,340,y-17,'COLOR OPTIONS',8,GREY,True)
                wrap(c,' / '.join(item['colors']),340,y-36,184,10,15)
                wrap(c,item.get('notes') or 'Confirm color-size combinations and customization for your order.',56,top-234,480,9,13,GREY)
            text(c,40,65,'Samples, availability, fit, pricing and lead time are confirmed per order.',9,GREY)
            c.showPage(); page+=1
    frame(c,page,'LET US PLAN YOUR FACTORY VISIT')
    text(c,40,747,'Let us meet in Quanzhou',28,NAVY,True)
    wrap(c,'Bring your ideas. We can begin with a few selected models and a clear discussion of your brand direction.',40,707,505,13,20)
    text(c,40,624,'BEFORE YOUR VISIT',10,TEAL,True)
    y=590
    for line in ['Your preferred visit date and number of visitors','3-5 model codes or reference styles','Your target customers, market and sales channel','Your expected first-order quantity and sample needs']:
        text(c,43,y,'- '+line,11); y-=29
    c.setFillColor(HexColor(NAVY)); c.roundRect(40,167,515,275,10,fill=1,stroke=0)
    text(c,63,404,cfg['name'],26,'#FFFFFF',True)
    text(c,63,374,cfg['role'],12,'#BCD7D4')
    text(c,63,330,'WhatsApp  '+cfg['phone'],12,'#FFFFFF')
    text(c,63,302,cfg['email'],12,'#FFFFFF')
    text(c,63,274,cfg['website'].replace('https://','').rstrip('/'),12,'#FFFFFF')
    wrap(c,cfg['company'],63,229,335,10,15,'#FFFFFF')
    c.setFillColor(white); c.rect(437,315,92,92,fill=1,stroke=0)
    qr(c,cfg['whatsapp'],440,318,86)
    text(c,439,301,'WhatsApp',9,'#FFFFFF')
    c.linkURL(cfg['whatsapp'],(62,324,345,345))
    c.linkURL('mailto:'+cfg['email'],(62,295,359,318))
    c.linkURL(cfg['website'],(62,267,359,289))
    wrap(c,'These styles are a starting point for discussions with our team. Customization and production arrangements are reviewed for each selected model. Samples and order terms are confirmed individually.',40,122,510,10,15,GREY)
    c.save()
    return {'catalogue':str(path),'pages':page,'styles':codes,
            'source_ledger_updated_on':ledger['updated_on'],
            'original_packages_checked':26}


def build_card(out,cfg):
    # Photograph-based editorial layout; contact facts stay in the local configuration.
    w,h=1800,1080
    ivory='#F6F5F1'; navy='#17323D'; gold='#AA7F43'
    reg=lambda n:ImageFont.truetype(str(FONT_DIR/'arial.ttf'),n)
    bold=lambda n:ImageFont.truetype(str(FONT_DIR/'arialbd.ttf'),n)
    factory=Image.open(cfg['card_factory_image']).convert('RGB')
    factory=factory.crop(tuple(cfg['card_factory_crop']))
    im=Image.new('RGB',(w,h),ivory)
    im.paste(ImageOps.fit(factory,(790,h),centering=(0.42,0.5)),(1010,0))
    d=ImageDraw.Draw(im)
    d.polygon([(0,0),(1220,0),(1050,h),(0,h)],fill=ivory)
    d.polygon([(1208,0),(1220,0),(1050,h),(1038,h)],fill=gold)
    d.text((82,64),'BEIQIANG',font=bold(67),fill=navy)
    d.text((85,146),'FOOTWEAR & APPAREL',font=reg(25),fill=gold)
    d.text((83,210),'Quanzhou Beiqiang',font=reg(42),fill=navy)
    d.text((83,260),'Footwear & Apparel Co., Ltd.',font=reg(42),fill=navy)
    d.line((84,328,181,328),fill=gold,width=5)
    d.text((78,365),cfg['name'],font=bold(84),fill=navy)
    d.text((84,467),cfg['role'],font=reg(40),fill='#56676C')
    contact=[('Phone',cfg['phone']),('WhatsApp',cfg['phone']),
             ('WeChat',cfg['wechat']),('Email',cfg['email'])]
    for index,(label,value) in enumerate(contact):
        y=560+index*74
        d.text((85,y+9),label.upper(),font=bold(32),fill=gold)
        d.text((310,y),value,font=reg(46),fill=navy)
    d.line((85,862,968,862),fill='#DAD5CA',width=2)
    d.text((85,883),'FACTORY ADDRESS',font=bold(27),fill=gold)
    for index,line in enumerate(cfg['address_lines']):
        d.text((85,924+index*50),line,font=reg(42),fill=navy)
    png=out/'Beiqiang_Business_Card.png'; im.save(png)
    back=Image.new('RGB',(w,h),ivory);bd=ImageDraw.Draw(back)
    bd.text((85,64),'BEIQIANG',font=bold(67),fill=navy)
    bd.text((89,157),'KNIT  /  CASUAL  /  OEM & ODM',font=reg(27),fill=gold)
    for index,path in enumerate(cfg['card_shoe_images']):
        shoe=Image.open(path).convert('RGB')
        diff=ImageChops.difference(shoe,Image.new('RGB',shoe.size,'white')).convert('L')
        box=diff.point(lambda p:255 if p>12 else 0).getbbox()
        if box:shoe=shoe.crop(box)
        panel=ImageOps.contain(shoe,(775,385))
        x=85+index*855;back.paste(panel,(x+(775-panel.width)//2,273+(385-panel.height)//2))
        bd.text((x,702),['L1009','L1026'][index],font=bold(40),fill=navy)
    bd.rectangle((0,797,w,h),fill=navy)
    bd.text((85,839),cfg['company'],font=reg(42),fill='white')
    bd.text((85,902),cfg['name']+'  |  '+cfg['role'],font=reg(39),fill='#DBE3DD')
    bd.text((85,970),cfg['address'],font=reg(39),fill='#DBE3DD')
    back_path=out/'Beiqiang_Business_Card_Back.png';back.save(back_path)
    path=out/'Beiqiang_Business_Card_Print.pdf'
    mm=72/25.4; width,height=96*mm,60*mm
    c=canvas.Canvas(str(path),pagesize=(width,height))
    c.setTitle(cfg['name']+' | Beiqiang | Business Card | 90 x 54 mm + 3 mm bleed')
    c.setAuthor(cfg['company'])
    for image in [im,back]:
        # Extend only edge pixels into the bleed, keeping the entire trim artwork intact.
        border=60
        bleed=Image.new('RGB',(w+2*border,h+2*border))
        bleed.paste(image,(border,border))
        bleed.paste(image.crop((0,0,w,1)).resize((w,border)),(border,0))
        bleed.paste(image.crop((0,h-1,w,h)).resize((w,border)),(border,h+border))
        bleed.paste(bleed.crop((border,0,border+1,h+2*border)).resize((border,h+2*border)),(0,0))
        bleed.paste(bleed.crop((w+border-1,0,w+border,h+2*border)).resize((border,h+2*border)),(w+border,0))
        c.drawImage(ImageReader(bleed),0,0,width,height)
        c.showPage()
    c.save()
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import RectangleObject
    reader=PdfReader(path)
    writer=PdfWriter()
    writer.append(reader)
    for page in writer.pages:
        page.trimbox=RectangleObject([3*mm,3*mm,93*mm,57*mm])
        page.bleedbox=RectangleObject([0,0,width,height])
    with path.open('wb') as stream:
        writer.write(stream)
    return str(path)


def build_expanded_catalogue(out,cfg):
    inventory=json.loads(Path(cfg['catalogue_inventory']).read_text(encoding='utf-8-sig'))
    rows=inventory['styles'];by_code={r['code']:r for r in rows}
    groups=[]
    for name in ['Beiqiang factory styles','More casual & knit styles','Outdoor & boot collection','Sandals, loafers & easy wear','Junior size styles']:
        selected=[r for r in rows if r['group']==name and r['code'] not in ['BQ008','BQ009']]
        if selected:groups.append((name,selected))
    sections=[];next_page=5
    for name,selected in groups:
        count=(len(selected)+3)//4
        sections.append((name,next_page,next_page+count-1,len(selected)))
        next_page+=count
    path=out/'Beiqiang_Product_Catalogue.pdf';c=canvas.Canvas(str(path),pagesize=(595,842))
    c.setTitle('Beiqiang Footwear Catalogue | '+str(len(rows))+' styles')
    c.setAuthor(cfg['company'])
    c.setFillColor(HexColor(NAVY));c.rect(0,0,595,842,fill=1,stroke=0)
    text(c,40,793,'BEIQIANG',22,'#FFFFFF',True)
    text(c,40,731,'FOOTWEAR',44,'#FFFFFF',True)
    text(c,40,679,'COLLECTION',44,'#FFFFFF',True)
    text(c,42,640,str(len(rows))+' styles for your next footwear collection',14,'#BCD7D4')
    photo(c,out/'cover_factory.jpg',40,306,515,290,crop=True)
    text(c,40,270,'FEATURING L1009 & L1026',16,'#FFFFFF',True)
    wrap(c,'Knit & casual  /  Sport inspired  /  Outdoor & boots  /  Loafers & easy wear',40,235,500,12,19,'#BCD7D4')
    wrap(c,'Beiqiang factory styles and partner-sourced footwear, clearly identified throughout the catalogue.',40,168,500,12,19,'#FFFFFF')
    text(c,40,93,cfg['company'],11,'#FFFFFF')
    text(c,40,69,'Quanzhou, Fujian, China  |  October 2026',10,'#BCD7D4');c.showPage()
    frame(c,2,'FIND YOUR COLLECTION')
    text(c,40,748,'Find your collection',29,NAVY,True)
    wrap(c,'Explore by silhouette, then send us 3-5 model codes to start a discussion about your brand.',40,710,505,12,18)
    text(c,40,648,'Featured: L1009 / BQ008',15,TEAL,True);text(c,490,648,'03',14,NAVY,True)
    text(c,40,610,'Featured: L1026 / BQ009',15,TEAL,True);text(c,490,610,'04',14,NAVY,True)
    y=553
    for name,start,end,count in sections:
        text(c,40,y,name,16,NAVY,True)
        text(c,40,y-23,str(count)+' styles',10,GREY)
        text(c,465,y,f'{start:02}-{end:02}',12,TEAL,True);y-=62
    text(c,40,y-7,'Plan your brand & factory visit',15,NAVY,True)
    text(c,465,y-7,f'{next_page:02}-{next_page+1:02}',12,TEAL,True)
    c.setFillColor(HexColor(PAPER));c.roundRect(40,88,515,93,8,fill=1,stroke=0)
    wrap(c,'Beiqiang factory: styles in our factory range. Partner-sourced: additional styles coordinated through supply partners. Customization, quantities, samples, fit and lead time are reviewed per model and order.',54,156,485,10,15)
    c.showPage()
    for page,code in [(3,'BQ008'),(4,'BQ009')]:
        r=by_code[code];frame(c,page,'FEATURED FACTORY STYLE')
        text(c,40,744,r['model'],38,TEAL,True);text(c,245,751,r['code'],13,GREY)
        text(c,245,727,'Beiqiang factory',11,TEAL,True)
        photo(c,r['image'],40,390,515,305,trim_white=True)
        text(c,40,353,r['title'],24,NAVY,True)
        text(c,40,314,'Lace up  /  Mesh-textile upper  /  Athletic casual style',12,INK)
        text(c,40,274,r['size'],15,NAVY,True)
        wrap(c,'Colors: '+' / '.join(r['colors']),40,240,505,12,18)
        c.setFillColor(HexColor(PAPER));c.roundRect(40,100,515,79,7,fill=1,stroke=0)
        wrap(c,'Discuss your preferred color, logo details, size ratio and sample requirements with us. Sole composition, fit, pricing and lead time are confirmed for the selected order.',55,153,482,11,17)
        c.showPage()
    page=5
    for name,selected in groups:
        for i in range(0,len(selected),4):
            frame(c,page,name.upper());text(c,40,751,name,25,NAVY,True)
            text(c,40,724,'Quote both the model and Beiqiang reference when making your shortlist.',9,GREY)
            for j,r in enumerate(selected[i:i+4]):
                x=40+(j%2)*264;top=701-(j//2)*318
                c.setFillColor(HexColor(PAPER));c.roundRect(x,top-308,251,308,7,fill=1,stroke=0)
                photo(c,r['image'],x+12,top-175,227,161,trim_white=True)
                label=r['model']
                if r['code'].startswith('LQ-'):label=r['code']
                text(c,x+13,top-196,label,16,TEAL,True)
                text(c,x+13,top-211,r['code'] if label!=r['code'] else 'Model reference',8,GREY)
                wrap(c,r['title'],x+13,top-230,224,10.5,13,NAVY,True)
                size=r['size']
                if len(size)>48:size='Size options on request'
                text(c,x+13,top-249,size,9,INK)
                color=' / '.join(r.get('colors') or [])
                if len(color)>88:color=f"{len(r['colors'])} color options; details on request"
                wrap(c,color or 'Color options on request',x+13,top-266,224,8.5,12,GREY)
                note=r.get('notes','')
                if note and note!='Color options on request.':
                    wrap(c,note,x+13,top-282,224,7.3,9,INK)
                text(c,x+13,top-297,r['origin'],8,TEAL,True)
            c.showPage();page+=1
    frame(c,page,'PLAN YOUR BRAND & FACTORY VISIT')
    text(c,40,749,'Build your first collection',28,NAVY,True)
    steps=[('01','Choose your direction','Tell us your target customer, sales market and preferred retail price range.'),
           ('02','Shortlist 3-5 models','Send the original model code and Beiqiang reference, with preferred colors and sizes.'),
           ('03','Review brand details','Discuss logo placement, materials, colors and packaging. Feasibility is reviewed for the selected model.'),
           ('04','Agree the sample plan','Confirm the sample purpose, specifications, cost, timing and review criteria.'),
           ('05','Confirm your visit','Share your preferred visit date and number of visitors. We can then agree the meeting plan.')]
    y=672
    for n,title,body in steps:
        text(c,40,y,n,25,TEAL,True);text(c,95,y+3,title,16,NAVY,True)
        wrap(c,body,95,y-24,445,12,18);y-=111
    c.showPage();page+=1
    frame(c,page,'CONTACT BEIQIANG')
    text(c,40,746,'Let us meet in Quanzhou',28,NAVY,True)
    wrap(c,'Bring your ideas and selected model codes. We can discuss the next practical step for your footwear brand.',40,704,500,13,20)
    c.setFillColor(HexColor(NAVY));c.roundRect(40,285,515,310,10,fill=1,stroke=0)
    text(c,64,548,cfg['name'],29,'#FFFFFF',True);text(c,64,513,cfg['role'],13,'#BCD7D4')
    text(c,64,458,'Phone / WhatsApp  '+cfg['phone'],12,'#FFFFFF')
    text(c,64,426,'WeChat  '+cfg['wechat'],12,'#FFFFFF')
    text(c,64,394,cfg['email'],12,'#FFFFFF')
    wrap(c,cfg['address'],64,354,462,10,15,'#FFFFFF')
    for url,rect in [(cfg['whatsapp'],(63,451,450,476)),('mailto:'+cfg['email'],(63,384,450,410))]:c.linkURL(url,rect)
    wrap(c,'Factory and partner-sourced styles are identified individually. OEM/ODM options, samples, color-size combinations, packaging, pricing and lead time are confirmed per model and order.',40,225,510,11,17,GREY)
    text(c,40,125,'Your shortlist is the start of the conversation.',14,TEAL,True)
    c.save()
    return {'catalogue':str(path),'pages':page,'styles':[r['code'] for r in rows],
            'style_count':len(rows),'factory_styles':sum(r['origin']=='Beiqiang factory' for r in rows),
            'featured_models':['L1009 / BQ008','L1026 / BQ009'],'source_ledger_updated_on':inventory['ledger_date']}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    cfg=json.loads(args.config.read_text(encoding='utf-8-sig'))
    out=args.output; out.mkdir(parents=True,exist_ok=True)
    data_dir=args.root/'04_客户开发/06_报价与产品册/full_catalog_2026-10-04'
    report=build_expanded_catalogue(out,cfg) if cfg.get('catalogue_inventory') else build_catalogue(args.root,data_dir,out,cfg)
    report['card']=build_card(out,cfg)
    (out/'qa_local.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    main()
