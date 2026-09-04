#!/usr/bin/env python3
"""Replace complete six-image Alibaba galleries from a JSON plan.

Each local file is uploaded to the official image bank first. The script then
updates only the Schema `scImages` group and verifies the six returned URLs.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from alibaba_openapi import DEFAULT_CONFIG, api_error, load_config, top_call, upload_image
from batch_replace_hero import GENERIC_FACTORY_VIDEO, bq_number, failed, load_video_map, response_refs, scimages_xml, image_key


def process_one(row: dict, config: dict, videos: dict[str, str], generic: str) -> dict:
    product_id = str(row["product_id"])
    files = [Path(value) for value in row["images"]]
    record: dict = {"product_id": product_id, "files": [str(path) for path in files], "ok": False}
    if len(files) != 6 or any(not path.is_file() for path in files):
        record.update(stage="plan_validation", error="Plan must contain six existing local files")
        return record

    before_response = top_call(config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
    if failed(before_response) or not before_response.get("product"):
        record.update(stage="product_get_before", response=response_refs(before_response))
        return record
    before = before_response["product"]

    uploaded_rows: list[dict] = []
    for slot, path in enumerate(files, start=1):
        upload = upload_image(config, path, None)
        if failed(upload) or not upload.get("upload_image_response"):
            record.update(stage="upload_image", failed_slot=slot, uploaded=uploaded_rows, response=response_refs(upload))
            return record
        item = upload["upload_image_response"]
        uploaded_rows.append({
            "slot": slot,
            "file": str(path),
            "file_id": str(item["file_id"]),
            "url": str(item["photobank_url"]),
            **response_refs(upload),
        })

    number = bq_number(str(before.get("subject", "")), str(before.get("subject", "")))
    selected_video = str(row.get("video_id") or videos.get(number or "", generic))
    video_response = top_call(
        config,
        "alibaba.icbu.video.relation.product.main",
        {"product_id": before["product_id"], "video_id": selected_video},
    )
    if failed(video_response):
        record.update(stage="video_bind", uploaded=uploaded_rows, response=response_refs(video_response))
        return record

    urls = [row["url"] for row in uploaded_rows]
    ids = [row["file_id"] for row in uploaded_rows]
    update_response = top_call(
        config,
        "alibaba.icbu.product.schema.update",
        {
            "param_product_top_publish_request": {
                "cat_id": int(before["category_id"]),
                "language": "en_US",
                "product_id": int(product_id),
                "xml": scimages_xml(urls, ids),
            }
        },
    )
    if failed(update_response):
        record.update(stage="schema_update", uploaded=uploaded_rows, video=response_refs(video_response), response=response_refs(update_response))
        return record

    after_response = top_call(config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
    if failed(after_response) or not after_response.get("product"):
        record.update(stage="product_get_after", response=response_refs(after_response))
        return record
    after = after_response["product"]
    returned = list((after.get("main_image") or {}).get("images") or [])
    verified = len(returned) == 6 and [image_key(url) for url in returned] == [image_key(url) for url in urls]
    record.update(
        ok=verified,
        stage="verified" if verified else "readback_mismatch",
        title=before.get("subject"),
        before_status=before.get("status"),
        after_status=after.get("status"),
        before_display=before.get("display"),
        after_display=after.get("display"),
        before_images=list((before.get("main_image") or {}).get("images") or []),
        after_images=returned,
        uploaded=uploaded_rows,
        video={"video_id": selected_video, **response_refs(video_response)},
        update=response_refs(update_response),
        readback=response_refs(after_response),
    )
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("video_audit_dir", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8-sig"))
    rows = plan["products"] if isinstance(plan, dict) else plan
    config = load_config(args.config)
    videos, generic = load_video_map(args.video_audit_dir)
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = {pool.submit(process_one, row, config, videos, generic): row for row in rows}
        for job in as_completed(jobs):
            try:
                result = job.result()
            except Exception as exc:
                result = {"product_id": str(jobs[job].get("product_id")), "ok": False, "stage": "exception", "error": str(exc)}
            results.append(result)
            print(f"{result['product_id']} {result['stage']} ok={result['ok']}", flush=True)

    results.sort(key=lambda value: value["product_id"])
    manifest = {
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "product_count": len(results),
        "success_count": sum(bool(row.get("ok")) for row in results),
        "failure_count": sum(not bool(row.get("ok")) for row in results),
        "results": results,
    }
    output = args.manifest or args.plan.with_name(args.plan.stem + "_result.json")
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Manifest: {output}", flush=True)
    return 0 if manifest["failure_count"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
