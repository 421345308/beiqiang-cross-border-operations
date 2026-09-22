#!/usr/bin/env python3
"""Update Alibaba product keywords only, with source protection and fail-fast readback."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
sys.path.insert(0, str(ROOT / ".agents/skills/alibaba-openapi-operator/scripts"))
from alibaba_openapi import DEFAULT_CONFIG, api_error, load_config, top_call  # noqa: E402


PROTECTED_PRODUCT_IDS = {
    "1601825074604", "1601825021825", "1601815020244", "1601814931739",
    "10000044041008", "10000043991998", "1601839073314", "1601838963947",
    "10000042821848", "10000044004948", "10000044024484", "10000044041031",
    "10000043744505", "10000044028277", "10000044007878", "10000046439033",
    "10000043732626",
    "1601839105416", "1601825070472", "10000043201799", "1601825160204", "1601839062659", "1601839050756", "10000046653813", "10000044011929", "10000044021584", "10000044034049", "10000042896165", "10000043200726", "10000043725883",
}


def model_number(product: dict) -> str:
    return next((str(row.get("value_name") or "") for row in product.get("attributes") or []
                 if row.get("attribute_name") == "Model Number"), "")


def normalized(value) -> list[str]:
    parts = [str(item) for item in value] if isinstance(value, list) else str(value or "").splitlines()
    return [" ".join(part.split()).lower() for part in parts if part.strip()]


def stable_snapshot(product: dict) -> dict:
    excluded = {"keywords", "gmt_modified", "status", "display", "pc_detail_url"}
    return {key: deepcopy(value) for key, value in product.items() if key not in excluded}


def keyword_xml(keywords: list[str]) -> str:
    root = ET.Element("itemSchema")
    field = ET.SubElement(root, "field", {"id": "productKeywords", "name": "Product keywords ", "type": "complex"})
    complex_value = ET.SubElement(field, "complex-value")
    node = ET.SubElement(complex_value, "field", {"id": "productKeywords_0", "name": "Product keywords ", "type": "input"})
    ET.SubElement(node, "value").text = "\n".join(keywords)
    return ET.tostring(root, encoding="unicode", short_empty_elements=True)


def refs(response: dict) -> dict:
    return {
        "request_id": response.get("request_id"),
        "trace_id": response.get("trace_id") or response.get("_trace_id_"),
        "error": api_error(response),
    }


def process(row: dict, config: dict, execute: bool) -> dict:
    product_id = str(row["product_id"])
    expected_model = str(row["expected_model"]).strip()
    keywords = [" ".join(str(value).split()) for value in row.get("keywords") or [] if str(value).strip()]
    result = {"product_id": product_id, "execute": execute, "ok": False}
    if product_id in PROTECTED_PRODUCT_IDS:
        return {**result, "stage": "protected_product_refusal"}
    if not 3 <= len(keywords) <= 5 or len({value.lower() for value in keywords}) != len(keywords):
        return {**result, "stage": "plan_validation", "error": "Need 3-5 unique keyword phrases"}

    before_response = top_call(config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
    before = before_response.get("product") or {}
    if not before or api_error(before_response):
        return {**result, "stage": "product_get_before", "response": refs(before_response)}
    if model_number(before) != expected_model:
        return {**result, "stage": "identity_check", "expected_model": expected_model, "actual_model": model_number(before)}
    if before.get("status") == "modified" or before.get("display") == "N":
        return {**result, "stage": "auditing_no_resubmit", "status": before.get("status"), "display": before.get("display")}

    result.update(ok=True, stage="preflight_pass", before_keywords=before.get("keywords"), requested_keywords=keywords,
                  before_status=before.get("status"), before_display=before.get("display"), request=refs(before_response))
    if not execute:
        return result

    update_response = top_call(config, "alibaba.icbu.product.schema.update", {
        "param_product_top_publish_request": {
            "cat_id": int(before["category_id"]), "language": "en_US",
            "product_id": int(product_id), "xml": keyword_xml(keywords),
        }
    })
    if api_error(update_response):
        return {**result, "ok": False, "stage": "schema_update", "update": refs(update_response)}
    after_response = top_call(config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
    after = after_response.get("product") or {}
    checks = {
        "keywords_ok": normalized(after.get("keywords")) == normalized(keywords),
        "identity_ok": model_number(after) == expected_model,
        "other_fields_unchanged": stable_snapshot(after) == stable_snapshot(before),
        "source_not_targeted": product_id not in PROTECTED_PRODUCT_IDS,
    }
    return {
        **result, "ok": all(checks.values()), "stage": "verified" if all(checks.values()) else "readback_mismatch",
        "after_keywords": after.get("keywords"), "after_status": after.get("status"), "after_display": after.get("display"),
        "checks": checks, "update": refs(update_response), "readback": refs(after_response),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    rows = json.loads(args.plan.read_text(encoding="utf-8-sig"))["products"]
    config = load_config(args.config)
    results = []
    for row in rows:
        outcome = process(row, config, args.execute)
        results.append(outcome)
        if args.execute and not outcome.get("ok"):
            break
    payload = {
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "mode": "execute" if args.execute else "preflight",
        "fail_fast": True,
        "results": results,
        "success_count": sum(bool(row.get("ok")) for row in results),
        "failure_count": sum(not bool(row.get("ok")) for row in results),
    }
    output = args.manifest or args.plan.with_name(args.plan.stem + ("_result.json" if args.execute else "_preflight.json"))
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(output), "mode": payload["mode"], "success_count": payload["success_count"],
                      "failure_count": payload["failure_count"], "stages": {row["product_id"]: row["stage"] for row in results}}, ensure_ascii=False))
    return 0 if payload["failure_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
