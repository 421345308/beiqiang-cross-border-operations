from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
SRC = ROOT / "99_临时区" / "HR002_S6077" / "01_标准化审图副本"
OUT = ROOT / "99_临时区" / "HR002_S6077" / "03_确定性排版候选"
COMPANY = ROOT / "02_Alibaba运营" / "06_图片与检查记录" / "公司图复用模板_v4_2026-09-21"
FONT = Path(r"C:\Windows\Fonts\arial.ttf")
BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")
W = H = 1000


def f(size: int, bold: bool = False):
    return ImageFont.truetype(str(BOLD if bold else FONT), size)


def fit_text(draw, text, max_w, start, bold=False):
    size = start
    while size > 18:
        font = f(size, bold)
        if draw.textbbox((0, 0), text, font=font)[2] <= max_w:
            return font
        size -= 2
    return f(size, bold)


def open_rgb(name):
    return Image.open(SRC / name).convert("RGB")


def cover(img, box):
    x0, y0, x1, y1 = box
    tile = ImageOps.fit(img, (x1 - x0, y1 - y0), method=Image.Resampling.LANCZOS)
    return tile, (x0, y0)


def contain(img, box, bg=(245, 247, 249)):
    x0, y0, x1, y1 = box
    tile = ImageOps.contain(img, (x1 - x0, y1 - y0), method=Image.Resampling.LANCZOS)
    panel = Image.new("RGB", (x1 - x0, y1 - y0), bg)
    panel.paste(tile, ((panel.width - tile.width) // 2, (panel.height - tile.height) // 2))
    return panel, (x0, y0)


def add_header(canvas, kicker, title, subtitle=None, dark=False):
    draw = ImageDraw.Draw(canvas)
    panel = (18, 28, 42) if dark else (255, 255, 255)
    primary = (255, 255, 255) if dark else (20, 30, 43)
    secondary = (205, 218, 231) if dark else (77, 91, 108)
    draw.rectangle((0, 0, W, 164 if subtitle else 132), fill=panel)
    draw.text((54, 27), kicker.upper(), fill=(34, 133, 160), font=f(22, True))
    draw.text((54, 58), title, fill=primary, font=fit_text(draw, title, 890, 48, True))
    if subtitle:
        draw.text((56, 118), subtitle, fill=secondary, font=fit_text(draw, subtitle, 880, 25))


def footer(canvas, left, right=None):
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 900, W, H), fill=(18, 28, 42))
    draw.text((50, 928), left, fill="white", font=fit_text(draw, left, 570, 30, True))
    if right:
        font = fit_text(draw, right, 330, 27, True)
        width = draw.textbbox((0, 0), right, font=font)[2]
        draw.text((950 - width, 930), right, fill=(118, 211, 233), font=font)


def save(img, name):
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / name, "JPEG", quality=95, optimize=True)


def m1_real_hero():
    # Preserve the source photograph as the factual hero; only add small B2B labels.
    source = open_rgb("06_5e3752_gallery.jpg")
    canvas = source.crop((40, 80, 760, 800)).resize((W, H), Image.Resampling.LANCZOS)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle((42, 42, 322, 104), radius=24, fill=(18, 28, 42, 230))
    draw.text((70, 59), "B2B WHOLESALE", fill="white", font=f(25, True))
    draw.rounded_rectangle((692, 910, 958, 966), radius=20, fill=(255, 255, 255, 232))
    draw.text((724, 926), "MODEL S6077", fill=(18, 28, 42), font=f(22, True))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    save(canvas, "M1_HERO_S6077.jpg")


def variant_real_hero(source_name, crop_box, badge, output_name):
    source = open_rgb(source_name)
    canvas = source.crop(crop_box).resize((W, H), Image.Resampling.LANCZOS)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle((42, 42, 342, 104), radius=24, fill=(18, 28, 42, 230))
    draw.text((70, 59), badge, fill="white", font=fit_text(draw, badge, 245, 25, True))
    draw.rounded_rectangle((692, 910, 958, 966), radius=20, fill=(255, 255, 255, 232))
    draw.text((724, 926), "MODEL S6077", fill=(18, 28, 42), font=f(22, True))
    save(Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB"), output_name)


def m2_colors():
    canvas = Image.new("RGB", (W, H), "white")
    img, pos = cover(open_rgb("04_4fe459_gallery.jpg"), (0, 164, 1000, 900))
    canvas.paste(img, pos)
    add_header(canvas, "B2B PRODUCT VIEW", "Two Color Options", "Actual S6077 source photography")
    footer(canvas, "BLACK  •  WHITE", "MODEL S6077")
    save(canvas, "M2_COLORS_S6077.jpg")


def split_proof(source, kicker, title, labels, name):
    canvas = Image.new("RGB", (W, H), (244, 247, 249))
    img, pos = contain(open_rgb(source), (0, 164, 620, 900), (240, 243, 246))
    canvas.paste(img, pos)
    add_header(canvas, kicker, title, "Visible construction only — no performance claim")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((620, 164, 1000, 900), fill=(232, 239, 244))
    y = 250
    for head, body in labels:
        draw.rounded_rectangle((660, y, 960, y + 135), radius=22, fill="white", outline=(206, 216, 226), width=2)
        draw.text((690, y + 25), head, fill=(18, 28, 42), font=fit_text(draw, head, 240, 29, True))
        draw.text((690, y + 72), body, fill=(75, 91, 108), font=fit_text(draw, body, 240, 22))
        y += 170
    footer(canvas, "ACTUAL PRODUCT DETAIL", "S6077")
    save(canvas, name)


def m5_size():
    canvas = Image.new("RGB", (W, H), (246, 249, 251))
    img, pos = cover(open_rgb("09_c89a93_gallery.jpg"), (0, 164, 570, 900))
    canvas.paste(img, pos)
    add_header(canvas, "B2B SKU RANGE", "EU Size Range 39–48", "Black and white source-page options")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((570, 164, 1000, 900), fill="white")
    draw.text((635, 230), "AVAILABLE SIZES", fill=(20, 30, 43), font=f(30, True))
    sizes = list(range(39, 49))
    for idx, size in enumerate(sizes):
        col = idx % 2
        row = idx // 2
        x = 635 + col * 150
        y = 300 + row * 100
        draw.rounded_rectangle((x, y, x + 112, y + 62), radius=18, fill=(231, 241, 245), outline=(153, 190, 201), width=2)
        label = str(size)
        font = f(29, True)
        tw = draw.textbbox((0, 0), label, font=font)[2]
        draw.text((x + (112 - tw) / 2, y + 14), label, fill=(25, 77, 91), font=font)
    draw.text((635, 825), "Reconfirm stock before order", fill=(87, 101, 116), font=f(21))
    footer(canvas, "20 COLOR–SIZE COMBINATIONS", "2 COLORS")
    save(canvas, "M5_SIZE_S6077.jpg")


def m6_factory_collage():
    canvas = Image.new("RGB", (W, H), (246, 248, 247))
    add_header(
        canvas,
        "B2B SUPPLIER VIEW",
        "Beiqiang Footwear Factory",
        "Company-level evidence; product-specific route confirmed per order",
    )
    sources = [
        ("C1_real_factory_identity.jpg", (45, 45, 1155, 805), "SUPPLIER IDENTITY"),
        ("C3_real_production_organization.jpg", (55, 230, 755, 1050), "WORKSHOP"),
        ("C4_real_quality_checkpoints.jpg", (40, 225, 400, 915), "ORDER CHECKS"),
    ]
    draw = ImageDraw.Draw(canvas)
    for idx, (filename, crop_box, label) in enumerate(sources):
        source = Image.open(COMPANY / filename).convert("RGB").crop(crop_box)
        x0 = 28 + idx * 324
        x1 = x0 + 296
        photo = ImageOps.fit(source, (296, 610), method=Image.Resampling.LANCZOS)
        canvas.paste(photo, (x0, 198))
        draw.rounded_rectangle((x0, 830, x1, 884), radius=18, fill=(18, 28, 42))
        font = fit_text(draw, label, 260, 20, True)
        tw = draw.textbbox((0, 0), label, font=font)[2]
        draw.text((x0 + (296 - tw) / 2, 847), label, fill="white", font=font)
    footer(canvas, "REAL COMPANY EVIDENCE", "QUANZHOU, CHINA")
    save(canvas, "M6_FACTORY_PROCESS.jpg")


def d1_overview():
    canvas = Image.new("RGB", (W, H), "white")
    left, p1 = cover(open_rgb("06_5e3752_gallery.jpg"), (0, 164, 500, 900))
    right, p2 = cover(open_rgb("05_ae58e1_gallery.jpg"), (500, 164, 1000, 900))
    canvas.paste(left, p1)
    canvas.paste(right, p2)
    add_header(canvas, "PRODUCT OVERVIEW", "S6077 Retro Mesh Lace-Up Shoes", "Actual black and white source photography")
    footer(canvas, "BLACK", "WHITE")
    save(canvas, "D1_OVERVIEW_S6077.jpg")


def d2_colors():
    canvas = Image.new("RGB", (W, H), "white")
    img, pos = cover(open_rgb("08_a967ff_gallery.jpg"), (0, 164, 1000, 900))
    canvas.paste(img, pos)
    add_header(canvas, "WHITE COLOR DETAIL", "Front and Side View", "Actual S6077 source photography")
    footer(canvas, "WHITE", "MULTI-ANGLE VIEW")
    save(canvas, "D2_COLORS_S6077.jpg")


def d4_outsole_size():
    canvas = Image.new("RGB", (W, H), (246, 249, 251))
    img, pos = contain(open_rgb("02_c9f464_white_view.jpg"), (0, 164, 570, 900), (240, 243, 246))
    canvas.paste(img, pos)
    add_header(canvas, "ORDER PREPARATION", "Product Range and Order Inputs", "Confirm current terms before purchase")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((570, 164, 1000, 900), fill="white")
    draw.text((630, 240), "EU 39–48", fill=(18, 28, 42), font=f(52, True))
    draw.text((630, 320), "Black / White", fill=(34, 133, 160), font=f(31, True))
    draw.line((630, 390, 930, 390), fill=(210, 220, 229), width=3)
    draw.text((630, 440), "Order inputs to confirm", fill=(18, 28, 42), font=f(27, True))
    for idx, text in enumerate(["Quantity", "Size mix", "Packing", "Delivery terms"]):
        y = 510 + idx * 72
        draw.ellipse((632, y + 8, 648, y + 24), fill=(34, 133, 160))
        draw.text((670, y), text, fill=(76, 90, 107), font=f(25))
    footer(canvas, "WHITE PRODUCT VIEW", "CONFIRM BEFORE ORDER")
    save(canvas, "D4_OUTSOLE_SIZE_S6077.jpg")


def make_contact_sheet():
    files = sorted(path for path in OUT.glob("*.jpg") if path.name != "contact_sheet.jpg")
    thumbs = []
    for path in files:
        img = Image.open(path).convert("RGB")
        img.thumbnail((360, 360), Image.Resampling.LANCZOS)
        tile = Image.new("RGB", (380, 420), "white")
        tile.paste(img, ((380 - img.width) // 2, 0))
        draw = ImageDraw.Draw(tile)
        draw.text((16, 370), path.name, fill=(20, 30, 43), font=fit_text(draw, path.name, 348, 20, True))
        thumbs.append(tile)
    cols = 3
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 380, rows * 420), (225, 231, 236))
    for idx, tile in enumerate(thumbs):
        sheet.paste(tile, ((idx % cols) * 380, (idx // cols) * 420))
    sheet.save(OUT / "contact_sheet.jpg", "JPEG", quality=92, optimize=True)


def main():
    m1_real_hero()
    variant_real_hero("05_ae58e1_gallery.jpg", (40, 40, 760, 760), "B2B WHOLESALE", "B_M1_HERO_S6077.jpg")
    variant_real_hero("04_4fe459_gallery.jpg", (20, 20, 780, 780), "BULK SOURCING", "C_M1_HERO_S6077.jpg")
    m2_colors()
    split_proof(
        "13_665298_detail.webp",
        "UPPER & CLOSURE",
        "Mesh Upper and Lace-Up View",
        [("MESH VIEW", "Visible upper texture"), ("LACE-UP", "Adjustable closure")],
        "M3_MESH_LACE_S6077.jpg",
    )
    split_proof(
        "12_5419b5_detail.webp",
        "OUTSOLE DETAIL",
        "Tread Pattern View",
        [("OUTSOLE VIEW", "Actual source detail"), ("TREAD DETAIL", "Visible pattern only")],
        "M4_OUTSOLE_S6077.jpg",
    )
    m5_size()
    m6_factory_collage()
    d1_overview()
    d2_colors()
    split_proof(
        "07_49cf6a_gallery.jpg",
        "BLACK COLOR DETAIL",
        "Side Profile Construction",
        [("PANEL VIEW", "Visible upper structure"), ("SOLE PROFILE", "Layered side view")],
        "D3_MESH_LACE_S6077.jpg",
    )
    d4_outsole_size()
    make_contact_sheet()


if __name__ == "__main__":
    main()
