from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
import json
from pathlib import Path
from PIL import Image, ImageOps
import requests


def dhash_image(image: Image.Image, size: int = 16) -> int:
    gray = ImageOps.grayscale(image).resize((size + 1, size), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    value = 0
    for y in range(size):
        row = y * (size + 1)
        for x in range(size):
            value = (value << 1) | int(pixels[row + x] > pixels[row + x + 1])
    return value


def fetch(row):
    response = requests.get(row["url"], timeout=20)
    response.raise_for_status()
    with Image.open(BytesIO(response.content)) as image:
        return row, dhash_image(image)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("audit_json", type=Path)
    parser.add_argument("targets", nargs="+", type=Path)
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()
    data = json.loads(args.audit_json.read_text(encoding="utf-8-sig"))
    targets = {}
    for path in args.targets:
        with Image.open(path) as image:
            targets[str(path)] = dhash_image(image)
    rows = []
    seen = set()
    for product_id, payload in data.items():
        product = (payload or {}).get("product") or {}
        for index, url in enumerate(((product.get("main_image") or {}).get("images") or []), 1):
            if not url or url in seen:
                continue
            seen.add(url)
            rows.append({
                "product_id": product_id,
                "model": product.get("red_model", ""),
                "title": product.get("subject", ""),
                "index": index,
                "url": url,
            })
    matches = {target: [] for target in targets}
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(fetch, row) for row in rows]
        for future in as_completed(futures):
            try:
                row, value = future.result()
            except Exception:
                continue
            for target, target_hash in targets.items():
                matches[target].append({"distance": (value ^ target_hash).bit_count(), **row})
    result = {target: sorted(items, key=lambda item: item["distance"])[: args.top] for target, items in matches.items()}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
