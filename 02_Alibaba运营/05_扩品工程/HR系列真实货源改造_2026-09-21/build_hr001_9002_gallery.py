from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
PROJECT = ROOT / r"02_Alibaba运营\05_扩品工程\HR系列真实货源改造_2026-09-21"
SOURCE = PROJECT / r"00_来源素材\HR001_9002"
COMPANY = ROOT / r"02_Alibaba运营\06_图片与检查记录\公司图复用模板_v4_2026-09-21"
OUT = PROJECT / r"01_正式主图候选\HR001_9002"
DETAIL_OUT = PROJECT / r"02_正式详情候选\HR001_9002"
OUT.mkdir(parents=True, exist_ok=True)
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
        fitted = ImageOps.contain(
            src.convert("RGB"),
            (size[0] - pad * 2, size[1] - pad * 2),
            Image.Resampling.LANCZOS,
        )
    frame = Image.new("RGB", size, bg)
    frame.paste(fitted, ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2))
    return frame


def save(image, folder: Path, name: str):
    image.convert("RGB").save(folder / name, quality=94, subsampling=0)


def contact_sheet(folder: Path, names: list[Path], output_name: str):
    sheet = Image.new("RGB", (1200, 820), "#E2E7E5")
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(names):
        x = (index % 3) * 400
        y = (index // 3) * 410
        sheet.paste(contain(path, (390, 360), WHITE, 5), (x + 5, y + 5))
        text(draw, (x + 18, y + 370), path.stem, 17, INK, True)
    sheet.save(folder / output_name, quality=92)


light = SOURCE / "02_gallery.webp"
dark = SOURCE / "03_gallery.webp"
dark_pair = SOURCE / "04_gallery.webp"
dark_sole = SOURCE / "05_gallery.webp"
light_sole = SOURCE / "06_gallery.webp"

# Clean real-photo SKU swatches for the two confirmed colorways.
save(contain(light, (W, H), WHITE, 25), OUT, "SKU_9002_light.jpg")
save(contain(dark, (W, H), WHITE, 25), OUT, "SKU_9002_dark.jpg")


# M1: product-first hero; real shoe remains unchanged.
m1 = contain(light, (W, H), WHITE, 25)
d = ImageDraw.Draw(m1)
d.rounded_rectangle((838, 48, 1150, 142), radius=18, fill=GREEN)
text(d, (994, 80), "WHOLESALE · B2B", 25, WHITE, True, "mm")
text(d, (994, 115), "MODEL 9002", 18, WHITE, True, "mm")
save(m1, OUT, "M1_9002_b2b.jpg")


# M2: actual SKU choices and order inputs.
m2 = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(m2)
header(d, "SKU CHOICE", "2 COLORS · EU 38–47", "Confirm quantity and size ratio before quotation")
for index, (path, label) in enumerate([
    (light, "LIGHT GRAY / BEIGE SOLE"),
    (dark, "DARK GRAY / BLACK SOLE"),
]):
    x0 = 70 + index * 550
    rounded_card(m2, (x0, 220, x0 + 510, 900))
    m2.paste(contain(path, (470, 520), WHITE, 8), (x0 + 20, 250))
    text(d, (x0 + 255, 810), label, 23, INK, True, "mm")
    text(d, (x0 + 255, 856), "MODEL 9002", 20, GREEN, True, "mm")
rounded_card(m2, (70, 950, 1130, 1118), fill=PALE, outline=PALE)
text(d, (110, 985), "BUYER INPUT", 19, GREEN, True)
text(d, (110, 1025), "Selected colors · Size ratio · Order quantity", 30, INK, True)
save(m2, OUT, "M2_9002_colors_sizes.jpg")


# M3: construction proof from distinct real views.
m3 = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(m3)
header(d, "PRODUCT PROOF", "VISIBLE CONSTRUCTION", "Exact Model 9002 source-photo evidence")
for index, (path, label) in enumerate([
    (light, "TEXTILE UPPER"),
    (dark_sole, "BLACK EVA OUTSOLE"),
    (light_sole, "BEIGE EVA OUTSOLE"),
]):
    x0 = 60 + index * 380
    rounded_card(m3, (x0, 230, x0 + 340, 980))
    with Image.open(path) as src:
        panel = ImageOps.fit(src.convert("RGB"), (300, 610), Image.Resampling.LANCZOS)
    m3.paste(panel, (x0 + 20, 250))
    text(d, (x0 + 170, 916), label, 20, GREEN, True, "mm")
rounded_card(m3, (60, 1020, 1140, 1125), fill=GREEN, outline=GREEN)
text(d, (600, 1072), "SLIP-ON STRUCTURE · EVA OUTSOLE", 22, WHITE, True, "mm")
save(m3, OUT, "M3_9002_construction.jpg")


# M4: custom-project inputs; no unconditional customization promise.
m4 = Image.new("RGB", (W, H), "#F7F4EC")
d = ImageDraw.Draw(m4)
header(d, "OEM / ODM DISCUSSION", "SEND A CLEAR PROJECT BRIEF", "Scope is reviewed against quantity and requirements")
m4.paste(contain(dark_pair, (520, 760), WHITE, 12), (70, 250))
for index, (num, title, body) in enumerate([
    ("01", "LOGO / ARTWORK", "Placement and reference files"),
    ("02", "TARGET COLOR", "Color reference or target range"),
    ("03", "ORDER MATRIX", "Quantity, sizes and ratio"),
    ("04", "PACKING NEED", "Bag, shoe box, label or marks"),
]):
    y = 250 + index * 185
    rounded_card(m4, (640, y, 1130, y + 150), fill=WHITE)
    text(d, (675, y + 34), num, 18, GREEN, True)
    text(d, (735, y + 30), title, 24, INK, True)
    text(d, (735, y + 78), body, 20, MUTED)
rounded_card(m4, (70, 1050, 1130, 1130), fill=GREEN, outline=GREEN)
text(d, (600, 1090), "SEND REFERENCES FOR FEASIBILITY REVIEW", 21, WHITE, True, "mm")
save(m4, OUT, "M4_9002_oem_inputs.jpg")


# M5: verified reusable company proof.
m5 = Image.new("RGB", (W, H), "#073F34")
d = ImageDraw.Draw(m5)
text(d, (70, 58), "SUPPLIER PROOF", 22, "#B6D8CB", True)
text(d, (70, 96), "PRODUCTION + QUALITY WORKFLOW", 42, WHITE, True)
text(d, (70, 153), "Real workshop and visible order-review activities", 22, "#DCEBE5")
with Image.open(COMPANY / "C3_real_production_organization.jpg") as src:
    workshop = ImageOps.fit(src.convert("RGB").crop((55, 245, 790, 1000)), (510, 700), Image.Resampling.LANCZOS)
with Image.open(COMPANY / "C4_real_quality_checkpoints.jpg") as src:
    qc = ImageOps.fit(src.convert("RGB").crop((55, 240, 1145, 805)), (510, 700), Image.Resampling.LANCZOS)
m5.paste(workshop, (70, 230))
m5.paste(qc, (620, 230))
text(d, (325, 970), "WORKSHOP ORGANIZATION", 21, WHITE, True, "mm")
text(d, (875, 970), "VISIBLE QUALITY CHECKPOINTS", 21, WHITE, True, "mm")
d.rounded_rectangle((70, 1030, 1130, 1125), radius=24, fill="#E9F1EE")
text(d, (600, 1077), "ORDER REQUIREMENTS ARE REVIEWED BEFORE PRODUCTION", 20, GREEN, True, "mm")
save(m5, OUT, "M5_factory_quality.jpg")


# M6: packaging options and quotation inputs.
m6 = Image.new("RGB", (W, H), "#EAF1F4")
d = ImageDraw.Draw(m6)
header(d, "PACKING + QUOTATION", "CONFIRM OPTIONS BEFORE ORDER", "Packing and freight are confirmed for the actual order")
for index, (title, body) in enumerate([
    ("PLASTIC BAG", "Discuss individual bag, label and marks"),
    ("SHOE BOX", "Confirm box requirement and quotation impact"),
]):
    x0 = 70 + index * 550
    rounded_card(m6, (x0, 250, x0 + 510, 620), fill=WHITE)
    if index == 0:
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
for index, line in enumerate(["Order quantity", "Selected colors + size ratio", "Packing and destination"]):
    y = 795 + index * 70
    d.ellipse((112, y + 6, 130, y + 24), fill=GREEN)
    text(d, (155, y), line, 29, INK, True)
rounded_card(m6, (70, 1070, 1130, 1140), fill=GREEN, outline=GREEN)
text(d, (600, 1105), "OPTIONS ARE CONFIRMED WITH THE FINAL QUOTATION", 19, WHITE, True, "mm")
save(m6, OUT, "M6_packing_quote.jpg")


# D1: exact product identity.
d1 = Image.new("RGB", (W, H), WHITE)
d = ImageDraw.Draw(d1)
header(d, "MODEL HR001-A / 9002", "MEN'S KNIT SLIP-ON WALKING SHOES", "Wholesale offer for importers, wholesalers and online sellers")
d1.paste(contain(light, (880, 680), WHITE, 5), (160, 225))
for index, label in enumerate(["TEXTILE UPPER", "SLIP-ON", "EU 38–47", "2 COLORS"]):
    x0 = 65 + index * 285
    d.rounded_rectangle((x0, 955, x0 + 250, 1028), radius=30, fill=PALE)
    text(d, (x0 + 125, 991), label, 18, GREEN, True, "mm")
text(d, (600, 1090), "Final order details are confirmed before quotation", 21, MUTED, False, "mm")
save(d1, DETAIL_OUT, "D1_product_overview.jpg")


# D2: verified facts only.
d2 = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(d2)
header(d, "VERIFIED PRODUCT FACTS", "MODEL 9002 SPECIFICATIONS", "Fields mapped to the current source page")
facts = [
    ("TARGET", "Men"),
    ("UPPER", "Textile Upper"),
    ("OUTSOLE", "EVA"),
    ("CLOSURE", "Slip-On / No Laces"),
    ("SEASON", "Autumn 2026"),
    ("SIZE RANGE", "EU 38–47"),
    ("COLORS", "Light Gray/Beige · Dark Gray/Black"),
]
rounded_card(d2, (65, 225, 690, 1080), fill=WHITE)
for index, (label, value) in enumerate(facts):
    y = 270 + index * 108
    text(d, (105, y), label, 17, GREEN, True)
    text(d, (105, y + 34), value, 24, INK, True)
    if index < len(facts) - 1:
        d.line((105, y + 86, 650, y + 86), fill=BORDER, width=2)
d2.paste(contain(dark, (410, 650), WHITE, 10), (735, 270))
rounded_card(d2, (735, 955, 1145, 1080), fill=PALE, outline=PALE)
text(d, (940, 995), "FINAL CONFIRMATION", 19, GREEN, True, "mm")
text(d, (940, 1032), "Size ratio and packing before order", 16, MUTED, False, "mm")
save(d2, DETAIL_OUT, "D2_verified_specs.jpg")


# D3: color-size order matrix.
d3 = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(d3)
header(d, "ORDER MATRIX", "COLOR + SIZE SELECTION", "Send required quantity for each selected EU size")
for index, (path, label) in enumerate([(light, "LIGHT GRAY"), (dark, "DARK GRAY")]):
    x0 = 75 + index * 355
    rounded_card(d3, (x0, 240, x0 + 320, 650), fill=WHITE)
    d3.paste(contain(path, (280, 280), WHITE, 8), (x0 + 20, 270))
    text(d, (x0 + 160, 595), label, 20, INK, True, "mm")
text(d, (830, 250), "EU SIZE RANGE", 22, GREEN, True)
for index, value in enumerate([str(x) for x in range(38, 48)]):
    col = index % 3
    row = index // 3
    x0 = 805 + col * 110
    y0 = 310 + row * 95
    d.rounded_rectangle((x0, y0, x0 + 82, y0 + 62), radius=16, fill=PALE, outline=BORDER, width=2)
    text(d, (x0 + 41, y0 + 31), value, 22, GREEN, True, "mm")
rounded_card(d3, (75, 735, 1125, 1055), fill=WHITE)
text(d, (115, 780), "BUYER CHECKLIST", 20, GREEN, True)
for index, line in enumerate(["Selected color", "Pairs per EU size", "Total quantity + packing requirement"]):
    y = 835 + index * 62
    d.ellipse((116, y + 6, 132, y + 22), fill=GREEN)
    text(d, (155, y), line, 25, INK, True)
text(d, (600, 1115), "FINAL SIZE RATIO IS CONFIRMED BEFORE ORDER", 18, MUTED, True, "mm")
save(d3, DETAIL_OUT, "D3_colors_sizes.jpg")


# D4: safe wholesale pricing; lowest tier stays above 130% of CNY 55 at 6.7487 CNY/USD.
d4 = Image.new("RGB", (W, H), "#F7F4EC")
d = ImageDraw.Draw(d4)
header(d, "WHOLESALE ORDER", "CURRENT PRICE TIERS", "Freight is quoted separately for destination and quantity")
for index, (qty, price) in enumerate([
    ("2–49 PAIRS", "USD 11.90 / pair"),
    ("50–99 PAIRS", "USD 11.50 / pair"),
    ("100+ PAIRS", "USD 10.90 / pair"),
]):
    y = 255 + index * 150
    rounded_card(d4, (75, y, 760, y + 118), fill=WHITE)
    text(d, (115, y + 38), qty, 22, GREEN, True)
    text(d, (715, y + 59), price, 28, INK, True, "rm")
rounded_card(d4, (75, 760, 1125, 1050), fill=WHITE)
text(d, (115, 805), "QUOTE INPUTS", 20, GREEN, True)
for index, line in enumerate(["Selected colors and size ratio", "Packing requirement", "Destination country, city or port"]):
    y = 855 + index * 58
    d.ellipse((116, y + 7, 132, y + 23), fill=GREEN)
    text(d, (155, y), line, 24, INK, True)
text(d, (600, 1110), "FREIGHT QUOTED SEPARATELY", 18, GREEN, True, "mm")
save(d4, DETAIL_OUT, "D4_price_quote.jpg")


# D5: custom-project workflow.
d5 = Image.new("RGB", (W, H), "#F7F4EC")
d = ImageDraw.Draw(d5)
header(d, "CUSTOM PROJECT FLOW", "FROM BUYER BRIEF TO QUOTATION", "Each step is confirmed against the actual order")
for index, (num, title, body) in enumerate([
    ("1", "BUYER BRIEF", "Model, quantity, market and packing"),
    ("2", "ARTWORK REVIEW", "Logo, label and placement files"),
    ("3", "FEASIBILITY CHECK", "Color, size ratio and requested changes"),
    ("4", "FINAL QUOTATION", "Product, packing, freight and timing"),
]):
    col = index % 2
    row = index // 2
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
text(d, (110, 928), "Send references and target order information", 30, INK, True)
text(d, (110, 978), "We review feasibility before any commercial commitment.", 21, MUTED)
rounded_card(d5, (70, 1070, 1130, 1140), fill=GREEN, outline=GREEN)
text(d, (600, 1105), "START WITH A CLEAR BRIEF", 20, WHITE, True, "mm")
save(d5, DETAIL_OUT, "D5_oem_project_inputs.jpg")


contact_sheet(OUT, sorted(OUT.glob("M*.jpg")), "CONTACT_HR001_9002.jpg")
contact_sheet(DETAIL_OUT, sorted(DETAIL_OUT.glob("D*.jpg")), "CONTACT_HR001_9002_DETAILS.jpg")
print(OUT)
print(DETAIL_OUT)
