from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(r"C:\Users\spq\Desktop\贝强")
OUT = ROOT / "outputs" / "outreach_product_sheet_20260803"
OUT.mkdir(parents=True, exist_ok=True)

W, H = 1200, 1600
BG, WHITE = "#F4F8F7", "#FFFFFF"
INK, MUTED = "#172A35", "#607074"
GREEN, PALE, ORANGE = "#0F766E", "#E2F2EE", "#F28C45"
REG, BOLD = r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"

def f(size, bold=False):
    return ImageFont.truetype(BOLD if bold else REG, size)

def trim_fit(path, size, crop=None):
    im = Image.open(path).convert("RGB")
    if crop:
        im = im.crop(crop)
    mask = im.convert("L").point(lambda p: 255 if p < 242 else 0)
    bbox = mask.getbbox()
    if bbox:
        x0, y0, x1, y1 = bbox
        pad = 15
        im = im.crop((max(0, x0-pad), max(0, y0-pad), min(im.width, x1+pad), min(im.height, y1+pad)))
    ratio = min(size[0]/im.width, size[1]/im.height)
    im = im.resize((int(im.width*ratio), int(im.height*ratio)), Image.Resampling.LANCZOS)
    out = Image.new("RGB", size, WHITE)
    out.paste(im, ((size[0]-im.width)//2, (size[1]-im.height)//2))
    return out

def card_shadow(base, box):
    x0,y0,x1,y1 = box
    sh = Image.new("RGBA", base.size, (0,0,0,0))
    sd = ImageDraw.Draw(sh)
    sd.rounded_rectangle((x0+4,y0+8,x1+4,y1+8), 24, fill=(23,42,53,30))
    base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(12)))
    ImageDraw.Draw(base).rounded_rectangle(box, 24, fill=WHITE)

products = [
    ("BQ001", "Wide-Toe Knit Slip-On", ROOT/"01_产品资产" / "02_可发布素材"/"00_最终上传"/"BQ001_数据包1"/"03_颜色图"/"all_black.jpg", None),
    ("BQ002", "Wide-Toe Knit Slip-On", ROOT/"01_产品资产" / "02_可发布素材"/"00_最终上传"/"BQ002_数据包2"/"03_颜色图"/"grey_white.jpg", None),
    ("L1026", "Thick-Sole Knit Walker", ROOT/"01_产品资产" / "02_可发布素材"/"00_最终上传"/"BQ009_L1026"/"01_主图"/"01_main.jpg", None),
    ("A830", "Men's Knit Slip-On", ROOT/"01_产品资产" / "02_可发布素材"/"00_最终上传"/"BQ024_A830"/"01_主图"/"01_main.jpg", None),
    ("M8506", "Chunky Knit Walking Shoe", ROOT/"01_产品资产" / "02_可发布素材"/"00_最终上传"/"BQ012_M8506"/"04_参考预览"/"old_main_20260613"/"01_main.jpg", (120,300,1080,900)),
    ("A116", "Lightweight Knit Walker", ROOT/"01_产品资产" / "02_可发布素材"/"00_最终上传"/"BQ018_A116"/"01_主图"/"01_main.jpg", None),
]

canvas = Image.new("RGBA", (W,H), BG)
d = ImageDraw.Draw(canvas)
d.rectangle((0,0,W,18), fill=GREEN)
d.text((60,55), "BEIQIANG FOOTWEAR", font=f(28,True), fill=GREEN)
d.text((60,102), "BREATHABLE KNIT WALKING SHOES", font=f(48,True), fill=INK)
d.text((60,166), "Wide-Toe  |  Slip-On  |  Chunky Sole  |  OEM/ODM", font=f(25), fill=MUTED)

card_w, card_h = 515, 325
xs, ys = [60, 625], [245, 600, 955]
for (code, name, path, crop), (x,y) in zip(products, [(x,y) for y in ys for x in xs]):
    card_shadow(canvas, (x,y,x+card_w,y+card_h))
    pic = trim_fit(path, (455,210), crop)
    canvas.paste(pic, (x+30,y+18))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((x+30,y+240,x+135,y+278), 18, fill=PALE)
    d.text((x+82,y+247), code, font=f(20,True), anchor="ma", fill=GREEN)
    d.text((x+30,y+287), name, font=f(23,True), fill=INK)

d.rounded_rectangle((60,1325,1140,1442), 26, fill=INK)
items = ["RELIABLE QUALITY", "FACTORY PRICING", "OEM/ODM SUPPORT", "SAMPLE CHECK"]
for cx, label in zip([190,465,740,1015], items):
    d.ellipse((cx-11,1352,cx+11,1374), fill=ORANGE)
    d.text((cx,1390), label, font=f(18,True), anchor="ma", fill=WHITE)

d.text((600,1478), "CONTACT US FOR STYLES, SAMPLES & CUSTOMIZATION", font=f(27,True), anchor="ma", fill=GREEN)
d.text((600,1520), "WhatsApp +86 189 5980 5256  |  shepeiqiang@gmail.com", font=f(21,True), anchor="ma", fill=INK)
d.text((600,1553), "Alibaba: cn1576227362luzl.m.en.alibaba.com", font=f(18), anchor="ma", fill=MUTED)

png = OUT/"Beiqiang_6_Style_Knit_Walking_Shoes_EN.png"
jpg = OUT/"Beiqiang_6_Style_Knit_Walking_Shoes_EN_email.jpg"
canvas.convert("RGB").save(png, quality=95)
canvas.convert("RGB").save(jpg, quality=87, optimize=True, progressive=True)
print(png)
print(jpg)
