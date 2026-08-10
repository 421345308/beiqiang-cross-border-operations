from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = next(p for p in ROOT.iterdir() if p.name.startswith("01_"))
UPLOAD_ROOT = next(p for p in ROOT.iterdir() if p.name.startswith("02_"))
COMPANY_ROOT = next(p for p in ROOT.iterdir() if p.name.startswith("03_"))
FACTORY_DIR = next(p for p in COMPANY_ROOT.iterdir() if p.is_dir())
OUT = UPLOAD_ROOT / "company-detail-v3"


def get_font(size: int, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
    ]
    for file in candidates:
        try:
            return ImageFont.truetype(file, size)
        except OSError:
            pass
    return ImageFont.load_default()


F_TITLE = get_font(54, True)
F_SUB = get_font(27, True)
F_BODY = get_font(25)
F_SMALL = get_font(19)
F_LABEL = get_font(22, True)

GREEN = (55, 91, 74)
DARK = (34, 43, 40)
MUTED = (83, 96, 90)
BG = (248, 250, 248)
CARD = (238, 244, 240)
LINE = (213, 225, 218)


def wrap(draw, text, font, width):
    words = text.split()
    lines, cur = [], ""
    for word in words:
        test = word if not cur else cur + " " + word
        if draw.textbbox((0, 0), test, font=font)[2] <= width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def paragraph(draw, text, x, y, width, font=F_BODY, fill=DARK, gap=6):
    for line in wrap(draw, text, font, width):
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + gap
    return y


def image_cover(path, size):
    im = Image.open(path).convert("RGB")
    return ImageOps.fit(im, size, Image.LANCZOS, centering=(0.5, 0.5))


def product_contain(path, size):
    im = Image.open(path).convert("RGBA")
    im.thumbnail((size[0] - 36, size[1] - 44), Image.LANCZOS)
    bg = Image.new("RGBA", size, (255, 255, 255, 255))
    bg.alpha_composite(im, ((size[0] - im.width) // 2, (size[1] - im.height) // 2))
    return bg.convert("RGB")


def round_paste(base, im, xy, radius=22):
    mask = Image.new("L", im.size, 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=radius, fill=255)
    base.paste(im, xy, mask)


def header(draw, title, subtitle):
    draw.rectangle((0, 0, 1200, 18), fill=GREEN)
    draw.text((70, 50), title, font=F_TITLE, fill=GREEN)
    draw.text((72, 116), subtitle, font=F_SUB, fill=MUTED)


def draw_points(draw, points, x, y, width, cols=2):
    col_w = width // cols
    row_h = 78
    for idx, text in enumerate(points):
        cx = x + (idx % cols) * col_w
        cy = y + (idx // cols) * row_h
        draw.rounded_rectangle((cx, cy, cx + col_w - 22, cy + 56), radius=12, fill=CARD, outline=LINE)
        draw.ellipse((cx + 18, cy + 20, cx + 31, cy + 33), fill=GREEN)
        paragraph(draw, text, cx + 48, cy + 14, col_w - 88, F_SMALL, DARK, 2)


def draw_image_grid(canvas, paths, x, y, w, h, product=False):
    cell_w = (w - 26) // 2
    cell_h = (h - 26) // 2
    positions = [(x, y), (x + cell_w + 26, y), (x, y + cell_h + 26), (x + cell_w + 26, y + cell_h + 26)]
    for path, pos in zip(paths[:4], positions):
        im = product_contain(path, (cell_w, cell_h)) if product else image_cover(path, (cell_w, cell_h))
        round_paste(canvas, im, pos, 20)


def module(title, subtitle, intro, points, images, out_name, product=False):
    W, H = 1200, 1260
    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)
    header(draw, title, subtitle)
    y = paragraph(draw, intro, 72, 174, 1040, F_BODY, DARK, 6)
    draw_points(draw, points, 70, y + 14, 1060)
    draw_image_grid(canvas, images, 70, 410, 1060, 700, product=product)
    draw.text((72, H - 54), "Beiqiang Footwear | Walking Shoes Supplier", font=F_SMALL, fill=MUTED)
    OUT.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT / out_name, quality=94)


def process_module(images):
    W, H = 1200, 1260
    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)
    header(draw, "CUSTOMIZATION PROCESS", "Simple order steps for private label buyers")
    y = paragraph(
        draw,
        "From inquiry to shipment, each step is confirmed before production. This helps buyers control style, size ratio, packaging and delivery details.",
        72,
        174,
        1040,
        F_BODY,
        DARK,
        6,
    )
    steps = [
        ("01", "Inquiry", "Style, quantity and market needs"),
        ("02", "Confirm", "Logo, color, size and package"),
        ("03", "Sample", "Quality check before order"),
        ("04", "Production", "Bulk order after approval"),
        ("05", "Packing", "Box, bag or custom package"),
        ("06", "Shipping", "Carton and freight details"),
    ]
    sx, sy = 70, y + 24
    bw, bh = 336, 126
    for i, (num, name, desc) in enumerate(steps):
        x = sx + (i % 3) * 365
        yy = sy + (i // 3) * 154
        draw.rounded_rectangle((x, yy, x + bw, yy + bh), radius=18, fill=(255, 255, 255), outline=LINE, width=2)
        draw.ellipse((x + 18, yy + 24, x + 66, yy + 72), fill=GREEN)
        draw.text((x + 33, yy + 37), num, font=F_LABEL, fill=(255, 255, 255))
        draw.text((x + 84, yy + 24), name, font=F_SUB, fill=GREEN)
        paragraph(draw, desc, x + 84, yy + 66, 220, F_SMALL, DARK, 2)
    draw_image_grid(canvas, images, 70, 650, 1060, 460)
    draw.text((72, H - 54), "Confirm MOQ, sample cost and lead time before bulk order", font=F_SMALL, fill=MUTED)
    canvas.save(OUT / "05_process.jpg", quality=94)


def make_preview():
    files = sorted([p for p in OUT.glob("*.jpg") if p.name != "preview.jpg"])
    tw, th = 360, 378
    cols = 2
    rows = (len(files) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + 42)), (242, 244, 246))
    d = ImageDraw.Draw(sheet)
    for i, p in enumerate(files):
        im = Image.open(p).convert("RGB")
        im.thumbnail((tw, th), Image.LANCZOS)
        x, y = (i % cols) * tw, (i // cols) * (th + 42)
        sheet.paste(im, (x + (tw - im.width) // 2, y))
        d.text((x + 8, y + th + 8), f"{p.name} ({len(p.name)})", font=F_SMALL, fill=DARK)
    sheet.save(OUT / "preview.jpg", quality=92)


def main():
    photos = {p.name: p for p in FACTORY_DIR.iterdir() if p.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]}
    def fp(names):
        return [photos[n] for n in names if n in photos]

    products = [p for p in RAW_ROOT.rglob("5M*.png") if p.is_file()]
    products = products[:6]

    module(
        "BEIQIANG FOOTWEAR",
        "Factory supplier for casual walking shoes",
        "We focus on practical walking shoes with knitted upper, lightweight EVA sole, wide toe box design and easy slip-on comfort for daily wear.",
        ["Factory and warehouse photos", "Small trial orders available", "Mixed sizes and colors", "Custom package for bulk orders"],
        fp(["312131B92967C3A2090BFAFDB951C0A4.png", "9123A5EB607A681AC92FFFABE40B3005.png", "E7AE0BC4F8A9D61778E2322DDE44D6F6.png", "A9C9E3B935A11A476BE00DE0FD0C3BBC.png"]),
        "01_company.jpg",
    )
    module(
        "COMPETITIVE ADVANTAGES",
        "Flexible supply for wholesalers and online sellers",
        "We support buyers who want to test walking shoe styles first, then expand to repeat orders or customized packaging after market feedback.",
        ["Wide toe walking shoe focus", "Sample checking before bulk", "Factory and warehouse visibility", "Trade Assurance order support"],
        fp(["FF0EB3E94E43735A20D8584C73B4242F.png", "312131B92967C3A2090BFAFDB951C0A4.png", "D6C7FD5A226C319802D341A1CF7B4E06.png", "A228768BC3566451DFC612A7F03B619D.png"]),
        "02_advantage.jpg",
    )
    module(
        "FACTORY PROFILE",
        "Real workshop, warehouse and product handling areas",
        "These on-site photos help buyers understand our actual working environment before cooperation. Exact capacity and delivery time should be confirmed by order.",
        ["Workshop production areas", "Warehouse storage areas", "Material and product handling", "Real photos for buyer trust"],
        fp(["84FF9D0383A2DC0DB22BB759FA5F4EA8.png", "6547C269B1439AC9E425D210A83A5BC7.png", "E7AE0BC4F8A9D61778E2322DDE44D6F6.png", "3CD1A61634DA5270C85F4B3E4CCAD9F7.png"]),
        "03_factory.jpg",
    )
    module(
        "PRODUCT CHECKING",
        "Product details checked before shipment",
        "We confirm material, outsole, color, size ratio and packing details before shipment. Pre-shipment photos can be discussed for bulk orders.",
        ["Knitted upper confirmation", "EVA sole confirmation", "Size and color ratio check", "Packing details check"],
        products[:4] if len(products) >= 4 else fp(["312131B92967C3A2090BFAFDB951C0A4.png", "FF0EB3E94E43735A20D8584C73B4242F.png"]),
        "04_quality.jpg",
        product=len(products) >= 4,
    )
    process_module(fp(["FF0EB3E94E43735A20D8584C73B4242F.png", "A63A0FD1CBA98FD532B425D5C499173E.png", "E33B3E32BABD18D4A9770DCED97ED38F.png", "C278DF7185486C15215089FAC3776592.png"]))
    module(
        "PACKAGING & SHIPPING",
        "Standard package and custom package options",
        "Standard packaging can be shoe box or plastic bag. For larger orders, custom packaging, labels and packing method can be discussed before production.",
        ["Shoe box or plastic bag", "Custom package for bulk orders", "Carton details confirmed", "Shipping method discussed"],
        fp(["3D7E6320356123E5172283244B177B69.png", "429528D5FACB6A995B4B6CD84C5A5EDA.png", "9123A5EB607A681AC92FFFABE40B3005.png", "D226973837DEA739118B2588DF676E1D.png"]),
        "06_pack.jpg",
    )
    module(
        "BUYER SERVICE SUPPORT",
        "Lower-risk cooperation for first orders",
        "For new buyers, we recommend starting with available styles, sample checking and mixed size or color orders before larger customized production.",
        ["Samples before bulk order", "Mixed colors and sizes", "Sample fee can be deducted", "MOQ depends on order needs"],
        fp(["312131B92967C3A2090BFAFDB951C0A4.png", "A228768BC3566451DFC612A7F03B619D.png", "D6C7FD5A226C319802D341A1CF7B4E06.png", "9123A5EB607A681AC92FFFABE40B3005.png"]),
        "07_service.jpg",
    )
    (OUT / "README.txt").write_text(
        "Do not use fake certificate, trade show, or buyer review modules. Add those only after real materials are provided.\n",
        encoding="utf-8",
    )
    make_preview()
    print(OUT)


if __name__ == "__main__":
    main()
