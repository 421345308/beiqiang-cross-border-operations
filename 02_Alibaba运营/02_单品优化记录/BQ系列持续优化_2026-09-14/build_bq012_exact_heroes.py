#!/usr/bin/env python3
"""Build BQ012/M8506 heroes without modifying the supplied shoe pixels.

Only the canvas, color-specific background, scale, placement and contact shadow
are generated.  The product layer is copied from the verified transparent PNG.
"""

from pathlib import Path

from PIL import Image, ImageFilter


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
SOURCE = ROOT / "01_产品资产/02_可发布素材/00_最终上传/BQ012_M8506/03_颜色图"
OUTPUT = ROOT / "01_产品资产/02_可发布素材/00_最终上传/BQ012_M8506/05_优化候选_2026-09-14"

VARIANTS = {
    "BQ012-W1_black-white_exact.png": ("black_white.png", (244, 248, 250), (229, 237, 241)),
    "BQ012-R1_red-white_exact.png": ("red_white.png", (255, 250, 244), (247, 236, 226)),
    "BQ012-O1_all-black_exact.png": ("black_black.png", (244, 245, 246), (218, 223, 226)),
}


def gradient(size: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGB", (size, size))
    pixels = image.load()
    for y in range(size):
        t = y / (size - 1)
        color = tuple(round(a * (1 - t) + b * t) for a, b in zip(top, bottom))
        for x in range(size):
            pixels[x, y] = color
    return image.convert("RGBA")


def build(source_name: str, output_name: str, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> None:
    source = Image.open(SOURCE / source_name).convert("RGBA")
    bbox = source.getbbox()
    if not bbox:
        raise ValueError(f"No visible product pixels in {source_name}")
    product = source.crop(bbox)

    # The product is resampled uniformly; no retouching or generative pixels.
    target_width = 910
    scale = target_width / product.width
    target_height = round(product.height * scale)
    product = product.resize((target_width, target_height), Image.Resampling.LANCZOS)

    canvas = gradient(1000, top, bottom)
    x = (1000 - product.width) // 2
    y = 500 - product.height // 2

    alpha = Image.new("L", canvas.size, 0)
    alpha.paste(product.getchannel("A"), (x, y + 24))
    shadow_alpha = alpha.filter(ImageFilter.GaussianBlur(24)).point(lambda value: round(value * 0.24))
    shadow = Image.new("RGBA", canvas.size, (25, 30, 32, 0))
    shadow.putalpha(shadow_alpha)
    canvas.alpha_composite(shadow)
    canvas.alpha_composite(product, (x, y))

    OUTPUT.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(OUTPUT / output_name, format="PNG", optimize=True)


def main() -> None:
    for output_name, (source_name, top, bottom) in VARIANTS.items():
        build(source_name, output_name, top, bottom)
        print(OUTPUT / output_name)


if __name__ == "__main__":
    main()
