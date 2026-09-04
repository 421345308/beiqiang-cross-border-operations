from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps


PRODUCT = Path(r"E:\贝强大文件\01_产品资产\02_可发布素材\00_最终上传\BQ006_M8811")
RAW = Path(r"E:\贝强大文件\01_产品资产\01_原始数据包\已整理_BQ006_M8811_贝强鞋业秋冬季新款M8811男女鞋35-45批58元\贝强鞋业秋冬季新款M8811男女鞋35-45批58元\主图")
FACTORY = Path(r"E:\贝强大文件\01_产品资产\02_可发布素材\00_最终上传\00_厂家资料\00_精选可用照片")
OUT = PRODUCT / "04_修复_2026-09-04"
DETAIL_OUT = OUT / "01_product_detail"
COMPANY_OUT = OUT / "02_company_detail"
COLOR_OUT = OUT / "03_sku_colors"

W = H = 1200
BG = (247, 249, 247)
WHITE = (255, 255, 255)
DARK = (31, 43, 38)
GREEN = (37, 94, 69)
MUTED = (86, 103, 95)
LINE = (215, 224, 219)
PALE = (232, 240, 235)


def font(size: int, bold: bool = False):
    choices = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
    ]
    for path in choices:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


FT = font(58, True)
FS = font(29, True)
FB = font(25)
FL = font(22, True)
FSM = font(18)


def fit(path: Path, size: tuple[int, int], centering=(0.5, 0.5)) -> Image.Image:
    with Image.open(path) as image:
        return ImageOps.fit(image.convert("RGB"), size, Image.Resampling.LANCZOS, centering=centering)


def contain(path: Path, size: tuple[int, int], bg=WHITE) -> Image.Image:
    with Image.open(path) as image:
        image = image.convert("RGB")
        image.thumbnail(size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", size, bg)
        canvas.paste(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
        return canvas


def rounded_paste(base: Image.Image, image: Image.Image, xy: tuple[int, int], radius=24):
    mask = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, image.width - 1, image.height - 1), radius=radius, fill=255)
    base.paste(image, xy, mask)


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, width: int):
    lines, current = [], ""
    for word in text.split():
        trial = word if not current else f"{current} {word}"
        if draw.textbbox((0, 0), trial, font=fnt)[2] <= width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def paragraph(draw, text, x, y, width, fnt=FB, fill=DARK, gap=8):
    for line in wrap(draw, text, fnt, width):
        draw.text((x, y), line, font=fnt, fill=fill)
        y += fnt.size + gap
    return y


def header(draw, kicker: str, title: str, subtitle: str):
    draw.rectangle((0, 0, W, 16), fill=GREEN)
    draw.text((68, 48), kicker.upper(), font=FL, fill=GREEN)
    draw.text((68, 86), title, font=FT, fill=DARK)
    paragraph(draw, subtitle, 70, 160, 1040, FS, MUTED, 5)


def footer(draw):
    draw.line((68, 1140, 1132, 1140), fill=LINE, width=2)
    draw.text((68, 1155), "BEIQIANG FOOTWEAR  |  OEM / ODM & WHOLESALE SUPPLY", font=FSM, fill=MUTED)


def bullet_list(draw, items, x, y, width, gap=58):
    for item in items:
        draw.ellipse((x, y + 8, x + 14, y + 22), fill=GREEN)
        paragraph(draw, item, x + 30, y, width - 30, FB, DARK, 5)
        y += gap


def save(canvas, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, quality=94, optimize=True)


def detail_overview():
    c = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(c)
    header(d, "M8811 PRODUCT OVERVIEW", "Breathable Knit Walking Shoe", "A regular-fit lace-up style for casual walking and seasonal retail collections.")
    rounded_paste(c, contain(PRODUCT / "01_主图/03_grey.jpg", (620, 620)), (60, 300), 28)
    d.rounded_rectangle((720, 300, 1140, 920), radius=28, fill=WHITE, outline=LINE, width=2)
    d.text((770, 350), "BUYER HIGHLIGHTS", font=FS, fill=GREEN)
    bullet_list(d, ["Breathable knitted textile upper", "Adjustable lace-up closure", "Lightweight chunky EVA sole", "EU 35–45 size assortment"], 770, 430, 320, 92)
    d.rounded_rectangle((720, 810, 1090, 880), radius=18, fill=PALE)
    d.text((760, 830), "REGULAR FIT", font=FL, fill=GREEN)
    footer(d)
    save(c, DETAIL_OUT / "01_overview.jpg")


def detail_structure():
    c = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(c)
    header(d, "PRODUCT PROOF", "Construction Buyers Can Check", "Visible product details shown from the M8811 source package.")
    cards = [
        (RAW / "19.jpg", "KNITTED UPPER", "Breathable textile construction"),
        (RAW / "17.jpg", "OUTSOLE TEXTURE", "Visible tread for buyer review"),
        (RAW / "20.jpg", "LACE-UP FRONT", "Adjustable everyday closure"),
    ]
    for i, (path, label, copy) in enumerate(cards):
        x = 55 + i * 380
        d.rounded_rectangle((x, 300, x + 350, 980), radius=28, fill=WHITE, outline=LINE, width=2)
        rounded_paste(c, fit(path, (310, 410)), (x + 20, 325), 22)
        d.text((x + 26, 775), label, font=FL, fill=GREEN)
        paragraph(d, copy, x + 26, 825, 295, FB, DARK, 6)
    footer(d)
    save(c, DETAIL_OUT / "02_structure.jpg")


def detail_size_colors():
    c = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(c)
    header(d, "ASSORTMENT", "Sizes & Actual Color Options", "Confirm the final size and color ratio for the current order before production.")
    d.rounded_rectangle((65, 265, 1135, 360), radius=24, fill=GREEN)
    d.text((118, 287), "MAIN SIZE RANGE: EU 35–45", font=FS, fill=WHITE)
    d.text((665, 291), "PINK & PURPLE: EU 35–40", font=FL, fill=WHITE)
    colors = [
        (PRODUCT / "01_主图/02_white.jpg", "All White"),
        (PRODUCT / "01_主图/03_grey.jpg", "White Grey"),
        (PRODUCT / "01_主图/04_blackw.jpg", "Black White"),
        (PRODUCT / "01_主图/07_black.jpg", "All Black"),
        (PRODUCT / "01_主图/05_purple.jpg", "White Purple"),
        (PRODUCT / "01_主图/06_pink.jpg", "White Pink"),
        (PRODUCT / "01_主图/08_white_green_catalog.png", "White Green"),
    ]
    positions = [(55 + i * 275, 405) for i in range(4)] + [(190 + i * 275, 740) for i in range(3)]
    for (path, label), (x, y) in zip(colors, positions):
        d.rounded_rectangle((x, y, x + 255, y + 285), radius=22, fill=WHITE, outline=LINE, width=2)
        rounded_paste(c, contain(path, (225, 205)), (x + 15, y + 15), 16)
        tw = d.textbbox((0, 0), label, font=FSM)[2]
        d.text((x + (255 - tw) / 2, y + 235), label, font=FSM, fill=DARK)
    footer(d)
    save(c, DETAIL_OUT / "03_size_colors.jpg")


def detail_order_support():
    c = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(c)
    header(d, "ORDER SUPPORT", "From Requirement to Confirmed Sample", "Send your target market, quantity and customization brief for production review.")
    rounded_paste(c, contain(PRODUCT / "01_主图/01_main.jpg", (510, 610), BG), (55, 315), 30)
    steps = [
        ("01", "Requirement Review", "Style, quantity, sizes and destination"),
        ("02", "Customization Discussion", "Logo, color, insole and packaging"),
        ("03", "Sample Confirmation", "Confirm appearance and order details"),
        ("04", "Production & Dispatch", "Arrange promptly after details are confirmed"),
    ]
    for i, (num, title, copy) in enumerate(steps):
        y = 300 + i * 165
        d.ellipse((640, y, 710, y + 70), fill=GREEN)
        d.text((657, y + 18), num, font=FL, fill=WHITE)
        d.text((745, y), title, font=FS, fill=DARK)
        paragraph(d, copy, 745, y + 48, 385, FB, MUTED, 5)
    d.rounded_rectangle((620, 970, 1135, 1080), radius=22, fill=PALE)
    paragraph(d, "Customized-order timing depends on materials, quantity and requirements and is confirmed before order.", 650, 988, 455, FSM, GREEN, 4)
    footer(d)
    save(c, DETAIL_OUT / "04_order_support.jpg")


def company_page(kicker, title, subtitle, photo_paths, labels, out_name, intro):
    c = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(c)
    header(d, kicker, title, subtitle)
    if len(photo_paths) == 1:
        rounded_paste(c, fit(photo_paths[0], (1060, 600)), (70, 300), 30)
    else:
        rounded_paste(c, fit(photo_paths[0], (520, 600)), (70, 300), 30)
        rounded_paste(c, fit(photo_paths[1], (520, 600)), (610, 300), 30)
    d.rounded_rectangle((70, 935, 1130, 1100), radius=24, fill=WHITE, outline=LINE, width=2)
    paragraph(d, intro, 105, 965, 990, FB, DARK, 7)
    if labels:
        d.text((105, 1050), "  •  ".join(labels), font=FSM, fill=GREEN)
    footer(d)
    save(c, COMPANY_OUT / out_name)


def company_customization():
    c = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(c)
    header(d, "CUSTOMIZATION", "Confirm Options Before Production", "Share your logo, color, size ratio and packaging brief for review.")
    colors = [
        (PRODUCT / "01_主图/02_white.jpg", "All White"),
        (PRODUCT / "01_主图/03_grey.jpg", "White Grey"),
        (PRODUCT / "01_主图/04_blackw.jpg", "Black White"),
        (PRODUCT / "01_主图/07_black.jpg", "All Black"),
        (PRODUCT / "01_主图/08_white_green_catalog.png", "White Green"),
        (PRODUCT / "01_主图/05_purple.jpg", "White Purple"),
        (PRODUCT / "01_主图/06_pink.jpg", "White Pink"),
    ]
    positions = [(55 + i * 275, 285) for i in range(4)] + [(190 + i * 275, 525) for i in range(3)]
    for (path, label), (x, y) in zip(colors, positions):
        d.rounded_rectangle((x, y, x + 255, y + 205), radius=20, fill=WHITE, outline=LINE, width=2)
        rounded_paste(c, contain(path, (225, 145)), (x + 15, y + 12), 14)
        tw = d.textbbox((0, 0), label, font=FSM)[2]
        d.text((x + (255 - tw) / 2, y + 169), label, font=FSM, fill=DARK)
    d.rounded_rectangle((70, 780, 1130, 1095), radius=24, fill=WHITE, outline=LINE, width=2)
    d.text((105, 820), "BUYER BRIEF", font=FS, fill=GREEN)
    bullet_list(d, [
        "Send logo artwork and target color references",
        "Confirm size ratio, quantity and target market",
        "Review sample details before bulk production",
    ], 105, 880, 970, 58)
    d.text((105, 1050), "Available options are confirmed against the selected style before order.", font=FSM, fill=MUTED)
    footer(d)
    save(c, COMPANY_OUT / "02_customization.jpg")


def company_packing():
    c = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(c)
    header(d, "PACKING & DISPATCH", "Order-Specific Packing Review", "Packing and shipping details are confirmed for each order before dispatch.")
    steps = [
        ("01", "PACKING", "Confirm shoe box and carton requirements"),
        ("02", "QUANTITY", "Confirm order quantity and size ratio"),
        ("03", "DESTINATION", "Provide country, city and postal code"),
        ("04", "TRADE TERM", "Confirm EXW, FOB or requested option"),
    ]
    for i, (num, title, copy) in enumerate(steps):
        x = 55 + i * 285
        d.rounded_rectangle((x, 300, x + 260, 835), radius=26, fill=WHITE, outline=LINE, width=2)
        d.ellipse((x + 88, 345, x + 172, 429), fill=GREEN)
        d.text((x + 108, 368), num, font=FL, fill=WHITE)
        # Neutral unbranded carton illustration; this is a process diagram, not order evidence.
        d.rectangle((x + 60, 485, x + 200, 600), fill=PALE, outline=GREEN, width=4)
        d.line((x + 60, 485, x + 130, 445, x + 200, 485), fill=GREEN, width=4)
        d.line((x + 130, 445, x + 130, 560), fill=GREEN, width=3)
        tw = d.textbbox((0, 0), title, font=FL)[2]
        d.text((x + (260 - tw) / 2, 650), title, font=FL, fill=GREEN)
        paragraph(d, copy, x + 28, 705, 205, FSM, DARK, 4)
    d.rounded_rectangle((70, 890, 1130, 1095), radius=24, fill=WHITE, outline=LINE, width=2)
    paragraph(d, "Freight is quoted separately after the destination, quantity, packing method and trade term are confirmed.", 105, 930, 990, FB, DARK, 8)
    d.text((105, 1035), "Final packing and dispatch arrangements follow the confirmed order details.", font=FSM, fill=MUTED)
    footer(d)
    save(c, COMPANY_OUT / "05_packing.jpg")


def company_pages():
    company_page(
        "SUPPLIER IDENTITY", "Real Factory in Quanzhou", "A footwear supplier serving overseas wholesale and private-label buyers.",
        [FACTORY / "03_工厂仓库/大门.jpg", FACTORY / "03_工厂仓库/01_workshop.png"],
        ["Factory exterior", "Workshop environment"], "01_factory.jpg",
        "Quanzhou Beiqiang Footwear & Apparel Co., Ltd. supports OEM/ODM and wholesale footwear cooperation.",
    )
    company_customization()
    company_page(
        "PRODUCTION", "Production Arrangement", "Order details are confirmed before production scheduling.",
        [FACTORY / "02_产品检查生产/03_line_sorting.jpg"],
        ["Line preparation", "Batch sorting", "Production scheduling"], "03_production.jpg",
        "Production or dispatch is arranged promptly after the style, quantity, materials and customization requirements are confirmed.",
    )
    company_page(
        "QUALITY CHECK", "Manual Product Inspection", "Visible checks before packing preparation.",
        [FACTORY / "02_产品检查生产/01_upper_check.jpg", FACTORY / "02_产品检查生产/02_sole_check.jpg"],
        ["Upper check", "Sole check"], "04_quality.jpg",
        "The product condition, upper, sole and order details can be checked against the approved sample and confirmed specifications.",
    )
    company_packing()


def sku_color_files():
    COLOR_OUT.mkdir(parents=True, exist_ok=True)
    sources = {
        "white_pink.jpg": PRODUCT / "01_主图/06_pink.jpg",
        "white_purple.jpg": PRODUCT / "01_主图/05_purple.jpg",
        "white_grey.jpg": PRODUCT / "01_主图/03_grey.jpg",
        "all_black.jpg": PRODUCT / "01_主图/07_black.jpg",
        "black_white.jpg": PRODUCT / "01_主图/04_blackw.jpg",
        "white_green.jpg": PRODUCT / "01_主图/08_white_green_catalog.png",
        "all_white.jpg": PRODUCT / "01_主图/02_white.jpg",
    }
    for name, path in sources.items():
        contain(path, (800, 800), WHITE).save(COLOR_OUT / name, quality=95, optimize=True)


def preview():
    files = sorted(DETAIL_OUT.glob("*.jpg")) + sorted(COMPANY_OUT.glob("*.jpg"))
    sheet = Image.new("RGB", (900, len(files) * 250), (235, 238, 236))
    draw = ImageDraw.Draw(sheet)
    for i, path in enumerate(files):
        with Image.open(path) as image:
            image = image.convert("RGB")
            image.thumbnail((220, 220), Image.Resampling.LANCZOS)
            sheet.paste(image, (20, i * 250 + 15))
        draw.text((270, i * 250 + 35), path.name, font=FS, fill=DARK)
    save(sheet, OUT / "preview.jpg")


def main():
    for folder in (DETAIL_OUT, COMPANY_OUT, COLOR_OUT):
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.glob("*.jpg"):
            old.unlink()
    detail_overview()
    detail_structure()
    detail_size_colors()
    detail_order_support()
    company_pages()
    sku_color_files()
    preview()
    print(OUT)


if __name__ == "__main__":
    main()
