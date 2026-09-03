#!/usr/bin/env python3
"""Safely replace Alibaba product M1 images while preserving M2-M6.

The script uploads each local replacement to the seller image bank, assigns a
product-specific video where available (otherwise the approved short factory
video), updates the complete six-image Schema field, and reads the product back.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from PIL import Image

from alibaba_openapi import DEFAULT_CONFIG, api_error, load_config, top_call, upload_image


GENERIC_FACTORY_VIDEO = "AAGnjmk4AOWGexucDVhQxsS4"
PILOT_PRODUCT_ID = "1601939754004"


def image_key(url: str) -> str:
    name = Path(urlparse(url.replace("//", "https://", 1) if url.startswith("//") else url).path).name
    name = re.sub(r"_\d+x\d+\.jpg$", "", name, flags=re.I)
    return name.rsplit(".", 1)[0]


def load_bank_map(audit_dir: Path) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for path in sorted(audit_dir.glob("photobank_page*_500.json")):
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        for row in data.get("pagination_query_list", {}).get("list", []):
            result[image_key(str(row.get("url", "")))] = row
    return result


def load_video_map(audit_dir: Path) -> tuple[dict[str, str], str]:
    data = json.loads((audit_dir / "video_bank.json").read_text(encoding="utf-8-sig"))
    rows = data.get("result", {}).get("model", {}).get("list", [])
    by_bq: dict[str, str] = {}
    generic = GENERIC_FACTORY_VIDEO
    for row in rows:
        title = str(row.get("title", ""))
        match = re.match(r"BQ(\d{3}) Product and Factory Overview", title)
        if match and row.get("status") == "approved":
            by_bq[match.group(1)] = str(row["video_id"])
        if title.startswith("Footwear Production Process") and row.get("status") == "approved":
            generic = str(row["video_id"])
    return by_bq, generic


def bq_number(name: str, model: str) -> str | None:
    match = re.search(r"BQ[-_ ]?(\d{1,3})", f"{name} {model}", flags=re.I)
    return match.group(1).zfill(3) if match else None


def scimages_xml(urls: list[str], ids: list[str]) -> str:
    root = ET.Element("itemSchema")
    group = ET.SubElement(root, "field", {"id": "scImages", "type": "complex"})
    values = ET.SubElement(group, "complex-value")
    for index, (url, file_id) in enumerate(zip(urls, ids)):
        field = ET.SubElement(values, "field", {"id": f"scImages_{index}", "type": "input"})
        value = ET.SubElement(field, "value", {"fileId": str(file_id)})
        value.text = url.replace("https:", "").replace("http:", "")
    return ET.tostring(root, encoding="unicode", short_empty_elements=True)


def stable_snapshot(product: dict) -> dict:
    keys = [
        "subject", "category_id", "language", "product_type", "keywords",
        "attributes", "product_sku", "sourcing_trade", "struct_detail",
        "struct_detail_product", "price_type", "rts", "sub_market_type",
    ]
    return {key: deepcopy(product.get(key)) for key in keys}


def failed(response: dict) -> bool:
    return bool(api_error(response)) or response.get("biz_success") is False or response.get("model") is False


def response_refs(response: dict) -> dict:
    return {
        "request_id": response.get("request_id"),
        "trace_id": response.get("trace_id") or response.get("_trace_id_"),
        "message": response.get("message") or response.get("msg_info"),
        "error": api_error(response),
    }


def rebank_existing_image(config: dict, url: str, slot: int) -> tuple[dict, dict]:
    source_url = url if url.startswith("http") else "https:" + url
    suffix = Path(urlparse(source_url).path).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"
    with tempfile.TemporaryDirectory(prefix="beiqiang-rebank-") as tmp:
        downloaded = Path(tmp) / f"source_{slot}{suffix}"
        local = Path(tmp) / f"preserve_{slot}.jpg"
        request = Request(source_url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=60) as response:
            downloaded.write_bytes(response.read())
        with Image.open(downloaded) as image:
            # Transparent PNG/WebP files may contain arbitrary RGB data in fully
            # transparent pixels. Converting them straight to RGB reveals that
            # hidden data as streaks. Composite on white before saving JPEG.
            rgba = image.convert("RGBA")
            flattened = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            flattened.alpha_composite(rgba)
            flattened.convert("RGB").save(local, format="JPEG", quality=95, optimize=True)
        uploaded = upload_image(config, local, None)
    return uploaded, {"source_url": source_url, "source_key": image_key(source_url)}


def process_one(path: Path, config: dict, bank: dict[str, dict], videos: dict[str, str], generic: str) -> dict:
    product_id = path.name.split("_", 1)[0]
    record: dict = {"product_id": product_id, "file": str(path), "ok": False}
    before_response = top_call(config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
    if failed(before_response) or not before_response.get("product"):
        record["stage"] = "product_get_before"
        record["response"] = response_refs(before_response)
        return record
    before = before_response["product"]
    old_urls = list(before.get("main_image", {}).get("images", []))
    if len(old_urls) != 6:
        record.update(stage="gallery_precheck", error=f"Expected 6 images, got {len(old_urls)}")
        return record

    preserved_ids: list[str] = []
    preserved_urls: list[str] = []
    preserved_reuploads: list[dict] = []
    for slot, url in enumerate(old_urls[1:], start=2):
        row = bank.get(image_key(url))
        if row:
            preserved_ids.append(str(row["id"]))
            preserved_urls.append(str(row["url"]))
            continue
        rebank, source = rebank_existing_image(config, url, slot)
        if failed(rebank) or not rebank.get("upload_image_response"):
            record.update(stage="preserved_image_rebank", source=source, response=response_refs(rebank))
            return record
        item = rebank["upload_image_response"]
        preserved_ids.append(str(item["file_id"]))
        preserved_urls.append(str(item["photobank_url"]))
        preserved_reuploads.append({
            "slot": slot,
            **source,
            "file_id": str(item["file_id"]),
            "photobank_url": str(item["photobank_url"]),
            **response_refs(rebank),
        })

    upload = upload_image(config, path, None)
    if failed(upload) or not upload.get("upload_image_response"):
        record["stage"] = "upload_image"
        record["response"] = response_refs(upload)
        return record
    uploaded = upload["upload_image_response"]
    new_url = str(uploaded["photobank_url"])
    new_id = str(uploaded["file_id"])

    number = bq_number(path.name, str(before.get("subject", "")))
    selected_video = videos.get(number or "", generic)
    video_response = top_call(
        config,
        "alibaba.icbu.video.relation.product.main",
        {"product_id": before["product_id"], "video_id": selected_video},
    )
    if failed(video_response):
        record.update(
            stage="video_bind",
            upload={"file_id": new_id, "url": new_url, **response_refs(upload)},
            response=response_refs(video_response),
        )
        return record

    new_urls = [new_url, *preserved_urls]
    all_ids = [new_id, *preserved_ids]
    update_response = top_call(
        config,
        "alibaba.icbu.product.schema.update",
        {
            "param_product_top_publish_request": {
                "cat_id": int(before["category_id"]),
                "language": "en_US",
                "product_id": int(product_id),
                "xml": scimages_xml(new_urls, all_ids),
            }
        },
    )
    if failed(update_response):
        record.update(
            stage="schema_update",
            upload={"file_id": new_id, "url": new_url, **response_refs(upload)},
            video={"video_id": selected_video, **response_refs(video_response)},
            response=response_refs(update_response),
        )
        return record

    after_response = top_call(config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
    if failed(after_response) or not after_response.get("product"):
        record.update(stage="product_get_after", response=response_refs(after_response))
        return record
    after = after_response["product"]
    after_urls = list(after.get("main_image", {}).get("images", []))
    gallery_ok = (
        len(after_urls) == 6
        and image_key(after_urls[0]) == image_key(new_url)
        and [image_key(url) for url in after_urls[1:]] == [image_key(url) for url in preserved_urls]
    )
    fields_ok = stable_snapshot(before) == stable_snapshot(after)
    record.update(
        ok=gallery_ok and fields_ok,
        stage="verified" if gallery_ok and fields_ok else "readback_mismatch",
        model=number,
        encrypted_product_id=before.get("product_id"),
        title=before.get("subject"),
        before_status=before.get("status"),
        after_status=after.get("status"),
        before_display=before.get("display"),
        after_display=after.get("display"),
        old_images=old_urls,
        new_images=after_urls,
        preserved_m2_m6=gallery_ok,
        other_fields_unchanged=fields_ok,
        preserved_reuploads=preserved_reuploads,
        upload={"file_id": new_id, "url": new_url, **response_refs(upload)},
        video={"video_id": selected_video, **response_refs(video_response)},
        update=response_refs(update_response),
        readback=response_refs(after_response),
    )
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_dir", type=Path)
    parser.add_argument("audit_dir", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--include-pilot", action="store_true")
    parser.add_argument("--manifest-name", default="首图API替换执行记录_2026-09-03.json")
    args = parser.parse_args()

    candidates = sorted(path for path in args.candidate_dir.iterdir() if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if not args.include_pilot:
        candidates = [path for path in candidates if not path.name.startswith(PILOT_PRODUCT_ID + "_")]
    config = load_config(args.config)
    bank = load_bank_map(args.audit_dir)
    videos, generic = load_video_map(args.audit_dir)
    started = datetime.now(timezone.utc).isoformat()
    results: list[dict] = []
    print(f"Starting {len(candidates)} products with {args.workers} workers", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = {pool.submit(process_one, path, config, bank, videos, generic): path for path in candidates}
        for job in as_completed(jobs):
            try:
                result = job.result()
            except Exception as exc:  # preserve batch progress if one request fails
                result = {"product_id": jobs[job].name.split("_", 1)[0], "file": str(jobs[job]), "ok": False, "stage": "exception", "error": str(exc)}
            results.append(result)
            print(f"[{len(results)}/{len(candidates)}] {result['product_id']} {result['stage']} ok={result['ok']}", flush=True)

    results.sort(key=lambda row: row["product_id"])
    manifest = {
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(candidates),
        "success_count": sum(bool(row.get("ok")) for row in results),
        "failure_count": sum(not bool(row.get("ok")) for row in results),
        "results": results,
    }
    output = args.audit_dir / args.manifest_name
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Manifest: {output}", flush=True)
    return 0 if manifest["failure_count"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
