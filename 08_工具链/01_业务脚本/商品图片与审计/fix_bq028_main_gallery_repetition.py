from __future__ import annotations

from pathlib import Path
import io
import shutil

from PIL import Image, ImageDraw, ImageEnhance, ImageFont


PRODUCT = "BQ028_BISCUIT"
ARCHIVE_NAME = "BQ028_gallery_role_fix_20260621"
ROLE_FILES = ["02_upper.jpg", "03_fit.jpg", "04_sole.jpg", "06_scene.jpg"]


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
PREVIEW_DIR = child_by_prefix(PRODUCT_DIR, "04_")
QA_ROOT = ARCHIVE_ROOT / ARCHIVE_NAME
BACKUP_DIR = QA_ROOT / "backups"


def raw_main_dir() -> Path:
    package = next(p for p in RAW_ROOT.iterdir() if p.is_dir() and "BQ028" in p.name)
    for folder in package.rglob("*"):
        if folder.is_dir() and (folder / "10.jpg").exists() and (folder / "37.jpg").exists():
            return folder
    raise FileNotFoundError("Cannot locate BQ028 raw main image folder")


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


def text_fit(draw: ImageDraw.ImageDraw, text: str, max_width: int, start: int, bold: bool = False) -> ImageFont.ImageFont:
    size = start
    while size >= 18:
        fnt = font(size, bold)
        if draw.textlength(text, font=fnt) <= max_width:
            return fnt
        size -= 2
    return font(18, bold)


def draw_header(draw: ImageDraw.ImageDraw, title: str, subtitle: str) -> None:
    draw.text((76, 66), title, fill=(18, 25, 38), font=text_fit(draw, title, 1040, 47, True))
    draw.text((78, 132), subtitle, fill=(71, 85, 105), font=text_fit(draw, subtitle, 1040, 26))


def add_pills(draw: ImageDraw.ImageDraw, labels: list[str], accent: tuple[int, int, int]) -> None:
    x = 74
    y = 1030
    for label in labels:
        fnt = text_fit(draw, label, 280, 24, True)
        width = int(draw.textlength(label, font=fnt)) + 42
        draw.rounded_rectangle((x, y, x + width, y + 50), radius=25, fill=accent)
        draw.text((x + 21, y + 13), label, fill=(255, 255, 255), font=fnt)
        x += width + 18


def paste_cover(canvas: Image.Image, image: Image.Image, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    tw, th = x1 - x0, y1 - y0
    scale = max(tw / image.width, th / image.height)
    resized = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - tw) // 2)
    top = max(0, (resized.height - th) // 2)
    canvas.paste(resized.crop((left, top, left + tw, top + th)), (x0, y0))


def paste_contain(canvas: Image.Image, image: Image.Image, box: tuple[int, int, int, int], pad: int = 16) -> None:
    x0, y0, x1, y1 = box
    pic = image.copy()
    pic.thumbnail((x1 - x0 - pad * 2, y1 - y0 - pad * 2), Image.Resampling.LANCZOS)
    x = x0 + pad + (x1 - x0 - pad * 2 - pic.width) // 2
    y = y0 + pad + (y1 - y0 - pad * 2 - pic.height) // 2
    canvas.paste(pic, (x, y))


def feature_image(
    out: Path,
    source_name: str,
    title: str,
    subtitle: str,
    labels: list[str],
    accent: tuple[int, int, int],
    mode: str = "cover",
) -> None:
    canvas = Image.new("RGB", (1200, 1200), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    draw_header(draw, title, subtitle)
    image = open_source(source_name)
    box = (76, 250, 1124, 960)
    if mode == "contain":
        draw.rounded_rectangle((62, 238, 1138, 976), radius=24, fill=(248, 250, 252))
        paste_contain(canvas, image, box, pad=18)
    else:
        paste_cover(canvas, image, box)
    add_pills(draw, labels, accent)
    save_jpg(canvas, out, quality=95)


def backup_current() -> None:
    for file_name in ROLE_FILES:
        src = MAIN_DIR / file_name
        if src.exists():
            dst = BACKUP_DIR / "01_主图" / file_name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def build_gallery_roles() -> None:
    feature_image(
        MAIN_DIR / "02_upper.jpg",
        "10.jpg",
        "KNIT UPPER & TOE DETAIL",
        "Close-up photo for upper texture and toe construction check",
        ["Knit Upper", "Toe Detail", "Real Photo"],
        (18, 118, 99),
    )
    feature_image(
        MAIN_DIR / "03_fit.jpg",
        "37.jpg",
        "EASY SLIP-ON FIT",
        "On-foot photo showing low-cut opening and pull-on use",
        ["Slip-On", "EU 35-45", "Sample Check"],
        (37, 99, 235),
    )
    feature_image(
        MAIN_DIR / "04_sole.jpg",
        "11.jpg",
        "BISCUIT SOLE TEXTURE",
        "Real outsole texture from the source package",
        ["Sole Texture", "Source Photo", "Buyer Check"],
        (124, 58, 237),
    )
    feature_image(
        MAIN_DIR / "06_scene.jpg",
        "31.jpg",
        "CASUAL WALKING SCENE",
        "Blue colorway on-foot photo for daily wear display",
        ["Daily Wear", "Color Option", "Wholesale"],
        (217, 119, 6),
        mode="contain",
    )


def make_preview(out: Path) -> None:
    files = ["01_main.jpg", "02_upper.jpg", "03_fit.jpg", "04_sole.jpg", "05_colors.jpg", "06_scene.jpg"]
    cols = 3
    cell_w, cell_h = 330, 390
    canvas = Image.new("RGB", (cols * cell_w, 2 * cell_h), "white")
    draw = ImageDraw.Draw(canvas)
    for i, file_name in enumerate(files):
        path = MAIN_DIR / file_name
        image = Image.open(path).convert("RGB")
        image.thumbnail((300, 320), Image.Resampling.LANCZOS)
        x = (i % cols) * cell_w
        y = (i // cols) * cell_h
        draw.text((x + 12, y + 10), file_name, fill=(0, 0, 0), font=font(14, True))
        canvas.paste(image, (x + (cell_w - image.width) // 2, y + 45))
    save_jpg(canvas, out, quality=92)


def main() -> None:
    backup_current()
    build_gallery_roles()
    make_preview(PREVIEW_DIR / "bq028_gallery_role_fix_applied.jpg")
    print("BQ028 main gallery role images fixed")
    print(f"backup={BACKUP_DIR}")
    print(f"preview={PREVIEW_DIR / 'bq028_gallery_role_fix_applied.jpg'}")


if __name__ == "__main__":
    main()
