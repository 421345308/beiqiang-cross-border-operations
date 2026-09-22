#!/usr/bin/env python3
"""Build exact-photo BQ006/M8811 main-image variants.

Only content-aware cropping, uniform resizing and white-canvas placement are
applied. Shoe pixels, colors, upper structure, outsole geometry and closure
are never generated, repainted or retouched.
"""

from hashlib import sha256
from pathlib import Path

from PIL import Image, ImageChops


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
SOURCE = ROOT / "01_产品资产/02_可发布素材/00_最终上传/BQ006_M8811/01_主图"
OUTPUT = ROOT / "01_产品资产/02_可发布素材/00_最终上传/BQ006_M8811/05_优化候选_2026-09-14"

VARIANTS = {
    "BQ006-W1_white-green_exact.png": "08_white_green_catalog.png",
    "BQ006-R1_white-pink_exact.png": "06_pink.jpg",
    "BQ006-O1_all-black_exact.png": "07_black.jpg",
}

# The pink source contains one tiny isolated mark above the shoe.  Exclude it
# with a conservative crop that still retains the full shoe and floor shadow;
# no product pixel is edited.
BBOX_OVERRIDES = {
    "06_pink.jpg": (35, 230, 775, 630),
}


def content_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    rgb = image.convert("RGB")
    difference = ImageChops.difference(rgb, Image.new("RGB", rgb.size, "white")).convert("L")
    mask = difference.point(lambda value: 255 if value > 8 else 0)
    bbox = mask.getbbox()
    if not bbox:
        raise ValueError("No product pixels found")
    left, top, right, bottom = bbox
    margin = max(10, round(max(rgb.size) * 0.018))
    expanded = (
        max(0, left - margin),
        max(0, top - margin),
        min(rgb.width, right + margin),
        min(rgb.height, bottom + margin),
    )
    if not (0 <= expanded[0] < expanded[2] <= rgb.width):
        raise ValueError(f"Invalid horizontal crop {expanded} for {rgb.size}")
    if not (0 <= expanded[1] < expanded[3] <= rgb.height):
        raise ValueError(f"Invalid vertical crop {expanded} for {rgb.size}")
    return expanded


def build(source_name: str, output_name: str) -> None:
    source_path = SOURCE / source_name
    source = Image.open(source_path).convert("RGB")
    bbox = BBOX_OVERRIDES.get(source_name, content_bbox(source))
    if not (0 <= bbox[0] < bbox[2] <= source.width and 0 <= bbox[1] < bbox[3] <= source.height):
        raise ValueError(f"Invalid override crop {bbox} for {source.size}")
    product = source.crop(bbox)

    max_width, max_height = 930, 780
    scale = min(max_width / product.width, max_height / product.height)
    target = (round(product.width * scale), round(product.height * scale))
    product = product.resize(target, Image.Resampling.LANCZOS)

    canvas = Image.new("RGB", (1000, 1000), "white")
    x = (canvas.width - product.width) // 2
    y = (canvas.height - product.height) // 2 + 18
    if x < 0 or y < 0 or x + product.width > canvas.width or y + product.height > canvas.height:
        raise ValueError(f"Placement outside canvas: {(x, y, *target)}")
    canvas.paste(product, (x, y))

    OUTPUT.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT / output_name
    canvas.save(output_path, format="PNG", optimize=True)
    digest = sha256(output_path.read_bytes()).hexdigest()
    print(f"{output_path}\tsource={source_name}\tbbox={bbox}\ttarget={target}\tsha256={digest}")


def main() -> None:
    for output_name, source_name in VARIANTS.items():
        build(source_name, output_name)


if __name__ == "__main__":
    main()
