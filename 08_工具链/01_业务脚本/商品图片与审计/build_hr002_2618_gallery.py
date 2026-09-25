"""Local B2B gallery candidates for sourced model 2618; no online writes."""

from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
SRC = ROOT / "99_临时区" / "HR002_2618_货源候选_2026-09-24"
OUT = SRC / "本地候选_v1"
COMP = ROOT / "02_Alibaba运营" / "06_图片与检查记录" / "公司图复用模板_v4_2026-09-21"
W = 1200
BG = "#f2f6f4"
WHITE = "#ffffff"
INK = "#172c2a"
GREEN = "#124f40"
PALE = "#e0eeea"
MUTED = "#526560"


def f(size: int, bold: bool = False):
    name = "arialbd.ttf" if bold else "arial.ttf"
    return ImageFont.truetype(str(Path(r"C:\Windows\Fonts") / name), size)


def label(draw: ImageDraw.ImageDraw, at: tuple[int, int], value: str, size: int = 25,
          color: str = INK, bold: bool = False):
    draw.text(at, value, font=f(size, bold), fill=color)


def page(kicker: str, headline: str, subtitle: str = "") -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (W, W), BG)
    draw = ImageDraw.Draw(image)
    label(draw, (60, 45), kicker, 22, GREEN, True)
    label(draw, (60, 87), headline, 44, INK, True)
    if subtitle:
        label(draw, (60, 151), subtitle, 22, MUTED)
    return image, draw


def card(draw: ImageDraw.ImageDraw, box, fill=WHITE):
    draw.rounded_rectangle(box, radius=22, fill=fill, outline="#d4e2dc", width=2)


def img(path: Path, box: tuple[int, int, int, int] | None = None) -> Image.Image:
    with Image.open(path) as opened:
        photo = opened.convert("RGB")
    return photo.crop(box) if box else photo


def place(canvas: Image.Image, source: Image.Image, box: tuple[int, int, int, int], fit=False):
    x0, y0, x1, y1 = box
    width, height = x1 - x0, y1 - y0
    photo = (ImageOps.fit(source, (width, height), Image.Resampling.LANCZOS)
             if fit else ImageOps.contain(source, (width, height), Image.Resampling.LANCZOS))
    canvas.paste(photo, (x0 + (width - photo.width) // 2, y0 + (height - photo.height) // 2))


def save(image: Image.Image, name: str):
    image.save(OUT / name, quality=94, subsampling=0)


sku = {color: img(OUT / f"SKU_2618_{color}.jpg") for color in ("khaki", "black", "brown")}
hero = img(SRC / "2618_公开首图.jpg")
wear = {
    "khaki": img(SRC / "详情原图" / "13.jpg", (15, 653, 785, 1325)),
    "black": img(SRC / "详情原图" / "16.jpg", (15, 485, 785, 1012)),
    "brown": img(SRC / "详情原图" / "19.jpg", (15, 398, 785, 940)),
}
khaki_side = img(SRC / "详情原图" / "25.jpg", (432, 330, 770, 594))
khaki_sole = img(SRC / "详情原图" / "25.jpg", (432, 145, 770, 315))
black_side = img(SRC / "详情原图" / "26.jpg", (432, 333, 770, 610))

# M2 answers which purchasable colors and sizes exist, not the search-hero role.
m2, d = page("COLOR AND SIZE CHOICE", "THREE REAL COLORWAYS", "Model 2618 · EU 39–48 · 30 color-size choices")
for n, (color, title) in enumerate((("black", "BLACK"), ("khaki", "KHAKI"), ("brown", "DARK BROWN"))):
    x = 55 + n * 370
    card(d, (x, 225, x + 350, 943))
    place(m2, sku[color], (x + 10, 260, x + 340, 805))
    label(d, (x + 32, 840), title, 29, GREEN, True)
    label(d, (x + 32, 890), "EU 39–48", 24, MUTED)
card(d, (55, 990, 1145, 1125), PALE)
label(d, (90, 1030), "For quotation: send colors, EU size ratio and quantity.", 28, INK, True)
save(m2, "M2_2618_colors.jpg")

# M3 focuses on verified structure and source-stated material layers.
m3, d = page("CONSTRUCTION", "LACE-UP LOW TOP", "Material labels follow the exact source listing")
card(d, (55, 215, 720, 1020))
place(m3, wear["khaki"], (80, 250, 695, 795), fit=True)
label(d, (92, 850), "LACE-UP CLOSURE", 29, GREEN, True)
label(d, (92, 902), "LOW-TOP SILHOUETTE", 24, MUTED)
card(d, (750, 215, 1145, 1020))
place(m3, khaki_sole, (775, 255, 1120, 445))
for j, line in enumerate(("MESH LINING", "RUBBER OUTSOLE", "RUBBER MIDSOLE")):
    y = 530 + j * 120
    d.rounded_rectangle((785, y, 1105, y + 75), radius=12, fill=PALE)
    label(d, (804, y + 20), line, 22, GREEN, True)
save(m3, "M3_2618_structure.jpg")

# M4: genuine on-foot proof with different contexts from the color-card M2.
m4, d = page("WEARING REFERENCE", "SEE THE REAL SHOE ON FOOT", "Actual model 2618 product photos")
card(d, (55, 225, 765, 1000))
place(m4, wear["black"], (75, 270, 745, 860))
label(d, (86, 925), "BLACK · ON-FOOT SIDE PROFILE", 27, GREEN, True)
for y, color, title in ((225, "khaki", "KHAKI"), (620, "brown", "DARK BROWN")):
    card(d, (790, y, 1145, y + 375))
    place(m4, wear[color], (805, y + 24, 1130, y + 300))
    label(d, (815, y + 323), title, 23, GREEN, True)
label(d, (55, 1054), "Confirm the required EU size mix before purchase.", 22, MUTED)
save(m4, "M4_2618_onfoot.jpg")

# M5: company-level process evidence. It does not represent production of 2618.
m5, d = page("BEIQIANG COMPANY CAPABILITY", "ORDER COORDINATION", "Workshop and order-management capability")
production = img(COMP / "C3_real_production_organization.jpg", (55, 245, 790, 1000))
quality = img(COMP / "C4_real_quality_checkpoints.jpg", (55, 240, 1145, 805))
for x, picture, caption in ((55, production, "PRODUCTION PLANNING"), (610, quality, "QUALITY CHECK POINTS")):
    card(d, (x, 230, x + 535, 942))
    place(m5, picture, (x + 18, 250, x + 517, 820), fit=True)
    label(d, (x + 30, 857), caption, 24, GREEN, True)
card(d, (55, 990, 1145, 1128), PALE)
label(d, (83, 1024), "Sourcing, specification and order details are reviewed per project.", 23, INK, True)
save(m5, "M5_2618_company.jpg")

# M6 is a buyer-input prompt, not a claim that either pack is included.
m6, d = page("ORDER SUPPORT", "SEND A SOURCING BRIEF", "Packing and timing are confirmed for each actual order")
for n, (head, body) in enumerate((
    ("1  COLOR + SIZE", "Black, khaki or dark brown; EU 39–48"),
    ("2  ORDER QUANTITY", "Tell us pairs per color and size"),
    ("3  PACKING NEED", "Ask about bag or box options"),
    ("4  DESTINATION", "Share destination and preferred forwarder"),
)):
    y = 240 + n * 205
    card(d, (70, y, 1130, y + 166), WHITE)
    label(d, (105, y + 33), head, 30, GREEN, True)
    label(d, (105, y + 88), body, 25, MUTED)
label(d, (76, 1094), "Quotation and feasibility depend on the final brief.", 22, INK, True)
save(m6, "M6_2618_brief.jpg")

# D1–D4 are product-specific detail modules; no inherited S6077 or concept art.
d1, d = page("HR002 / MODEL 2618", "MEN'S LACE-UP CASUAL SHOES", "Current product photos · wholesale inquiry")
place(d1, hero, (85, 215, 1115, 930))
for n, tag in enumerate(("LOW TOP", "3 COLORS", "EU 39–48")):
    x = 70 + n * 370
    d.rounded_rectangle((x, 1000, x + 330, 1080), radius=18, fill=PALE)
    label(d, (x + 30, 1023), tag, 25, GREEN, True)
save(d1, "D1_2618_overview.jpg")

d2, d = page("AVAILABLE OPTIONS", "THREE COLORS · EU 39–48", "Confirm each order's color-size quantities before fulfillment")
for n, (color, title) in enumerate((("black", "BLACK"), ("khaki", "KHAKI"), ("brown", "DARK BROWN"))):
    x = 55 + n * 370
    card(d, (x, 235, x + 350, 1020))
    place(d2, sku[color], (x + 10, 260, x + 340, 900))
    label(d, (x + 25, 940), title, 27, GREEN, True)
save(d2, "D2_2618_options.jpg")

d3, d = page("SOURCE-STATED MATERIALS", "SHOE STRUCTURE", "Exact model 2618 · material details from the product source")
card(d, (60, 225, 1140, 630))
place(d3, khaki_side, (86, 245, 640, 595))
label(d, (670, 285), "LOW TOP", 29, GREEN, True)
label(d, (670, 350), "LACE-UP", 29, GREEN, True)
label(d, (670, 415), "MESH LINING", 29, GREEN, True)
card(d, (60, 670, 1140, 1090))
place(d3, khaki_sole, (90, 700, 620, 1045))
label(d, (670, 770), "RUBBER OUTSOLE", 28, GREEN, True)
label(d, (670, 850), "RUBBER MIDSOLE", 28, GREEN, True)
save(d3, "D3_2618_materials.jpg")

d4, d = page("B2B ORDER FLOW", "WHAT TO SEND FOR A QUOTE", "Model 2618 · wholesale inquiry")
place(d4, black_side, (60, 245, 585, 625))
for n, line in enumerate((
    "Selected colors and EU size ratio",
    "Total pairs and target market",
    "Bag or box packing requirements",
    "Destination and order timing",
)):
    y = 300 + n * 130
    d.ellipse((650, y + 9, 674, y + 33), fill=GREEN)
    label(d, (702, y), line, 25, INK, True)
card(d, (60, 850, 1140, 1085), PALE)
label(d, (100, 895), "We reconfirm price, color-size availability", 27, GREEN, True)
label(d, (100, 945), "and timing before accepting the order.", 27, GREEN, True)
save(d4, "D4_2618_quote.jpg")

names = [
    "M1A_2618_khaki.jpg", "M2_2618_colors.jpg", "M3_2618_structure.jpg",
    "M4_2618_onfoot.jpg", "M5_2618_company.jpg", "M6_2618_brief.jpg",
    "D1_2618_overview.jpg", "D2_2618_options.jpg", "D3_2618_materials.jpg",
    "D4_2618_quote.jpg",
]
sheet = Image.new("RGB", (1600, 830), "#e6ece9")
sd = ImageDraw.Draw(sheet)
for n, name in enumerate(names):
    with Image.open(OUT / name) as picture:
        small = picture.resize((300, 300), Image.Resampling.LANCZOS)
    x = (n % 5) * 320 + 10
    y = (n // 5) * 410 + 10
    sheet.paste(small, (x, y))
    label(sd, (x, y + 310), name.removesuffix(".jpg"), 18, INK, True)
sheet.save(OUT / "contact_gallery.jpg", quality=90)
print(OUT)
