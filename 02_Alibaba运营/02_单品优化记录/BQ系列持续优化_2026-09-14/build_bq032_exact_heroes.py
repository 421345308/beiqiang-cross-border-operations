from __future__ import annotations

from pathlib import Path

from PIL import Image


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
SOURCE = ROOT / "01_产品资产/02_可发布素材/00_最终上传/BQ032_ZX2212/03_颜色图"
OUTPUT = ROOT / "02_Alibaba运营/02_单品优化记录/BQ系列持续优化_2026-09-14/BQ032_真实鞋型主图_2026-09-14"

COLORS = {
    "apricot_pair.jpg": SOURCE / "01_apricot.jpg",
    "blue_pair.jpg": SOURCE / "02_blue.jpg",
    "white_pair.jpg": SOURCE / "03_white.jpg",
    "grey_pair.jpg": SOURCE / "04_grey.jpg",
    "black_white_pair.jpg": SOURCE / "05_black_white.jpg",
    "all_black_pair.jpg": SOURCE / "06_all_black.jpg",
}


def corner_background(image: Image.Image) -> tuple[int, int, int]:
    rgb = image.convert("RGB")
    samples = [rgb.getpixel((x, y)) for x, y in ((5, 5), (994, 5), (5, 994), (994, 994))]
    return tuple(sum(pixel[channel] for pixel in samples) // len(samples) for channel in range(3))


def place_crop(source: Image.Image, box: tuple[int, int, int, int], name: str, max_width: int, max_height: int) -> None:
    crop = source.crop(box).convert("RGB")
    # PIL.thumbnail() never enlarges a crop.  These source sheets are 1000 px
    # collages, so deliberately scale the retained real-pixel crop to the
    # target occupancy while preserving its aspect ratio.
    scale = min(max_width / crop.width, max_height / crop.height)
    target = (max(1, round(crop.width * scale)), max(1, round(crop.height * scale)))
    crop = crop.resize(target, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (1000, 1000), corner_background(source))
    x = (1000 - crop.width) // 2
    y = (1000 - crop.height) // 2
    canvas.paste(crop, (x, y))
    canvas.save(OUTPUT / name, quality=95, subsampling=0, optimize=True)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for output_name, source_path in COLORS.items():
        image = Image.open(source_path).convert("RGB")
        # Keep only the large real product pair.  Starting below the label band
        # removes every bilingual colour label without altering the shoe.
        place_crop(image, (180, 205, 875, 575), output_name, 940, 640)

    blue = Image.open(SOURCE / "02_blue.jpg").convert("RGB")
    # Real-pixel upper crop from the large front shoe; no generative fill or geometry change.
    place_crop(blue, (305, 255, 825, 550), "upper_detail_blue.jpg", 930, 620)

    white = Image.open(SOURCE / "03_white.jpg").convert("RGB")
    # Real outsole crop from the original bottom-center view.
    place_crop(white, (370, 700, 695, 845), "outsole_white.jpg", 900, 440)

    print(f"created 8 exact-pixel assets in {OUTPUT}")


if __name__ == "__main__":
    main()
