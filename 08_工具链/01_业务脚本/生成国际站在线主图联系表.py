"""Create visual contact sheets from Workctl list-information batch output.

The script reads a saved, read-only trunk batch result, downloads only the six
online gallery images returned by Alibaba, and creates review sheets in groups
of five products. It does not edit platform data.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


CELL_W = 230
CELL_H = 250
LABEL_H = 34
COLS = 6
ROWS_PER_SHEET = 5


def load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\msyh.ttc"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def bq_number(model: str) -> int:
    match = re.search(r"BQ-?(\d{3})", model or "", re.IGNORECASE)
    return int(match.group(1)) if match else 9999


def load_products(result_path: Path) -> list[dict]:
    outer = json.loads(result_path.read_text(encoding="utf-8-sig"))
    rows: list[dict] = []
    for result in outer["data"]["results"]:
        payload = result["output"]["data"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        attrs = payload.get("basicInfo", {}).get("attr") or []
        model = next(
            (item.get("attrValue", "") for item in attrs if item.get("attrName") == "Model Number"),
            "",
        )
        images = payload.get("basicInfo", {}).get("images") or []
        images = sorted(images, key=lambda item: item.get("imageIndex", 0))
        rows.append(
            {
                "product_id": int(re.sub(r"^trunk_", "", result["name"])),
                "model": model,
                "images": [item.get("originalImageUrl", "") for item in images],
            }
        )
    return sorted(rows, key=lambda row: (bq_number(row["model"]), row["product_id"]))


def download_image(url: str) -> Image.Image:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read()
    return Image.open(io.BytesIO(data)).convert("RGB")


def render_cell(image: Image.Image | None, label: str, font: ImageFont.ImageFont) -> Image.Image:
    cell = Image.new("RGB", (CELL_W, CELL_H), "white")
    draw = ImageDraw.Draw(cell)
    draw.rectangle((0, 0, CELL_W - 1, CELL_H - 1), outline="#c8c8c8", width=1)
    draw.rectangle((0, 0, CELL_W - 1, LABEL_H - 1), fill="#f2f4f7")
    draw.text((7, 8), label, fill="#111111", font=font)
    if image is None:
        draw.text((65, 115), "MISSING", fill="#c00000", font=font)
        return cell
    fitted = ImageOps.contain(image, (CELL_W - 12, CELL_H - LABEL_H - 12))
    x = (CELL_W - fitted.width) // 2
    y = LABEL_H + (CELL_H - LABEL_H - fitted.height) // 2
    cell.paste(fitted, (x, y))
    return cell


def create_sheets(products: list[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    font = load_font(15)
    for offset in range(0, len(products), ROWS_PER_SHEET):
        group = products[offset : offset + ROWS_PER_SHEET]
        sheet = Image.new("RGB", (COLS * CELL_W, ROWS_PER_SHEET * CELL_H), "#dddddd")
        downloaded: dict[tuple[int, int], Image.Image | None] = {}
        with ThreadPoolExecutor(max_workers=12) as executor:
            futures = {}
            for row_index, product in enumerate(group):
                for image_index in range(COLS):
                    url = product["images"][image_index] if image_index < len(product["images"]) else ""
                    if url:
                        futures[executor.submit(download_image, url)] = (row_index, image_index)
                    else:
                        downloaded[(row_index, image_index)] = None
            for future in as_completed(futures):
                key = futures[future]
                try:
                    downloaded[key] = future.result()
                except Exception:
                    downloaded[key] = None
        for row_index, product in enumerate(group):
            for image_index in range(COLS):
                image = downloaded.get((row_index, image_index))
                label = f'{product["model"] or product["product_id"]}  #{image_index + 1}'
                sheet.paste(render_cell(image, label, font), (image_index * CELL_W, row_index * CELL_H))
        first = bq_number(group[0]["model"])
        last = bq_number(group[-1]["model"])
        target = output_dir / f"BQ{first:03d}-BQ{last:03d}_online_gallery.jpg"
        sheet.save(target, quality=90, optimize=True)
        print(target)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("result_json", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    create_sheets(load_products(args.result_json), args.output_dir)


if __name__ == "__main__":
    main()
