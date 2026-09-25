"""Build a deterministic, source-faithful HR005/1882 B2B gallery."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
SRC = ROOT / "99_临时区" / "HR005_1882" / "00_候选页面素材"
OUT = ROOT / "99_临时区" / "HR005_1882" / "02_确定性排版候选"
SKU_OUT = ROOT / "99_临时区" / "HR005_1882" / "03_SKU上传候选"
COMPANY = ROOT / "02_Alibaba运营" / "06_图片与检查记录" / "公司图复用模板_v4_2026-09-21"
FONT = Path(r"C:\Windows\Fonts\arial.ttf")
BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")
W = H = 1000
GRAY_PAIR = "173ae140339b159a.jpg!bac"
BLUE_PAIR = "52edb5bb33f256b5.jpg!bac"  # evidence only; not used in launch gallery
BLACK_WEAR = "565647ff746cc4d2.jpg!bac"
GRAY_WEAR = "f4cea44e4c291e91.jpg!bac"


def font(size, bold=False):
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


def resolved(spec):
    if isinstance(spec, tuple):
        name, box = spec
        return source(name).crop(box)
    return source(spec)


def paste_cover(canvas, img, box, centering=(0.5, 0.5)):
    x0, y0, x1, y1 = box
    tile = ImageOps.fit(img, (x1 - x0, y1 - y0), method=Image.Resampling.LANCZOS, centering=centering)
    canvas.paste(tile, (x0, y0))


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
    draw.text((50, 928), left, fill="white", font=fitted(draw, left, 580, 28, True))
    if right:
        fnt = fitted(draw, right, 320, 26, True)
        width = draw.textbbox((0, 0), right, font=fnt)[2]
        draw.text((950 - width, 930), right, fill=(118, 211, 233), font=fnt)


def save(canvas, name):
    OUT.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT / name, "JPEG", quality=95, optimize=True)


def hero(name, badge, output_name):
    canvas = ImageOps.fit(source(name), (W, H), method=Image.Resampling.LANCZOS)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle((42, 42, 345, 104), radius=24, fill=(18, 28, 42, 230))
    draw.text((70, 59), badge, fill="white", font=fitted(draw, badge, 250, 25, True))
    draw.rounded_rectangle((722, 910, 958, 966), radius=20, fill=(255, 255, 255, 232))
    draw.text((756, 926), "MODEL 1882", fill=(18, 28, 42), font=font(22, True))
    save(Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB"), output_name)


def split_panel(left_name, right_name, kicker, title, subtitle, left_label, right_label, output_name):
    canvas = Image.new("RGB", (W, H), "white")
    paste_cover(canvas, resolved(left_name), (0, 164, 500, 900))
    paste_cover(canvas, resolved(right_name), (500, 164, 1000, 900))
    header(canvas, kicker, title, subtitle)
    footer(canvas, left_label, right_label)
    save(canvas, output_name)


def evidence_panel(name, crop_box, kicker, title, rows, output_name):
    canvas = Image.new("RGB", (W, H), (244, 247, 249))
    img = source(name).crop(crop_box)
    paste_cover(canvas, img, (0, 164, 620, 900))
    header(canvas, kicker, title, "Visible construction only — no performance claim")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((620, 164, 1000, 900), fill=(232, 239, 244))
    y = 250
    for heading, body in rows:
        draw.rounded_rectangle((660, y, 960, y + 142), radius=22, fill="white", outline=(206, 216, 226), width=2)
        draw.text((690, y + 27), heading, fill=(18, 28, 42), font=fitted(draw, heading, 240, 29, True))
        draw.text((690, y + 78), body, fill=(75, 91, 108), font=fitted(draw, body, 240, 22))
        y += 180
    footer(canvas, "ACTUAL PRODUCT DETAIL", "MODEL 1882")
    save(canvas, output_name)


def size_panel():
    canvas = Image.new("RGB", (W, H), (246, 249, 251))
    paste_cover(canvas, source(GRAY_WEAR), (0, 164, 570, 900), centering=(0.62, 0.5))
    header(canvas, "B2B SKU RANGE", "EU Size Range 39–44", "Gray and black launch colors; reconfirm supply before order")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((570, 164, 1000, 900), fill="white")
    draw.text((625, 235), "AVAILABLE SIZES", fill=(20, 30, 43), font=font(29, True))
    for idx, size in enumerate(range(39, 45)):
        col, row = idx % 3, idx // 3
        x, y = 620 + col * 120, 340 + row * 125
        draw.rounded_rectangle((x, y, x + 92, y + 66), radius=17, fill=(231, 241, 245), outline=(153, 190, 201), width=2)
        fnt = font(28, True)
        label = str(size)
        tw = draw.textbbox((0, 0), label, font=fnt)[2]
        draw.text((x + (92 - tw) / 2, y + 15), label, fill=(25, 77, 91), font=fnt)
    draw.text((625, 655), "Launch colors", fill=(20, 30, 43), font=font(27, True))
    draw.text((625, 710), "Gray / Black", fill=(34, 133, 160), font=font(29, True))
    draw.text((625, 780), "Confirm quantity and size mix", fill=(87, 101, 116), font=font(19))
    footer(canvas, "12 COLOR–SIZE COMBINATIONS", "2 COLORS")
    save(canvas, "M5_SIZE_1882.jpg")


def company_collage():
    canvas = Image.new("RGB", (W, H), (246, 248, 247))
    header(canvas, "B2B SUPPLIER VIEW", "Beiqiang Footwear Factory", "Company evidence; external supply route is confirmed per order")
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
    save(canvas, "M6_FACTORY_1882.jpg")


def order_panel():
    canvas = Image.new("RGB", (W, H), (246, 249, 251))
    paste_cover(canvas, source(BLACK_WEAR), (0, 164, 570, 900), centering=(0.38, 0.5))
    header(canvas, "ORDER PREPARATION", "Confirm Order Inputs", "Current terms must be reconfirmed before purchase")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((570, 164, 1000, 900), fill="white")
    draw.text((630, 235), "MODEL 1882", fill=(18, 28, 42), font=font(46, True))
    draw.text((630, 310), "EU 39–44", fill=(34, 133, 160), font=font(32, True))
    draw.line((630, 380, 930, 380), fill=(210, 220, 229), width=3)
    draw.text((630, 430), "Inputs to confirm", fill=(18, 28, 42), font=font(27, True))
    for idx, text in enumerate(["Quantity", "Color / size mix", "Packing", "Delivery terms"]):
        y = 505 + idx * 72
        draw.ellipse((632, y + 8, 648, y + 24), fill=(34, 133, 160))
        draw.text((670, y), text, fill=(76, 90, 107), font=font(25))
    footer(canvas, "SOURCE-PAGE PRODUCT VIEW", "CONFIRM BEFORE ORDER")
    save(canvas, "D4_ORDER_1882.jpg")


def black_detail_panel():
    canvas = Image.new("RGB", (W, H), "white")
    black = source(BLACK_WEAR)
    # Left is a tight material/opening crop; right preserves the complete on-foot context.
    paste_cover(canvas, black.crop((55, 335, 690, 745)), (0, 164, 500, 900), centering=(0.42, 0.52))
    paste_cover(canvas, black, (500, 164, 1000, 900), centering=(0.58, 0.5))
    header(canvas, "BLACK PRODUCT VIEW", "Upper Texture and Wearing View", "Distinct detail crop and complete on-foot view")
    footer(canvas, "TEXTURE / OPENING", "ON-FOOT VIEW")
    save(canvas, "D3_BLACK_1882.jpg")


def sku_candidates():
    SKU_OUT.mkdir(parents=True, exist_ok=True)
    for name, output in [(GRAY_WEAR, "SKU_GREY_1882.jpg"), (BLACK_WEAR, "SKU_BLACK_1882.jpg")]:
        ImageOps.fit(source(name), (1000, 1000), method=Image.Resampling.LANCZOS).save(
            SKU_OUT / output, "JPEG", quality=95, optimize=True
        )


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
    hero(GRAY_WEAR, "B2B WHOLESALE", "M1_HERO_1882.jpg")
    hero(BLACK_WEAR, "B2B WHOLESALE", "B_M1_HERO_1882.jpg")
    split_panel((GRAY_PAIR, (0, 0, 800, 330)), BLACK_WEAR, "BULK SOURCING", "Gray and Black Mesh Mules", "Actual 1882 source photography", "GRAY", "BLACK", "C_M1_HERO_1882.jpg")
    split_panel(GRAY_WEAR, BLACK_WEAR, "B2B PRODUCT VIEW", "Two Source-Verified Colors", "Actual product; launch range only", "GRAY", "BLACK", "M2_COLORS_1882.jpg")
    evidence_panel(GRAY_PAIR, (25, 20, 790, 325), "UPPER VIEW", "Open Mesh Texture", [("MESH VIEW", "Visible upper texture"), ("SLIP-ON", "No lace closure")], "M3_MESH_1882.jpg")
    evidence_panel(BLACK_WEAR, (40, 210, 780, 780), "BACKLESS VIEW", "Mule Opening and Sole Shape", [("OPEN HEEL", "Visible backless structure"), ("SOLE VIEW", "No performance claim")], "M4_BACKLESS_1882.jpg")
    size_panel()
    company_collage()
    split_panel(GRAY_WEAR, BLACK_WEAR, "PRODUCT OVERVIEW", "1882 Backless Mesh Mule Shoes", "Actual gray and black source photography", "GRAY", "BLACK", "D1_OVERVIEW_1882.jpg")
    split_panel((GRAY_PAIR, (0, 470, 800, 800)), GRAY_WEAR, "GRAY PRODUCT VIEW", "Gray Pair and On-Foot View", "Two distinct source roles", "PAIR VIEW", "ON-FOOT VIEW", "D2_GRAY_1882.jpg")
    black_detail_panel()
    order_panel()
    sku_candidates()
    contact_sheet()


if __name__ == "__main__":
    main()
