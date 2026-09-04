from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(r"E:\贝强大文件\01_产品资产\02_可发布素材\00_全店统一升级_2026-09-04")
PLAN = ROOT / "全店151款首图与产品亮点写入计划.json"
OUT = ROOT / "02_逐款复核联系表"


def main() -> None:
    rows = json.loads(PLAN.read_text(encoding="utf-8-sig"))["products"]
    OUT.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 14)
    for page in range(math.ceil(len(rows) / 20)):
        subset = rows[page * 20 : (page + 1) * 20]
        sheet = Image.new("RGB", (1600, 1320), (245, 247, 248))
        draw = ImageDraw.Draw(sheet)
        for offset, row in enumerate(subset):
            x, y = (offset % 5) * 320, (offset // 5) * 330
            image = Image.open(row["output"]).convert("RGB")
            image.thumbnail((300, 260))
            sheet.paste(image, (x + (320 - image.width) // 2, y + 4))
            draw.text((x + 6, y + 268), f"{row['sequence']:03d} | {row['product_id']} | M{row['source_slot']}", fill=(15, 23, 42), font=font)
            draw.text((x + 6, y + 291), str(row["title"])[:38], fill=(55, 65, 81), font=font)
        sheet.save(OUT / f"全店首图_{page + 1:02d}.jpg", quality=92)
    print(f"Wrote {math.ceil(len(rows) / 20)} contact sheets")


if __name__ == "__main__":
    main()
