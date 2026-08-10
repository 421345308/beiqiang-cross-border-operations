from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
import gc
import re
import shutil
import time

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageFilter


ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = next(p for p in ROOT.iterdir() if p.is_dir() and p.name.startswith("01_"))
UPLOAD_ROOT = next(p for p in ROOT.iterdir() if p.is_dir() and p.name.startswith("02_")) / "00_最终上传"
PREVIEW_ROOT = ROOT / "04_work_newpkg_preview_20260616"

MAIN_DIR = "01_主图"
DETAIL_DIR = "02_详情页"
COLOR_DIR = "03_颜色图"
REF_DIR = "04_参考预览"
FORM_NAME = "00_上架填写表.md"

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
FONT = "C:/Windows/Fonts/arial.ttf"
BOLD = "C:/Windows/Fonts/arialbd.ttf"
CN_FONT = "C:/Windows/Fonts/msyh.ttc"


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = BOLD if bold else FONT
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.truetype(CN_FONT, size)


def natural_key(path: Path) -> list[object]:
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", path.name)]


def safe_filename(text: str, suffix: str = ".jpg", limit: int = 30) -> str:
    base = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower() or "image"
    max_base = max(1, limit - len(suffix))
    return base[:max_base] + suffix


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        trial = word if not line else f"{line} {word}"
        if draw.textlength(trial, font=font) <= width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def text_fit(draw: ImageDraw.ImageDraw, text: str, max_width: int, start: int, bold: bool = False) -> ImageFont.ImageFont:
    size = start
    while size >= 18:
        font = load_font(size, bold)
        if draw.textlength(text, font=font) <= max_width:
            return font
        size -= 2
    return load_font(18, bold)


def all_images(root: Path) -> list[Path]:
    return sorted(
        [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in IMG_EXTS],
        key=natural_key,
    )


def score_source_dir(path: Path) -> int:
    name = path.name.lower()
    count = len([p for p in path.iterdir() if p.is_file() and p.suffix.lower() in IMG_EXTS])
    score = min(count, 35)
    if "800" in name:
        score += 55
    if "主图" in path.name or "zhutu" in name or "ö÷" in name:
        score += 45
    if path.name in {"png", "PNG"} or "透明" in path.name:
        score += 30
    if any(x in path.name for x in ["750", "790", "620", "手机", "天猫", "淘宝"]):
        score -= 20
    return score


def source_dirs(roots: Iterable[Path]) -> list[Path]:
    dirs: list[Path] = []
    for root in roots:
        for path in root.rglob("*"):
            if path.is_dir() and any(p.suffix.lower() in IMG_EXTS for p in path.iterdir() if p.is_file()):
                dirs.append(path)
    return sorted(dirs, key=score_source_dir, reverse=True)


def find_raw(name: str) -> Path:
    exact = RAW_ROOT / name
    if exact.exists():
        return exact
    candidates = [path for path in RAW_ROOT.iterdir() if path.is_dir() and name in path.name]
    for path in candidates:
        if path.name.endswith(name):
            return path
    for path in RAW_ROOT.iterdir():
        if path.is_dir() and name in path.name:
            return path
    raise FileNotFoundError(f"Raw package not found: {name}")


def find_by_hints(images: list[Path], hints: list[str], limit: int) -> list[Path]:
    picked: list[Path] = []
    used: set[Path] = set()
    lower_map = [(p, p.name.lower()) for p in images]
    for hint in hints:
        h = hint.lower()
        for path, lname in lower_map:
            if path not in used and h in lname:
                picked.append(path)
                used.add(path)
                break
    for path in images:
        if path not in used:
            picked.append(path)
            used.add(path)
        if len(picked) >= limit:
            break
    return picked[:limit]


def crop_soft(image: Image.Image) -> Image.Image:
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    alpha = image.getchannel("A")
    if alpha.getextrema()[0] < 255:
        bbox = alpha.getbbox()
        return image.crop(bbox) if bbox else image
    rgb = image.convert("RGB")
    bg = Image.new("RGB", rgb.size, rgb.getpixel((0, 0)))
    diff = Image.eval(ImageChops.difference(rgb, bg).convert("L"), lambda v: 255 if v > 16 else 0)
    bbox = diff.getbbox()
    return image.crop(bbox) if bbox else image


def open_image(path: Path) -> Image.Image:
    with Image.open(path) as img:
        return img.convert("RGBA")


def paste_fit(canvas: Image.Image, src: Path, box: tuple[int, int, int, int], shadow: bool = True) -> None:
    img = open_image(src)
    if img.getchannel("A").getextrema()[0] < 255:
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)
    else:
        # Keep JPG backgrounds, but trim obvious white margins.
        rgb = img.convert("RGB")
        bg = Image.new("RGB", rgb.size, rgb.getpixel((0, 0)))
        diff = ImageChops.difference(rgb, bg).convert("L")
        diff = Image.eval(diff, lambda v: 255 if v > 18 else 0)
        bbox = diff.getbbox()
        if bbox:
            img = img.crop(bbox).convert("RGBA")
    max_w = box[2] - box[0]
    max_h = box[3] - box[1]
    img.thumbnail((max_w, max_h), Image.LANCZOS)
    x = box[0] + (max_w - img.width) // 2
    y = box[1] + (max_h - img.height) // 2
    if shadow and img.getchannel("A").getextrema()[0] < 255:
        alpha = img.getchannel("A")
        sh = Image.new("RGBA", img.size, (0, 0, 0, 95))
        sh.putalpha(alpha.filter(ImageFilter.GaussianBlur(18)))
        canvas.alpha_composite(sh, (x + 14, y + 26))
    canvas.alpha_composite(img, (x, y))


def object_bbox_from_background(image: Image.Image) -> tuple[int, int, int, int] | None:
    rgb = image.convert("RGB")
    small = rgb.copy()
    small.thumbnail((420, 420), Image.LANCZOS)
    arr = np.asarray(small).astype(np.int16)
    h, w = arr.shape[:2]
    edge = max(4, min(h, w) // 24)
    edge_pixels = np.concatenate(
        [
            arr[:edge, :, :].reshape(-1, 3),
            arr[-edge:, :, :].reshape(-1, 3),
            arr[:, :edge, :].reshape(-1, 3),
            arr[:, -edge:, :].reshape(-1, 3),
        ],
        axis=0,
    )
    bg = np.median(edge_pixels, axis=0)
    dist = np.sqrt(((arr - bg) ** 2).sum(axis=2))
    threshold = max(28, float(np.percentile(dist, 78)) * 0.8)
    mask = dist > threshold
    coverage = float(mask.mean())
    if coverage < 0.015 or coverage > 0.82:
        return None
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return None
    scale_x = rgb.width / w
    scale_y = rgb.height / h
    left = int(xs.min() * scale_x)
    top = int(ys.min() * scale_y)
    right = int((xs.max() + 1) * scale_x)
    bottom = int((ys.max() + 1) * scale_y)
    if right - left < rgb.width * 0.08 or bottom - top < rgb.height * 0.08:
        return None
    return left, top, right, bottom


def edge_background_color(image: Image.Image) -> tuple[int, int, int]:
    rgb = image.convert("RGB")
    sample = Image.new("RGB", (rgb.width, rgb.height))
    sample.paste(rgb)
    arr = np.asarray(sample).astype(np.uint8)
    h, w = arr.shape[:2]
    edge = max(4, min(h, w) // 20)
    pixels = np.concatenate(
        [
            arr[:edge, :, :].reshape(-1, 3),
            arr[-edge:, :, :].reshape(-1, 3),
            arr[:, :edge, :].reshape(-1, 3),
            arr[:, -edge:, :].reshape(-1, 3),
        ],
        axis=0,
    )
    color = np.median(pixels, axis=0).astype(int)
    return int(color[0]), int(color[1]), int(color[2])


def square_photo_canvas(src: Path, size: int = 1200, occupancy: float = 0.86) -> Image.Image:
    with Image.open(src) as opened:
        image = opened.convert("RGBA")

    alpha = image.getchannel("A")
    if alpha.getextrema()[0] < 255:
        bbox = image.getbbox()
        product = image.crop(bbox) if bbox else image
        max_w = int(size * occupancy)
        max_h = int(size * 0.76)
        product.thumbnail((max_w, max_h), Image.LANCZOS)
        canvas = Image.new("RGBA", (size, size), (255, 255, 255, 255))
        x = (size - product.width) // 2
        y = (size - product.height) // 2
        canvas.alpha_composite(product, (x, y))
        return canvas

    rgb = image.convert("RGB")
    aspect = rgb.width / max(1, rgb.height)
    if 0.92 <= aspect <= 1.08:
        return rgb.resize((size, size), Image.LANCZOS).convert("RGBA")

    bbox = object_bbox_from_background(rgb)
    if bbox:
        left, top, right, bottom = bbox
        bw, bh = right - left, bottom - top
        side = int(max(bw, bh) / occupancy)
        side = max(side, int(min(rgb.width, rgb.height) * 0.72))
        side = min(side, min(rgb.width, rgb.height))
        cx = (left + right) // 2
        cy = (top + bottom) // 2
    else:
        side = min(rgb.width, rgb.height)
        cx = rgb.width // 2
        cy = rgb.height // 2

    side = int(side)
    half = side // 2
    crop_left = int(cx - half)
    crop_top = int(cy - half)
    crop_left = max(0, min(crop_left, rgb.width - side))
    crop_top = max(0, min(crop_top, rgb.height - side))
    square = rgb.crop((crop_left, crop_top, crop_left + side, crop_top + side))
    square = square.resize((size, size), Image.LANCZOS)
    return square.convert("RGBA")


def add_text_panel(
    canvas: Image.Image,
    title: str,
    subtitle: str,
    labels: list[str],
    accent: tuple[int, int, int],
) -> None:
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle((48, 48, 1152, 236), radius=26, fill=(255, 255, 255, 220))
    title_font = text_fit(draw, title, 980, 48, True)
    subtitle_font = text_fit(draw, subtitle, 980, 27)
    draw.text((82, 72), title, fill=(22, 31, 43), font=title_font)
    draw.text((84, 145), subtitle, fill=(75, 85, 99), font=subtitle_font)
    x = 74
    y = 1018
    for label in labels[:4]:
        font = text_fit(draw, label, 260, 24, True)
        width = int(draw.textlength(label, font=font)) + 42
        draw.rounded_rectangle((x, y, x + width, y + 50), radius=25, fill=accent + (232,))
        draw.text((x + 21, y + 13), label, fill=(255, 255, 255), font=font)
        x += width + 16
        if x > 990:
            break
    canvas.alpha_composite(overlay)


def save_jpg(canvas: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(path, "JPEG", quality=93, optimize=True)


def clear_direct_files(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    resolved = path.resolve()
    if ROOT not in resolved.parents:
        raise RuntimeError(f"Refusing to clean outside workspace: {path}")
    for child in path.iterdir():
        if child.is_file():
            child.unlink()


def base_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    canvas = Image.new("RGBA", (1200, 1200), (248, 250, 252, 255))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((44, 44, 1156, 1156), radius=28, fill=(255, 255, 255))
    return canvas, draw


def draw_title(draw: ImageDraw.ImageDraw, title: str, subtitle: str | None = None) -> None:
    title_font = text_fit(draw, title, 1040, 54, True)
    draw.text((74, 68), title, fill=(22, 31, 43), font=title_font)
    if subtitle:
        sub_font = text_fit(draw, subtitle, 980, 30)
        draw.text((76, 138), subtitle, fill=(84, 96, 112), font=sub_font)


def draw_pill(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, fill=(18, 118, 99)) -> None:
    font = text_fit(draw, text, 310, 25, True)
    w = int(draw.textlength(text, font=font)) + 36
    draw.rounded_rectangle((x, y, x + w, y + 44), radius=22, fill=fill)
    draw.text((x + 18, y + 10), text, fill=(255, 255, 255), font=font)


def make_plain_main(out: Path, product: "Product", hero: Path) -> None:
    canvas = square_photo_canvas(hero, 1200, 0.88)
    save_jpg(canvas, out)


def make_feature(out: Path, product: "Product", hero: Path, title: str, subtitle: str, labels: list[str], accent: tuple[int, int, int]) -> None:
    canvas = square_photo_canvas(hero, 1200, 0.82)
    add_text_panel(canvas, title, subtitle, labels, accent)
    save_jpg(canvas, out)


def make_color_image(out: Path, product: "Product", images: list[Path]) -> None:
    canvas, draw = base_canvas()
    draw_title(draw, "COLOR OPTIONS", "Actual SKU colors from source package")
    slots = [(90, 270, 380, 610), (455, 270, 745, 610), (820, 270, 1110, 610), (90, 690, 380, 1030), (455, 690, 745, 1030), (820, 690, 1110, 1030)]
    for i, color in enumerate(product.colors[:6]):
        box = slots[i]
        draw.rounded_rectangle((box[0], box[1], box[2], box[3]), radius=22, fill=(248, 250, 252), outline=(222, 230, 238), width=2)
        src = images[min(i, len(images) - 1)]
        paste_fit(canvas, src, (box[0] + 16, box[1] + 18, box[2] - 16, box[3] - 62), shadow=False)
        draw.ellipse((box[0] + 24, box[3] - 45, box[0] + 52, box[3] - 17), fill=color[1], outline=(148, 163, 184))
        draw.text((box[0] + 64, box[3] - 45), color[0], fill=(30, 41, 59), font=text_fit(draw, color[0], 190, 22, True))
    save_jpg(canvas, out)


def make_size_chart(out: Path, product: "Product", hero: Path) -> None:
    canvas, draw = base_canvas()
    draw_title(draw, "SIZE REFERENCE", f"{product.size_range} | Reference only")
    paste_fit(canvas, hero, (760, 245, 1110, 565), shadow=False)
    eu_sizes = product.eu_sizes()
    foot_lengths = product.foot_lengths()
    x, y = 90, 265
    row_h = 54
    widths = [150, 190, 220]
    headers = ["EU Size", "US Ref.", "Foot Length"]
    draw.rounded_rectangle((x - 8, y - 8, x + sum(widths) + 8, y + row_h * (len(eu_sizes) + 1) + 8), radius=18, fill=(248, 250, 252), outline=(226, 232, 240), width=2)
    for col, header in enumerate(headers):
        cx = x + sum(widths[:col])
        draw.rectangle((cx, y, cx + widths[col], y + row_h), fill=(31, 41, 55))
        draw.text((cx + 16, y + 15), header, fill=(255, 255, 255), font=load_font(21, True))
    for r, size in enumerate(eu_sizes):
        yy = y + row_h * (r + 1)
        fill = (255, 255, 255) if r % 2 == 0 else (241, 245, 249)
        draw.rectangle((x, yy, x + sum(widths), yy + row_h), fill=fill)
        values = [str(size), product.us_ref(size), f"{foot_lengths[r]:.0f}-{foot_lengths[r] + 5:.0f} mm"]
        for col, value in enumerate(values):
            cx = x + sum(widths[:col])
            draw.text((cx + 16, yy + 15), value, fill=(35, 45, 59), font=load_font(21))
    note = "Reference only. Final fit can vary by style and order requirements."
    for i, line in enumerate(wrap_text(draw, note, load_font(24), 980)):
        draw.text((95, 1050 + i * 32), line, fill=(99, 112, 128), font=load_font(24))
    save_jpg(canvas, out)


def make_info(out: Path, product: "Product", hero: Path) -> None:
    canvas, draw = base_canvas()
    draw_title(draw, "PRODUCT INFORMATION", product.detail_subtitle)
    paste_fit(canvas, hero, (735, 265, 1110, 575), shadow=False)
    rows = [
        ("Model", product.model),
        ("Upper", product.upper),
        ("Sole", "Cushion sole"),
        ("Closure", product.closure),
        ("Size", product.size_range),
        ("Season", product.season),
        ("Application", product.application),
        ("Packing", "Shoe box or plastic bag"),
    ]
    x, y = 90, 270
    for i, (k, v) in enumerate(rows):
        yy = y + i * 82
        draw.rounded_rectangle((x, yy, 670, yy + 64), radius=16, fill=(248, 250, 252), outline=(226, 232, 240), width=1)
        draw.text((x + 24, yy + 18), k, fill=(71, 85, 105), font=load_font(22, True))
        draw.text((x + 195, yy + 18), v, fill=(30, 41, 59), font=text_fit(draw, v, 430, 22))
    draw_pill(draw, 740, 640, product.group, (31, 103, 86))
    for i, phrase in enumerate(product.keywords[:3]):
        draw.text((746, 720 + i * 45), f"- {phrase}", fill=(52, 65, 80), font=load_font(25))
    save_jpg(canvas, out)


def make_order(out: Path, product: "Product", hero: Path) -> None:
    canvas, draw = base_canvas()
    draw_title(draw, "ORDER SUPPORT", "Key details for quotation and bulk order")
    paste_fit(canvas, hero, (90, 285, 600, 760), shadow=True)
    cards = [
        ("Sample Check", "Samples can be arranged before bulk order."),
        ("Mixed Options", "Mixed colors and sizes can be discussed."),
        ("Packing", "Shoe box or plastic bag according to order needs."),
        ("Bulk Details", "MOQ, lead time and carton details can be reviewed before order."),
    ]
    for i, (head, body) in enumerate(cards):
        x = 650
        y = 300 + i * 155
        draw.rounded_rectangle((x, y, 1110, y + 118), radius=20, fill=(248, 250, 252), outline=(226, 232, 240), width=2)
        draw.text((x + 28, y + 22), head, fill=(22, 101, 83), font=load_font(27, True))
        for j, line in enumerate(wrap_text(draw, body, load_font(22), 390)[:2]):
            draw.text((x + 28, y + 62 + j * 28), line, fill=(71, 85, 105), font=load_font(22))
    draw.text((88, 1042), "Before quotation, review material, size ratio, packing, MOQ and lead time.", fill=(82, 94, 108), font=load_font(25))
    save_jpg(canvas, out)


def make_contact_sheet(out: Path, product: "Product", images: list[Path]) -> None:
    cell_w, cell_h = 210, 245
    cols = 5
    rows = min(3, (len(images) + cols - 1) // cols)
    canvas = Image.new("RGB", (cols * cell_w, 64 + rows * cell_h), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((10, 12), f"{product.code}_{product.model} source preview", fill=(20, 31, 45), font=ImageFont.truetype(CN_FONT, 20))
    for i, src in enumerate(images[: cols * rows]):
        with Image.open(src) as opened:
            img = opened.convert("RGB")
        img.thumbnail((cell_w, 190), Image.LANCZOS)
        x = (i % cols) * cell_w + (cell_w - img.width) // 2
        y = 64 + (i // cols) * cell_h + 8
        canvas.paste(img, (x, y))
        draw.text(((i % cols) * cell_w + 8, 64 + (i // cols) * cell_h + 205), src.name[:28], fill=(31, 41, 55), font=ImageFont.truetype(CN_FONT, 12))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, "JPEG", quality=90)


@dataclass
class Product:
    code: str
    model: str
    raw_names: list[str]
    group: str
    title: str
    size_range: str
    colors: list[tuple[str, tuple[int, int, int]]]
    closure: str
    upper: str
    season: str
    application: str
    core_keyword: str
    detail_subtitle: str
    feature_title: str
    fit_title: str
    sole_title: str
    keywords: list[str]
    selling_points: list[str]
    pending: list[str]
    duplicate_note: str = ""
    source_hints: list[str] = field(default_factory=list)
    color_hints: list[str] = field(default_factory=list)
    raw_rename_names: list[str] = field(default_factory=list)

    @property
    def folder_name(self) -> str:
        return f"{self.code}_{self.model}"

    def eu_sizes(self) -> list[int]:
        m = re.search(r"(\d+)\s*-\s*(\d+)", self.size_range)
        if not m:
            return list(range(35, 46))
        start, end = int(m.group(1)), int(m.group(2))
        return list(range(start, end + 1))

    def foot_lengths(self) -> list[float]:
        sizes = self.eu_sizes()
        # Conservative reference values only.
        base = 195 + (sizes[0] - 31) * 6.5
        return [base + i * 5 for i in range(len(sizes))]

    def us_ref(self, eu_size: int) -> str:
        if "Kids" in self.group or "Kids" in self.title:
            return f"Kids {max(12, eu_size - 20)}"
        return f"{max(4, eu_size - 32)}-{max(5, eu_size - 31)}"


PRODUCTS = [
    Product(
        "BQ016", "201",
        ["201贝强工厂店秋季一脚蹬女鞋童鞋31-40批50元"],
        "Kids Slip-On Walking Shoes",
        "Wholesale Lightweight Knit Slip-On Kids Walking Shoes Cushion Sole Casual Sneakers for Girls",
        "EU 31-40",
        [("Black", (20, 20, 20)), ("Pink", (235, 181, 198)), ("Grey Stripe", (160, 164, 168)), ("Black White", (45, 45, 45))],
        "Slip-On", "Knitted Textile Upper", "Autumn", "School, daily walking, casual wear",
        "Kids Walking Shoes", "Knit slip-on style for girls and small-size markets",
        "KNIT SLIP-ON UPPER", "EASY PULL-ON FIT", "LIGHT CUSHION SOLE",
        ["kids slip-on walking shoes", "girls knit casual sneakers", "lightweight school shoes"],
        [
            "Slip-On Convenience: Easy pull-on design supports daily school and casual wear.",
            "Knitted Upper: Soft textile upper gives a comfortable casual feel.",
            "Small Size Range: EU 31-40 targets girls and small-size women markets.",
            "Color Options: Black, pink and grey stripe options suit different retail collections.",
        ],
        ["White-background main image has been rebuilt from the source photo; request cleaner original photography for future batches.", "Confirm whether this should be positioned as kids, women, or girls/women mixed sizing.", "Confirm outsole/midsole material before final publishing.", "Confirm MOQ, lead time, packing weight and carton details."],
        "Adult slip-on shoes in this batch are similar; keep this separate only because size range and buyer target are different.",
        ["20.jpg", "19.jpg", "13.jpg", "12.jpg", "18.jpg"],
    ),
    Product(
        "BQ017", "A008",
        ["2024贝强鞋业A008套袜一脚蹬男女鞋35-45批55元"],
        "Quilted Casual Walking Shoes",
        "Wholesale Quilted Textile Lace-Up Casual Walking Shoes Lightweight Cushion Sole Sneakers for Daily Wear",
        "EU 35-45",
        [("Grey", (145, 150, 154)), ("White", (235, 232, 220)), ("Black White", (35, 35, 35)), ("All Black", (5, 5, 5))],
        "Lace-Up", "Quilted Textile Upper", "Autumn", "Daily walking, commuting, casual wear",
        "Casual Walking Shoes", "Quilted low-top textile shoe with lace-up fit",
        "QUILTED TEXTILE UPPER", "ADJUSTABLE LACE-UP FIT", "FLEXIBLE CUSHION SOLE",
        ["quilted casual walking shoes", "textile lace-up sneakers", "lightweight daily shoes"],
        [
            "Quilted Upper: Distinct quilted textile look helps separate this style from plain knit shoes.",
            "Lace-Up Fit: Adjustable closure supports different daily walking needs.",
            "Casual Collection Style: Neutral colors are suitable for online sellers and wholesalers.",
            "Light Cushion Sole: Thick sole appearance supports daily commuting and casual wear.",
        ],
        ["Confirm outsole/midsole material.", "Confirm whether '套袜' refers to sock-like comfort only or a specific lining construction.", "Confirm MOQ, lead time and package data."],
        "Keep separate from other knit lace-up shoes because the quilted upper is visually distinct.",
        color_hints=["主图 (2)", "主图 (1)", "主图 (4)", "主图 (3)"],
    ),
    Product(
        "BQ018", "A116",
        ["A116贝强工厂店多走路男鞋35-45批55元"],
        "Lightweight Knit Walking Shoes",
        "Factory Direct Knit Lace-Up Walking Shoes Lightweight Cushion Sole Casual Sneakers for Men Daily Walking",
        "EU 35-45",
        [("Lavender", (190, 174, 224)), ("Cream", (228, 222, 205)), ("Black", (12, 12, 12)), ("Black White", (25, 25, 25))],
        "Lace-Up", "Knitted Textile Upper", "Spring, Summer, Autumn", "Daily walking, commuting, travel",
        "Walking Shoes", "Lightweight lace-up walking shoe for long daily wear",
        "KNITTED TEXTILE UPPER", "LACE-UP WALKING FIT", "SOFT WALKING SOLE",
        ["men knit walking shoes", "lightweight lace-up sneakers", "daily walking casual shoes"],
        [
            "Walking-Oriented Style: Source package positions the shoe for more daily walking.",
            "Knitted Upper: Textile upper gives a soft and breathable casual feel.",
            "Lace-Up Closure: Adjustable fit helps buyers cover different foot shapes.",
            "Neutral Color Mix: Black, cream and lavender support broader retail choices.",
        ],
        ["Confirm if this model is men-only or unisex.", "Confirm outsole/midsole material.", "Confirm MOQ, inventory, lead time and packing details."],
        color_hints=["1 (1)", "1 (13)", "1 (7)", "1 (10)"],
    ),
    Product(
        "BQ019", "A206",
        ["A206情侣鞋图片"],
        "Breathable Knit Casual Shoes",
        "Wholesale Breathable Knit Lace-Up Walking Shoes Lightweight Cushion Sole Casual Sneakers for Men Women",
        "EU 35-45",
        [("Black", (20, 20, 20)), ("Cream", (222, 216, 200)), ("Light Grey", (178, 188, 190)), ("White", (235, 235, 230))],
        "Lace-Up", "Breathable Knitted Upper", "Spring, Summer, Autumn", "Daily walking, commuting, casual wear",
        "Knit Walking Shoes", "Breathable couple-style lace-up walking sneakers",
        "BREATHABLE KNIT UPPER", "LACE-UP CASUAL FIT", "LIGHTWEIGHT SOLE",
        ["couple knit walking shoes", "breathable lace-up sneakers", "men women casual walking shoes"],
        [
            "Couple Style: Men/women casual appearance supports mixed market buying.",
            "Breathable Knit Upper: Open knit texture supports spring and summer daily wear.",
            "Lace-Up Closure: Adjustable fit improves buyer confidence for different customers.",
            "Simple Retail Colors: Black, cream and light grey are easy to match.",
        ],
        ["Confirm exact size range if not all colors cover EU 35-45.", "Confirm outsole/midsole material.", "Confirm MOQ, lead time, packing and inventory."],
        source_hints=["20.jpg", "19.jpg", "18.jpg", "15.jpg"],
        color_hints=["20.jpg", "19.jpg", "18.jpg", "15.jpg"],
    ),
    Product(
        "BQ020", "A218",
        ["A218贝强鞋业夏季透孔一脚蹬男女鞋35-45批55元"],
        "Summer Breathable Walking Shoes",
        "Wholesale Summer Hollow Knit Lace-Up Walking Shoes Breathable Cushion Sole Casual Sneakers for Men Women",
        "EU 35-45",
        [("Black White", (20, 20, 20)), ("All Black", (5, 5, 5)), ("Grey", (170, 174, 178)), ("White", (235, 235, 230))],
        "Lace-Up", "Hollow Knitted Upper", "Spring, Summer", "Daily walking, commuting, light outdoor casual wear",
        "Breathable Walking Shoes", "Summer hollow upper is the main search and click point",
        "HOLLOW KNIT UPPER", "SUMMER AIRFLOW FIT", "CUSHION WALKING SOLE",
        ["summer breathable walking shoes", "hollow knit lace-up sneakers", "lightweight casual shoes"],
        [
            "Hollow Knit Upper: Visible ventilation design supports summer buyer intent.",
            "Lace-Up Fit: Adjustable closure makes the style more stable than slip-on shoes.",
            "Light Casual Sole: Suitable for daily walking, commuting and casual use.",
            "Basic Color Range: Black, white and grey cover common wholesale demand.",
        ],
        ["Confirm outsole/midsole material.", "Confirm whether all color variants share the same material and size range.", "Confirm MOQ, lead time and package data."],
        color_hints=["主图 (1)", "主图 (3)", "主图 (4)", "主图 (2)"],
    ),
    Product(
        "BQ021", "K6212",
        ["贝强鞋业K6212款35-45批53元"],
        "Winter Slip-On Walking Shoes",
        "Wholesale Textile Slip-On Walking Shoes Optional Fleece Lined Cushion Sole Casual Sneakers for Daily Wear",
        "EU 35-45",
        [("Black White", (25, 25, 25)), ("All Black", (5, 5, 5)), ("White", (238, 238, 235)), ("Blue", (34, 107, 162)), ("Grey", (120, 127, 135))],
        "Slip-On", "Stretch Textile Upper", "Autumn, Winter", "Daily walking, commuting, casual wear",
        "Slip-On Walking Shoes", "Optional fleece image exists in source package",
        "STRETCH TEXTILE UPPER", "EASY SLIP-ON FIT", "CUSHION WALKING SOLE",
        ["winter slip-on walking shoes", "textile sock sneakers", "optional fleece casual shoes"],
        [
            "Slip-On Convenience: Easy on/off structure is suitable for everyday casual buyers.",
            "Textile Upper: Stretch textile upper gives a soft sock-like fit.",
            "Optional Fleece Evidence: Source package includes fleece images for black white and all black.",
            "Color Options: White, black, blue and grey options support mixed wholesale orders.",
        ],
        ["Confirm whether regular and fleece-lined versions should publish in one listing.", "Confirm fleece coverage by color.", "Confirm outsole/midsole material and real lining material.", "Confirm MOQ, lead time and package data."],
        "Potential overlap with A2208 and biscuit-sole slip-on styles; keep separate only if fleece/sole/upper differences are used clearly.",
        ["23.jpg", "24.jpg", "21.jpg", "20.jpg", "14.jpg", "18.jpg"],
        color_hints=["20.jpg", "23.jpg", "14.jpg", "24.jpg", "18.jpg"],
    ),
    Product(
        "BQ022", "A2208",
        ["A2208情侣鞋图片", "A2208"],
        "Striped Knit Slip-On Shoes",
        "Wholesale Striped Knit Slip-On Walking Shoes Lightweight Sock Sneakers for Men Women Daily Walking",
        "EU 35-45",
        [("Black", (18, 18, 18)), ("Black White Stripe", (210, 214, 218)), ("Light Grey", (190, 194, 196))],
        "Slip-On", "Striped Knitted Upper", "Spring, Summer, Autumn", "Daily walking, commuting, travel",
        "Slip-On Walking Shoes", "Two A2208 raw packages merged to avoid duplicate listing risk",
        "STRIPED KNIT UPPER", "EASY SOCK-LIKE FIT", "LIGHT WALKING SOLE",
        ["striped knit slip-on shoes", "sock walking sneakers", "men women casual slip-on shoes"],
        [
            "Merged Source Package: Two A2208 folders are treated as the same product material pool.",
            "Striped Knit Upper: Clear stripe pattern gives a distinct search-result visual.",
            "Slip-On Fit: Sock-like opening supports quick everyday use.",
            "Couple Style: Neutral colors work for men/women casual markets.",
        ],
        ["Current upload assets use 3 confirmed color photos only; do not upload Black Grey as a separate SKU unless the factory confirms another colorway.", "Confirm exact size range and color availability.", "Confirm that both A2208 source folders are the same model.", "Confirm outsole/midsole material.", "Confirm MOQ, lead time and package data."],
        "Do not publish the two A2208 folders as separate links unless supplier confirms a meaningful product difference.",
        ["14.jpg", "15.jpg", "12.jpg", "11.jpg", "6.jpg", "8.jpg", "9.jpg"],
        color_hints=["14.jpg", "13.jpg", "15.jpg"],
    ),
    Product(
        "BQ023", "A505",
        ["A505数据包"],
        "Soft Slip-On Walking Shoes",
        "Wholesale Soft Knit Slip-On Walking Shoes Lightweight Cushion Sole Casual Sneakers for Daily Walking",
        "EU 35-45",
        [("Black", (15, 15, 15)), ("Grey", (140, 145, 148)), ("Brown", (139, 78, 42))],
        "Slip-On", "Soft Knitted Upper", "Spring, Summer, Autumn", "Daily walking, commuting, travel",
        "Slip-On Walking Shoes", "Soft low-cut slip-on with brown/grey/black retail colors",
        "SOFT KNIT UPPER", "LOW-CUT SLIP-ON FIT", "FLEXIBLE CUSHION SOLE",
        ["soft knit slip-on shoes", "lightweight walking sneakers", "casual daily walking shoes"],
        [
            "Soft Slip-On Style: Low-cut opening is easy for everyday wear.",
            "Knitted Upper: Soft textile upper supports casual comfort positioning.",
            "Retail Color Mix: Black, grey and brown provide simple market choices.",
            "Daily Use: Suitable for walking, commuting, travel and light casual wear.",
        ],
        ["Confirm size range because package name does not show it clearly.", "Confirm outsole/midsole material.", "Confirm MOQ, inventory, lead time and package data."],
        "Similar to A1689/A830 slip-on styles; keep separate only if outsole/upper/color target is positioned clearly.",
        ["1.jpg", "2.jpg", "3.jpg", "23.jpg", "24.jpg", "19.jpg"],
    ),
    Product(
        "BQ024", "A830",
        ["A830贝强工厂店37-45批55元"],
        "Men Slip-On Walking Shoes",
        "Factory Direct Soft Knit Slip-On Walking Shoes Lightweight Cushion Sole Casual Shoes for Men Daily Walking",
        "EU 37-45",
        [("Dark Grey", (64, 70, 75)), ("Light Grey", (190, 190, 184)), ("Yellow Sole", (238, 190, 18)), ("All Black", (10, 10, 10))],
        "Slip-On", "Soft Knitted Upper", "Spring, Summer, Autumn", "Men daily walking, commuting, casual wear",
        "Men Slip-On Shoes", "Men-size slip-on range starts at EU 37",
        "SOFT KNIT UPPER", "MEN SLIP-ON FIT", "SOFT CUSHION SOLE",
        ["men slip-on walking shoes", "soft knit casual shoes", "lightweight daily shoes"],
        [
            "Men Size Range: EU 37-45 fits a different buyer target from small-size kids/women styles.",
            "Soft Knit Upper: Simple textile upper supports daily walking comfort.",
            "Slip-On Design: No-lace opening is easy for workday and commuting use.",
            "Color Sole Choice: Yellow sole variant creates a visible retail difference.",
        ],
        ["Confirm if EU 37-45 applies to every color.", "Confirm outsole/midsole material.", "Confirm MOQ, lead time and package data."],
        "Similar to low-cut slip-on styles; use men size range and yellow-sole option to separate it.",
    ),
    Product(
        "BQ025", "A1689",
        ["A1689情侣鞋图片"],
        "Low Cut Slip-On Walking Shoes",
        "Wholesale Low Cut Knit Slip-On Walking Shoes Lightweight Cushion Sole Casual Sneakers for Men Women",
        "EU 35-45",
        [("Light Grey", (190, 198, 204)), ("Black White", (18, 18, 18)), ("All Black", (5, 5, 5))],
        "Slip-On", "Low Cut Knitted Upper", "Spring, Summer, Autumn", "Daily walking, commuting, casual wear",
        "Low Cut Slip-On Shoes", "Minimal low-cut slip-on couple shoe",
        "LOW-CUT KNIT UPPER", "EASY SLIP-ON FIT", "LIGHT WALKING SOLE",
        ["low cut slip-on shoes", "couple casual walking sneakers", "knit walking shoes"],
        [
            "Low-Cut Profile: Cleaner opening creates a different look from higher sock-style slip-ons.",
            "Couple Style: Black and grey options fit mixed men/women retail demand.",
            "Soft Knit Upper: Textile upper supports easy daily comfort positioning.",
            "Lightweight Casual Use: Suitable for daily walking, commuting and travel.",
        ],
        ["Confirm exact size range.", "Confirm outsole/midsole material.", "Confirm MOQ, inventory, lead time and package data."],
        "Potential duplicate risk with A505/A830; keep separate only because upper opening and product silhouette differ.",
        ["x366A9293", "x366A9294", "x366A9295", "x366A9296", "x366A9297"],
        color_hints=["x366A9293", "x366A9294", "x366A9295"],
    ),
    Product(
        "BQ026", "T5828",
        ["T5828"],
        "Lightweight Knit Walking Shoes",
        "Wholesale 177g Breathable Knit Lace-Up Walking Shoes Lightweight Cushion Sole Sneakers for Women",
        "EU 35-45",
        [("Black", (20, 20, 20)), ("White", (238, 238, 232)), ("Grey", (86, 99, 104)), ("Red", (210, 22, 28)), ("Pink", (236, 174, 184))],
        "Lace-Up", "Breathable Knitted Upper", "Spring, Summer, Autumn", "Daily walking, commuting, casual wear",
        "Lightweight Walking Shoes", "Source image shows approx. 177g per single shoe",
        "BREATHABLE KNIT UPPER", "LACE-UP LIGHT FIT", "177G LIGHTWEIGHT FEEL",
        ["177g lightweight walking shoes", "breathable knit lace-up sneakers", "women casual walking shoes"],
        [
            "Lightweight Evidence: Source image shows about 177g per single shoe.",
            "Breathable Knit Upper: Knit surface supports airflow for daily wear.",
            "Lace-Up Closure: Adjustable fit improves buyer confidence.",
            "Color Range: Black, white, grey, red and pink support retail SKU selection.",
        ],
        ["Confirm whether 177g applies to all sizes/colors or only sampled size.", "Confirm size range and outsole/midsole material.", "Confirm MOQ, lead time and package data."],
        "Original domestic main images contain Chinese text; only cleaned product photos should be used for Alibaba.",
        ["5M4A8135", "5M4A8136", "5M4A8137", "5M4A8138", "5M4A8139", "5M4A8143", "5M4A8144", "5M4A8145"],
    ),
    Product(
        "BQ027", "K6116",
        ["贝强工厂店K6116情侣款35-45批55元限价79"],
        "Knit Casual Walking Shoes",
        "Wholesale Knit Lace-Up Walking Shoes Lightweight Chunky Cushion Sole Casual Sneakers for Men Women",
        "EU 35-45",
        [("Cream", (232, 226, 210)), ("Black", (8, 8, 8)), ("Black White", (25, 25, 25)), ("Grey", (182, 188, 190))],
        "Lace-Up", "Knitted Textile Upper", "Spring, Summer, Autumn", "Daily walking, commuting, casual wear",
        "Knit Walking Shoes", "Chunky lace-up knit shoe with white/black sole variants",
        "KNIT TEXTILE UPPER", "LACE-UP CASUAL FIT", "CHUNKY CUSHION SOLE",
        ["knit lace-up walking shoes", "chunky sole casual sneakers", "couple walking shoes"],
        [
            "Chunky Sole Look: More structured outsole helps separate it from thin slip-on styles.",
            "Knit Upper: Textile upper supports casual walking and commuting use.",
            "Lace-Up Fit: Adjustable closure works for daily movement.",
            "Source Fleece Folder: Package includes fleece main images that need confirmation.",
        ],
        ["Confirm whether fleece option belongs in the same product listing.", "Confirm outsole/midsole material.", "Confirm MOQ, lead time, size-color availability and package data."],
        source_hints=["x366A0519", "x366A0520", "x366A0521", "x366A0523", "x366A0525", "X366A0802"],
        color_hints=["x366A0519", "x366A0521", "x366A0523", "x366A0525"],
    ),
    Product(
        "BQ028", "BISCUIT",
        ["贝强鞋业2024秋冬新款饼干鞋底一脚蹬男女鞋35-45批55元"],
        "Winter Slip-On Walking Shoes",
        "Wholesale Biscuit Sole Slip-On Walking Shoes Autumn Winter Knit Casual Sneakers for Men Women",
        "EU 35-45",
        [("Black White", (15, 15, 15)), ("Grey", (115, 125, 132)), ("Apricot", (198, 184, 164)), ("White", (238, 238, 232)), ("Blue", (55, 119, 151))],
        "Slip-On", "Knitted Textile Upper", "Autumn, Winter", "Daily walking, commuting, casual wear",
        "Slip-On Walking Shoes", "Biscuit-style outsole and autumn/winter positioning",
        "KNIT SLIP-ON UPPER", "AUTUMN WINTER FIT", "BISCUIT SOLE TEXTURE",
        ["biscuit sole slip-on shoes", "winter knit walking shoes", "casual sock sneakers"],
        [
            "Biscuit Sole Style: Outsole texture gives a distinct visible selling point.",
            "Slip-On Upper: Sock-like opening supports quick everyday wear.",
            "Autumn/Winter Direction: Source folder includes fleece-related images for confirmation.",
            "Color Range: Black white, grey, apricot, white and blue options support mixed SKU demand.",
        ],
        ["White-background main image has been rebuilt from the black-white fleece source angle.", "Source color note confirms black white, grey, apricot, white and blue; do not use mixed-color group photo as a SKU.", "Confirm fleece availability and whether regular/fleece versions share one listing.", "Confirm outsole/midsole material.", "Confirm MOQ, lead time and packing data."],
        "Potential overlap with K6212/A2208; use biscuit sole and winter/fleece evidence to separate it.",
        ["21.jpg", "10.jpg", "37.jpg", "11.jpg", "31.jpg", "23.jpg", "46.jpg", "43.jpg", "5.jpg", "47.jpg"],
        color_hints=["23.jpg", "46.jpg", "43.jpg", "5.jpg", "47.jpg"],
    ),
    Product(
        "BQ029", "A025",
        ["贝强鞋业A025高帮波浪纹35-45批58元全网限价88元"],
        "High Top Sock Walking Shoes",
        "Wholesale High Top Knit Sock Walking Shoes Wave Pattern Cushion Sole Casual Sneakers for Autumn Winter",
        "EU 35-45",
        [("Black White", (10, 10, 10)), ("All Black", (5, 5, 5))],
        "Slip-On", "High Top Knit Textile Upper", "Autumn, Winter", "Daily walking, commuting, casual wear",
        "High Top Walking Shoes", "High-top sock silhouette is clearly different from low-cut slip-ons",
        "HIGH TOP KNIT UPPER", "SOCK-LIKE ANKLE FIT", "WAVE PATTERN SOLE",
        ["high top sock walking shoes", "knit ankle sneakers", "winter casual shoes"],
        [
            "High-Top Profile: Sock-style ankle height creates a clear separate listing reason.",
            "Wave Texture Upper: Visual texture helps search-result differentiation.",
            "Slip-On Convenience: Stretch opening supports easy daily wear.",
            "Autumn/Winter Style: Higher upper suits colder-season casual markets.",
        ],
        ["Confirm if all-black and black-white are both available.", "Confirm outsole/midsole material.", "Confirm real lining material, MOQ, lead time and package data."],
    ),
    Product(
        "BQ030", "A811",
        ["贝强鞋业A811童鞋31-40批55元全网限价76元"],
        "Kids Walking Shoes",
        "Wholesale Kids Breathable Mesh Lace-Up Walking Shoes Lightweight Cushion Sole Sneakers for Boys Girls",
        "EU 31-40",
        [("Pink", (238, 148, 164)), ("Purple", (91, 56, 135)), ("Grey", (142, 146, 150)), ("Green", (17, 122, 78))],
        "Lace-Up", "Breathable Mesh Upper", "Spring, Summer, Autumn", "School, daily walking, casual wear",
        "Kids Walking Shoes", "Kids size range and colorful mesh upper",
        "BREATHABLE MESH UPPER", "KIDS LACE-UP FIT", "LIGHT CUSHION SOLE",
        ["kids mesh walking shoes", "boys girls lace-up sneakers", "lightweight school shoes"],
        [
            "Kids Size Range: EU 31-40 clearly targets boys/girls markets.",
            "Breathable Mesh Upper: Mesh panels support spring and summer daily wear.",
            "Lace-Up Fit: Adjustable closure improves secure daily use.",
            "Color Options: Grey, pink, green and purple fit children's retail assortment.",
        ],
        ["Confirm child size table and age positioning.", "Confirm outsole/midsole material.", "Confirm MOQ, lead time, package weight and carton details."],
        "Keep separate from BQ016 because this is lace-up kids sneaker, not slip-on knit shoe.",
        color_hints=["01 (5)", "01 (6)", "01 (7)", "01 (8)"],
    ),
]


def collect_product_images(product: Product, roots: list[Path]) -> list[Path]:
    dirs = source_dirs(roots)
    transparent = [p for d in dirs if ("透明" in d.name or d.name in {"png", "PNG"}) for p in all_images(d)]
    main = [p for d in dirs if score_source_dir(d) >= 35 for p in sorted([x for x in d.iterdir() if x.is_file() and x.suffix.lower() in IMG_EXTS], key=natural_key)]
    everything = list(dict.fromkeys(transparent + main + [p for r in roots for p in all_images(r)]))
    return find_by_hints(everything, product.source_hints, 18)


def collect_color_images(product: Product, roots: list[Path], fallback: list[Path]) -> list[Path]:
    if not product.color_hints:
        return fallback
    priority: list[Path] = []
    for d in source_dirs(roots):
        priority.extend(sorted([p for p in d.iterdir() if p.is_file() and p.suffix.lower() in IMG_EXTS], key=natural_key))
    everything = list(dict.fromkeys(priority + [p for root in roots for p in all_images(root)]))
    return find_by_hints(everything, product.color_hints, max(len(product.colors), 6))


def write_form(product: Product, out_dir: Path) -> None:
    color_text = ", ".join(f"`{name}`" for name, _ in product.colors)
    pending_text = "\n".join(f"- {item}" for item in product.pending)
    selling_text = "\n".join(f"{i + 1}. {point}" for i, point in enumerate(product.selling_points))
    keyword_text = "\n".join(f"- `{kw}`" for kw in product.keywords)
    duplicate = product.duplicate_note or "No obvious duplicate issue beyond normal style similarity; still compare before publishing."
    content = f"""# {product.code}_{product.model} 上架填写表

## 基本信息

- 商品名称: `{product.title}`
- 商品分组: `{product.group}`
- 品牌: `Beiqiang`
- 型号: `{product.model}`
- 尺码范围: `{product.size_range}`
- 颜色: {color_text}
- 产品角色: 新上架候选。发布前需要确认差异点和高影响字段。

## 策略简报

- 买家搜索意图: {", ".join(product.keywords)}
- 点击理由: {product.detail_subtitle}
- 转化理由: 图片集已覆盖产品外观、上脚/结构、尺码参考、颜色和订单支持。
- 平台流量逻辑: 标题、属性、卖点和图片围绕同一产品关键词，不把同款素材拆成重复链接。
- 重复风险: {duplicate}

## 关键词/卖点字段

{keyword_text}

## 必填属性建议

| 字段 | 建议填写 | 说明 |
|---|---|---|
| Outsole material | `EVA` | 视觉和贝强历史款式推断，最终发布前请供应商确认 |
| Upper material | `Textile` | 细节可写 `{product.upper}` |
| Origin | `China` | 固定填写 |
| Midsole material | `EVA` | 最终发布前确认 |
| Lining material | `Mesh/Textile` | 加绒或特殊内里必须按实际款式确认 |

## 其他属性建议

- Province: `Fujian`
- Product features: `Comfort`, `Light Weight`, `Breathable`, `Anti-Slip` when supported by final photos
- Season: `{product.season}`
- Style: `{product.core_keyword}`
- Pattern type: `Solid` or actual color pattern
- Closure type: `{product.closure}`
- Toe style: `Round Toe`
- Leather type / logo process / logo position: leave blank unless supplier provides evidence

## 自定义属性

| 属性名 | 属性值 |
|---|---|
| Upper Material Detail | {product.upper} |
| Sole Type | Cushion sole, EVA to confirm |
| Size Range | {product.size_range} |
| Closure | {product.closure} |
| Application | {product.application} |
| Packing | Shoe Box or Plastic Bag |
| Sample Policy | Sample Fee Can Be Deducted from Bulk Order |

## 商品卖点

{selling_text}

## 图片上传顺序

主图: `01_主图/01_main.jpg`, `02_upper.jpg`, `03_fit.jpg`, `04_sole.jpg`, `05_colors.jpg`, `06_scene.jpg`

详情页: `02_详情页/01_size.jpg`, `02_info.jpg`, `03_upper.jpg`, `04_sole.jpg`, `05_colors.jpg`, `06_order.jpg`

颜色图: 使用 `03_颜色图/` 中对应颜色图片。颜色名以实际后台规格为准。

## 待确认

{pending_text}
"""
    (out_dir / FORM_NAME).write_text(content, encoding="utf-8")


def make_product(product: Product) -> None:
    raw_roots = [find_raw(name) for name in product.raw_names]
    out_dir = UPLOAD_ROOT / product.folder_name
    main_dir = out_dir / MAIN_DIR
    detail_dir = out_dir / DETAIL_DIR
    color_dir = out_dir / COLOR_DIR
    ref_dir = out_dir / REF_DIR
    for path in [main_dir, detail_dir, color_dir, ref_dir]:
        clear_direct_files(path)

    selected = collect_product_images(product, raw_roots)
    if not selected:
        raise RuntimeError(f"No images selected for {product.code}")
    color_selected = collect_color_images(product, raw_roots, selected)
    hero = selected[0]

    make_plain_main(main_dir / "01_main.jpg", product, hero)
    make_feature(main_dir / "02_upper.jpg", product, hero, product.feature_title, product.upper, ["Soft Textile", "Breathable Feel", "Daily Comfort"], (18, 118, 99))
    make_feature(main_dir / "03_fit.jpg", product, hero, product.fit_title, f"{product.closure} closure for everyday wear", [product.closure, "Easy Daily Wear", product.size_range], (37, 99, 235))
    make_feature(main_dir / "04_sole.jpg", product, hero, product.sole_title, "Built for walking, commuting and casual use", ["Cushion Feel", "Textured Support", "Stable Step"], (124, 58, 237))
    make_color_image(main_dir / "05_colors.jpg", product, color_selected)
    make_feature(main_dir / "06_scene.jpg", product, hero, "DAILY WALKING USE", product.application, ["Walking", "Commuting", "Travel", "Casual Wear"], (217, 119, 6))

    make_size_chart(detail_dir / "01_size.jpg", product, hero)
    make_info(detail_dir / "02_info.jpg", product, hero)
    make_feature(detail_dir / "03_upper.jpg", product, hero, product.feature_title, product.upper, ["Product-Led Detail", "Source Photo Anchor", "Clean B2B Layout"], (18, 118, 99))
    make_feature(detail_dir / "04_sole.jpg", product, hero, product.sole_title, "Cushion feel for walking, commuting and casual wear", ["Cushion Sole", "Daily Walking", "Stable Step"], (124, 58, 237))
    make_color_image(detail_dir / "05_colors.jpg", product, color_selected)
    make_order(detail_dir / "06_order.jpg", product, hero)

    used_names: set[str] = set()
    for i, (name, _) in enumerate(product.colors):
        src = selected[min(i, len(selected) - 1)]
        src = color_selected[min(i, len(color_selected) - 1)]
        filename = safe_filename(name)
        while filename in used_names:
            filename = safe_filename(f"{name}_{i + 1}")
        used_names.add(filename)
        canvas = Image.new("RGBA", (900, 900), (255, 255, 255, 255))
        paste_fit(canvas, src, (45, 45, 855, 855), shadow=False)
        save_jpg(canvas, color_dir / filename)

    make_contact_sheet(ref_dir / "source_contact.jpg", product, selected)
    (ref_dir / "source_manifest.txt").write_text(
        "\n".join(str(p.relative_to(ROOT)) for p in selected),
        encoding="utf-8",
    )
    write_form(product, out_dir)


def rename_raw_packages() -> None:
    failures: list[str] = []
    for product in PRODUCTS:
        for idx, name in enumerate(product.raw_names):
            src = find_raw(name)
            supplement = "补充_" if len(product.raw_names) > 1 and idx > 0 else ""
            target_name = f"已整理_{product.code}_{product.model}_{supplement}{src.name}"
            target = src.with_name(target_name)
            if src.name.startswith("已整理_") or target.exists():
                continue
            if ROOT not in src.resolve().parents or ROOT not in target.resolve().parents:
                raise RuntimeError(f"Unsafe rename target: {src} -> {target}")
            for attempt in range(3):
                try:
                    src.rename(target)
                    break
                except PermissionError:
                    gc.collect()
                    time.sleep(1 + attempt)
            else:
                failures.append(f"{src.name} -> {target.name}")
    failure_log = UPLOAD_ROOT / "raw_rename_failures.txt"
    if failures:
        failure_log.write_text("\n".join(failures), encoding="utf-8")
        print(f"Raw rename failures: {len(failures)}. See {failure_log}")
    elif failure_log.exists():
        failure_log.unlink()


def write_batch_readme() -> None:
    rows = []
    for product in PRODUCTS:
        rows.append(f"| {product.code}_{product.model} | {product.group} | {product.size_range} | {product.closure} | {product.detail_subtitle} |")
    content = f"""# 2026-06-16 新数据包整理说明

本批按 Alibaba International Station skill 的产品页逻辑整理，输出位置:

```text
{UPLOAD_ROOT}
```

每个产品目录包含:

```text
00_上架填写表.md
01_主图/
02_详情页/
03_颜色图/
04_参考预览/
```

## 本批产品映射

| 内部编码 | 产品分组 | 尺码 | 闭合方式 | 核心差异 |
|---|---|---|---|---|
{chr(10).join(rows)}

## 处理原则

- A2208 两个原始包合并为 `BQ022_A2208`，不单独拆成两个链接，避免重复产品分散流量。
- 第一张主图使用清洁产品图，不放中文促销文案和内部确认文字。
- 国内详情页和带中文的主图只作为证据，不直接作为国际站上传图。
- 图片中的鞋款、颜色、结构均来自原始包照片；不使用虚假证书、评论、品牌或医疗/防水等未确认承诺。
- 高影响字段写在填写表的待确认区: 材质、尺码、加绒范围、MOQ、交期、包装重量、箱规和物流/报关字段。

## 发布前重点确认

- 所有款式的大底/中底是否最终确认为 EVA。
- K6212、K6116、饼干底等带加绒素材的款式，常规款和加绒款是否同链接发布。
- 儿童/女鞋混合尺码款是否按 kids、girls 还是 women/kids 混合定位。
- 每款 MOQ、样品费、交期、库存、包装尺寸、毛重和箱规。
"""
    (UPLOAD_ROOT / "README_20260616_新包整理说明.md").write_text(content, encoding="utf-8")


def main() -> None:
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    for product in PRODUCTS:
        make_product(product)
    write_batch_readme()
    rename_raw_packages()
    print(f"Organized {len(PRODUCTS)} product folders under {UPLOAD_ROOT}")


if __name__ == "__main__":
    main()
