from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


FACTORY = Path(
    r"E:\贝强大文件\01_产品资产\02_可发布素材\00_最终上传\00_厂家资料\00_精选可用照片"
)
OUT = Path(
    r"E:\贝强大文件\01_产品资产\02_可发布素材\00_最终上传\00_共用中性公司图_v2_2026-09-04"
)

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
            pass
    return ImageFont.load_default()


FT = font(58, True)
FS = font(29, True)
FB = font(25)
FL = font(22, True)
FSM = font(18)


def fit(path: Path, size: tuple[int, int], centering=(0.5, 0.5)) -> Image.Image:
    with Image.open(path) as image:
        return ImageOps.fit(
            image.convert("RGB"), size, Image.Resampling.LANCZOS, centering=centering
        )


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
    draw.text(
        (68, 1155),
        "BEIQIANG FOOTWEAR  |  OEM / ODM & WHOLESALE SUPPLY",
        font=FSM,
        fill=MUTED,
    )


def save(canvas: Image.Image, name: str):
    OUT.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT / name, quality=94, optimize=True)


def photo_page(kicker, title, subtitle, photos, labels, intro, name):
    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)
    header(draw, kicker, title, subtitle)
    if len(photos) == 1:
        rounded_paste(canvas, fit(photos[0], (1060, 600)), (70, 300), 30)
    else:
        rounded_paste(canvas, fit(photos[0], (520, 600)), (70, 300), 30)
        rounded_paste(canvas, fit(photos[1], (520, 600)), (610, 300), 30)
    draw.rounded_rectangle((70, 935, 1130, 1100), radius=24, fill=WHITE, outline=LINE, width=2)
    paragraph(draw, intro, 105, 965, 990, FB, DARK, 7)
    draw.text((105, 1050), "  •  ".join(labels), font=FSM, fill=GREEN)
    footer(draw)
    save(canvas, name)


def customization_page():
    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)
    header(
        draw,
        "OEM / ODM DISCUSSION",
        "Confirm the Buyer Brief First",
        "Available customization is reviewed against the selected style before sampling or production.",
    )
    cards = [
        ("01", "LOGO", "Send vector artwork and placement reference"),
        ("02", "COLOR", "Share target colors or physical references"),
        ("03", "SIZE RATIO", "Confirm market, size range and quantities"),
        ("04", "PACKING", "Confirm shoe box, labels and carton brief"),
    ]
    for index, (number, title, copy) in enumerate(cards):
        x = 55 + index * 285
        draw.rounded_rectangle((x, 300, x + 260, 790), radius=26, fill=WHITE, outline=LINE, width=2)
        draw.ellipse((x + 88, 345, x + 172, 429), fill=GREEN)
        draw.text((x + 108, 368), number, font=FL, fill=WHITE)
        draw.rounded_rectangle((x + 55, 485, x + 205, 610), radius=18, fill=PALE)
        draw.line((x + 90, 545, x + 170, 545), fill=GREEN, width=5)
        draw.line((x + 130, 505, x + 130, 585), fill=GREEN, width=5)
        title_width = draw.textbbox((0, 0), title, font=FL)[2]
        draw.text((x + (260 - title_width) / 2, 650), title, font=FL, fill=GREEN)
        paragraph(draw, copy, x + 28, 705, 205, FSM, DARK, 4)
    draw.rounded_rectangle((70, 845, 1130, 1095), radius=24, fill=WHITE, outline=LINE, width=2)
    draw.text((105, 885), "WHAT TO SEND", font=FS, fill=GREEN)
    paragraph(
        draw,
        "Selected style or reference • target quantity • destination market • logo/color/packing brief",
        105,
        945,
        980,
        FB,
        DARK,
        8,
    )
    draw.text(
        (105, 1045),
        "Materials, tooling, MOQ, sample cost and timing are confirmed for the current request.",
        font=FSM,
        fill=MUTED,
    )
    footer(draw)
    save(canvas, "02_customization.jpg")


def packing_page():
    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)
    header(
        draw,
        "PACKING & DISPATCH",
        "Order-Specific Packing Review",
        "Packing, freight and dispatch details are confirmed for each order.",
    )
    cards = [
        ("01", "PACKING", "Confirm shoe box and carton requirements"),
        ("02", "QUANTITY", "Confirm order quantity and size ratio"),
        ("03", "DESTINATION", "Provide country, city and postal code"),
        ("04", "TRADE TERM", "Confirm EXW, FOB or requested option"),
    ]
    for index, (number, title, copy) in enumerate(cards):
        x = 55 + index * 285
        draw.rounded_rectangle((x, 300, x + 260, 835), radius=26, fill=WHITE, outline=LINE, width=2)
        draw.ellipse((x + 88, 345, x + 172, 429), fill=GREEN)
        draw.text((x + 108, 368), number, font=FL, fill=WHITE)
        draw.rectangle((x + 60, 485, x + 200, 600), fill=PALE, outline=GREEN, width=4)
        draw.line((x + 60, 485, x + 130, 445, x + 200, 485), fill=GREEN, width=4)
        draw.line((x + 130, 445, x + 130, 560), fill=GREEN, width=3)
        title_width = draw.textbbox((0, 0), title, font=FL)[2]
        draw.text((x + (260 - title_width) / 2, 650), title, font=FL, fill=GREEN)
        paragraph(draw, copy, x + 28, 705, 205, FSM, DARK, 4)
    draw.rounded_rectangle((70, 890, 1130, 1095), radius=24, fill=WHITE, outline=LINE, width=2)
    paragraph(
        draw,
        "Freight is quoted separately after destination, quantity, packing method and trade term are confirmed.",
        105,
        930,
        990,
        FB,
        DARK,
        8,
    )
    draw.text(
        (105, 1035),
        "Final packing and dispatch arrangements follow the confirmed order details.",
        font=FSM,
        fill=MUTED,
    )
    footer(draw)
    save(canvas, "05_packing.jpg")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.jpg"):
        old.unlink()
    photo_page(
        "SUPPLIER IDENTITY",
        "Real Factory in Quanzhou",
        "A footwear supplier serving overseas wholesale and private-label buyers.",
        [FACTORY / "03_工厂仓库/大门.jpg", FACTORY / "03_工厂仓库/01_workshop.png"],
        ["Factory exterior", "Workshop environment"],
        "Quanzhou Beiqiang Footwear & Apparel Co., Ltd. supports OEM/ODM and wholesale footwear cooperation.",
        "01_factory.jpg",
    )
    customization_page()
    photo_page(
        "PRODUCTION",
        "Production Arrangement",
        "Order details are confirmed before production scheduling.",
        [FACTORY / "02_产品检查生产/03_line_sorting.jpg"],
        ["Line preparation", "Batch sorting", "Production scheduling"],
        "Production or dispatch is arranged promptly after style, quantity, materials and customization requirements are confirmed.",
        "03_production.jpg",
    )
    photo_page(
        "QUALITY CHECK",
        "Manual Product Inspection",
        "Visible checks before packing preparation.",
        [FACTORY / "02_产品检查生产/01_upper_check.jpg", FACTORY / "02_产品检查生产/02_sole_check.jpg"],
        ["Upper check", "Sole check"],
        "Product condition, upper, sole and order details can be checked against the approved sample and confirmed specifications.",
        "04_quality.jpg",
    )
    packing_page()
    print(OUT)


if __name__ == "__main__":
    main()
