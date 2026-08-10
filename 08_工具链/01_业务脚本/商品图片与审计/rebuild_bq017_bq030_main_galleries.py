from __future__ import annotations

from pathlib import Path
import argparse
import importlib.util
import io
import re
import shutil
import sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFont


TARGET_RE = re.compile(r"^BQ0(1[7-9]|2[0-9]|30)_")
GALLERY_FILES = ["01_main.jpg", "02_upper.jpg", "03_fit.jpg", "04_sole.jpg", "05_colors.jpg", "06_scene.jpg"]
REPLACE_FILES = ["02_upper.jpg", "03_fit.jpg", "04_sole.jpg", "05_colors.jpg", "06_scene.jpg"]
ROLE_FILES = ["02_upper.jpg", "03_fit.jpg", "04_sole.jpg", "06_scene.jpg"]


def workspace_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "AGENTS.md").exists() and any(p.is_dir() and p.name.startswith("02_") for p in cwd.iterdir()):
        return cwd
    return Path(__file__).resolve().parents[2]


ROOT = workspace_root()
UPLOAD_PARENT = next(p for p in ROOT.iterdir() if p.is_dir() and p.name.startswith("02_"))
UPLOAD_ROOT = next(p for p in UPLOAD_PARENT.iterdir() if p.is_dir() and p.name.startswith("00_"))
ARCHIVE_ROOT = next(p for p in UPLOAD_PARENT.iterdir() if p.is_dir() and p.name.startswith("99_"))
QA_ROOT = ARCHIVE_ROOT / "BQ017_BQ030_gallery_rebuild_20260621"
CANDIDATE_ROOT = QA_ROOT / "candidates"
BACKUP_ROOT = QA_ROOT / "backups"
ORG_SCRIPT = Path(__file__).with_name("organize_20260616_new_packages.py")


# 1-based source_manifest index selection. These are chosen to avoid repeating the
# same central product image and to stay close to each product's visible evidence.
SOURCE_MAP: dict[str, dict[str, int]] = {
    "BQ017_A008": {"upper": 6, "fit": 5, "sole": 13, "scene": 15},
    "BQ018_A116": {"upper": 13, "fit": 14, "sole": 10, "scene": 15},
    "BQ019_A206": {"upper": 1, "fit": 5, "sole": 4, "scene": 6},
    "BQ020_A218": {"upper": 2, "fit": 5, "sole": 10, "scene": 12},
    "BQ021_K6212": {"upper": 1, "fit": 12, "sole": 7, "scene": 14},
    "BQ022_A2208": {"upper": 3, "fit": 8, "sole": 6, "scene": 11},
    "BQ023_A505": {"upper": 4, "fit": 7, "sole": 6, "scene": 12},
    "BQ024_A830": {"upper": 1, "fit": 4, "sole": 15, "scene": 3},
    "BQ025_A1689": {"upper": 4, "fit": 6, "sole": 14, "scene": 11},
    "BQ026_T5828": {"upper": 1, "fit": 6, "sole": 3, "scene": 8},
    "BQ027_K6116": {"upper": 1, "fit": 5, "sole": 14, "scene": 12},
    "BQ028_BISCUIT": {"upper": 3, "fit": 2, "sole": 13, "scene": 8},
    "BQ029_A025": {"upper": 3, "fit": 6, "sole": 4, "scene": 12},
    "BQ030_A811": {"upper": 1, "fit": 10, "sole": 11, "scene": 4},
}

DIRECT_SOURCE_FILES: dict[str, dict[str, str]] = {
    "BQ028_BISCUIT": {
        "upper": "10.jpg",
        "fit": "37.jpg",
        "sole": "11.jpg",
        "scene": "31.jpg",
    },
}

TITLE_OVERRIDES: dict[str, dict[str, str]] = {
    "BQ026_T5828": {"sole": "LIGHTWEIGHT WALKING SOLE"},
}


ACCENTS = {
    "upper": (18, 118, 99),
    "fit": (37, 99, 235),
    "sole": (124, 58, 237),
    "scene": (217, 119, 6),
    "colors": (18, 118, 99),
}


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


def text_fit(draw: ImageDraw.ImageDraw, text: str, max_width: int, start: int, bold: bool = False) -> ImageFont.ImageFont:
    size = start
    while size >= 18:
        font = load_font(size, bold)
        if draw.textlength(text, font=font) <= max_width:
            return font
        size -= 2
    return load_font(18, bold)


def save_jpg(image: Image.Image, path: Path, quality: int = 95) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "JPEG", quality=quality, optimize=True, subsampling=1)
    path.write_bytes(buffer.getvalue())


def product_dirs() -> list[Path]:
    return sorted([p for p in UPLOAD_ROOT.iterdir() if p.is_dir() and TARGET_RE.match(p.name)], key=lambda p: p.name)


def main_dir(product_dir: Path) -> Path:
    return next(p for p in product_dir.iterdir() if p.is_dir() and p.name.startswith("01_"))


def color_dir(product_dir: Path) -> Path | None:
    dirs = [p for p in product_dir.iterdir() if p.is_dir() and p.name.startswith("03_")]
    return dirs[0] if dirs else None


def ref_dir(product_dir: Path) -> Path:
    return next(p for p in product_dir.iterdir() if p.is_dir() and p.name.startswith("04_"))


def manifest_paths(product_dir: Path) -> list[Path]:
    manifest = ref_dir(product_dir) / "source_manifest.txt"
    paths: list[Path] = []
    for line in manifest.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line:
            paths.append(ROOT / line)
    return paths


def source_for(product_dir: Path, role: str) -> Path:
    paths = manifest_paths(product_dir)
    direct_name = DIRECT_SOURCE_FILES.get(product_dir.name, {}).get(role)
    if direct_name and paths:
        direct = paths[0].parent / direct_name
        if direct.exists():
            return direct
    index = SOURCE_MAP.get(product_dir.name, {}).get(role, 1)
    if not paths:
        raise RuntimeError(f"No source manifest for {product_dir.name}")
    return paths[max(0, min(len(paths) - 1, index - 1))]


def load_metadata() -> dict[str, object]:
    spec = importlib.util.spec_from_file_location("newpkg_metadata_rebuild", ORG_SCRIPT)
    if spec is None or spec.loader is None:
        return {}
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return {product.folder_name: product for product in module.PRODUCTS}


def enhance(image: Image.Image) -> Image.Image:
    image = image.convert("RGB")
    image = ImageEnhance.Contrast(image).enhance(1.025)
    image = ImageEnhance.Sharpness(image).enhance(1.045)
    return ImageEnhance.Color(image).enhance(1.01)


def add_header(draw: ImageDraw.ImageDraw, title: str, subtitle: str) -> None:
    title_font = text_fit(draw, title, 1030, 46, True)
    subtitle_font = text_fit(draw, subtitle, 1040, 27)
    draw.text((76, 66), title, fill=(18, 25, 38), font=title_font)
    draw.text((78, 132), subtitle, fill=(75, 85, 99), font=subtitle_font)


def add_pills(draw: ImageDraw.ImageDraw, labels: list[str], accent: tuple[int, int, int]) -> None:
    x = 74
    y = 1030
    for label in labels:
        font = text_fit(draw, label, 285, 24, True)
        width = int(draw.textlength(label, font=font)) + 42
        if x + width > 1130:
            break
        draw.rounded_rectangle((x, y, x + width, y + 50), radius=25, fill=accent)
        draw.text((x + 21, y + 13), label, fill=(255, 255, 255), font=font)
        x += width + 18


def paste_cover(canvas: Image.Image, src: Image.Image, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    target_w = x1 - x0
    target_h = y1 - y0
    image = enhance(src)
    scale = max(target_w / max(1, image.width), target_h / max(1, image.height))
    image = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.Resampling.LANCZOS)
    left = max(0, (image.width - target_w) // 2)
    top = max(0, (image.height - target_h) // 2)
    canvas.paste(image.crop((left, top, left + target_w, top + target_h)), (x0, y0))


def paste_contain(canvas: Image.Image, src: Image.Image, box: tuple[int, int, int, int], pad: int = 16) -> None:
    x0, y0, x1, y1 = box
    max_w = x1 - x0 - pad * 2
    max_h = y1 - y0 - pad * 2
    image = enhance(src)
    image.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    x = x0 + pad + (max_w - image.width) // 2
    y = y0 + pad + (max_h - image.height) // 2
    canvas.paste(image, (x, y))


def opened(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGB")


def make_feature(
    product_dir: Path,
    product: object,
    role: str,
    out: Path,
    title: str,
    subtitle: str,
    labels: list[str],
    mode: str,
) -> None:
    canvas = Image.new("RGB", (1200, 1200), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    title = TITLE_OVERRIDES.get(product_dir.name, {}).get(role, title)
    add_header(draw, title, subtitle)
    source = opened(source_for(product_dir, role))
    panel = (76, 252, 1124, 952)
    if mode == "contain":
        draw.rounded_rectangle((62, 240, 1138, 970), radius=24, fill=(248, 250, 252))
        paste_contain(canvas, source, panel, pad=18)
    else:
        paste_cover(canvas, source, panel)
    add_pills(draw, labels, ACCENTS[role])
    save_jpg(canvas, out)


def normalize_name(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def color_image_map(product_dir: Path) -> dict[str, Path]:
    folder = color_dir(product_dir)
    if folder is None:
        return {}
    return {path.stem.lower(): path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}}


def pick_color_path(product_dir: Path, label: str, fallback_index: int) -> Path:
    color_map = color_image_map(product_dir)
    key = normalize_name(label)
    if key in color_map:
        return color_map[key]
    compact = key.replace("_", "")
    for stem, path in color_map.items():
        if stem.replace("_", "") == compact or compact in stem.replace("_", ""):
            return path
    paths = manifest_paths(product_dir)
    return paths[min(fallback_index, len(paths) - 1)]


def make_color_grid(product_dir: Path, product: object, out: Path) -> None:
    canvas = Image.new("RGB", (1200, 1200), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    add_header(draw, "ACTUAL COLOR OPTIONS", "Color photos from the source package for buyer checking")
    slots = [(76, 250, 572, 548), (628, 250, 1124, 548), (76, 644, 572, 942), (628, 644, 1124, 942)]
    colors = getattr(product, "colors", [])[:4]
    for i, (label, swatch) in enumerate(colors):
        box = slots[i]
        draw.rounded_rectangle(box, radius=24, fill=(248, 250, 252), outline=(226, 232, 240), width=2)
        image = opened(pick_color_path(product_dir, label, i))
        paste_contain(canvas, image, (box[0] + 22, box[1] + 18, box[2] - 22, box[3] - 72), pad=0)
        draw.ellipse((box[0] + 28, box[3] - 50, box[0] + 58, box[3] - 20), fill=swatch, outline=(148, 163, 184))
        draw.text((box[0] + 72, box[3] - 51), label, fill=(30, 41, 59), font=text_fit(draw, label, 340, 25, True))
    add_pills(draw, ["Mixed Colors", getattr(product, "size_range", "Size Range"), "Sample Check"], ACCENTS["colors"])
    save_jpg(canvas, out)


def scene_title(product_dir: Path, product: object) -> str:
    if "Kids" in getattr(product, "group", ""):
        return "SCHOOL & DAILY WALKING"
    if "Winter" in getattr(product, "group", "") or "High Top" in getattr(product, "group", ""):
        return "AUTUMN WINTER CASUAL"
    if "Men " in getattr(product, "group", ""):
        return "MEN DAILY WALKING"
    return "DAILY WALKING USE"


def make_product_candidates(product_dir: Path, product: object) -> None:
    out_dir = CANDIDATE_ROOT / product_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(main_dir(product_dir) / "01_main.jpg", out_dir / "01_main.jpg")
    make_feature(
        product_dir,
        product,
        "upper",
        out_dir / "02_upper.jpg",
        getattr(product, "feature_title", "UPPER DETAIL"),
        getattr(product, "upper", "Real product upper detail"),
        ["Real Photo", "Upper Detail", "B2B Check"],
        "cover",
    )
    make_feature(
        product_dir,
        product,
        "fit",
        out_dir / "03_fit.jpg",
        getattr(product, "fit_title", "FIT DETAIL"),
        f"{getattr(product, 'closure', 'Closure')} closure, {getattr(product, 'size_range', 'size range')}",
        [getattr(product, "closure", "Fit"), getattr(product, "size_range", "Size Range"), "Easy Fit"],
        "contain",
    )
    make_feature(
        product_dir,
        product,
        "sole",
        out_dir / "04_sole.jpg",
        getattr(product, "sole_title", "SOLE DETAIL"),
        "Visible sole or side structure from source photo",
        ["Sole Detail", "Cushion Feel", "Stable Step"],
        "cover",
    )
    make_color_grid(product_dir, product, out_dir / "05_colors.jpg")
    make_feature(
        product_dir,
        product,
        "scene",
        out_dir / "06_scene.jpg",
        scene_title(product_dir, product),
        getattr(product, "application", "Daily walking, commuting and casual wear"),
        ["Daily Use", "Sample Check", "Wholesale"],
        "contain",
    )


def make_overview(products: list[Path], out: Path, applied: bool) -> None:
    thumb = 150
    label_h = 44
    left = 170
    top = 92
    canvas = Image.new("RGB", (left + len(GALLERY_FILES) * thumb + 24, top + len(products) * (thumb + label_h) + 24), "white")
    draw = ImageDraw.Draw(canvas)
    title = "BQ017-BQ030 rebuilt gallery - applied" if applied else "BQ017-BQ030 rebuilt gallery - candidates"
    draw.text((16, 16), title, fill=(18, 25, 38), font=load_font(21, True))
    for col, file_name in enumerate(GALLERY_FILES):
        draw.text((left + col * thumb + 32, 58), Path(file_name).stem, fill=(71, 85, 105), font=load_font(13, True))
    for row, product_dir in enumerate(products):
        y = top + row * (thumb + label_h)
        draw.text((12, y + 58), product_dir.name, fill=(30, 41, 59), font=load_font(13, True))
        folder = main_dir(product_dir) if applied else CANDIDATE_ROOT / product_dir.name
        for col, file_name in enumerate(GALLERY_FILES):
            path = folder / file_name
            if not path.exists():
                continue
            image = opened(path)
            image.thumbnail((thumb - 12, thumb - 12), Image.Resampling.LANCZOS)
            x = left + col * thumb + (thumb - image.width) // 2
            canvas.paste(image, (x, y + 6))
    save_jpg(canvas, out, quality=93)


def apply_candidates(products: list[Path]) -> None:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    for product_dir in products:
        backup_dir = BACKUP_ROOT / product_dir.name
        backup_dir.mkdir(parents=True, exist_ok=True)
        src_dir = CANDIDATE_ROOT / product_dir.name
        dst_dir = main_dir(product_dir)
        for file_name in REPLACE_FILES:
            src = src_dir / file_name
            dst = dst_dir / file_name
            backup = backup_dir / f"{Path(file_name).stem}_before_role_rebuild.jpg"
            if not backup.exists():
                shutil.copy2(dst, backup)
            shutil.copy2(src, dst)


def run(apply: bool) -> None:
    QA_ROOT.mkdir(parents=True, exist_ok=True)
    metadata = load_metadata()
    products = product_dirs()
    for product_dir in products:
        product = metadata.get(product_dir.name)
        if product is None:
            raise RuntimeError(f"Missing product metadata: {product_dir.name}")
        make_product_candidates(product_dir, product)
    make_overview(products, QA_ROOT / "bq017_bq030_gallery_candidates.jpg", applied=False)
    if apply:
        apply_candidates(products)
        make_overview(products, QA_ROOT / "bq017_bq030_gallery_applied.jpg", applied=True)
    print(f"products={len(products)} apply={apply}")
    print(f"qa={QA_ROOT}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="replace BQ017-BQ030 main gallery role images")
    args = parser.parse_args()
    run(apply=args.apply)
