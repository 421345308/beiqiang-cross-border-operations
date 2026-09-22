from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
TASK = ROOT / r"02_Alibaba运营\02_单品优化记录\BQ系列持续优化_2026-09-14"
HERO = TASK / "BQ016_真实鞋型主图_2026-09-14"
RAW = Path(
    r"E:\贝强大文件\01_产品资产\01_原始数据包"
    r"\已整理_BQ016_201_201贝强工厂店秋季一脚蹬女鞋童鞋31-40批50元"
    r"\201贝强工厂店秋季一脚蹬女鞋童鞋31-40批50元\主图"
)
OUT = TASK / "BQ016_纯实拍六图候选_2026-09-14"


GALLERIES = {
    "1601939608691_BQ016-W1_black": [
        (HERO / "black_clean.jpg", "01_black_hero.jpg"),
        (RAW / "17.jpg", "02_black_outsole.jpg"),
        (RAW / "19.jpg", "03_black_angle.jpg"),
        (RAW / "18.jpg", "04_black_top.jpg"),
        (RAW / "12.jpg", "05_three_colors.jpg"),
        (RAW / "00001.jpg", "06_black_handheld.jpg"),
    ],
    "1601939691301_BQ016-R1_pink": [
        (HERO / "pink_clean.jpg", "01_pink_hero.jpg"),
        (RAW / "16.jpg", "02_pink_top.jpg"),
        (RAW / "14.jpg", "03_pink_angle.jpg"),
        (RAW / "15.jpg", "04_pink_outsole.jpg"),
        (RAW / "12.jpg", "05_three_colors.jpg"),
        (RAW / "0001.jpg", "06_pink_handheld.jpg"),
    ],
    "1601939633580_BQ016-O1_zebra": [
        (HERO / "zebra_clean.jpg", "01_zebra_hero.jpg"),
        (RAW / "24.jpg", "02_zebra_angle.jpg"),
        (RAW / "23.jpg", "03_zebra_top.jpg"),
        (RAW / "21.jpg", "04_zebra_heel.jpg"),
        (RAW / "12.jpg", "05_three_colors.jpg"),
        (RAW / "001.jpg", "06_zebra_handheld.jpg"),
    ],
}


def normalize(source: Path, target: Path) -> None:
    with Image.open(source) as opened:
        image = opened.convert("RGB")
    image = ImageEnhance.Contrast(image).enhance(1.01)
    image = ImageEnhance.Sharpness(image).enhance(1.02)
    if image.size != (1000, 1000):
        image = image.resize((1000, 1000), Image.Resampling.LANCZOS)
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, "JPEG", quality=96, optimize=True, subsampling=1)


def make_contact_sheet(gallery_dir: Path) -> None:
    files = sorted(path for path in gallery_dir.glob("*.jpg") if not path.name.endswith("_contact.jpg"))
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
    canvas.save(OUT / f"{gallery_dir.name}_contact_v2.jpg", "JPEG", quality=94)


def main() -> None:
    for gallery, items in GALLERIES.items():
        for source, filename in items:
            if not source.exists():
                raise FileNotFoundError(source)
            normalize(source, OUT / gallery / filename)
        make_contact_sheet(OUT / gallery)
    print(f"built={len(GALLERIES)} galleries")
    print(f"images={sum(len(items) for items in GALLERIES.values())}")
    print(f"output={OUT}")


if __name__ == "__main__":
    main()
