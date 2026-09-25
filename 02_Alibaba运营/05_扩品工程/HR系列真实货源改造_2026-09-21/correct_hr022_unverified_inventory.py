"""Guarded correction of legacy 999 inventory for the unsourced HR022 family.

Default mode only checks product identity and inventory. --apply subtracts only
verified 999 values and reads all 30 SKUs back; it never creates inventory.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG = Path.home() / ".config/beiqiang/alibaba-openapi.json"
PRODUCTS = {
    "HR022-A": 1601943496879,
    "HR022-B": 1601943496880,
    "HR022-C": 1601943578396,
}


def load_client():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require_inventory(api, response: dict, method: str) -> list[dict]:
    error = api.api_error(response)
    if error:
        raise RuntimeError(f"{method}: {error}")
    result = response.get("result") or {}
    if result.get("success") is not True:
        raise RuntimeError(f"{method}: business result {result}")
    rows = result.get("data_list") or []
    if isinstance(rows, dict):
        rows = rows.get("data") or []
    return rows if isinstance(rows, list) else [rows]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("listing", choices=sorted(PRODUCTS))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    api = load_client()
    config = api.load_config(CONFIG)
    product_id = PRODUCTS[args.listing]
    product_response = api.top_call(config, "alibaba.icbu.product.get", {
        "product_id": product_id, "language": "ENGLISH",
    })
    error = api.api_error(product_response)
    if error:
        raise RuntimeError(f"product.get: {error}")
    product = product_response.get("product") or {}
    skus = (product.get("product_sku") or {}).get("skus") or []
    expected_ids = {int(sku["sku_id"]) for sku in skus}
    if not (
        product.get("status") == "approved"
        and product.get("display") == "Y"
        and len(skus) == len(expected_ids) == 30
        and all(str(sku.get("sku_code", "")).startswith(args.listing + "-") for sku in skus)
    ):
        raise RuntimeError("Product identity/status/SKU guard failed; no inventory write")

    before_response = api.top_call(config, "alibaba.icbu.product.sku.inventory.get", {
        "product_id": product_id, "language": "en_US",
    })
    before = require_inventory(api, before_response, "inventory.get")
    if len(before) != 30 or {int(row["sku_id"]) for row in before} != expected_ids:
        raise RuntimeError("Inventory SKU IDs do not match product.get; no write")
    if any(int(row["inventory"]) not in (0, 999) for row in before):
        raise RuntimeError("Unexpected inventory value; no write")
    if any(row.get("inventory_code") != "CN_LOCAL_01" for row in before):
        raise RuntimeError("Unexpected warehouse code; no write")

    changes = [
        {
            "sku_id": int(row["sku_id"]),
            "inventory_code": row["inventory_code"],
            "inventory": int(row["inventory"]),
            "operate": "sub",
        }
        for row in before if int(row["inventory"]) == 999
    ]
    receipt = {
        "listing": args.listing,
        "product_id": product_id,
        "checked_at": datetime.now().astimezone().isoformat(),
        "mode": "apply" if args.apply else "dry_run",
        "product_request_id": product_response.get("request_id"),
        "before_request_id": before_response.get("request_id"),
        "before_count": len(before),
        "before_values": sorted({int(row["inventory"]) for row in before}),
        "changes": len(changes),
    }
    if args.apply and changes:
        update = api.top_call(config, "alibaba.icbu.product.inventory.update", {
            "request_param": json.dumps({
                "product_id": product_id,
                "inventory_list": changes,
            }, ensure_ascii=False, separators=(",", ":")),
        })
        receipt["update_request_id"] = update.get("request_id")
        receipt["update_trace_id"] = update.get("trace_id") or update.get("_trace_id_")
        receipt["update_error"] = api.api_error(update)
        result = update.get("result") or {}
        if receipt["update_error"] or result.get("success") is not True or str(result.get("data")).lower() != "true":
            raise RuntimeError(f"Inventory update not confirmed: {receipt}")
    if args.apply:
        after_response = api.top_call(config, "alibaba.icbu.product.sku.inventory.get", {
            "product_id": product_id, "language": "en_US",
        })
        after = require_inventory(api, after_response, "inventory.get-after")
        receipt["after_request_id"] = after_response.get("request_id")
        receipt["after_count"] = len(after)
        receipt["after_values"] = sorted({int(row["inventory"]) for row in after})
        receipt["passed"] = len(after) == 30 and all(int(row["inventory"]) == 0 for row in after)
    else:
        receipt["passed"] = len(before) == 30

    out = Path(__file__).with_name(f"{args.listing}_库存校正_{'正式' if args.apply else '预检'}_回执.json")
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
