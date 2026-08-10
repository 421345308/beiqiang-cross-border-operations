from __future__ import annotations

from pathlib import Path
import io
import shutil

from PIL import Image, ImageDraw, ImageEnhance, ImageFont


PRODUCT = "BQ022_A2208"
ARCHIVE_NAME = "BQ022_color_fix_20260621"


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
BACKUP_DIR = ARCHIVE_ROOT / ARCHIVE_NAME / "backups"


def raw_main_dir() -> Path:
    package = next(p for p in RAW_ROOT.iterdir() if p.is_dir() and "BQ022" in p.name)
    for folder in package.rglob("*"):
        if folder.is_dir() and (folder / "13.jpg").exists() and (folder / "15.jpg").exists():
            return folder
    raise FileNotFoundError("Cannot locate BQ022 raw main image folder")


RAW_MAIN_DIR = raw_main_dir()


COLOR_SOURCES = [
    ("Black", "14.jpg", (18, 18, 18), "Black upper"),
    ("Black White Stripe", "13.jpg", (210, 214, 218), "Striped upper"),
    ("Light Grey", "15.jpg", (178, 188, 194), "Light grey upper"),
]


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


def draw_header(draw: ImageDraw.ImageDraw, title: str, subtitle: str) -> None:
    draw.text((76, 70), title, fill=(18, 25, 38), font=font(52, True))
    draw.text((78, 142), subtitle, fill=(71, 85, 105), font=font(25))


def draw_color_grid(out: Path) -> None:
    canvas = Image.new("RGB", (1200, 1200), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    draw_header(draw, "ACTUAL COLOR OPTIONS", "3 confirmed single-color SKU photos from source")
    slots = [(76, 302, 396, 812), (440, 302, 760, 812), (804, 302, 1124, 812)]
    for (label, source_name, swatch, note), box in zip(COLOR_SOURCES, slots):
        draw.rounded_rectangle(box, radius=22, fill=(248, 250, 252), outline=(226, 232, 240), width=2)
        paste_contain(canvas, open_source(source_name), (box[0] + 22, box[1] + 28, box[2] - 22, box[3] - 108))
        draw.ellipse((box[0] + 28, box[3] - 76, box[0] + 58, box[3] - 46), fill=swatch, outline=(148, 163, 184))
        label_font = font(23, True) if label != "Black White Stripe" else font(20, True)
        draw.text((box[0] + 72, box[3] - 80), label, fill=(15, 23, 42), font=label_font)
        draw.text((box[0] + 30, box[3] - 38), note, fill=(71, 85, 105), font=font(17))
    pill_font = font(23, True)
    x = 76
    for label in ["EU 35-45", "Sample Check", "Mixed Sizes Discussable"]:
        w = int(draw.textlength(label, font=pill_font)) + 40
        draw.rounded_rectangle((x, 1028, x + w, 1078), radius=25, fill=(18, 118, 99))
        draw.text((x + 20, 1041), label, fill=(255, 255, 255), font=pill_font)
        x += w + 16
    save_jpg(canvas, out, quality=95)


def make_sku_image(source_name: str, out: Path) -> None:
    canvas = Image.new("RGB", (1000, 1000), (255, 255, 255))
    paste_contain(canvas, open_source(source_name), (55, 55, 945, 945))
    save_jpg(canvas, out, quality=96)


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
        COLOR_DIR / "black_white_stripe.jpg",
        COLOR_DIR / "light_grey.jpg",
    ]
    cols = 2
    cell_w, cell_h = 380, 430
    rows = (len(files) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * cell_w, rows * cell_h), (245, 245, 245))
    draw = ImageDraw.Draw(canvas)
    for i, path in enumerate(files):
        image = Image.open(path).convert("RGB")
        image.thumbnail((350, 340), Image.Resampling.LANCZOS)
        x = (i % cols) * cell_w
        y = (i // cols) * cell_h
        draw.text((x + 12, y + 10), path.parent.name + "/" + path.name, fill=(0, 0, 0), font=font(14, True))
        canvas.paste(image, (x + (cell_w - image.width) // 2, y + 55))
    save_jpg(canvas, out, quality=92)


def main() -> None:
    for path in [
        MAIN_DIR / "05_colors.jpg",
        DETAIL_DIR / "05_colors.jpg",
        COLOR_DIR / "black.jpg",
        COLOR_DIR / "black_grey.jpg",
        COLOR_DIR / "grey_stripe.jpg",
        COLOR_DIR / "light_grey.jpg",
        COLOR_DIR / "black_white_stripe.jpg",
        PRODUCT_DIR / "00_上架填写表.md",
    ]:
        backup_file(path)

    draw_color_grid(MAIN_DIR / "05_colors.jpg")
    draw_color_grid(DETAIL_DIR / "05_colors.jpg")
    make_sku_image("14.jpg", COLOR_DIR / "black.jpg")
    make_sku_image("13.jpg", COLOR_DIR / "black_white_stripe.jpg")
    make_sku_image("15.jpg", COLOR_DIR / "light_grey.jpg")

    for stale_name in ["black_grey.jpg", "grey_stripe.jpg"]:
        stale = COLOR_DIR / stale_name
        if stale.exists():
            stale.unlink()

    make_preview(PREVIEW_DIR / "bq022_color_fix_applied.jpg")
    print("BQ022 color images fixed")
    print(f"backup={BACKUP_DIR}")
    print(f"preview={PREVIEW_DIR / 'bq022_color_fix_applied.jpg'}")


if __name__ == "__main__":
    main()
