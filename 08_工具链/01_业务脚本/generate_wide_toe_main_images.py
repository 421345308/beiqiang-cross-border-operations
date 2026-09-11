from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "01_产品资产" / "02_可发布素材" / "主图优化_前5张_20260530"

NAVY = (17, 24, 39)
SLATE = (75, 85, 99)
MUTED = (107, 114, 128)
GREEN = (15, 126, 104)
GREEN_DARK = (35, 84, 69)
LIGHT_BG = (246, 248, 250)
PANEL = (255, 255, 255)
LINE = (214, 220, 226)
ORANGE = (210, 117, 38)
RED = (215, 65, 74)
KHAKI = (154, 137, 103)
BLACK = (28, 28, 28)
WHITE = (255, 255, 255)


def font(size, bold=False):
    candidates = [
        Path(r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf"),
    ]
    for p in candidates:
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


F = {
    "hero": font(58, True),
    "title": font(44, True),
    "mid": font(30, True),
    "body": font(24, False),
    "small": font(19, False),
    "tiny": font(16, False),
}


def canvas(bg=WHITE):
    return Image.new("RGB", (1000, 1000), bg)


def draw_text(draw, xy, text, fill=NAVY, f=None, anchor=None):
    draw.text(xy, text, fill=fill, font=f or F["body"], anchor=anchor)


def rounded(draw, box, radius=24, fill=PANEL, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def load_shoe(path):
    im = Image.open(path).convert("RGBA")
    alpha = im.getchannel("A")
    bbox = alpha.point(lambda p: 255 if p > 10 else 0).getbbox()
    if bbox:
        im = im.crop(bbox)
    return im


def paste_fit(base, shoe, box, shadow=True):
    x1, y1, x2, y2 = box
    max_w, max_h = x2 - x1, y2 - y1
    scale = min(max_w / shoe.width, max_h / shoe.height)
    new_size = (int(shoe.width * scale), int(shoe.height * scale))
    im = shoe.resize(new_size, Image.LANCZOS)
    x = x1 + (max_w - new_size[0]) // 2
    y = y1 + (max_h - new_size[1]) // 2
    if shadow:
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        sx1 = x + int(new_size[0] * 0.16)
        sx2 = x + int(new_size[0] * 0.88)
        sy1 = y + int(new_size[1] * 0.82)
        sy2 = sy1 + max(30, int(new_size[1] * 0.10))
        od.ellipse((sx1, sy1, sx2, sy2), fill=(0, 0, 0, 34))
        overlay = overlay.filter(ImageFilter.GaussianBlur(18))
        base.paste(overlay, (0, 0), overlay)
    base.paste(im, (x, y), im)
    return (x, y, x + new_size[0], y + new_size[1])


def label(draw, xy, text, fill=GREEN, text_fill=WHITE):
    x, y = xy
    pad_x, pad_y = 22, 12
    bbox = draw.textbbox((0, 0), text, font=F["mid"])
    w, h = bbox[2] - bbox[0] + pad_x * 2, bbox[3] - bbox[1] + pad_y * 2
    rounded(draw, (x, y, x + w, y + h), radius=28, fill=fill)
    draw.text((x + pad_x, y + pad_y - 2), text, font=F["mid"], fill=text_fill)
    return (x, y, x + w, y + h)


def draw_check(draw, center, color=GREEN):
    x, y = center
    draw.ellipse((x - 23, y - 23, x + 23, y + 23), fill=color)
    draw.line((x - 11, y, x - 3, y + 10, x + 14, y - 12), fill=WHITE, width=6, joint="curve")


def draw_x(draw, center):
    x, y = center
    draw.ellipse((x - 23, y - 23, x + 23, y + 23), outline=RED, width=6)
    draw.line((x - 10, y - 10, x + 10, y + 10), fill=RED, width=5)
    draw.line((x + 10, y - 10, x - 10, y + 10), fill=RED, width=5)


def draw_foot(draw, x, y, wide=True):
    skin = (250, 238, 218)
    outline = (82, 90, 101)
    width = 110 if wide else 76
    draw.rounded_rectangle((x, y + 52, x + width, y + 210), radius=34, fill=skin, outline=outline, width=3)
    toe_offsets = [0, 23, 45, 66, 86] if wide else [0, 15, 29, 42, 54]
    sizes = [28, 25, 22, 20, 18]
    for i, off in enumerate(toe_offsets):
        s = sizes[i]
        draw.ellipse((x + off, y + 18 + i * 2, x + off + s, y + 18 + i * 2 + s), fill=skin, outline=outline, width=3)


def main_image(cfg, out):
    im = canvas(WHITE)
    d = ImageDraw.Draw(im)
    shoe = load_shoe(cfg["main"])
    paste_fit(im, shoe, (25, 150, 975, 875), shadow=True)
    draw_text(d, (70, 72), "WIDE TOE BOX", NAVY, F["title"])
    d.line((70, 133, 280, 133), fill=GREEN, width=5)
    im.save(out / "01_MAIN_WIDE_TOE_BOX.jpg", quality=95)


def wide_toe_image(cfg, out):
    im = canvas(LIGHT_BG)
    d = ImageDraw.Draw(im)
    draw_text(d, (72, 58), "ROOMY TOE SPACE", NAVY, F["title"])
    draw_text(d, (72, 112), "Wide toe box helps reduce forefoot pressure", SLATE, F["body"])
    rounded(d, (60, 185, 460, 890), radius=34, fill=WHITE, outline=LINE)
    rounded(d, (540, 185, 940, 890), radius=34, fill=WHITE, outline=LINE)
    draw_text(d, (260, 230), "Narrow Toe", NAVY, F["mid"], anchor="mm")
    draw_text(d, (740, 230), "Wide Toe Box", NAVY, F["mid"], anchor="mm")
    draw_foot(d, 214, 305, wide=False)
    draw_foot(d, 675, 305, wide=True)
    draw_x(d, (260, 710))
    draw_check(d, (740, 710))
    draw_text(d, (260, 770), "Squeezed toes", MUTED, F["body"], anchor="mm")
    draw_text(d, (740, 770), "Natural toe spread", GREEN_DARK, F["body"], anchor="mm")
    shoe = load_shoe(cfg["top"])
    paste_fit(im, shoe, (560, 505, 925, 675), shadow=False)
    im.save(out / "02_ROOMY_TOE_SPACE.jpg", quality=95)


def comfort_image(cfg, out):
    im = canvas((248, 249, 250))
    d = ImageDraw.Draw(im)
    draw_text(d, (70, 62), "WALK LONGER FEEL BETTER", NAVY, F["title"])
    draw_text(d, (70, 118), "Cushion support for daily walking and standing", SLATE, F["body"])
    d.rounded_rectangle((0, 650, 1000, 1000), radius=0, fill=(232, 238, 235))
    for y, color in [(650, (222, 232, 227)), (705, (216, 226, 221)), (760, (210, 221, 216))]:
        d.arc((-90, y, 1090, y + 410), 186, 354, fill=color, width=9)
    shoe = load_shoe(cfg["main"])
    paste_fit(im, shoe, (72, 250, 900, 720), shadow=True)
    for x in [195, 355, 515, 675]:
        d.arc((x, 690, x + 130, 760), 200, 340, fill=ORANGE, width=6)
    cards = [("Shock Absorption", 82), ("Standing Comfort", 375), ("Daily Walking", 668)]
    for text, x in cards:
        rounded(d, (x, 805, x + 250, 880), radius=18, fill=WHITE, outline=LINE)
        draw_check(d, (x + 39, 842), GREEN)
        draw_text(d, (x + 75, 825), text, NAVY, F["small"])
    im.save(out / "03_WALK_LONGER_FEEL_BETTER.jpg", quality=95)


def structure_image(cfg, out):
    im = canvas(WHITE)
    d = ImageDraw.Draw(im)
    draw_text(d, (70, 58), "ALL DAY COMFORT", NAVY, F["title"])
    draw_text(d, (70, 112), "Engineered with practical comfort components", SLATE, F["body"])
    shoe = load_shoe(cfg["main"])
    bbox = paste_fit(im, shoe, (70, 245, 850, 720), shadow=True)
    callouts = [
        ("Knit Upper", (650, 282), (575, 385)),
        ("Cushion Insole", (650, 392), (625, 330)),
        ("EVA Midsole", (650, 502), (520, 610)),
        ("Rubber Outsole", (650, 612), (420, 665)),
    ]
    for text, pos, target in callouts:
        x, y = pos
        rounded(d, (x, y, x + 275, y + 70), radius=18, fill=LIGHT_BG, outline=LINE)
        d.ellipse((x + 22, y + 24, x + 42, y + 44), fill=GREEN)
        draw_text(d, (x + 58, y + 21), text, NAVY, F["body"])
        d.line((x, y + 35, target[0], target[1]), fill=GREEN, width=3)
        d.ellipse((target[0] - 6, target[1] - 6, target[0] + 6, target[1] + 6), fill=GREEN)
    im.save(out / "04_ALL_DAY_COMFORT_STRUCTURE.jpg", quality=95)


def oem_image(cfg, out):
    im = canvas((247, 249, 250))
    d = ImageDraw.Draw(im)
    draw_text(d, (70, 58), "CUSTOM YOUR BRAND", NAVY, F["title"])
    draw_text(d, (70, 112), "OEM ODM service for importers and brands", SLATE, F["body"])
    shoe = load_shoe(cfg["main"])
    paste_fit(im, shoe, (165, 235, 835, 650), shadow=True)
    items = [
        ("Custom Logo", (70, 720), GREEN),
        ("Custom Box", (295, 720), KHAKI),
        ("Custom Insole", (520, 720), ORANGE),
        ("Custom Color", (745, 720), BLACK),
    ]
    for text, (x, y), color in items:
        rounded(d, (x, y, x + 185, y + 165), radius=24, fill=WHITE, outline=LINE)
        if text == "Custom Box":
            d.rectangle((x + 58, y + 40, x + 128, y + 100), outline=color, width=5)
            d.line((x + 58, y + 40, x + 92, y + 18, x + 128, y + 40), fill=color, width=5)
        elif text == "Custom Insole":
            d.rounded_rectangle((x + 70, y + 26, x + 116, y + 105), radius=22, outline=color, width=5)
        elif text == "Custom Color":
            for i, c in enumerate([GREEN, KHAKI, ORANGE, BLACK]):
                d.ellipse((x + 38 + i * 30, y + 45, x + 62 + i * 30, y + 69), fill=c)
        else:
            d.ellipse((x + 63, y + 30, x + 122, y + 89), outline=color, width=5)
            draw_text(d, (x + 92, y + 47), "B", color, F["mid"], anchor="mm")
        draw_text(d, (x + 92, y + 120), text, NAVY, F["small"], anchor="mm")
    im.save(out / "05_CUSTOM_YOUR_BRAND_OEM_ODM.jpg", quality=95)


def lightweight_image(cfg, out):
    im = canvas(WHITE)
    d = ImageDraw.Draw(im)
    draw_text(d, (70, 58), "LIGHTWEIGHT FLEXIBLE COMFORT", NAVY, F["title"])
    draw_text(d, (70, 112), "Easy wear for travel, work and daily walking", SLATE, F["body"])

    shoe = load_shoe(cfg["main"])
    paste_fit(im, shoe, (65, 230, 695, 620), shadow=True)

    rounded(d, (705, 230, 930, 430), radius=26, fill=LIGHT_BG, outline=LINE)
    draw_text(d, (818, 278), cfg["weight"], ORANGE, font(54, True), anchor="mm")
    draw_text(d, (818, 335), "Approx. single shoe", NAVY, F["small"], anchor="mm")
    draw_text(d, (818, 365), "size 41 reference", MUTED, F["tiny"], anchor="mm")

    rounded(d, (705, 470, 930, 670), radius=26, fill=LIGHT_BG, outline=LINE)
    d.arc((760, 510, 875, 610), 200, 340, fill=GREEN, width=8)
    d.polygon([(855, 565), (882, 553), (872, 584)], fill=GREEN)
    draw_text(d, (818, 625), "Flexible Sole", NAVY, F["small"], anchor="mm")

    features = [
        ("Lightweight", 92),
        ("Flexible", 378),
        ("Comfort", 664),
    ]
    for text, x in features:
        rounded(d, (x, 760, x + 245, 840), radius=18, fill=LIGHT_BG, outline=LINE)
        draw_check(d, (x + 42, 800), GREEN)
        draw_text(d, (x + 82, 783), text, NAVY, F["body"])

    im.save(out / "06_LIGHTWEIGHT_FLEXIBLE_COMFORT.jpg", quality=95)


def generate():
    products = {
        "数据包1_白黑款": {
            "main": ROOT / "01_原始数据包" / "5.13贝强1数据包" / "透明图" / "5M4A1132.png",
            "top": ROOT / "01_原始数据包" / "5.13贝强1数据包" / "透明图" / "5M4A1120.png",
            "weight": "267g",
        },
        "数据包2_灰卡其款": {
            "main": ROOT / "01_原始数据包" / "5.13贝强2数据包" / "透明图" / "5M4A1145.png",
            "top": ROOT / "01_原始数据包" / "5.13贝强2数据包" / "透明图" / "5M4A1153.png",
            "weight": "253g",
        },
    }
    for name, cfg in products.items():
        out = OUT_ROOT / name
        out.mkdir(parents=True, exist_ok=True)
        main_image(cfg, out)
        wide_toe_image(cfg, out)
        comfort_image(cfg, out)
        structure_image(cfg, out)
        oem_image(cfg, out)
        lightweight_image(cfg, out)
    print(OUT_ROOT)


if __name__ == "__main__":
    generate()
