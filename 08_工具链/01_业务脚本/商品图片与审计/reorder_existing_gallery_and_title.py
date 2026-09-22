#!/usr/bin/env python3
"""Reorder an existing Alibaba six-image gallery and update its title safely.

The plan must contain official image-bank URLs and their existing file IDs. No
image is uploaded. Default mode is read-only preflight; --apply submits one
minimal Schema update and verifies title, image order and every non-target field.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
import time


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT_DIR = ROOT / ".agents/skills/alibaba-openapi-operator/scripts"
SCRIPT_DIR = ROOT / "08_工具链/01_业务脚本/商品图片与审计"
sys.path.insert(0, str(CLIENT_DIR))
sys.path.insert(0, str(SCRIPT_DIR))

from alibaba_openapi import DEFAULT_CONFIG, api_error, load_config, top_call as raw_top_call  # noqa: E402
from batch_replace_hero import failed, image_key, response_refs, scimages_xml  # noqa: E402


PROTECTED_PRODUCT_IDS = {
    "10000042821848", "10000042896165", "10000043200726", "10000043201799",
    "10000043725883", "10000043732626", "10000043744505", "10000043991998",
    "10000044004948", "10000044007878", "10000044011929", "10000044021584",
    "10000044024484", "10000044028277", "10000044034049", "10000044041008",
    "10000044041031", "10000046439033", "10000046653813", "1601814931739",
    "1601815020244", "1601825021825", "1601825070472", "1601825074604",
    "1601825160204", "1601838963947", "1601839050756", "1601839062659",
    "1601839073314", "1601839105416",
}


def top_call(config: dict, method: str, params: dict) -> dict:
    response: dict = {}
    for attempt in range(4):
        response = raw_top_call(config, method, params)
        error = response.get("error_response") or response.get("error") or {}
        if str(error.get("code") or "") != "ApiCallLimit":
            return response
        if attempt < 3:
            time.sleep(1.5 * (attempt + 1))
    return response


def model_number(product: dict) -> str:
    for row in product.get("attributes") or []:
        if row.get("attribute_name") == "Model Number":
            return str(row.get("value_name") or "")
    return ""


def normalized_snapshot(product: dict) -> dict:
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

    def walk(left, right, current: str) -> None:
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
    import xml.etree.ElementTree as ET

    root = ET.fromstring(scimages_xml(urls, ids))
    title_field = ET.Element("field", {"id": "productTitle", "type": "input"})
    ET.SubElement(title_field, "value").text = title
    root.insert(0, title_field)
    return ET.tostring(root, encoding="unicode", short_empty_elements=True)


def process(row: dict, config: dict, apply: bool) -> dict:
    product_id = str(row.get("product_id") or "").strip()
    expected_model = str(row.get("expected_model") or "").strip()
    expected_title = " ".join(str(row.get("expected_current_title") or "").split())
    new_title = " ".join(str(row.get("title") or "").split())
    images = row.get("images") or []
    result = {"product_id": product_id, "mode": "apply" if apply else "preflight", "ok": False}

    if product_id in PROTECTED_PRODUCT_IDS:
        result.update(stage="protected_source_refusal", error="Product ID is a protected source")
        return result
    if not product_id.isdigit() or not expected_model or not 1 <= len(new_title) <= 128 or len(images) != 6:
        result.update(stage="plan_validation", error="Invalid identity, title or six-image plan")
        return result
    urls = [str(item.get("url") or "") for item in images]
    file_ids = [str(item.get("file_id") or "") for item in images]
    if any(not url.startswith("https://sc04.alicdn.com/kf/") or not file_id.isdigit() for url, file_id in zip(urls, file_ids)):
        result.update(stage="plan_validation", error="Every image needs an official Alibaba CDN URL and numeric file ID")
        return result
    target_keys = [image_key(url) for url in urls]
    if len(set(target_keys)) != 6:
        result.update(stage="plan_validation", error="Target gallery is not six unique images")
        return result

    before_response = top_call(config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
    before = before_response.get("product") or {}
    if failed(before_response) or not before:
        result.update(stage="product_get_before", response=response_refs(before_response))
        return result
    current_urls = list((before.get("main_image") or {}).get("images") or [])
    current_keys = [image_key(url) for url in current_urls]
    checks = {
        "identity_ok": model_number(before) == expected_model,
        "approved_and_live": before.get("status") == "approved" and before.get("display") == "Y",
        "title_baseline_ok": not expected_title or before.get("subject") == expected_title,
        "six_current_images": len(current_urls) == 6,
        "same_image_set": sorted(current_keys) == sorted(target_keys),
        "new_hero_differs": bool(current_keys) and current_keys[0] == str(row.get("expected_current_hero_key") or current_keys[0]) and target_keys[0] != current_keys[0],
    }
    result.update(
        stage="preflight_pass" if all(checks.values()) else "preflight_mismatch",
        ok=all(checks.values()),
        expected_model=expected_model,
        old_title=before.get("subject"),
        new_title=new_title,
        title_length=len(new_title),
        before_status=before.get("status"),
        before_display=before.get("display"),
        current_images=current_urls,
        target_images=urls,
        target_file_ids=file_ids,
        checks=checks,
        read_before=response_refs(before_response),
    )
    if not result["ok"] or not apply:
        return result

    update_response = top_call(config, "alibaba.icbu.product.schema.update", {
        "param_product_top_publish_request": {
            "cat_id": int(before["category_id"]),
            "language": "en_US",
            "product_id": int(product_id),
            "xml": title_and_images_xml(new_title, urls, file_ids),
        }
    })
    if api_error(update_response) or update_response.get("biz_success") is False or update_response.get("model") is False:
        result.update(ok=False, stage="schema_update", update=response_refs(update_response))
        return result

    after_response = top_call(config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
    after = after_response.get("product") or {}
    if failed(after_response) or not after:
        result.update(ok=False, stage="product_get_after", update=response_refs(update_response), read_after=response_refs(after_response))
        return result
    returned_urls = list((after.get("main_image") or {}).get("images") or [])
    differences = diff_paths(normalized_snapshot(before), normalized_snapshot(after))
    final_checks = {
        "title_ok": after.get("subject") == new_title,
        "model_ok": model_number(after) == expected_model,
        "gallery_order_ok": [image_key(url) for url in returned_urls] == target_keys,
        "sku_count_unchanged": len((after.get("product_sku") or {}).get("skus") or []) == len((before.get("product_sku") or {}).get("skus") or []),
        "non_target_fields_unchanged": not differences,
        "source_not_targeted": product_id not in PROTECTED_PRODUCT_IDS,
    }
    result.update(
        ok=all(final_checks.values()),
        stage="verified" if all(final_checks.values()) else "readback_mismatch",
        after_title=after.get("subject"),
        after_status=after.get("status"),
        after_display=after.get("display"),
        after_images=returned_urls,
        after_sku_count=len((after.get("product_sku") or {}).get("skus") or []),
        final_checks=final_checks,
        snapshot_diff_paths=differences,
        update=response_refs(update_response),
        read_after=response_refs(after_response),
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8-sig"))
    rows = plan.get("products") if isinstance(plan, dict) else plan
    config = load_config(args.config)
    results = [process(row, config, args.apply) for row in rows]
    payload = {
        "mode": "apply" if args.apply else "preflight",
        "success_count": sum(bool(row.get("ok")) for row in results),
        "failure_count": sum(not bool(row.get("ok")) for row in results),
        "protected_source_count": len(PROTECTED_PRODUCT_IDS),
        "results": results,
    }
    if args.output:
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"success_count": payload["success_count"], "failure_count": payload["failure_count"], "stages": {row["product_id"]: row["stage"] for row in results}, "output": str(args.output or "")}, ensure_ascii=False))
    return 0 if payload["failure_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
