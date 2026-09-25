"""Build traceable, deterministic HR002/2618 SKU and hero candidates.

These outputs are local QA candidates, never automatic Alibaba uploads.
Only crop/resize/composite source pixels; do not alter the shoe.
"""

from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
SOURCE = ROOT / "99_临时区" / "HR002_2618_货源候选_2026-09-24"
OUTPUT = SOURCE / "本地候选_v1"
OUTPUT.mkdir(parents=True, exist_ok=True)
SIZE = 1200
GREEN = (16, 76, 61)
INK = (27, 36, 39)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    file = "arialbd.ttf" if bold else "arial.ttf"
    return ImageFont.truetype(str(Path(r"C:\Windows\Fonts") / file), size)


def load(name: str) -> Image.Image:
    return Image.open(SOURCE / name).convert("RGB")


def crop_card(path: str, box: tuple[int, int, int, int]) -> Image.Image:
    image = load(path)
    assert 0 <= box[0] < box[2] <= image.width
    assert 0 <= box[1] < box[3] <= image.height
    return image.crop(box)


def white_square(image: Image.Image, max_box: tuple[int, int] = (1080, 1080)) -> Image.Image:
    square = Image.new("RGB", (SIZE, SIZE), "white")
    fitted = ImageOps.contain(image, max_box, Image.Resampling.LANCZOS)
    square.paste(fitted, ((SIZE - fitted.width) // 2, (SIZE - fitted.height) // 2))
    return square


def save(image: Image.Image, name: str) -> None:
    image.save(OUTPUT / name, quality=94, subsampling=0)


# Source #25 is a two-panel genuine color card. Source #26 is the black card.
# Crops exclude Chinese color labels and keep only a single true-color pair.
sku_sources = {
    "khaki": ("详情原图/25.jpg", (56, 136, 426, 566)),
    "brown": ("详情原图/25.jpg", (56, 758, 426, 1198)),
    "black": ("详情原图/26.jpg", (56, 145, 395, 562)),
}
for color, (path, box) in sku_sources.items():
    save(white_square(crop_card(path, box), (1020, 1020)), f"SKU_2618_{color}.jpg")


def hero(image: Image.Image, title: str, name: str) -> None:
    canvas = Image.new("RGB", (SIZE, SIZE), "white")
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((64, 32, 378, 112), radius=14, fill=GREEN)
    draw.text((84, 59), "WHOLESALE · B2B", font=font(28, True), fill="white")
    draw.text((412, 55), title, font=font(28, True), fill=INK)
    fitted = ImageOps.contain(image, (1080, 1030), Image.Resampling.LANCZOS)
    canvas.paste(fitted, ((SIZE - fitted.width) // 2, 145 + (1015 - fitted.height) // 2))
    save(canvas, name)


# A is a clean source pair on a studio background. B/C use genuine on-foot
# photographs, not colorized versions of A. They remain local candidates until
# full-resolution hero and source comparison pass.
hero(load("2618_公开首图.jpg"), "MODEL 2618 · KHAKI", "M1A_2618_khaki.jpg")
hero(crop_card("详情原图/16.jpg", (15, 485, 785, 1012)), "MODEL 2618 · BLACK", "M1B_2618_black.jpg")
hero(crop_card("详情原图/19.jpg", (15, 398, 785, 940)), "MODEL 2618 · DARK BROWN", "M1C_2618_brown.jpg")


paths = [
    OUTPUT / "M1A_2618_khaki.jpg",
    OUTPUT / "M1B_2618_black.jpg",
    OUTPUT / "M1C_2618_brown.jpg",
    OUTPUT / "SKU_2618_khaki.jpg",
    OUTPUT / "SKU_2618_black.jpg",
    OUTPUT / "SKU_2618_brown.jpg",
]
sheet = Image.new("RGB", (1200, 830), "#e8eeeb")
draw = ImageDraw.Draw(sheet)
for index, path in enumerate(paths):
    with Image.open(path) as src:
        thumb = src.resize((380, 380), Image.Resampling.LANCZOS)
    x = (index % 3) * 400 + 10
    y = (index // 3) * 415 + 10
    sheet.paste(thumb, (x, y))
    draw.text((x, y + 384), path.stem, font=font(18, True), fill=INK)
sheet.save(OUTPUT / "contact_hero_sku.jpg", quality=90)
print(OUTPUT)
