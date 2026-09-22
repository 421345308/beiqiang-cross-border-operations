from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from scipy import ndimage


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
OUT = ROOT / "02_Alibaba运营/02_单品优化记录/BQ系列持续优化_2026-09-14/BQ019_W1_整页视觉样板_v3_2026-09-16"
COLORS = OUT / "01_统一四色白底"
MAIN = OUT / "02_主图六张"
DETAIL = OUT / "03_产品详情"
COMPANY = OUT / "04_公司详情"
AI = OUT / "05_AI候选"
PREVIEW = OUT / "06_预览"
for folder in (COLORS, MAIN, DETAIL, COMPANY, AI, PREVIEW):
    folder.mkdir(parents=True, exist_ok=True)

RAW = ROOT / "01_产品资产/01_原始数据包/已整理_BQ019_A206_A206情侣鞋图片/A206情侣鞋图片/主图"
PRODUCT = ROOT / "01_产品资产/02_可发布素材/00_最终上传/BQ019_A206"
FACTORY = ROOT / "01_产品资产/02_可发布素材/00_最终上传/00_厂家资料/00_精选可用照片"

W = H = 1200
WHITE = "#FFFFFF"
INK = "#172129"
MUTED = "#637078"
GREEN = "#17624C"
GREEN_DARK = "#103F34"
MINT = "#EAF3EF"
SAND = "#F3EFE6"
LINE = "#D9E2DE"


def font(size: int, bold: bool = False):
    return ImageFont.truetype(str(Path(r"C:\Windows\Fonts") / ("arialbd.ttf" if bold else "arial.ttf")), size)


def open_rgb(path: Path):
    return Image.open(path).convert("RGB")


def cover(img: Image.Image, size, focus=(0.5, 0.5)):
    ratio = max(size[0] / img.width, size[1] / img.height)
    img = img.resize((round(img.width * ratio), round(img.height * ratio)), Image.Resampling.LANCZOS)
    x = max(0, min(img.width - size[0], round((img.width - size[0]) * focus[0])))
    y = max(0, min(img.height - size[1], round((img.height - size[1]) * focus[1])))
    return img.crop((x, y, x + size[0], y + size[1]))


def contain(img: Image.Image, size, bg=WHITE, pad=0):
    frame = Image.new("RGB", size, bg)
    obj = ImageOps.contain(img, (size[0] - 2 * pad, size[1] - 2 * pad), Image.Resampling.LANCZOS)
    frame.paste(obj, ((size[0] - obj.width) // 2, (size[1] - obj.height) // 2))
    return frame


def normalize_single(src: Path, dst: Path):
    im = open_rgb(src)
    # Existing single-shoe sources already have clean white backgrounds. Crop the useful
    # object area, then place every color on the same canvas and baseline.
    arr = np.asarray(im)
    fg = np.any(arr < 245, axis=2)
    labels, count = ndimage.label(fg)
    if count:
        sizes = ndimage.sum(fg, labels, range(1, count + 1))
        keep = labels == (int(np.argmax(sizes)) + 1)
        ys, xs = np.where(keep)
        box = (max(0, xs.min() - 18), max(0, ys.min() - 18), min(im.width, xs.max() + 19), min(im.height, ys.max() + 19))
        im = im.crop(box)
    frame = Image.new("RGB", (W, H), WHITE)
    obj = ImageOps.contain(im, (1000, 760), Image.Resampling.LANCZOS)
    frame.paste(obj, ((W - obj.width) // 2, 220 + (760 - obj.height) // 2))
    frame.save(dst, quality=96)


def extract_white_manual(src: Path, dst: Path):
    """Deterministic extraction of the foreground real shoe; no generative redraw."""
    # The right shoe in the verified white color photo is fully separated from the
    # other shoe. Crop it first so the extraction cannot leak into the second shoe.
    full = open_rgb(src)
    im = full.crop((300, 245, 845, 805))
    arr = np.asarray(im)
    roi_arr = np.ones((im.height, im.width), dtype=bool)
    mx, mn = arr.max(axis=2), arr.min(axis=2)
    brightness = arr.mean(axis=2)
    # White/cream shoe against very dark pavement.
    seed = roi_arr & (brightness > 92) & ((mx - mn) < 115)
    seed = ndimage.binary_closing(seed, iterations=3)
    seed = ndimage.binary_fill_holes(seed)
    seed = ndimage.binary_dilation(seed, iterations=1)
    seed &= roi_arr
    # Keep only the largest connected foreground area.
    labels, count = ndimage.label(seed)
    if count:
        sizes = ndimage.sum(seed, labels, range(1, count + 1))
        seed = labels == (int(np.argmax(sizes)) + 1)
    alpha = Image.fromarray((seed * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0))
    rgba = im.convert("RGBA")
    rgba.putalpha(alpha)
    bbox = alpha.getbbox()
    if not bbox:
        raise RuntimeError("white shoe extraction failed")
    obj = rgba.crop(bbox)
    obj = ImageOps.contain(obj, (1000, 760), Image.Resampling.LANCZOS)
    frame = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    x = (W - obj.width) // 2
    y = 220 + (760 - obj.height) // 2
    shadow = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse((x + 100, y + obj.height - 34, x + obj.width - 70, y + obj.height + 32), fill=(40, 48, 48, 35))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    frame = Image.alpha_composite(frame, shadow)
    frame.alpha_composite(obj, (x, y))
    frame.convert("RGB").save(dst, quality=96)


normalize_single(RAW / "20.jpg", COLORS / "01_black.jpg")
normalize_single(RAW / "19.jpg", COLORS / "02_cream.jpg")
normalize_single(RAW / "18.jpg", COLORS / "03_light_grey.jpg")
extract_white_manual(PRODUCT / "03_颜色图/white.jpg", COLORS / "04_white_manual.jpg")


def text(draw, xy, value, size, color=INK, bold=False, anchor=None):
    draw.text(xy, value, font=font(size, bold), fill=color, anchor=anchor)


def wrap(draw, value, width, size, bold=False):
    words, lines, line = value.split(), [], ""
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


def card(draw, box, fill=WHITE, outline=LINE, radius=26, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def round_mask(size, radius):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


def paste_round(canvas, img, box, radius=26, focus=(0.5, 0.5), contain_mode=False, bg=WHITE):
    x, y, w, h = box
    fitted = contain(img, (w, h), bg, 18) if contain_mode else cover(img, (w, h), focus)
    canvas.paste(fitted, (x, y), round_mask((w, h), radius))


def canvas(bg="#F6F8F7"):
    return Image.new("RGB", (W, H), bg)


def header(im, eyebrow, title, subtitle=None, dark=False):
    d = ImageDraw.Draw(im)
    base = WHITE if dark else INK
    muted = "#DDE9E4" if dark else MUTED
    text(d, (66, 62), eyebrow.upper(), 22, "#A7D7C4" if dark else GREEN, True)
    text(d, (66, 102), title, 46, base, True)
    if subtitle:
        text(d, (66, 164), subtitle, 22, muted)
    return d


def save_contact(paths, dst, cols=3, thumb=420, label_h=46):
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb, rows * (thumb + label_h)), "#E9ECEB")
    d = ImageDraw.Draw(sheet)
    for i, path in enumerate(paths):
        im = contain(open_rgb(path), (thumb, thumb), WHITE, 5)
        x, y = (i % cols) * thumb, (i // cols) * (thumb + label_h)
        sheet.paste(im, (x, y))
        text(d, (x + 14, y + thumb + label_h // 2), path.stem, 18, INK, True, anchor="lm")
    sheet.save(dst, quality=93)


black = open_rgb(COLORS / "01_black.jpg")
cream = open_rgb(COLORS / "02_cream.jpg")
grey = open_rgb(COLORS / "03_light_grey.jpg")
white = open_rgb(COLORS / "04_white_manual.jpg")
factory_exterior = open_rgb(AI / "factory_exterior_ai_v1.png")
factory_workshop = open_rgb(AI / "factory_workshop_ai_v1.png")
factory_qc = open_rgb(AI / "factory_qc_ai_v1.png")
real_batch = open_rgb(FACTORY / "02_产品检查生产/04_batch_check.jpg")
real_line = open_rgb(FACTORY / "02_产品检查生产/03_line_sorting.jpg")
angle_hand = open_rgb(RAW / "5.jpg")
angle_top = open_rgb(RAW / "10.jpg")
angle_outsole = open_rgb(RAW / "15.jpg")
faq_product = open_rgb(RAW / "4.jpg")


# Main gallery v3: only M1 is a plain white-background image. M2-M6 use
# clearly different visual roles instead of repeating catalog-white layouts.
m1 = grey.copy()
m1.save(MAIN / "M1_light_grey_white_search_hero.jpg", quality=96)

m2 = canvas("#DDEAE4"); d = header(m2, "COLOR OPTIONS", "FOUR VERIFIED COLORS", "Black · Cream · Light Grey · White")
for i, (name, im) in enumerate([("BLACK", black), ("CREAM", cream), ("LIGHT GREY", grey), ("WHITE", white)]):
    x, y = 55 + (i % 2) * 570, 225 + (i // 2) * 440
    card(d, (x, y, x + 520, y + 390), fill="#F7FAF8", outline="#BDD2C9")
    paste_round(m2, im, (x + 18, y + 18, 484, 300), 18, contain_mode=True, bg="#F7FAF8")
    text(d, (x + 28, y + 350), name, 24, INK, True)
m2.save(MAIN / "M2_four_color_range.jpg", quality=95)

m3 = canvas(GREEN_DARK); d = header(m3, "MULTI-ANGLE PROOF", "SEE THE SHOE FROM THREE VIEWS", "Real A206 source photography", dark=True)
for i, (im, title, focus) in enumerate([
    (angle_hand, "SIDE PROFILE", (0.50, 0.55)),
    (angle_top, "TOP + OPENING", (0.50, 0.50)),
    (angle_outsole, "SOLE + OUTSOLE", (0.70, 0.58)),
]):
    x = 45 + i * 390
    paste_round(m3, im, (x, 245, 355, 700), 24, focus=focus)
    text(d, (x + 18, 990), f"0{i + 1}", 19, "#A7D7C4", True)
    text(d, (x + 68, 990), title, 21, WHITE, True)
m3.save(MAIN / "M3_multi_angle_proof.jpg", quality=95)

m4 = canvas(SAND); d = header(m4, "OEM / ODM", "CUSTOMIZATION DISCUSSION", "Confirm the scope before sampling and bulk production")
d.rounded_rectangle((55, 235, 645, 1055), radius=34, fill="#E0E9E1")
paste_round(m4, cream, (85, 300, 530, 650), 28, contain_mode=True, bg="#E0E9E1")
text(d, (350, 992), "A206 PRODUCT ANCHOR", 19, GREEN_DARK, True, anchor="mm")
for i, (title, body) in enumerate([
    ("LOGO ARTWORK", "Review placement and artwork"),
    ("COLOR DIRECTION", "Based on approved materials"),
    ("SIZE MIX", "Confirm range and ratio"),
    ("PACKING", "Discuss label and box needs"),
]):
    y = 250 + i * 198
    card(d, (690, y, 1145, y + 156), fill=WHITE)
    text(d, (722, y + 34), f"0{i + 1}", 21, GREEN, True)
    text(d, (790, y + 31), title, 22, INK, True)
    text(d, (790, y + 75), body, 18, MUTED)
m4.save(MAIN / "M4_cream_oem_odm.jpg", quality=95)

m5 = canvas("#E7F0EC"); d = header(m5, "QUOTATION FAQ", "WHAT HELPS US QUOTE FASTER?", "One clear purchase brief reduces back-and-forth")
paste_round(m5, faq_product, (55, 235, 560, 820), 30, focus=(0.43, 0.53))
for i, (title, body) in enumerate([
    ("MODEL + COLOR", "Choose the product direction"),
    ("QUANTITY", "Total pairs and size ratio"),
    ("CUSTOMIZATION", "Logo artwork and packing"),
    ("DESTINATION", "Country, city or port"),
]):
    y = 235 + i * 205
    card(d, (660, y, 1145, y + 165), fill="#F8FBF9", outline="#BDD2C9")
    text(d, (690, y + 33), f"0{i + 1}", 19, GREEN, True)
    text(d, (750, y + 31), title, 22, INK, True)
    text(d, (750, y + 78), body, 18, MUTED)
m5.save(MAIN / "M5_quotation_faq.jpg", quality=95)

m6 = canvas(GREEN_DARK); d = header(m6, "FACTORY PROFILE", "FROM FACTORY TO ORDER REVIEW", "Real-photo anchored supplier presentation", dark=True)
paste_round(m6, factory_exterior, (55, 235, 520, 735), 26, focus=(0.52, 0.50))
paste_round(m6, factory_workshop, (600, 235, 545, 350), 26, focus=(0.52, 0.52))
paste_round(m6, factory_qc, (600, 610, 545, 360), 26, focus=(0.50, 0.58))
text(d, (55, 1035), "QUANZHOU BASE", 19, "#DDE9E4", True)
text(d, (600, 1035), "WORKSHOP + ORDER-BASED REVIEW", 19, "#DDE9E4", True)
m6.save(MAIN / "M6_upgraded_factory_profile.jpg", quality=95)


# Product detail modules.
d1 = canvas(); d = header(d1, "A206", "MEN'S KNIT LACE-UP WALKING SHOES", "For importers, wholesalers, online sellers and brand buyers")
paste_round(d1, cream, (55, 225, 700, 850), 30, contain_mode=True)
for i, value in enumerate(["KNIT / TEXTILE UPPER", "LACE-UP", "EVA SOLE", "ROUND TOE", "REGULAR FIT"]):
    card(d, (800, 245 + i * 150, 1145, 360 + i * 150), fill=WHITE)
    text(d, (828, 303 + i * 150), value, 21, GREEN_DARK, True, anchor="lm")
d1.save(DETAIL / "D1_product_overview.jpg", quality=95)

d2 = canvas(); d = header(d2, "VERIFIED FIELDS", "SPECIFICATION AT A GLANCE", "No unsupported performance or medical claims")
specs = [("MODEL", "A206"), ("UPPER", "Knit / Textile"), ("CLOSURE", "Lace-Up"), ("SOLE", "EVA"),
         ("TOE", "Round Toe"), ("FIT", "Regular Fit"), ("SIZE", "EU 35–45"), ("COLORS", "Black / Cream / Light Grey / White")]
for i, (key, value) in enumerate(specs):
    x, y = 55 + (i % 2) * 570, 230 + (i // 2) * 205
    card(d, (x, y, x + 520, y + 160), fill=WHITE)
    text(d, (x + 28, y + 28), key, 19, GREEN, True)
    text(d, (x + 28, y + 78), value, 25, INK, True)
d2.save(DETAIL / "D2_verified_specifications.jpg", quality=95)

d3 = canvas(); d = header(d3, "REAL PRODUCT", "CONSTRUCTION DETAILS", "Different colors help buyers read each structure clearly")
for i, (im, title, body) in enumerate([(black, "KNIT UPPER", "Visible knitted texture"), (grey, "LACE-UP", "Adjustable closure"), (white, "SOLE PROFILE", "Visible EVA structure")]):
    x = 45 + i * 390
    paste_round(d3, im, (x, 235, 355, 650), 24, contain_mode=True)
    card(d, (x, 910, x + 355, 1055), fill=WHITE)
    text(d, (x + 24, 937), title, 22, GREEN, True)
    text(d, (x + 24, 981), body, 18, MUTED)
d3.save(DETAIL / "D3_construction_details.jpg", quality=95)

d4 = m2.copy(); ImageDraw.Draw(d4).rectangle((0, 0, W, 205), fill="#F6F8F7")
header(d4, "ORDER OPTIONS", "COLOR + SIZE DIRECTION", "EU 35–45 · Confirm final color and size ratio before order")
d4.save(DETAIL / "D4_color_and_size.jpg", quality=95)

d5 = canvas(SAND); d = header(d5, "OEM / ODM FLOW", "FROM BUYER BRIEF TO BULK ORDER", "A practical discussion path for customization")
steps = [("01", "BUYER BRIEF", "Model, quantity, market"), ("02", "ARTWORK REVIEW", "Logo and packing files"),
         ("03", "SAMPLE DISCUSSION", "Confirm requested scope"), ("04", "ORDER REVIEW", "Size ratio and delivery terms")]
for i, (num, title, body) in enumerate(steps):
    x, y = 70 + (i % 2) * 555, 260 + (i // 2) * 365
    card(d, (x, y, x + 500, y + 300), fill=WHITE)
    d.ellipse((x + 30, y + 34, x + 110, y + 114), fill=GREEN)
    text(d, (x + 70, y + 74), num, 22, WHITE, True, anchor="mm")
    text(d, (x + 135, y + 45), title, 23, INK, True)
    d.multiline_text((x + 35, y + 150), wrap(d, body, 430, 21), font=font(21), fill=MUTED, spacing=7)
d5.save(DETAIL / "D5_oem_odm_workflow.jpg", quality=95)

d6 = canvas(); d = header(d6, "INQUIRY CHECKLIST", "SEND THESE DETAILS FOR A USEFUL REPLY", "Clear inputs reduce back-and-forth")
paste_round(d6, grey, (640, 235, 510, 775), 28, contain_mode=True)
for i, value in enumerate(["Selected model / color", "Estimated quantity", "Size range and ratio", "Logo / label / packing", "Destination and target timing"]):
    y = 255 + i * 145
    card(d, (55, y, 590, y + 105), fill=WHITE)
    d.ellipse((80, y + 29, 128, y + 77), fill=GREEN)
    text(d, (104, y + 53), "✓", 24, WHITE, True, anchor="mm")
    text(d, (155, y + 53), value, 21, INK, True, anchor="lm")
d6.save(DETAIL / "D6_inquiry_checklist.jpg", quality=95)


# Company detail modules using accepted real-origin AI retouch candidates.
def company_full(img, eyebrow, title, subtitle, dst, focus=(0.5, 0.5)):
    page = canvas(GREEN_DARK)
    paste_round(page, img, (45, 45, 1110, 825), 30, focus=focus)
    d = ImageDraw.Draw(page)
    text(d, (70, 925), eyebrow.upper(), 21, "#A7D7C4", True)
    text(d, (70, 970), title, 40, WHITE, True)
    d.multiline_text((70, 1030), wrap(d, subtitle, 1040, 22), font=font(22), fill="#DDE9E4", spacing=6)
    page.save(dst, quality=95)


company_full(factory_exterior, "Factory identity", "QUANZHOU BEIQIANG FOOTWEAR", "Factory profile anchored to the real company entrance.", COMPANY / "C1_factory_identity.jpg", (0.55, 0.50))
company_full(factory_workshop, "Workshop", "FOOTWEAR PRODUCTION ENVIRONMENT", "Development and production discussions are handled against the selected product brief.", COMPANY / "C2_workshop_environment.jpg", (0.52, 0.54))
company_full(factory_qc, "Order review", "VISIBLE SOLE + SHOE CHECK", "Quality requirements should be confirmed by model, materials, quantity and buyer standard.", COMPANY / "C3_quality_review.jpg", (0.48, 0.57))

c4 = canvas(); d = header(c4, "PROCESS EVIDENCE", "WORK-IN-PROCESS CONTROL", "Real workshop view presented without capacity claims")
paste_round(c4, real_line, (55, 225, 650, 790), 28, focus=(0.60, 0.50))
card(d, (755, 225, 1145, 1015), fill=WHITE)
text(d, (790, 280), "ORDER-BASED REVIEW", 25, GREEN, True)
for i, value in enumerate(["Model and material", "Construction points", "Size ratio", "Packing requirement"]):
    text(d, (795, 390 + i * 110), f"•  {value}", 21, INK)
c4.save(COMPANY / "C4_process_evidence.jpg", quality=95)

c5 = canvas(SAND); d = header(c5, "BUYER BRIEF", "WHAT WE NEED TO START", "One clear brief creates a more useful OEM/ODM discussion")
for i, (title, body) in enumerate([("PRODUCT", "Reference model or target style"), ("QUANTITY", "Estimated pairs and size ratio"),
                                   ("CUSTOMIZATION", "Logo, color and packing files"), ("MARKET", "Destination and sales channel")]):
    x, y = 55 + (i % 2) * 570, 240 + (i // 2) * 330
    card(d, (x, y, x + 520, y + 270), fill=WHITE)
    text(d, (x + 30, y + 38), title, 24, GREEN, True)
    d.multiline_text((x + 30, y + 100), wrap(d, body, 455, 22), font=font(22), fill=INK, spacing=7)
card(d, (55, 930, 1145, 1065), fill=GREEN_DARK, outline=GREEN_DARK)
text(d, (600, 997), "SEND YOUR BRIEF FOR MODEL-SPECIFIC DISCUSSION", 25, WHITE, True, anchor="mm")
c5.save(COMPANY / "C5_buyer_brief.jpg", quality=95)


main_paths = sorted(MAIN.glob("*.jpg"))
detail_paths = sorted(DETAIL.glob("*.jpg"))
company_paths = sorted(COMPANY.glob("*.jpg"))
color_paths = sorted(COLORS.glob("*.jpg"))
save_contact(color_paths, PREVIEW / "01_unified_color_set.jpg", cols=4, thumb=360)
save_contact(main_paths, PREVIEW / "02_main_gallery_contact.jpg", cols=3, thumb=420)
save_contact(detail_paths, PREVIEW / "03_product_detail_contact.jpg", cols=3, thumb=420)
save_contact(company_paths, PREVIEW / "04_company_detail_contact.jpg", cols=3, thumb=420)

with (OUT / "README.md").open("w", encoding="utf-8") as f:
    f.write("# BQ019-W1 整页视觉样板 v3\n\n")
    f.write("状态：仅供视觉复核，未上传平台。\n\n")
    f.write("- 首图：浅灰单鞋、纯白底、不叠字；六张中只有这一张是整幅纯白搜索图。\n")
    f.write("- 四色：黑 / 米白 / 浅灰 / 白，用浅绿色采购页统一承载，不再做第二张整幅白底图。\n")
    f.write("- 六张主图：搜索首图、四色、三视角、OEM/ODM、实拍FAQ、工厂概览各司其职。\n")
    f.write("- 工厂：外观、车间、检查使用实拍锚定的 AI 修复候选；第三方字样纸箱图已淘汰。\n")
    f.write("- 淘汰：白鞋 AI 重画（鞋型漂移）；鞋楦货架 AI 修复（数量复制）；厂房拉远 AI 候选（补造未知右侧立面）。\n")
    f.write("- 风险边界：不写年限、产能、证书、准时交付等无证据承诺。\n")
