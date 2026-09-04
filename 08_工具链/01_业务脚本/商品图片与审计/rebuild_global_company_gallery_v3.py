"""Build the AI-assisted, evidence-safe Beiqiang company gallery v3.

The AI asset is used only as an abstract background.  Every factory/process
photo is an untouched real source photo (apart from crop/resize/color-neutral
overlay); all factual copy stays within confirmed Beiqiang positioning.
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance


SRC = Path(r"E:\贝强大文件\01_产品资产\02_可发布素材\00_最终上传\00_厂家资料\00_精选可用照片")
OUT = Path(r"E:\贝强大文件\01_产品资产\02_可发布素材\00_最终上传\00_共用中性公司图_v3_2026-09-04")
BG_PATH = OUT / "00_ai_background.png"
W = H = 1200

INK = (23, 39, 33)
GREEN = (25, 86, 61)
GREEN_2 = (42, 112, 78)
MUTED = (83, 101, 92)
CREAM = (248, 246, 239)
WHITE = (255, 255, 255)
LINE = (210, 219, 213)
PALE = (229, 239, 233)


def font(size: int, bold: bool = False):
    paths = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
    ]
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


F_KICK = font(19, True)
F_H1 = font(48, True)
F_H2 = font(27, True)
F_BODY = font(22)
F_BODY_B = font(22, True)
F_SMALL = font(17)
F_TINY = font(15)


def base() -> Image.Image:
    with Image.open(BG_PATH) as image:
        canvas = ImageOps.fit(image.convert("RGB"), (W, H), Image.Resampling.LANCZOS)
    wash = Image.new("RGBA", (W, H), (255, 255, 255, 38))
    return Image.alpha_composite(canvas.convert("RGBA"), wash)


def fit_photo(path: Path, size: tuple[int, int], centering=(0.5, 0.5)) -> Image.Image:
    with Image.open(path) as image:
        photo = ImageOps.fit(image.convert("RGB"), size, Image.Resampling.LANCZOS, centering=centering)
    return ImageEnhance.Contrast(ImageEnhance.Color(photo).enhance(0.96)).enhance(1.04)


def round_paste(canvas: Image.Image, photo: Image.Image, xy: tuple[int, int], radius=28):
    mask = Image.new("L", photo.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, photo.width - 1, photo.height - 1), radius=radius, fill=255)
    canvas.paste(photo.convert("RGBA"), xy, mask)


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, width: int):
    lines, current = [], ""
    for word in text.split():
        test = word if not current else f"{current} {word}"
        if draw.textbbox((0, 0), test, font=fnt)[2] <= width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def text_block(draw, text, x, y, width, fnt=F_BODY, fill=INK, gap=7):
    for line in wrap(draw, text, fnt, width):
        draw.text((x, y), line, font=fnt, fill=fill)
        y += fnt.size + gap
    return y


def top(draw, kicker: str, title: str, subtitle: str):
    draw.rounded_rectangle((54, 48, 1146, 228), radius=28, fill=(255, 255, 255, 236), outline=LINE, width=2)
    draw.text((82, 72), kicker.upper(), font=F_KICK, fill=GREEN_2)
    draw.text((82, 102), title, font=F_H1, fill=INK)
    text_block(draw, subtitle, 84, 164, 1000, F_BODY, MUTED, 4)


def footer(draw):
    draw.rounded_rectangle((54, 1138, 1146, 1184), radius=18, fill=(25, 86, 61, 242))
    draw.text((78, 1152), "BEIQIANG FOOTWEAR  ·  QUANZHOU, FUJIAN, CHINA", font=F_TINY, fill=WHITE)
    right = "OEM / ODM  ·  WHOLESALE SUPPLY"
    tw = draw.textbbox((0, 0), right, font=F_TINY)[2]
    draw.text((1120 - tw, 1152), right, font=F_TINY, fill=WHITE)


def card(draw, box, title, copy, number=None):
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=22, fill=(255, 255, 255, 238), outline=LINE, width=2)
    tx = x1 + 26
    if number:
        draw.ellipse((tx, y1 + 22, tx + 42, y1 + 64), fill=GREEN)
        draw.text((tx + 11, y1 + 33), number, font=F_TINY, fill=WHITE)
        tx += 56
    draw.text((tx, y1 + 26), title, font=F_BODY_B, fill=GREEN)
    text_block(draw, copy, x1 + 26, y1 + 72, x2 - x1 - 52, F_SMALL, INK, 5)


def page_identity():
    canvas = base(); draw = ImageDraw.Draw(canvas, "RGBA")
    top(draw, "SUPPLIER PROFILE", "A Real Footwear Factory Partner", "Footwear development, OEM/ODM and wholesale support for overseas B2B buyers.")
    scene = fit_photo(OUT / "00_ai_factory_profile.png", (1068, 590), (0.5, 0.58))
    round_paste(canvas, scene, (66, 266), 30)
    card(draw, (62, 892, 326, 1110), "QUANZHOU BASED", "Quanzhou Beiqiang Footwear & Apparel Co., Ltd.")
    card(draw, (344, 892, 718, 1110), "PRODUCT FOCUS", "Comfort walking, casual, lightweight slip-on and breathable textile footwear")
    card(draw, (736, 892, 1136, 1110), "COOPERATION", "OEM/ODM and wholesale supply for importers, brands, wholesalers and online sellers")
    footer(draw); save(canvas, "01_factory_profile.jpg")


def page_customization():
    canvas = base(); draw = ImageDraw.Draw(canvas, "RGBA")
    top(draw, "OEM / ODM", "From Buyer Brief to Approved Sample", "A structured development conversation helps reduce errors before production.")
    workshop = fit_photo(OUT / "00_ai_customization.png", (1068, 320), (0.5, 0.53))
    round_paste(canvas, workshop, (66, 264), 30)
    steps = [
        ("01", "BRIEF", "Style or reference, target market and quantity"),
        ("02", "DETAILS", "Logo artwork, colors, sizes and packing"),
        ("03", "SAMPLE", "Sample scope, cost and timing confirmed"),
        ("04", "APPROVAL", "Final specifications agreed before bulk"),
    ]
    for i, (num, title, copy) in enumerate(steps):
        x = 62 + i * 270
        card(draw, (x, 620, x + 252, 842), title, copy, num)
    draw.rounded_rectangle((62, 876, 1136, 1110), radius=26, fill=(255, 255, 255, 241), outline=LINE, width=2)
    draw.text((92, 906), "WHAT TO SEND WITH YOUR INQUIRY", font=F_H2, fill=GREEN)
    text_block(draw, "Selected model or reference · expected quantity · size range and ratio · logo/vector artwork · target colors · packing preference · destination market", 92, 956, 980, F_BODY, INK, 8)
    draw.text((92, 1060), "Materials, tooling, MOQ and lead time are reviewed for the selected request.", font=F_SMALL, fill=MUTED)
    footer(draw); save(canvas, "02_oem_odm_workflow.jpg")


def page_production():
    canvas = base(); draw = ImageDraw.Draw(canvas, "RGBA")
    top(draw, "PRODUCTION", "Order Details Drive the Schedule", "Production or dispatch is arranged promptly after the style and order requirements are confirmed.")
    photo = fit_photo(OUT / "00_ai_production.png", (1068, 520), (0.5, 0.5))
    round_paste(canvas, photo, (66, 266), 30)
    labels = [
        ("01", "SPEC CHECK", "Style, sizes and quantity"),
        ("02", "MATERIALS", "Confirmed for the order"),
        ("03", "SCHEDULING", "Based on actual requirements"),
        ("04", "FOLLOW-UP", "Progress communicated promptly"),
    ]
    for i, (num, title, copy) in enumerate(labels):
        x = 62 + i * 270
        card(draw, (x, 820, x + 252, 1056), title, copy, num)
    draw.rounded_rectangle((62, 1072, 1136, 1120), radius=16, fill=(25, 86, 61, 232))
    draw.text((86, 1085), "Timing depends on style, quantity, materials and customization; confirm it in the quotation.", font=F_SMALL, fill=WHITE)
    footer(draw); save(canvas, "03_production_process.jpg")


def page_quality():
    canvas = base(); draw = ImageDraw.Draw(canvas, "RGBA")
    top(draw, "QUALITY REVIEW", "Check Against the Approved Requirements", "Visible checks focus on the product and order details agreed with the buyer.")
    quality = fit_photo(OUT / "00_ai_quality.png", (1076, 510), (0.5, 0.5))
    round_paste(canvas, quality, (62, 266), 28)
    checks = [
        ("UPPER & COLOR", "Appearance and visible upper details"),
        ("SOLE & BONDING", "Visible sole condition and assembly"),
        ("SIZE & RATIO", "Order size plan and batch sorting"),
        ("PACKING REVIEW", "Labels and packing against the brief"),
    ]
    for i, (title, copy) in enumerate(checks):
        x = 62 + (i % 2) * 540; y = 812 + (i // 2) * 142
        card(draw, (x, y, x + 518, y + 126), title, copy)
    footer(draw); save(canvas, "04_quality_control.jpg")


def page_packing():
    canvas = base(); draw = ImageDraw.Draw(canvas, "RGBA")
    top(draw, "PACKING & QUOTATION", "Give Us the Details That Affect Delivery", "Packing and freight can be quoted accurately only after the order and destination are clear.")
    packing = fit_photo(OUT / "00_ai_packing.png", (1068, 360), (0.5, 0.5))
    round_paste(canvas, packing, (66, 264), 30)
    items = [
        ("01", "PACKING", "Shoe box, labels and carton preference"),
        ("02", "QUANTITY", "Pairs, color mix and size ratio"),
        ("03", "DESTINATION", "Country, city and postal code"),
        ("04", "TRADE TERM", "EXW, FOB or requested option"),
    ]
    for i, (num, title, copy) in enumerate(items):
        x = 62 + i * 270
        card(draw, (x, 656, x + 252, 850), title, copy, num)
    draw.rounded_rectangle((62, 884, 1136, 1108), radius=30, fill=(255, 255, 255, 242), outline=LINE, width=2)
    draw.text((94, 916), "NEXT STEP", font=F_KICK, fill=GREEN_2)
    draw.text((94, 950), "Send the model + quantity + customization brief", font=F_H2, fill=INK)
    text_block(draw, "We will review feasibility, MOQ, sample needs, packing and production timing before quoting.", 94, 998, 950, F_SMALL, INK, 5)
    draw.rounded_rectangle((94, 1062, 528, 1106), radius=18, fill=GREEN)
    draw.text((124, 1072), "REQUEST A QUOTATION", font=F_BODY_B, fill=WHITE)
    footer(draw); save(canvas, "05_packing_inquiry.jpg")


def save(canvas: Image.Image, name: str):
    OUT.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(OUT / name, quality=94, optimize=True)


def main():
    if not BG_PATH.is_file():
        raise FileNotFoundError(BG_PATH)
    page_identity(); page_customization(); page_production(); page_quality(); page_packing()
    print(OUT)


if __name__ == "__main__":
    main()
