from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
SRC = ROOT / "99_临时区" / "HR003_9922" / "02_商品详情原图"
OUT = ROOT / "99_临时区" / "HR003_9922" / "04_确定性排版候选"
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


def paste_contain(canvas, img, box, bg=(245, 247, 249)):
    x0, y0, x1, y1 = box
    panel = Image.new("RGB", (x1 - x0, y1 - y0), bg)
    tile = ImageOps.contain(img, panel.size, method=Image.Resampling.LANCZOS)
    panel.paste(tile, ((panel.width - tile.width) // 2, (panel.height - tile.height) // 2))
    canvas.paste(panel, (x0, y0))


def header(canvas, kicker, title, subtitle=None):
    draw = ImageDraw.Draw(canvas)
    height = 164 if subtitle else 132
    draw.rectangle((0, 0, W, height), fill="white")
    draw.text((54, 27), kicker.upper(), fill=(34, 133, 160), font=font(22, True))
    draw.text((54, 58), title, fill=(20, 30, 43), font=fitted(draw, title, 890, 48, True))
    if subtitle:
        draw.text((56, 118), subtitle, fill=(77, 91, 108), font=fitted(draw, subtitle, 880, 25))


def footer(canvas, left, right=None):
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 900, W, H), fill=(18, 28, 42))
    draw.text((50, 928), left, fill="white", font=fitted(draw, left, 570, 30, True))
    if right:
        fnt = fitted(draw, right, 330, 27, True)
        width = draw.textbbox((0, 0), right, font=fnt)[2]
        draw.text((950 - width, 930), right, fill=(118, 211, 233), font=fnt)


def save(canvas, name):
    OUT.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT / name, "JPEG", quality=95, optimize=True)


def hero(source_name, badge, output_name):
    img = source(source_name)
    canvas = ImageOps.fit(img, (W, H), method=Image.Resampling.LANCZOS)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle((42, 42, 345, 104), radius=24, fill=(18, 28, 42, 230))
    draw.text((70, 59), badge, fill="white", font=fitted(draw, badge, 250, 25, True))
    draw.rounded_rectangle((720, 910, 958, 966), radius=20, fill=(255, 255, 255, 232))
    draw.text((755, 926), "MODEL 9922", fill=(18, 28, 42), font=font(22, True))
    save(Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB"), output_name)


def two_color_hero():
    canvas = Image.new("RGB", (W, H), "white")
    paste_cover(canvas, source("13_p7otcyss1hk5hb06kiggudtnydj18ugw.jpg"), (0, 0, 500, 1000))
    paste_cover(canvas, source("19_5zdln57nnfpdlsxauv9gofvu17jifxic.jpg"), (500, 0, 1000, 1000))
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle((42, 42, 330, 104), radius=24, fill=(18, 28, 42, 230))
    draw.text((70, 59), "BULK SOURCING", fill="white", font=font(25, True))
    draw.rounded_rectangle((720, 910, 958, 966), radius=20, fill=(255, 255, 255, 232))
    draw.text((755, 926), "MODEL 9922", fill=(18, 28, 42), font=font(22, True))
    save(Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB"), "C_M1_HERO_9922.jpg")


def two_color_panel(output_name="M2_COLORS_9922.jpg"):
    canvas = Image.new("RGB", (W, H), "white")
    paste_contain(canvas, source("03_l644ai4bmtbaujz38cmvyu7nyxcoyauw.jpg"), (0, 164, 1000, 900), "white")
    header(canvas, "B2B PRODUCT VIEW", "Two Verified Color Options", "Actual 9922 source-page photography")
    footer(canvas, "WHITE  •  BLACK", "MODEL 9922")
    save(canvas, output_name)


def evidence_panel(source_name, kicker, title, rows, output_name):
    canvas = Image.new("RGB", (W, H), (244, 247, 249))
    paste_contain(canvas, source(source_name), (0, 164, 620, 900))
    header(canvas, kicker, title, "Visible construction only — no performance claim")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((620, 164, 1000, 900), fill=(232, 239, 244))
    y = 255
    for heading, body in rows:
        draw.rounded_rectangle((660, y, 960, y + 135), radius=22, fill="white", outline=(206, 216, 226), width=2)
        draw.text((690, y + 25), heading, fill=(18, 28, 42), font=fitted(draw, heading, 240, 29, True))
        draw.text((690, y + 72), body, fill=(75, 91, 108), font=fitted(draw, body, 240, 22))
        y += 170
    footer(canvas, "ACTUAL PRODUCT DETAIL", "9922")
    save(canvas, output_name)


def size_panel():
    canvas = Image.new("RGB", (W, H), (246, 249, 251))
    paste_cover(canvas, source("14_0nmcoxdk3jduf372ln29zupwc1w8jpw1.jpg"), (0, 164, 570, 900))
    header(canvas, "B2B SKU RANGE", "EU Size Range 39–44", "White and black launch colors; reconfirm stock before order")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((570, 164, 1000, 900), fill="white")
    draw.text((635, 240), "AVAILABLE SIZES", fill=(20, 30, 43), font=font(30, True))
    for idx, size in enumerate(range(39, 45)):
        col, row = idx % 2, idx // 2
        x, y = 635 + col * 150, 330 + row * 120
        draw.rounded_rectangle((x, y, x + 112, y + 68), radius=18, fill=(231, 241, 245), outline=(153, 190, 201), width=2)
        label = str(size)
        fnt = font(30, True)
        tw = draw.textbbox((0, 0), label, font=fnt)[2]
        draw.text((x + (112 - tw) / 2, y + 15), label, fill=(25, 77, 91), font=fnt)
    draw.text((635, 735), "Colors", fill=(20, 30, 43), font=font(27, True))
    draw.text((635, 782), "White / Black", fill=(34, 133, 160), font=font(29, True))
    draw.text((635, 838), "Inventory confirmed per order", fill=(87, 101, 116), font=font(20))
    footer(canvas, "12 COLOR–SIZE COMBINATIONS", "2 COLORS")
    save(canvas, "M5_SIZE_9922.jpg")


def company_collage():
    canvas = Image.new("RGB", (W, H), (246, 248, 247))
    header(canvas, "B2B SUPPLIER VIEW", "Beiqiang Footwear Factory", "Company-level evidence; 9922 sourcing route confirmed per order")
    files = [
        ("C1_real_factory_identity.jpg", (45, 45, 1155, 805), "SUPPLIER IDENTITY"),
        ("C3_real_production_organization.jpg", (55, 230, 755, 1050), "WORKSHOP"),
        ("C4_real_quality_checkpoints.jpg", (40, 225, 400, 915), "ORDER CHECKS"),
    ]
    draw = ImageDraw.Draw(canvas)
    for idx, (name, crop, label) in enumerate(files):
        img = Image.open(COMPANY / name).convert("RGB").crop(crop)
        x0 = 28 + idx * 324
        canvas.paste(ImageOps.fit(img, (296, 610), method=Image.Resampling.LANCZOS), (x0, 198))
        draw.rounded_rectangle((x0, 830, x0 + 296, 884), radius=18, fill=(18, 28, 42))
        fnt = fitted(draw, label, 260, 20, True)
        tw = draw.textbbox((0, 0), label, font=fnt)[2]
        draw.text((x0 + (296 - tw) / 2, 847), label, fill="white", font=fnt)
    footer(canvas, "REAL COMPANY EVIDENCE", "QUANZHOU, CHINA")
    save(canvas, "M6_FACTORY_PROCESS.jpg")


def split_overview(left_name, right_name, title, subtitle, left_label, right_label, output_name):
    canvas = Image.new("RGB", (W, H), "white")
    paste_cover(canvas, source(left_name), (0, 164, 500, 900))
    paste_cover(canvas, source(right_name), (500, 164, 1000, 900))
    header(canvas, "PRODUCT OVERVIEW", title, subtitle)
    footer(canvas, left_label, right_label)
    save(canvas, output_name)


def order_panel():
    canvas = Image.new("RGB", (W, H), (246, 249, 251))
    paste_contain(canvas, source("20_lwz3shwnxbs9d8mqbxnmutx5suk3cxjw.jpg"), (0, 164, 570, 900))
    header(canvas, "ORDER PREPARATION", "Confirm Order Inputs", "Current terms must be reconfirmed before purchase")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((570, 164, 1000, 900), fill="white")
    draw.text((630, 240), "MODEL 9922", fill=(18, 28, 42), font=font(48, True))
    draw.text((630, 315), "EU 39–44", fill=(34, 133, 160), font=font(32, True))
    draw.line((630, 385, 930, 385), fill=(210, 220, 229), width=3)
    draw.text((630, 435), "Inputs to confirm", fill=(18, 28, 42), font=font(27, True))
    for idx, text in enumerate(["Quantity", "Color / size mix", "Packing", "Delivery terms"]):
        y = 510 + idx * 72
        draw.ellipse((632, y + 8, 648, y + 24), fill=(34, 133, 160))
        draw.text((670, y), text, fill=(76, 90, 107), font=font(25))
    footer(canvas, "SOURCE-PAGE PRODUCT VIEW", "CONFIRM BEFORE ORDER")
    save(canvas, "D4_ORDER_INPUTS_9922.jpg")


def contact_sheet():
    files = sorted(p for p in OUT.glob("*.jpg") if p.name != "contact_sheet.jpg")
    cols = 3
    rows = (len(files) + cols - 1) // cols
    sheet = Image.new("RGB", (1140, rows * 420), (225, 231, 236))
    for idx, path in enumerate(files):
        img = Image.open(path).convert("RGB")
        img.thumbnail((360, 360), Image.Resampling.LANCZOS)
        tile = Image.new("RGB", (380, 420), "white")
        tile.paste(img, ((380 - img.width) // 2, 0))
        draw = ImageDraw.Draw(tile)
        draw.text((16, 370), path.name, fill=(20, 30, 43), font=fitted(draw, path.name, 348, 20, True))
        sheet.paste(tile, ((idx % cols) * 380, (idx // cols) * 420))
    sheet.save(OUT / "contact_sheet.jpg", "JPEG", quality=92, optimize=True)


def main():
    hero("13_p7otcyss1hk5hb06kiggudtnydj18ugw.jpg", "B2B WHOLESALE", "M1_HERO_9922.jpg")
    hero("19_5zdln57nnfpdlsxauv9gofvu17jifxic.jpg", "B2B WHOLESALE", "B_M1_HERO_9922.jpg")
    two_color_hero()
    two_color_panel()
    evidence_panel(
        "12_umyf886pfv64iclvknonaj1ywqlw5y6c.jpg",
        "UPPER & CLOSURE",
        "Mesh Panels and Lace-Up View",
        [("MESH VIEW", "Visible upper texture"), ("LACE-UP", "Adjustable closure")],
        "M3_MESH_LACE_9922.jpg",
    )
    evidence_panel(
        "11_0t1r2mvgpqe6wc7z5rljrp41hss4v3vn.jpg",
        "SOLE PROFILE",
        "Chunky Thick-Sole Side View",
        [("SIDE PROFILE", "Actual source detail"), ("THICK SOLE", "Visible structure only")],
        "M4_THICK_SOLE_9922.jpg",
    )
    size_panel()
    company_collage()
    split_overview(
        "13_p7otcyss1hk5hb06kiggudtnydj18ugw.jpg",
        "19_5zdln57nnfpdlsxauv9gofvu17jifxic.jpg",
        "9922 Chunky Mesh Lace-Up Shoes",
        "Actual white and black source photography",
        "WHITE",
        "BLACK",
        "D1_OVERVIEW_9922.jpg",
    )
    split_overview(
        "10_lievfilfsyqycmqiulhx0o56pbc2f30e.jpg",
        "14_0nmcoxdk3jduf372ln29zupwc1w8jpw1.jpg",
        "White Color Multi-Angle View",
        "Source-page product photography",
        "PAIR VIEW",
        "ON-FOOT VIEW",
        "D2_WHITE_9922.jpg",
    )
    split_overview(
        "16_k5c8lnoutrpa7hpqmbeclrpqzqry014u.jpg",
        "17_qqvvc86fhmdtc0wohmh73beixpw77uax.jpg",
        "Black Color Multi-Angle View",
        "Source-page product photography",
        "PAIR VIEW",
        "ON-FOOT VIEW",
        "D3_BLACK_9922.jpg",
    )
    order_panel()
    contact_sheet()


if __name__ == "__main__":
    main()
