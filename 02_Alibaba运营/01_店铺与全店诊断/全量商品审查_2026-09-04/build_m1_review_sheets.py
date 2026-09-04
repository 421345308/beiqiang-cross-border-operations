from __future__ import annotations

import csv
import math
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).parent / "主图视觉二次筛查_2026-09-04"
CSV_PATH = ROOT / "主图视觉二次筛查.csv"
OUT_DIR = ROOT / "逐款首图人工复核"


def model_from_title(title: str) -> str:
    matches = re.findall(r"(?:Model\s+)?([A-Z]{1,3}[- ]?\d{2,6}|\d{3,5})", title, re.I)
    return matches[-1] if matches else ""


def main() -> None:
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    OUT_DIR.mkdir(exist_ok=True)
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 14)
    width, tile_width, image_height, label_height = 1600, 320, 250, 70
    for page in range(math.ceil(len(rows) / 20)):
        subset = rows[page * 20 : (page + 1) * 20]
        sheet = Image.new("RGB", (width, 4 * (image_height + label_height)), (245, 247, 248))
        draw = ImageDraw.Draw(sheet)
        for offset, row in enumerate(subset):
            x = (offset % 5) * tile_width
            y = (offset // 5) * (image_height + label_height)
            cache = Path(row["cache"]) if row["cache"] else None
            if cache and cache.is_file():
                image = Image.open(cache).convert("RGB")
                image.thumbnail((300, 240))
                sheet.paste(image, (x + (tile_width - image.width) // 2, y + 5))
            else:
                draw.rectangle((x + 10, y + 10, x + 310, y + 235), fill=(255, 235, 235))
                draw.text((x + 88, y + 105), "NO MAIN IMAGE", fill=(170, 24, 24), font=font)
            index = page * 20 + offset + 1
            label = f"{index:03d} | {row['product_id']} | {model_from_title(row['title'])}"
            draw.text((x + 6, y + 250), label, fill=(15, 23, 42), font=font)
            draw.text((x + 6, y + 272), row["title"][:36], fill=(55, 65, 81), font=font)
        sheet.save(OUT_DIR / f"M1_{page + 1:02d}.jpg", quality=92)
    print(f"Wrote {math.ceil(len(rows) / 20)} sheets for {len(rows)} products to {OUT_DIR}")


if __name__ == "__main__":
    main()
