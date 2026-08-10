from pathlib import Path
import shutil
from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[2]
FACTORY_DIR = ROOT / "03_厂家资料" / "厂家照片"
PRODUCT_DIR = ROOT / "02_可上传素材"
OUT = ROOT / "02_可上传素材" / "公司图集"


def font(size: int, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


FONT_TITLE = font(54, True)
FONT_SUBTITLE = font(25)
FONT_LABEL = font(22, True)
FONT_BODY = font(22)
FONT_SMALL = font(18)


def load_cover(path: Path, size: tuple[int, int]) -> Image.Image:
    im = Image.open(path).convert("RGB")
    return ImageOps.fit(im, size, Image.LANCZOS, centering=(0.5, 0.5))


def rounded_paste(base: Image.Image, im: Image.Image, box: tuple[int, int], radius: int = 20):
    mask = Image.new("L", im.size, 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0, 0, im.size[0] - 1, im.size[1] - 1), radius=radius, fill=255)
    base.paste(im, box, mask)


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont, max_width: int):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = word if not current else f"{current} {word}"
        if draw.textbbox((0, 0), test, font=fnt)[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def make_card(title: str, subtitle: str, bullets: list[str], images: list[Path], out: Path):
    W, H = 1200, 900
    canvas = Image.new("RGB", (W, H), (246, 248, 246))
    draw = ImageDraw.Draw(canvas)

    draw.rectangle((0, 0, W, 18), fill=(64, 103, 83))
    draw.text((70, 60), title, fill=(54, 87, 70), font=FONT_TITLE)
    draw.text((72, 132), subtitle, fill=(85, 98, 92), font=FONT_SUBTITLE)

    left, top = 70, 200
    if len(images) == 1:
        rounded_paste(canvas, load_cover(images[0], (660, 560)), (470, 230), 24)
    else:
        positions = [(470, 220), (805, 220), (470, 520), (805, 520)]
        for p, pos in zip(images[:4], positions):
            rounded_paste(canvas, load_cover(p, (305, 250)), pos, 18)

    y = top
    for bullet in bullets:
        draw.rounded_rectangle((left, y + 2, left + 14, y + 16), radius=7, fill=(64, 103, 83))
        lines = wrap(draw, bullet, FONT_BODY, 330)
        for line in lines:
            draw.text((left + 30, y - 4), line, fill=(42, 50, 48), font=FONT_BODY)
            y += 30
        y += 22

    draw.text((72, H - 64), "Beiqiang Footwear | Casual Walking Shoes Supplier", fill=(110, 119, 115), font=FONT_SMALL)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, quality=94)


def copy_originals(group_name: str, files: list[Path]):
    dest = OUT / group_name / "原图候选"
    dest.mkdir(parents=True, exist_ok=True)
    for index, src in enumerate(files, 1):
        shutil.copy2(src, dest / f"{index:02d}_{src.name}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    photos = {p.name: p for p in FACTORY_DIR.iterdir() if p.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]}

    groups = {
        "01_公司介绍_Company overview": {
            "title": "COMPANY OVERVIEW",
            "subtitle": "Footwear supplier focused on casual walking shoes",
            "bullets": [
                "Real factory and warehouse photos for buyer trust",
                "Focused product line: wide toe box slip-on walking shoes",
                "Flexible supply support for early-stage wholesale orders",
            ],
            "images": [
                "312131B92967C3A2090BFAFDB951C0A4.png",
                "9123A5EB607A681AC92FFFABE40B3005.png",
                "A9C9E3B935A11A476BE00DE0FD0C3BBC.png",
                "E7AE0BC4F8A9D61778E2322DDE44D6F6.png",
            ],
        },
        "02_公司优势_Competitive advantages": {
            "title": "COMPETITIVE ADVANTAGES",
            "subtitle": "Practical footwear supply for daily walking styles",
            "bullets": [
                "Wide toe box designs for casual walking demand",
                "Multiple color options available for product selection",
                "English product visuals prepared for international buyers",
            ],
            "images": [
                "312131B92967C3A2090BFAFDB951C0A4.png",
                "FF0EB3E94E43735A20D8584C73B4242F.png",
                "D6C7FD5A226C319802D341A1CF7B4E06.png",
                "A228768BC3566451DFC612A7F03B619D.png",
            ],
        },
        "03_工厂情况_Factory profile": {
            "title": "FACTORY PROFILE",
            "subtitle": "Workshop, warehouse and on-site production areas",
            "bullets": [
                "Workshop areas for shoe assembly and handling",
                "Warehouse racks for product and material storage",
                "On-site photos help buyers understand real capacity",
            ],
            "images": [
                "84FF9D0383A2DC0DB22BB759FA5F4EA8.png",
                "6547C269B1439AC9E425D210A83A5BC7.png",
                "E7AE0BC4F8A9D61778E2322DDE44D6F6.png",
                "3CD1A61634DA5270C85F4B3E4CCAD9F7.png",
            ],
        },
        "04_定制能力_Customization capability": {
            "title": "CUSTOMIZATION SUPPORT",
            "subtitle": "Style, color and product detail communication",
            "bullets": [
                "Casual walking shoe styles can be discussed by order needs",
                "Color and material details should be confirmed before bulk order",
                "Use inquiry messages to confirm logo, packaging and MOQ",
            ],
            "images": [
                "FF0EB3E94E43735A20D8584C73B4242F.png",
                "312131B92967C3A2090BFAFDB951C0A4.png",
                "A63A0FD1CBA98FD532B425D5C499173E.png",
                "E33B3E32BABD18D4A9770DCED97ED38F.png",
            ],
        },
        "05_生产流程_Production workflow": {
            "title": "PRODUCTION WORKFLOW",
            "subtitle": "From materials and assembly to packing preparation",
            "bullets": [
                "Material and semi-finished product handling",
                "Workshop assembly and product checking process",
                "Packing preparation before shipment",
            ],
            "images": [
                "6547C269B1439AC9E425D210A83A5BC7.png",
                "F9AE6735D3DB57639F7457C3BAC4C3F1.png",
                "FC87A87FE0658260F34EFA145338CBD1.png",
                "C278DF7185486C15215089FAC3776592.png",
            ],
        },
        "07_包装运输_Packaging shipping": {
            "title": "PACKAGING & SHIPPING",
            "subtitle": "Warehouse storage and carton handling support",
            "bullets": [
                "Carton storage area for ready-to-ship preparation",
                "Warehouse shelves help organize product batches",
                "Confirm final carton size and gross weight before shipping",
            ],
            "images": [
                "3D7E6320356123E5172283244B177B69.png",
                "429528D5FACB6A995B4B6CD84C5A5EDA.png",
                "9123A5EB607A681AC92FFFABE40B3005.png",
                "D226973837DEA739118B2588DF676E1D.png",
            ],
        },
    }

    for folder, data in groups.items():
        imgs = [photos[name] for name in data["images"] if name in photos]
        make_card(data["title"], data["subtitle"], data["bullets"], imgs, OUT / folder / "01_upload_cover_en.jpg")
        copy_originals(folder, imgs)

    # Product-range support image from already prepared English product visuals.
    product_sources = [
        PRODUCT_DIR / "数据包1" / "英文主图" / "01_WIDE_TOE_BOX_MAIN_EN.jpg",
        PRODUCT_DIR / "数据包1" / "英文主图" / "04_267G_LIGHTWEIGHT_MAIN_EN.jpg",
        PRODUCT_DIR / "数据包2" / "英文主图" / "01_WIDE_TOE_BOX_MAIN_EN.jpg",
        PRODUCT_DIR / "数据包2" / "英文主图" / "04_253G_LIGHTWEIGHT_MAIN_EN.jpg",
    ]
    make_card(
        "PRODUCT RANGE",
        "Wide toe box casual walking shoes for daily wear",
        [
            "Slip-on walking shoe styles for men and women",
            "Lightweight EVA sole options for daily use",
            "Product details prepared in English for global buyers",
        ],
        [p for p in product_sources if p.exists()],
        OUT / "08_其他公司介绍_Extended company profile" / "01_product_range_en.jpg",
    )
    copy_originals("08_其他公司介绍_Extended company profile", [p for p in product_sources if p.exists()])

    readme = OUT / "README_公司图集上传建议.txt"
    readme.write_text(
        "\n".join(
            [
                "Alibaba company gallery upload suggestion",
                "",
                "Recommended upload order:",
                "1. 公司介绍 / Company overview: upload 01_upload_cover_en.jpg",
                "2. 公司优势 / Competitive advantages: upload 01_upload_cover_en.jpg",
                "3. 工厂情况 / Factory profile: upload 01_upload_cover_en.jpg and 1-2 real original candidates if needed",
                "4. 定制能力 / Customization capability: upload 01_upload_cover_en.jpg only after confirming customization/MOQ terms",
                "5. 生产流程 / Production workflow: upload 01_upload_cover_en.jpg",
                "6. 参展情况 / Trade show participation: no real trade show material found, do not upload generated fake trade show photos",
                "7. 包装运输 / Packaging & shipping: upload 01_upload_cover_en.jpg",
                "8. 其他公司介绍 / Extended company profile: upload 01_product_range_en.jpg",
                "",
                "Notes:",
                "- These images use real photos from the folder where possible.",
                "- Generated text is conservative and avoids fake certificates, fake trade show claims, and exact capacity claims.",
                "- Before publishing, confirm company name, MOQ, customization scope, carton size, and shipping terms.",
            ]
        ),
        encoding="utf-8",
    )

    print(OUT)


if __name__ == "__main__":
    main()
