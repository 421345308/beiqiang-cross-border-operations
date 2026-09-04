from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFont, ImageFilter


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
AUDIT = ROOT / "02_Alibaba运营/01_店铺与全店诊断/全量商品审查_2026-09-04"
DETAILS = AUDIT / "api_product_get_details.json"
OUTPUT = Path(r"E:\贝强大文件\01_产品资产\02_可发布素材\00_全店统一升级_2026-09-04")

# These current first images have a structurally incomplete sole. Use a verified
# alternate image from the same live product instead of trying to hallucinate it.
SOURCE_SLOT_OVERRIDES = {
    "1601939602873": 3,  # A206
    "1601939641542": 2,  # A116
    "1601939658415": 2,  # A507
    "1601939626612": 2,  # A502
    "1601939707196": 3,  # BQ001
    "1601939638522": 2,  # T55836 clean pair instead of text card
}

SOURCE_PRODUCT_SLOT_OVERRIDES = {
    "1601939736061": ("1601939638522", 3),  # T55836 clean single shoe
    "10000043763325": ("1601939638522", 2),  # T55836 clean pair
}

REMOVE_OLD_TOP_LEFT_LABEL = {"10000042896165", "10000042821848"}
FORCE_REBUILD = {
    "1601939726170", "1601939638522", "1601939736061", "10000043763325",
    "10000042896165", "10000042821848",
}


def download(url: str) -> Image.Image:
    last_error = None
    for attempt in range(1, 6):
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "image/avif,image/webp,image/*,*/*"})
            with urlopen(request, timeout=60) as response:
                data = response.read()
            break
        except Exception as exc:
            last_error = exc
            if attempt == 5:
                raise
            time.sleep(attempt * 1.5)
    source = Image.open(BytesIO(data)).convert("RGBA")
    # Correctly flatten transparent Alibaba PNGs. Hidden RGB data in zero-alpha
    # pixels caused the vertical-streak failures seen in earlier listings.
    white = Image.new("RGBA", source.size, (255, 255, 255, 255))
    white.alpha_composite(source)
    return white.convert("RGB")


def square_canvas(image: Image.Image) -> Image.Image:
    canvas = Image.new("RGB", (1000, 1000), (250, 251, 252))
    copy = image.copy()
    copy.thumbnail((1000, 1000), Image.Resampling.LANCZOS)
    canvas.paste(copy, ((1000 - copy.width) // 2, (1000 - copy.height) // 2))
    return canvas


def add_badge(image: Image.Image, clear_old_label: bool) -> Image.Image:
    canvas = square_canvas(image)
    if clear_old_label:
        # These two legacy M1 files have a pure-white studio background. Match
        # it exactly when removing the old top-left claim so no grey repair
        # rectangle remains visible around the new service badge.
        ImageDraw.Draw(canvas).rectangle((0, 0, 440, 155), fill=(255, 255, 255))

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle((38, 42, 278, 126), radius=18, fill=(18, 44, 39, 55))
    shadow = shadow.filter(ImageFilter.GaussianBlur(9))
    overlay.alpha_composite(shadow)

    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle((32, 34, 272, 118), radius=18, fill=(255, 255, 255, 244), outline=(38, 105, 88, 255), width=2)
    draw.ellipse((48, 54, 78, 84), fill=(38, 105, 88, 255))
    draw.line((56, 70, 64, 78, 73, 61), fill=(255, 255, 255, 255), width=4)

    bold = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 23)
    regular = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 17)
    draw.text((90, 47), "CUSTOM LOGO", font=bold, fill=(25, 70, 59, 255))
    draw.text((90, 80), "OEM / ODM", font=regular, fill=(58, 77, 71, 255))
    return Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")


def product_fact(summary: str, title: str) -> str:
    fact = re.split(r"\s+Prepared for\s+", summary.strip(), maxsplit=1, flags=re.I)[0].strip()
    if not fact:
        fact = title.strip().rstrip(".")
    return fact.rstrip(".") + "."


def buyer_highlights(summary: str, title: str) -> str:
    return " ".join(
        [
            product_fact(summary, title),
            "Factory-direct wholesale pricing is quoted according to style, quantity, materials, size ratio and packing.",
            "Custom logo, color and packaging options can be discussed for OEM/ODM orders.",
            "Product appearance, size assortment and quantity are checked before shipment.",
            "Production and dispatch are arranged promptly after specifications are confirmed.",
            "Samples can be discussed for quality and fit evaluation before bulk orders.",
        ]
    )


def main() -> None:
    details = json.loads(DETAILS.read_text(encoding="utf-8-sig"))
    image_dir = OUTPUT / "01_首图"
    image_dir.mkdir(parents=True, exist_ok=True)
    ordered_ids = sorted(details, key=lambda value: int(value))

    def prepare_one(index: int, product_id: str) -> dict:
        product = details[product_id].get("product") or {}
        if not product:
            raise RuntimeError(f"Missing product.get payload for {product_id}")
        urls = list((product.get("main_image") or {}).get("images") or [])
        if len(urls) != 6:
            raise RuntimeError(f"{product_id} has {len(urls)} main images; expected 6")
        source_product_id, slot = SOURCE_PRODUCT_SLOT_OVERRIDES.get(
            product_id, (product_id, SOURCE_SLOT_OVERRIDES.get(product_id, 1))
        )
        source_product = details[source_product_id].get("product") or {}
        source_urls = list((source_product.get("main_image") or {}).get("images") or [])
        source_url = source_urls[slot - 1]
        model = next(
            (str(row.get("value")) for row in product.get("attributes") or [] if str(row.get("name", "")).lower() in {"model number", "model no.", "model"}),
            "",
        )
        safe_model = re.sub(r"[^A-Za-z0-9_-]+", "_", model)[:40].strip("_") or "NO_MODEL"
        output = image_dir / f"{product_id}_{safe_model}_M1.jpg"
        if not output.is_file() or product_id in FORCE_REBUILD:
            image = download(source_url)
            final = add_badge(image, product_id in REMOVE_OLD_TOP_LEFT_LABEL)
            final.save(output, quality=95, subsampling=0, optimize=True)
        old_summary = str(((product.get("struct_detail") or {}).get("product_summary") or ""))
        return {
            "sequence": index,
            "product_id": product_id,
            "encrypted_product_id": product.get("product_id"),
            "title": product.get("subject"),
            "model": model,
            "category_id": product.get("category_id"),
            "source_slot": slot,
            "source_product_id": source_product_id,
            "source_url": source_url,
            "output": str(output),
            "old_summary": old_summary,
            "new_summary": buyer_highlights(old_summary, str(product.get("subject") or "")),
            "video_policy": "preserve existing verified binding",
        }

    rows = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = {
            pool.submit(prepare_one, index, product_id): (index, product_id)
            for index, product_id in enumerate(ordered_ids, 1)
        }
        for job in as_completed(jobs):
            row = job.result()
            rows.append(row)
            print(f"[{len(rows):03d}/151] prepared {row['product_id']} {row['model']} from M{row['source_slot']}", flush=True)
    rows.sort(key=lambda row: row["sequence"])
    manifest = OUTPUT / "全店151款首图与产品亮点写入计划.json"
    manifest.write_text(json.dumps({"product_count": len(rows), "products": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(manifest)


if __name__ == "__main__":
    main()
