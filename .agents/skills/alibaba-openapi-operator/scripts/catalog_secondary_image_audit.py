#!/usr/bin/env python3
"""Read-only audit of Alibaba SKU, product-detail, and company images."""

from __future__ import annotations

import argparse
import csv
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
from pathlib import Path
import re
import time
import xml.etree.ElementTree as ET
from urllib.request import Request, urlopen

from PIL import Image

from alibaba_openapi import DEFAULT_CONFIG, api_error, load_config, top_call


def get_product(config: dict, product_id: str) -> tuple[str, dict | None, str | None]:
    last_error = None
    for attempt in range(3):
        response = top_call(config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
        product = response.get("product")
        if product:
            return product_id, product, None
        last_error = str(api_error(response) or response.get("msg_info") or response.get("message") or "missing product")
        time.sleep(1 + attempt)
    return product_id, None, last_error


HTML_IMAGE_RE = re.compile(r"(?:https?:)?//sc\d+\.alicdn\.com/kf/[A-Za-z0-9]+\.(?:png|jpg|jpeg|webp)(?:_[^\s\"'<>?]+)?", re.I)


def get_description_data(config: dict, product_id: str) -> tuple[str | None, list[str], str | None]:
    response = top_call(
        config,
        "alibaba.icbu.product.schema.render",
        {"param_product_top_publish_request": {"product_id": int(product_id), "language": "en_US"}},
    )
    xml_text = response.get("data")
    if not isinstance(xml_text, str):
        return None, [], str(api_error(response) or response.get("message") or "missing schema XML")
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        return None, [], f"invalid schema XML:{exc}"
    value = root.find(".//field[@id='productDescType']/value")
    desc_type = value.text if value is not None else None
    super_text = root.find(".//field[@id='superText']/value")
    html_urls = HTML_IMAGE_RE.findall(super_text.text or "") if super_text is not None else []
    return desc_type, html_urls, None


def url_key(url: str) -> str:
    return url.split("?", 1)[0].replace("http://", "https://")


def probe(url: str) -> dict:
    last_error = None
    for attempt in range(3):
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "image/jpeg"})
            with urlopen(request, timeout=30) as response:
                data = response.read()
                content_type = response.headers.get("Content-Type", "")
            image = Image.open(BytesIO(data))
            image.load()
            return {"ok": True, "width": image.width, "height": image.height, "format": image.format, "content_type": content_type}
        except Exception as exc:
            last_error = f"{type(exc).__name__}:{exc}"
            time.sleep(0.5 + attempt)
    return {"ok": False, "error": last_error}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    catalog = json.loads(args.catalog.read_text(encoding="utf-8-sig"))
    ids = [str(row["product_id"]) for row in catalog]
    config = load_config(args.config)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        fetched = list(pool.map(lambda pid: get_product(config, pid), ids))

    products = {pid: product for pid, product, _ in fetched if product}
    fetch_errors = {pid: error for pid, _, error in fetched if error}
    records: list[dict] = []
    all_urls: set[str] = set()

    for pid in ids:
        product = products.get(pid)
        if not product:
            records.append({"product_id": pid, "scope": "product", "position": "", "name": "", "url": "", "risk": f"PRODUCT_GET_ERROR:{fetch_errors.get(pid)}"})
            continue

        main_urls = list((product.get("main_image") or {}).get("images") or [])
        detail_rows = list((((product.get("struct_detail") or {}).get("detail_image") or {}).get("images") or []))
        company_rows = list((((product.get("struct_detail") or {}).get("company_image") or {}).get("images") or []))
        sku_attrs = list((product.get("product_sku") or {}).get("sku_attributes") or [])
        color_values = []
        for attr in sku_attrs:
            values = list(attr.get("values") or [])
            if "color" in str(attr.get("attribute_name", "")).lower() or any(value.get("image_url") for value in values):
                color_values.extend(values)

        description_type = None
        html_detail_urls: list[str] = []
        if not detail_rows and not company_rows:
            description_type, html_detail_urls, description_error = get_description_data(config, pid)
            if description_error:
                records.append({"product_id": pid, "scope": "detail", "position": "", "name": "", "url": "", "risk": f"DESCRIPTION_TYPE_CHECK_ERROR:{description_error}"})
        if description_type not in {"2", "5"}:
            if len(detail_rows) < 4:
                records.append({"product_id": pid, "scope": "detail", "position": "", "name": "", "url": "", "risk": f"DETAIL_IMAGE_COUNT_{len(detail_rows)}"})
            if len(company_rows) != 5:
                records.append({"product_id": pid, "scope": "company", "position": "", "name": "", "url": "", "risk": f"COMPANY_IMAGE_COUNT_{len(company_rows)}"})

        groups = [
            ("sku_color", [(value.get("system_value_name", ""), value.get("image_url", "")) for value in color_values]),
            ("detail", [((row.get("image_set") or {}).get("name", ""), row.get("image_url", "")) for row in detail_rows]),
            ("company", [((row.get("image_set") or {}).get("name", ""), row.get("image_url", "")) for row in company_rows]),
            ("html_detail", [("HTML detail image", url) for url in html_detail_urls]),
        ]
        main_keys = {url_key(url) for url in main_urls}
        for scope, rows in groups:
            seen_within: set[str] = set()
            for position, (name, url) in enumerate(rows, 1):
                risk: list[str] = []
                if not url:
                    risk.append("MISSING_URL")
                else:
                    key = url_key(url)
                    all_urls.add(key)
                    if ".alicdn.com/kf/" not in key:
                        risk.append("NOT_ALIBABA_IMAGE_BANK_URL")
                    # The same exterior image may legitimately serve regular and
                    # fleece SKUs when the lining is not visible. Do not invent a
                    # visually different SKU image merely to make URLs unique.
                    if key in seen_within and scope != "sku_color":
                        risk.append("DUPLICATE_SECONDARY_URL")
                    seen_within.add(key)
                    if scope in {"detail", "html_detail"} and key in main_keys:
                        risk.append("DETAIL_DUPLICATES_MAIN")
                records.append({"product_id": pid, "scope": scope, "position": position, "name": name, "url": url, "risk": "|".join(risk)})

    with ThreadPoolExecutor(max_workers=16) as pool:
        probe_rows = dict(zip(sorted(all_urls), pool.map(probe, sorted(all_urls))))
    for row in records:
        url = row.get("url")
        if not url:
            continue
        result = probe_rows.get(url_key(url), {})
        row.update({"width": result.get("width", ""), "height": result.get("height", ""), "format": result.get("format", "")})
        if not result.get("ok"):
            row["risk"] = "|".join(filter(None, [row.get("risk", ""), "DOWNLOAD_ERROR:" + str(result.get("error"))]))

    fields = ["product_id", "scope", "position", "name", "url", "width", "height", "format", "risk"]
    with (args.output / "次级图片审计.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    risk_rows = [row for row in records if row.get("risk")]
    summary = {
        "catalog_products": len(ids),
        "products_fetched": len(products),
        "unique_secondary_images": len(all_urls),
        "records": len(records),
        "risk_records": len(risk_rows),
        "risk_products": len({row["product_id"] for row in risk_rows}),
        "product_get_errors": fetch_errors,
    }
    (args.output / "次级图片审计摘要.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
