from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
TASK = ROOT / r"02_Alibaba运营\02_单品优化记录\BQ系列持续优化_2026-09-14"
RAW = ROOT / (
    r"01_产品资产\01_原始数据包"
    r"\已整理_BQ011_A002_A002贝强工厂店一脚蹬男鞋39-45批58元"
    r"\A002贝强工厂店一脚蹬男鞋39-45批58元\800"
)
OUT = TASK / "BQ011_真实鞋型六图候选_2026-09-15"


# Only original factory-package photos are used. No generative fill, recolor,
# shape editing, sole editing, text overlay, or unsupported product claim.
GALLERIES = {
    "1601939634522_BQ011-W1_grey_white": [
        ("x366A2152.jpg", "01_grey_white_hero.jpg"),
        ("X366A2337.jpg", "02_grey_white_handheld.jpg"),
        ("X366A2338.jpg", "03_grey_white_pair.jpg"),
        ("X366A2339.jpg", "04_grey_white_side_pair.jpg"),
        ("X366A3020.jpg", "05_grey_white_wearing.jpg"),
        ("X366A3025.jpg", "06_grey_white_closeup.jpg"),
    ],
    "1601939666421_BQ011-R1_grey_green": [
        ("x366A2153.jpg", "01_grey_green_hero.jpg"),
        ("X366A2332.jpg", "02_grey_green_pair.jpg"),
        ("X366A2334.jpg", "03_grey_green_handheld.jpg"),
        ("X366A2335.jpg", "04_grey_green_top_sole.jpg"),
        ("X366A3016.jpg", "05_grey_green_wearing.jpg"),
        ("X366A3019.jpg", "06_grey_green_slip_on.jpg"),
    ],
    "1601939606803_BQ011-O1_all_black": [
        ("x366A2151.jpg", "01_all_black_hero.jpg"),
        ("X366A2330.jpg", "02_all_black_handheld.jpg"),
        ("X366A3009.jpg", "03_all_black_front_wearing.jpg"),
        ("X366A3010.jpg", "04_all_black_slip_on.jpg"),
        ("X366A3011.jpg", "05_all_black_side_wearing.jpg"),
        ("X366A3013.jpg", "06_all_black_closeup.jpg"),
    ],
}


def normalize(source: Path, target: Path) -> None:
    with Image.open(source) as opened:
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
        for filename, target_name in items:
            source = RAW / filename
            if not source.is_file():
                raise FileNotFoundError(source)
            normalize(source, gallery_dir / target_name)
        make_contact_sheet(gallery_dir)
    print(f"built={len(GALLERIES)} galleries")
    print(f"images={sum(len(items) for items in GALLERIES.values())}")
    print(f"output={OUT}")


if __name__ == "__main__":
    main()
