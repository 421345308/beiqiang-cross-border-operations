"""Build a reviewed buyer PDF from the existing product sources and real images.

Requires reportlab and Pillow. Supply a modern Node executable for the site's
TypeScript data. Outputs/contact/evidence remain local; no API writes or sends.
"""
import argparse
import hashlib
import io
import json
import re
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape
from PIL import Image

from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, Color
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / '04_客户开发/06_报价与产品册/国际B2B精选册'
SITE = ROOT / '03_独立站/03_网站源码'
PRIVATE = ROOT / '00_总控台/产品中心/数据/.local/主推组合评估/2026-10-29'
W, H = 842, 595
INK = '#183C36'
BODY = '#354B46'
MUTED = '#63756F'
PAPER = '#F5F3EC'
LINE = '#D5DDD6'
ACCENT = '#BF542F'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def prepare(node):
    selection = read(PROJECT / 'selection.json')
    module = (SITE / 'app/data/products.ts').as_uri()
    js = f"import {{ products }} from {json.dumps(module)}; process.stdout.write(JSON.stringify(products));"
    data = json.loads(subprocess.check_output(
        [node, '--experimental-strip-types', '--input-type=module', '-e', js], text=True, encoding='utf-8'))
    site_products = {p['code']: p for p in data}
    provenance = read(SITE / 'data/product-photo-provenance.json')['products']
    canonical = {p['id']: p for p in read(ROOT / '00_总控台/产品中心/数据/产品.json')['products']}
    assets = []
    for p in selection['products']:
        code = p['code']
        identity = 'HR009' if code == 'BQ1009' else code
        product = canonical[identity]
        p['canonical_id'] = identity
        if p['supply'] == 'Beiqiang factory':
            assert f'01_产品资产/01_原始素材/{code}' in product['raw_packages'], code
        else:
            assert product['source_state'] == 'ADOPTED', code
        formal_path = PRIVATE / f"{p['id']}-current.json"
        formal = read(formal_path)['response']['product']
        assert formal['status'] == 'approved' and formal['display'] == 'Y', code
        p['url'] = formal['pc_detail_url']
        if code == 'BQ1009':
            image = ROOT / '01_产品资产/02_成品素材/BQ1009/BQ1009_15caf94cd85133d6.jpg'
            sizes = sorted({int(re.search(r'EU(\d+)', s['sku_code'])[1])
                            for s in formal['product_sku']['skus']})
            p['size'] = f'EU {min(sizes)}-{max(sizes)}'
            p['colors'] = 'White / contrast heel'
            expected = '15caf94cd85133d69645a9e66cc05ad5244893d89dd9cbec46f6f560eb633281'
            assert hashlib.sha256(image.read_bytes()).hexdigest() == expected
            fact_source = '02_Alibaba运营/05_扩品工程/执行记录/HR实源替换/HR009/来源与正式绑定核验.json'
        else:
            src = site_products[code]
            image = SITE / 'public' / src['images'][0].lstrip('/')
            p['size'] = src['size'].replace('\u2013', '-')
            p['colors'] = ' / '.join(src['colors'])
            fact_source = '03_独立站/03_网站源码/app/data/products.ts'
            record = next(x for x in provenance[code] if x['image'] == src['images'][0])
            assert hashlib.sha256(image.read_bytes()).hexdigest() == record['outputSha256'], code
            if p['supply'] == 'Beiqiang factory':
                assert record['sourceKind'] == 'factory-original-package', code
                raw = ROOT / '01_产品资产/01_原始素材' / code / record['sourceFile']
                assert hashlib.sha256(raw.read_bytes()).hexdigest() == record['sourceSha256'], code
        p['image'] = str(image)
        assets.append({'code': code, 'canonical_id': identity, 'image': str(image.relative_to(ROOT)),
                       'sha256': hashlib.sha256(image.read_bytes()).hexdigest(),
                       'fact_source': fact_source, 'formal_read': str(formal_path.relative_to(ROOT))})
    return selection, assets


def build(node):
    selection, assets = prepare(node)
    products = selection['products']
    contact = read(ROOT / '04_客户开发/06_报价与产品册/工厂参观资料/contact.local.json')
    out = PROJECT / '交付'
    qa = PROJECT / 'qa'
    out.mkdir(parents=True, exist_ok=True)
    qa.mkdir(parents=True, exist_ok=True)
    for name, file in [('Sans', 'segoeui.ttf'), ('Bold', 'seguisb.ttf'), ('Display', 'georgia.ttf')]:
        pdfmetrics.registerFont(TTFont(name, str(Path('C:/Windows/Fonts') / file)))
    target = out / 'Beiqiang-Selected-Casual-Footwear.pdf'
    c = canvas.Canvas(str(target), pagesize=(W, H), pageCompression=1)
    c.setTitle('Beiqiang | Selected Casual Footwear')
    c.setAuthor(contact['company'])
    overflow = []
    embedded_images = {}

    def box(x, top, w, h, color):
        c.setFillColor(HexColor(color)); c.rect(x, H-top-h, w, h, stroke=0, fill=1)

    def text(s, x, top, size=11, font='Sans', color=INK):
        c.setFont(font, size); c.setFillColor(HexColor(color)); c.drawString(x, H-top-size, s)

    def para(s, x, top, w, size=11, color=BODY, leading=None, maxh=100):
        style = ParagraphStyle('p', fontName='Sans', fontSize=size, leading=leading or size*1.4,
                               textColor=HexColor(color))
        p = Paragraph(s, style)
        _, h = p.wrap(w, maxh)
        if h > maxh: overflow.append({'page': c.getPageNumber(), 'text': s, 'height': h, 'allowed': maxh})
        p.drawOn(c, x, H-top-h)
        return h

    def photo(path, x, top, w, h):
        key = str(path)
        if key not in embedded_images:
            im = Image.open(path).convert('RGB')
            im.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            stream = io.BytesIO()
            im.save(stream, format='JPEG', quality=88, optimize=True)
            stream.seek(0)
            embedded_images[key] = ImageReader(stream)
        c.drawImage(embedded_images[key], x, H-top-h, w, h, preserveAspectRatio=True,
                    anchor='c', mask='auto')

    def rule(top, x=40, w=762):
        c.setStrokeColor(HexColor(LINE)); c.setLineWidth(.65); c.line(x, H-top, x+w, H-top)

    def page(kicker, title, intro, n):
        box(0, 0, W, H, PAPER)
        text('BEIQIANG', 40, 24, 12, 'Bold')
        text(kicker.upper(), 560, 27, 8.5, 'Bold', MUTED)
        text(title, 40, 63, 29, 'Display')
        para(intro, 40, 107, 755, 10.5, maxh=34)
        footer(n)

    def footer(n):
        rule(560)
        text('BEIQIANG  /  SELECTED CASUAL FOOTWEAR', 40, 570, 7.5, 'Bold', MUTED)
        text('OCT 2026', 682, 570, 7.5, color=MUTED)
        text(f'{n:02d} / 06', 766, 570, 7.5, color=MUTED)

    # Cover: full original image, no product retouching.
    box(0, 0, W, H, PAPER)
    text('BEIQIANG', 40, 34, 16, 'Bold')
    text('SELECTED COLLECTION  /  OCT 2026', 40, 83, 8.5, 'Bold', ACCENT)
    text('Everyday casual', 40, 131, 36, 'Display')
    text('footwear.', 40, 176, 36, 'Display')
    para('Build your next range around a focused selection of knit, textile and casual styles.',
         42, 242, 300, 14, maxh=85)
    para('For importers, wholesalers and private-label buyers. Factory styles from Quanzhou, with selected partner-sourced additions.',
         42, 339, 290, 11, maxh=78)
    photo(products[0]['image'], 377, 116, 425, 375)
    text('FEATURED  BQ008', 400, 503, 9, 'Bold', MUTED)
    rule(451, 42, 285)
    text('5 factory styles', 42, 469, 12, 'Bold')
    text('3 complementary selections', 42, 492, 12, 'Bold')
    footer(1); c.showPage()

    def card(p, x, top):
        photo(p['image'], x, top, 174, 174)
        tx=x+184
        text(p['code'], tx, top+2, 12, 'Bold', ACCENT)
        para(escape(p['name']), tx, top+25, 184, 13, INK, maxh=42)
        para(escape(p['detail']), tx, top+70, 184, 9.3, maxh=42)
        text(p['size'], tx, top+119, 10, 'Bold')
        text(p['supply'], tx, top+140, 8.5, color=MUTED)
        text('View style >', tx, top+158, 8.5, 'Bold')
        c.linkURL(p['url'], (tx,H-top-174,tx+115,H-top-156), relative=0)

    page('01 / Factory collection', 'Start with four distinct silhouettes.',
         'Layered, clean, wide-toe and slip-on options - each with a different role in your range.', 2)
    for i,p in enumerate(products[:4]): card(p,40+(i%2)*390,151+(i//2)*197)
    c.showPage()

    page('02 / Complement your range', 'Add the styles your buyers need.',
         'One more factory knit option, plus selected partner-sourced styles for specific assortment gaps.',3)
    for i,p in enumerate(products[4:]): card(p,40+(i%2)*390,151+(i//2)*197)
    c.showPage()

    page('03 / Manufacturing', 'Meet the manufacturing behind the range.',
         'Beiqiang was established in Quanzhou in 2015, with production experience supporting established footwear brands in China.',4)
    for x, val, label in [(40,'2015','Established in Quanzhou'),(301,'3,000+ m2','Manufacturing base'),(562,'200,000 pairs','Annual output')]:
        text(val,x,143,21,'Display');text(label,x,173,9,color=MUTED)
    factory=SITE/'public/factory-video-stills'
    pics=[('material-cutting.webp','01  Material cutting'),('stitching-line.webp','02  Upper stitching'),
          ('sole-bonding.webp','03  Sole bonding'),('assembly-line.webp','04  Assembly line')]
    for i,(filename,caption) in enumerate(pics):
        x=40+(i%2)*390; y=201+(i//2)*174
        fp=factory/filename;photo(fp,x,y,372,142);text(caption,x,y+146,9,'Bold')
        assets.append({'factory_image':str(fp.relative_to(ROOT)), 'sha256':hashlib.sha256(fp.read_bytes()).hexdigest()})
    c.showPage()

    page('04 / Range planning', 'Compare the selection at a glance.',
         'Choose the role first, then narrow the colour and size mix for your market.',5)
    cols=[40,158,345,543,672]
    box(40,148,762,28,INK)
    for s,x in zip(['STYLE','RANGE ROLE','SIZE SELECTION','SUPPLY','FASTENING'],cols):text(s,x+8,156,8,'Bold','#FFFFFF')
    for i,p in enumerate(products):
        y=176+i*31
        if i%2==0:box(40,y,762,31,'#E9EDE6')
        closure='Slip-on' if p['code']=='BQ001' else 'Heel strap' if p['code']=='BQ-C2627' else 'Lace-up'
        supply='Factory' if p['supply']=='Beiqiang factory' else 'Partner-sourced'
        for s,x in zip([p['code'],p['role'],p['size'],supply,closure],cols):text(s,x+8,y+9,9)
    para('Sizes shown are the documented style ranges. We confirm the selected colour, size mix and order availability in your quotation.',
         40,432,755,9,MUTED,maxh=30)
    text('Make the cost comparison useful.',40,471,16,'Display')
    para('Ask us to compare an existing style with your requested changes: upper materials, branding, packaging and quantity. This makes the cost of each choice visible before you commit to sampling or production.',
         40,500,745,10.5,maxh=47)
    c.showPage()

    page('05 / Work with Beiqiang', 'From a shortlist to a clear buying decision.',
         'Send the style codes that interest you, your market and an indicative order quantity. We will build the next step around that brief.',6)
    routes=[
        ('01','Select an existing style','Start with style codes, colour and size needs.','Receive a version-specific sample and quotation proposal, including applicable sample charges and timing.'),
        ('02','Adapt a factory style','Share the artwork, colour or packaging changes you want.','Receive the feasible changes, sample scope and cost differences for that style before development starts.'),
        ('03','Explore a new construction','Share the intended use and technical requirements.','Start with a feasibility review covering the development scope, tooling, testing, costs and sample acceptance criteria.')]
    for i,(num,title,start,result) in enumerate(routes):
        y=151+i*95
        text(num,40,y,22,'Display',ACCENT);text(title,88,y+1,15,'Bold')
        para(start,88,y+30,300,10,maxh=43)
        para(result,424,y+5,367,10.5,maxh=72)
        if i<2:rule(y+83,88,714)
    box(40,446,762,102,INK)
    text('Build your shortlist with us.',58,461,21,'Display','#FFFFFF')
    text(contact['name']+'  |  '+contact['role'],58,498,10,'Bold','#FFFFFF')
    text(contact['email'],434,463,11,'Bold','#FFFFFF')
    text('WhatsApp  '+contact['phone'],434,486,10,color='#FFFFFF')
    text('www.beiqiang.online',434,509,10,color='#FFFFFF')
    c.linkURL('mailto:'+contact['email'],(434,H-480,740,H-459),relative=0)
    c.linkURL(contact['whatsapp'],(434,H-504,760,H-483),relative=0)
    c.linkURL('https://www.beiqiang.online/',(434,H-528,710,H-506),relative=0)
    c.showPage();c.save()
    assert not overflow, overflow
    manifest={'edition':selection['edition'],'pdf':str(target.relative_to(ROOT)),
              'sha256':hashlib.sha256(target.read_bytes()).hexdigest(), 'pages':6,
              'assets':assets,'paragraph_overflow':overflow,
              'company_fact_source':'02_Alibaba运营/01_店铺与全店诊断/店铺首页优化方案_2026-09-14.md',
              'contact_source':'04_客户开发/06_报价与产品册/工厂参观资料/contact.local.json',
              'reviewed_copy_source':'02_Alibaba运营/02_单品优化记录/全店FAQ与产品亮点优化/内容质量复核/逐款文案.json',
              'scope':'Buyer presentation; no stock, performance, development-success or fixed delivery guarantee.'}
    (qa/'build-manifest.local.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'pdf':str(target),'pages':6,'bytes':target.stat().st_size,'overflow':0},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--node',required=True)
    build(parser.parse_args().node)
