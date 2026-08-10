from __future__ import annotations

from pathlib import Path
import io
import shutil

from PIL import Image, ImageDraw, ImageEnhance, ImageFont


PRODUCT = "BQ016_201"
ARCHIVE_NAME = "BQ016_color_fix_20260621"


def workspace_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "AGENTS.md").exists():
        return cwd
    return Path(__file__).resolve().parents[2]


ROOT = workspace_root()


def child_by_prefix(parent: Path, prefix: str) -> Path:
    return next(p for p in parent.iterdir() if p.is_dir() and p.name.startswith(prefix))


RAW_ROOT = child_by_prefix(ROOT, "01_")
ASSET_ROOT = child_by_prefix(ROOT, "02_")
FINAL_ROOT = child_by_prefix(ASSET_ROOT, "00_")
ARCHIVE_ROOT = child_by_prefix(ASSET_ROOT, "99_")
PRODUCT_DIR = FINAL_ROOT / PRODUCT
MAIN_DIR = child_by_prefix(PRODUCT_DIR, "01_")
DETAIL_DIR = child_by_prefix(PRODUCT_DIR, "02_")
COLOR_DIR = child_by_prefix(PRODUCT_DIR, "03_")
PREVIEW_DIR = child_by_prefix(PRODUCT_DIR, "04_")
QA_ROOT = ARCHIVE_ROOT / ARCHIVE_NAME
BACKUP_DIR = QA_ROOT / "backups"


def raw_main_dir() -> Path:
    package = next(p for p in RAW_ROOT.iterdir() if p.is_dir() and "BQ016" in p.name)
    for path in package.rglob("20.jpg"):
        if path.is_file() and any((path.parent / name).exists() for name in ["13.jpg", "28.jpg"]):
            return path.parent
    raise FileNotFoundError("Cannot locate BQ016 raw main image folder")


RAW_MAIN_DIR = raw_main_dir()


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def save_jpg(image: Image.Image, path: Path, quality: int = 95) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "JPEG", quality=quality, optimize=True, subsampling=1)
    path.write_bytes(buffer.getvalue())


def open_source(name: str) -> Image.Image:
    image = Image.open(RAW_MAIN_DIR / name).convert("RGB")
    image = ImageEnhance.Contrast(image).enhance(1.02)
    image = ImageEnhance.Sharpness(image).enhance(1.03)
    return image


def paste_contain(canvas: Image.Image, image: Image.Image, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    max_w = x1 - x0
    max_h = y1 - y0
    pic = image.copy()
    pic.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    x = x0 + (max_w - pic.width) // 2
    y = y0 + (max_h - pic.height) // 2
    canvas.paste(pic, (x, y))


def make_sku_image(source_name: str, out: Path) -> None:
    canvas = Image.new("RGB", (1000, 1000), (255, 255, 255))
    image = open_source(source_name)
    paste_contain(canvas, image, (55, 55, 945, 945))
    save_jpg(canvas, out, quality=96)


def draw_header(draw: ImageDraw.ImageDraw, title: str, subtitle: str) -> None:
    draw.text((76, 70), title, fill=(18, 25, 38), font=font(52, True))
    draw.text((78, 142), subtitle, fill=(71, 85, 105), font=font(25))


def draw_color_grid(out: Path, compact: bool = False) -> None:
    colors = [
        {
            "label": "Black",
            "source": "20.jpg",
            "swatch": (20, 20, 20),
            "note": "Black gold-thread upper",
        },
        {
            "label": "Pink",
            "source": "13.jpg",
            "swatch": (235, 181, 198),
            "note": "Pink gold-thread upper",
        },
        {
            "label": "Zebra Stripe",
            "source": "28.jpg",
            "swatch": (210, 214, 218),
            "note": "Stripe gold-thread upper",
        },
    ]
    canvas = Image.new("RGB", (1200, 1200), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    if compact:
        draw_header(draw, "COLOR OPTIONS", "3 confirmed colors from the source package")
        slots = [(76, 300, 360, 770), (458, 300, 742, 770), (840, 300, 1124, 770)]
        image_boxes = [(94, 330, 342, 628), (476, 330, 724, 628), (858, 330, 1106, 628)]
    else:
        draw_header(draw, "ACTUAL COLOR OPTIONS", "Single-color SKU photos only; no mixed-color photo used")
        slots = [(76, 280, 396, 810), (440, 280, 760, 810), (804, 280, 1124, 810)]
        image_boxes = [(100, 318, 372, 650), (464, 318, 736, 650), (828, 318, 1100, 650)]

    for item, slot, image_box in zip(colors, slots, image_boxes):
        draw.rounded_rectangle(slot, radius=22, fill=(248, 250, 252), outline=(226, 232, 240), width=2)
        paste_contain(canvas, open_source(item["source"]), image_box)
        x0, _y0, _x1, y1 = slot
        draw.ellipse((x0 + 28, y1 - 116, x0 + 58, y1 - 86), fill=item["swatch"], outline=(148, 163, 184))
        draw.text((x0 + 72, y1 - 120), item["label"], fill=(15, 23, 42), font=font(26, True))
        draw.text((x0 + 30, y1 - 70), item["note"], fill=(71, 85, 105), font=font(18))

    pill_font = font(24, True)
    pills = ["EU 31-40", "Sample Check", "Mixed Sizes Discussable"]
    x = 76
    for label in pills:
        w = int(draw.textlength(label, font=pill_font)) + 42
        draw.rounded_rectangle((x, 1005, x + w, 1055), radius=25, fill=(18, 118, 99))
        draw.text((x + 21, 1018), label, fill=(255, 255, 255), font=pill_font)
        x += w + 18

    save_jpg(canvas, out, quality=95)


def backup_file(path: Path) -> None:
    if not path.exists():
        return
    rel = path.relative_to(PRODUCT_DIR)
    target = BACKUP_DIR / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)


def make_preview(out: Path) -> None:
    files = [
        MAIN_DIR / "05_colors.jpg",
        DETAIL_DIR / "05_colors.jpg",
        COLOR_DIR / "black.jpg",
        COLOR_DIR / "pink.jpg",
        COLOR_DIR / "zebra_stripe.jpg",
    ]
    cell_w, cell_h = 360, 430
    cols = 2
    rows = (len(files) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * cell_w, rows * cell_h), (245, 245, 245))
    draw = ImageDraw.Draw(canvas)
    for i, path in enumerate(files):
        image = Image.open(path).convert("RGB")
        image.thumbnail((330, 330), Image.Resampling.LANCZOS)
        x = (i % cols) * cell_w
        y = (i // cols) * cell_h
        draw.text((x + 12, y + 10), path.parent.name + "/" + path.name, fill=(0, 0, 0), font=font(14, True))
        canvas.paste(image, (x + (cell_w - image.width) // 2, y + 55))
    save_jpg(canvas, out, quality=92)


def main() -> None:
    targets = [
        MAIN_DIR / "05_colors.jpg",
        DETAIL_DIR / "05_colors.jpg",
        COLOR_DIR / "black.jpg",
        COLOR_DIR / "pink.jpg",
        COLOR_DIR / "grey_stripe.jpg",
        COLOR_DIR / "black_white.jpg",
        COLOR_DIR / "zebra_stripe.jpg",
        PRODUCT_DIR / "00_上架填写表.md",
    ]
    for path in targets:
        backup_file(path)

    draw_color_grid(MAIN_DIR / "05_colors.jpg")
    draw_color_grid(DETAIL_DIR / "05_colors.jpg", compact=True)
    make_sku_image("20.jpg", COLOR_DIR / "black.jpg")
    make_sku_image("13.jpg", COLOR_DIR / "pink.jpg")
    make_sku_image("28.jpg", COLOR_DIR / "zebra_stripe.jpg")

    for stale_name in ["grey_stripe.jpg", "black_white.jpg"]:
        stale = COLOR_DIR / stale_name
        if stale.exists():
            stale.unlink()

    make_preview(PREVIEW_DIR / "bq016_color_fix_applied.jpg")
    print("BQ016 color images fixed")
    print(f"backup={BACKUP_DIR}")
    print(f"preview={PREVIEW_DIR / 'bq016_color_fix_applied.jpg'}")


if __name__ == "__main__":
    main()
