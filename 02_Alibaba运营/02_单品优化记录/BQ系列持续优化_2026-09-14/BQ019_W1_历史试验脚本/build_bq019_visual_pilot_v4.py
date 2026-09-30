from pathlib import Path
import shutil

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
OUT = ROOT / "02_Alibaba运营/02_单品优化记录/BQ系列持续优化_2026-09-14/BQ019_W1_整页视觉样板_v4_2026-09-16"
MAIN = OUT / "01_主图六张"
DETAIL = OUT / "02_产品详情四张"
COMPANY = OUT / "03_公司详情五张"
FACTCHECK = OUT / "04_待确认AI候选"
PREVIEW = OUT / "05_审阅预览"
for folder in (MAIN, DETAIL, COMPANY, FACTCHECK, PREVIEW):
    folder.mkdir(parents=True, exist_ok=True)

V3 = ROOT / "02_Alibaba运营/02_单品优化记录/BQ系列持续优化_2026-09-14/BQ019_W1_整页视觉样板_v3_2026-09-16"
RAW = ROOT / "01_产品资产/01_原始数据包/已整理_BQ019_A206_A206情侣鞋图片/A206情侣鞋图片/主图"
FACTORY = ROOT / "01_产品资产/02_可发布素材/00_最终上传/00_厂家资料/00_精选可用照片"
AI_WIDE = Path(r"C:\Users\spq\.codex\generated_images\01a094e6-52ec-7100-b16c-509ee49cbb58\exec-6898cb6e-e013-45d2-82df-913c20e2e995.png")
AI_WORKSHOP = Path(r"C:\Users\spq\.codex\generated_images\01a094e6-52ec-7100-b16c-509ee49cbb58\exec-d2e28334-c0ba-44df-ab70-4f25b158705c.png")

W = H = 1200
INK = "#12221F"
MUTED = "#5D6B68"
GREEN = "#0C6B50"
DEEP = "#073D32"
MINT = "#E7F1ED"
SAND = "#F4EFE4"
BLUE = "#EAF1F5"
WHITE = "#FFFFFF"
LINE = "#CBD9D4"
AMBER = "#F4B942"


def font(size, bold=False):
    return ImageFont.truetype(str(Path(r"C:\Windows\Fonts") / ("arialbd.ttf" if bold else "arial.ttf")), size)


def open_rgb(path):
    return Image.open(path).convert("RGB")


def text(draw, xy, value, size, color=INK, bold=False, anchor=None):
    draw.text(xy, value, font=font(size, bold), fill=color, anchor=anchor)


def wrap(draw, value, width, size, bold=False):
    words, lines, current = value.split(), [], ""
    f = font(size, bold)
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textbbox((0, 0), test, font=f)[2] <= width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return "\n".join(lines)


def canvas(bg="#F6F8F7"):
    return Image.new("RGB", (W, H), bg)


def card(draw, box, fill=WHITE, outline=LINE, radius=26, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def mask(size, radius=26):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return m


def cover(img, size, focus=(0.5, 0.5)):
    ratio = max(size[0] / img.width, size[1] / img.height)
    img = img.resize((round(img.width * ratio), round(img.height * ratio)), Image.Resampling.LANCZOS)
    x = max(0, min(img.width - size[0], round((img.width - size[0]) * focus[0])))
    y = max(0, min(img.height - size[1], round((img.height - size[1]) * focus[1])))
    return img.crop((x, y, x + size[0], y + size[1]))


def contain(img, size, bg=WHITE, pad=20):
    frame = Image.new("RGB", size, bg)
    obj = ImageOps.contain(img, (size[0] - pad * 2, size[1] - pad * 2), Image.Resampling.LANCZOS)
    frame.paste(obj, ((size[0] - obj.width) // 2, (size[1] - obj.height) // 2))
    return frame


def paste(canvas_img, img, box, radius=26, focus=(0.5, 0.5), fit="cover", bg=WHITE):
    x, y, w, h = box
    fitted = contain(img, (w, h), bg, 18) if fit == "contain" else cover(img, (w, h), focus)
    canvas_img.paste(fitted, (x, y), mask((w, h), radius))


def header(page, eyebrow, title, subtitle="", dark=False):
    d = ImageDraw.Draw(page)
    base = WHITE if dark else INK
    sub = "#D6E7E1" if dark else MUTED
    text(d, (60, 54), eyebrow.upper(), 20, "#9DD5C2" if dark else GREEN, True)
    text(d, (60, 94), title, 43, base, True)
    if subtitle:
        text(d, (60, 151), subtitle, 20, sub)
    return d


def pill(draw, xy, label, fill=GREEN, fg=WHITE):
    x, y = xy
    width = draw.textbbox((0, 0), label, font=font(19, True))[2] + 38
    draw.rounded_rectangle((x, y, x + width, y + 42), radius=21, fill=fill)
    text(draw, (x + width / 2, y + 21), label, 19, fg, True, anchor="mm")
    return width


def numbered_row(draw, y, number, title, body, x=60, width=1080, fill=WHITE):
    card(draw, (x, y, x + width, y + 116), fill=fill)
    draw.ellipse((x + 22, y + 26, x + 84, y + 88), fill=GREEN)
    text(draw, (x + 53, y + 57), number, 19, WHITE, True, anchor="mm")
    text(draw, (x + 110, y + 25), title, 22, INK, True)
    text(draw, (x + 110, y + 63), body, 18, MUTED)


def save_contact(paths, dst, cols=3, thumb=400, label_h=52):
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb, rows * (thumb + label_h)), "#E8ECEA")
    d = ImageDraw.Draw(sheet)
    for i, path in enumerate(paths):
        im = contain(open_rgb(path), (thumb, thumb), WHITE, 4)
        x, y = (i % cols) * thumb, (i // cols) * (thumb + label_h)
        sheet.paste(im, (x, y))
        text(d, (x + 12, y + thumb + label_h / 2), path.stem, 17, INK, True, anchor="lm")
    sheet.save(dst, quality=94)


# Product anchors are deterministic white-background reconstructions from real A206 photographs.
black = open_rgb(V3 / "01_统一四色白底/01_black.jpg")
cream = open_rgb(V3 / "01_统一四色白底/02_cream.jpg")
grey = open_rgb(V3 / "01_统一四色白底/03_light_grey.jpg")
white = open_rgb(V3 / "01_统一四色白底/04_white_manual.jpg")
hand = open_rgb(RAW / "5.jpg")
top = open_rgb(RAW / "10.jpg")
outsole = open_rgb(RAW / "15.jpg")
quote_photo = open_rgb(RAW / "4.jpg")

factory_real = open_rgb(FACTORY / "03_工厂仓库/大门.jpg")
workshop_real = open_rgb(FACTORY / "03_工厂仓库/04_workshop_area.png")
upper_check = open_rgb(FACTORY / "02_产品检查生产/01_upper_check.jpg")
sole_check = open_rgb(FACTORY / "02_产品检查生产/02_sole_check.jpg")
line_sort = open_rgb(FACTORY / "02_产品检查生产/03_line_sorting.jpg")
batch_check = open_rgb(FACTORY / "02_产品检查生产/04_batch_check.jpg")


# MAIN GALLERY — one white search image, five distinct decision roles.
grey.save(MAIN / "M1_A206_light_grey_search.jpg", quality=96)

m2 = canvas(MINT)
d = header(m2, "REAL ORDER OPTIONS", "4 COLORS · EU 35–45", "Confirm the final color and size ratio before order")
for i, (name, im) in enumerate((("BLACK", black), ("CREAM", cream), ("LIGHT GREY", grey), ("WHITE", white))):
    x, y = 55 + (i % 2) * 570, 225 + (i // 2) * 420
    card(d, (x, y, x + 520, y + 370), fill="#F8FBFA", outline="#B9D0C7")
    paste(m2, im, (x + 15, y + 15, 490, 285), 18, fit="contain", bg="#F8FBFA")
    text(d, (x + 26, y + 332), name, 22, INK, True)
    if i == 3:
        pill(d, (x + 338, y + 319), "SIZE MIX BY ORDER", fill=DEEP)
m2.save(MAIN / "M2_colors_and_size.jpg", quality=95)

m3 = canvas(DEEP)
d = header(m3, "REAL PRODUCT PROOF", "WHAT BUYERS CAN VERIFY", "Three different views from the A206 source set", dark=True)
for i, (im, label, body, focus) in enumerate((
    (hand, "SIDE PROFILE", "Upper + sole proportion", (0.48, 0.55)),
    (top, "TOP + OPENING", "Laces + foot opening", (0.50, 0.50)),
    (outsole, "SOLE VIEW", "Outsole shape + tread", (0.69, 0.58)),
)):
    x = 40 + i * 390
    paste(m3, im, (x, 225, 360, 690), 24, focus=focus)
    text(d, (x + 12, 960), label, 21, "#A9D9C8", True)
    text(d, (x + 12, 999), body, 18, "#D6E7E1")
m3.save(MAIN / "M3_three_view_product_proof.jpg", quality=95)

m4 = canvas(SAND)
d = header(m4, "PRIVATE LABEL PROJECT", "OEM / ODM STARTS WITH A CLEAR BRIEF", "Scope is reviewed before sampling and bulk production")
paste(m4, cream, (55, 235, 500, 665), 28, fit="contain", bg="#E7E3D8")
text(d, (305, 930), "A206 PRODUCT ANCHOR", 18, GREEN, True, anchor="mm")
for i, (title, body) in enumerate((
    ("LOGO FILE", "Artwork + placement"),
    ("COLOR DIRECTION", "Target color + material"),
    ("SIZE RATIO", "Range + pair breakdown"),
    ("PACKING FILE", "Label + box request"),
)):
    x = 600 + (i % 2) * 285
    y = 245 + (i // 2) * 270
    card(d, (x, y, x + 255, y + 225), fill=WHITE)
    d.ellipse((x + 24, y + 24, x + 78, y + 78), fill=GREEN)
    text(d, (x + 51, y + 51), str(i + 1), 18, WHITE, True, anchor="mm")
    text(d, (x + 24, y + 105), title, 19, INK, True)
    d.multiline_text((x + 24, y + 145), wrap(d, body, 205, 17), font=font(17), fill=MUTED, spacing=5)
numbered_row(d, 820, "→", "NEXT STEP", "Send model, quantity and artwork files.", x=600, width=540, fill="#E4ECE7")
m4.save(MAIN / "M4_oem_odm_scope.jpg", quality=95)

m5 = canvas(BLUE)
d = header(m5, "QUOTE PREPARATION", "SEND 5 DETAILS FOR A WORKABLE QUOTE", "The final offer depends on the actual order request")
paste(m5, quote_photo, (55, 230, 520, 815), 28, focus=(0.44, 0.52))
for i, (title, body) in enumerate((
    ("MODEL + COLOR", "A206 and selected direction"),
    ("QUANTITY", "Total pairs"),
    ("SIZE RATIO", "Pairs by EU size"),
    ("CUSTOM FILES", "Logo, label or packing"),
    ("DESTINATION", "Country, city or port"),
)):
    y = 230 + i * 155
    card(d, (620, y, 1145, y + 125), fill=WHITE, outline="#C4D5DF")
    text(d, (650, y + 30), f"0{i+1}", 18, GREEN, True)
    text(d, (715, y + 27), title, 20, INK, True)
    text(d, (715, y + 68), body, 17, MUTED)
m5.save(MAIN / "M5_quote_input_checklist.jpg", quality=95)

m6 = canvas(DEEP)
d = header(m6, "SUPPLIER EVIDENCE", "THREE THINGS BUYERS CAN CHECK", "Real Beiqiang source photographs · no capacity or certification claims", dark=True)
for i, (im, label, body, focus) in enumerate((
    (factory_real, "01  FACTORY IDENTITY", "Beiqiang building sign", (0.55, 0.55)),
    (workshop_real, "02  PRODUCTION FLOOR", "Work area + in-process shoes", (0.53, 0.55)),
    (sole_check, "03  IN-PROCESS CHECK", "Visible sole and shoe handling", (0.48, 0.55)),
)):
    x = 40 + i * 390
    paste(m6, im, (x, 225, 360, 690), 24, focus=focus)
    text(d, (x + 10, 955), label, 19, "#A9D9C8", True)
    text(d, (x + 10, 993), body, 17, "#D6E7E1")
m6.save(MAIN / "M6_real_supplier_evidence.jpg", quality=95)


# PRODUCT DETAIL — four information-complete modules without repeating main cards.
d1 = canvas()
d = header(d1, "A206 PRODUCT", "MEN'S KNIT / TEXTILE LACE-UP SHOES", "Verified page facts for wholesale discussion")
paste(d1, grey, (55, 230, 650, 820), 28, fit="contain")
facts = (("MODEL", "A206"), ("UPPER", "Knit / Textile"), ("CLOSURE", "Lace-Up"),
         ("SOLE", "EVA"), ("TOE", "Round Toe"), ("FIT", "Regular Fit"))
for i, (key, value) in enumerate(facts):
    y = 235 + i * 132
    card(d, (750, y, 1145, y + 104), fill=WHITE)
    text(d, (775, y + 22), key, 16, GREEN, True)
    text(d, (775, y + 57), value, 22, INK, True)
d1.save(DETAIL / "D1_verified_product_overview.jpg", quality=95)

d2 = canvas(MINT)
d = header(d2, "ORDER MATRIX", "CHOOSE COLOR · CONFIRM SIZE RATIO", "EU 35–45 · final combinations are reviewed against the order")
for i, (name, im) in enumerate((("BLACK", black), ("CREAM", cream), ("LIGHT GREY", grey), ("WHITE", white))):
    x = 50 + i * 285
    paste(d2, im, (x, 235, 260, 410), 22, fit="contain", bg="#F8FBFA")
    text(d, (x + 130, 675), name, 19, INK, True, anchor="mm")
card(d, (55, 755, 1145, 1055), fill="#F8FBFA", outline="#B9D0C7")
text(d, (90, 800), "SIZE-RATIO INPUT", 22, GREEN, True)
text(d, (90, 852), "Tell us how many pairs you need in each EU size.", 24, INK, True)
text(d, (90, 915), "Example input format: 35×__  36×__  37×__  …  45×__", 21, MUTED)
text(d, (90, 975), "Mixed color and size arrangements are confirmed for the actual order.", 19, MUTED)
d2.save(DETAIL / "D2_color_size_order_matrix.jpg", quality=95)

d3 = canvas(DEEP)
d = header(d3, "CONSTRUCTION VIEW", "READ THE SHOE BEFORE YOU SOURCE IT", "Real A206 side, opening and outsole views", dark=True)
for i, (im, title, desc, focus) in enumerate((
    (hand, "UPPER + SOLE", "Side proportion", (0.48, 0.55)),
    (top, "LACES + OPENING", "Top construction", (0.50, 0.50)),
    (outsole, "OUTSOLE", "Visible tread", (0.68, 0.58)),
)):
    x = 45 + i * 390
    paste(d3, im, (x, 235, 355, 670), 24, focus=focus)
    text(d, (x + 12, 950), title, 20, "#A9D9C8", True)
    text(d, (x + 12, 990), desc, 18, "#D6E7E1")
d3.save(DETAIL / "D3_construction_views.jpg", quality=95)

d4 = canvas(SAND)
d = header(d4, "WHOLESALE + OEM / ODM", "HOW THE PROJECT MOVES FORWARD", "Commercial terms are confirmed against the selected model and order")
for i, (title, body) in enumerate((
    ("1 · PRODUCT BRIEF", "Model, color, quantity, market"),
    ("2 · ARTWORK REVIEW", "Logo, label and packing files"),
    ("3 · SAMPLE DISCUSSION", "Confirm purpose and requested scope"),
    ("4 · ORDER SPEC", "Size ratio, packing, destination and timing"),
)):
    x = 55 + (i % 2) * 570
    y = 240 + (i // 2) * 300
    card(d, (x, y, x + 520, y + 245), fill=WHITE)
    text(d, (x + 30, y + 35), title, 22, GREEN, True)
    d.multiline_text((x + 30, y + 96), wrap(d, body, 455, 21), font=font(21), fill=INK, spacing=7)
card(d, (55, 900, 1145, 1055), fill=DEEP, outline=DEEP)
text(d, (600, 950), "MOQ BASELINE: 2 PAIRS", 22, "#A9D9C8", True, anchor="mm")
text(d, (600, 1000), "Final price and timing depend on quantity, materials, size ratio, packing and order requirements.", 18, WHITE, anchor="mm")
d4.save(DETAIL / "D4_wholesale_oem_inquiry.jpg", quality=95)


# COMPANY DETAIL — five different procurement-risk questions.
c1 = canvas(DEEP)
paste(c1, factory_real, (45, 45, 1110, 760), 28, focus=(0.55, 0.55))
d = ImageDraw.Draw(c1)
text(d, (60, 855), "SUPPLIER IDENTITY", 20, "#A9D9C8", True)
text(d, (60, 900), "QUANZHOU BEIQIANG FOOTWEAR & APPAREL", 34, WHITE, True)
text(d, (60, 962), "Real building sign retained as identity evidence.", 20, "#D6E7E1")
pill(d, (60, 1020), "QUANZHOU · FUJIAN · CHINA", fill="#146C57")
c1.save(COMPANY / "C1_real_factory_identity.jpg", quality=95)

c2 = canvas(SAND)
d = header(c2, "CUSTOM PROJECT", "WHAT HAPPENS AFTER YOU SEND A BRIEF", "A practical communication flow—not a generic OEM badge")
for i, (title, body) in enumerate((
    ("BUYER BRIEF", "Model · quantity · market"),
    ("ARTWORK REVIEW", "Logo · label · packing"),
    ("SAMPLE SCOPE", "Purpose · requested checks"),
    ("ORDER CONFIRMATION", "Ratio · packing · destination"),
)):
    x = 55 + (i % 2) * 570
    y = 245 + (i // 2) * 315
    card(d, (x, y, x + 520, y + 260), fill=WHITE)
    d.ellipse((x + 30, y + 30, x + 94, y + 94), fill=GREEN)
    text(d, (x + 62, y + 62), str(i + 1), 20, WHITE, True, anchor="mm")
    text(d, (x + 120, y + 39), title, 22, INK, True)
    d.multiline_text((x + 30, y + 130), wrap(d, body, 450, 20), font=font(20), fill=MUTED, spacing=6)
numbered_row(d, 910, "→", "BUYER ACTION", "Send reference files and the target order information.", fill="#E7E3D8")
c2.save(COMPANY / "C2_custom_project_flow.jpg", quality=95)

c3 = canvas()
d = header(c3, "PRODUCTION ORGANIZATION", "WHAT THE REAL WORKSHOP PHOTO SHOWS", "Use the image as evidence only for visible conditions")
paste(c3, workshop_real, (55, 230, 700, 820), 28, focus=(0.53, 0.55))
for i, (title, body) in enumerate((
    ("WORK AREA", "Visible footwear workstations"),
    ("IN-PROCESS SHOES", "Products organized around the line"),
    ("ORDER REVIEW", "Model-specific requirements discussed before production"),
)):
    y = 245 + i * 235
    card(d, (800, y, 1145, y + 195), fill=WHITE)
    text(d, (825, y + 30), title, 20, GREEN, True)
    d.multiline_text((825, y + 78), wrap(d, body, 290, 18), font=font(18), fill=MUTED, spacing=5)
c3.save(COMPANY / "C3_real_production_organization.jpg", quality=95)

c4 = canvas(DEEP)
d = header(c4, "QUALITY CHECKPOINTS", "VISIBLE ORDER REVIEW ACTIVITIES", "Confirm buyer-specific standards before production", dark=True)
for i, (im, title, body, focus) in enumerate((
    (upper_check, "UPPER / FINISH", "Visible surface handling", (0.52, 0.54)),
    (sole_check, "SOLE / CONSTRUCTION", "Visible sole attachment review", (0.48, 0.55)),
    (line_sort, "LINE SORTING", "Pairs organized during processing", (0.58, 0.50)),
)):
    x = 40 + i * 390
    paste(c4, im, (x, 225, 360, 690), 24, focus=focus)
    text(d, (x + 10, 955), title, 19, "#A9D9C8", True)
    text(d, (x + 10, 993), body, 17, "#D6E7E1")
c4.save(COMPANY / "C4_real_quality_checkpoints.jpg", quality=95)

c5 = canvas(BLUE)
d = header(c5, "PACKING + HANDOFF", "CONFIRM THESE BEFORE ORDER RELEASE", "Packing and shipping arrangements follow the actual order")
for i, (title, body) in enumerate((
    ("PACKING FILE", "Box, label and mark requirements"),
    ("ORDER MATRIX", "Quantity, colors and size ratio"),
    ("DESTINATION", "Country, city or port"),
    ("TRADE + FORWARDER", "Confirm terms and nominated logistics"),
)):
    x = 55 + (i % 2) * 570
    y = 245 + (i // 2) * 300
    card(d, (x, y, x + 520, y + 245), fill=WHITE, outline="#C4D5DF")
    text(d, (x + 30, y + 35), f"0{i+1}  {title}", 21, GREEN, True)
    d.multiline_text((x + 30, y + 100), wrap(d, body, 455, 20), font=font(20), fill=INK, spacing=6)
card(d, (55, 900, 1145, 1055), fill=DEEP, outline=DEEP)
text(d, (600, 955), "NO FIXED DDP / FBA / DELIVERY-TIME CLAIMS", 21, "#A9D9C8", True, anchor="mm")
text(d, (600, 1005), "The route and timing are confirmed for the destination and order.", 18, WHITE, anchor="mm")
c5.save(COMPANY / "C5_packing_order_handoff.jpg", quality=95)


# Separate review-only AI architecture candidate. It is never included in the formal five-company-image contact sheet.
if AI_WIDE.exists():
    copied = FACTCHECK / "FACT_CHECK_factory_wide_gate_v2.png"
    shutil.copy2(AI_WIDE, copied)
    review = canvas("#FFF5DC")
    paste(review, open_rgb(copied), (40, 40, 1120, 865), 26, focus=(0.5, 0.5))
    d = ImageDraw.Draw(review)
    text(d, (60, 950), "FACT CHECK REQUIRED", 28, "#8A5B00", True)
    text(d, (60, 1000), "Please confirm the left gate, stone pillars, right facade and building width match the real site.", 20, INK)
    text(d, (60, 1045), "Do not upload until owner confirmation.", 19, "#8A5B00", True)
    review.save(FACTCHECK / "REVIEW_factory_wide_gate_v2.jpg", quality=95)

if AI_WORKSHOP.exists():
    copied = FACTCHECK / "FACT_CHECK_workshop_cleanup_v2.png"
    shutil.copy2(AI_WORKSHOP, copied)
    review = canvas("#FFF5DC")
    paste(review, open_rgb(copied), (40, 40, 1120, 865), 26, focus=(0.5, 0.5))
    d = ImageDraw.Draw(review)
    text(d, (60, 950), "AI-ENHANCED WORKSHOP · REVIEW REQUIRED", 27, "#8A5B00", True)
    text(d, (60, 1000), "Perspective and clutter were improved; verify workers, machines and in-process layout remain acceptable.", 19, INK)
    text(d, (60, 1045), "The formal C3 still uses the real source photo until approval.", 19, "#8A5B00", True)
    review.save(FACTCHECK / "REVIEW_workshop_cleanup_v2.jpg", quality=95)


main_paths = sorted(MAIN.glob("*.jpg"))
detail_paths = sorted(DETAIL.glob("*.jpg"))
company_paths = sorted(COMPANY.glob("*.jpg"))
save_contact(main_paths, PREVIEW / "01_main_gallery_v4.jpg", 3, 400)
save_contact(detail_paths, PREVIEW / "02_product_detail_v4.jpg", 2, 500)
save_contact(company_paths, PREVIEW / "03_company_detail_v4.jpg", 3, 400)

with (OUT / "README.md").open("w", encoding="utf-8") as f:
    f.write("# BQ019-W1 整页视觉样板 v4\n\n")
    f.write("状态：LOCAL REVIEW ONLY，未上传平台。\n\n")
    f.write("- 正式审阅组：6张主图、4张产品详情、5张公司详情。\n")
    f.write("- 只有M1为纯白搜索图；其余图片分别回答颜色尺码、结构、定制、报价和供应商证据。\n")
    f.write("- 公司图只使用真实原始厂图或中性流程图；v3 AI车间和AI质检图已完全排除。\n")
    f.write("- 厂房拉远图单独放入04_待确认AI候选，不属于正式公司图；确认建筑真实后才能替换C1。\n")
    f.write("- 所有对外文字避免年份、产能、认证、固定物流、固定交期、第三方品牌和无证据性能。\n")
