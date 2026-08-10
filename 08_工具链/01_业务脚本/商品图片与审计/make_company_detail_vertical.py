from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[2]


def find_child(parent: Path, prefix: str | None = None, contains: str | None = None) -> Path:
    for child in parent.iterdir():
        if not child.exists():
            continue
        ok_prefix = prefix is None or child.name.startswith(prefix)
        ok_contains = contains is None or contains in child.name
        if ok_prefix and ok_contains:
            return child
    raise FileNotFoundError((parent, prefix, contains))


SOURCE_ROOT = find_child(ROOT, prefix="03_")
FACTORY_DIR = next(p for p in SOURCE_ROOT.iterdir() if p.is_dir())
UPLOAD_ROOT = find_child(ROOT, prefix="02_")
OUT = UPLOAD_ROOT / "company-detail-v2"


def font(size: int, bold: bool = False):
    files = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
    ]
    for file in files:
        try:
            return ImageFont.truetype(file, size)
        except OSError:
            pass
    return ImageFont.load_default()


F_TITLE = font(58, True)
F_SUBTITLE = font(30, True)
F_BODY = font(27)
F_SMALL = font(20)
F_TAG = font(22, True)

GREEN = (55, 91, 74)
DARK = (36, 45, 42)
MUTED = (91, 104, 98)
BG = (247, 249, 247)
LINE = (214, 224, 218)
PALE = (235, 241, 237)


def cover(path: Path, size: tuple[int, int]) -> Image.Image:
    im = Image.open(path).convert("RGB")
    return ImageOps.fit(im, size, Image.LANCZOS, centering=(0.5, 0.5))


def contain(path: Path, size: tuple[int, int]) -> Image.Image:
    im = Image.open(path).convert("RGB")
    im.thumbnail(size, Image.LANCZOS)
    canvas = Image.new("RGB", size, (255, 255, 255))
    canvas.paste(im, ((size[0] - im.width) // 2, (size[1] - im.height) // 2))
    return canvas


def round_paste(base: Image.Image, im: Image.Image, xy: tuple[int, int], radius: int = 22):
    mask = Image.new("L", im.size, 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=radius, fill=255)
    base.paste(im, xy, mask)


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, width: int):
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = word if not current else current + " " + word
        if draw.textbbox((0, 0), test, font=fnt)[2] <= width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_paragraph(draw, text: str, x: int, y: int, width: int, fnt=F_BODY, fill=DARK, gap=8):
    for line in wrap(draw, text, fnt, width):
        draw.text((x, y), line, font=fnt, fill=fill)
        y += fnt.size + gap
    return y


def header(draw, title: str, subtitle: str):
    draw.rectangle((0, 0, 1200, 18), fill=GREEN)
    draw.text((70, 64), title, font=F_TITLE, fill=GREEN)
    draw.text((72, 138), subtitle, font=F_SUBTITLE, fill=MUTED)


def bullet_grid(draw, bullets: list[str], x: int, y: int, width: int, cols: int = 2):
    col_w = width // cols
    row_h = 92
    for idx, text in enumerate(bullets):
        cx = x + (idx % cols) * col_w
        cy = y + (idx // cols) * row_h
        draw.rounded_rectangle((cx, cy, cx + col_w - 26, cy + 68), radius=14, fill=PALE, outline=LINE)
        draw.ellipse((cx + 20, cy + 23, cx + 34, cy + 37), fill=GREEN)
        draw_paragraph(draw, text, cx + 52, cy + 15, col_w - 100, F_SMALL, DARK, 3)


def image_grid(canvas, paths: list[Path], x: int, y: int, w: int, h: int):
    if len(paths) <= 1:
        if paths:
            round_paste(canvas, cover(paths[0], (w, h)), (x, y), 24)
        return
    cell_w = (w - 28) // 2
    cell_h = (h - 28) // 2
    positions = [(x, y), (x + cell_w + 28, y), (x, y + cell_h + 28), (x + cell_w + 28, y + cell_h + 28)]
    for path, pos in zip(paths[:4], positions):
        round_paste(canvas, cover(path, (cell_w, cell_h)), pos, 22)


def make_module(title: str, subtitle: str, intro: str, bullets: list[str], images: list[Path], out_name: str):
    W, H = 1200, 1280
    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)
    header(draw, title, subtitle)
    y = draw_paragraph(draw, intro, 72, 198, 1040, F_BODY, DARK, 8)
    bullet_grid(draw, bullets, 70, y + 16, 1060, 2)
    image_grid(canvas, images, 70, 460, 1060, 700)
    draw.text((72, H - 58), "Beiqiang Footwear | Wide Toe Box Walking Shoes Supplier", font=F_SMALL, fill=MUTED)
    OUT.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT / out_name, quality=94)


def make_process(images: list[Path]):
    W, H = 1200, 1280
    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)
    header(draw, "CUSTOMIZATION PROCESS", "Clear steps for logo, color and packaging orders")
    intro = "For buyers who need private label or packaging support, we confirm each step before production to reduce misunderstanding and improve order efficiency."
    y = draw_paragraph(draw, intro, 72, 198, 1040, F_BODY, DARK, 8)
    steps = [
        ("01", "Inquiry", "Send style, quantity and market needs"),
        ("02", "Design Check", "Confirm logo, color, size ratio and package"),
        ("03", "Sample", "Prepare sample for quality checking"),
        ("04", "Production", "Arrange bulk production after approval"),
        ("05", "Packing", "Shoe box, plastic bag or custom package"),
        ("06", "Shipment", "Confirm carton details and shipping method"),
    ]
    sx, sy = 80, y + 34
    box_w, box_h = 320, 142
    for i, (num, name, desc) in enumerate(steps):
        x = sx + (i % 3) * 365
        yy = sy + (i // 3) * 190
        draw.rounded_rectangle((x, yy, x + box_w, yy + box_h), radius=18, fill=(255, 255, 255), outline=LINE, width=2)
        draw.ellipse((x + 22, yy + 24, x + 76, yy + 78), fill=GREEN)
        draw.text((x + 39, yy + 38), num, font=F_TAG, fill=(255, 255, 255))
        draw.text((x + 92, yy + 26), name, font=F_SUBTITLE, fill=GREEN)
        draw_paragraph(draw, desc, x + 92, yy + 72, 205, F_SMALL, DARK, 3)
    image_grid(canvas, images, 70, 680, 1060, 480)
    draw.text((72, H - 58), "Beiqiang Footwear | OEM/ODM details should be confirmed before bulk order", font=F_SMALL, fill=MUTED)
    canvas.save(OUT / "04_process.jpg", quality=94)


def make_placeholder_notes():
    note = OUT / "README_materials_needed.txt"
    note.write_text(
        "\n".join(
            [
                "Materials still needed for stronger trust modules:",
                "",
                "1. Product certificates or test reports: upload real certificate photos/PDFs only.",
                "2. Trade show photos: use real booth, exhibition or buyer-meeting photos only.",
                "3. Customer reviews: use real buyer feedback screenshots with sensitive data removed.",
                "4. Packaging details: carton size, gross weight, shoe box size and package photos.",
                "5. Customization policy: confirmed logo MOQ, package MOQ, sample cost and lead time.",
                "",
                "Current generated modules avoid fake certificate, fake trade show and fake customer review claims.",
            ]
        ),
        encoding="utf-8",
    )


def main():
    photos = {p.name: p for p in FACTORY_DIR.iterdir() if p.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]}
    def p(names):
        return [photos[n] for n in names if n in photos]

    product_images = []
    for candidate in UPLOAD_ROOT.glob("*/英文主图/*.jpg"):
        if "WIDE_TOE_BOX" in candidate.name or "LIGHTWEIGHT" in candidate.name:
            product_images.append(candidate)
    product_images = product_images[:4]

    make_module(
        "BEIQIANG FOOTWEAR",
        "Casual walking shoes supplier for international buyers",
        "We focus on practical walking shoes with breathable knitted upper, lightweight EVA sole, wide toe box design and easy slip-on comfort for daily wear.",
        [
            "Factory and warehouse photos available",
            "Small trial orders can be discussed",
            "Mixed sizes and colors for available styles",
            "Packaging customization for larger orders",
        ],
        p(["312131B92967C3A2090BFAFDB951C0A4.png", "9123A5EB607A681AC92FFFABE40B3005.png", "E7AE0BC4F8A9D61778E2322DDE44D6F6.png", "A9C9E3B935A11A476BE00DE0FD0C3BBC.png"]),
        "01_company.jpg",
    )

    make_module(
        "ABOUT THE SUPPLIER",
        "Real workshop, warehouse and product supply support",
        "Our team supports wholesale buyers with product selection, sample checking, packaging discussion and long-term walking shoe supply cooperation.",
        [
            "Focused on casual walking shoe products",
            "Buyer requirements confirmed before order",
            "Clear communication for sample and bulk order",
            "Suitable for wholesalers and online sellers",
        ],
        p(["84FF9D0383A2DC0DB22BB759FA5F4EA8.png", "6547C269B1439AC9E425D210A83A5BC7.png", "D6C7FD5A226C319802D341A1CF7B4E06.png", "3CD1A61634DA5270C85F4B3E4CCAD9F7.png"]),
        "02_supplier.jpg",
    )

    make_module(
        "PRODUCT QUALITY CONTROL",
        "Product details confirmed before shipping",
        "We use practical product checking steps instead of exaggerated claims. Material, outsole, size ratio, color and packaging details should be confirmed before bulk order.",
        [
            "Knitted upper and EVA sole confirmation",
            "Size and color ratio checked before packing",
            "Packaging method confirmed by order needs",
            "Pre-shipment photos can be discussed",
        ],
        product_images or p(["FF0EB3E94E43735A20D8584C73B4242F.png", "312131B92967C3A2090BFAFDB951C0A4.png", "A63A0FD1CBA98FD532B425D5C499173E.png", "E33B3E32BABD18D4A9770DCED97ED38F.png"]),
        "03_quality.jpg",
    )

    make_process(p(["FF0EB3E94E43735A20D8584C73B4242F.png", "A63A0FD1CBA98FD532B425D5C499173E.png", "E33B3E32BABD18D4A9770DCED97ED38F.png", "C278DF7185486C15215089FAC3776592.png"]))

    make_module(
        "PACKAGING & SHIPPING",
        "Standard package and custom package options",
        "Standard packaging can be shoe box or plastic bag. For larger orders, custom packaging, labels and packing method can be discussed before production.",
        [
            "Shoe box or plastic bag for standard package",
            "Custom packaging for larger quantity orders",
            "Carton details confirmed before shipping",
            "Alibaba Trade Assurance can support safer orders",
        ],
        p(["3D7E6320356123E5172283244B177B69.png", "429528D5FACB6A995B4B6CD84C5A5EDA.png", "9123A5EB607A681AC92FFFABE40B3005.png", "D226973837DEA739118B2588DF676E1D.png"]),
        "05_pack.jpg",
    )

    make_module(
        "BUYER SERVICE SUPPORT",
        "Flexible cooperation for early orders and long-term supply",
        "For new buyers, we recommend starting with available styles, sample checking and mixed size or color orders before larger customized production.",
        [
            "Sample checking before bulk order",
            "Mixed colors and sizes can be discussed",
            "Sample fee can be deducted from bulk order",
            "MOQ depends on stock and customization needs",
        ],
        p(["312131B92967C3A2090BFAFDB951C0A4.png", "A228768BC3566451DFC612A7F03B619D.png", "D6C7FD5A226C319802D341A1CF7B4E06.png", "16_D6C7FD5A226C319802D341A1CF7B4E06.png"]),
        "06_service.jpg",
    )

    make_placeholder_notes()
    print(OUT)


if __name__ == "__main__":
    main()
