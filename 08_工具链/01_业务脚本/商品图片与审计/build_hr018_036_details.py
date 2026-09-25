"""Build four product-specific B2B detail panels from exact HR018/036 photos."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "99_临时区/HR018_候选核验"
ASSET = ROOT / "02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21/06_确定性图稿/HR018_036"
FONT = "C:/Windows/Fonts/arial.ttf"
BOLD = "C:/Windows/Fonts/arialbd.ttf"
INK = (30, 45, 54)
MUTED = (94, 107, 113)
GREEN = (21, 91, 77)
BG = (249, 250, 248)


def f(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(BOLD if bold else FONT, size)


def card(title: str, subtitle: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (1200, 1200), BG)
    d = ImageDraw.Draw(img)
    d.text((66, 56), title, font=f(51, True), fill=INK)
    d.text((68, 127), subtitle, font=f(28), fill=MUTED)
    return img, d


def photo(image: Image.Image, box: tuple[int, int, int, int], source: Image.Image) -> None:
    x1, y1, x2, y2 = box
    fitted = ImageOps.fit(source, (x2 - x1, y2 - y1), method=Image.Resampling.LANCZOS)
    image.paste(fitted, (x1, y1))


def label(d: ImageDraw.ImageDraw, xy: tuple[int, int], head: str, body: str) -> None:
    x, y = xy
    d.text((x, y), head, font=f(31, True), fill=GREEN)
    d.text((x, y + 50), body, font=f(31), fill=INK)


def save(img: Image.Image, filename: str) -> None:
    ASSET.mkdir(parents=True, exist_ok=True)
    img.save(ASSET / filename, format="PNG", optimize=True)


def main() -> None:
    black = Image.open(RAW / "路崎036_图2.jpg").convert("RGB")
    beige_scene = Image.open(RAW / "路崎036_图3.jpg").convert("RGB")
    color_black = Image.open(ASSET / "HR018_036_SKU_black.png").convert("RGB")
    color_beige = Image.open(ASSET / "HR018_036_SKU_beige.png").convert("RGB")
    upper = Image.open(RAW / "路崎036_详情原图/es4kmcjclgjv1vv08q0a7zdci7b5k1tq.jpg").convert("RGB")
    sole_panel = Image.open(ASSET / "HR018_036_M4_outsole.png").convert("RGB")

    # D1: actual style and sourcing identity, with a distinct beige wear view.
    d1, d = card("MODEL HR018 / 036 | LACE-UP MESH SHOE", "Wholesale product overview")
    photo(d1, (60, 212, 763, 1013), beige_scene)
    d.rounded_rectangle((790, 212, 1140, 1013), radius=20, fill=(233, 246, 241))
    label(d, (820, 277), "MODEL", "HR018 / 036")
    label(d, (820, 454), "COLORS", "Black / Beige")
    label(d, (820, 631), "SIZE RANGE", "EU 39–48")
    label(d, (820, 808), "CLOSURE", "Lace-up")
    d.text((70, 1070), "Confirm color-size mix and availability when requesting a quote.", font=f(27), fill=MUTED)
    save(d1, "HR018_036_D1_overview.png")

    # D2: construction evidence; source-photo crop begins below the Chinese wide-fit claim.
    d2, d = card("VISIBLE CONSTRUCTION", "Actual upper and outsole photos of the same 036 style")
    upper_crop = upper.crop((0, 340, 790, 1102))
    photo(d2, (65, 230, 560, 890), upper_crop)
    photo(d2, (640, 230, 1135, 890), sole_panel.crop((56, 170, 945, 770)))
    d.text((75, 923), "MESH UPPER + LACE-UP", font=f(31, True), fill=GREEN)
    d.text((645, 923), "OUTSOLE TREAD VIEW", font=f(31, True), fill=GREEN)
    d.text((75, 1025), "Confirm final material details against the actual order specification.",
           font=f(25), fill=MUTED)
    save(d2, "HR018_036_D2_construction.png")

    # D3: SKU choice; single-color source-pixel crops, no speculative conversions.
    d3, d = card("COLOR AND EU SIZE CHOICE", "Two photographed colors | EU 39–48")
    photo(d3, (55, 240, 570, 795), color_black)
    photo(d3, (630, 240, 1145, 795), color_beige)
    d.text((248, 815), "BLACK", font=f(36, True), fill=INK)
    d.text((830, 815), "BEIGE", font=f(36, True), fill=INK)
    d.rounded_rectangle((106, 917, 1094, 1086), radius=22, fill=GREEN)
    d.text((190, 953), "EU 39  40  41  42  43  44  45  46  47  48", font=f(35, True), fill=(255, 255, 255))
    d.text((275, 1110), "Send your preferred size ratio with the inquiry.", font=f(27), fill=MUTED)
    save(d3, "HR018_036_D3_colors_sizes.png")

    # D4: product-specific RFQ route; no factory-origin or exact stock promise.
    d4, d = card("SEND AN ORDER BRIEF", "For the photographed HR018 / 036 shoe")
    photo(d4, (64, 235, 520, 770), black)
    d.rounded_rectangle((562, 235, 1140, 770), radius=20, fill=(233, 246, 241))
    rows = ["01  Black / Beige color mix", "02  EU 39–48 size ratio", "03  Target quantity", "04  Bag / box packing request", "05  Destination and terms"]
    for i, row in enumerate(rows):
        d.text((600, 278 + i * 91), row, font=f(29), fill=INK)
    d.rounded_rectangle((65, 842, 1135, 1070), radius=22, fill=GREEN)
    d.text((112, 875), "We confirm the final quotation and options", font=f(35, True), fill=(255, 255, 255))
    d.text((112, 932), "against your actual order requirements.", font=f(33), fill=(255, 255, 255))
    d.text((70, 1110), "Packing and dispatch terms are confirmed for each order.", font=f(26), fill=MUTED)
    save(d4, "HR018_036_D4_order_brief.png")


if __name__ == "__main__":
    main()
