from __future__ import annotations

from pathlib import Path
import argparse
import io
import re
import shutil

from PIL import Image, ImageDraw, ImageEnhance, ImageFont


PRODUCT = "BQ016_201"
ROLE_FILES = ["02_upper.jpg", "03_fit.jpg", "04_sole.jpg", "05_colors.jpg", "06_scene.jpg"]


def workspace_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "AGENTS.md").exists() and any(p.is_dir() and p.name.startswith("02_") for p in cwd.iterdir()):
        return cwd
    return Path(__file__).resolve().parents[2]


ROOT = workspace_root()
RAW_ROOT = next(p for p in ROOT.iterdir() if p.is_dir() and p.name.startswith("01_"))
UPLOAD_ROOT = next(p for p in next(p for p in ROOT.iterdir() if p.is_dir() and p.name.startswith("02_")).iterdir() if p.is_dir() and p.name.startswith("00_"))
ARCHIVE_ROOT = next(p for p in next(p for p in ROOT.iterdir() if p.is_dir() and p.name.startswith("02_")).iterdir() if p.is_dir() and p.name.startswith("99_"))
QA_ROOT = ARCHIVE_ROOT / "BQ016_gallery_role_fix_20260621"
CANDIDATE_DIR = QA_ROOT / "candidates"
BACKUP_DIR = QA_ROOT / "backups"


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def natural_key(path: Path) -> list[object]:
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", path.name)]


def save_jpg(image: Image.Image, path: Path, quality: int = 95) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "JPEG", quality=quality, optimize=True, subsampling=1)
    path.write_bytes(buffer.getvalue())


def raw_folder() -> Path:
    return next(p for p in RAW_ROOT.iterdir() if p.is_dir() and "BQ016" in p.name)


def product_main_dir() -> Path:
    product_dir = UPLOAD_ROOT / PRODUCT
    return next(p for p in product_dir.iterdir() if p.is_dir() and p.name.startswith("01_"))


def find_raw_image(file_name: str, parent_name: str | None = None, size: tuple[int, int] | None = None) -> Path:
    matches = sorted(
        [p for p in raw_folder().rglob(file_name) if p.is_file()],
        key=natural_key,
    )
    if parent_name:
        matches = [p for p in matches if p.parent.name == parent_name]
    if size:
        sized: list[Path] = []
        for path in matches:
            try:
                with Image.open(path) as image:
                    if image.size == size:
                        sized.append(path)
            except OSError:
                continue
        matches = sized
    if not matches:
        raise FileNotFoundError(f"Missing source image: {parent_name or '*'} / {file_name}")
    return matches[0]


def text_fit(draw: ImageDraw.ImageDraw, text: str, max_width: int, start: int, bold: bool = False) -> ImageFont.ImageFont:
    size = start
    while size >= 18:
        font = load_font(size, bold)
        if draw.textlength(text, font=font) <= max_width:
            return font
        size -= 2
    return load_font(18, bold)


def add_header(draw: ImageDraw.ImageDraw, title: str, subtitle: str) -> None:
    title_font = text_fit(draw, title, 1040, 52, True)
    subtitle_font = text_fit(draw, subtitle, 1040, 28)
    draw.text((76, 68), title, fill=(18, 25, 38), font=title_font)
    draw.text((78, 138), subtitle, fill=(75, 85, 99), font=subtitle_font)


def add_pills(draw: ImageDraw.ImageDraw, labels: list[str], accent: tuple[int, int, int]) -> None:
    x = 74
    y = 1030
    for label in labels:
        font = text_fit(draw, label, 280, 24, True)
        width = int(draw.textlength(label, font=font)) + 42
        if x + width > 1128:
            break
        draw.rounded_rectangle((x, y, x + width, y + 50), radius=25, fill=accent)
        draw.text((x + 21, y + 13), label, fill=(255, 255, 255), font=font)
        x += width + 18


def paste_contain(canvas: Image.Image, src: Image.Image, box: tuple[int, int, int, int], pad: int = 0) -> None:
    x0, y0, x1, y1 = box
    max_w = x1 - x0 - pad * 2
    max_h = y1 - y0 - pad * 2
    image = src.convert("RGB")
    image.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    x = x0 + pad + (max_w - image.width) // 2
    y = y0 + pad + (max_h - image.height) // 2
    canvas.paste(image, (x, y))


def paste_cover(canvas: Image.Image, src: Image.Image, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    target_w = x1 - x0
    target_h = y1 - y0
    image = src.convert("RGB")
    scale = max(target_w / image.width, target_h / image.height)
    image = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.Resampling.LANCZOS)
    left = max(0, (image.width - target_w) // 2)
    top = max(0, (image.height - target_h) // 2)
    image = image.crop((left, top, left + target_w, top + target_h))
    canvas.paste(image, (x0, y0))


def source_crop(path: Path, box: tuple[int, int, int, int] | None = None) -> Image.Image:
    image = Image.open(path).convert("RGB")
    if box:
        image = image.crop(box)
    image = ImageEnhance.Contrast(image).enhance(1.03)
    image = ImageEnhance.Sharpness(image).enhance(1.04)
    return image


def feature_image(
    out: Path,
    source: Path,
    crop: tuple[int, int, int, int],
    title: str,
    subtitle: str,
    labels: list[str],
    accent: tuple[int, int, int],
    mode: str = "cover",
) -> None:
    canvas = Image.new("RGB", (1200, 1200), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    add_header(draw, title, subtitle)
    image = source_crop(source, crop)
    box = (78, 260, 1122, 955)
    if mode == "contain":
        draw.rounded_rectangle((64, 246, 1136, 970), radius=24, fill=(248, 250, 252))
        paste_contain(canvas, image, box, pad=18)
    else:
        paste_cover(canvas, image, box)
    add_pills(draw, labels, accent)
    save_jpg(canvas, out)


def color_grid(out: Path) -> None:
    colors = [
        ("Black", find_raw_image("20.jpg", size=(800, 800)), (40, 170, 760, 600), (18, 18, 18)),
        ("Pink", find_raw_image("13.jpg", size=(800, 800)), (34, 175, 766, 610), (234, 175, 194)),
        ("Grey Stripe", find_raw_image("001.jpg", size=(800, 800)), (30, 110, 770, 660), (154, 161, 164)),
        ("Black White", find_raw_image("18.jpg", size=(800, 800)), (58, 105, 742, 640), (34, 34, 34)),
    ]
    canvas = Image.new("RGB", (1200, 1200), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    add_header(draw, "ACTUAL COLOR OPTIONS", "Color photos from the source package for buyer checking")
    slots = [(76, 260, 572, 560), (628, 260, 1124, 560), (76, 660, 572, 960), (628, 660, 1124, 960)]
    for (label, path, crop, swatch), box in zip(colors, slots):
        draw.rounded_rectangle(box, radius=24, fill=(248, 250, 252), outline=(226, 232, 240), width=2)
        with Image.open(path) as opened:
            image = opened.convert("RGB").crop(crop)
        paste_contain(canvas, image, (box[0] + 24, box[1] + 22, box[2] - 24, box[3] - 74), pad=0)
        draw.ellipse((box[0] + 28, box[3] - 50, box[0] + 58, box[3] - 20), fill=swatch, outline=(148, 163, 184))
        draw.text((box[0] + 72, box[3] - 51), label, fill=(30, 41, 59), font=load_font(25, True))
    add_pills(draw, ["Mixed Colors", "EU 31-40", "Sample Check"], (18, 118, 99))
    save_jpg(canvas, out)


def copy_hero_for_candidate() -> None:
    main_dir = product_main_dir()
    shutil.copy2(main_dir / "01_main.jpg", CANDIDATE_DIR / "01_main.jpg")


def make_candidates() -> None:
    CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
    copy_hero_for_candidate()

    feature_image(
        CANDIDATE_DIR / "02_upper.jpg",
        find_raw_image("1_03.jpg", parent_name="790"),
        (0, 330, 790, 925),
        "BREATHABLE KNIT UPPER",
        "Close-up texture proof from the real product photo",
        ["Knit Texture", "Soft Textile", "Daily Comfort"],
        (18, 118, 99),
    )
    feature_image(
        CANDIDATE_DIR / "03_fit.jpg",
        find_raw_image("1_08.jpg", parent_name="790"),
        (18, 16, 772, 724),
        "EASY PULL-ON FIT",
        "Slip-on opening for school and daily casual wear",
        ["Slip-On", "Easy Wear", "EU 31-40"],
        (37, 99, 235),
        mode="contain",
    )
    feature_image(
        CANDIDATE_DIR / "04_sole.jpg",
        find_raw_image("1_06.jpg", parent_name="790"),
        (0, 205, 790, 830),
        "TEXTURED CUSHION SOLE",
        "Visible sole pattern for daily walking use",
        ["Textured Bottom", "Cushion Feel", "Stable Step"],
        (124, 58, 237),
    )
    color_grid(CANDIDATE_DIR / "05_colors.jpg")
    feature_image(
        CANDIDATE_DIR / "06_scene.jpg",
        find_raw_image("1_09.jpg", parent_name="790"),
        (22, 18, 768, 654),
        "SCHOOL & DAILY WALKING",
        "For kids, girls and small-size casual shoe markets",
        ["School", "Casual Wear", "Sample Check"],
        (217, 119, 6),
        mode="contain",
    )


def make_overview(out: Path, applied: bool = False) -> None:
    files = ["01_main.jpg"] + ROLE_FILES
    row_labels = ["Before", "Candidate"] if not applied else ["Applied"]
    rows = len(row_labels)
    cell_w = 190
    cell_h = 236
    left = 124
    top = 78
    canvas = Image.new("RGB", (left + cell_w * len(files) + 20, top + cell_h * rows + 28), "white")
    draw = ImageDraw.Draw(canvas)
    title = "BQ016 gallery role rebuild - applied" if applied else "BQ016 gallery role rebuild - candidate check"
    draw.text((14, 18), title, fill=(18, 25, 38), font=load_font(22, True))
    for col, file_name in enumerate(files):
        draw.text((left + col * cell_w + 42, 50), Path(file_name).stem, fill=(71, 85, 105), font=load_font(13, True))
    for row, row_label in enumerate(row_labels):
        y = top + row * cell_h
        draw.text((18, y + 82), row_label, fill=(30, 41, 59), font=load_font(15, True))
        for col, file_name in enumerate(files):
            path = product_main_dir() / file_name if (applied or row_label == "Before") else CANDIDATE_DIR / file_name
            with Image.open(path) as opened:
                image = opened.convert("RGB")
            image.thumbnail((cell_w - 14, cell_w - 14), Image.Resampling.LANCZOS)
            x = left + col * cell_w + (cell_w - image.width) // 2
            canvas.paste(image, (x, y + 10))
    save_jpg(canvas, out, quality=93)


def apply_candidates() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    main_dir = product_main_dir()
    for file_name in ROLE_FILES:
        src = CANDIDATE_DIR / file_name
        dst = main_dir / file_name
        backup = BACKUP_DIR / f"{Path(file_name).stem}_before_role_fix.jpg"
        if not backup.exists():
            shutil.copy2(dst, backup)
        shutil.copy2(src, dst)


def run(apply: bool) -> None:
    QA_ROOT.mkdir(parents=True, exist_ok=True)
    make_candidates()
    make_overview(QA_ROOT / "bq016_gallery_role_candidates.jpg", applied=False)
    if apply:
        apply_candidates()
        make_overview(QA_ROOT / "bq016_gallery_role_applied.jpg", applied=True)
    print(f"product={PRODUCT} apply={apply}")
    print(f"qa={QA_ROOT}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="replace BQ016 main gallery role images")
    args = parser.parse_args()
    run(apply=args.apply)
