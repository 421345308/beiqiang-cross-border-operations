"""Build an English color/size panel from exact Luqi 036 source-photo crops."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "99_临时区/HR018_候选核验/路崎036_详情原图/ll40450zz76rj9y5qc6jn8x88knz9xas.jpg"
OUT = ROOT / "02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21/06_确定性图稿/HR018_036/HR018_036_M2_colors.png"
SKU_OUT = {
    "BLACK": OUT.with_name("HR018_036_SKU_black.png"),
    "BEIGE": OUT.with_name("HR018_036_SKU_beige.png"),
}
FONT = Path("C:/Windows/Fonts/arial.ttf")
BOLD = Path("C:/Windows/Fonts/arialbd.ttf")


def draw_centered(draw: ImageDraw.ImageDraw, y: int, value: str, font: ImageFont.FreeTypeFont,
                  fill: tuple[int, int, int]) -> None:
    left, top, right, bottom = draw.textbbox((0, 0), value, font=font)
    draw.text(((1000 - (right - left)) // 2, y - top), value, font=font, fill=fill)


def main() -> None:
    source = Image.open(SOURCE).convert("RGB")
    if source.size != (790, 1034):
        raise ValueError(f"Unexpected source size: {source.size}")
    canvas = Image.new("RGB", (1000, 1000), (250, 250, 248))
    draw = ImageDraw.Draw(canvas)
    draw_centered(draw, 95, "AVAILABLE COLORS", ImageFont.truetype(str(BOLD), 51), (28, 42, 52))

    shoe_boxes = [
        ((20, 340, 390, 558), (18, 260), "BLACK"),
        ((400, 340, 780, 558), (510, 260), "BEIGE"),
    ]
    sku_reports: list[dict] = []
    for crop_box, location, label in shoe_boxes:
        crop = source.crop(crop_box)
        sku_shoe = ImageOps.contain(crop, (748, 440), method=Image.Resampling.LANCZOS)
        sku_canvas = Image.new("RGB", (800, 800), (241, 241, 241))
        sku_canvas.paste(sku_shoe, ((800 - sku_shoe.width) // 2, 180))
        sku_path = SKU_OUT[label]
        sku_path.parent.mkdir(parents=True, exist_ok=True)
        sku_canvas.save(sku_path, format="PNG", optimize=True)
        sku_reports.append({
            "color": label,
            "output": str(sku_path.relative_to(ROOT)),
            "output_sha256": hashlib.sha256(sku_path.read_bytes()).hexdigest(),
            "shoe_size": list(sku_shoe.size),
            "no_other_color_or_text": True,
        })
        crop = crop.resize((472, 278), Image.Resampling.LANCZOS)
        canvas.paste(crop, location)
        label_font = ImageFont.truetype(str(BOLD), 36)
        label_width = draw.textbbox((0, 0), label, font=label_font)[2]
        draw.text((location[0] + (472 - label_width) // 2, 580), label,
                  font=label_font, fill=(28, 42, 52))

    draw.rounded_rectangle((296, 690, 704, 773), radius=18, fill=(28, 42, 52))
    draw_centered(draw, 710, "EU 39–48", ImageFont.truetype(str(BOLD), 43), (255, 255, 255))
    draw_centered(draw, 826, "Confirm size mix when requesting a quote", ImageFont.truetype(str(FONT), 24), (93, 105, 110))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT, format="PNG", optimize=True)
    report = {
        "checked_at": datetime.now().astimezone().isoformat(),
        "status": "LOCAL_CANDIDATE_ONLY_NOT_UPLOADED",
        "source": str(SOURCE.relative_to(ROOT)),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "output": str(OUT.relative_to(ROOT)),
        "output_sha256": hashlib.sha256(OUT.read_bytes()).hexdigest(),
        "method": "deterministic crop, uniform scale and English text layout; no generative shoe redraw",
        "facts": ["Black", "Beige", "EU 39–48"],
        "excluded_source_copy": ["鞋底材质 EVA", "宽楦", "防滑"],
        "crop_boxes": [list(item[0]) for item in shoe_boxes],
        "sku_images": sku_reports,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
