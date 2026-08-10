from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
OUT = ROOT / "outputs" / "outreach_product_sheet_20260803"
OUT.mkdir(parents=True, exist_ok=True)

W, H = 1200, 1500
BG = "#F5F8F7"
INK = "#172A35"
MUTED = "#5F6F73"
GREEN = "#0F766E"
PALE = "#E3F2EE"
ORANGE = "#F28C45"
WHITE = "#FFFFFF"

REG = r"C:\Windows\Fonts\arial.ttf"
BOLD = r"C:\Windows\Fonts\arialbd.ttf"


def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else REG, size)


def rounded_shadow(base, box, radius=28):
    x0, y0, x1, y1 = box
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((x0 + 5, y0 + 10, x1 + 5, y1 + 10), radius, fill=(23, 42, 53, 34))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    base.alpha_composite(shadow)
    ImageDraw.Draw(base).rounded_rectangle(box, radius, fill=WHITE)


def fit_image(path, target_size, crop=None):
    im = Image.open(path).convert("RGB")
    if crop:
        im = im.crop(crop)
    # Trim near-white margins so the real product remains visually dominant.
    gray = im.convert("L")
    mask = gray.point(lambda p: 255 if p < 242 else 0)
    bbox = mask.getbbox()
    if bbox:
        pad = 18
        x0, y0, x1, y1 = bbox
        im = im.crop((max(0, x0 - pad), max(0, y0 - pad), min(im.width, x1 + pad), min(im.height, y1 + pad)))
    tw, th = target_size
    ratio = min(tw / im.width, th / im.height)
    im = im.resize((int(im.width * ratio), int(im.height * ratio)), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", target_size, WHITE)
    canvas.paste(im, ((tw - im.width) // 2, (th - im.height) // 2))
    return canvas


canvas = Image.new("RGBA", (W, H), BG)
draw = ImageDraw.Draw(canvas)

# Brand header
draw.rectangle((0, 0, W, 18), fill=GREEN)
draw.text((70, 62), "BEIQIANG FOOTWEAR", font=font(30, True), fill=GREEN)
draw.text((70, 112), "COMFORT WALKING SHOES", font=font(58, True), fill=INK)
draw.text((70, 184), "Factory Supply  |  Wholesale  |  OEM/ODM", font=font(27), fill=MUTED)

products = [
    {
        "code": "L1026",
        "name": "Breathable Knit Walking Shoe",
        "detail": "Thick cushion sole  |  Lace-up fit",
        "path": ROOT / "02_可上传素材" / "00_最终上传" / "BQ009_L1026" / "01_主图" / "01_main.jpg",
        "crop": None,
    },
    {
        "code": "A830",
        "name": "Men's Knit Slip-On Shoe",
        "detail": "Easy-on design  |  Casual comfort",
        "path": ROOT / "02_可上传素材" / "00_最终上传" / "BQ024_A830" / "01_主图" / "01_main.jpg",
        "crop": None,
    },
    {
        "code": "M8506",
        "name": "Knit Chunky Walking Shoe",
        "detail": "Breathable upper  |  Cushion sole",
        "path": ROOT / "02_可上传素材" / "00_最终上传" / "BQ012_M8506" / "04_参考预览" / "old_main_20260613" / "01_main.jpg",
        "crop": (120, 300, 1080, 900),
    },
]

row_y = [270, 535, 800]
for y, p in zip(row_y, products):
    rounded_shadow(canvas, (55, y, 1145, y + 230), 28)
    img = fit_image(p["path"], (380, 200), p["crop"])
    canvas.paste(img, (75, y + 15))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((490, y + 30, 610, y + 72), 21, fill=PALE)
    draw.text((513, y + 37), p["code"], font=font(22, True), fill=GREEN)
    draw.text((490, y + 92), p["name"], font=font(31, True), fill=INK)
    draw.text((490, y + 145), p["detail"], font=font(23), fill=MUTED)
    draw.text((490, y + 184), "Ask for colors, sizes & sample details", font=font(20), fill=GREEN)

# Benefit panel
draw.rounded_rectangle((55, 1060, 1145, 1265), 30, fill=INK)
benefits = [
    ("RELIABLE", "QUALITY"),
    ("COMPETITIVE", "FACTORY PRICING"),
    ("OEM/ODM", "SUPPORT"),
    ("SAMPLE", "BEFORE BULK"),
]
centers = [190, 465, 740, 1015]
for cx, (top, bottom) in zip(centers, benefits):
    draw.ellipse((cx - 17, 1092, cx + 17, 1126), fill=ORANGE)
    draw.text((cx, 1144), top, font=font(21, True), anchor="ma", fill=WHITE)
    draw.text((cx, 1176), bottom, font=font(20), anchor="ma", fill="#C9D7D8")

# CTA and contact
draw.text((600, 1312), "REQUEST 3 STYLES & SAMPLE DETAILS", font=font(32, True), anchor="ma", fill=GREEN)
draw.text((600, 1360), "WhatsApp: +86 189 5980 5256  |  shepeiqiang@gmail.com", font=font(24, True), anchor="ma", fill=INK)
draw.text((600, 1405), "Quanzhou Beiqiang Footwear & Apparel Co., Ltd.", font=font(21), anchor="ma", fill=MUTED)
draw.text((600, 1440), "Final price depends on style, quantity, sizes, packing and order requirements.", font=font(17), anchor="ma", fill="#7A898D")

png_path = OUT / "Beiqiang_3_Style_B2B_Product_Sheet_EN.png"
jpg_path = OUT / "Beiqiang_3_Style_B2B_Product_Sheet_EN_email.jpg"
canvas.convert("RGB").save(png_path, quality=95)
canvas.convert("RGB").save(jpg_path, quality=88, optimize=True, progressive=True)
print(png_path)
print(jpg_path)
