#!/usr/bin/env python3
"""Repair only the BQ011/A002 Grey Green color label and SKU-code segment.

The protected source product is never accepted as a target. Default mode is
dry-run; ``--apply`` updates the three verified expansion links sequentially.
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
from batch_replace_hero import response_refs  # noqa: E402


SOURCE_PRODUCT_ID = "10000043725883"
PRODUCTS = {
    "1601939634522": "BQ011-W1 / A002",
    "1601939666421": "BQ011-R1 / A002",
    "1601939606803": "BQ011-O1 / A002",
}
COLOR_ID = "-31"
EXPECTED_COLORS = {"-31": "Light Grey", "-16": "Grey White", "-1": "Grey Black"}
TARGET_COLORS = {"-31": "Grey Green", "-16": "Grey White", "-1": "Grey Black"}


def failed(response: dict) -> bool:
    return bool(api_error(response)) or response.get("biz_success") is False or response.get("model") is False


def call_retry(config: dict, method: str, params: dict, attempts: int = 3) -> dict:
    for attempt in range(1, attempts + 1):
        try:
            return top_call(config, method, params)
        except Exception as exc:
            transient = any(x in str(exc).lower() for x in ("ssl", "eof", "timed out", "connection reset"))
            if not transient or attempt == attempts:
                raise
            time.sleep(attempt * 2)
    raise RuntimeError("unreachable")


def get_product(config: dict, product_id: str) -> tuple[dict, dict]:
    response = call_retry(config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
    product = (response.get("product_get_response") or {}).get("product") or response.get("product") or {}
    if failed(response) or not product:
        raise RuntimeError(f"product.get failed for {product_id}: {response_refs(response)}")
    return response, product


def model_number(product: dict) -> str:
    return next((str(x.get("value_name") or "") for x in product.get("attributes") or []
                 if x.get("attribute_name") == "Model Number"), "")


def color_rows(product: dict) -> dict[str, dict]:
    for group in (product.get("product_sku") or {}).get("sku_attributes") or []:
        if int(group.get("attribute_id") or 0) == 191288010:
            return {str(x.get("value_id")): x for x in group.get("values") or []}
    return {}


def normalized_snapshot(product: dict) -> dict:
    copy = deepcopy(product)
    for key in ("status", "display", "gmt_modified", "pc_detail_url"):
        copy.pop(key, None)
    sku = copy.get("product_sku") or {}
    for row in sku.get("skus") or []:
        row.pop("sku_code", None)
    for group in sku.get("sku_attributes") or []:
        if int(group.get("attribute_id") or 0) == 191288010:
            for value in group.get("values") or []:
                value.pop("system_value_name", None)
    return copy


def target_state(product: dict, prefix: str) -> bool:
    colors = color_rows(product)
    if {cid: str(row.get("system_value_name") or "") for cid, row in colors.items()} != TARGET_COLORS:
        return False
    skus = (product.get("product_sku") or {}).get("skus") or []
    if len(skus) != 21:
        return False
    for sku in skus:
        attrs = json.loads(sku.get("attr2_value") or "{}")
        if str(attrs.get("191288010")) == COLOR_ID and not str(sku.get("sku_code") or "").startswith(f"{prefix}-GREY-GREEN-"):
            return False
    return True


def render(config: dict, product_id: str) -> tuple[dict, ET.Element]:
    response = call_retry(config, "alibaba.icbu.product.schema.render", {
        "param_product_top_publish_request": {"product_id": int(product_id), "language": "en_US"}
    })
    data = response.get("data")
    if failed(response) or not isinstance(data, str):
        raise RuntimeError(f"schema.render failed for {product_id}: {response_refs(response)}")
    return response, ET.fromstring(data)


def build_xml(rendered: ET.Element, prefix: str) -> tuple[str, int]:
    sale_prop = rendered.find("./field[@id='saleProp']")
    sku_field = rendered.find("./field[@id='sku']")
    if sale_prop is None or sku_field is None:
        raise RuntimeError("Current rendered Schema lacks saleProp or sku")
    sale_prop = deepcopy(sale_prop)
    sku_field = deepcopy(sku_field)

    color_field = sale_prop.find("./complex-value/field[@id='p-191288010']")
    values = color_field.findall("./values/value") if color_field is not None else []
    found = {str(v.text): str(v.attrib.get("inputValue") or "") for v in values}
    if found not in (EXPECTED_COLORS, TARGET_COLORS):
        raise RuntimeError(f"Unexpected live color mapping: {found}")
    for value in values:
        cid = str(value.text)
        if cid == COLOR_ID:
            value.attrib["inputValue"] = "Grey Green"

    changed_rows = 0
    for item in sku_field.findall("./complex-values"):
        prop_values = item.findall("./field[@id='props']/values/value")
        color = next((v for v in prop_values if v.attrib.get("propId") == "191288010"), None)
        size = next((v for v in prop_values if v.attrib.get("propId") == "222038415"), None)
        outer = item.find("./field[@id='skuOuterId']/value")
        if color is None or size is None or outer is None:
            raise RuntimeError("Malformed SKU row in current Schema")
        if str(color.attrib.get("propValueId")) == COLOR_ID:
            color.attrib["propValueName"] = "Grey Green"
            outer.text = f"{prefix}-GREY-GREEN-{size.attrib['propValueName']}"
            changed_rows += 1
    if changed_rows != 7:
        raise RuntimeError(f"Expected 7 Grey Green size rows, got {changed_rows}")
    root = ET.Element("itemSchema")
    root.append(sale_prop)
    root.append(sku_field)
    return ET.tostring(root, encoding="unicode"), changed_rows


def process(config: dict, product_id: str, expected_model: str, apply: bool) -> dict:
    if product_id == SOURCE_PRODUCT_ID or product_id not in PRODUCTS:
        raise RuntimeError(f"Protected or unknown target: {product_id}")
    before_response, before = get_product(config, product_id)
    prefix = expected_model.split(" / ", 1)[0]
    record = {"product_id": product_id, "expected_model": expected_model,
              "before": response_refs(before_response), "before_status": before.get("status"),
              "before_display": before.get("display"), "mode": "apply" if apply else "dry-run"}
    if model_number(before) != expected_model or int(before.get("category_id") or 0) != 201334413:
        raise RuntimeError(f"Identity/category mismatch for {product_id}")
    if len((before.get("product_sku") or {}).get("skus") or []) != 21:
        raise RuntimeError(f"Expected 21 SKUs for {product_id}")
    if target_state(before, prefix):
        record.update(stage="verified_existing", ok=True)
        return record
    if before.get("status") != "approved" or before.get("display") != "Y":
        record.update(stage="auditing_no_resubmit", ok=False)
        return record
    current = {cid: str(row.get("system_value_name") or "") for cid, row in color_rows(before).items()}
    if current != EXPECTED_COLORS:
        raise RuntimeError(f"Unexpected pre-update color state for {product_id}: {current}")

    schema_response, rendered = render(config, product_id)
    xml, changed_rows = build_xml(rendered, prefix)
    record.update(stage="prepared", render=response_refs(schema_response), changed_sku_rows=changed_rows)
    if not apply:
        record.update(ok=True)
        return record

    before_snapshot = normalized_snapshot(before)
    update_response = call_retry(config, "alibaba.icbu.product.schema.update", {
        "param_product_top_publish_request": {
            "cat_id": 201334413, "language": "en_US", "product_id": int(product_id), "xml": xml,
        }
    })
    if failed(update_response):
        raise RuntimeError(f"schema.update failed for {product_id}: {response_refs(update_response)}")
    after_response, after = get_product(config, product_id)
    checks = {
        "identity_ok": model_number(after) == expected_model,
        "target_state_ok": target_state(after, prefix),
        "sku_count_21": len((after.get("product_sku") or {}).get("skus") or []) == 21,
        "non_target_fields_unchanged": normalized_snapshot(after) == before_snapshot,
        "source_not_targeted": product_id != SOURCE_PRODUCT_ID,
    }
    record.update(stage="submitted", update=response_refs(update_response), readback=response_refs(after_response),
                  after_status=after.get("status"), after_display=after.get("display"), checks=checks,
                  ok=all(checks.values()))
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
    results = [process(config, product_id, expected_model, args.apply)
               for product_id, expected_model in selected.items()]
    receipt = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_product_id_protected": SOURCE_PRODUCT_ID,
        "mode": "apply" if args.apply else "dry-run",
        "change_scope": "Light Grey label and seven matching SKU-code segments per expansion only",
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "results": {r["product_id"]: r["stage"] for r in results}}, ensure_ascii=False))
    return 0 if all(r.get("ok") for r in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
