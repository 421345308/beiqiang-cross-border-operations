from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[2]
ASSETS = next(p for p in ROOT.iterdir() if p.name.startswith("02_"))
SUPPLIER = next(p for p in ROOT.iterdir() if p.name.startswith("03_"))
SELECTED = SUPPLIER / "精选素材"
OUT = ASSETS / "公司详情-推荐上传"


def font(size, bold=False):
    for file in [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
    ]:
        try:
            return ImageFont.truetype(file, size)
        except OSError:
            pass
    return ImageFont.load_default()


F_TITLE = font(52, True)
F_SUB = font(27, True)
F_BODY = font(24)
F_SMALL = font(18)

GREEN = (54, 88, 72)
DARK = (35, 45, 41)
MUTED = (82, 96, 90)
BG = (248, 250, 248)
CARD = (238, 244, 240)
LINE = (214, 225, 219)


def wrap(draw, text, fnt, width):
    words = text.split()
    lines, cur = [], ""
    for word in words:
        test = word if not cur else cur + " " + word
        if draw.textbbox((0, 0), test, font=fnt)[2] <= width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def paragraph(draw, text, x, y, width, fnt=F_BODY, fill=DARK, gap=5):
    for line in wrap(draw, text, fnt, width):
        draw.text((x, y), line, font=fnt, fill=fill)
        y += fnt.size + gap
    return y


def cover(path, size):
    im = Image.open(path).convert("RGB")
    return ImageOps.fit(im, size, Image.LANCZOS, centering=(0.5, 0.5))


def round_paste(base, im, xy, radius=20):
    mask = Image.new("L", im.size, 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=radius, fill=255)
    base.paste(im, xy, mask)


def header(draw, title, subtitle):
    draw.rectangle((0, 0, 1200, 18), fill=GREEN)
    draw.text((70, 48), title, font=F_TITLE, fill=GREEN)
    draw.text((72, 112), subtitle, font=F_SUB, fill=MUTED)


def points(draw, items, x, y, width):
    col_w = width // 2
    row_h = 70
    for i, item in enumerate(items):
        cx = x + (i % 2) * col_w
        cy = y + (i // 2) * row_h
        draw.rounded_rectangle((cx, cy, cx + col_w - 22, cy + 50), radius=12, fill=CARD, outline=LINE)
        draw.ellipse((cx + 18, cy + 18, cx + 31, cy + 31), fill=GREEN)
        paragraph(draw, item, cx + 48, cy + 12, col_w - 84, F_SMALL, DARK, 2)


def image_grid(canvas, img_paths, x, y, w, h):
    cell_w = (w - 26) // 2
    cell_h = (h - 26) // 2
    positions = [(x, y), (x + cell_w + 26, y), (x, y + cell_h + 26), (x + cell_w + 26, y + cell_h + 26)]
    for path, pos in zip(img_paths[:4], positions):
        round_paste(canvas, cover(path, (cell_w, cell_h)), pos, 20)


def make_page(title, subtitle, intro, item_list, img_paths, out_name, footer="Beiqiang Footwear | Walking Shoes Supplier"):
    W, H = 1200, 1180
    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)
    header(draw, title, subtitle)
    y = paragraph(draw, intro, 72, 170, 1040, F_BODY, DARK, 5)
    points(draw, item_list, 70, y + 14, 1060)
    image_grid(canvas, img_paths, 70, 370, 1060, 650)
    draw.text((72, H - 52), footer, font=F_SMALL, fill=MUTED)
    OUT.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT / out_name, quality=94)


def files(folder, names):
    base = SELECTED / folder
    return [base / name for name in names]


def make_preview():
    imgs = sorted([p for p in OUT.glob("*.jpg") if p.name != "preview.jpg"])
    tw, th = 360, 354
    sheet = Image.new("RGB", (tw, len(imgs) * (th + 42)), (242, 244, 246))
    d = ImageDraw.Draw(sheet)
    for i, p in enumerate(imgs):
        im = Image.open(p).convert("RGB")
        im.thumbnail((tw, th), Image.LANCZOS)
        y = i * (th + 42)
        sheet.paste(im, ((tw - im.width) // 2, y))
        d.text((8, y + th + 8), f"{p.name} ({len(p.name)})", font=F_SMALL, fill=DARK)
    sheet.save(OUT / "preview.jpg", quality=92)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.jpg"):
        old.unlink()

    make_page(
        "COMPANY & FACTORY",
        "Practical walking shoes supplier",
        "We focus on casual walking shoes with knitted upper, EVA sole, wide toe box design and easy slip-on comfort for daily wear.",
        ["Real workshop photos", "Warehouse and carton storage", "Walking shoe product focus", "Mixed colors and sizes"],
        files(
            "03_工厂仓库",
            ["01_workshop.png", "02_carton_storage.png", "03_workshop_line.png", "04_workshop_area.png"],
        ),
        "01_company.jpg",
    )

    make_page(
        "PRODUCTION & CHECKING",
        "Manual checking before packing",
        "Manual checking and batch sorting help confirm upper, sole, color and product condition before packing preparation.",
        ["Upper detail check", "Sole detail check", "Batch product sorting", "Production line arrangement"],
        files(
            "02_产品检查生产",
            ["01_upper_check.jpg", "02_sole_check.jpg", "03_line_sorting.jpg", "04_batch_check.jpg"],
        ),
        "02_check.jpg",
    )

    make_page(
        "STOCK & PACKING",
        "Stock sorting and packing preparation",
        "Stock shelves and carton areas support available-style orders. Final sample, MOQ, packing and lead time should be confirmed before bulk order.",
        ["Ready stock preparation", "Mixed color options", "Carton and packing area", "Packing details confirmed by order"],
        files(
            "01_公司优势库存",
            ["01_stock_sorting.jpg", "02_color_options.jpg", "03_stock_boxes.jpg", "04_warehouse_boxes.png"],
        ),
        "03_pack.jpg",
        "Sample, MOQ, packing and lead time should be confirmed before bulk order",
    )

    (OUT / "README.txt").write_text(
        "Final compact set for Alibaba detail page upload. Use 01_company.jpg, 02_check.jpg, 03_pack.jpg.\n",
        encoding="utf-8",
    )
    make_preview()
    print(OUT)


if __name__ == "__main__":
    main()
