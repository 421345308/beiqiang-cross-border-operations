"""Deterministic B/C information-role galleries from the sourced 2618 photos.

No shoe generation or recoloring. Output is local candidate art, not an Alibaba write.
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(r"C:\Users\spq\Desktop\贝强")
SRC = ROOT / "99_临时区/HR002_2618_货源候选_2026-09-24"
OUT = SRC / "本地候选_v1"
COMP = ROOT / "02_Alibaba运营/06_图片与检查记录/公司图复用模板_v4_2026-09-21"
SIZE = 1200
WHITE = "#ffffff"
INK = "#1e292b"
MUTED = "#526363"


def font(size: int, bold: bool = False):
    return ImageFont.truetype(str(Path(r"C:\Windows\Fonts") / ("arialbd.ttf" if bold else "arial.ttf")), size)


def draw_text(d: ImageDraw.ImageDraw, xy, value: str, size: int, fill=INK, bold=False):
    d.text(xy, value, font=font(size, bold), fill=fill)


def photo(path: Path, crop=None):
    with Image.open(path) as opened:
        image = opened.convert("RGB")
    return image.crop(crop) if crop else image


def put(canvas: Image.Image, source: Image.Image, bounds, *, fit=False):
    x0, y0, x1, y1 = bounds
    w, h = x1 - x0, y1 - y0
    image = ImageOps.fit(source, (w, h), Image.Resampling.LANCZOS) if fit else ImageOps.contain(source, (w, h), Image.Resampling.LANCZOS)
    canvas.paste(image, (x0 + (w - image.width) // 2, y0 + (h - image.height) // 2))


def card(d: ImageDraw.ImageDraw, bounds, fill=WHITE):
    d.rounded_rectangle(bounds, radius=20, fill=fill, outline="#d8e1e1", width=2)


def sheet(title: str, sub: str, *, bg: str, accent: str):
    canvas = Image.new("RGB", (SIZE, SIZE), bg)
    d = ImageDraw.Draw(canvas)
    draw_text(d, (55, 43), "HR002  |  MODEL 2618  |  B2B", 22, accent, True)
    draw_text(d, (55, 87), title, 43, INK, True)
    draw_text(d, (55, 148), sub, 21, MUTED)
    return canvas, d


sku = {name: photo(OUT / f"SKU_2618_{name}.jpg") for name in ("black", "khaki", "brown")}
wear = {
    "black": photo(SRC / "详情原图/16.jpg", (15, 485, 785, 1012)),
    "khaki": photo(SRC / "详情原图/13.jpg", (15, 653, 785, 1325)),
    "brown": photo(SRC / "详情原图/19.jpg", (15, 398, 785, 940)),
}
views = {
    "black_side": photo(SRC / "详情原图/26.jpg", (432, 333, 770, 610)),
    "black_sole": photo(SRC / "详情原图/26.jpg", (432, 145, 770, 315)),
    "brown_side": photo(SRC / "详情原图/25.jpg", (432, 950, 770, 1190)),
    "brown_sole": photo(SRC / "详情原图/25.jpg", (432, 765, 770, 930)),
}
factory = photo(COMP / "C3_real_production_organization.jpg", (55, 230, 755, 1050))
inspection = photo(COMP / "C4_real_quality_checkpoints.jpg", (430, 225, 790, 920))
variants = {
    "B": {"focus": "black", "label": "BLACK", "accent": "#203f49", "bg": "#f2f6f7", "side": views["black_side"], "sole": views["black_sole"]},
    "C": {"focus": "brown", "label": "DARK BROWN", "accent": "#5b4236", "bg": "#f8f5f1", "side": views["brown_side"], "sole": views["brown_sole"]},
}


def save(canvas: Image.Image, variant: str, role: str):
    name = f"{variant}_{role}_2618.jpg"
    if len(name) > 30:
        raise ValueError(name)
    canvas.save(OUT / name, quality=93, subsampling=0)
    return name


all_names = []
for variant, data in variants.items():
    focus = data["focus"]
    accent = data["accent"]
    bg = data["bg"]
    label = data["label"]

    # M2: genuine on-foot color comparison, not a second search hero.
    canvas, d = sheet("COMPARE REAL COLORWAYS", "Three source-listed colors; confirm order quantities by color", bg=bg, accent=accent)
    order = (focus,) + tuple(name for name in ("black", "khaki", "brown") if name != focus)
    for n, color in enumerate(order):
        x = 55 + 370 * n
        card(d, (x, 235, x + 350, 1030))
        put(canvas, wear[color], (x + 16, 260, x + 334, 865))
        draw_text(d, (x + 25, 930), {"black": "BLACK", "khaki": "KHAKI", "brown": "DARK BROWN"}[color], 25, accent, True)
    all_names.append(save(canvas, variant, "M2_colors"))

    # M3: source-backed construction seen from the actual variant.
    canvas, d = sheet("LOW-TOP LACE-UP STRUCTURE", "Material words follow the 2618 supplier specification", bg=bg, accent=accent)
    card(d, (55, 225, 765, 1005))
    put(canvas, data["side"], (80, 255, 735, 810))
    draw_text(d, (90, 875), f"{label}  |  SIDE PROFILE", 27, accent, True)
    card(d, (790, 225, 1145, 1005))
    put(canvas, data["sole"], (805, 270, 1130, 510))
    for n, item in enumerate(("LACE-UP", "MESH LINING", "RUBBER OUTSOLE", "RUBBER MIDSOLE")):
        draw_text(d, (815, 570 + n * 95), item, 23, accent, True)
    all_names.append(save(canvas, variant, "M3_structure"))

    # M4: Beiqiang proof is company-level, not a production claim for 2618.
    canvas, d = sheet("BEIQIANG COMPANY CONTEXT", "Company-level facilities and checks; sourcing reviewed per order", bg=bg, accent=accent)
    for x, source_image, caption in ((55, factory, "COMPANY IDENTITY"), (610, inspection, "QUALITY CHECK POINTS")):
        card(d, (x, 235, x + 535, 1000))
        put(canvas, source_image, (x + 16, 265, x + 519, 855), fit=True)
        draw_text(d, (x + 28, 925), caption, 23, accent, True)
    all_names.append(save(canvas, variant, "M4_company"))

    # M5: packaging discussion inputs, no assertion of default inclusion.
    canvas, d = sheet("PACKING REQUIREMENTS", "Ask for a packing quotation before confirming the order", bg=bg, accent=accent)
    for n, (head, body) in enumerate((("BAG OPTION", "Tell us the bag specification"), ("BOX OPTION", "Share box size and branding brief"))):
        y = 250 + n * 330
        card(d, (75, y, 1125, y + 260))
        draw_text(d, (115, y + 48), head, 35, accent, True)
        draw_text(d, (115, y + 116), body, 27, MUTED)
        draw_text(d, (115, y + 178), "Cost and feasibility are quoted per order.", 24, INK)
    draw_text(d, (85, 1010), "No packing format is included by default in the displayed shoe price.", 21, MUTED)
    all_names.append(save(canvas, variant, "M5_packing"))

    # M6: structured size-ratio input, not a duplicate color photo.
    canvas, d = sheet("EU SIZE RATIO FOR QUOTE", "Source-listed EU 39-48; send pairs needed in each size", bg=bg, accent=accent)
    card(d, (70, 250, 1130, 955))
    for n, size in enumerate(range(39, 49)):
        col, row = n % 5, n // 5
        x, y = 115 + col * 205, 335 + row * 265
        d.rounded_rectangle((x, y, x + 165, y + 175), radius=18, fill="#e1ebe9")
        draw_text(d, (x + 30, y + 38), f"EU {size}", 27, accent, True)
        draw_text(d, (x + 30, y + 110), "pairs: ___", 23, MUTED)
    draw_text(d, (86, 1005), "Actual color-size availability is reconfirmed for each order.", 24, INK)
    all_names.append(save(canvas, variant, "M6_sizes"))

    # Four product-specific detail modules, separate from company proof.
    canvas, d = sheet(f"{label} PRODUCT OVERVIEW", "Men's low-top lace-up casual shoes  |  Model 2618", bg=bg, accent=accent)
    card(d, (95, 235, 1105, 1030))
    put(canvas, wear[focus], (115, 260, 1085, 875))
    draw_text(d, (135, 925), "ACTUAL SOURCE PRODUCT PHOTO", 26, accent, True)
    all_names.append(save(canvas, variant, "D1_overview"))

    canvas, d = sheet("COLOR + SIZE CHOICES", "Black  |  Khaki  |  Dark Brown  |  EU 39-48", bg=bg, accent=accent)
    for n, color in enumerate(order):
        x = 60 + n * 370
        card(d, (x, 245, x + 345, 1045))
        put(canvas, sku[color], (x + 10, 275, x + 335, 875))
        draw_text(d, (x + 26, 935), {"black": "BLACK", "khaki": "KHAKI", "brown": "DARK BROWN"}[color], 23, accent, True)
    all_names.append(save(canvas, variant, "D2_options"))

    canvas, d = sheet("SOURCE-STATED COMPONENTS", "2618 source listing: mesh lining, rubber midsole and outsole", bg=bg, accent=accent)
    card(d, (55, 230, 1145, 1005))
    put(canvas, data["side"], (85, 265, 655, 835))
    for n, item in enumerate(("LOW TOP", "LACE-UP", "MESH LINING", "RUBBER MIDSOLE", "RUBBER OUTSOLE")):
        draw_text(d, (685, 315 + n * 120), item, 26, accent, True)
    all_names.append(save(canvas, variant, "D3_components"))

    canvas, d = sheet("WHAT TO INCLUDE IN AN INQUIRY", "A clear brief lets us check current sourcing terms", bg=bg, accent=accent)
    for n, text in enumerate(("Color and EU size ratio", "Total quantity", "Packing preference", "Destination and timing request")):
        y = 250 + 190 * n
        card(d, (80, y, 1120, y + 150))
        draw_text(d, (120, y + 48), f"{n+1}.  {text}", 29, accent, True)
    draw_text(d, (90, 1050), "Price, availability and delivery are checked before order acceptance.", 22, MUTED)
    all_names.append(save(canvas, variant, "D4_inquiry"))

sheet_image = Image.new("RGB", (1600, 1650), "#e8eeee")
sd = ImageDraw.Draw(sheet_image)
for n, name in enumerate(all_names):
    with Image.open(OUT / name) as opened:
        small = opened.resize((300, 300), Image.Resampling.LANCZOS)
    x, y = (n % 5) * 320 + 10, (n // 5) * 410 + 10
    sheet_image.paste(small, (x, y))
    draw_text(sd, (x, y + 310), name.removesuffix(".jpg"), 17, INK, True)
sheet_image.save(OUT / "contact_BC_2618.jpg", quality=90)
print(OUT)
