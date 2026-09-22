from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
TASK = ROOT / r"02_Alibaba运营\02_单品优化记录\BQ系列持续优化_2026-09-14"
RAW = Path(r"E:\贝强大文件\01_产品资产\01_原始数据包\已整理_BQ002_5.13贝强2数据包")
TRANSPARENT = RAW / "透明图"
PHOTOS = RAW / "800X800主图"
OUT = TASK / "BQ002_真实鞋型六图候选_2026-09-15"


GALLERIES = {
    "1601939654418_BQ002-W1_grey_black": [
        (TRANSPARENT / "5M4A1150.png", "01_grey_black_hero.jpg"),
        (PHOTOS / "5M4A1149.JPG", "02_grey_black_side.jpg"),
        (PHOTOS / "5M4A1151.JPG", "03_grey_black_outsole.jpg"),
        (PHOTOS / "5M4A1162.JPG", "04_top_view.jpg"),
        (PHOTOS / "5M4A1159.JPG", "05_grey_black_pair.jpg"),
        (PHOTOS / "01 (13).jpg", "06_three_colors.jpg"),
    ],
    "1601939614689_BQ002-R1_grey_khaki": [
        (TRANSPARENT / "5M4A1153.png", "01_grey_khaki_hero.jpg"),
        (PHOTOS / "5M4A1152.JPG", "02_grey_khaki_side.jpg"),
        (PHOTOS / "5M4A1154.JPG", "03_grey_khaki_outsole.jpg"),
        (PHOTOS / "5M4A1156.JPG", "04_grey_khaki_top.jpg"),
        (PHOTOS / "5M4A1157.JPG", "05_grey_khaki_pair.jpg"),
        (PHOTOS / "01 (15).jpg", "06_grey_khaki_views.jpg"),
    ],
    "1601939635505_BQ002-O1_grey_white": [
        (TRANSPARENT / "5M4A1145.png", "01_grey_white_hero.jpg"),
        (PHOTOS / "5M4A1144.JPG", "02_grey_white_side.jpg"),
        (PHOTOS / "5M4A1146.JPG", "03_grey_white_outsole.jpg"),
        (PHOTOS / "5M4A1148.JPG", "04_grey_white_top.jpg"),
        (PHOTOS / "5M4A1158.JPG", "05_grey_white_pair.jpg"),
        (PHOTOS / "01 (14).jpg", "06_grey_white_views.jpg"),
    ],
}


def normalize(source: Path, target: Path) -> None:
    with Image.open(source) as opened:
        if opened.mode in {"RGBA", "LA"} or "transparency" in opened.info:
            rgba = opened.convert("RGBA")
            image = Image.new("RGB", rgba.size, "white")
            image.paste(rgba, mask=rgba.getchannel("A"))
        else:
            image = opened.convert("RGB")
    if image.size != (1000, 1000):
        image = image.resize((1000, 1000), Image.Resampling.LANCZOS)
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, "JPEG", quality=96, optimize=True, subsampling=1)


def make_contact_sheet(gallery_dir: Path) -> None:
    files = sorted(gallery_dir.glob("*.jpg"))
    canvas = Image.new("RGB", (1000, 720), "white")
    draw = ImageDraw.Draw(canvas)
    for index, path in enumerate(files):
        with Image.open(path) as opened:
            image = opened.convert("RGB")
        image.thumbnail((310, 300), Image.Resampling.LANCZOS)
        col, row = index % 3, index // 3
        x, y = col * 333 + 11, row * 355 + 10
        canvas.paste(image, (x + (310 - image.width) // 2, y))
        draw.text((x, y + 305), path.name, fill="black")
    canvas.save(OUT / f"{gallery_dir.name}_contact.jpg", "JPEG", quality=94)


def main() -> None:
    for gallery, items in GALLERIES.items():
        gallery_dir = OUT / gallery
        for source, filename in items:
            if not source.is_file():
                raise FileNotFoundError(source)
            normalize(source, gallery_dir / filename)
        make_contact_sheet(gallery_dir)
    print(f"built={len(GALLERIES)} galleries")
    print(f"images={sum(len(items) for items in GALLERIES.values())}")
    print(f"output={OUT}")


if __name__ == "__main__":
    main()
