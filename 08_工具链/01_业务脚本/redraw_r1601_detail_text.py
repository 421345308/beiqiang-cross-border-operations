from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(r"C:\Users\spq\Desktop\贝强\01_产品资产\02_可发布素材\00_最终上传\BQ010_R1601\02_详情页")
FONT_REGULAR = r"C:\Windows\Fonts\arial.ttf"
FONT_BOLD = r"C:\Windows\Fonts\arialbd.ttf"
GREEN = (39, 93, 76)
TEXT = (66, 68, 66)
BULLET = (39, 105, 81)
BACKGROUND = (248, 250, 247)


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def redraw(source: str, target: str, title: str, subtitle: str, bullets: list[str], footer: str) -> None:
    image = Image.open(ROOT / source).convert("RGB")
    draw = ImageDraw.Draw(image)

    draw.rectangle((45, 30, 1160, 330), fill=BACKGROUND)
    draw.rectangle((45, 1080, 1160, 1170), fill=BACKGROUND)
    draw.text((78, 66), title, font=font(FONT_BOLD, 52), fill=GREEN)
    draw.text((79, 126), subtitle, font=font(FONT_BOLD, 31), fill=TEXT)

    y = 198
    for line in bullets:
        draw.ellipse((78, y + 9, 91, y + 22), fill=BULLET)
        draw.text((112, y), line, font=font(FONT_REGULAR, 24), fill=TEXT)
        y += 46

    draw.text((72, 1117), footer, font=font(FONT_REGULAR, 20), fill=TEXT)
    image.save(ROOT / target, quality=95, subsampling=0)


redraw(
    "02_scene.jpg",
    "02_scene_v2.jpg",
    "LOW-TOP STRETCH FABRIC",
    "Flexible lace-up sneakers for daily casual wear",
    [
        "Stretch fabric upper with a distinctive toe-cap profile",
        "Low-top lace-up fit for everyday casual collections",
        "Two color options for wholesale assortment planning",
    ],
    "Beiqiang Footwear | Product use reference",
)

redraw(
    "03_detail.jpg",
    "03_detail_v2.jpg",
    "PRODUCT DETAILS",
    "Verified product features",
    [
        "Stretch fabric upper with lace-up closure",
        "Toe-cap profile for a distinctive casual look",
        "Mesh lining and EVA sole shown in platform attributes",
    ],
    "Beiqiang Footwear | R1601 product reference",
)
