#!/usr/bin/env python3
"""Update one Alibaba product title and complete six-image gallery safely.

The plan supplies product_id, expected_model, title and exactly six local image
files. The script refuses protected source links, products under review and combined
keyword writes. Alibaba accepted but ignored productKeywords when bundled with
title/gallery on 2026-09-14, so keywords must use a separately verified workflow.
The script uploads all six reviewed files and verifies every non-target field by
immediate OpenAPI readback.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import time
import xml.etree.ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT_DIR = ROOT / ".agents/skills/alibaba-openapi-operator/scripts"
sys.path.insert(0, str(CLIENT_DIR))

from alibaba_openapi import DEFAULT_CONFIG, load_config, top_call as raw_top_call, upload_image  # noqa: E402
from batch_replace_hero import (  # noqa: E402
    failed,
    image_key,
    load_video_map,
    response_refs,
    scimages_xml,
)


PROTECTED_PRODUCT_IDS = {
    "1601825074604", "1601825021825", "1601815020244", "1601814931739",
    "10000044041008", "10000043991998", "1601839073314", "1601838963947",
    "10000042821848", "10000044004948", "10000044024484", "10000044041031",
    "10000043744505", "10000044028277", "10000044007878", "10000046439033",
    "10000043732626",
    "1601839105416", "1601825070472", "10000043201799", "1601825160204", "1601839062659", "1601839050756", "10000046653813", "10000044011929", "10000044021584", "10000044034049", "10000042896165", "10000043200726", "10000043725883",
}


def top_call(config: dict, method: str, params: dict) -> dict:
    """Retry only Alibaba's explicit one-second access throttle."""
    response: dict = {}
    for attempt in range(3):
        response = raw_top_call(config, method, params)
        error = response.get("error_response") or response.get("error") or {}
        if str(error.get("code") or "") != "ApiCallLimit":
            return response
        if attempt < 2:
            time.sleep(1.5)
    return response


def model_number(product: dict) -> str:
    for row in product.get("attributes") or []:
        if row.get("attribute_name") == "Model Number":
            return str(row.get("value_name") or "")
    return ""


def stable_snapshot(product: dict, keywords_targeted: bool = False, model_targeted: bool = False) -> dict:
    excluded = {"subject", "main_image", "gmt_modified", "status", "display", "pc_detail_url"}
    if keywords_targeted:
        excluded.add("keywords")

    def normalize(value):
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in sorted(value.items())}
        if isinstance(value, list):
            items = [normalize(item) for item in value]
            return sorted(items, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
        return value

    snapshot = {key: deepcopy(value) for key, value in product.items() if key not in excluded}
    if model_targeted:
        snapshot["attributes"] = [
            row for row in snapshot.get("attributes") or []
            if int(row.get("attribute_id") or 0) != 3
        ]
    return normalize(snapshot)


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


def normalized_keywords(value) -> list[str]:
    if isinstance(value, list):
        parts = [str(item) for item in value]
    else:
        parts = str(value or "").splitlines()
    return [" ".join(part.split()).lower() for part in parts if part.strip()]


def title_keywords_model_and_images_xml(
    title: str,
    keywords: list[str],
    new_model: str,
    rendered_model_field: ET.Element | None,
    urls: list[str],
    ids: list[str],
) -> str:
    root = ET.fromstring(scimages_xml(urls, ids))
    field = ET.Element("field", {"id": "productTitle", "type": "input"})
    ET.SubElement(field, "value").text = title
    root.insert(0, field)
    if keywords:
        keyword_field = ET.Element("field", {"id": "productKeywords", "name": "Product keywords ", "type": "complex"})
        complex_value = ET.SubElement(keyword_field, "complex-value")
        keyword_input = ET.SubElement(complex_value, "field", {"id": "productKeywords_0", "name": "Product keywords ", "type": "input"})
        ET.SubElement(keyword_input, "value").text = "\n".join(keywords)
        root.insert(1, keyword_field)
    if new_model:
        if rendered_model_field is None:
            raise RuntimeError("Rendered Schema lacks Model Number field")
        model_field = deepcopy(rendered_model_field)
        value = model_field.find("./value")
        if value is None:
            raise RuntimeError("Rendered Model Number field lacks value node")
        value.attrib["inputValue"] = new_model
        category_properties = ET.Element("field", {"id": "icbuCatProp", "name": "Product feature", "type": "complex"})
        complex_value = ET.SubElement(category_properties, "complex-value")
        complex_value.append(model_field)
        root.insert(1, category_properties)
    return ET.tostring(root, encoding="unicode", short_empty_elements=True)


def process_one(row: dict, config: dict, videos: dict[str, str], generic_video: str, execute: bool) -> dict:
    product_id = str(row["product_id"])
    title = str(row["title"]).strip()
    expected_model = str(row["expected_model"]).strip()
    new_model = str(row.get("new_model") or "").strip()
    keywords = [" ".join(str(value).split()) for value in (row.get("keywords") or []) if str(value).strip()]
    files = [Path(value) for value in row.get("image_files") or []]
    record: dict = {"product_id": product_id, "ok": False, "execute": execute}

    if product_id in PROTECTED_PRODUCT_IDS:
        record.update(stage="protected_product_refusal", error="Product is protected from write operations")
        return record
    if keywords:
        record.update(stage="combined_keywords_refusal", error="Combined productKeywords writes are platform-ignored; use a separate verified keyword workflow")
        return record
    if new_model and not 1 <= len(new_model) <= 128:
        record.update(stage="plan_validation", error="new_model must be 1-128 characters")
        return record
    if not 1 <= len(title) <= 128 or len(files) != 6 or not all(path.is_file() for path in files):
        record.update(stage="plan_validation", error="Title must be 1-128 characters and exactly six image files must exist")
        return record
    if keywords and (
        not 3 <= len(keywords) <= 5
        or len({value.lower() for value in keywords}) != len(keywords)
        or any(not 2 <= len(value) <= 128 for value in keywords)
    ):
        record.update(stage="plan_validation", error="Keywords must contain 3-5 unique non-empty phrases of 2-128 characters")
        return record

    before_response = top_call(config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
    if failed(before_response) or not before_response.get("product"):
        record.update(stage="product_get_before", response=response_refs(before_response))
        return record
    before = before_response["product"]
    old_urls = list((before.get("main_image") or {}).get("images") or [])
    if model_number(before) != expected_model:
        record.update(stage="identity_check", expected_model=expected_model, actual_model=model_number(before))
        return record
    if len(old_urls) != 6:
        record.update(stage="gallery_precheck", error=f"Expected 6 existing images, got {len(old_urls)}")
        return record
    if before.get("status") == "modified" or before.get("display") == "N":
        record.update(stage="auditing_no_resubmit", error="Product is under review; poll instead of resubmitting")
        return record

    rendered_model_field = None
    render_refs = None
    if new_model:
        render_response = top_call(config, "alibaba.icbu.product.schema.render", {
            "param_product_top_publish_request": {"product_id": int(product_id), "language": "en_US"}
        })
        data = render_response.get("data")
        if failed(render_response) or not isinstance(data, str):
            record.update(stage="schema_render", response=response_refs(render_response))
            return record
        rendered = ET.fromstring(data)
        rendered_model_field = rendered.find(".//field[@id='p-3']")
        rendered_value = rendered_model_field.find("./value") if rendered_model_field is not None else None
        if rendered_value is None or str(rendered_value.attrib.get("inputValue") or "") != expected_model:
            record.update(stage="rendered_model_identity", actual_model=(rendered_value.attrib.get("inputValue") if rendered_value is not None else None))
            return record
        render_refs = response_refs(render_response)

    record.update(
        stage="preflight_pass",
        ok=True,
        expected_model=expected_model,
        new_model=new_model or expected_model,
        old_title=before.get("subject"),
        new_title=title,
        old_keywords=before.get("keywords"),
        new_keywords=keywords,
        old_images=old_urls,
        image_files=[str(path) for path in files],
        before_status=before.get("status"),
        before_display=before.get("display"),
        request=response_refs(before_response),
        schema_render=render_refs,
    )
    if not execute:
        return record

    uploads: list[dict] = []
    urls: list[str] = []
    ids: list[str] = []
    for slot, path in enumerate(files, start=1):
        response = upload_image(config, path, None)
        uploaded = response.get("upload_image_response") or {}
        if failed(response) or not uploaded:
            record.update(ok=False, stage=f"image_upload_m{slot}", response=response_refs(response), uploads=uploads)
            return record
        url = str(uploaded["photobank_url"])
        file_id = str(uploaded["file_id"])
        urls.append(url)
        ids.append(file_id)
        uploads.append({"slot": slot, "file": str(path), "file_id": file_id, "url": url, **response_refs(response)})

    if len({image_key(url) for url in urls}) != 6:
        record.update(ok=False, stage="uploaded_gallery_deduplication", uploads=uploads)
        return record

    bq_match = re.search(r"BQ[-_ ]?(\d{1,3})", expected_model, flags=re.I)
    bq_number = bq_match.group(1).zfill(3) if bq_match else ""
    selected_video = str(row.get("video_id") or videos.get(bq_number, generic_video))
    video_response = top_call(config, "alibaba.icbu.video.relation.product.main", {"product_id": before["product_id"], "video_id": selected_video})
    if failed(video_response):
        record.update(ok=False, stage="video_bind", uploads=uploads, response=response_refs(video_response))
        return record

    update_response = top_call(config, "alibaba.icbu.product.schema.update", {
        "param_product_top_publish_request": {
            "cat_id": int(before["category_id"]),
            "language": "en_US",
            "product_id": int(product_id),
            "xml": title_keywords_model_and_images_xml(title, keywords, new_model, rendered_model_field, urls, ids),
        }
    })
    if failed(update_response):
        record.update(ok=False, stage="schema_update", uploads=uploads, response=response_refs(update_response))
        return record

    after_response = top_call(config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
    if failed(after_response) or not after_response.get("product"):
        record.update(ok=False, stage="product_get_after", uploads=uploads, response=response_refs(after_response))
        return record
    after = after_response["product"]
    returned_urls = list((after.get("main_image") or {}).get("images") or [])
    snapshot_differences = diff_paths(
        stable_snapshot(before, keywords_targeted=bool(keywords), model_targeted=bool(new_model)),
        stable_snapshot(after, keywords_targeted=bool(keywords), model_targeted=bool(new_model)),
    )
    checks = {
        "identity_ok": model_number(after) == (new_model or expected_model),
        "title_ok": after.get("subject") == title,
        "keywords_ok": not keywords or normalized_keywords(after.get("keywords")) == normalized_keywords(keywords),
        "gallery_ok": len(returned_urls) == 6 and [image_key(url) for url in returned_urls] == [image_key(url) for url in urls],
        "other_fields_unchanged": not snapshot_differences,
        "source_not_targeted": product_id not in PROTECTED_PRODUCT_IDS,
    }
    ok = all(checks.values())
    record.update(
        ok=ok,
        stage="verified" if ok else "readback_mismatch",
        uploads=uploads,
        new_images=returned_urls,
        after_title=after.get("subject"),
        after_keywords=after.get("keywords"),
        after_status=after.get("status"),
        after_display=after.get("display"),
        checks=checks,
        snapshot_diff_paths=snapshot_differences,
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
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8-sig"))
    rows = plan["products"] if isinstance(plan, dict) else plan
    config = load_config(args.config)
    videos, generic_video = load_video_map(args.audit_dir)
    results = []
    for index, row in enumerate(rows):
        if index:
            # Alibaba may apply a one-second read throttle even during preflight.
            # Keep batch runs deterministic instead of turning valid rows into
            # false failures that require a manual rerun.
            time.sleep(1.2)
        results.append(process_one(row, config, videos, generic_video, args.execute))
    manifest = {
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "mode": "execute" if args.execute else "preflight",
        "success_count": sum(bool(row.get("ok")) for row in results),
        "failure_count": sum(not bool(row.get("ok")) for row in results),
        "protected_product_ids": sorted(PROTECTED_PRODUCT_IDS),
        "results": results,
    }
    output = args.manifest or args.plan.with_name(args.plan.stem + ("_result.json" if args.execute else "_preflight.json"))
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(output), "mode": manifest["mode"], "success_count": manifest["success_count"], "failure_count": manifest["failure_count"], "stages": {row["product_id"]: row["stage"] for row in results}}, ensure_ascii=False))
    return 0 if manifest["failure_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
