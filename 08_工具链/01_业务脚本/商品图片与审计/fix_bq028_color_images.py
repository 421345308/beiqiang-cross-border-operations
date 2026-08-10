from __future__ import annotations

from pathlib import Path
import io
import shutil

from PIL import Image, ImageDraw, ImageEnhance, ImageFont


PRODUCT = "BQ028_BISCUIT"
ARCHIVE_NAME = "BQ028_color_fix_20260621"


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
    package = next(p for p in RAW_ROOT.iterdir() if p.is_dir() and "BQ028" in p.name)
    for folder in package.rglob("*"):
        if folder.is_dir() and (folder / "1.jpg").exists() and (folder / "49.jpg").exists():
            return folder
    raise FileNotFoundError("Cannot locate BQ028 raw main image folder")


RAW_MAIN_DIR = raw_main_dir()


COLOR_SOURCES = [
    ("Black White", "23.jpg", (16, 16, 16), "Black-white upper"),
    ("Grey", "46.jpg", (122, 132, 139), "Grey upper"),
    ("Apricot", "43.jpg", (198, 184, 164), "Apricot upper"),
    ("White", "5.jpg", (240, 240, 236), "White upper"),
    ("Blue", "47.jpg", (55, 119, 151), "Blue upper"),
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
    draw.text((76, 66), title, fill=(18, 25, 38), font=font(49, True))
    draw.text((78, 132), subtitle, fill=(71, 85, 105), font=font(24))


def draw_color_grid(out: Path) -> None:
    canvas = Image.new("RGB", (1200, 1200), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    draw_header(draw, "ACTUAL COLOR OPTIONS", "Confirmed supplier colors; no mixed-color SKU photo used")
    slots = [
        (72, 245, 392, 560),
        (440, 245, 760, 560),
        (808, 245, 1128, 560),
        (256, 640, 576, 955),
        (624, 640, 944, 955),
    ]
    for (label, source_name, swatch, note), box in zip(COLOR_SOURCES, slots):
        draw.rounded_rectangle(box, radius=22, fill=(248, 250, 252), outline=(226, 232, 240), width=2)
        paste_contain(canvas, open_source(source_name), (box[0] + 22, box[1] + 22, box[2] - 22, box[3] - 86))
        draw.ellipse((box[0] + 26, box[3] - 58, box[0] + 56, box[3] - 28), fill=swatch, outline=(148, 163, 184))
        draw.text((box[0] + 70, box[3] - 62), label, fill=(15, 23, 42), font=font(24, True))
        draw.text((box[0] + 28, box[3] - 28), note, fill=(71, 85, 105), font=font(16))
    pill_font = font(22, True)
    x = 76
    for label in ["EU 35-45", "Sample Check", "Mixed Sizes Discussable"]:
        w = int(draw.textlength(label, font=pill_font)) + 40
        draw.rounded_rectangle((x, 1032, x + w, 1080), radius=24, fill=(18, 118, 99))
        draw.text((x + 20, 1045), label, fill=(255, 255, 255), font=pill_font)
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
        COLOR_DIR / "black_white.jpg",
        COLOR_DIR / "grey.jpg",
        COLOR_DIR / "apricot.jpg",
        COLOR_DIR / "white.jpg",
        COLOR_DIR / "blue.jpg",
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
        COLOR_DIR / "black_white.jpg",
        COLOR_DIR / "grey.jpg",
        COLOR_DIR / "mixed_colors.jpg",
        COLOR_DIR / "white.jpg",
        COLOR_DIR / "apricot.jpg",
        COLOR_DIR / "blue.jpg",
        PRODUCT_DIR / "00_上架填写表.md",
    ]:
        backup_file(path)

    draw_color_grid(MAIN_DIR / "05_colors.jpg")
    draw_color_grid(DETAIL_DIR / "05_colors.jpg")
    make_sku_image("23.jpg", COLOR_DIR / "black_white.jpg")
    make_sku_image("46.jpg", COLOR_DIR / "grey.jpg")
    make_sku_image("43.jpg", COLOR_DIR / "apricot.jpg")
    make_sku_image("5.jpg", COLOR_DIR / "white.jpg")
    make_sku_image("47.jpg", COLOR_DIR / "blue.jpg")

    stale = COLOR_DIR / "mixed_colors.jpg"
    if stale.exists():
        stale.unlink()

    make_preview(PREVIEW_DIR / "bq028_color_fix_applied.jpg")
    print("BQ028 color images fixed")
    print(f"backup={BACKUP_DIR}")
    print(f"preview={PREVIEW_DIR / 'bq028_color_fix_applied.jpg'}")


if __name__ == "__main__":
    main()
