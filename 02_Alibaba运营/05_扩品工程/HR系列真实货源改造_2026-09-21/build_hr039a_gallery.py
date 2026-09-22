from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(r"C:\Users\spq\Desktop\贝强")
PROJECT = ROOT / r"02_Alibaba运营\05_扩品工程\HR系列真实货源改造_2026-09-21"
SOURCE = ROOT / r"01_产品资产\02_可发布素材\00_最终上传\BQ036_8025"
COMPANY = ROOT / r"02_Alibaba运营\06_图片与检查记录\公司图复用模板_v4_2026-09-21"
OUT = PROJECT / "01_正式主图候选" / "HR039-A_8025"
OUT.mkdir(parents=True, exist_ok=True)
DETAIL_OUT = PROJECT / "02_正式详情候选" / "HR039-A_8025"
DETAIL_OUT.mkdir(parents=True, exist_ok=True)

W = H = 1200
WHITE = "#FFFFFF"
BG = "#F4F7F6"
INK = "#152129"
MUTED = "#59666C"
GREEN = "#075440"
PALE = "#E8F2EE"
BORDER = "#D4DEDA"


def font(size: int, bold: bool = False):
    choices = [
        Path(r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf"),
    ]
    for choice in choices:
        if choice.exists():
            return ImageFont.truetype(str(choice), size)
    return ImageFont.load_default()


def text(draw, xy, value, size, color=INK, bold=False, anchor=None):
    draw.text(xy, value, font=font(size, bold), fill=color, anchor=anchor)


def header(draw, kicker, title, subtitle=None):
    text(draw, (70, 58), kicker.upper(), 22, GREEN, True)
    text(draw, (70, 92), title, 46, INK, True)
    if subtitle:
        text(draw, (70, 153), subtitle, 22, MUTED)


def rounded_card(canvas, box, fill=WHITE, outline=BORDER, radius=24):
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=2)
    canvas.paste(overlay, (0, 0), overlay)


def contain(path: Path, size, bg=WHITE, pad=20):
    with Image.open(path) as src:
        src = src.convert("RGB")
        fitted = ImageOps.contain(src, (size[0] - pad * 2, size[1] - pad * 2), Image.Resampling.LANCZOS)
    frame = Image.new("RGB", size, bg)
    frame.paste(fitted, ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2))
    return frame


def save(image, name):
    image.convert("RGB").save(OUT / name, quality=94, subsampling=0)


# M1 — resize the already reviewed real-photo candidate without changing content.
with Image.open(PROJECT / "05_AI候选" / "HR039-A_8025_B2B_M1_candidate_v2.png") as src:
    m1 = ImageOps.fit(src.convert("RGB"), (W, H), Image.Resampling.LANCZOS)
    md = ImageDraw.Draw(m1)
    md.rectangle((860, 42, 1160, 125), fill=GREEN)
    text(md, (1010, 70), "WHOLESALE · B2B", 25, WHITE, True, "mm")
    text(md, (1010, 103), "MODEL 8025", 18, WHITE, True, "mm")
    save(m1, "M1_8025_wholesale.jpg")


# M2 — real color and size choice.
m2 = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(m2)
header(d, "SKU CHOICE", "2 COLORS · EU 35–45", "Confirm quantity and size ratio before quotation")
cards = [
    (SOURCE / "03_颜色图" / "01_black_white.jpg", "BLACK / WHITE"),
    (SOURCE / "03_颜色图" / "02_all_black.jpg", "ALL BLACK"),
]
for i, (path, label) in enumerate(cards):
    x0 = 70 + i * 550
    rounded_card(m2, (x0, 220, x0 + 510, 900))
    panel = contain(path, (470, 520), WHITE, 10)
    m2.paste(panel, (x0 + 20, 250))
    text(d, (x0 + 255, 810), label, 27, INK, True, "mm")
    text(d, (x0 + 255, 856), "MODEL 8025", 20, GREEN, True, "mm")
rounded_card(m2, (70, 950, 1130, 1118), fill=PALE, outline=PALE)
text(d, (110, 985), "BUYER INPUT", 19, GREEN, True)
text(d, (110, 1025), "Selected colors · Size ratio · Order quantity", 30, INK, True)
save(m2, "M2_8025_colors_sizes.jpg")


# M3 — three distinct visible construction views.
m3 = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(m3)
header(d, "PRODUCT PROOF", "VISIBLE CONSTRUCTION", "Three views from the real Model 8025 photo set")
proofs = [
    (SOURCE / "01_主图" / "02_upper.jpg", "KNIT UPPER"),
    (SOURCE / "01_主图" / "03_structure.jpg", "SLIP-ON OPENING"),
    (SOURCE / "01_主图" / "04_sole.jpg", "OUTSOLE VIEW"),
]
for i, (path, label) in enumerate(proofs):
    x0 = 60 + i * 380
    rounded_card(m3, (x0, 230, x0 + 340, 980))
    panel = ImageOps.fit(Image.open(path).convert("RGB"), (300, 610), Image.Resampling.LANCZOS)
    m3.paste(panel, (x0 + 20, 250))
    text(d, (x0 + 170, 916), label, 22, GREEN, True, "mm")
rounded_card(m3, (60, 1020, 1140, 1125), fill=GREEN, outline=GREEN)
text(d, (600, 1072), "THREE VIEWS FROM THE REAL PRODUCT SET", 22, WHITE, True, "mm")
save(m3, "M3_8025_construction.jpg")


# M4 — inquiry inputs, not an unconditional customization promise.
m4 = Image.new("RGB", (W, H), "#F7F4EC")
d = ImageDraw.Draw(m4)
header(d, "OEM / ODM DISCUSSION", "SEND A CLEAR PROJECT BRIEF", "Final scope is confirmed against quantity and requirements")
product = contain(SOURCE / "01_主图" / "03_structure.jpg", (520, 760), WHITE, 18)
m4.paste(product, (70, 250))
items = [
    ("01", "LOGO / ARTWORK", "Send placement and reference files"),
    ("02", "TARGET COLOR", "Share color reference or target range"),
    ("03", "ORDER MATRIX", "Quantity, sizes and ratio"),
    ("04", "PACKING NEED", "Bag, shoe box, label or marks"),
]
for i, (num, title, body) in enumerate(items):
    y = 250 + i * 185
    rounded_card(m4, (640, y, 1130, y + 150), fill=WHITE)
    text(d, (675, y + 34), num, 18, GREEN, True)
    text(d, (735, y + 30), title, 24, INK, True)
    text(d, (735, y + 78), body, 20, MUTED)
rounded_card(m4, (70, 1050, 1130, 1130), fill=GREEN, outline=GREEN)
text(d, (600, 1090), "SEND REFERENCES FOR FEASIBILITY REVIEW", 21, WHITE, True, "mm")
save(m4, "M4_8025_oem_inputs.jpg")


# M5 — gallery-specific production + quality collage from verified company templates.
m5 = Image.new("RGB", (W, H), "#073F34")
d = ImageDraw.Draw(m5)
text(d, (70, 58), "SUPPLIER PROOF", 22, "#B6D8CB", True)
text(d, (70, 96), "PRODUCTION + QUALITY WORKFLOW", 42, WHITE, True)
text(d, (70, 153), "Real workshop and visible order-review activities", 22, "#DCEBE5")
with Image.open(COMPANY / "C3_real_production_organization.jpg") as src:
    workshop = src.convert("RGB").crop((55, 245, 790, 1000))
    workshop = ImageOps.fit(workshop, (510, 700), Image.Resampling.LANCZOS)
with Image.open(COMPANY / "C4_real_quality_checkpoints.jpg") as src:
    qc = src.convert("RGB").crop((55, 240, 1145, 805))
    qc = ImageOps.fit(qc, (510, 700), Image.Resampling.LANCZOS)
m5.paste(workshop, (70, 230))
m5.paste(qc, (620, 230))
text(d, (325, 970), "WORKSHOP ORGANIZATION", 21, WHITE, True, "mm")
text(d, (875, 970), "VISIBLE QUALITY CHECKPOINTS", 21, WHITE, True, "mm")
d.rounded_rectangle((70, 1030, 1130, 1125), radius=24, fill="#E9F1EE")
text(d, (600, 1077), "ORDER REQUIREMENTS ARE REVIEWED BEFORE PRODUCTION", 20, GREEN, True, "mm")
save(m5, "M5_factory_quality.jpg")


# M6 — available packing discussions + quotation inputs; not included-price claims.
m6 = Image.new("RGB", (W, H), "#EAF1F4")
d = ImageDraw.Draw(m6)
header(d, "PACKING + QUOTATION", "CONFIRM OPTIONS BEFORE ORDER", "Packing method and freight are confirmed for the actual order")
for i, (title, body) in enumerate([
    ("PLASTIC BAG", "Discuss individual bag, label and marks"),
    ("SHOE BOX", "Confirm box requirement and quotation impact"),
]):
    x0 = 70 + i * 550
    rounded_card(m6, (x0, 250, x0 + 510, 620), fill=WHITE)
    # Simple neutral line icon: option illustration, not a photograph or inclusion claim.
    if i == 0:
        d.rounded_rectangle((x0 + 160, 300, x0 + 350, 455), radius=22, outline=GREEN, width=7)
        d.line((x0 + 190, 300, x0 + 205, 265, x0 + 305, 265, x0 + 320, 300), fill=GREEN, width=7)
    else:
        d.rectangle((x0 + 145, 315, x0 + 365, 455), outline=GREEN, width=7)
        d.line((x0 + 145, 315, x0 + 245, 255, x0 + 365, 315), fill=GREEN, width=7)
        d.line((x0 + 245, 255, x0 + 245, 395), fill=GREEN, width=5)
    text(d, (x0 + 255, 505), title, 28, INK, True, "mm")
    text(d, (x0 + 255, 555), body, 18, MUTED, False, "mm")
rounded_card(m6, (70, 690, 1130, 1035), fill=WHITE)
text(d, (110, 730), "SEND FOR QUOTATION", 22, GREEN, True)
for i, line in enumerate(["Order quantity", "Selected colors + size ratio", "Packing and destination"]):
    y = 795 + i * 70
    d.ellipse((112, y + 6, 130, y + 24), fill=GREEN)
    text(d, (155, y), line, 29, INK, True)
rounded_card(m6, (70, 1070, 1130, 1140), fill=GREEN, outline=GREEN)
text(d, (600, 1105), "OPTIONS ARE CONFIRMED WITH THE FINAL QUOTATION", 19, WHITE, True, "mm")
save(m6, "M6_packing_quote_inputs.jpg")


# Review contact sheet.
names = sorted(OUT.glob("M*.jpg"))
sheet = Image.new("RGB", (1200, 820), "#E2E7E5")
sd = ImageDraw.Draw(sheet)
for idx, path in enumerate(names):
    x = (idx % 3) * 400
    y = (idx // 3) * 410
    thumb = contain(path, (390, 360), WHITE, 5)
    sheet.paste(thumb, (x + 5, y + 5))
    text(sd, (x + 18, y + 370), path.stem, 18, INK, True)
sheet.save(OUT / "CONTACT_HR039A.jpg", quality=92)

print(OUT)


def save_detail(image, name):
    image.convert("RGB").save(DETAIL_OUT / name, quality=94, subsampling=0)


# D1 — exact product identity and verified choices.
d1 = Image.new("RGB", (W, H), WHITE)
d = ImageDraw.Draw(d1)
header(d, "MODEL HR039-A / 8025", "HIGH TOP KNIT SLIP-ON SHOES", "Wholesale offer for importers, wholesalers and online sellers")
hero = contain(SOURCE / "01_主图" / "01_main.jpg", (880, 680), WHITE, 5)
d1.paste(hero, (160, 225))
for i, label in enumerate(["REGULAR FIT", "SLIP-ON", "EU 35–45", "2 COLORS"]):
    x0 = 65 + i * 285
    d.rounded_rectangle((x0, 955, x0 + 250, 1028), radius=30, fill=PALE)
    text(d, (x0 + 125, 991), label, 20, GREEN, True, "mm")
text(d, (600, 1090), "Final order details are confirmed before quotation", 21, MUTED, False, "mm")
save_detail(d1, "D1_product_overview.jpg")


# D2 — verified product facts only.
d2 = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(d2)
header(d, "VERIFIED PRODUCT FACTS", "MODEL 8025 SPECIFICATIONS", "Product fields must stay consistent with the real source")
facts = [
    ("FIT", "Regular Fit"),
    ("UPPER", "High Top Knitted Textile Upper"),
    ("SOLE", "EVA Sole"),
    ("CLOSURE", "Slip-On"),
    ("TOE", "Round Toe"),
    ("SIZE RANGE", "EU 35–45"),
    ("COLORS", "Black/White · All Black"),
]
rounded_card(d2, (65, 225, 690, 1080), fill=WHITE)
for i, (label, value) in enumerate(facts):
    y = 270 + i * 108
    text(d, (105, y), label, 17, GREEN, True)
    text(d, (105, y + 34), value, 26, INK, True)
    if i < len(facts) - 1:
        d.line((105, y + 86, 650, y + 86), fill=BORDER, width=2)
spec_img = contain(SOURCE / "01_主图" / "02_upper.jpg", (410, 650), WHITE, 10)
d2.paste(spec_img, (735, 270))
rounded_card(d2, (735, 955, 1145, 1080), fill=PALE, outline=PALE)
text(d, (940, 995), "FINAL CONFIRMATION", 19, GREEN, True, "mm")
text(d, (940, 1032), "Size ratio and packing before order", 16, MUTED, False, "mm")
save_detail(d2, "D2_verified_specs.jpg")


# D3 — dedicated color + size order matrix, distinct from gallery M2.
d3 = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(d3)
header(d, "ORDER MATRIX", "COLOR + SIZE SELECTION", "Send the required quantity for each selected EU size")
for i, (path, label) in enumerate(cards):
    x0 = 75 + i * 355
    rounded_card(d3, (x0, 240, x0 + 320, 650), fill=WHITE)
    panel = contain(path, (280, 280), WHITE, 8)
    d3.paste(panel, (x0 + 20, 270))
    text(d, (x0 + 160, 595), label, 20, INK, True, "mm")
text(d, (830, 250), "EU SIZE RANGE", 22, GREEN, True)
sizes = ["35", "36", "37", "38", "39", "40", "41", "42", "43", "44", "45"]
for i, value in enumerate(sizes):
    col = i % 3
    row = i // 3
    x0 = 805 + col * 110
    y0 = 310 + row * 95
    d.rounded_rectangle((x0, y0, x0 + 82, y0 + 62), radius=16, fill=PALE, outline=BORDER, width=2)
    text(d, (x0 + 41, y0 + 31), value, 22, GREEN, True, "mm")
rounded_card(d3, (75, 735, 1125, 1055), fill=WHITE)
text(d, (115, 780), "BUYER CHECKLIST", 20, GREEN, True)
for i, line in enumerate(["Selected color", "Pairs per EU size", "Total quantity + packing requirement"]):
    y = 835 + i * 62
    d.ellipse((116, y + 6, 132, y + 22), fill=GREEN)
    text(d, (155, y), line, 25, INK, True)
text(d, (600, 1115), "FINAL SIZE RATIO IS CONFIRMED BEFORE ORDER", 18, MUTED, True, "mm")
save_detail(d3, "D3_colors_sizes.jpg")


# D4 — current safe pricing and quote conditions.
d4 = Image.new("RGB", (W, H), "#F7F4EC")
d = ImageDraw.Draw(d4)
header(d, "WHOLESALE ORDER", "CURRENT PRICE TIERS", "Freight is quoted separately for destination and quantity")
tiers = [
    ("2–49 PAIRS", "USD 12.90 / pair"),
    ("50–99 PAIRS", "USD 12.50 / pair"),
    ("100+ PAIRS", "USD 12.00 / pair"),
]
for i, (qty, price) in enumerate(tiers):
    y = 255 + i * 150
    rounded_card(d4, (75, y, 760, y + 118), fill=WHITE)
    text(d, (115, y + 38), qty, 22, GREEN, True)
    text(d, (715, y + 59), price, 28, INK, True, "rm")
rounded_card(d4, (75, 760, 1125, 1050), fill=WHITE)
text(d, (115, 805), "QUOTE INPUTS", 20, GREEN, True)
for i, line in enumerate(["Selected colors and size ratio", "Packing requirement", "Destination country, city or port"]):
    y = 855 + i * 58
    d.ellipse((116, y + 7, 132, y + 23), fill=GREEN)
    text(d, (155, y), line, 24, INK, True)
text(d, (600, 1110), "FREIGHT QUOTED SEPARATELY", 18, GREEN, True, "mm")
save_detail(d4, "D4_price_quote.jpg")


# D5 — custom-project sequence, distinct from gallery M4.
d5 = Image.new("RGB", (W, H), "#F7F4EC")
d = ImageDraw.Draw(d5)
header(d, "CUSTOM PROJECT FLOW", "FROM BUYER BRIEF TO QUOTATION", "Each step is confirmed against the actual order requirements")
steps = [
    ("1", "BUYER BRIEF", "Model, quantity, market and packing"),
    ("2", "ARTWORK REVIEW", "Logo, label and placement files"),
    ("3", "FEASIBILITY CHECK", "Color, size ratio and requested changes"),
    ("4", "FINAL QUOTATION", "Product, packing, freight and timing"),
]
for i, (num, title, body) in enumerate(steps):
    col = i % 2
    row = i // 2
    x0 = 70 + col * 550
    y0 = 250 + row * 270
    rounded_card(d5, (x0, y0, x0 + 510, y0 + 220), fill=WHITE)
    d.ellipse((x0 + 32, y0 + 32, x0 + 86, y0 + 86), fill=GREEN)
    text(d, (x0 + 59, y0 + 59), num, 19, WHITE, True, "mm")
    text(d, (x0 + 112, y0 + 38), title, 24, INK, True)
    text(d, (x0 + 112, y0 + 91), body, 19, MUTED)
    text(d, (x0 + 112, y0 + 138), "Confirm before next step", 17, GREEN, True)
rounded_card(d5, (70, 835, 1130, 1035), fill=PALE, outline=PALE)
text(d, (110, 880), "BUYER ACTION", 20, GREEN, True)
text(d, (110, 928), "Send references and the target order information", 30, INK, True)
text(d, (110, 978), "We review feasibility before any commercial commitment.", 21, MUTED)
rounded_card(d5, (70, 1070, 1130, 1140), fill=GREEN, outline=GREEN)
text(d, (600, 1105), "START WITH A CLEAR BRIEF", 20, WHITE, True, "mm")
save_detail(d5, "D5_oem_project_inputs.jpg")


# Detail review sheet.
detail_names = sorted(DETAIL_OUT.glob("D*.jpg"))
detail_sheet = Image.new("RGB", (1200, 820), "#E2E7E5")
dd = ImageDraw.Draw(detail_sheet)
for idx, path in enumerate(detail_names):
    x = (idx % 3) * 400
    y = (idx // 3) * 410
    thumb = contain(path, (390, 360), WHITE, 5)
    detail_sheet.paste(thumb, (x + 5, y + 5))
    text(dd, (x + 18, y + 370), path.stem, 18, INK, True)
detail_sheet.save(DETAIL_OUT / "CONTACT_HR039A_DETAILS.jpg", quality=92)

print(DETAIL_OUT)
