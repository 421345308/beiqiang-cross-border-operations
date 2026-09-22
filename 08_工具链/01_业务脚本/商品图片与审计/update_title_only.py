#!/usr/bin/env python3
"""Safely update Alibaba product titles without touching images or other fields.

The JSON plan contains product_id, expected_model and title. Source products are
hard-blocked. By default this performs a read-only preflight; --execute submits a
minimal productTitle schema update and immediately verifies all protected fields.
Results are printed to stdout so callers can persist reviewed receipts explicitly.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
import time
import xml.etree.ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT_DIR = ROOT / ".agents/skills/alibaba-openapi-operator/scripts"
sys.path.insert(0, str(CLIENT_DIR))

from alibaba_openapi import DEFAULT_CONFIG, api_error, load_config, top_call as raw_top_call  # noqa: E402


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
    last_exception: Exception | None = None
    for attempt in range(4):
        try:
            response = raw_top_call(config, method, params)
            last_exception = None
        except Exception as exc:
            last_exception = exc
            if attempt < 3:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
        error = response.get("error_response") or response.get("error") or {}
        if str(error.get("code") or "") != "ApiCallLimit":
            return response
        if attempt < 3:
            time.sleep(1.5 * (attempt + 1))
    if last_exception is not None:
        raise last_exception
    return response


def failed(response: dict) -> bool:
    return bool(api_error(response)) or response.get("biz_success") is False or response.get("model") is False


def refs(response: dict) -> dict:
    return {
        "request_id": response.get("request_id"),
        "trace_id": response.get("trace_id") or response.get("_trace_id_"),
        "error": api_error(response),
    }


def model_number(product: dict) -> str:
    for row in product.get("attributes") or []:
        if row.get("attribute_name") == "Model Number":
            return str(row.get("value_name") or "")
    return ""


def image_keys(product: dict) -> list[str]:
    return [str(value).split("?")[0] for value in ((product.get("main_image") or {}).get("images") or [])]


def stable_snapshot(product: dict) -> dict:
    excluded = {"subject", "gmt_modified", "status", "display", "pc_detail_url"}

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


def title_xml(title: str) -> str:
    root = ET.Element("itemSchema")
    field = ET.SubElement(root, "field", {"id": "productTitle", "type": "input"})
    ET.SubElement(field, "value").text = title
    return ET.tostring(root, encoding="unicode", short_empty_elements=True)


def process(row: dict, config: dict, execute: bool) -> dict:
    product_id = str(row.get("product_id") or "").strip()
    title = " ".join(str(row.get("title") or "").split())
    expected_model = str(row.get("expected_model") or "").strip()
    result = {"product_id": product_id, "mode": "execute" if execute else "preflight", "ok": False}

    if product_id in PROTECTED_PRODUCT_IDS:
        result.update(stage="protected_source_refusal", error="Product ID is a protected source")
        return result
    if not product_id.isdigit() or not expected_model or not 1 <= len(title) <= 128:
        result.update(stage="plan_validation", error="Invalid product_id, expected_model, or title length")
        return result

    before_response = top_call(config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
    before = before_response.get("product") or {}
    if failed(before_response) or not before:
        result.update(stage="product_get_before", response=refs(before_response))
        return result
    if model_number(before) != expected_model:
        result.update(stage="identity_check", expected_model=expected_model, actual_model=model_number(before))
        return result
    if before.get("status") != "approved" or before.get("display") != "Y":
        result.update(stage="auditing_no_resubmit", status=before.get("status"), display=before.get("display"))
        return result
    before_images = image_keys(before)
    if len(before_images) != 6:
        result.update(stage="gallery_precheck", image_count=len(before_images))
        return result

    result.update(
        ok=True,
        stage="preflight_pass",
        expected_model=expected_model,
        old_title=before.get("subject"),
        new_title=title,
        title_length=len(title),
        before_status=before.get("status"),
        before_display=before.get("display"),
        before_images=before_images,
        before_sku_count=len((before.get("product_sku") or {}).get("skus") or []),
        source_not_targeted=True,
        read_before=refs(before_response),
    )
    if not execute:
        return result

    update_response = top_call(config, "alibaba.icbu.product.schema.update", {
        "param_product_top_publish_request": {
            "cat_id": int(before["category_id"]),
            "language": "en_US",
            "product_id": int(product_id),
            "xml": title_xml(title),
        }
    })
    if failed(update_response):
        result.update(ok=False, stage="schema_update", update=refs(update_response))
        return result

    after_response = top_call(config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
    after = after_response.get("product") or {}
    if failed(after_response) or not after:
        result.update(ok=False, stage="product_get_after", update=refs(update_response), read_after=refs(after_response))
        return result

    differences = diff_paths(stable_snapshot(before), stable_snapshot(after))
    checks = {
        "title_ok": after.get("subject") == title,
        "model_ok": model_number(after) == expected_model,
        "gallery_unchanged": image_keys(after) == before_images,
        "sku_count_unchanged": len((after.get("product_sku") or {}).get("skus") or []) == result["before_sku_count"],
        "non_target_fields_unchanged": not differences,
        "source_not_targeted": product_id not in PROTECTED_PRODUCT_IDS,
    }
    result.update(
        ok=all(checks.values()),
        stage="verified" if all(checks.values()) else "readback_mismatch",
        after_title=after.get("subject"),
        after_status=after.get("status"),
        after_display=after.get("display"),
        after_images=image_keys(after),
        after_sku_count=len((after.get("product_sku") or {}).get("skus") or []),
        checks=checks,
        snapshot_diff_paths=differences,
        update=refs(update_response),
        read_after=refs(after_response),
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8-sig"))
    rows = plan.get("products") if isinstance(plan, dict) else plan
    config = load_config(args.config)
    results = []
    for index, row in enumerate(rows):
        if index:
            time.sleep(1.5)
        results.append(process(row, config, args.execute))
    payload = {
        "mode": "execute" if args.execute else "preflight",
        "success_count": sum(bool(row.get("ok")) for row in results),
        "failure_count": sum(not bool(row.get("ok")) for row in results),
        "protected_source_count": len(PROTECTED_PRODUCT_IDS),
        "results": results,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["failure_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
