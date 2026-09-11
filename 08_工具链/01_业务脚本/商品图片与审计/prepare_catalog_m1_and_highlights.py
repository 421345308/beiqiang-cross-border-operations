from __future__ import annotations

import argparse
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
PLAN = OUTPUT / "全店151款首图与产品亮点写入计划.json"

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
# Alibaba's current score diagnostics explicitly recommend these clean source
# images for the five 3.9-point products flagged as bordered/composite images.
PLATFORM_RECOMMENDED_SOURCE_URLS = {
    "1601924292931": "https://sc04.alicdn.com/kf/Ha3948ca04b3144628ad4bcbff277403bR.jpg",
    "10000046705043": "https://sc04.alicdn.com/kf/H434791cf6b0e45f18b869e68f84e1924b.jpg",
    "10000047187673": "https://sc04.alicdn.com/kf/Sbc8a094bd5084b48be95aeb5008ad858g.jpg",
    "10000047198577": "https://sc04.alicdn.com/kf/S2e182987b56445148838b8e8df6739cc7.jpg",
    "10000047216427": "https://sc04.alicdn.com/kf/Sd2821a68cfcf4af48c465e31599c1ba1f.jpg",
    "10000047220568": "https://sc04.alicdn.com/kf/Sba6877c6d8814895aef0325699a0448ew.jpg",
    "10000043201799": "https://sc04.alicdn.com/kf/He96e1217a59947fba411e47bfeed4a3c7.jpg",
    "10000047208726": "https://sc04.alicdn.com/kf/Se4cd8fb7a8924678bc60f6c2039ae7d9x.jpg",
    "10000047221334": "https://sc04.alicdn.com/kf/Hdc031a497a614308a4809a400861caecb.jpg",
}

# These images are explicitly classified by Alibaba as bordered/composite after
# the standard header treatment. Their source photos contain a large uniform
# outer margin, so use a full-bleed layout and place sourcing cues directly on
# the photograph instead of preserving a separate white header band.
PLATFORM_FULL_BLEED = {
    "1601815020244",
    "1601924292931",
    "1601924347721",
    "10000046705043",
    "10000047187673",
    "10000047198577",
    "10000047216427",
    "10000047220568",
}

PLATFORM_COMPACT_B2B = {
    "1601924292931",
    "10000046705043",
    "10000047187673",
    "10000043201799",
    "10000047208726",
    "10000047221334",
    "10000047396313",
}

# These four products had no clean single-shoe photograph in their six-image
# gallery. Alibaba repeatedly classified the two-shoe compositions as combined
# images, so the approved replacements are controlled edits of the same SKU:
# only the second shoe/background clutter was removed; product identity is kept.
LOCAL_SINGLE_SHOE_SOURCE_PATHS = {
    "10000043201799": OUTPUT / "04_AI单鞋首图/10000043201799_A502_single.jpg",
    "10000047208726": OUTPUT / "04_AI单鞋首图/10000047208726_A189_single.jpg",
    "10000047221334": OUTPUT / "04_AI单鞋首图/10000047221334_811_single.jpg",
    "10000047396313": OUTPUT / "04_AI单鞋首图/10000047396313_A350_single.jpg",
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


def crop_uniform_margin(image: Image.Image) -> Image.Image:
    """Remove broad near-uniform outer margins without segmenting the shoe."""
    source = image.convert("RGB")
    probe = source.resize((250, 250), Image.Resampling.LANCZOS)
    corners = [probe.getpixel((4, 4)), probe.getpixel((245, 4)), probe.getpixel((4, 245)), probe.getpixel((245, 245))]
    background = tuple(sorted(pixel[channel] for pixel in corners)[len(corners) // 2] for channel in range(3))
    mask = Image.new("L", probe.size, 0)
    pixels = mask.load()
    for y in range(probe.height):
        for x in range(probe.width):
            pixel = probe.getpixel((x, y))
            distance = max(abs(pixel[channel] - background[channel]) for channel in range(3))
            # A low threshold is intentional: many studio sources use a light
            # grey photo field inside a pure-white outer margin. A higher
            # threshold mistakes that field for margin and zooms into the shoe.
            if distance > 6:
                pixels[x, y] = 255
    bbox = mask.getbbox()
    if not bbox:
        return source
    left, top, right, bottom = bbox
    # Expand slightly so shadows and toe/heel edges are not clipped.
    pad = 4
    left, top = max(0, left - pad), max(0, top - pad)
    right, bottom = min(250, right + pad), min(250, bottom + pad)
    scale_x, scale_y = source.width / 250, source.height / 250
    crop_box = (
        int(left * scale_x),
        int(top * scale_y),
        int(right * scale_x),
        int(bottom * scale_y),
    )
    return source.crop(crop_box)


def full_bleed_canvas(image: Image.Image) -> Image.Image:
    source = crop_uniform_margin(image)
    scale = max(1000 / source.width, 1000 / source.height)
    resized = source.resize(
        (max(1000, round(source.width * scale)), max(1000, round(source.height * scale))),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - 1000) // 2
    top = (resized.height - 1000) // 2
    return resized.crop((left, top, left + 1000, top + 1000))


def add_b2b_block(
    image: Image.Image,
    clear_old_label: bool,
    full_bleed: bool = False,
    compact: bool = False,
) -> Image.Image:
    canvas = full_bleed_canvas(image) if full_bleed else square_canvas(image)
    if clear_old_label:
        # These two legacy M1 files have a pure-white studio background. Match
        # it exactly when removing the old top-left claim so no grey repair
        # rectangle remains visible around the new service badge.
        ImageDraw.Draw(canvas).rectangle((0, 0, 440, 155), fill=(255, 255, 255))

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    if compact:
        # The score service still penalizes a large two-line overlay for these
        # three photos. Keep all sourcing cues in one unobtrusive line, with no
        # card, bar, border or multi-panel layout.
        sample = canvas.crop((20, 20, 780, 105)).convert("L")
        mean = sum(sample.resize((1, 1)).getdata())
        fill = (24, 79, 63, 255) if mean > 150 else (255, 255, 255, 255)
        stroke = (255, 255, 255, 180) if mean > 150 else (0, 0, 0, 180)
        compact_font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 18)
        draw.text(
            (28, 28),
            "FACTORY DIRECT | OEM/ODM | CUSTOM LOGO | MOQ 2 PAIRS | QC",
            font=compact_font,
            fill=fill,
            stroke_width=1,
            stroke_fill=stroke,
        )
        return Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    # Keep the first image product-led. This is a compact sourcing-value block,
    # not a bordered ad card, so it does not introduce the framed/composite look
    # reported by Alibaba's image-quality diagnostics.
    if full_bleed:
        # Text sits directly on the photograph. Alibaba classified even a
        # full-width translucent strip as a separate composite region on a
        # small subset of products, so do not draw any panel or border here.
        primary_fill = (255, 255, 255, 255)
        secondary_fill = (225, 243, 237, 255)
    else:
        draw.rounded_rectangle((34, 36, 45, 99), radius=5, fill=(28, 105, 83, 255))
        primary_fill = (24, 68, 57, 255)
        secondary_fill = (52, 73, 68, 255)
    bold = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 21)
    regular = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 15)
    text_kwargs = {"stroke_width": 2, "stroke_fill": (0, 0, 0, 180)} if full_bleed else {}
    draw.text((61, 34), "FACTORY DIRECT  |  OEM/ODM", font=bold, fill=primary_fill, **text_kwargs)
    draw.text((61, 69), "CUSTOM LOGO  |  MOQ 2 PAIRS  |  PRE-SHIPMENT QC", font=regular, fill=secondary_fill, **text_kwargs)
    return Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")


def buyer_highlights(summary: str, title: str) -> str:
    # Product Highlights are purchase-support copy, not a second title field.
    # Never fall back to the listing title when a product-specific fact sentence
    # is unavailable; that was the source of the previous title duplication.
    return " ".join(
        [
            "Factory-direct supply supports competitive wholesale quotations based on style, quantity, materials, size ratio and packing.",
            "OEM/ODM support includes custom logo, color and packaging options.",
            "Pre-shipment checks cover product appearance, size assortment and order quantity.",
            "Production and dispatch are arranged promptly after specifications are confirmed.",
            "Samples can be discussed for product and fit evaluation before bulk orders.",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", action="append", default=[])
    args = parser.parse_args()
    details = json.loads(DETAILS.read_text(encoding="utf-8-sig"))
    previous = {}
    if PLAN.is_file():
        previous = {
            str(row["product_id"]): row
            for row in json.loads(PLAN.read_text(encoding="utf-8-sig"))["products"]
        }
    image_dir = OUTPUT / "01_首图"
    image_dir.mkdir(parents=True, exist_ok=True)
    ordered_ids = sorted(set(details) | set(previous), key=lambda value: int(value))
    if args.only:
        wanted = {str(value) for value in args.only}
        ordered_ids = [product_id for product_id in ordered_ids if product_id in wanted]

    def prepare_one(index: int, product_id: str) -> dict:
        prior = previous.get(product_id) or {}
        product = (details.get(product_id) or {}).get("product") or {}
        urls = list((product.get("main_image") or {}).get("images") or [])
        if not product and not prior:
            raise RuntimeError(f"Missing product.get payload and prior plan for {product_id}")
        source_product_id, slot = SOURCE_PRODUCT_SLOT_OVERRIDES.get(
            product_id, (product_id, SOURCE_SLOT_OVERRIDES.get(product_id, 1))
        )
        source_product = (details.get(source_product_id) or {}).get("product") or {}
        source_urls = list((source_product.get("main_image") or {}).get("images") or [])
        source_url = PLATFORM_RECOMMENDED_SOURCE_URLS.get(product_id)
        if not source_url:
            source_url = str(prior.get("source_url") or source_urls[slot - 1])
        model = next(
            (
                str(row.get("value_name") or row.get("value") or "")
                for row in product.get("attributes") or []
                if str(row.get("attribute_name") or row.get("name") or "").lower()
                in {"model number", "model no.", "model"}
            ),
            str(prior.get("model") or ""),
        )
        safe_model = re.sub(r"[^A-Za-z0-9_-]+", "_", model)[:40].strip("_") or "NO_MODEL"
        output = image_dir / f"{product_id}_{safe_model}_M1.jpg"
        local_source = LOCAL_SINGLE_SHOE_SOURCE_PATHS.get(product_id)
        image = Image.open(local_source).convert("RGB") if local_source else download(source_url)
        final = add_b2b_block(
            image,
            product_id in REMOVE_OLD_TOP_LEFT_LABEL,
            full_bleed=product_id in PLATFORM_FULL_BLEED,
            compact=product_id in PLATFORM_COMPACT_B2B,
        )
        final.save(output, quality=95, subsampling=0, optimize=True)
        old_summary = str(((product.get("struct_detail") or {}).get("product_summary") or prior.get("old_summary") or ""))
        return {
            "sequence": index,
            "product_id": product_id,
            "encrypted_product_id": product.get("product_id") or prior.get("encrypted_product_id"),
            "title": product.get("subject") or prior.get("title"),
            "model": model,
            "category_id": product.get("category_id") or prior.get("category_id"),
            "source_slot": slot,
            "source_product_id": source_product_id,
            "source_url": source_url,
            "output": str(output),
            "old_summary": old_summary,
            "new_summary": buyer_highlights(old_summary, str(product.get("subject") or prior.get("title") or "")),
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
            print(f"[{len(rows):03d}/{len(ordered_ids):03d}] prepared {row['product_id']} {row['model']} from M{row['source_slot']}", flush=True)
    rows.sort(key=lambda row: row["sequence"])
    if args.only:
        merged = {str(row["product_id"]): row for row in previous.values()}
        merged.update({str(row["product_id"]): row for row in rows})
        final_rows = sorted(merged.values(), key=lambda row: int(row["sequence"]))
    else:
        final_rows = rows
    PLAN.write_text(json.dumps({"product_count": len(final_rows), "products": final_rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(PLAN)


if __name__ == "__main__":
    main()
