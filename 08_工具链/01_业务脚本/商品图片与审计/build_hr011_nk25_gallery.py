from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
PROJECT = ROOT / "02_Alibaba运营" / "05_扩品工程" / "HR系列真实货源改造_2026-09-21"
SRC = PROJECT / "00_来源素材" / "HR011_NK25" / "NK25_lingzi_full"
MAIN = PROJECT / "01_正式主图候选" / "HR011_NK25"
DETAIL = PROJECT / "02_正式详情候选" / "HR011_NK25"
COMPANY = ROOT / "02_Alibaba运营" / "06_图片与检查记录" / "公司图复用模板_v4_2026-09-21"
FONT = Path(r"C:\Windows\Fonts\arial.ttf")
BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")
W = H = 1000


def font(size: int, bold: bool = False):
    return ImageFont.truetype(str(BOLD if bold else FONT), size)


def fitted(draw, text, max_width, start, bold=False):
    size = start
    while size > 18:
        candidate = font(size, bold)
        if draw.textbbox((0, 0), text, font=candidate)[2] <= max_width:
            return candidate
        size -= 2
    return font(size, bold)


def source(name):
    return Image.open(SRC / name).convert("RGB")


def paste_cover(canvas, img, box):
    x0, y0, x1, y1 = box
    tile = ImageOps.fit(img, (x1 - x0, y1 - y0), method=Image.Resampling.LANCZOS)
    canvas.paste(tile, (x0, y0))


def paste_contain(canvas, img, box, bg=(247, 249, 250)):
    x0, y0, x1, y1 = box
    panel = Image.new("RGB", (x1 - x0, y1 - y0), bg)
    tile = ImageOps.contain(img, panel.size, method=Image.Resampling.LANCZOS)
    panel.paste(tile, ((panel.width - tile.width) // 2, (panel.height - tile.height) // 2))
    canvas.paste(panel, (x0, y0))


def save(canvas, folder, name):
    folder.mkdir(parents=True, exist_ok=True)
    canvas.save(folder / name, "JPEG", quality=95, optimize=True)


def header(canvas, kicker, title, subtitle=None):
    draw = ImageDraw.Draw(canvas)
    height = 166 if subtitle else 132
    draw.rectangle((0, 0, W, height), fill="white")
    draw.text((54, 26), kicker.upper(), fill=(31, 124, 145), font=font(22, True))
    draw.text((54, 58), title, fill=(19, 30, 42), font=fitted(draw, title, 890, 48, True))
    if subtitle:
        draw.text((56, 120), subtitle, fill=(76, 91, 106), font=fitted(draw, subtitle, 880, 24))


def footer(canvas, left, right=None):
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 900, W, H), fill=(18, 28, 42))
    draw.text((50, 928), left, fill="white", font=fitted(draw, left, 590, 29, True))
    if right:
        fnt = fitted(draw, right, 310, 26, True)
        width = draw.textbbox((0, 0), right, font=fnt)[2]
        draw.text((950 - width, 931), right, fill=(126, 216, 232), font=fnt)


def clean_shoe_crop(color):
    chart = source("07.jpg")
    if color == "black":
        crop = chart.crop((14, 29, 368, 325))
    elif color == "grey":
        crop = chart.crop((383, 408, 737, 703))
    else:
        raise ValueError(color)
    return crop


def hero(color, badge, name):
    canvas = Image.new("RGB", (W, H), "white")
    shoe = clean_shoe_crop(color)
    paste_contain(canvas, shoe, (42, 110, 958, 845), "white")
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((42, 42, 320, 102), radius=22, fill=(18, 28, 42))
    draw.text((68, 59), badge, fill="white", font=fitted(draw, badge, 225, 24, True))
    draw.text((50, 902), "KNIT SLIP-ON SOCK SNEAKER", fill=(19, 30, 42), font=font(28, True))
    draw.text((770, 904), "NK25", fill=(31, 124, 145), font=font(31, True))
    save(canvas, MAIN, name)


def split_hero():
    canvas = Image.new("RGB", (W, H), "white")
    paste_contain(canvas, clean_shoe_crop("black"), (20, 135, 500, 850), "white")
    paste_contain(canvas, clean_shoe_crop("grey"), (500, 135, 980, 850), "white")
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((42, 42, 315, 102), radius=22, fill=(18, 28, 42))
    draw.text((69, 59), "B2B WHOLESALE", fill="white", font=font(24, True))
    draw.line((500, 155, 500, 825), fill=(224, 229, 233), width=3)
    draw.text((80, 865), "BLACK", fill=(19, 30, 42), font=font(25, True))
    draw.text((790, 865), "GREY", fill=(19, 30, 42), font=font(25, True))
    draw.text((50, 932), "TWO LAUNCH COLORS", fill=(19, 30, 42), font=font(28, True))
    draw.text((850, 933), "NK25", fill=(31, 124, 145), font=font(28, True))
    save(canvas, MAIN, "C_M1_NK25.jpg")


def colors_panel():
    canvas = Image.new("RGB", (W, H), (247, 249, 250))
    header(canvas, "B2B SKU CHOICE", "Black and Grey Launch Colors", "Actual source-page product photography")
    paste_contain(canvas, clean_shoe_crop("black"), (35, 185, 490, 790), "white")
    paste_contain(canvas, clean_shoe_crop("grey"), (510, 185, 965, 790), "white")
    draw = ImageDraw.Draw(canvas)
    for x0, label in ((35, "BLACK"), (510, "GREY")):
        draw.rounded_rectangle((x0, 810, x0 + 455, 875), radius=18, fill="white", outline=(206, 216, 224), width=2)
        fnt = font(26, True)
        tw = draw.textbbox((0, 0), label, font=fnt)[2]
        draw.text((x0 + (455 - tw) / 2, 829), label, fill=(19, 30, 42), font=fnt)
    footer(canvas, "2 COLORS  •  EU 36–45", "20 SKU")
    save(canvas, MAIN, "M2_COLORS_NK25.jpg")


def knit_panel():
    canvas = Image.new("RGB", (W, H), (247, 249, 250))
    header(canvas, "VISIBLE CONSTRUCTION", "Knit Upper Texture", "Detail is shown as visible structure, not a performance claim")
    texture = source("08.jpg").crop((0, 255, 750, 1007))
    paste_cover(canvas, texture, (0, 166, 610, 900))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((610, 166, 1000, 900), fill=(235, 241, 245))
    cards = [(250, "KNIT VIEW", "Actual upper texture"), (455, "SOCK COLLAR", "No-lace opening"), (660, "SOURCE PROOF", "NK25 photography")]
    for y, title, body in cards:
        draw.rounded_rectangle((650, y, 960, y + 145), radius=22, fill="white", outline=(205, 215, 224), width=2)
        draw.text((680, y + 28), title, fill=(19, 30, 42), font=fitted(draw, title, 245, 27, True))
        draw.text((680, y + 82), body, fill=(76, 91, 106), font=fitted(draw, body, 245, 21))
    footer(canvas, "ACTUAL PRODUCT DETAIL", "MODEL NK25")
    save(canvas, MAIN, "M3_KNIT_STRUCTURE_NK25.jpg")


def slip_on_panel():
    canvas = Image.new("RGB", (W, H), (247, 249, 250))
    header(canvas, "PRODUCT IDENTITY", "Slip-On Sock-Collar Construction", "No laces — keep title, images and SKU facts aligned")
    img = source("15.jpg")
    paste_cover(canvas, img, (0, 166, 650, 900))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((650, 166, 1000, 900), fill="white")
    for y, title, body in ((280, "SLIP-ON", "No lace closure"), (485, "SOCK COLLAR", "Knit opening"), (690, "LOW TOP", "Actual side profile")):
        draw.rounded_rectangle((688, y, 958, y + 140), radius=22, fill=(240, 246, 248), outline=(195, 214, 220), width=2)
        draw.text((716, y + 25), title, fill=(19, 30, 42), font=fitted(draw, title, 215, 27, True))
        draw.text((716, y + 78), body, fill=(76, 91, 106), font=fitted(draw, body, 215, 21))
    footer(canvas, "VISIBLE STRUCTURE ONLY", "NK25")
    save(canvas, MAIN, "M4_SLIP_ON_NK25.jpg")


def size_order_panel():
    canvas = Image.new("RGB", (W, H), (246, 249, 251))
    header(canvas, "B2B ORDER INPUT", "EU Size Range 36–45", "Launch colors: Black and Grey; reconfirm availability before order")
    paste_cover(canvas, source("23.jpg"), (0, 166, 520, 900))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((520, 166, 1000, 900), fill="white")
    draw.text((580, 235), "AVAILABLE SIZES", fill=(19, 30, 42), font=font(29, True))
    for idx, size in enumerate(range(36, 46)):
        col, row = idx % 2, idx // 2
        x, y = 585 + col * 175, 315 + row * 93
        draw.rounded_rectangle((x, y, x + 128, y + 58), radius=16, fill=(232, 242, 246), outline=(157, 191, 201), width=2)
        label = str(size)
        fnt = font(27, True)
        tw = draw.textbbox((0, 0), label, font=fnt)[2]
        draw.text((x + (128 - tw) / 2, y + 13), label, fill=(25, 77, 91), font=fnt)
    draw.text((585, 810), "Confirm quantity + size ratio", fill=(76, 91, 106), font=font(21))
    footer(canvas, "20 COLOR–SIZE COMBINATIONS", "2 COLORS")
    save(canvas, DETAIL, "D4_SIZE_ORDER_NK25.jpg")


def factory_panel():
    canvas = Image.new("RGB", (W, H), (245, 248, 247))
    header(canvas, "SUPPLIER PROOF", "Beiqiang Factory and Order Support", "Company-level evidence; NK25 is an external sourcing route")
    files = [
        ("C1_real_factory_identity.jpg", (45, 45, 1155, 805), "SUPPLIER IDENTITY"),
        ("C3_real_production_organization.jpg", (55, 230, 755, 1050), "PRODUCTION ORGANIZATION"),
        ("C4_real_quality_checkpoints.jpg", (40, 225, 400, 915), "QUALITY CHECKPOINTS"),
    ]
    draw = ImageDraw.Draw(canvas)
    for idx, (name, crop, label) in enumerate(files):
        img = Image.open(COMPANY / name).convert("RGB").crop(crop)
        x0 = 25 + idx * 325
        paste_cover(canvas, img, (x0, 190, x0 + 300, 800))
        draw.rounded_rectangle((x0, 820, x0 + 300, 875), radius=17, fill=(18, 28, 42))
        fnt = fitted(draw, label, 268, 19, True)
        tw = draw.textbbox((0, 0), label, font=fnt)[2]
        draw.text((x0 + (300 - tw) / 2, 838), label, fill="white", font=fnt)
    footer(canvas, "REAL COMPANY EVIDENCE", "QUANZHOU, CHINA")
    save(canvas, MAIN, "M5_FACTORY_NK25.jpg")


def packaging_panel():
    canvas = Image.new("RGB", (W, H), (241, 247, 249))
    header(canvas, "PACKAGING OPTIONS", "Confirm Packing Before Quotation", "Options are discussed per order and are not automatically included")
    draw = ImageDraw.Draw(canvas)
    cards = [
        (45, 215, 315, 735, "POLYBAG", "Individual bag option"),
        (365, 215, 635, 735, "SHOE BOX", "Box option"),
        (685, 215, 955, 735, "OUTER CARTON", "Order handoff"),
    ]
    for x0, y0, x1, y1, title, body in cards:
        draw.rounded_rectangle((x0, y0, x1, y1), radius=25, fill="white", outline=(197, 212, 220), width=3)
        if title == "POLYBAG":
            draw.rounded_rectangle((x0 + 58, y0 + 70, x1 - 58, y0 + 285), radius=20, outline=(31, 124, 145), width=7)
            draw.line((x0 + 75, y0 + 105, x1 - 75, y0 + 105), fill=(31, 124, 145), width=5)
        elif title == "SHOE BOX":
            draw.rectangle((x0 + 45, y0 + 115, x1 - 45, y0 + 275), outline=(31, 124, 145), width=7)
            draw.line((x0 + 45, y0 + 155, x1 - 45, y0 + 155), fill=(31, 124, 145), width=5)
        else:
            draw.rectangle((x0 + 42, y0 + 95, x1 - 42, y0 + 295), outline=(31, 124, 145), width=7)
            draw.line((x0 + 42, y0 + 150, x1 - 42, y0 + 150), fill=(31, 124, 145), width=5)
            draw.line(((x0 + x1) // 2, y0 + 95, (x0 + x1) // 2, y0 + 295), fill=(31, 124, 145), width=5)
        fnt = fitted(draw, title, x1 - x0 - 40, 27, True)
        tw = draw.textbbox((0, 0), title, font=fnt)[2]
        draw.text((x0 + (x1 - x0 - tw) / 2, y0 + 340), title, fill=(19, 30, 42), font=fnt)
        body_font = fitted(draw, body, x1 - x0 - 38, 21)
        bw = draw.textbbox((0, 0), body, font=body_font)[2]
        draw.text((x0 + (x1 - x0 - bw) / 2, y0 + 395), body, fill=(76, 91, 106), font=body_font)
    draw.rounded_rectangle((150, 785, 850, 865), radius=24, fill=(18, 28, 42))
    note = "CONFIRM QUANTITY • LABEL • MARK • DESTINATION"
    nf = fitted(draw, note, 640, 23, True)
    nw = draw.textbbox((0, 0), note, font=nf)[2]
    draw.text(((W - nw) / 2, 812), note, fill="white", font=nf)
    footer(canvas, "PACKING CONFIRMED PER ORDER", "B2B")
    save(canvas, MAIN, "M6_PACKAGING_NK25.jpg")


def detail_overview():
    canvas = Image.new("RGB", (W, H), "white")
    header(canvas, "PRODUCT OVERVIEW", "NK25 Knit Slip-On Sock Sneaker", "Actual Black and Grey source photography")
    paste_cover(canvas, source("13.jpg"), (0, 166, 500, 900))
    paste_cover(canvas, source("25.jpg"), (500, 166, 1000, 900))
    footer(canvas, "BLACK", "GREY")
    save(canvas, DETAIL, "D1_OVERVIEW_NK25.jpg")


def detail_angles():
    for color, left, right, name in (
        ("BLACK", "14.jpg", "15.jpg", "D2_BLACK_ANGLES_NK25.jpg"),
        ("GREY", "22.jpg", "24.jpg", "D3_GREY_ANGLES_NK25.jpg"),
    ):
        canvas = Image.new("RGB", (W, H), "white")
        header(canvas, "MULTI-ANGLE VIEW", f"{color.title()} Color Product View", "Actual source-page photography")
        paste_cover(canvas, source(left), (0, 166, 500, 900))
        paste_cover(canvas, source(right), (500, 166, 1000, 900))
        footer(canvas, "SIDE / HEEL VIEW", "ON-FOOT VIEW")
        save(canvas, DETAIL, name)


def sku_images():
    for color in ("black", "grey"):
        canvas = Image.new("RGB", (1000, 1000), "white")
        paste_contain(canvas, clean_shoe_crop(color), (80, 80, 920, 920), "white")
        save(canvas, MAIN, f"SKU_{color.upper()}_NK25.jpg")


def contact_sheet():
    files = sorted(list(MAIN.glob("*.jpg")) + list(DETAIL.glob("*.jpg")))
    cols = 3
    rows = (len(files) + cols - 1) // cols
    sheet = Image.new("RGB", (1140, rows * 420), (225, 231, 236))
    for idx, path in enumerate(files):
        img = Image.open(path).convert("RGB")
        img.thumbnail((360, 360), Image.Resampling.LANCZOS)
        tile = Image.new("RGB", (380, 420), "white")
        tile.paste(img, ((380 - img.width) // 2, 0))
        draw = ImageDraw.Draw(tile)
        label = path.name
        draw.text((16, 370), label, fill=(20, 30, 43), font=fitted(draw, label, 348, 19, True))
        sheet.paste(tile, ((idx % cols) * 380, (idx // cols) * 420))
    review = PROJECT / "04_审核" / "HR011_NK25"
    review.mkdir(parents=True, exist_ok=True)
    sheet.save(review / "HR011_NK25_gallery_contact.jpg", "JPEG", quality=92, optimize=True)


def main():
    for stale in (
        MAIN / "M5_SIZE_ORDER_NK25.jpg",
        MAIN / "M6_FACTORY_NK25.jpg",
        DETAIL / "D4_PACKAGING_NK25.jpg",
    ):
        if stale.exists():
            stale.unlink()
    hero("grey", "B2B WHOLESALE", "A_M1_NK25.jpg")
    hero("black", "B2B WHOLESALE", "B_M1_NK25.jpg")
    split_hero()
    colors_panel()
    knit_panel()
    slip_on_panel()
    size_order_panel()
    factory_panel()
    detail_overview()
    detail_angles()
    packaging_panel()
    sku_images()
    contact_sheet()


if __name__ == "__main__":
    main()
