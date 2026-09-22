#!/usr/bin/env python3
"""Repair only BQ028 expansion SKU color thumbnail bindings.

The protected 7212 source product is never writable. The three expansion
products keep their color names, SKU codes, 55 color/size SKUs, title,
six-image gallery, prices, attributes and details. Default mode is a read-only
preflight; ``--apply`` is accepted only when a product is approved/Y.
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


SOURCE_PRODUCT_ID = "1601839105416"
PRODUCTS = {
    "1601939720204": "BQ028-W1 / 7212",
    "1601939625627": "BQ028-R1 / 7212",
    "1601939705262": "BQ028-O1 / 7212",
}
TARGET = {
    "123085": {
        "name": "Blue",
        "image_url": "https://sc04.alicdn.com/kf/S153f232093a1490582fed2b62170a351f.jpg",
    },
    "3483425": {
        "name": "Grey",
        "image_url": "https://sc04.alicdn.com/kf/Sfac3c3d26d3f404b86cd3addb65d5109A.jpg",
    },
    "-1": {
        "name": "Black White",
        "image_url": "https://sc04.alicdn.com/kf/S840ec60105a7483da34391fb5efc2dbdR.jpg",
    },
    "3331185": {
        "name": "White",
        "image_url": "https://sc04.alicdn.com/kf/S3ee1fe3ddfff4f00ba00c8975e83f4acj.jpg",
    },
    "-57": {
        "name": "Apricot",
        "image_url": "https://sc04.alicdn.com/kf/S7281b7ce1e3a42918b2f90bd0088d622t.jpg",
    },
}


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
    return next(
        (str(row.get("value_name") or "") for row in product.get("attributes") or []
         if row.get("attribute_name") == "Model Number"),
        "",
    )


def color_rows(product: dict) -> dict[str, dict]:
    for group in (product.get("product_sku") or {}).get("sku_attributes") or []:
        if int(group.get("attribute_id") or 0) == 191288010:
            return {str(row.get("value_id")): row for row in group.get("values") or []}
    return {}


def target_state(product: dict) -> bool:
    colors = color_rows(product)
    return set(colors) == set(TARGET) and all(
        str(colors[color_id].get("system_value_name") or "") == row["name"]
        and image_key(str(colors[color_id].get("image_url") or "")) == image_key(row["image_url"])
        for color_id, row in TARGET.items()
    )


def normalized_without_color_images(product: dict) -> dict:
    snapshot = deepcopy(product)
    for key in ("status", "display", "gmt_modified", "pc_detail_url"):
        snapshot.pop(key, None)
    sku = snapshot.get("product_sku") or {}
    for group in sku.get("sku_attributes") or []:
        if int(group.get("attribute_id") or 0) == 191288010:
            for value in group.get("values") or []:
                value.pop("image_url", None)
        if group.get("values"):
            group["values"].sort(key=lambda row: str(row.get("value_id") or ""))
    if sku.get("sku_attributes"):
        sku["sku_attributes"].sort(key=lambda row: int(row.get("attribute_id") or 0))
    if sku.get("skus"):
        sku["skus"].sort(key=lambda row: int(row.get("sku_id") or 0))
    return snapshot


def render(config: dict, product_id: str) -> tuple[dict, ET.Element]:
    response = call_retry(config, "alibaba.icbu.product.schema.render", {
        "param_product_top_publish_request": {"product_id": int(product_id), "language": "en_US"}
    })
    data = response.get("data")
    if failed(response) or not isinstance(data, str):
        raise RuntimeError(f"schema.render failed for {product_id}: {response_refs(response)}")
    return response, ET.fromstring(data)


def build_xml(rendered: ET.Element) -> str:
    sale_prop = rendered.find("./field[@id='saleProp']")
    if sale_prop is None:
        raise RuntimeError("Current rendered Schema lacks saleProp")
    sale_prop = deepcopy(sale_prop)
    color_field = sale_prop.find("./complex-value/field[@id='p-191288010']")
    values = color_field.findall("./values/value") if color_field is not None else []
    found = {str(value.text): str(value.attrib.get("inputValue") or "") for value in values}
    expected = {color_id: row["name"] for color_id, row in TARGET.items()}
    if found != expected:
        raise RuntimeError(f"Unexpected live color IDs/names: {found}")
    for value in values:
        value.attrib["img"] = TARGET[str(value.text)]["image_url"]
    root = ET.Element("itemSchema")
    root.append(sale_prop)
    return ET.tostring(root, encoding="unicode")


def process(config: dict, product_id: str, expected_model: str, apply: bool) -> dict:
    before_response, before = get_product(config, product_id)
    record = {
        "product_id": product_id,
        "expected_model": expected_model,
        "mode": "apply" if apply else "dry-run",
        "before_status": before.get("status"),
        "before_display": before.get("display"),
        "before": response_refs(before_response),
    }
    if product_id == SOURCE_PRODUCT_ID:
        raise RuntimeError("Protected source product cannot be processed")
    if model_number(before) != expected_model or int(before.get("category_id") or 0) != 201334413:
        raise RuntimeError(f"Identity/category mismatch for {product_id}")
    skus = (before.get("product_sku") or {}).get("skus") or []
    if len(skus) != EXPECTED_SKU_COUNT:
        raise RuntimeError(f"Expected {EXPECTED_SKU_COUNT} SKUs for {product_id}")
    if target_state(before):
        record.update(stage="verified_existing", ok=True)
        return record
    live_names = {color_id: str(row.get("system_value_name") or "") for color_id, row in color_rows(before).items()}
    expected_names = {color_id: row["name"] for color_id, row in TARGET.items()}
    if live_names != expected_names:
        raise RuntimeError(f"Unexpected color names for {product_id}: {live_names}")
    if before.get("status") != "approved" or before.get("display") != "Y":
        record.update(stage="auditing_no_resubmit", ok=False)
        return record

    render_response, rendered = render(config, product_id)
    xml = build_xml(rendered)
    record.update(stage="prepared", render=response_refs(render_response), target=TARGET, ok=True)
    if not apply:
        return record

    before_snapshot = normalized_without_color_images(before)
    before_sku_codes = [str(row.get("sku_code") or "") for row in skus]
    update_response = call_retry(config, "alibaba.icbu.product.schema.update", {
        "param_product_top_publish_request": {
            "cat_id": 201334413,
            "language": "en_US",
            "product_id": int(product_id),
            "xml": xml,
        }
    })
    if failed(update_response):
        raise RuntimeError(f"schema.update failed for {product_id}: {response_refs(update_response)}")
    after_response, after = get_product(config, product_id)
    after_skus = (after.get("product_sku") or {}).get("skus") or []
    checks = {
        "identity_ok": model_number(after) == expected_model,
        "target_images_ok": target_state(after),
        "color_names_unchanged": {
            color_id: str(row.get("system_value_name") or "") for color_id, row in color_rows(after).items()
        } == expected_names,
        f"sku_count_{EXPECTED_SKU_COUNT}": len(after_skus) == EXPECTED_SKU_COUNT,
        "sku_codes_unchanged": [str(row.get("sku_code") or "") for row in after_skus] == before_sku_codes,
        "all_non_image_fields_unchanged": normalized_without_color_images(after) == before_snapshot,
    }
    record.update(
        stage="submitted",
        update=response_refs(update_response),
        readback=response_refs(after_response),
        after_status=after.get("status"),
        after_display=after.get("display"),
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
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "results": {row["product_id"]: row["stage"] for row in results}}, ensure_ascii=False))
    return 0 if all(row.get("ok") for row in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
EXPECTED_SKU_COUNT = 55
