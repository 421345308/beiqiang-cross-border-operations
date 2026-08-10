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
    row_h = 72
    for i, item in enumerate(items):
        cx = x + (i % 2) * col_w
        cy = y + (i // 2) * row_h
        draw.rounded_rectangle((cx, cy, cx + col_w - 22, cy + 52), radius=12, fill=CARD, outline=LINE)
        draw.ellipse((cx + 18, cy + 19, cx + 31, cy + 32), fill=GREEN)
        paragraph(draw, item, cx + 48, cy + 13, col_w - 84, F_SMALL, DARK, 2)


def img_grid(canvas, img_paths, x, y, w, h):
    cell_w = (w - 26) // 2
    cell_h = (h - 26) // 2
    positions = [(x, y), (x + cell_w + 26, y), (x, y + cell_h + 26), (x + cell_w + 26, y + cell_h + 26)]
    for path, pos in zip(img_paths[:4], positions):
        round_paste(canvas, cover(path, (cell_w, cell_h)), pos, 20)


def module(title, subtitle, intro, item_list, folder, out_name):
    W, H = 1200, 1220
    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)
    header(draw, title, subtitle)
    y = paragraph(draw, intro, 72, 170, 1040, F_BODY, DARK, 5)
    points(draw, item_list, 70, y + 14, 1060)
    imgs = sorted((SELECTED / folder).iterdir())
    img_grid(canvas, imgs, 70, 390, 1060, 690)
    draw.text((72, H - 52), "Beiqiang Footwear | Walking Shoes Supplier", font=F_SMALL, fill=MUTED)
    OUT.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT / out_name, quality=94)


def process_module():
    W, H = 1200, 1220
    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)
    header(draw, "ORDER & PACKING PROCESS", "From production checking to stock preparation")
    intro = "We focus on practical order handling steps that can be supported by real workshop and stock preparation photos."
    y = paragraph(draw, intro, 72, 170, 1040, F_BODY, DARK, 5)
    steps = [
        ("01", "Check", "Manual product checking"),
        ("02", "Sort", "Batch sorting by style"),
        ("03", "Stock", "Ready stock preparation"),
        ("04", "Pack", "Carton and packing area"),
    ]
    sx, sy = 70, y + 26
    box_w, box_h = 250, 112
    for i, (num, name, desc) in enumerate(steps):
        x = sx + i * 270
        draw.rounded_rectangle((x, sy, x + box_w, sy + box_h), radius=16, fill=(255, 255, 255), outline=LINE, width=2)
        draw.ellipse((x + 20, sy + 24, x + 66, sy + 70), fill=GREEN)
        draw.text((x + 34, sy + 36), num, font=F_SMALL, fill=(255, 255, 255))
        draw.text((x + 82, sy + 24), name, font=F_SUB, fill=GREEN)
        paragraph(draw, desc, x + 82, sy + 60, 145, F_SMALL, DARK, 2)
    imgs = sorted((SELECTED / "04_订单包装流程").iterdir())
    img_grid(canvas, imgs, 70, 430, 1060, 650)
    draw.text((72, H - 52), "Sample, MOQ, packing and lead time should be confirmed before bulk order", font=F_SMALL, fill=MUTED)
    canvas.save(OUT / "05_process.jpg", quality=94)


def readme():
    (OUT / "README.txt").write_text(
        "\n".join(
            [
                "Recommended Alibaba upload set.",
                "Use these images instead of old company-detail-v2/v3/vertical drafts.",
                "No logo customization, certificate, trade show or customer review claims are included because no matching source photos are available.",
            ]
        ),
        encoding="utf-8",
    )


def preview():
    files = sorted([p for p in OUT.glob("*.jpg") if p.name != "preview.jpg"])
    tw, th = 360, 366
    cols = 2
    rows = (len(files) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + 42)), (242, 244, 246))
    d = ImageDraw.Draw(sheet)
    for i, p in enumerate(files):
        im = Image.open(p).convert("RGB")
        im.thumbnail((tw, th), Image.LANCZOS)
        x = (i % cols) * tw
        y = (i // cols) * (th + 42)
        sheet.paste(im, (x + (tw - im.width) // 2, y))
        d.text((x + 8, y + th + 8), f"{p.name} ({len(p.name)})", font=F_SMALL, fill=DARK)
    sheet.save(OUT / "preview.jpg", quality=92)


def main():
    module(
        "BEIQIANG FOOTWEAR",
        "Practical walking shoes supplier",
        "We focus on casual walking shoes with knitted upper, EVA sole, wide toe box design and easy slip-on comfort for daily wear.",
        ["Factory and warehouse photos", "Walking shoe product focus", "Small trial orders can be discussed", "Mixed colors and sizes"],
        "03_工厂仓库",
        "01_company.jpg",
    )
    module(
        "COMPETITIVE ADVANTAGES",
        "Stock, sorting and flexible order support",
        "Real stock and product sorting photos help buyers understand our supply capability for available walking shoe styles.",
        ["Ready stock preparation", "Mixed color options", "Batch product sorting", "Warehouse and carton storage"],
        "01_公司优势库存",
        "02_advantage.jpg",
    )
    module(
        "FACTORY & WAREHOUSE",
        "Workshop, warehouse and product handling areas",
        "On-site photos show the real working environment, warehouse shelves and carton storage for walking shoe orders.",
        ["Workshop production area", "Warehouse storage", "Product handling area", "Carton storage area"],
        "03_工厂仓库",
        "03_factory.jpg",
    )
    module(
        "PRODUCT CHECKING",
        "Manual checking before packing",
        "Manual checking and batch sorting help confirm upper, sole, color and product condition before packing preparation.",
        ["Upper detail check", "Sole detail check", "Batch product sorting", "Production line arrangement"],
        "02_产品检查生产",
        "04_check.jpg",
    )
    process_module()
    module(
        "PACKING PREPARATION",
        "Warehouse stock and carton preparation",
        "Stock shelves and carton areas support order packing preparation. Final package details should be confirmed before shipment.",
        ["Stock and carton area", "Product sorting before packing", "Mixed size and color support", "Packing details confirmed by order"],
        "04_订单包装流程",
        "06_pack.jpg",
    )
    readme()
    preview()
    print(OUT)


if __name__ == "__main__":
    main()
