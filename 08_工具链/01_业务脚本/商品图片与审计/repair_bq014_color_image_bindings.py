#!/usr/bin/env python3
"""Repair only swapped BQ014/A507 Black and White color-image bindings.

The source product is protected and cannot be targeted. Default mode is a
dry-run; ``--apply`` updates the three verified expansion links sequentially.
SKU IDs, names, codes, inventory, prices, title and gallery remain unchanged.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
SCRIPT_DIR = ROOT / "08_工具链/01_业务脚本/商品图片与审计"
sys.path.insert(0, str(SCRIPT_DIR))

from repair_bq011_grey_green_label import (  # noqa: E402
    DEFAULT_CONFIG,
    call_retry,
    color_rows,
    failed,
    get_product,
    model_number,
    render,
    response_refs,
)
from batch_replace_hero import image_key  # noqa: E402


SOURCE_PRODUCT_ID = "10000043732626"
PRODUCTS = {
    "1601939669411": "BQ014-W1 / A507",
    "1601939658415": "BQ014-R1 / A507",
    "1601939608686": "BQ014-O1 / A507",
}
EXPECTED_NAMES = {"3327837": "Black", "-34": "Black White", "3331185": "White"}
CURRENT_IMAGES = {
    "3327837": "https://sc04.alicdn.com/kf/Se89b514a5e024ef09d4288af0b44e299K.png",
    "-34": "https://sc04.alicdn.com/kf/Scc55b368e2bb4e19b8cdd467ed90efdfv.png",
    "3331185": "https://sc04.alicdn.com/kf/Sa06a555836094985bff6de7d0cfe388bV.png",
}
TARGET_IMAGES = {
    "3327837": CURRENT_IMAGES["3331185"],  # Black -> actual all-black shoe
    "-34": CURRENT_IMAGES["-34"],          # Black White remains correct
    "3331185": CURRENT_IMAGES["3327837"],  # White -> actual beige/off-white shoe
}


def normalized_snapshot(product: dict) -> dict:
    copy = deepcopy(product)
    for key in ("status", "display", "gmt_modified", "pc_detail_url"):
        copy.pop(key, None)
    for group in (copy.get("product_sku") or {}).get("sku_attributes") or []:
        if int(group.get("attribute_id") or 0) == 191288010:
            for value in group.get("values") or []:
                value.pop("image_url", None)
    return copy


def image_map(product: dict) -> dict[str, str]:
    return {cid: str(row.get("image_url") or "") for cid, row in color_rows(product).items()}


def target_state(product: dict) -> bool:
    colors = color_rows(product)
    names = {cid: str(row.get("system_value_name") or "") for cid, row in colors.items()}
    if names != EXPECTED_NAMES:
        return False
    return all(image_key(image_map(product).get(cid, "")) == image_key(url)
               for cid, url in TARGET_IMAGES.items())


def build_xml(rendered: ET.Element) -> str:
    sale_prop = rendered.find("./field[@id='saleProp']")
    sku_field = rendered.find("./field[@id='sku']")
    if sale_prop is None or sku_field is None:
        raise RuntimeError("Current rendered Schema lacks saleProp or sku")
    sale_prop = deepcopy(sale_prop)
    sku_field = deepcopy(sku_field)
    color_field = sale_prop.find("./complex-value/field[@id='p-191288010']")
    values = color_field.findall("./values/value") if color_field is not None else []
    found_names = {str(v.text): str(v.attrib.get("inputValue") or "") for v in values}
    found_images = {str(v.text): str(v.attrib.get("img") or "") for v in values}
    if found_names != EXPECTED_NAMES:
        raise RuntimeError(f"Unexpected live color mapping: {found_names}")
    if not all(image_key(found_images.get(cid, "")) in {image_key(CURRENT_IMAGES[cid]), image_key(TARGET_IMAGES[cid])}
               for cid in EXPECTED_NAMES):
        raise RuntimeError(f"Unexpected live color-image state: {found_images}")
    for value in values:
        cid = str(value.text)
        value.attrib["img"] = TARGET_IMAGES[cid]
    if len(sku_field.findall("./complex-values")) != 33:
        raise RuntimeError("Expected exactly 33 SKU rows")
    root = ET.Element("itemSchema")
    root.append(sale_prop)
    root.append(sku_field)
    return ET.tostring(root, encoding="unicode")


def process(config: dict, product_id: str, expected_model: str, apply: bool) -> dict:
    if product_id == SOURCE_PRODUCT_ID or product_id not in PRODUCTS:
        raise RuntimeError(f"Protected or unknown target: {product_id}")
    before_response, before = get_product(config, product_id)
    record = {"product_id": product_id, "expected_model": expected_model,
              "before": response_refs(before_response), "before_status": before.get("status"),
              "before_display": before.get("display"), "mode": "apply" if apply else "dry-run",
              "before_images": image_map(before)}
    if model_number(before) != expected_model or int(before.get("category_id") or 0) != 201334413:
        raise RuntimeError(f"Identity/category mismatch for {product_id}")
    if len((before.get("product_sku") or {}).get("skus") or []) != 33:
        raise RuntimeError(f"Expected 33 SKUs for {product_id}")
    if target_state(before):
        record.update(stage="verified_existing", ok=True)
        return record
    if before.get("status") != "approved" or before.get("display") != "Y":
        record.update(stage="auditing_no_resubmit", ok=False)
        return record
    names = {cid: str(row.get("system_value_name") or "") for cid, row in color_rows(before).items()}
    if names != EXPECTED_NAMES or any(image_key(image_map(before).get(cid, "")) != image_key(url)
                                      for cid, url in CURRENT_IMAGES.items()):
        raise RuntimeError(f"Unexpected pre-update color state for {product_id}")

    schema_response, rendered = render(config, product_id)
    xml = build_xml(rendered)
    record.update(stage="prepared", render=response_refs(schema_response), target_images=TARGET_IMAGES)
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
        "target_bindings_ok": target_state(after),
        "sku_count_33": len((after.get("product_sku") or {}).get("skus") or []) == 33,
        "non_target_fields_unchanged": normalized_snapshot(after) == before_snapshot,
        "source_not_targeted": product_id != SOURCE_PRODUCT_ID,
    }
    record.update(stage="submitted", update=response_refs(update_response), readback=response_refs(after_response),
                  after_status=after.get("status"), after_display=after.get("display"),
                  after_images=image_map(after), checks=checks, ok=all(checks.values()))
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--product-id", choices=sorted(PRODUCTS))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from repair_bq011_grey_green_label import load_config
    config = load_config(args.config)
    selected = {args.product_id: PRODUCTS[args.product_id]} if args.product_id else PRODUCTS
    results = [process(config, product_id, expected_model, args.apply)
               for product_id, expected_model in selected.items()]
    receipt = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_product_id_protected": SOURCE_PRODUCT_ID,
        "mode": "apply" if args.apply else "dry-run",
        "change_scope": "Swap only Black and White color-image URLs; keep names, SKU IDs/codes, inventory, prices, title and gallery unchanged.",
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "results": {r["product_id"]: r["stage"] for r in results}}, ensure_ascii=False))
    return 0 if all(r.get("ok") for r in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
