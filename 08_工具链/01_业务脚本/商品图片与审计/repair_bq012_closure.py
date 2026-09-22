#!/usr/bin/env python3
"""Repair only BQ012 expansion Closure Type from Lace-up to Slip-On.

The M8506 source sheet confirms ``Slip-On with Lace Detail`` and explicitly
rejects ordinary adjustable lace-up wording. The source product is protected.
Default mode is a read-only dry run; ``--apply`` writes the three expansion
links sequentially and verifies that every non-target field stayed unchanged.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import xml.etree.ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT_DIR = ROOT / ".agents/skills/alibaba-openapi-operator/scripts"
sys.path.insert(0, str(CLIENT_DIR))

from alibaba_openapi import DEFAULT_CONFIG, api_error, load_config, top_call  # noqa: E402


SOURCE_PRODUCT_ID = "10000043744505"
PRODUCTS = {
    "1601939650458": "BQ012-W1 / M8506",
    "1601939681367": "BQ012-R1 / M8506",
    "1601939606805": "BQ012-O1 / M8506",
}
CATEGORY_ID = 201334413
CLOSURE_ATTRIBUTE_ID = 200000388
FIELD_ID = f"p-{CLOSURE_ATTRIBUTE_ID}"
OLD_VALUE_ID = 80806811
OLD_VALUE_NAME = "Lace-up"
TARGET_VALUE_ID = 13325270
TARGET_VALUE_NAME = "Slip-On"


def failed(response: dict) -> bool:
    return bool(api_error(response)) or response.get("biz_success") is False or response.get("model") is False


def refs(response: dict) -> dict:
    return {
        "request_id": response.get("request_id"),
        "trace_id": response.get("trace_id") or response.get("_trace_id_"),
        "message": response.get("message") or response.get("msg_info"),
        "error": api_error(response),
    }


def call_retry(config: dict, method: str, params: dict, attempts: int = 4) -> dict:
    for attempt in range(1, attempts + 1):
        try:
            return top_call(config, method, params)
        except Exception as exc:
            transient = any(token in str(exc).lower() for token in ("ssl", "eof", "timed out", "connection reset"))
            if not transient or attempt == attempts:
                raise
            time.sleep(attempt * 2)
    raise RuntimeError("unreachable")


def get_product(config: dict, product_id: str) -> tuple[dict, dict]:
    response = call_retry(config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
    product = (response.get("product_get_response") or {}).get("product") or response.get("product") or {}
    if failed(response) or not product:
        raise RuntimeError(f"product.get failed for {product_id}: {refs(response)}")
    return response, product


def attribute(product: dict, attribute_id: int) -> dict | None:
    return next((row for row in product.get("attributes") or [] if int(row.get("attribute_id") or 0) == attribute_id), None)


def model_number(product: dict) -> str:
    row = attribute(product, 3)
    return str((row or {}).get("value_name") or "")


def frozen_snapshot(product: dict) -> dict:
    copy = deepcopy(product)
    for key in ("status", "display", "gmt_modified", "pc_detail_url"):
        copy.pop(key, None)
    copy["attributes"] = [
        row for row in copy.get("attributes") or []
        if int(row.get("attribute_id") or 0) != CLOSURE_ATTRIBUTE_ID
    ]
    return copy


def render(config: dict, product_id: str) -> tuple[dict, ET.Element]:
    response = call_retry(config, "alibaba.icbu.product.schema.render", {
        "param_product_top_publish_request": {"product_id": int(product_id), "language": "en_US"}
    })
    data = response.get("data")
    if failed(response) or not isinstance(data, str):
        raise RuntimeError(f"schema.render failed for {product_id}: {refs(response)}")
    return response, ET.fromstring(data)


def closure_xml(rendered: ET.Element) -> str:
    current = rendered.find(f".//field[@id='{FIELD_ID}']")
    if current is None:
        raise RuntimeError(f"Rendered Schema lacks {FIELD_ID}")
    value = current.find("./value")
    if value is None:
        raise RuntimeError("Closure field has no value node")
    observed = (int(value.text or 0), str(value.attrib.get("inputValue") or ""))
    if observed not in ((OLD_VALUE_ID, OLD_VALUE_NAME), (TARGET_VALUE_ID, TARGET_VALUE_NAME)):
        raise RuntimeError(f"Unexpected current closure value: {observed}")
    value.text = str(TARGET_VALUE_ID)
    value.attrib["inputValue"] = TARGET_VALUE_NAME
    # Category properties must remain under the icbuCatProp complex container.
    # A bare p-* field may be accepted by schema.update but silently ignored.
    root = ET.Element("itemSchema")
    category_properties = ET.SubElement(root, "field", {
        "id": "icbuCatProp", "name": "Product feature", "type": "complex",
    })
    complex_value = ET.SubElement(category_properties, "complex-value")
    complex_value.append(deepcopy(current))
    return ET.tostring(root, encoding="unicode")


def process(config: dict, product_id: str, expected_model: str, apply: bool) -> dict:
    before_response, before = get_product(config, product_id)
    record = {
        "product_id": product_id,
        "expected_model": expected_model,
        "mode": "apply" if apply else "dry-run",
        "before": refs(before_response),
        "before_status": before.get("status"),
        "before_display": before.get("display"),
    }
    if product_id == SOURCE_PRODUCT_ID or product_id not in PRODUCTS:
        raise RuntimeError(f"Protected or unapproved product target: {product_id}")
    if model_number(before) != expected_model or int(before.get("category_id") or 0) != CATEGORY_ID:
        raise RuntimeError(f"Identity/category mismatch for {product_id}")
    closure_before = attribute(before, CLOSURE_ATTRIBUTE_ID) or {}
    record["before_closure"] = closure_before
    if int(closure_before.get("value_id") or 0) == TARGET_VALUE_ID and closure_before.get("value_name") == TARGET_VALUE_NAME:
        record.update(stage="verified_existing", ok=True)
        return record
    if (int(closure_before.get("value_id") or 0), closure_before.get("value_name")) != (OLD_VALUE_ID, OLD_VALUE_NAME):
        raise RuntimeError(f"Unexpected product closure value for {product_id}: {closure_before}")
    if before.get("status") != "approved" or before.get("display") != "Y":
        record.update(stage="auditing_no_resubmit", ok=False)
        return record

    render_response, rendered = render(config, product_id)
    xml = closure_xml(rendered)
    record.update(stage="prepared", render=refs(render_response), requested_closure={
        "attribute_id": CLOSURE_ATTRIBUTE_ID,
        "value_id": TARGET_VALUE_ID,
        "value_name": TARGET_VALUE_NAME,
    })
    if not apply:
        record.update(ok=True)
        return record

    frozen = frozen_snapshot(before)
    update_response = call_retry(config, "alibaba.icbu.product.schema.update", {
        "param_product_top_publish_request": {
            "cat_id": CATEGORY_ID,
            "language": "en_US",
            "product_id": int(product_id),
            "xml": xml,
        }
    })
    if failed(update_response):
        raise RuntimeError(f"schema.update failed for {product_id}: {refs(update_response)}")
    after_response, after = get_product(config, product_id)
    closure_after = attribute(after, CLOSURE_ATTRIBUTE_ID) or {}
    checks = {
        "identity_ok": model_number(after) == expected_model,
        "closure_is_slip_on": (int(closure_after.get("value_id") or 0), closure_after.get("value_name")) == (TARGET_VALUE_ID, TARGET_VALUE_NAME),
        "image_count_6": len((after.get("main_image") or {}).get("images") or []) == 6,
        "non_target_fields_unchanged": frozen_snapshot(after) == frozen,
    }
    record.update(
        stage="submitted",
        update=refs(update_response),
        readback=refs(after_response),
        after_status=after.get("status"),
        after_display=after.get("display"),
        after_closure=closure_after,
        checks=checks,
        ok=all(checks.values()),
    )
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--product-id", choices=sorted(PRODUCTS))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = load_config(args.config)

    selected = {args.product_id: PRODUCTS[args.product_id]} if args.product_id else PRODUCTS
    results = [process(config, product_id, model, args.apply) for product_id, model in selected.items()]
    receipt = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_product_id_protected": SOURCE_PRODUCT_ID,
        "mode": "apply" if args.apply else "dry-run",
        "results": results,
        "success_count": sum(bool(row.get("ok")) for row in results),
        "failure_count": sum(not bool(row.get("ok")) for row in results),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "results": {row["product_id"]: row["stage"] for row in results},
        "success_count": receipt["success_count"],
        "failure_count": receipt["failure_count"],
    }, ensure_ascii=False))
    return 0 if receipt["failure_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
