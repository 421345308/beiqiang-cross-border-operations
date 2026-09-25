"""Build link-specific D1 cards from the verified Model 9002 source photo.

The original HR001-A card is intentionally left untouched. This script only
renders the B/C model labels with the same deterministic layout and shoe pixels.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


PROJECT = Path(__file__).resolve().parent
SOURCE = PROJECT / "00_来源素材" / "HR001_9002" / "02_gallery.webp"
OUTPUT = PROJECT / "02_正式详情候选" / "HR001_9002"
WIDTH = HEIGHT = 1200


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = Path(r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf")
    return ImageFont.truetype(str(path), size)


def write(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str,
          size: int, fill: str, bold: bool = False, anchor: str | None = None) -> None:
    draw.text(xy, value, font=font(size, bold), fill=fill, anchor=anchor)


def build(suffix: str) -> Path:
    image = Image.new("RGB", (WIDTH, HEIGHT), "#FFFFFF")
    draw = ImageDraw.Draw(image)
    write(draw, (70, 58), f"MODEL HR001-{suffix} / 9002", 22, "#075440", True)
    write(draw, (70, 92), "MEN'S KNIT SLIP-ON WALKING SHOES", 46, "#152129", True)
    write(draw, (70, 153), "Wholesale offer for importers, wholesalers and online sellers", 22, "#59666C")

    with Image.open(SOURCE) as source:
        fitted = ImageOps.contain(source.convert("RGB"), (870, 670), Image.Resampling.LANCZOS)
    panel = Image.new("RGB", (880, 680), "#FFFFFF")
    panel.paste(fitted, ((880 - fitted.width) // 2, (680 - fitted.height) // 2))
    image.paste(panel, (160, 225))

    for index, label in enumerate(("TEXTILE UPPER", "SLIP-ON", "EU 38–47", "2 COLORS")):
        left = 65 + index * 285
        draw.rounded_rectangle((left, 955, left + 250, 1028), radius=30, fill="#E8F2EE")
        write(draw, (left + 125, 991), label, 18, "#075440", True, "mm")
    write(draw, (600, 1090), "Final order details are confirmed before quotation",
          21, "#59666C", anchor="mm")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / f"D1_product_overview_HR001-{suffix}.jpg"
    if path.exists():
        raise FileExistsError(f"Will not overwrite an existing asset: {path}")
    image.save(path, quality=94, subsampling=0)
    return path


if __name__ == "__main__":
    for variant in ("B", "C"):
        print(build(variant))
