from __future__ import annotations

import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).parent
M1_CSV = ROOT / "主图视觉二次筛查_2026-09-04/主图视觉二次筛查.csv"
SIX_CSV = ROOT / "全六图视觉二次审计_2026-09-04/全六图逐槽视觉筛查.csv"
OUT = ROOT / "逐款问题图复核"
SUSPECT_INDEXES = {42, 43, 45, 57, 61, 64, 73, 74, 75, 85, 95, 98, 99, 128, 135, 136, 143, 150, 151}


def main() -> None:
    with M1_CSV.open(encoding="utf-8-sig", newline="") as handle:
        m1_rows = list(csv.DictReader(handle))
    suspect_ids = {m1_rows[index - 1]["product_id"] for index in SUSPECT_INDEXES}
    with SIX_CSV.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_product: dict[str, list[dict]] = {}
    for row in rows:
        if row["product_id"] in suspect_ids:
            by_product.setdefault(row["product_id"], []).append(row)
    OUT.mkdir(exist_ok=True)
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 18)
    for index in sorted(SUSPECT_INDEXES):
        product = m1_rows[index - 1]
        pid = product["product_id"]
        images = sorted(by_product.get(pid, []), key=lambda row: int(row["image_position"] or 0))
        sheet = Image.new("RGB", (1500, 600), (244, 246, 248))
        draw = ImageDraw.Draw(sheet)
        draw.text((20, 10), f"{index:03d} | {pid} | {product['title']}", fill=(15, 23, 42), font=font)
        for offset, row in enumerate(images[:6]):
            x = offset * 250
            cache = Path(row["cache"]) if row.get("cache") else None
            if cache and cache.is_file():
                image = Image.open(cache).convert("RGB")
                image.thumbnail((230, 470))
                sheet.paste(image, (x + 10, 55 + (470 - image.height) // 2))
            else:
                draw.rectangle((x + 10, 70, x + 240, 510), fill=(255, 232, 232))
            draw.text((x + 95, 545), f"M{offset + 1}", fill=(15, 23, 42), font=font)
        sheet.save(OUT / f"{index:03d}_{pid}.jpg", quality=92)
    print(f"Wrote {len(SUSPECT_INDEXES)} gallery sheets to {OUT}")


if __name__ == "__main__":
    main()
