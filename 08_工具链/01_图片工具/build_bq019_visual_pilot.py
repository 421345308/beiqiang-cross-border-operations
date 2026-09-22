from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
import json


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
OUT = ROOT / "02_Alibaba运营/02_单品优化记录/BQ系列持续优化_2026-09-14/BQ019_W1_整页视觉样板_2026-09-16"
MAIN = OUT / "01_主图六张"
DETAIL = OUT / "02_产品详情六张"
COMPANY = OUT / "03_公司详情五张"
PREVIEW = OUT / "04_整组预览"
for p in (MAIN, DETAIL, COMPANY, PREVIEW):
    p.mkdir(parents=True, exist_ok=True)

PRODUCT = ROOT / "01_产品资产/02_可发布素材/00_最终上传/BQ019_A206"
RAW = ROOT / "01_产品资产/01_原始数据包/已整理_BQ019_A206_A206情侣鞋图片/A206情侣鞋图片/主图"
FACTORY = ROOT / "01_产品资产/02_可发布素材/00_最终上传/00_厂家资料/00_精选可用照片"
AI_BG = ROOT / "01_产品资产/02_可发布素材/00_最终上传/00_共用中性公司图_v3_2026-09-04/00_ai_background.png"
CAND = ROOT / "02_Alibaba运营/02_单品优化记录/BQ系列持续优化_2026-09-14/BQ019_W1_D7整组候选_2026-09-15/候选六图"

W = H = 1200
GREEN = "#155F4A"
GREEN2 = "#0F4436"
MINT = "#E9F3EF"
CREAM = "#F5F1E8"
INK = "#15212A"
MUTED = "#5C6872"
LINE = "#D7E2DD"
WHITE = "#FFFFFF"


def font(size, bold=False):
    name = "arialbd.ttf" if bold else "arial.ttf"
    return ImageFont.truetype(str(Path(r"C:\Windows\Fonts") / name), size)


def open_rgb(path):
    return Image.open(path).convert("RGB")


def cover(img, size, focus=(0.5, 0.5)):
    img = img.copy()
    ratio = max(size[0] / img.width, size[1] / img.height)
    img = img.resize((round(img.width * ratio), round(img.height * ratio)), Image.Resampling.LANCZOS)
    x = max(0, min(img.width - size[0], round((img.width - size[0]) * focus[0])))
    y = max(0, min(img.height - size[1], round((img.height - size[1]) * focus[1])))
    return img.crop((x, y, x + size[0], y + size[1]))


def contain(img, size, bg=WHITE, pad=0):
    frame = Image.new("RGB", size, bg)
    box = (max(1, size[0] - 2 * pad), max(1, size[1] - 2 * pad))
    obj = ImageOps.contain(img.copy(), box, Image.Resampling.LANCZOS)
    frame.paste(obj, ((size[0] - obj.width) // 2, (size[1] - obj.height) // 2))
    return frame


def round_mask(size, radius):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return m


def paste_round(canvas, img, box, radius=26, focus=(0.5, 0.5), contain_mode=False, bg=WHITE):
    x, y, w, h = box
    fitted = contain(img, (w, h), bg=bg, pad=18) if contain_mode else cover(img, (w, h), focus)
    canvas.paste(fitted, (x, y), round_mask((w, h), radius))


def text(draw, xy, value, size, color=INK, bold=False, anchor=None):
    draw.text(xy, value, font=font(size, bold), fill=color, anchor=anchor)


def wrap(draw, value, width, size, bold=False):
    words = value.split()
    lines, line = [], ""
    f = font(size, bold)
    for word in words:
        test = f"{line} {word}".strip()
        if draw.textbbox((0, 0), test, font=f)[2] <= width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return "\n".join(lines)


def bg_canvas():
    bg = cover(open_rgb(AI_BG), (W, H), (0.58, 0.5))
    veil = Image.new("RGBA", (W, H), (255, 255, 255, 215))
    return Image.alpha_composite(bg.convert("RGBA"), veil).convert("RGB")


def header(canvas, eyebrow, title, sub=None, y=60):
    d = ImageDraw.Draw(canvas)
    text(d, (70, y), eyebrow.upper(), 23, GREEN, True)
    text(d, (70, y + 37), title, 48, INK, True)
    if sub:
        text(d, (70, y + 98), sub, 23, MUTED)
    return d


def card(draw, box, fill=WHITE, outline=LINE, radius=26):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=2)


def label(draw, xy, value, fill=GREEN):
    x, y = xy
    w = draw.textbbox((0, 0), value, font=font(21, True))[2] + 42
    draw.rounded_rectangle((x, y, x + w, y + 42), radius=21, fill=fill)
    text(draw, (x + 21, y + 21), value, 21, WHITE, True, anchor="lm")
    return w


hero = open_rgb(PRODUCT / "01_主图/01_main.jpg")
upper = open_rgb(CAND / "M2_black_handheld_scale.jpg")
lace = open_rgb(CAND / "M3_lightgrey_top_lace.jpg")
sole = open_rgb(CAND / "M4_white_outsole_structure.jpg")
colors = open_rgb(CAND / "M5_three_color_range.jpg")
pair = open_rgb(CAND / "M6_black_pair.jpg")
black = open_rgb(PRODUCT / "03_颜色图/black.jpg")
cream = open_rgb(PRODUCT / "03_颜色图/cream.jpg")
grey = open_rgb(PRODUCT / "03_颜色图/light_grey.jpg")
white = open_rgb(PRODUCT / "03_颜色图/white.jpg")

building = open_rgb(FACTORY / "03_工厂仓库/大门.jpg")
workshop = open_rgb(FACTORY / "03_工厂仓库/01_workshop.png").rotate(17, expand=True, resample=Image.Resampling.BICUBIC)
line = open_rgb(FACTORY / "03_工厂仓库/03_workshop_line.png")
upper_check = open_rgb(FACTORY / "02_产品检查生产/01_upper_check.jpg")
sole_check = open_rgb(FACTORY / "02_产品检查生产/02_sole_check.jpg")
batch = open_rgb(FACTORY / "02_产品检查生产/04_batch_check.jpg")
stock = open_rgb(FACTORY / "01_公司优势库存/01_stock_sorting.jpg")
packing = open_rgb(FACTORY / "04_订单包装流程/04_carton_ready.png")


# M1: strict product-first white search hero.
m1 = contain(hero, (W, H), WHITE, pad=18)
m1.save(MAIN / "M1_white_search_hero.jpg", quality=94)


# M2: product construction proof.
m2 = bg_canvas(); d = header(m2, "PRODUCT PROOF", "KNIT UPPER · LACE-UP · EVA SOLE", "A206 visible construction from real product photography")
paste_round(m2, hero, (60, 220, 650, 820), 34, contain_mode=True, bg=WHITE)
for y, title, body, im in [
    (220, "KNIT / TEXTILE UPPER", "Visible knitted texture", upper),
    (500, "LACE-UP CLOSURE", "Adjustable lace construction", lace),
    (780, "EVA SOLE", "Visible sole profile and tread", sole),
]:
    card(d, (750, y, 1140, y + 230))
    paste_round(m2, im, (770, y + 18, 150, 194), 18)
    text(d, (945, y + 48), title, 22, GREEN, True)
    d.multiline_text((945, y + 91), wrap(d, body, 175, 20), font=font(20), fill=MUTED, spacing=6)
m2.save(MAIN / "M2_product_structure.jpg", quality=94)


# M3: customization conversation, with no fake logo applied to the shoe.
m3 = bg_canvas(); d = header(m3, "OEM / ODM", "CUSTOMIZATION SUPPORT", "Discuss the approved scope before sampling and bulk production")
paste_round(m3, pair, (60, 220, 620, 760), 34)
items = [
    ("LOGO ARTWORK", "Placement and artwork review"),
    ("COLOR DIRECTION", "Based on approved materials"),
    ("SIZE MIX", "Confirm range and ratio"),
    ("PACKING", "Discuss label and box needs"),
]
for i, (t, b) in enumerate(items):
    y = 235 + i * 180
    card(d, (720, y, 1140, y + 142), fill=WHITE)
    d.ellipse((748, y + 36, 818, y + 106), fill=GREEN)
    text(d, (783, y + 71), f"0{i+1}", 22, WHITE, True, anchor="mm")
    text(d, (840, y + 31), t, 25, INK, True)
    text(d, (840, y + 72), b, 20, MUTED)
label(d, (720, 1004), "Send model + quantity + target market")
m3.save(MAIN / "M3_oem_odm_support.jpg", quality=94)


# M4: verified current online color range.
m4 = bg_canvas(); d = header(m4, "COLOR RANGE", "FOUR VERIFIED ONLINE COLORS", "Black · Cream · Light Grey · White")
for i, (name, im) in enumerate([("BLACK", black), ("CREAM", cream), ("LIGHT GREY", grey), ("WHITE", white)]):
    x = 60 + (i % 2) * 570; y = 225 + (i // 2) * 410
    card(d, (x, y, x + 520, y + 360))
    paste_round(m4, im, (x + 20, y + 20, 480, 265), 20, contain_mode=True, bg=WHITE)
    text(d, (x + 38, y + 318), name, 25, INK, True)
text(d, (60, 1085), "Color and size combinations are confirmed against the selected order.", 24, MUTED)
m4.save(MAIN / "M4_color_options.jpg", quality=94)


# M5: decision FAQ.
m5 = bg_canvas(); d = header(m5, "BUYER FAQ", "KEY QUESTIONS BEFORE QUOTATION", "Clear inputs help us prepare a more accurate response")
paste_round(m5, hero, (675, 220, 465, 520), 34, contain_mode=True, bg=WHITE)
faqs = [
    ("MOQ?", "Online ordering starts from 2 pairs. Bulk terms depend on the selected request."),
    ("SAMPLE?", "Sample arrangements can be discussed for the confirmed model."),
    ("LEAD TIME?", "Confirmed after quantity, colors, size ratio and packing are reviewed."),
    ("SHIPPING?", "Freight is checked by destination, quantity and packing requirement."),
]
for i, (q, a) in enumerate(faqs):
    x = 60 if i < 2 else 610; y = 220 + (i % 2) * 300
    if i >= 2: y = 780 + (i - 2) * 0
    # Bottom two occupy one row for a balanced thumbnail.
    if i == 2: x, y = 60, 790
    if i == 3: x, y = 610, 790
    card(d, (x, y, x + 530, y + 245), fill=WHITE)
    text(d, (x + 30, y + 28), q, 29, GREEN, True)
    d.multiline_text((x + 30, y + 81), wrap(d, a, 465, 22), font=font(22), fill=MUTED, spacing=8)
m5.save(MAIN / "M5_buyer_faq.jpg", quality=94)


# M6: compact real-factory evidence collage.
m6 = bg_canvas(); d = header(m6, "REAL FACTORY EVIDENCE", "FROM WORKSHOP TO ORDER CHECK", "Real Beiqiang photos · no invented years, capacity or certificates")
factory_cells = [
    (building, "QUANZHOU BASE"), (workshop, "WORKSHOP"),
    (upper_check, "VISIBLE CHECK"), (packing, "ORDER PACKING"),
]
for i, (im, cap) in enumerate(factory_cells):
    x = 60 + (i % 2) * 560; y = 220 + (i // 2) * 410
    paste_round(m6, im, (x, y, 520, 330), 26, focus=(0.5, 0.45))
    d.rounded_rectangle((x + 20, y + 268, x + 245, y + 314), radius=20, fill=GREEN2)
    text(d, (x + 36, y + 291), cap, 20, WHITE, True, anchor="lm")
text(d, (60, 1082), "Footwear development · OEM/ODM discussion · wholesale supply", 25, INK, True)
m6.save(MAIN / "M6_factory_strength.jpg", quality=94)


# Product details D1-D6.
d1 = bg_canvas(); d = header(d1, "A206", "MEN'S KNIT LACE-UP WALKING SHOES", "A clean product overview for wholesalers, importers and online sellers")
paste_round(d1, hero, (70, 225, 690, 830), 36, contain_mode=True, bg=WHITE)
for i, value in enumerate(["KNIT / TEXTILE UPPER", "LACE-UP", "EVA SOLE", "EU 35–45", "REGULAR FIT"]):
    card(d, (800, 250 + i * 142, 1135, 355 + i * 142), fill=WHITE)
    text(d, (830, 302 + i * 142), value, 22, GREEN2, True, anchor="lm")
d1.save(DETAIL / "D1_product_overview.jpg", quality=94)

d2 = bg_canvas(); d = header(d2, "PRODUCT FACTS", "SPECIFICATION AT A GLANCE", "Only verified A206 fields are shown")
specs = [
    ("MODEL", "A206"), ("UPPER", "Knit / Textile"), ("CLOSURE", "Lace-Up"),
    ("SOLE", "EVA"), ("TOE", "Round Toe"), ("FIT", "Regular Fit"),
    ("SIZE", "EU 35–45"), ("COLORS", "Black / Cream / Light Grey / White"),
]
for i, (k, v) in enumerate(specs):
    x = 70 + (i % 2) * 550; y = 235 + (i // 2) * 190
    card(d, (x, y, x + 500, y + 150), fill=WHITE)
    text(d, (x + 28, y + 27), k, 20, GREEN, True)
    d.multiline_text((x + 28, y + 69), wrap(d, v, 445, 25, True), font=font(25, True), fill=INK, spacing=4)
label(d, (70, 1030), "Daily walking · commuting · casual wear")
d2.save(DETAIL / "D2_specifications.jpg", quality=94)

d3 = bg_canvas(); d = header(d3, "CONSTRUCTION", "REAL PRODUCT DETAILS", "Texture, closure and sole are shown with source photography")
for i, (im, t, b) in enumerate([
    (upper, "KNITTED TEXTURE", "Visible upper construction"),
    (lace, "LACE-UP", "Adjustable closure"),
    (sole, "SOLE PROFILE", "Visible EVA sole structure"),
]):
    x = 60 + i * 380
    paste_round(d3, im, (x, 235, 340, 630), 26)
    card(d, (x, 895, x + 340, 1035), fill=WHITE)
    text(d, (x + 22, 918), t, 22, GREEN, True)
    text(d, (x + 22, 964), b, 19, MUTED)
d3.save(DETAIL / "D3_structure_proof.jpg", quality=94)

d4 = bg_canvas(); d = header(d4, "COLOR & SIZE", "BUILD THE ORDER MIX", "Select confirmed colors and discuss the EU 35–45 size ratio")
for i, (name, im) in enumerate([("BLACK", black), ("CREAM", cream), ("LIGHT GREY", grey), ("WHITE", white)]):
    x = 60 + i * 280
    paste_round(d4, im, (x, 245, 250, 420), 24, contain_mode=True, bg=WHITE)
    text(d, (x + 125, 695), name, 22, INK, True, anchor="mm")
card(d, (60, 780, 1140, 1015), fill=WHITE)
text(d, (92, 815), "WHAT TO CONFIRM", 24, GREEN, True)
for i, item in enumerate(["Target colors", "EU size range", "Size ratio", "Order quantity"]):
    x = 92 + i * 255
    d.ellipse((x, 880, x + 42, 922), fill=GREEN)
    text(d, (x + 21, 901), str(i + 1), 18, WHITE, True, anchor="mm")
    text(d, (x, 950), item, 20, MUTED)
text(d, (60, 1080), "Final availability and combinations are reviewed for the selected order.", 22, MUTED)
d4.save(DETAIL / "D4_color_range.jpg", quality=94)

d5 = bg_canvas(); d = header(d5, "OEM / ODM", "FROM REQUEST TO APPROVED SAMPLE", "A clear brief helps reduce avoidable changes before bulk production")
paste_round(d5, pair, (60, 230, 470, 650), 30)
steps = [
    ("01", "BUYER BRIEF", "Model, market and quantity"),
    ("02", "REQUIREMENTS", "Logo, colors, sizes and packing"),
    ("03", "SAMPLE SCOPE", "Cost and timing confirmed"),
    ("04", "APPROVAL", "Final details agreed before bulk"),
]
for i, (n, t, b) in enumerate(steps):
    x = 580 + (i % 2) * 290; y = 230 + (i // 2) * 315
    card(d, (x, y, x + 260, y + 270), fill=WHITE)
    d.ellipse((x + 24, y + 24, x + 84, y + 84), fill=GREEN)
    text(d, (x + 54, y + 54), n, 19, WHITE, True, anchor="mm")
    text(d, (x + 24, y + 112), t, 22, INK, True)
    d.multiline_text((x + 24, y + 158), wrap(d, b, 210, 19), font=font(19), fill=MUTED, spacing=6)
card(d, (60, 930, 1140, 1090), fill=GREEN2, outline=GREEN2)
text(d, (90, 966), "SEND WITH YOUR INQUIRY", 22, WHITE, True)
text(d, (90, 1016), "Model · quantity · colors · size ratio · artwork · packing · destination", 22, WHITE)
d5.save(DETAIL / "D5_oem_odm.jpg", quality=94)

d6 = bg_canvas(); d = header(d6, "INQUIRY GUIDE", "GET A CLEARER QUOTATION", "Share the order inputs that affect product and freight conditions")
questions = [
    ("QUANTITY", "Expected sample or bulk quantity"),
    ("COLORS", "Target color selection"),
    ("SIZE RATIO", "EU 35–45 assortment"),
    ("LOGO / PACKING", "Artwork and packing preference"),
    ("DESTINATION", "Country or delivery point"),
    ("TIMING", "Required delivery window"),
]
for i, (q, a) in enumerate(questions):
    x = 60 + (i % 2) * 550; y = 230 + (i // 2) * 245
    card(d, (x, y, x + 500, y + 205), fill=WHITE)
    d.ellipse((x + 24, y + 26, x + 78, y + 80), fill=GREEN)
    text(d, (x + 51, y + 53), str(i + 1), 18, WHITE, True, anchor="mm")
    text(d, (x + 100, y + 28), q, 22, GREEN2, True)
    d.multiline_text((x + 100, y + 76), wrap(d, a, 355, 20), font=font(20), fill=MUTED, spacing=6)
label(d, (60, 1025), "Final price and timing depend on the confirmed order brief")
d6.save(DETAIL / "D6_faq_inquiry.jpg", quality=94)


# Company details C1-C5 use only real photos as evidence.
def company_page(eyebrow, title_value, subtitle, images, captions, filename):
    c = bg_canvas(); dr = header(c, eyebrow, title_value, subtitle)
    if len(images) == 2:
        boxes = [(60, 230, 520, 710), (620, 230, 520, 710)]
    else:
        boxes = [(60, 230, 340, 610), (430, 230, 340, 610), (800, 230, 340, 610)]
    for im, cap, box in zip(images, captions, boxes):
        paste_round(c, im, box, 28, focus=(0.5, 0.48))
        x, y, w, h = box
        dr.rounded_rectangle((x + 18, y + h - 65, x + min(w - 18, 310), y + h - 18), radius=20, fill=GREEN2)
        text(dr, (x + 34, y + h - 41), cap, 20, WHITE, True, anchor="lm")
    text(dr, (60, 1020), "QUANZHOU BEIQIANG FOOTWEAR & APPAREL CO., LTD.", 25, INK, True)
    text(dr, (60, 1065), "OEM / ODM discussion · wholesale supply · order-based confirmation", 22, MUTED)
    c.save(COMPANY / filename, quality=94)


company_page("SUPPLIER PROFILE", "REAL FACTORY, REAL WORKFLOW", "Beiqiang factory photos organized around buyer-relevant evidence", [building, workshop], ["QUANZHOU BASE", "WORKSHOP"], "C1_factory_profile.jpg")
company_page("OEM / ODM", "FROM BRIEF TO APPROVED SAMPLE", "Customization scope is reviewed before bulk production", [stock, colors, pair], ["BUYER BRIEF", "COLOR / MATERIAL", "SAMPLE REVIEW"], "C2_oem_odm_process.jpg")
company_page("PRODUCTION", "VISIBLE WORKFLOW", "Real workshop photos showing footwear handling and batch organization", [line, workshop, batch], ["WORKSHOP LINE", "ASSEMBLY AREA", "BATCH CHECK"], "C3_production_process.jpg")
company_page("QUALITY REVIEW", "CHECK AGAINST THE ORDER BRIEF", "Visible product and packing checks support buyer confirmation", [upper_check, sole_check], ["UPPER CHECK", "SOLE CHECK"], "C4_quality_review.jpg")
company_page("PACKING & INQUIRY", "PREPARE THE ORDER DETAILS", "Send quantity, colors, size ratio, logo/packing needs and destination", [packing, stock], ["PACKING READY", "ORDER SORTING"], "C5_packing_inquiry.jpg")


def contact_sheet(files, out, cols=3, thumb=(360, 360), label_h=54):
    rows = (len(files) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (thumb[0] + 24) + 24, rows * (thumb[1] + label_h + 24) + 24), WHITE)
    dr = ImageDraw.Draw(sheet)
    for i, p in enumerate(files):
        x = 24 + (i % cols) * (thumb[0] + 24)
        y = 24 + (i // cols) * (thumb[1] + label_h + 24)
        im = contain(open_rgb(p), thumb, WHITE)
        sheet.paste(im, (x, y))
        text(dr, (x + 4, y + thumb[1] + 14), p.stem, 18, INK, True)
    sheet.save(out, quality=92)


contact_sheet(sorted(MAIN.glob("*.jpg")), PREVIEW / "01_main_gallery_contact.jpg", cols=3)
contact_sheet(sorted(DETAIL.glob("*.jpg")), PREVIEW / "02_product_detail_contact.jpg", cols=3)
contact_sheet(sorted(COMPANY.glob("*.jpg")), PREVIEW / "03_company_detail_contact.jpg", cols=3)

raw_product_images = sorted(
    RAW.glob("*.jpg"),
    key=lambda p: int(p.stem) if p.stem.isdigit() else 9999,
)
contact_sheet(raw_product_images, PREVIEW / "05_all_raw_product_images.jpg", cols=6, thumb=(170, 170), label_h=36)

ai_candidate = OUT / "05_AI候选/AI_M1_candidate_v1.png"
if ai_candidate.exists():
    comparison = Image.new("RGB", (1220, 660), WHITE)
    comparison.paste(contain(hero, (590, 590), WHITE, pad=8), (10, 60))
    comparison.paste(contain(open_rgb(ai_candidate), (590, 590), WHITE, pad=8), (620, 60))
    cd = ImageDraw.Draw(comparison)
    text(cd, (20, 20), "REAL SOURCE / CURRENT PILOT", 24, GREEN2, True)
    text(cd, (630, 20), "AI CANDIDATE V1 — REVIEW ONLY", 24, "#A33B2B", True)
    comparison.save(PREVIEW / "04_ai_m1_before_after.jpg", quality=94)

manifest = {
    "product_id": "1601939616747",
    "link_code": "BQ019-W1",
    "model": "A206",
    "status": "LOCAL_VISUAL_PILOT_NOT_UPLOADED",
    "main_images": [p.name for p in sorted(MAIN.glob("*.jpg"))],
    "product_detail_images": [p.name for p in sorted(DETAIL.glob("*.jpg"))],
    "company_detail_images": [p.name for p in sorted(COMPANY.glob("*.jpg"))],
    "ai_use": "Existing AI-generated abstract non-factual background texture is used behind deterministic layouts. AI M1 candidate v1 is retained under 05_AI候选 for comparison only and is not approved for upload.",
    "fact_guards": [
        "No invented years, capacity, certificates, reviews or brand partnerships",
        "No fake logo applied to product",
        "No wide-toe, medical, waterproof or tested-performance claims",
        "Factory evidence uses real Beiqiang source photographs",
    ],
}
(OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(OUT)
