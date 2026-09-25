"""Create procurement and optional-packing main panels for sourced HR018/036."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21/06_确定性图稿/HR018_036"
SHOE = ROOT / "99_临时区/HR018_候选核验/路崎036_图2.jpg"
PACK = ROOT / "02_Alibaba运营/06_图片与检查记录/公司图复用模板_v5_2026-09-23/C5_bag_box_options_candidate.png"
BOLD = "C:/Windows/Fonts/arialbd.ttf"
REG = "C:/Windows/Fonts/arial.ttf"
INK = (28, 45, 53)
GREEN = (19, 91, 76)
BG = (250, 250, 248)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(BOLD if bold else REG, size)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    shoe = Image.open(SHOE).convert("RGB")
    if shoe.size != (800, 800):
        raise ValueError(shoe.size)
    m5 = Image.new("RGB", (1000, 1000), BG)
    d = ImageDraw.Draw(m5)
    d.text((52, 40), "REQUEST A SOURCING QUOTE", font=font(42, True), fill=INK)
    d.text((53, 98), "Model 036 | Lace-up mesh shoe", font=font(26), fill=(91, 105, 111))
    product = ImageOps.contain(shoe, (620, 620), Image.Resampling.LANCZOS)
    m5.paste(product, (25, 190))
    d.rounded_rectangle((618, 200, 968, 815), radius=22, fill=(236, 246, 242))
    rows = ["COLOR  Black / Beige", "SIZE  EU 39–48", "SIZE MIX  Your ratio", "QUANTITY  Your target", "PACKING  Your brief", "MARKET  Destination"]
    for i, row in enumerate(rows):
        y = 245 + i * 89
        d.ellipse((645, y + 13, 660, y + 28), fill=GREEN)
        d.text((678, y), row, font=font(23), fill=INK)
    d.rounded_rectangle((44, 858, 956, 955), radius=19, fill=GREEN)
    d.text((90, 885), "Confirm final price and availability per order", font=font(29, True), fill=(255, 255, 255))
    m5.save(OUT / "HR018_036_M5_quote_brief.png", format="PNG", optimize=True)

    pack = Image.open(PACK).convert("RGB")
    if pack.size != (1254, 1254):
        raise ValueError(pack.size)
    # Illustration panels only; replace candidate's broad availability sentence.
    bag = pack.crop((45, 260, 610, 1015))
    box = pack.crop((640, 260, 1210, 1015))
    m6 = Image.new("RGB", (1000, 1000), (245, 250, 249))
    d = ImageDraw.Draw(m6)
    d.text((52, 45), "PACKING OPTIONS TO DISCUSS", font=font(41, True), fill=INK)
    d.text((54, 101), "Illustrative bag / box options — not included by default", font=font(23), fill=(91, 105, 111))
    for image, x in [(bag, 35), (box, 510)]:
        fitted = ImageOps.contain(image, (455, 640), Image.Resampling.LANCZOS)
        m6.paste(fitted, (x + (455 - fitted.width) // 2, 180))
    d.rounded_rectangle((47, 830, 953, 958), radius=19, fill=GREEN)
    d.text((89, 853), "Final packing, cost and availability", font=font(31, True), fill=(255, 255, 255))
    d.text((89, 900), "confirmed against the actual order", font=font(27), fill=(255, 255, 255))
    m6.save(OUT / "HR018_036_M6_packing_brief.png", format="PNG", optimize=True)


if __name__ == "__main__":
    main()
