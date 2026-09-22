from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
TASK = ROOT / r"02_Alibaba运营\02_单品优化记录\BQ系列持续优化_2026-09-14"
RAW = Path(
    r"E:\贝强大文件\01_产品资产\01_原始数据包"
    r"\已整理_BQ017_A008_2024贝强鞋业A008套袜一脚蹬男女鞋35-45批55元"
    r"\贝强鞋业A008套袜一脚蹬男女鞋35-45批55元"
)
TRANSPARENT = RAW / "透明图"
SCENES = RAW / "800X800主图"
OUT = TASK / "BQ017_真实鞋型六图候选_2026-09-14"


GALLERIES = {
    "1601939636508_BQ017-W1_grey": [
        (TRANSPARENT / "PD2A6605.png", "01_grey_hero.jpg"),
        (TRANSPARENT / "PD2A6608.png", "02_black_white.jpg"),
        (TRANSPARENT / "PD2A6607.png", "03_all_black.jpg"),
        (TRANSPARENT / "PD2A6606.png", "04_white.jpg"),
        (SCENES / "主图 (2).JPG", "05_grey_scene.jpg"),
        (SCENES / "主图 (6).jpg", "06_grey_pair.jpg"),
    ],
    "1601939697271_BQ017-R1_white": [
        (TRANSPARENT / "PD2A6606.png", "01_white_hero.jpg"),
        (TRANSPARENT / "PD2A6605.png", "02_grey.jpg"),
        (TRANSPARENT / "PD2A6608.png", "03_black_white.jpg"),
        (TRANSPARENT / "PD2A6607.png", "04_all_black.jpg"),
        (SCENES / "主图 (1).JPG", "05_white_scene.jpg"),
        (SCENES / "主图 (5).JPG", "06_white_pair.jpg"),
    ],
    "1601939593839_BQ017-O1_all_black": [
        (TRANSPARENT / "PD2A6607.png", "01_all_black_hero.jpg"),
        (TRANSPARENT / "PD2A6608.png", "02_black_white.jpg"),
        (TRANSPARENT / "PD2A6605.png", "03_grey.jpg"),
        (TRANSPARENT / "PD2A6606.png", "04_white.jpg"),
        (SCENES / "主图 (3).JPG", "05_all_black_scene.jpg"),
        (SCENES / "主图 (7).JPG", "06_all_black_pair.jpg"),
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
