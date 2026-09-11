import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


CANVAS = 1200
NAVY = (25, 39, 55)
BLUE = (73, 135, 170)
LIGHT = (244, 247, 249)
MID = (99, 113, 126)
WHITE = (255, 255, 255)


def font(size: int, bold: bool = False):
    name = "arialbd.ttf" if bold else "arial.ttf"
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / name), size)


def fit_cover(path: Path, size=(CANVAS, CANVAS)):
    im = Image.open(path).convert("RGB")
    ratio = max(size[0] / im.width, size[1] / im.height)
    im = im.resize((round(im.width * ratio), round(im.height * ratio)), Image.Resampling.LANCZOS)
    left = (im.width - size[0]) // 2
    top = (im.height - size[1]) // 2
    return im.crop((left, top, left + size[0], top + size[1]))


def fit_inside(path: Path, box, background=WHITE):
    im = Image.open(path).convert("RGB")
    w, h = box[2] - box[0], box[3] - box[1]
    ratio = min(w / im.width, h / im.height)
    im = im.resize((round(im.width * ratio), round(im.height * ratio)), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (w, h), background)
    canvas.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
    return canvas


def label(draw, xy, text, size=30, color=NAVY, bold=False):
    draw.text(xy, text, font=font(size, bold), fill=color)


def save(im, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, "PNG", optimize=True)


def overview(cfg, root, out):
    im = fit_cover(root / cfg["overview_bg"])
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle((54, 52, 1146, 238), 26, fill=(255, 255, 255, 235))
    od.rectangle((54, 52, 68, 238), fill=BLUE)
    im = Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")
    d = ImageDraw.Draw(im)
    label(d, (94, 76), cfg["overview_title"], 44, NAVY, True)
    label(d, (96, 148), cfg["overview_subtitle"], 27, MID)
    save(im, out / f'{cfg["model"]}_d01_overview.png')


def structure(cfg, root, out):
    im = Image.new("RGB", (CANVAS, CANVAS), LIGHT)
    d = ImageDraw.Draw(im)
    label(d, (70, 56), "PRODUCT CONSTRUCTION", 48, NAVY, True)
    label(d, (72, 122), "Clear materials for sourcing discussion", 27, MID)
    shoe = fit_inside(root / cfg["structure_image"], (70, 180, 1130, 675), LIGHT)
    im.paste(shoe, (70, 180))
    d = ImageDraw.Draw(im)
    items = cfg["structure_items"]
    positions = [(70, 720), (620, 720), (70, 900), (620, 900)]
    for i, (title, desc) in enumerate(items):
        x, y = positions[i]
        d.rounded_rectangle((x, y, x + 510, y + 145), 24, fill=WHITE, outline=(220, 226, 231), width=2)
        d.ellipse((x + 24, y + 38, x + 84, y + 98), fill=BLUE)
        label(d, (x + 44, y + 48), str(i + 1), 30, WHITE, True)
        label(d, (x + 108, y + 28), title, 27, NAVY, True)
        label(d, (x + 108, y + 75), desc, 21, MID)
    d.rounded_rectangle((70, 1090, 1130, 1140), 18, fill=(226, 234, 239))
    label(d, (337, 1102), "Specifications confirmed before production", 22, NAVY)
    save(im, out / f'{cfg["model"]}_d02_structure.png')


def colors_and_sizes(cfg, root, out):
    im = Image.new("RGB", (CANVAS, CANVAS), WHITE)
    d = ImageDraw.Draw(im)
    label(d, (70, 56), "COLORS & SIZE RANGE", 48, NAVY, True)
    label(d, (72, 122), f'Available labeling: {cfg["size_range"]}', 28, MID)
    card_w, card_h = 330, 620
    x_positions = [55, 435, 815]
    for idx, item in enumerate(cfg["colors"]):
        x = x_positions[idx]
        d.rounded_rectangle((x, 215, x + card_w, 215 + card_h), 30, fill=LIGHT, outline=(220, 226, 231), width=2)
        shoe = fit_inside(root / item["image"], (x + 16, 250, x + card_w - 16, 670), LIGHT)
        im.paste(shoe, (x + 16, 250))
        label(d, (x + 38, 710), item["name"], 30, NAVY, True)
        label(d, (x + 38, 758), "Color option", 22, MID)
    d.rounded_rectangle((70, 900, 1130, 1085), 28, fill=NAVY)
    label(d, (118, 938), cfg["size_range"], 52, WHITE, True)
    label(d, (430, 945), "Mixed colors and sizes can be discussed", 28, WHITE)
    label(d, (72, 1120), "Color appearance may vary slightly by screen and production batch.", 21, MID)
    save(im, out / f'{cfg["model"]}_d03_colors.png')


def oem(cfg, root, out):
    im = fit_cover(root / cfg["oem_bg"])
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle((54, 48, 730, 420), 28, fill=(255, 255, 255, 238))
    im = Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")
    d = ImageDraw.Draw(im)
    label(d, (90, 76), "OEM / ODM DISCUSSION", 44, NAVY, True)
    label(d, (92, 138), "Color  •  Logo  •  Insole", 27, MID)
    label(d, (92, 179), "Label  •  Packaging", 27, MID)
    d.rounded_rectangle((90, 242, 690, 294), 18, fill=NAVY)
    label(d, (118, 253), f'MOQ  {cfg["moq"]}', 25, WHITE, True)
    label(d, (92, 320), f'{cfg["lead_time"]}', 26, NAVY, True)
    label(d, (92, 365), f'{cfg["package"]}', 22, MID)
    d.rounded_rectangle((54, 1090, 1146, 1150), 20, fill=(255, 255, 255, 230))
    label(d, (270, 1107), "Final details confirmed for each order before production", 22, NAVY)
    save(im, out / f'{cfg["model"]}_d04_oem.png')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("config")
    args = parser.parse_args()
    cfg_path = Path(args.config).resolve()
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    root = Path(cfg["product_root"])
    out = root / "02_详情页"
    overview(cfg, root, out)
    structure(cfg, root, out)
    colors_and_sizes(cfg, root, out)
    oem(cfg, root, out)
    print(json.dumps({"output": str(out), "files": sorted(p.name for p in out.glob("*.png"))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
