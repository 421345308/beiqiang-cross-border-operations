#!/usr/bin/env python3
"""Update one Alibaba product title and M1 in a single Schema submission.

The JSON plan must provide product_id, expected_model, title and hero_file.
M2-M6 and all non-target business fields are preserved and verified by readback.
Protected product IDs are refused even if they appear in a plan.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT_DIR = ROOT / ".agents/skills/alibaba-openapi-operator/scripts"
sys.path.insert(0, str(CLIENT_DIR))

from alibaba_openapi import DEFAULT_CONFIG, api_error, load_config, top_call, upload_image  # noqa: E402
from batch_replace_hero import (  # noqa: E402
    failed,
    image_key,
    load_bank_map,
    load_video_map,
    rebank_existing_image,
    response_refs,
    scimages_xml,
)


PROTECTED_PRODUCT_IDS = {"1601825074604", "1601825021825", "1601815020244", "1601814931739", "10000044041008", "10000043991998", "1601839073314", "1601838963947", "10000042821848", "10000044004948", "10000044024484", "10000044041031", "10000043744505", "10000044028277", "10000044007878", "10000046439033", "10000043732626", "1601839105416", "1601825070472", "10000043201799", "1601825160204", "1601839062659", "1601839050756", "10000046653813", "10000044011929", "10000044021584", "10000044034049", "10000042896165", "10000043200726", "10000043725883"}


def model_number(product: dict) -> str:
    for row in product.get("attributes") or []:
        if row.get("attribute_name") == "Model Number":
            return str(row.get("value_name") or "")
    return ""


def stable_snapshot(product: dict) -> dict:
    # Alibaba regenerates the public URL slug from the title after an update.
    # That derived URL is expected to change and is not an unintended field mutation.
    excluded = {"subject", "main_image", "gmt_modified", "status", "display", "pc_detail_url"}
    def normalize(value):
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in sorted(value.items())}
        if isinstance(value, list):
            items = [normalize(item) for item in value]
            return sorted(items, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
        return value

    return normalize({key: deepcopy(value) for key, value in product.items() if key not in excluded})


def diff_paths(before, after, path: str = "$", limit: int = 50) -> list[str]:
    differences: list[str] = []

    def walk(left, right, current: str):
        if len(differences) >= limit:
            return
        if type(left) is not type(right):
            differences.append(f"{current}: type {type(left).__name__} -> {type(right).__name__}")
            return
        if isinstance(left, dict):
            for key in sorted(set(left) | set(right)):
                child = f"{current}.{key}"
                if key not in left:
                    differences.append(f"{child}: added")
                elif key not in right:
                    differences.append(f"{child}: removed")
                else:
                    walk(left[key], right[key], child)
            return
        if isinstance(left, list):
            if len(left) != len(right):
                differences.append(f"{current}: length {len(left)} -> {len(right)}")
                return
            for index, (left_item, right_item) in enumerate(zip(left, right)):
                walk(left_item, right_item, f"{current}[{index}]")
            return
        if left != right:
            differences.append(f"{current}: {left!r} -> {right!r}")

    walk(before, after, path)
    return differences


def title_and_images_xml(title: str, urls: list[str], ids: list[str]) -> str:
    root = ET.fromstring(scimages_xml(urls, ids))
    field = ET.Element("field", {"id": "productTitle", "type": "input"})
    ET.SubElement(field, "value").text = title
    root.insert(0, field)
    return ET.tostring(root, encoding="unicode", short_empty_elements=True)


def process_one(row: dict, config: dict, bank: dict[str, dict], videos: dict[str, str], generic_video: str) -> dict:
    product_id = str(row["product_id"])
    record: dict = {"product_id": product_id, "ok": False}
    if product_id in PROTECTED_PRODUCT_IDS:
        record.update(stage="protected_product_refusal", error="Product is protected from write operations")
        return record

    title = str(row["title"]).strip()
    hero = Path(row["hero_file"])
    expected_model = str(row["expected_model"]).strip()
    if not 1 <= len(title) <= 128 or not hero.is_file():
        record.update(stage="plan_validation", error="Title must be 1-128 characters and hero_file must exist")
        return record

    before_response = top_call(config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
    if failed(before_response) or not before_response.get("product"):
        record.update(stage="product_get_before", response=response_refs(before_response))
        return record
    before = before_response["product"]
    actual_model = model_number(before)
    if actual_model != expected_model:
        record.update(stage="identity_check", expected_model=expected_model, actual_model=actual_model)
        return record
    old_urls = list((before.get("main_image") or {}).get("images") or [])
    if len(old_urls) != 6:
        record.update(stage="gallery_precheck", error=f"Expected 6 images, got {len(old_urls)}")
        return record

    # A submitted edit is temporarily returned as modified / display=N.  Do not
    # upload another hero, rebind video, or call schema.update while Alibaba is
    # reviewing that edit.  The caller must poll and verify the accepted state
    # instead of turning an uncertain/slow run into a duplicate submission.
    if before.get("status") == "modified" or before.get("display") == "N":
        record.update(
            stage="auditing_no_resubmit",
            error="Product is under review; poll/read back instead of resubmitting",
            expected_model=expected_model,
            current_title=before.get("subject"),
            current_hero=old_urls[0],
            current_status=before.get("status"),
            current_display=before.get("display"),
        )
        return record

    hero_upload_response = upload_image(config, hero, None)
    hero_upload = hero_upload_response.get("upload_image_response") or {}
    if failed(hero_upload_response) or not hero_upload:
        record.update(stage="hero_upload", response=response_refs(hero_upload_response))
        return record
    hero_url = str(hero_upload["photobank_url"])
    hero_id = str(hero_upload["file_id"])

    # If the selected hero is already one of M2-M6, Alibaba de-duplicates the
    # gallery. Keep the displaced old M1 as M2 and remove only the matching old
    # slot so the listing still has six unique images after the reorder.
    hero_key = image_key(hero_url)
    old_secondary_urls = old_urls[1:]
    if any(image_key(url) == hero_key for url in old_secondary_urls):
        preserve_source_urls = [
            old_urls[0],
            *[url for url in old_secondary_urls if image_key(url) != hero_key],
        ]
    else:
        preserve_source_urls = old_secondary_urls

    preserved_ids: list[str] = []
    preserved_urls: list[str] = []
    preserved_reuploads: list[dict] = []
    for slot, url in enumerate(preserve_source_urls, start=2):
        item = bank.get(image_key(url))
        if item:
            preserved_ids.append(str(item["id"]))
            preserved_urls.append(str(item["url"]))
            continue
        upload_response, source = rebank_existing_image(config, url, slot)
        uploaded = upload_response.get("upload_image_response") or {}
        if failed(upload_response) or not uploaded:
            record.update(stage="preserved_image_rebank", source=source, response=response_refs(upload_response))
            return record
        preserved_ids.append(str(uploaded["file_id"]))
        preserved_urls.append(str(uploaded["photobank_url"]))
        preserved_reuploads.append({"slot": slot, **source, "file_id": str(uploaded["file_id"]), "url": str(uploaded["photobank_url"]), **response_refs(upload_response)})

    bq_match = re.search(r"BQ[-_ ]?(\d{1,3})", expected_model, flags=re.I)
    bq_number = bq_match.group(1).zfill(3) if bq_match else ""
    selected_video = str(row.get("video_id") or videos.get(bq_number, generic_video))
    video_response = top_call(config, "alibaba.icbu.video.relation.product.main", {"product_id": before["product_id"], "video_id": selected_video})
    if failed(video_response):
        record.update(stage="video_bind", response=response_refs(video_response))
        return record

    new_urls = [hero_url, *preserved_urls]
    new_ids = [hero_id, *preserved_ids]
    update_response = top_call(config, "alibaba.icbu.product.schema.update", {
        "param_product_top_publish_request": {
            "cat_id": int(before["category_id"]),
            "language": "en_US",
            "product_id": int(product_id),
            "xml": title_and_images_xml(title, new_urls, new_ids),
        }
    })
    if failed(update_response):
        record.update(stage="schema_update", response=response_refs(update_response))
        return record

    after_response = top_call(config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
    if failed(after_response) or not after_response.get("product"):
        record.update(stage="product_get_after", response=response_refs(after_response))
        return record
    after = after_response["product"]
    returned_urls = list((after.get("main_image") or {}).get("images") or [])
    before_snapshot = stable_snapshot(before)
    after_snapshot = stable_snapshot(after)
    snapshot_differences = diff_paths(before_snapshot, after_snapshot)
    checks = {
        "identity_ok": model_number(after) == expected_model,
        "title_ok": after.get("subject") == title,
        "hero_ok": bool(returned_urls) and image_key(returned_urls[0]) == image_key(hero_url),
        "m2_m6_ok": len(returned_urls) == 6 and [image_key(url) for url in returned_urls[1:]] == [image_key(url) for url in preserved_urls],
        "other_fields_unchanged": before_snapshot == after_snapshot,
        "source_not_targeted": product_id not in PROTECTED_PRODUCT_IDS,
    }
    ok = all(checks.values())
    record.update(
        ok=ok,
        stage="verified" if ok else "readback_mismatch",
        expected_model=expected_model,
        old_title=before.get("subject"),
        new_title=after.get("subject"),
        old_images=old_urls,
        new_images=returned_urls,
        before_status=before.get("status"),
        after_status=after.get("status"),
        before_display=before.get("display"),
        after_display=after.get("display"),
        checks=checks,
        snapshot_diff_paths=snapshot_differences,
        preserved_reuploads=preserved_reuploads,
        hero_upload={"file": str(hero), "file_id": hero_id, "url": hero_url, **response_refs(hero_upload_response)},
        video={"video_id": selected_video, **response_refs(video_response)},
        update=response_refs(update_response),
        readback=response_refs(after_response),
    )
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("audit_dir", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8-sig"))
    rows = plan["products"] if isinstance(plan, dict) else plan
    config = load_config(args.config)
    bank = load_bank_map(args.audit_dir)
    videos, generic_video = load_video_map(args.audit_dir)
    results = [process_one(row, config, bank, videos, generic_video) for row in rows]
    manifest = {
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "success_count": sum(bool(row.get("ok")) for row in results),
        "failure_count": sum(not bool(row.get("ok")) for row in results),
        "protected_product_ids": sorted(PROTECTED_PRODUCT_IDS),
        "results": results,
    }
    output = args.manifest or args.plan.with_name(args.plan.stem + "_result.json")
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(output), "success_count": manifest["success_count"], "failure_count": manifest["failure_count"], "stages": {row["product_id"]: row["stage"] for row in results}}, ensure_ascii=False))
    return 0 if manifest["failure_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
