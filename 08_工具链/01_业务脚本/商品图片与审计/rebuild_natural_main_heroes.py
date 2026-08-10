from __future__ import annotations

from pathlib import Path
import argparse
import importlib.util
import io
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


def workspace_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "AGENTS.md").exists() and any(p.is_dir() and p.name.startswith("02_") for p in cwd.iterdir()):
        return cwd
    return Path(__file__).resolve().parents[2]


ROOT = workspace_root()
UPLOAD_PARENT = next(p for p in ROOT.iterdir() if p.is_dir() and p.name.startswith("02_"))
UPLOAD_ROOT = next(p for p in UPLOAD_PARENT.iterdir() if p.is_dir() and p.name.startswith("00_"))
ARCHIVE_ROOT = next(p for p in UPLOAD_PARENT.iterdir() if p.is_dir() and p.name.startswith("99_"))
OLD_BACKUP_ROOT = ARCHIVE_ROOT / "main_hero_refine_20260619" / "before_backups"
QA_ROOT = ARCHIVE_ROOT / "main_hero_natural_fix_20260620"
RAW_ROOT = next(p for p in ROOT.iterdir() if p.is_dir() and p.name.startswith("01_"))
ORG_SCRIPT = Path(__file__).with_name("organize_20260616_new_packages.py")

MAIN_GALLERY_FILES = ["01_main.jpg", "02_upper.jpg", "03_fit.jpg", "04_sole.jpg", "06_scene.jpg"]


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


def product_dirs() -> list[Path]:
    dirs: list[Path] = []
    for item in sorted(UPLOAD_ROOT.iterdir(), key=lambda p: p.name):
        if not item.is_dir() or not item.name.startswith("BQ"):
            continue
        try:
            number = int(item.name[2:5])
        except ValueError:
            continue
        if 16 <= number <= 30:
            dirs.append(item)
    return dirs


def main_image_path(product_dir: Path) -> Path:
    return main_dir_path(product_dir) / "01_main.jpg"


def main_dir_path(product_dir: Path) -> Path:
    return next(p for p in product_dir.iterdir() if p.is_dir() and p.name.startswith("01_"))


def source_image_path(product_dir: Path) -> Path:
    if product_dir.name == "BQ016_201":
        matches = list(RAW_ROOT.rglob("27.jpg"))
        matches = [p for p in matches if "BQ016" in str(p)]
        if matches:
            return matches[0]
    if product_dir.name == "BQ028_BISCUIT":
        matches = list(RAW_ROOT.rglob("12.jpg"))
        matches = [p for p in matches if "BQ028" in str(p) and p.parent.name == "\u4e3b\u56fe"]
        if matches:
            return matches[0]
    old_backup = OLD_BACKUP_ROOT / f"{product_dir.name}_01_main_before.jpg"
    if old_backup.exists():
        return old_backup
    return main_image_path(product_dir)


def otsu_threshold(values: np.ndarray) -> float:
    clipped = np.clip(values, 0, 255).astype(np.uint8)
    hist = np.bincount(clipped.ravel(), minlength=256).astype(np.float64)
    total = clipped.size
    if total == 0:
        return 30.0
    cumulative = np.cumsum(hist)
    cumulative_mean = np.cumsum(hist * np.arange(256))
    global_mean = cumulative_mean[-1]
    denom = cumulative * (total - cumulative)
    denom[denom == 0] = 1
    variance = (global_mean * cumulative - cumulative_mean * total) ** 2 / denom
    return float(np.argmax(variance))


def foreground_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    small = image.convert("RGB")
    small.thumbnail((620, 620), Image.Resampling.LANCZOS)
    arr = np.asarray(small).astype(np.float32)
    h, w, _ = arr.shape
    border_size = max(10, min(h, w) // 35)
    border = np.concatenate(
        [
            arr[:border_size].reshape(-1, 3),
            arr[-border_size:].reshape(-1, 3),
            arr[:, :border_size].reshape(-1, 3),
            arr[:, -border_size:].reshape(-1, 3),
        ]
    )
    bg = np.median(border, axis=0)
    bg_luma = float(np.dot(bg, [0.299, 0.587, 0.114]))
    bg_sat = float(np.median(border.max(axis=1) - border.min(axis=1)))

    luma = arr[..., 0] * 0.299 + arr[..., 1] * 0.587 + arr[..., 2] * 0.114
    sat = arr.max(axis=2) - arr.min(axis=2)
    dist = np.linalg.norm(arr - bg, axis=2)
    edge = np.zeros_like(luma)
    edge[:, 1:] = np.maximum(edge[:, 1:], np.abs(luma[:, 1:] - luma[:, :-1]))
    edge[1:, :] = np.maximum(edge[1:, :], np.abs(luma[1:, :] - luma[:-1, :]))

    threshold = max(10.0, min(56.0, otsu_threshold(dist) * 0.62))
    fg = (
        (dist > threshold)
        | (luma < bg_luma - 18)
        | ((sat > bg_sat + 16) & (dist > 8))
        | ((edge > 7) & (luma < 248))
    )

    # Keep the product and its natural contact shadow, but ignore border noise.
    fg[:2, :] = False
    fg[-2:, :] = False
    fg[:, :2] = False
    fg[:, -2:] = False

    rows = np.where(fg.any(axis=1))[0]
    cols = np.where(fg.any(axis=0))[0]
    if len(rows) == 0 or len(cols) == 0:
        return (0, 0, image.width, image.height)

    x0 = int(cols[0] * image.width / w)
    x1 = int((cols[-1] + 1) * image.width / w)
    y0 = int(rows[0] * image.height / h)
    y1 = int((rows[-1] + 1) * image.height / h)

    bw = x1 - x0
    bh = y1 - y0
    pad_x = max(28, int(bw * 0.085))
    pad_top = max(26, int(bh * 0.10))
    pad_bottom = max(34, int(bh * 0.14))
    return (
        max(0, x0 - pad_x),
        max(0, y0 - pad_top),
        min(image.width, x1 + pad_x),
        min(image.height, y1 + pad_bottom),
    )


def canvas_color(crop: Image.Image) -> tuple[int, int, int]:
    arr = np.asarray(crop.convert("RGB")).astype(np.float32)
    h, w, _ = arr.shape
    b = max(8, min(h, w) // 18)
    border = np.concatenate(
        [
            arr[:b].reshape(-1, 3),
            arr[-b:].reshape(-1, 3),
            arr[:, :b].reshape(-1, 3),
            arr[:, -b:].reshape(-1, 3),
        ]
    )
    med = np.median(border, axis=0)
    luma = float(np.dot(med, [0.299, 0.587, 0.114]))
    sat = float(med.max() - med.min())
    if luma >= 214 and sat < 32:
        return (255, 255, 255)
    if luma >= 178 and sat < 42:
        value = int(max(236, min(248, luma + 18)))
        return (value, value, value)
    return (250, 250, 248)


def border_stats(crop: Image.Image) -> tuple[float, float, float]:
    arr = np.asarray(crop.convert("RGB")).astype(np.float32)
    h, w, _ = arr.shape
    b = max(8, min(h, w) // 18)
    border = np.concatenate(
        [
            arr[:b].reshape(-1, 3),
            arr[-b:].reshape(-1, 3),
            arr[:, :b].reshape(-1, 3),
            arr[:, -b:].reshape(-1, 3),
        ]
    )
    luma = border @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    sat = border.max(axis=1) - border.min(axis=1)
    return float(luma.mean()), float(luma.std()), float(sat.mean())


def soft_rect_mask(size: tuple[int, int], feather: int = 38) -> Image.Image:
    w, h = size
    mask = Image.new("L", (w, h), 255)
    if feather <= 0:
        return mask
    alpha = np.full((h, w), 255, dtype=np.float32)
    y = np.arange(h, dtype=np.float32)
    x = np.arange(w, dtype=np.float32)
    top = np.clip(y / feather, 0, 1)[:, None]
    bottom = np.clip((h - 1 - y) / feather, 0, 1)[:, None]
    left = np.clip(x / feather, 0, 1)[None, :]
    right = np.clip((w - 1 - x) / feather, 0, 1)[None, :]
    vertical = np.minimum(top, bottom)
    horizontal = np.minimum(left, right)
    alpha *= np.minimum(vertical, horizontal)
    return Image.fromarray(np.clip(alpha, 0, 255).astype(np.uint8), "L")


def soft_background(crop: Image.Image, size: tuple[int, int]) -> Image.Image:
    bg = crop.copy()
    bg.thumbnail(size, Image.Resampling.LANCZOS)
    cover = Image.new("RGB", size, canvas_color(crop))
    scale = max(size[0] / max(1, crop.width), size[1] / max(1, crop.height))
    bg = crop.resize((int(crop.width * scale) + 2, int(crop.height * scale) + 2), Image.Resampling.LANCZOS)
    x = (size[0] - bg.width) // 2
    y = (size[1] - bg.height) // 2
    cover.paste(bg, (x, y))
    cover = cover.filter(ImageFilter.GaussianBlur(28))
    cover = ImageEnhance.Color(cover).enhance(0.25)
    cover = ImageEnhance.Brightness(cover).enhance(1.14)
    white = Image.new("RGB", size, (255, 255, 255))
    return Image.blend(cover, white, 0.48)


FULL_SOURCE_PRODUCTS = {"BQ028_BISCUIT"}


def save_jpg(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "JPEG", quality=96, subsampling=1, optimize=True)
    path.write_bytes(buffer.getvalue())


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        trial = word if not line else f"{line} {word}"
        if draw.textlength(trial, font=font) <= width:
            line = trial
            continue
        if line:
            lines.append(line)
        line = word
    if line:
        lines.append(line)
    return lines


def text_fit(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    start: int,
    bold: bool = False,
) -> ImageFont.ImageFont:
    size = start
    while size >= 17:
        font = load_font(size, bold)
        if draw.textlength(text, font=font) <= max_width:
            return font
        size -= 2
    return load_font(17, bold)


def load_product_metadata() -> dict[str, object]:
    if not ORG_SCRIPT.exists():
        return {}
    spec = importlib.util.spec_from_file_location("beiqiang_newpkg_metadata", ORG_SCRIPT)
    if spec is None or spec.loader is None:
        return {}
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return {product.folder_name: product for product in module.PRODUCTS}


def candidate_name(product_name: str, file_name: str) -> str:
    return f"{product_name}_{Path(file_name).stem}_natural.jpg"


def full_source_hero(src: Path, dst: Path) -> None:
    image = Image.open(src).convert("RGB")
    if image.size != (1200, 1200):
        canvas = Image.new("RGB", (1200, 1200), canvas_color(image))
        scale = min(1200 / image.width, 1200 / image.height)
        resized = image.resize((int(image.width * scale), int(image.height * scale)), Image.Resampling.LANCZOS)
        canvas.paste(resized, ((1200 - resized.width) // 2, (1200 - resized.height) // 2))
        image = canvas
    image = ImageEnhance.Contrast(image).enhance(1.018)
    image = ImageEnhance.Sharpness(image).enhance(1.045)
    save_jpg(image, dst)


def natural_hero(src: Path, dst: Path, product_name: str) -> None:
    if product_name in FULL_SOURCE_PRODUCTS:
        full_source_hero(src, dst)
        return

    image = Image.open(src).convert("RGB")
    bbox = foreground_bbox(image)
    crop = image.crop(bbox)

    crop = ImageEnhance.Contrast(crop).enhance(1.025)
    crop = ImageEnhance.Sharpness(crop).enhance(1.06)
    crop = ImageEnhance.Color(crop).enhance(1.015)

    max_w = 1040
    max_h = 840
    scale = min(max_w / crop.width, max_h / crop.height)
    scale = min(scale, 1.55)
    new_size = (max(1, int(crop.width * scale)), max(1, int(crop.height * scale)))
    crop = crop.resize(new_size, Image.Resampling.LANCZOS)

    bg_luma, bg_std, bg_sat = border_stats(crop)
    use_soft_bg = bg_luma < 232 or bg_std > 8 or bg_sat > 22
    canvas = soft_background(crop, (1200, 1200)) if use_soft_bg else Image.new("RGB", (1200, 1200), canvas_color(crop))
    x = (1200 - crop.width) // 2
    y = int((1200 - crop.height) * 0.43)
    y = max(70, min(245, y))
    paste_mask = soft_rect_mask(crop.size, 42) if use_soft_bg else None
    canvas.paste(crop, (x, y), paste_mask)
    save_jpg(canvas, dst)


def natural_feature_base(src: Path, product_name: str) -> Image.Image:
    image = Image.open(src).convert("RGB")

    if product_name in FULL_SOURCE_PRODUCTS:
        canvas = Image.new("RGB", (1200, 1200), canvas_color(image))
        max_w = 1000
        max_h = 675
        scale = min(max_w / image.width, max_h / image.height)
        resized = image.resize(
            (max(1, int(image.width * scale)), max(1, int(image.height * scale))),
            Image.Resampling.LANCZOS,
        )
        x = (1200 - resized.width) // 2
        y = 300 + (675 - resized.height) // 2
        canvas.paste(resized, (x, y))
        return ImageEnhance.Sharpness(canvas).enhance(1.035)

    bbox = foreground_bbox(image)
    crop = image.crop(bbox)
    crop = ImageEnhance.Contrast(crop).enhance(1.025)
    crop = ImageEnhance.Sharpness(crop).enhance(1.06)
    crop = ImageEnhance.Color(crop).enhance(1.015)

    max_w = 1000
    max_h = 675
    scale = min(max_w / crop.width, max_h / crop.height)
    scale = min(scale, 1.45)
    crop = crop.resize(
        (max(1, int(crop.width * scale)), max(1, int(crop.height * scale))),
        Image.Resampling.LANCZOS,
    )

    bg_luma, bg_std, bg_sat = border_stats(crop)
    use_soft_bg = bg_luma < 232 or bg_std > 8 or bg_sat > 22
    canvas = soft_background(crop, (1200, 1200)) if use_soft_bg else Image.new("RGB", (1200, 1200), canvas_color(crop))
    x = (1200 - crop.width) // 2
    y = 300 + (675 - crop.height) // 2
    y = max(258, min(450, y))
    paste_mask = soft_rect_mask(crop.size, 42) if use_soft_bg else None
    canvas.paste(crop, (x, y), paste_mask)
    return canvas


def add_text_panel(
    image: Image.Image,
    title: str,
    subtitle: str,
    labels: list[str],
    accent: tuple[int, int, int],
) -> Image.Image:
    canvas = image.convert("RGBA")
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle((48, 48, 1152, 236), radius=26, fill=(255, 255, 255, 226))
    title_font = text_fit(draw, title, 980, 48, True)
    subtitle_font = text_fit(draw, subtitle, 980, 27)
    draw.text((82, 72), title, fill=(22, 31, 43), font=title_font)
    draw.text((84, 145), subtitle, fill=(75, 85, 99), font=subtitle_font)

    x = 74
    y = 1018
    for label in labels[:4]:
        font = text_fit(draw, label, 260, 24, True)
        width = int(draw.textlength(label, font=font)) + 42
        if x + width > 1140:
            break
        draw.rounded_rectangle((x, y, x + width, y + 50), radius=25, fill=accent + (232,))
        draw.text((x + 21, y + 13), label, fill=(255, 255, 255), font=font)
        x += width + 16

    canvas.alpha_composite(overlay)
    return canvas.convert("RGB")


def feature_specs(product: object) -> list[tuple[str, str, str, list[str], tuple[int, int, int]]]:
    return [
        ("02_upper.jpg", product.feature_title, product.upper, ["Soft Textile", "Breathable Feel", "Daily Comfort"], (18, 118, 99)),
        ("03_fit.jpg", product.fit_title, f"{product.closure} closure for everyday wear", [product.closure, "Easy Daily Wear", product.size_range], (37, 99, 235)),
        ("04_sole.jpg", product.sole_title, "Built for walking, commuting and casual use", ["Cushion Feel", "Textured Support", "Stable Step"], (124, 58, 237)),
        ("06_scene.jpg", "DAILY WALKING USE", product.application, ["Walking", "Commuting", "Travel", "Casual Wear"], (217, 119, 6)),
    ]


def natural_feature(src: Path, dst: Path, product_name: str, title: str, subtitle: str, labels: list[str], accent: tuple[int, int, int]) -> None:
    canvas = natural_feature_base(src, product_name)
    canvas = add_text_panel(canvas, title, subtitle, labels, accent)
    save_jpg(canvas, dst)


def make_overview(rows: list[tuple[str, Path, Path, Path]], out: Path) -> None:
    thumb = 245
    label_h = 46
    left = 185
    cols = 3
    canvas = Image.new("RGB", (left + cols * thumb, len(rows) * (thumb + label_h) + 62), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((16, 16), "BQ016-BQ030 natural main hero rebuild QA", fill=(18, 25, 38), font=load_font(22, True))
    for i, label in enumerate(["Old backup", "Current", "Natural rebuild"]):
        draw.text((left + i * thumb + 52, 20), label, fill=(71, 85, 105), font=load_font(15, True))
    for row, (name, old_src, current, candidate) in enumerate(rows):
        y = 62 + row * (thumb + label_h)
        draw.text((14, y + 98), name, fill=(30, 41, 59), font=load_font(15, True))
        for col, path in enumerate([old_src, current, candidate]):
            im = Image.open(path).convert("RGB")
            im.thumbnail((thumb - 14, thumb - 14), Image.Resampling.LANCZOS)
            x = left + col * thumb + (thumb - im.width) // 2
            canvas.paste(im, (x, y + 6))
    save_jpg(canvas, out)


def make_gallery_overview(rows: list[tuple[str, Path]], candidate_dir: Path, out: Path, applied: bool) -> None:
    thumb = 166
    label_h = 42
    left = 170
    top = 92
    cols = len(MAIN_GALLERY_FILES)
    canvas = Image.new("RGB", (left + cols * thumb + 22, top + len(rows) * (thumb + label_h) + 22), "white")
    draw = ImageDraw.Draw(canvas)
    title = "BQ016-BQ030 natural main folder QA - applied" if applied else "BQ016-BQ030 natural main folder QA - candidates"
    draw.text((16, 18), title, fill=(18, 25, 38), font=load_font(20, True))
    for col, file_name in enumerate(MAIN_GALLERY_FILES):
        label = Path(file_name).stem
        draw.text((left + col * thumb + 42, 58), label, fill=(71, 85, 105), font=load_font(14, True))

    for row, (name, product_dir) in enumerate(rows):
        y = top + row * (thumb + label_h)
        draw.text((14, y + 66), name, fill=(30, 41, 59), font=load_font(14, True))
        main_dir = main_dir_path(product_dir)
        for col, file_name in enumerate(MAIN_GALLERY_FILES):
            path = main_dir / file_name if applied else candidate_dir / candidate_name(name, file_name)
            if not path.exists():
                continue
            im = Image.open(path).convert("RGB")
            im.thumbnail((thumb - 14, thumb - 14), Image.Resampling.LANCZOS)
            x = left + col * thumb + (thumb - im.width) // 2
            canvas.paste(im, (x, y + 6))
    save_jpg(canvas, out)


def run(apply: bool) -> None:
    candidate_dir = QA_ROOT / "natural_candidates"
    backup_dir = QA_ROOT / "replaced_backups"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)

    metadata = load_product_metadata()
    rows: list[tuple[str, Path, Path, Path]] = []
    gallery_rows: list[tuple[str, Path]] = []
    for product in product_dirs():
        current = main_image_path(product)
        old_src = source_image_path(product)
        candidate = candidate_dir / candidate_name(product.name, "01_main.jpg")
        natural_hero(old_src, candidate, product.name)
        rows.append((product.name, old_src, current, candidate))

        product_meta = metadata.get(product.name)
        if product_meta is None:
            print(f"metadata_missing={product.name}; rebuilt 01_main only")
            gallery_files = ["01_main.jpg"]
        else:
            gallery_files = MAIN_GALLERY_FILES
            for file_name, title, subtitle, labels, accent in feature_specs(product_meta):
                feature_candidate = candidate_dir / candidate_name(product.name, file_name)
                natural_feature(old_src, feature_candidate, product.name, title, subtitle, labels, accent)

        gallery_rows.append((product.name, product))
        if apply:
            main_dir = main_dir_path(product)
            for file_name in gallery_files:
                candidate_file = candidate_dir / candidate_name(product.name, file_name)
                target = main_dir / file_name
                if not candidate_file.exists() or not target.exists():
                    continue
                backup = backup_dir / f"{product.name}_{Path(file_name).stem}_before_natural_fix.jpg"
                if not backup.exists():
                    shutil.copy2(target, backup)
                shutil.copy2(candidate_file, target)

    overview = QA_ROOT / ("natural_overview_applied.jpg" if apply else "natural_overview_candidates.jpg")
    make_overview(rows, overview)
    gallery_overview = QA_ROOT / ("natural_gallery_applied.jpg" if apply else "natural_gallery_candidates.jpg")
    make_gallery_overview(gallery_rows, candidate_dir, gallery_overview, apply)
    print(f"processed={len(rows)} apply={apply} qa={QA_ROOT}")
    print(f"overview={overview}")
    print(f"gallery_overview={gallery_overview}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="replace 01_main.jpg after generating natural candidates")
    args = parser.parse_args()
    run(apply=args.apply)
