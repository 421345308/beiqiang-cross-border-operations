"""Read-only status, image, attribute, SKU and inventory check for HR001-B."""

from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG = Path.home() / ".config/beiqiang/alibaba-openapi.json"
PRODUCTS = {"HR001-B": 1601943493004, "HR001-C": 1601943474137}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("listing", choices=sorted(PRODUCTS))
    args = parser.parse_args()
    product_id = PRODUCTS[args.listing]
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
    assert spec and spec.loader
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    config = api.load_config(CONFIG)
    product_reply = api.top_call(config, "alibaba.icbu.product.get", {
        "product_id": product_id, "language": "ENGLISH",
    })
    if api.api_error(product_reply):
        raise RuntimeError(f"product.get: {api.api_error(product_reply)}")
    product = product_reply.get("product") or {}
    attrs = {str(x.get("attribute_name")): x.get("value_name") for x in product.get("attributes") or []}
    skus = (product.get("product_sku") or {}).get("skus") or []
    details = (((product.get("struct_detail") or {}).get("detail_image") or {}).get("images") or [])
    company = (((product.get("struct_detail") or {}).get("company_image") or {}).get("images") or [])
    inventory_reply = api.top_call(config, "alibaba.icbu.product.sku.inventory.get", {
        "product_id": product_id, "language": "en_US",
    })
    inv_result = inventory_reply.get("result") or {}
    if inv_result.get("success") is not True:
        raise RuntimeError(f"inventory.get: {inventory_reply}")
    inventory = inv_result.get("data_list") or []
    if isinstance(inventory, dict):
        inventory = inventory.get("data") or []
    if isinstance(inventory, dict):
        inventory = [inventory]
    receipt = {
        "checked_at": datetime.now().astimezone().isoformat(),
        "product_id": product_id,
        "product_request_id": product_reply.get("request_id"),
        "inventory_request_id": inventory_reply.get("request_id"),
        "status": product.get("status"), "display": product.get("display"),
        "title": product.get("subject"), "model": attrs.get("Model Number"),
        "fit_type": attrs.get("Fit Type"),
        "sku_count": len(skus),
        "sku_code_prefix_ok": len(skus) == 20 and all(
            str(x.get("sku_code", "")).startswith(args.listing + "-9002-") for x in skus
        ),
        "main_image_count": len((product.get("main_image") or {}).get("images") or []),
        "detail_count": len(details),
        "detail_urls": [x.get("image_url") for x in details],
        "company_image_count": len(company),
        "inventory_rows": len(inventory),
        "inventory_values": sorted({int(x["inventory"]) for x in inventory}),
        "video_id": (product.get("main_video") or {}).get("video_id"),
    }
    out = Path(__file__).with_name(f"{args.listing}_9002_提交后实时回读.json")
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
