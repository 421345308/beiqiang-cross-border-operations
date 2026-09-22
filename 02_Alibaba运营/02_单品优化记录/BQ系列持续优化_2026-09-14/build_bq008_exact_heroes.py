#!/usr/bin/env python3
"""Build exact-pixel BQ008/L1009 main-image variants.

Only conservative cropping and uniform resizing are applied to verified,
unbranded product photos. No shoe pixels, colors, sole geometry, upper
structure, or closure details are generated or retouched.
"""

from pathlib import Path

from PIL import Image, ImageChops


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
SOURCE = ROOT / "01_产品资产/02_可发布素材/00_最终上传/BQ008_L1009/01_主图"
OUTPUT = ROOT / "01_产品资产/02_可发布素材/00_最终上传/BQ008_L1009/05_优化候选_2026-09-14"

VARIANTS = {
    "BQ008-W1_grey-green_exact.png": "02_greeng_clean.png",
    "BQ008-R1_white-black_exact.png": "03_white_clean.png",
    "BQ008-O1_all-black_exact.png": "04_black_clean.png",
}


def content_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    rgb = image.convert("RGB")
    white = Image.new("RGB", rgb.size, "white")
    difference = ImageChops.difference(rgb, white).convert("L")
    mask = difference.point(lambda value: 255 if value > 8 else 0)
    bbox = mask.getbbox()
    if not bbox:
        raise ValueError("No product pixels found")
    left, top, right, bottom = bbox
    margin = max(8, round(max(rgb.size) * 0.02))
    return (
        max(0, left - margin),
        max(0, top - margin),
        min(rgb.width, right + margin),
        min(rgb.height, bottom + margin),
    )


def build(source_name: str, output_name: str) -> None:
    source = Image.open(SOURCE / source_name).convert("RGB")
    product_rect = source.crop(content_bbox(source))

    target_width = 920
    scale = target_width / product_rect.width
    target_height = round(product_rect.height * scale)
    if target_height > 790:
        target_height = 790
        scale = target_height / product_rect.height
        target_width = round(product_rect.width * scale)

    product_rect = product_rect.resize(
        (target_width, target_height), Image.Resampling.LANCZOS
    )
    canvas = Image.new("RGB", (1000, 1000), "white")
    x = (1000 - target_width) // 2
    y = (1000 - target_height) // 2 + 18
    canvas.paste(product_rect, (x, y))

    OUTPUT.mkdir(parents=True, exist_ok=True)
    canvas.save(OUTPUT / output_name, format="PNG", optimize=True)


def main() -> None:
    for output_name, source_name in VARIANTS.items():
        build(source_name, output_name)
        print(OUTPUT / output_name)


if __name__ == "__main__":
    main()
