from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
RAW_ROOT = ROOT / "01_原始数据包"
UPLOAD_ROOT = ROOT / "02_可上传素材"
SRC = RAW_ROOT / "5.13贝强2数据包" if (RAW_ROOT / "5.13贝强2数据包").exists() else ROOT / "5.13贝强2数据包"
OUT = UPLOAD_ROOT / "数据包2" / "英文主图"
FONT = r"C:\Windows\Fonts\arial.ttf"
BOLD = r"C:\Windows\Fonts\arialbd.ttf"


def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)


def text_width(draw, text, f):
    return draw.textbbox((0, 0), text, font=f)[2]


def fit_font(draw, text, max_w, size, bold=False):
    while size > 14 and text_width(draw, text, font(size, bold)) > max_w:
        size -= 2
    return font(size, bold)


def rounded_panel(draw, xy, fill=(255, 255, 255), outline=(226, 232, 240), radius=24):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=2)


def bg(top=(237, 247, 250), bottom=(255, 255, 255)):
    img = Image.new("RGB", (800, 800), top)
    px = img.load()
    for y in range(800):
        t = y / 799
        col = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        for x in range(800):
            px[x, y] = col
    return img.convert("RGBA")


def paste_product(canvas, path, box, shadow=True, rotate=0):
    product = Image.open(path).convert("RGBA")
    bbox = product.getbbox()
    if bbox:
        product = product.crop(bbox)
    if rotate:
        product = product.rotate(rotate, expand=True, resample=Image.BICUBIC)
    product.thumbnail((box[2] - box[0], box[3] - box[1]), Image.LANCZOS)
    x = box[0] + (box[2] - box[0] - product.width) // 2
    y = box[1] + (box[3] - box[1] - product.height) // 2
    if shadow:
        alpha = product.split()[-1].filter(ImageFilter.GaussianBlur(14))
        sh = Image.new("RGBA", product.size, (0, 0, 0, 70))
        sh.putalpha(alpha)
        canvas.alpha_composite(sh, (x + 8, y + 18))
    canvas.alpha_composite(product, (x, y))


def pill(draw, xy, text, fill=(24, 121, 97), max_w=260):
    x, y = xy
    f = fit_font(draw, text, max_w - 36, 26, True)
    w = min(max_w, text_width(draw, text, f) + 36)
    draw.rounded_rectangle((x, y, x + w, y + 48), radius=24, fill=fill)
    draw.text((x + 18, y + 10), text, fill="white", font=f)


def check_icon(draw, cx, cy, ok=True):
    color = (16, 185, 129) if ok else (239, 68, 68)
    draw.ellipse((cx - 34, cy - 34, cx + 34, cy + 34), fill=(255, 255, 255), outline=color, width=7)
    if ok:
        draw.line((cx - 18, cy, cx - 4, cy + 15, cx + 22, cy - 18), fill=color, width=8)
    else:
        draw.line((cx - 18, cy - 18, cx + 18, cy + 18), fill=color, width=8)
        draw.line((cx + 18, cy - 18, cx - 18, cy + 18), fill=color, width=8)


def simple_foot(draw, x, y, wide=False):
    fill = (255, 248, 236)
    outline = (110, 118, 130)
    w = 74 if wide else 54
    draw.rounded_rectangle((x, y + 38, x + w, y + 168), radius=26, fill=fill, outline=outline, width=3)
    toe_r = [13, 11, 10, 9, 8]
    for i, r in enumerate(toe_r):
        tx = x + 8 + i * (w - 16) / 4
        ty = y + 28 - i * 2
        draw.ellipse((tx - r, ty - r, tx + r, ty + r), fill=fill, outline=outline, width=2)


def wide_toe_comparison():
    canvas = bg((246, 249, 252), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    draw.text((48, 38), "Wide Toe Box Comfort", fill=(15, 23, 42), font=fit_font(draw, "Wide Toe Box Comfort", 700, 50, True))
    draw.text((50, 98), "More forefoot room, less squeezing", fill=(71, 85, 105), font=fit_font(draw, "More forefoot room, less squeezing", 700, 28))

    paste_product(canvas, SRC / "透明图" / "5M4A1145.png", (18, 145, 385, 690), shadow=True, rotate=0)
    pill(draw, (60, 650), "Roomy Forefoot", (24, 121, 97))

    rounded_panel(draw, (410, 155, 755, 705), fill=(255, 255, 255), outline=(143, 181, 124), radius=28)
    draw.text((444, 188), "Narrow Toe", fill=(51, 65, 85), font=font(24, True))
    simple_foot(draw, 455, 230, False)
    simple_foot(draw, 548, 230, False)
    check_icon(draw, 665, 320, ok=False)
    draw.text((444, 420), "Wide Toe Box", fill=(51, 65, 85), font=font(24, True))
    simple_foot(draw, 455, 462, True)
    simple_foot(draw, 568, 462, True)
    check_icon(draw, 665, 552, ok=True)
    draw.text((440, 642), "Natural toe spread", fill=(24, 121, 97), font=font(25, True))
    canvas.convert("RGB").save(OUT / "01_WIDE_TOE_BOX_MAIN_EN.jpg", quality=95, optimize=True)


def widened_upper():
    canvas = bg((230, 246, 250), (252, 253, 255))
    draw = ImageDraw.Draw(canvas)
    draw.text((44, 42), "Wider & Higher Toe Area", fill=(15, 23, 42), font=fit_font(draw, "Wider & Higher Toe Area", 710, 46, True))
    draw.text((46, 98), "Comfortable fit for different foot shapes", fill=(71, 85, 105), font=fit_font(draw, "Comfortable fit for different foot shapes", 700, 27))
    paste_product(canvas, SRC / "透明图" / "5M4A1145.png", (20, 152, 360, 735), shadow=True)
    paste_product(canvas, SRC / "透明图" / "5M4A1153.png", (332, 230, 752, 520), shadow=True)
    draw.line((518, 300, 518, 450), fill=(248, 181, 92), width=9)
    draw.line((485, 300, 551, 300), fill=(248, 181, 92), width=9)
    draw.line((485, 450, 551, 450), fill=(248, 181, 92), width=9)
    pill(draw, (78, 610), "Wider Toe", (220, 38, 38))
    pill(draw, (448, 532), "Higher Upper", (220, 38, 38))
    rounded_panel(draw, (380, 590, 748, 720), fill=(255, 255, 255, 235), outline=(203, 213, 225), radius=18)
    draw.text((410, 620), "No tight squeeze", fill=(15, 23, 42), font=font(30, True))
    draw.text((410, 665), "Roomy casual walking fit", fill=(71, 85, 105), font=font(23))
    canvas.convert("RGB").save(OUT / "02_WIDER_HIGHER_TOE_MAIN_EN.jpg", quality=95, optimize=True)


def insole_support():
    canvas = bg((247, 250, 252), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    draw.text((45, 42), "Wide-Last Insole System", fill=(15, 23, 42), font=fit_font(draw, "Wide-Last Insole System", 710, 48, True))
    draw.text((47, 98), "Designed for comfort, cushioning and anti-slip support", fill=(71, 85, 105), font=fit_font(draw, "Designed for comfort, cushioning and anti-slip support", 700, 25))

    # Build insole-like shapes from product colors; this keeps all original information without the Chinese text.
    for x, fill, title, sub in [
        (70, (58, 107, 77), "Wide Last", "Roomy fit"),
        (310, (88, 120, 93), "Cushioned Insole", "Soft step"),
        (550, (227, 131, 59), "Textured Sole", "Stable grip"),
    ]:
        draw.rounded_rectangle((x, 215, x + 150, 610), radius=70, fill=fill, outline=(255, 255, 255), width=5)
        draw.ellipse((x + 20, 235, x + 130, 350), fill=tuple(min(255, c + 35) for c in fill))
        draw.rounded_rectangle((x + 42, 380, x + 108, 570), radius=32, fill=tuple(max(0, c - 30) for c in fill))
        draw.text((x - 12, 642), title, fill=(15, 23, 42), font=fit_font(draw, title, 185, 25, True))
        draw.text((x - 4, 680), sub, fill=(71, 85, 105), font=fit_font(draw, sub, 175, 21))

    rounded_panel(draw, (88, 725, 712, 775), fill=(236, 253, 245), outline=(187, 247, 208), radius=20)
    draw.text((128, 737), "Breathable mesh upper + EVA midsole + rubber outsole", fill=(22, 101, 52), font=fit_font(draw, "Breathable mesh upper + EVA midsole + rubber outsole", 560, 24, True))
    canvas.convert("RGB").save(OUT / "03_WIDE_LAST_INSOLE_MAIN_EN.jpg", quality=95, optimize=True)


def lightweight():
    canvas = bg((255, 255, 255), (247, 250, 252))
    draw = ImageDraw.Draw(canvas)
    draw.text((70, 54), "253g Lightweight Design", fill=(249, 115, 22), font=fit_font(draw, "253g Lightweight Design", 670, 50, True))
    draw.text((72, 116), "Approx. single-shoe weight, size 41 reference", fill=(71, 85, 105), font=fit_font(draw, "Approx. single-shoe weight, size 41 reference", 650, 25))
    paste_product(canvas, SRC / "透明图" / "5M4A1145.png", (55, 205, 745, 590), shadow=True)
    rounded_panel(draw, (198, 610, 602, 760), fill=(248, 250, 252), outline=(226, 232, 240), radius=24)
    draw.text((248, 632), "Easy for travel, walking", fill=(15, 23, 42), font=font(29, True))
    draw.text((260, 680), "and daily casual wear", fill=(71, 85, 105), font=font(27))
    canvas.convert("RGB").save(OUT / "04_253G_LIGHTWEIGHT_MAIN_EN.jpg", quality=95, optimize=True)


def fit_contain(path, size=(800, 800), fill=(255, 255, 255)):
    src = Image.open(path).convert("RGB")
    src.thumbnail(size, Image.LANCZOS)
    canvas = Image.new("RGB", size, fill)
    canvas.paste(src, ((size[0] - src.width) // 2, (size[1] - src.height) // 2))
    return canvas.convert("RGBA")


def original_style_hero():
    canvas = bg((86, 160, 222), (232, 247, 255))
    draw = ImageDraw.Draw(canvas)
    # Rebuild this one instead of editing the tall source so it remains a square main image.
    draw.rectangle((0, 690, 800, 800), fill=(164, 205, 72))
    draw.ellipse((-80, 705, 210, 880), fill=(119, 181, 58))
    draw.text((45, 48), "Wide-Last Casual Shoes", fill="white", font=fit_font(draw, "Wide-Last Casual Shoes", 720, 56, True), stroke_width=2, stroke_fill=(44, 98, 148))
    draw.text((58, 124), "Wider & higher toe design for more foot shapes", fill="white", font=fit_font(draw, "Wider & higher toe design for more foot shapes", 690, 30, True), stroke_width=1, stroke_fill=(44, 98, 148))
    paste_product(canvas, SRC / "透明图" / "5M4A1145.png", (55, 200, 430, 520), shadow=True, rotate=-18)
    paste_product(canvas, SRC / "透明图" / "5M4A1153.png", (135, 410, 760, 785), shadow=True, rotate=0)
    for start, end in [((115, 425), (55, 500)), ((190, 410), (130, 505)), ((250, 410), (318, 500))]:
        draw.line((start[0], start[1], end[0], end[1]), fill=(255, 255, 255), width=7)
        draw.polygon([(end[0], end[1]), (end[0] - 24, end[1] - 8), (end[0] + 8, end[1] - 25)], fill=(255, 255, 255))
    canvas.convert("RGB").save(OUT / "05_WIDE_LAST_CASUAL_MAIN_EN.jpg", quality=95, optimize=True)


def original_style_insole():
    img = fit_contain(SRC / "750天猫" / "001_02.jpg")
    draw = ImageDraw.Draw(img)
    # Replace Chinese title and bottom captions while preserving the lasts, shoe image and foot icons.
    draw.rectangle((0, 0, 800, 220), fill=(255, 255, 255))
    draw.text((86, 50), "Professional Wide Shoe Last", fill=(15, 23, 42), font=fit_font(draw, "Professional Wide Shoe Last", 640, 48, True))
    draw.rectangle((0, 642, 470, 800), fill=(255, 255, 255))
    draw.text((55, 674), "Wide Toe", fill=(15, 23, 42), font=font(27, True))
    draw.text((55, 708), "Last", fill=(15, 23, 42), font=font(27, True))
    draw.text((286, 674), "Regular", fill=(15, 23, 42), font=font(27, True))
    draw.text((286, 708), "Last", fill=(15, 23, 42), font=font(27, True))
    img.convert("RGB").save(OUT / "06_PROFESSIONAL_WIDE_LAST_MAIN_EN.jpg", quality=95, optimize=True)


def original_style_toe_compare():
    img = fit_contain(SRC / "750天猫" / "001_05.jpg", fill=(238, 238, 238))
    draw = ImageDraw.Draw(img)
    # Replace top headline.
    draw.rectangle((0, 0, 800, 132), fill=(238, 238, 238))
    draw.text((96, 22), "Roomy Toe Box Comfort", fill=(31, 41, 55), font=fit_font(draw, "Roomy Toe Box Comfort", 620, 45, True))
    draw.text((124, 78), "Break toe constraints, release forefoot space", fill=(71, 85, 105), font=fit_font(draw, "Break toe constraints, release forefoot space", 560, 25))
    # Cover Chinese captions inside the comparison panel and add English labels.
    draw.rectangle((430, 340, 742, 440), fill=(255, 255, 255))
    draw.rectangle((430, 604, 742, 732), fill=(255, 255, 255))
    draw.text((500, 362), "Narrow toe", fill=(31, 41, 55), font=font(23, True))
    draw.text((500, 394), "squeezed toes", fill=(71, 85, 105), font=font(20))
    draw.text((500, 636), "Wide toe box", fill=(24, 121, 97), font=font(23, True))
    draw.text((500, 672), "comfortable fit", fill=(71, 85, 105), font=font(20))
    img.convert("RGB").save(OUT / "07_ROOMY_TOE_COMPARISON_MAIN_EN.jpg", quality=95, optimize=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    wide_toe_comparison()
    widened_upper()
    insole_support()
    lightweight()
    original_style_hero()
    original_style_insole()
    original_style_toe_compare()


if __name__ == "__main__":
    main()
