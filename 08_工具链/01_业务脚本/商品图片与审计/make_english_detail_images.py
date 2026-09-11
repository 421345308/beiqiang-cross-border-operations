from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import shutil


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
RAW_ROOT = ROOT / "01_原始数据包"
UPLOAD_ROOT = ROOT / "01_产品资产" / "02_可发布素材"
FONT = r"C:\Windows\Fonts\arial.ttf"
BOLD = r"C:\Windows\Fonts\arialbd.ttf"


def first_existing(*paths):
    for path in paths:
        if path.exists():
            return path
    return paths[0]


def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)


def fit_text(draw, text, max_width, start_size, bold=False):
    size = start_size
    while size > 18:
        f = font(size, bold)
        if draw.textbbox((0, 0), text, font=f)[2] <= max_width:
            return f
        size -= 2
    return font(size, bold)


def paste_product(canvas, src_path, box, shadow=True):
    product = Image.open(src_path).convert("RGBA")
    bbox = product.getbbox()
    if bbox:
        product = product.crop(bbox)
    product.thumbnail((box[2] - box[0], box[3] - box[1]), Image.LANCZOS)
    x = box[0] + (box[2] - box[0] - product.width) // 2
    y = box[1] + (box[3] - box[1] - product.height) // 2

    if shadow:
        alpha = product.split()[-1]
        shadow_img = Image.new("RGBA", product.size, (0, 0, 0, 100))
        shadow_img.putalpha(alpha.filter(ImageFilter.GaussianBlur(18)))
        canvas.alpha_composite(shadow_img, (x + 12, y + 28))

    canvas.alpha_composite(product, (x, y))


def add_header(draw, title, subtitle=None):
    draw.text((80, 72), title, fill=(20, 31, 45), font=fit_text(draw, title, 1040, 62, True))
    if subtitle:
        draw.text((82, 154), subtitle, fill=(85, 98, 115), font=fit_text(draw, subtitle, 980, 34))


def add_pill(draw, xy, text, fill=(37, 99, 235)):
    x, y = xy
    f = fit_text(draw, text, 360, 30, True)
    w = draw.textbbox((0, 0), text, font=f)[2] + 42
    h = 58
    draw.rounded_rectangle((x, y, x + w, y + h), radius=29, fill=fill)
    draw.text((x + 22, y + 13), text, fill="white", font=f)


def add_feature_card(draw, xy, title, text, accent=(37, 99, 235)):
    x, y = xy
    draw.rounded_rectangle((x, y, x + 440, y + 148), radius=24, fill=(255, 255, 255), outline=(226, 232, 240), width=2)
    draw.ellipse((x + 28, y + 34, x + 78, y + 84), fill=accent)
    draw.line((x + 43, y + 59, x + 55, y + 71, x + 68, y + 48), fill="white", width=5)
    draw.text((x + 98, y + 30), title, fill=(20, 31, 45), font=font(30, True))
    draw.text((x + 98, y + 78), text, fill=(91, 104, 121), font=font(24))


def bg():
    canvas = Image.new("RGBA", (1200, 1200), (246, 249, 252, 255))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((52, 52, 1148, 1148), radius=36, fill=(255, 255, 255))
    draw.rectangle((52, 52, 1148, 250), fill=(237, 244, 252))
    return canvas, draw


def save(canvas, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out, "JPEG", quality=94, optimize=True)


def hero(out, product, title, subtitle, colors):
    canvas, draw = bg()
    add_header(draw, title, subtitle)
    paste_product(canvas, product, (150, 250, 1050, 760))
    y = 840
    for idx, (name, color) in enumerate(colors):
        x = 190 + idx * 280
        draw.rounded_rectangle((x, y, x + 230, y + 82), radius=26, fill=(248, 250, 252), outline=(226, 232, 240), width=2)
        draw.ellipse((x + 24, y + 23, x + 60, y + 59), fill=color, outline=(148, 163, 184))
        draw.text((x + 78, y + 25), name, fill=(30, 41, 59), font=font(26, True))
    add_pill(draw, (405, 990), "Ready for Daily Walking", (22, 163, 74))
    save(canvas, out)


def feature(out, product, title, subtitle, pill, notes, accent=(37, 99, 235)):
    canvas, draw = bg()
    add_header(draw, title, subtitle)
    paste_product(canvas, product, (90, 285, 760, 855))
    add_pill(draw, (760, 325), pill, accent)
    for i, (head, body) in enumerate(notes):
        add_feature_card(draw, (670, 430 + i * 180), head, body, accent)
    save(canvas, out)


def colors(out, products, title, subtitle, names):
    canvas, draw = bg()
    add_header(draw, title, subtitle)
    boxes = [(80, 285, 540, 650), (660, 285, 1120, 650), (370, 690, 830, 1045)]
    for p, b, name in zip(products, boxes, names):
        draw.rounded_rectangle((b[0], b[1], b[2], b[3] + 78), radius=28, fill=(248, 250, 252), outline=(226, 232, 240), width=2)
        paste_product(canvas, p, (b[0] + 25, b[1] + 25, b[2] - 25, b[3] - 10), shadow=False)
        draw.text((b[0] + 42, b[3] + 18), name, fill=(30, 41, 59), font=font(28, True))
    save(canvas, out)


def make_package(out_dir, product_paths, hero_product, weight_text, color_names, color_swatches):
    out_dir.mkdir(parents=True, exist_ok=True)
    hero(out_dir / "01_HERO_EN.jpg", hero_product, "Breathable Slip-On Walking Shoes", "Wide toe comfort for everyday wear", color_swatches)
    feature(
        out_dir / "02_WIDE_TOE_BOX_EN.jpg",
        hero_product,
        "Wide Toe Box",
        "Roomy forefoot space helps reduce pressure",
        "Natural Toe Space",
        [("Roomy Fit", "Allows toes to spread naturally"), ("Easy Comfort", "Suitable for long-time daily wear"), ("Slip-On Style", "Quick to put on and take off")],
        (14, 116, 144),
    )
    feature(
        out_dir / "03_BREATHABLE_MESH_UPPER_EN.jpg",
        hero_product,
        "Breathable Mesh Upper",
        "Soft knitted mesh improves airflow",
        "Air Flow Comfort",
        [("Mesh Fabric", "Light, soft and breathable upper"), ("Fresh Wear", "Helps keep feet comfortable"), ("Flexible Fit", "Moves naturally with the foot")],
        (37, 99, 235),
    )
    feature(
        out_dir / "04_LIGHTWEIGHT_DESIGN_EN.jpg",
        hero_product,
        "Lightweight Design",
        f"Approx. {weight_text}; easy for walking and travel",
        "Travel Friendly",
        [("Low Burden", "Comfortable for daily commuting"), ("Flexible Step", "Designed for easy movement"), ("Everyday Use", "Walking, travel and casual wear")],
        (22, 163, 74),
    )
    feature(
        out_dir / "05_CUSHIONED_EVA_MIDSOLE_EN.jpg",
        hero_product,
        "Cushioned EVA Midsole",
        "Soft support helps absorb daily impact",
        "Soft Cushion",
        [("EVA Midsole", "Lightweight cushioning support"), ("Stable Feel", "Comfort with every step"), ("Daily Walking", "Suitable for casual activities")],
        (124, 58, 237),
    )
    feature(
        out_dir / "06_ANTI_SLIP_RUBBER_OUTSOLE_EN.jpg",
        hero_product,
        "Anti-Slip Rubber Outsole",
        "Textured sole helps improve grip",
        "Stable Grip",
        [("Rubber Outsole", "Wear-resistant walking support"), ("Textured Pattern", "Grip for indoor and outdoor surfaces"), ("Steady Step", "Built for daily movement")],
        (220, 38, 38),
    )
    colors(out_dir / "07_COLOR_OPTIONS_EN.jpg", product_paths, "Color Options", "Clean solid colors for casual collections", color_names)


def main():
    pkg1_root = first_existing(RAW_ROOT / "5.13贝强1数据包", ROOT / "5.13贝强1数据包")
    pkg2_root = first_existing(RAW_ROOT / "5.13贝强2数据包", ROOT / "5.13贝强2数据包")
    pkg1 = pkg1_root / "透明图"
    pkg2 = pkg2_root / "透明图"
    out1 = UPLOAD_ROOT / "数据包1" / "英文详情图-平铺"
    out2 = UPLOAD_ROOT / "数据包2" / "英文详情图-平铺"

    p1 = [pkg1 / "5M4A1132.png", pkg1 / "5M4A1120.png", pkg1 / "5M4A1127.png"]
    p2 = [pkg2 / "5M4A1145.png", pkg2 / "5M4A1150.png", pkg2 / "5M4A1153.png"]
    make_package(
        out1,
        p1,
        p1[0],
        "267g per shoe",
        ["White", "Black / White Sole", "All Black"],
        [("White", (238, 238, 232)), ("Black White", (25, 25, 25)), ("All Black", (5, 5, 5))],
    )
    make_package(
        out2,
        p2,
        p2[0],
        "253g per shoe",
        ["Grey / White Sole", "Grey / Khaki Sole", "Grey / Black Sole"],
        [("Grey White", (126, 132, 137)), ("Grey Khaki", (132, 121, 91)), ("Grey Black", (60, 61, 64))],
    )

    for src, dst_dir in [
        (first_existing(ROOT / "推荐上传-商品详情图" / "1-尺寸图" / "BQ001_PRODUCT_DIMENSIONS_SIZE_REFERENCE.jpg", UPLOAD_ROOT / "数据包1" / "原整理详情图-中文参考" / "1-尺寸图" / "BQ001_PRODUCT_DIMENSIONS_SIZE_REFERENCE.jpg"), out1),
        (first_existing(ROOT / "推荐上传-商品详情图-数据包2" / "1-尺寸图" / "BQ002_PRODUCT_DIMENSIONS_SIZE_REFERENCE.jpg", UPLOAD_ROOT / "数据包2" / "原整理详情图-中文参考" / "1-尺寸图" / "BQ002_PRODUCT_DIMENSIONS_SIZE_REFERENCE.jpg"), out2),
    ]:
        if src.exists():
            shutil.copy2(src, dst_dir / src.name)

    group_for_upload(out1, UPLOAD_ROOT / "数据包1" / "推荐上传-英文详情图")
    group_for_upload(out2, UPLOAD_ROOT / "数据包2" / "推荐上传-英文详情图")


def group_for_upload(src_dir, grouped_dir):
    groups = {
        "1-尺寸图": ["BQ"],
        "2-场景图": ["01_HERO"],
        "3-细节图": ["02_", "03_", "04_", "05_", "06_"],
        "4-其他商品图片": ["07_"],
    }
    grouped_dir.mkdir(parents=True, exist_ok=True)
    for group_name, prefixes in groups.items():
        target = grouped_dir / group_name
        target.mkdir(parents=True, exist_ok=True)
        for img in src_dir.glob("*.jpg"):
            if any(img.name.startswith(prefix) for prefix in prefixes):
                shutil.copy2(img, target / img.name)


if __name__ == "__main__":
    main()
