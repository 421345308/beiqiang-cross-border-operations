from __future__ import annotations

from collections import deque
from pathlib import Path
import argparse
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

try:
    from rembg import new_session, remove
except ImportError:  # pragma: no cover - optional local dependency
    new_session = None
    remove = None


ROOT = Path(__file__).resolve().parents[2]
UPLOAD_PARENT = next(p for p in ROOT.iterdir() if p.is_dir() and p.name.startswith("02_"))
UPLOAD_ROOT = next(p for p in UPLOAD_PARENT.iterdir() if p.is_dir() and p.name.startswith("00_"))
ARCHIVE_ROOT = next(p for p in UPLOAD_PARENT.iterdir() if p.is_dir() and p.name.startswith("99_"))
QA_ROOT = ARCHIVE_ROOT / "main_hero_refine_20260619"
_REMBG_SESSION = None


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


def otsu_threshold(values: np.ndarray) -> float:
    clipped = np.clip(values, 0, 255).astype(np.uint8)
    hist = np.bincount(clipped.ravel(), minlength=256).astype(np.float64)
    total = clipped.size
    if total == 0:
        return 32.0
    cumulative = np.cumsum(hist)
    cumulative_mean = np.cumsum(hist * np.arange(256))
    global_mean = cumulative_mean[-1]
    denom = cumulative * (total - cumulative)
    denom[denom == 0] = 1
    variance = (global_mean * cumulative - cumulative_mean * total) ** 2 / denom
    return float(np.argmax(variance))


def connected_components(mask: np.ndarray) -> list[tuple[int, tuple[int, int, int, int], bool, np.ndarray]]:
    h, w = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    comps: list[tuple[int, tuple[int, int, int, int], bool, np.ndarray]] = []
    ys, xs = np.nonzero(mask)
    for start_y, start_x in zip(ys, xs):
        if visited[start_y, start_x]:
            continue
        queue: deque[tuple[int, int]] = deque([(int(start_y), int(start_x))])
        visited[start_y, start_x] = True
        pixels: list[tuple[int, int]] = []
        min_x = max_x = int(start_x)
        min_y = max_y = int(start_y)
        touches_border = False
        while queue:
            y, x = queue.popleft()
            pixels.append((y, x))
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)
            if x == 0 or y == 0 or x == w - 1 or y == h - 1:
                touches_border = True
            for ny in (y - 1, y, y + 1):
                for nx in (x - 1, x, x + 1):
                    if ny == y and nx == x:
                        continue
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = True
                        queue.append((ny, nx))
        arr = np.array(pixels, dtype=np.int32)
        comps.append((len(pixels), (min_x, min_y, max_x + 1, max_y + 1), touches_border, arr))
    comps.sort(key=lambda item: item[0], reverse=True)
    return comps


def mask_to_pil(mask: np.ndarray) -> Image.Image:
    return Image.fromarray((mask.astype(np.uint8) * 255), "L")


def get_rembg_session():
    global _REMBG_SESSION
    if remove is None or new_session is None:
        return None
    if _REMBG_SESSION is None:
        _REMBG_SESSION = new_session("u2net")
    return _REMBG_SESSION


def clean_model_alpha(rgba: Image.Image, aggressive: bool) -> Image.Image:
    arr = np.array(rgba.convert("RGBA"))
    rgb = arr[..., :3].astype(np.float32)
    alpha = arr[..., 3].astype(np.float32)
    if aggressive:
        luma = rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114
        sat = rgb.max(axis=2) - rgb.min(axis=2)
        edge = np.zeros_like(luma)
        edge[:, 1:] = np.maximum(edge[:, 1:], np.abs(luma[:, 1:] - luma[:, :-1]))
        edge[1:, :] = np.maximum(edge[1:, :], np.abs(luma[1:, :] - luma[:-1, :]))
        background_patch = (alpha > 12) & (luma > 128) & (luma < 208) & (sat < 38) & (edge < 18)
        alpha[background_patch] *= 0.04
        weak_noise = (alpha < 24) & (edge < 12)
        alpha[weak_noise] = 0
    else:
        alpha[alpha < 10] = 0

    alpha_img = Image.fromarray(np.clip(alpha, 0, 255).astype(np.uint8), "L")
    alpha_img = alpha_img.filter(ImageFilter.GaussianBlur(0.45))
    arr[..., 3] = np.asarray(alpha_img)
    return Image.fromarray(arr, "RGBA")


def build_model_cutout(image: Image.Image, product_name: str) -> Image.Image | None:
    session = get_rembg_session()
    if session is None or remove is None:
        return None
    result = remove(
        image.convert("RGBA"),
        session=session,
        alpha_matting=True,
        alpha_matting_foreground_threshold=240,
        alpha_matting_background_threshold=10,
        alpha_matting_erode_size=8,
    )
    return clean_model_alpha(result, aggressive=False)


def build_subject_mask(image: Image.Image) -> Image.Image:
    small = image.convert("RGB")
    small.thumbnail((500, 500), Image.Resampling.LANCZOS)
    arr = np.asarray(small).astype(np.float32)
    h, w, _ = arr.shape
    border = np.concatenate([arr[:12].reshape(-1, 3), arr[-12:].reshape(-1, 3), arr[:, :12].reshape(-1, 3), arr[:, -12:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    bg_luma = float(np.dot(bg, [0.299, 0.587, 0.114]))
    bg_sat = float(np.median(border.max(axis=1) - border.min(axis=1)))

    luma = arr[..., 0] * 0.299 + arr[..., 1] * 0.587 + arr[..., 2] * 0.114
    sat = arr.max(axis=2) - arr.min(axis=2)
    dist = np.linalg.norm(arr - bg, axis=2)

    edge = np.zeros_like(luma)
    edge[:, 1:] = np.maximum(edge[:, 1:], np.abs(luma[:, 1:] - luma[:, :-1]))
    edge[1:, :] = np.maximum(edge[1:, :], np.abs(luma[1:, :] - luma[:-1, :]))

    threshold = max(14.0, min(62.0, otsu_threshold(dist) * 0.72))
    seed = (dist > threshold) | (luma < bg_luma - 24) | ((sat > bg_sat + 18) & (dist > 10))
    seed[:2, :] = False
    seed[-2:, :] = False
    seed[:, :2] = False
    seed[:, -2:] = False

    kept_seed = np.zeros((h, w), dtype=bool)
    min_area = max(60, int(h * w * 0.00045))
    for area, _bbox, touches_border, pixels in connected_components(seed):
        if area < min_area:
            continue
        yy, xx = pixels[:, 0], pixels[:, 1]
        mean_dist = float(dist[yy, xx].mean())
        mean_luma = float(luma[yy, xx].mean())
        mean_sat = float(sat[yy, xx].mean())
        if touches_border and mean_luma > 80:
            continue
        if mean_dist > 22 or mean_luma < bg_luma - 16 or mean_sat > bg_sat + 12:
            kept_seed[yy, xx] = True

    if kept_seed.sum() < min_area:
        kept_seed = seed

    seed_pil = mask_to_pil(kept_seed).filter(ImageFilter.MaxFilter(25))
    seed_dilated = np.asarray(seed_pil) > 0
    candidate = seed_dilated & (
        (dist > max(7.0, threshold * 0.33))
        | (edge > 4.5)
        | (luma < bg_luma - 8)
        | (sat > bg_sat + 10)
    )
    candidate |= kept_seed

    final_small = np.zeros((h, w), dtype=bool)
    seed_overlap = np.asarray(mask_to_pil(kept_seed).filter(ImageFilter.MaxFilter(13))) > 0
    for area, _bbox, touches_border, pixels in connected_components(candidate):
        if area < max(35, min_area // 2):
            continue
        yy, xx = pixels[:, 0], pixels[:, 1]
        if not seed_overlap[yy, xx].any():
            continue
        if touches_border and area > h * w * 0.04:
            continue
        final_small[yy, xx] = True

    if final_small.sum() < min_area:
        final_small = kept_seed

    mask = mask_to_pil(final_small)
    mask = mask.filter(ImageFilter.MaxFilter(17))
    mask = mask.filter(ImageFilter.MinFilter(7))
    mask = mask.filter(ImageFilter.MaxFilter(9))
    mask = mask.resize(image.size, Image.Resampling.LANCZOS)
    mask = mask.filter(ImageFilter.GaussianBlur(1.8))
    return mask


def alpha_bbox(alpha: Image.Image) -> tuple[int, int, int, int]:
    bbox = alpha.point(lambda p: 255 if p > 18 else 0).getbbox()
    if not bbox:
        return (0, 0, alpha.width, alpha.height)
    x0, y0, x1, y1 = bbox
    pad_x = int((x1 - x0) * 0.035) + 12
    pad_y = int((y1 - y0) * 0.045) + 12
    return (max(0, x0 - pad_x), max(0, y0 - pad_y), min(alpha.width, x1 + pad_x), min(alpha.height, y1 + pad_y))


def make_white_hero(src: Path, dst: Path, product_name: str = "") -> None:
    image = Image.open(src).convert("RGB")
    model_cutout = build_model_cutout(image, product_name)
    if model_cutout is not None:
        alpha = model_cutout.getchannel("A")
        source_rgb = model_cutout.convert("RGB")
    else:
        alpha = build_subject_mask(image)
        source_rgb = image
    bbox = alpha_bbox(alpha)

    cut_rgb = source_rgb.crop(bbox)
    cut_alpha = alpha.crop(bbox)
    cut_rgb = ImageEnhance.Contrast(cut_rgb).enhance(1.035)
    cut_rgb = ImageEnhance.Sharpness(cut_rgb).enhance(1.08)

    max_w = 1085
    max_h = 900
    scale = min(max_w / cut_rgb.width, max_h / cut_rgb.height)
    scale = min(scale, 1.75)
    new_size = (max(1, int(cut_rgb.width * scale)), max(1, int(cut_rgb.height * scale)))
    cut_rgb = cut_rgb.resize(new_size, Image.Resampling.LANCZOS)
    cut_alpha = cut_alpha.resize(new_size, Image.Resampling.LANCZOS)

    canvas = Image.new("RGB", (1200, 1200), "white")
    x = (1200 - new_size[0]) // 2
    center_y = 640 if new_size[0] > new_size[1] * 1.25 else 610
    y = max(70, min(220, int(center_y - new_size[1] / 2)))

    canvas.paste(cut_rgb, (x, y), cut_alpha)
    canvas.save(dst, quality=95, subsampling=1)


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
    main_dir = next(p for p in product_dir.iterdir() if p.is_dir() and p.name.startswith("01_"))
    return main_dir / "01_main.jpg"


def source_override(product_dir: Path) -> Path | None:
    if product_dir.name != "BQ028_BISCUIT":
        return None
    raw_root = next(p for p in ROOT.iterdir() if p.is_dir() and p.name.startswith("01_"))
    raw_dirs = [p for p in raw_root.iterdir() if p.is_dir() and "BQ028" in p.name]
    if not raw_dirs:
        return None
    matches = list(raw_dirs[0].rglob("6.jpg"))
    matches.sort(key=lambda p: (0 if "\u9ed1" in str(p.parent) else 1, str(p)))
    return matches[0] if matches else None


def make_overview(before_after: list[tuple[str, Path, Path]], out: Path) -> None:
    thumb = 255
    label_h = 62
    cols = 2
    rows = len(before_after)
    canvas = Image.new("RGB", (cols * thumb + 250, rows * (thumb + label_h) + 62), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((18, 16), "White-background main hero refinement QA", fill=(18, 25, 38), font=load_font(24, True))
    draw.text((250, 20), "Before", fill=(71, 85, 105), font=load_font(18, True))
    draw.text((250 + thumb, 20), "Refined", fill=(71, 85, 105), font=load_font(18, True))
    for row, (name, before, after) in enumerate(before_after):
        y = 62 + row * (thumb + label_h)
        draw.text((18, y + 92), name, fill=(30, 41, 59), font=load_font(17, True))
        for col, path in enumerate((before, after)):
            im = Image.open(path).convert("RGB")
            im.thumbnail((thumb - 16, thumb - 16), Image.Resampling.LANCZOS)
            x = 250 + col * thumb + (thumb - im.width) // 2
            canvas.paste(im, (x, y + 8))
        draw.text((250, y + thumb + 10), "original", fill=(100, 116, 139), font=load_font(13))
        draw.text((250 + thumb, y + thumb + 10), "white hero", fill=(100, 116, 139), font=load_font(13))
    canvas.save(out, quality=92)


def run(apply: bool) -> None:
    cand_dir = QA_ROOT / "candidates"
    backup_dir = QA_ROOT / "before_backups"
    cand_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)

    overview_rows: list[tuple[str, Path, Path]] = []
    for product in product_dirs():
        before = main_image_path(product)
        backup = backup_dir / f"{product.name}_01_main_before.jpg"
        source = source_override(product) or (backup if backup.exists() else before)
        candidate = cand_dir / f"{product.name}_01_main_white.jpg"
        make_white_hero(source, candidate, product.name)
        overview_rows.append((product.name, before, candidate))
        if apply:
            if not backup.exists():
                shutil.copy2(before, backup)
            shutil.copy2(candidate, before)

    make_overview(overview_rows, QA_ROOT / ("overview_applied.jpg" if apply else "overview_candidates.jpg"))
    print(f"processed={len(overview_rows)} apply={apply} qa={QA_ROOT}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="replace final 01_main.jpg files after generating candidates")
    args = parser.parse_args()
    run(apply=args.apply)
