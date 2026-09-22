#!/usr/bin/env python3
"""Repair unsupported material values on BQ008/BQ011 expansion links.

BQ008/L1009 source evidence says sole material is not confirmed and the
pending qualifier must not be exposed to buyers. BQ011/A002 has no confirmed
sole material, while the live value ``Cushion`` is a construction/feel term,
not a material. Source products are hard-protected. Default mode is dry-run;
``--apply`` changes only Midsole Material and Outsole Material to Schema
``Other`` and verifies every non-target field by snapshot.
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


CATEGORY_ID = 201334413
PROTECTED_SOURCES = {"1601825021825", "10000043725883"}
PRODUCTS = {
    "1601939625569": {"model": "BQ008-W1 / L1009", "allowed": "EVA, Confirm Before Bulk Order"},
    "1601939628529": {"model": "BQ008-R1 / L1009", "allowed": "EVA, Confirm Before Bulk Order"},
    "1601939659415": {"model": "BQ008-O1 / L1009", "allowed": "EVA, Confirm Before Bulk Order"},
    "1601939634522": {"model": "BQ011-W1 / A002", "allowed": "Cushion"},
    "1601939666421": {"model": "BQ011-R1 / A002", "allowed": "Cushion"},
    "1601939606803": {"model": "BQ011-O1 / A002", "allowed": "Cushion"},
}
TARGETS = {
    20700: ("p-20700", "Midsole Material"),
    191290426: ("p-191290426", "Outsole Material"),
}
OTHER_VALUE_ID = 4
OTHER_VALUE_NAME = "Other"


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
    product = response.get("product") or (response.get("product_get_response") or {}).get("product") or {}
    if failed(response) or not product:
        raise RuntimeError(f"product.get failed for {product_id}: {refs(response)}")
    return response, product


def attribute(product: dict, attribute_id: int) -> dict | None:
    return next((row for row in product.get("attributes") or [] if int(row.get("attribute_id") or 0) == attribute_id), None)


def model_number(product: dict) -> str:
    row = attribute(product, 3)
    return str((row or {}).get("value_name") or "")


def image_keys(product: dict) -> list[str]:
    return [str(value).split("?")[0] for value in ((product.get("main_image") or {}).get("images") or [])]


def normalized(value):
    if isinstance(value, dict):
        return {key: normalized(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        items = [normalized(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
    return value


def frozen_snapshot(product: dict) -> dict:
    copy = deepcopy(product)
    for key in ("status", "display", "gmt_modified", "pc_detail_url"):
        copy.pop(key, None)
    copy["attributes"] = [
        row for row in copy.get("attributes") or []
        if int(row.get("attribute_id") or 0) not in TARGETS
    ]
    return normalized(copy)


def is_other(row: dict | None) -> bool:
    if not row:
        return False
    return str(row.get("value_name") or "").strip().casefold() == "other" and int(row.get("value_id") or 0) in (-1, 4)


def render(config: dict, product_id: str) -> tuple[dict, ET.Element]:
    response = call_retry(config, "alibaba.icbu.product.schema.render", {
        "param_product_top_publish_request": {"product_id": int(product_id), "language": "en_US"}
    })
    data = response.get("data")
    if failed(response) or not isinstance(data, str):
        raise RuntimeError(f"schema.render failed for {product_id}: {refs(response)}")
    return response, ET.fromstring(data)


def material_xml(rendered: ET.Element) -> str:
    root = ET.Element("itemSchema")
    category_properties = ET.SubElement(root, "field", {
        "id": "icbuCatProp", "name": "Product feature", "type": "complex",
    })
    complex_value = ET.SubElement(category_properties, "complex-value")
    for _, (field_id, attr_name) in TARGETS.items():
        current = rendered.find(f".//field[@id='{field_id}']")
        if current is None:
            current = ET.Element("field", {"id": field_id, "name": attr_name, "type": "multiCheck"})
        field_copy = deepcopy(current)
        values = field_copy.find("./values")
        if values is None:
            values = ET.SubElement(field_copy, "values")
        for old_value in list(values.findall("./value")):
            values.remove(old_value)
        value = ET.SubElement(values, "value", {"inputValue": OTHER_VALUE_NAME})
        value.text = str(OTHER_VALUE_ID)
        complex_value.append(field_copy)
    return ET.tostring(root, encoding="unicode")


def process(config: dict, product_id: str, spec: dict, apply: bool) -> dict:
    before_response, before = get_product(config, product_id)
    expected_model = spec["model"]
    allowed_current = spec["allowed"]
    record = {
        "product_id": product_id,
        "expected_model": expected_model,
        "mode": "apply" if apply else "dry-run",
        "before": refs(before_response),
        "before_status": before.get("status"),
        "before_display": before.get("display"),
        "before_title": before.get("subject"),
        "before_images": image_keys(before),
        "before_sku_count": len((before.get("product_sku") or {}).get("skus") or []),
        "before_materials": {name: attribute(before, attr_id) for attr_id, (_, name) in TARGETS.items()},
    }
    if product_id in PROTECTED_SOURCES or product_id not in PRODUCTS:
        raise RuntimeError(f"Protected or unapproved product target: {product_id}")
    if model_number(before) != expected_model or int(before.get("category_id") or 0) != CATEGORY_ID:
        raise RuntimeError(f"Identity/category mismatch for {product_id}")
    if len(image_keys(before)) != 6:
        raise RuntimeError(f"Gallery count is not 6 for {product_id}")

    material_rows = [attribute(before, attr_id) for attr_id in TARGETS]
    if all(is_other(row) for row in material_rows):
        record.update(stage="verified_existing", ok=True)
        return record
    current_names = [str((row or {}).get("value_name") or "") for row in material_rows]
    if any(name != allowed_current for name in current_names):
        raise RuntimeError(f"Unexpected current material values for {product_id}: {current_names}")
    if before.get("status") != "approved" or before.get("display") != "Y":
        record.update(stage="auditing_no_resubmit", ok=False)
        return record

    render_response, rendered = render(config, product_id)
    xml = material_xml(rendered)
    record.update(
        stage="preflight_pass",
        render=refs(render_response),
        requested_materials={name: {"value_id": OTHER_VALUE_ID, "value_name": OTHER_VALUE_NAME} for _, name in TARGETS.values()},
        protected_sources=sorted(PROTECTED_SOURCES),
        source_not_targeted=True,
        ok=True,
    )
    if not apply:
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
    checks = {
        "identity_ok": model_number(after) == expected_model,
        "midsole_is_other": is_other(attribute(after, 20700)),
        "outsole_is_other": is_other(attribute(after, 191290426)),
        "title_unchanged": after.get("subject") == before.get("subject"),
        "gallery_unchanged": image_keys(after) == image_keys(before),
        "sku_count_unchanged": len((after.get("product_sku") or {}).get("skus") or []) == record["before_sku_count"],
        "non_target_fields_unchanged": frozen_snapshot(after) == frozen,
        "source_not_targeted": product_id not in PROTECTED_SOURCES,
    }
    record.update(
        stage="submitted",
        update=refs(update_response),
        readback=refs(after_response),
        after_status=after.get("status"),
        after_display=after.get("display"),
        after_title=after.get("subject"),
        after_images=image_keys(after),
        after_sku_count=len((after.get("product_sku") or {}).get("skus") or []),
        after_materials={name: attribute(after, attr_id) for attr_id, (_, name) in TARGETS.items()},
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
    results = []
    for index, (product_id, spec) in enumerate(selected.items()):
        if index:
            time.sleep(1.5)
        results.append(process(config, product_id, spec, args.apply))
    receipt = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "protected_source_product_ids": sorted(PROTECTED_SOURCES),
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
