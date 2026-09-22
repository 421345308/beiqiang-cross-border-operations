from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
COLOR_SOURCE = ROOT / "01_产品资产/02_可发布素材/00_最终上传/BQ026_T5828/03_颜色图"
RAW_SOURCE = ROOT / "01_产品资产/01_原始数据包/已整理_BQ026_T5828_T5828/T5828/800X800主图"
OUTPUT = ROOT / "02_Alibaba运营/02_单品优化记录/BQ系列持续优化_2026-09-14/BQ026_真实鞋型主图_2026-09-14"

SOURCES = {
    "black_clean.jpg": COLOR_SOURCE / "black.jpg",
    "white_clean.jpg": COLOR_SOURCE / "white.jpg",
    "grey_clean.jpg": COLOR_SOURCE / "grey.jpg",
    "red_clean.jpg": COLOR_SOURCE / "red.jpg",
    "pink_clean.jpg": COLOR_SOURCE / "pink.jpg",
    "red_angle.jpg": RAW_SOURCE / "5M4A8149.JPG",
    "pink_pair.jpg": RAW_SOURCE / "5M4A8153.JPG",
    "grey_pair.jpg": RAW_SOURCE / "5M4A8159.JPG",
}


def background_color(image: Image.Image) -> tuple[int, int, int]:
    rgb = image.convert("RGB")
    w, h = rgb.size
    samples = [
        rgb.getpixel((5, 5)),
        rgb.getpixel((w - 6, 5)),
        rgb.getpixel((5, h - 6)),
        rgb.getpixel((w - 6, h - 6)),
    ]
    return tuple(sum(pixel[channel] for pixel in samples) // len(samples) for channel in range(3))


def foreground_box(image: Image.Image, bg: tuple[int, int, int]) -> tuple[int, int, int, int]:
    rgb = image.convert("RGB")
    background = Image.new("RGB", rgb.size, bg)
    difference = ImageChops.difference(rgb, background).convert("L")
    # Ignore light JPEG grain while retaining the real contact shadow.
    mask = difference.point(lambda value: 255 if value > 16 else 0)
    box = mask.getbbox()
    if box is None:
        raise RuntimeError("No foreground detected")
    left, top, right, bottom = box
    pad = 14
    return (
        max(0, left - pad),
        max(0, top - pad),
        min(rgb.width, right + pad),
        min(rgb.height, bottom + pad),
    )


def make_clean_square(source_path: Path, output_path: Path) -> None:
    source = Image.open(source_path).convert("RGB")
    bg = background_color(source)
    crop = source.crop(foreground_box(source, bg))
    scale = min(940 / crop.width, 680 / crop.height)
    target = (max(1, round(crop.width * scale)), max(1, round(crop.height * scale)))
    crop = crop.resize(target, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (1000, 1000), bg)
    x = (1000 - crop.width) // 2
    y = (1000 - crop.height) // 2
    canvas.paste(crop, (x, y))
    canvas.save(output_path, quality=95, subsampling=0, optimize=True)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, source in SOURCES.items():
        make_clean_square(source, OUTPUT / name)
    print(f"created {len(SOURCES)} exact-pixel BQ026 assets in {OUTPUT}")


if __name__ == "__main__":
    main()
