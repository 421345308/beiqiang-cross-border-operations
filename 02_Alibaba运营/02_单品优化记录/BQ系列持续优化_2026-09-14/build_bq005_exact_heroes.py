#!/usr/bin/env python3
"""Build exact-photo BQ005/A503 hero variants.

Only crop, uniform resize and white-canvas placement are used. The selected
pixels come from verified unbranded product photos. No shoe shape, outsole,
upper, closure or color is generated or retouched.
"""

from pathlib import Path

from PIL import Image


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
SOURCE = ROOT / "01_产品资产/02_可发布素材/00_最终上传/BQ005_A503/01_主图"
OUTPUT = ROOT / "01_产品资产/02_可发布素材/00_最终上传/BQ005_A503/05_优化候选_2026-09-14"

# Crop boxes were selected after visual review and retain every shoe pixel,
# including outsole edges, pull tabs, laces and natural product shadows.
VARIANTS = {
    "BQ005-W1_four-colors_exact.png": ("02_colors.jpg", (20, 160, 780, 670), 940),
    "BQ005-R1_pink_exact.png": ("04_pink.jpg", (45, 85, 755, 720), 900),
    "BQ005-O1_all-black_exact.png": ("05_black.jpg", (45, 180, 675, 650), 920),
}


def build(output_name: str, source_name: str, crop: tuple[int, int, int, int], target_width: int) -> None:
    source = Image.open(SOURCE / source_name).convert("RGB")
    if not (0 <= crop[0] < crop[2] <= source.width and 0 <= crop[1] < crop[3] <= source.height):
        raise ValueError(f"Crop {crop} is outside {source_name} dimensions {source.size}")
    image = source.crop(crop)
    scale = target_width / image.width
    target_height = round(image.height * scale)
    if target_height > 820:
        target_height = 820
        target_width = round(image.width * (target_height / image.height))
    image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)

    canvas = Image.new("RGB", (1000, 1000), "white")
    x = (1000 - target_width) // 2
    y = (1000 - target_height) // 2 + 12
    canvas.paste(image, (x, y))

    OUTPUT.mkdir(parents=True, exist_ok=True)
    canvas.save(OUTPUT / output_name, format="PNG", optimize=True)


def main() -> None:
    for output_name, (source_name, crop, target_width) in VARIANTS.items():
        build(output_name, source_name, crop, target_width)
        print(OUTPUT / output_name)


if __name__ == "__main__":
    main()
