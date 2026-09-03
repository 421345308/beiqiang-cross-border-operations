#!/usr/bin/env python3
"""Create a read-only visual audit pack for the live Alibaba.com catalog.

The script calls the authorized product-list API, downloads images only in
memory, creates compact contact sheets, and writes metadata/heuristic results.
It never changes an Alibaba product or image-bank record.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from io import BytesIO
import importlib.util
import json
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat


HERE = Path(__file__).resolve().parent
CLIENT_SPEC = importlib.util.spec_from_file_location(
    "alibaba_openapi", HERE / "alibaba_openapi.py"
)
CLIENT = importlib.util.module_from_spec(CLIENT_SPEC)
assert CLIENT_SPEC.loader is not None
CLIENT_SPEC.loader.exec_module(CLIENT)


def fetch_image(url: str) -> Image.Image:
    # Alibaba CDN may return AVIF for a generic browser Accept header even when
    # the URL ends in .jpg. Request JPEG/PNG explicitly so Pillow-based QA does
    # not misclassify a valid CDN image as corrupt.
    request = Request(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "image/jpeg"},
    )
    with urlopen(request, timeout=45) as response:
        return Image.open(BytesIO(response.read())).convert("RGB")


def dhash(image: Image.Image, size: int = 16) -> int:
    gray = image.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    value = 0
    for row in range(size):
        offset = row * (size + 1)
        for col in range(size):
            value = (value << 1) | (pixels[offset + col] > pixels[offset + col + 1])
    return value


def hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def occupancy(image: Image.Image) -> dict[str, float]:
    sample = image.copy()
    sample.thumbnail((400, 400))
    width, height = sample.size
    corners = [sample.getpixel((x, y)) for x, y in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1))]
    bg = tuple(int(sum(pixel[channel] for pixel in corners) / 4) for channel in range(3))
    # Pillow's native image operations avoid a slow Python loop over every
    # pixel. A luminance threshold is sufficient for this first-pass blank-
    # space heuristic; visual review remains authoritative.
    background = Image.new("RGB", sample.size, bg)
    mask = ImageChops.difference(sample, background).convert("L").point(
        lambda value: 255 if value >= 18 else 0
    )
    bbox = mask.getbbox()
    if not bbox:
        return {"width": 0.0, "height": 0.0, "box_area": 0.0, "ink": 0.0}
    left, top, right, bottom = bbox
    stat = ImageStat.Stat(mask)
    return {
        "width": (right - left) / width,
        "height": (bottom - top) / height,
        "box_area": ((right - left) * (bottom - top)) / (width * height),
        "ink": stat.mean[0] / 255,
    }


def load_and_measure(url: str, reference_hash: int | None) -> tuple[Image.Image | None, dict | None, int | None, str | None]:
    try:
        image = fetch_image(url)
        measure = occupancy(image)
        distance = hamming(reference_hash, dhash(image)) if reference_hash is not None else None
        preview = image.copy()
        preview.thumbnail((320, 320), Image.Resampling.LANCZOS)
        image.close()
        return preview, measure, distance, None
    except Exception as exc:
        return None, None, None, type(exc).__name__


def list_products(config: dict) -> list[dict]:
    first = CLIENT.top_call(config, "alibaba.icbu.product.list", {
        "language": "ENGLISH", "current_page": 1, "page_size": 50
    })
    if CLIENT.api_error(first):
        raise CLIENT.ClientError(json.dumps(first, ensure_ascii=False))
    total = int(first.get("total_item", 0))
    products = list(first.get("products", []))
    effective_page_size = int(first.get("page_size") or len(products) or 50)
    pages = (total + effective_page_size - 1) // effective_page_size
    for page in range(2, pages + 1):
        payload = CLIENT.top_call(config, "alibaba.icbu.product.list", {
            "language": "ENGLISH", "current_page": page, "page_size": 50
        })
        if CLIENT.api_error(payload):
            raise CLIENT.ClientError(json.dumps(payload, ensure_ascii=False))
        products.extend(payload.get("products", []))
    return products


def draw_fit(canvas: Image.Image, image: Image.Image, box: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = box
    copy = image.copy()
    copy.thumbnail((right - left, bottom - top), Image.Resampling.LANCZOS)
    x = left + (right - left - copy.width) // 2
    y = top + (bottom - top - copy.height) // 2
    canvas.paste(copy, (x, y))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--images-per-product", type=int, default=6, choices=range(1, 7))
    parser.add_argument("--product-id", type=str)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    config = CLIENT.load_config(CLIENT.DEFAULT_CONFIG)
    products = list_products(config)
    if args.product_id:
        products = [product for product in products if str(product.get("id")) == args.product_id]
        if not products:
            raise RuntimeError(f"product not found: {args.product_id}")
    reference_hash = None
    if args.reference and args.reference.is_file():
        with Image.open(args.reference) as source:
            reference_hash = dhash(source.convert("RGB"))

    font = ImageFont.load_default()
    cell_w, cell_h = 170, 170
    label_w, row_h = 330, 205
    cols = args.images_per_product
    rows_per_sheet = 10
    records: list[dict] = []
    product_rows: list[dict] = []
    closest: list[tuple[int, dict]] = []

    tasks: list[tuple[int, int, str]] = []
    for product_index, product in enumerate(products):
        urls = list((product.get("main_image") or {}).get("images") or [])[:args.images_per_product]
        tasks.extend((product_index, image_index, url) for image_index, url in enumerate(urls, 1))
    with ThreadPoolExecutor(max_workers=24) as pool:
        loaded_values = list(pool.map(lambda task: load_and_measure(task[2], reference_hash), tasks))
    loaded_map = {
        (product_index, image_index): value
        for (product_index, image_index, _), value in zip(tasks, loaded_values)
    }

    for product_index, product in enumerate(products):
        all_urls = list((product.get("main_image") or {}).get("images") or [])
        urls = all_urls[:args.images_per_product]
        image_items: list[tuple[str, Image.Image | None, dict]] = []
        product_risks: list[str] = []
        for image_index, url in enumerate(urls, 1):
            loaded_item = loaded_map[(product_index, image_index)]
            image, measure, distance, failure = loaded_item
            record = {
                "product_index": product_index + 1,
                "product_id": product.get("id", ""),
                "encrypted_product_id": product.get("product_id", ""),
                "model": product.get("red_model", ""),
                "title": product.get("subject", ""),
                "status": product.get("status", ""),
                "display": product.get("display", ""),
                "image_position": image_index,
                "url": url,
                "width": "",
                "height": "",
                "occupancy_width": "",
                "occupancy_height": "",
                "occupancy_box_area": "",
                "occupancy_ink": "",
                "risk": "",
                "reference_distance": "",
            }
            if image is not None and measure is not None:
                record.update({
                    "width": image.width,
                    "height": image.height,
                    "occupancy_width": round(measure["width"], 4),
                    "occupancy_height": round(measure["height"], 4),
                    "occupancy_box_area": round(measure["box_area"], 4),
                    "occupancy_ink": round(measure["ink"], 4),
                })
                risks = []
                # Footwear side views are naturally wide and low. Flag only
                # genuinely undersized subjects; the old height<0.48 rule
                # mislabeled most normal side-profile shoes as low occupancy.
                if image_index == 1 and (
                    measure["width"] < 0.60
                    or measure["height"] < 0.26
                    or measure["box_area"] < 0.18
                ):
                    risks.append("P0_LOW_HERO_OCCUPANCY")
                if image.width != image.height:
                    risks.append("NON_SQUARE")
                # product.list commonly returns a 320 px Alibaba CDN preview even
                # when the image-bank original is 1000 px or larger.  Preview
                # dimensions therefore cannot be used to judge source resolution.
                if min(image.width, image.height) < 300:
                    risks.append("UNUSABLY_SMALL_PREVIEW")
                record["risk"] = "|".join(risks)
                product_risks.extend(risks)
                if reference_hash is not None:
                    record["reference_distance"] = distance
                    closest.append((distance, record.copy()))
                image_items.append((url, image, record))
            else:  # keep the rest of the catalog auditable
                record["risk"] = f"DOWNLOAD_ERROR:{failure}"
                product_risks.append(record["risk"])
                image_items.append((url, None, record))
            records.append(record)

        if len(all_urls) != 6:
            product_risks.append(f"MAIN_IMAGE_COUNT_{len(all_urls)}")
        product_rows.append({
            "product_index": product_index + 1,
            "product_id": product.get("id", ""),
            "encrypted_product_id": product.get("product_id", ""),
            "model": product.get("red_model", ""),
            "title": product.get("subject", ""),
            "status": product.get("status", ""),
            "display": product.get("display", ""),
            "group": product.get("group_name", ""),
            "gallery_count": len(all_urls),
            "risks": "|".join(sorted(set(product_risks))),
            "pc_detail_url": product.get("pc_detail_url", ""),
            "images": image_items,
        })

    # Six-image contact sheets, ten products per page.
    for sheet_no, start in enumerate(range(0, len(product_rows), rows_per_sheet), 1):
        chunk = product_rows[start:start + rows_per_sheet]
        canvas = Image.new("RGB", (label_w + cols * cell_w, len(chunk) * row_h), "white")
        draw = ImageDraw.Draw(canvas)
        for row_index, row in enumerate(chunk):
            top = row_index * row_h
            label = f"{row['product_index']:03d}  {row['model']}  ID {row['product_id']}\n{row['title'][:48]}\n{row['risks'] or 'heuristic-pass'}"
            draw.multiline_text((8, top + 10), label, fill="black", font=font, spacing=4)
            for col, (_, image, record) in enumerate(row["images"][:cols]):
                left = label_w + col * cell_w
                if image is not None:
                    draw_fit(canvas, image, (left + 5, top + 5, left + cell_w - 5, top + cell_h - 5))
                draw.text((left + 5, top + cell_h + 5), f"M{record['image_position']} {record['risk'][:18]}", fill="black", font=font)
        sheet_prefix = "首图联系表" if args.images_per_product == 1 else "六主图联系表"
        canvas.save(args.output / f"{sheet_prefix}_{sheet_no:02d}.jpg", quality=88, optimize=True)

    serializable_products = [{key: value for key, value in row.items() if key != "images"} for row in product_rows]
    (args.output / "线上商品目录.json").write_text(
        json.dumps(serializable_products, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (args.output / "主图机器审计.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)
    if reference_hash is not None:
        matches = [item for _, item in sorted(closest, key=lambda pair: pair[0])[:20]]
        (args.output / "用户截图近似匹配.json").write_text(
            json.dumps(matches, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    summary = {
        "product_count": len(product_rows),
        "image_count": len(records),
        "products_not_six_images": sum(row["gallery_count"] != 6 for row in product_rows),
        "products_with_machine_risk": sum(bool(row["risks"]) for row in product_rows),
        "contact_sheets": (len(product_rows) + rows_per_sheet - 1) // rows_per_sheet,
    }
    (args.output / "审计摘要.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
