#!/usr/bin/env python3
"""Repair only BQ022 expansion Black -> Black White color semantics.

Evidence: the protected BQ022 source product and the raw A2208 image pool both
identify the photographed black-upper/white-sole option as Black White.  The
three expansion links currently reuse that exact physical color but label it
Black.  Default mode is a read-only dry-run.  ``--apply`` submits expansions
sequentially and never accepts the protected source product as a target.
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
from batch_replace_hero import image_key, response_refs  # noqa: E402


SOURCE_PRODUCT_ID = "10000043991998"
PRODUCTS = {
    "1601939641581": "BQ022-W1 / A2208",
    "1601939659468": "BQ022-R1 / A2208",
    "1601939709218": "BQ022-O1 / A2208",
}
CATEGORY_ID = 201334413
COLOR_PROP_ID = "191288010"
SIZE_PROP_ID = "222038415"
OLD_COLOR_ID = "3327837"
NEW_COLOR_ID = "-10"
OLD_COLORS = {OLD_COLOR_ID: "Black", "-57": "Light Grey", "-34": "Black White Stripe"}
TARGET_COLORS = {NEW_COLOR_ID: "Black White", "-57": "Light Grey", "-34": "Black White Stripe"}


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
        if str(group.get("attribute_id")) == COLOR_PROP_ID:
            return {str(x.get("value_id")): x for x in group.get("values") or []}
    return {}


def normalized_snapshot(product: dict) -> dict:
    """Normalize only the intended color ID/name and matching SKU-code segment."""
    copy = deepcopy(product)
    for key in ("status", "display", "gmt_modified", "pc_detail_url"):
        copy.pop(key, None)
    sku = copy.get("product_sku") or {}
    for group in sku.get("sku_attributes") or []:
        if str(group.get("attribute_id")) == COLOR_PROP_ID:
            for value in group.get("values") or []:
                if str(value.get("value_id")) in (OLD_COLOR_ID, NEW_COLOR_ID):
                    value["value_id"] = "__BLACK_WHITE__"
                    value["system_value_name"] = "__BLACK_WHITE__"
            group.get("values", []).sort(key=lambda row: str(row.get("value_id")))
    for row in sku.get("skus") or []:
        attrs = json.loads(row.get("attr2_value") or "{}")
        cid = str(attrs.get(COLOR_PROP_ID))
        size = str(attrs.get(SIZE_PROP_ID))
        if cid in (OLD_COLOR_ID, NEW_COLOR_ID):
            attrs[COLOR_PROP_ID] = "__BLACK_WHITE__"
            row["attr2_value"] = json.dumps(attrs, ensure_ascii=False, sort_keys=True)
            row["sku_code"] = f"__BLACK_WHITE__-{size}"
    sku.get("skus", []).sort(key=lambda row: int(row.get("sku_id") or 0))
    return copy


def render(config: dict, product_id: str) -> tuple[dict, ET.Element]:
    response = call_retry(config, "alibaba.icbu.product.schema.render", {
        "param_product_top_publish_request": {"product_id": int(product_id), "language": "en_US"}
    })
    data = response.get("data")
    if failed(response) or not isinstance(data, str):
        raise RuntimeError(f"schema.render failed for {product_id}: {response_refs(response)}")
    return response, ET.fromstring(data)


def build_xml(rendered: ET.Element, prefix: str) -> tuple[str, list[dict]]:
    sale_prop = rendered.find("./field[@id='saleProp']")
    sku_field = rendered.find("./field[@id='sku']")
    if sale_prop is None or sku_field is None:
        raise RuntimeError("Current rendered Schema lacks saleProp or sku")
    sale_prop = deepcopy(sale_prop)
    sku_field = deepcopy(sku_field)
    color_field = sale_prop.find(f"./complex-value/field[@id='p-{COLOR_PROP_ID}']")
    values = color_field.findall("./values/value") if color_field is not None else []
    found = {str(value.text): str(value.attrib.get("inputValue") or "") for value in values}
    if found not in (OLD_COLORS, TARGET_COLORS):
        raise RuntimeError(f"Unexpected live color mapping: {found}")
    for value in values:
        if str(value.text) == OLD_COLOR_ID:
            value.text = NEW_COLOR_ID
            value.attrib["inputValue"] = "Black White"

    changed = []
    for item in sku_field.findall("./complex-values"):
        props = item.findall("./field[@id='props']/values/value")
        color = next((v for v in props if v.attrib.get("propId") == COLOR_PROP_ID), None)
        size = next((v for v in props if v.attrib.get("propId") == SIZE_PROP_ID), None)
        outer = item.find("./field[@id='skuOuterId']/value")
        if color is None or size is None or outer is None:
            raise RuntimeError("Malformed SKU row in current Schema")
        if str(color.attrib.get("propValueId")) == OLD_COLOR_ID:
            color.attrib["propValueId"] = NEW_COLOR_ID
            color.attrib["propValueName"] = "Black White"
            outer.text = f"{prefix}-BLACK-WHITE-{size.attrib['propValueName']}"
            changed.append({"size": size.attrib["propValueName"], "sku_code": outer.text})
    if found == OLD_COLORS and len(changed) != 11:
        raise RuntimeError(f"Expected 11 Black White size rows, got {len(changed)}")
    root = ET.Element("itemSchema")
    root.append(sale_prop)
    root.append(sku_field)
    return ET.tostring(root, encoding="unicode"), changed


def target_state(product: dict, prefix: str, expected_image: str | None = None) -> bool:
    colors = color_rows(product)
    names = {cid: str(row.get("system_value_name") or "") for cid, row in colors.items()}
    if names != TARGET_COLORS or len((product.get("product_sku") or {}).get("skus") or []) != 33:
        return False
    if expected_image and image_key(str(colors[NEW_COLOR_ID].get("image_url") or "")) != image_key(expected_image):
        return False
    target_rows = 0
    for sku in (product.get("product_sku") or {}).get("skus") or []:
        attrs = json.loads(sku.get("attr2_value") or "{}")
        if str(attrs.get(COLOR_PROP_ID)) == NEW_COLOR_ID:
            target_rows += 1
            if not str(sku.get("sku_code") or "").startswith(f"{prefix}-BLACK-WHITE-"):
                return False
    return target_rows == 11


def process(config: dict, product_id: str, expected_model: str, apply: bool) -> dict:
    if product_id == SOURCE_PRODUCT_ID or product_id not in PRODUCTS:
        raise RuntimeError(f"Protected or unknown target: {product_id}")
    before_response, before = get_product(config, product_id)
    prefix = expected_model.split(" / ", 1)[0]
    colors = color_rows(before)
    target_image = str((colors.get(OLD_COLOR_ID) or colors.get(NEW_COLOR_ID) or {}).get("image_url") or "")
    record = {
        "product_id": product_id, "expected_model": expected_model,
        "mode": "apply" if apply else "dry-run", "before": response_refs(before_response),
        "before_status": before.get("status"), "before_display": before.get("display"),
        "before_title": before.get("subject"), "before_image_count": len((before.get("main_image") or {}).get("images") or []),
        "before_sku_count": len((before.get("product_sku") or {}).get("skus") or []),
        "before_colors": {cid: {"name": row.get("system_value_name"), "image_url": row.get("image_url")} for cid, row in colors.items()},
    }
    if model_number(before) != expected_model or int(before.get("category_id") or 0) != CATEGORY_ID:
        raise RuntimeError(f"Identity/category mismatch for {product_id}")
    if record["before_image_count"] != 6 or record["before_sku_count"] != 33:
        raise RuntimeError(f"Unexpected gallery/SKU count for {product_id}")
    if target_state(before, prefix, target_image):
        record.update(stage="verified_existing", ok=True)
        return record
    current = {cid: str(row.get("system_value_name") or "") for cid, row in colors.items()}
    if current != OLD_COLORS:
        raise RuntimeError(f"Unexpected pre-update color state for {product_id}: {current}")
    if before.get("status") != "approved" or before.get("display") != "Y":
        record.update(stage="auditing_no_resubmit", ok=False)
        return record

    render_response, rendered = render(config, product_id)
    xml, changed = build_xml(rendered, prefix)
    record.update(stage="prepared", render=response_refs(render_response), changed_sku_rows=changed,
                  intended_change="Black -> Black White; preserve its current thumbnail")
    if not apply:
        record.update(ok=True)
        return record

    frozen = normalized_snapshot(before)
    update_response = call_retry(config, "alibaba.icbu.product.schema.update", {
        "param_product_top_publish_request": {
            "cat_id": CATEGORY_ID, "language": "en_US", "product_id": int(product_id), "xml": xml,
        }
    })
    if failed(update_response):
        raise RuntimeError(f"schema.update failed for {product_id}: {response_refs(update_response)}")
    after_response, after = get_product(config, product_id)
    checks = {
        "identity_ok": model_number(after) == expected_model,
        "target_state_ok": target_state(after, prefix, target_image),
        "title_unchanged": after.get("subject") == before.get("subject"),
        "gallery_unchanged": (after.get("main_image") or {}).get("images") == (before.get("main_image") or {}).get("images"),
        "sku_count_33": len((after.get("product_sku") or {}).get("skus") or []) == 33,
        "non_target_fields_unchanged": normalized_snapshot(after) == frozen,
        "source_not_targeted": product_id != SOURCE_PRODUCT_ID,
    }
    record.update(stage="submitted", update=response_refs(update_response), readback=response_refs(after_response),
                  after_status=after.get("status"), after_display=after.get("display"),
                  after_colors={cid: {"name": row.get("system_value_name"), "image_url": row.get("image_url")} for cid, row in color_rows(after).items()},
                  checks=checks, ok=all(checks.values()))
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
    for index, (product_id, expected_model) in enumerate(selected.items()):
        if index:
            time.sleep(1.5)
        results.append(process(config, product_id, expected_model, args.apply))
    receipt = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_product_id_protected": SOURCE_PRODUCT_ID,
        "mode": "apply" if args.apply else "dry-run",
        "evidence": "protected source product + merged raw A2208 images + expansion thumbnail readback",
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "results": {r["product_id"]: r["stage"] for r in results}}, ensure_ascii=False))
    return 0 if all(row.get("ok") for row in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
