"""Clear only the legacy 999 inventory on one explicitly selected HR018 link.

This does not publish a new product or change its other fields. Readback gates
make reruns safe after an uncertain or partially applied API response.
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
    "HR018-A": 1601943561380,
    "HR018-B": 1601943555428,
    "HR018-C": 1601943607120,
}


def load_client():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require_result(response: dict, method: str) -> dict:
    if "error_response" in response or "error" in response:
        raise RuntimeError(f"{method}: {response.get('error_response') or response.get('error')}")
    result = response.get("result") or {}
    if result.get("success") is not True:
        raise RuntimeError(f"{method}: business result {result}")
    return result


def inventory_rows(result: dict) -> list[dict]:
    rows = result.get("data_list") or []
    if isinstance(rows, dict):
        rows = rows.get("data") or []
    return rows if isinstance(rows, list) else [rows]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("listing", choices=sorted(PRODUCTS))
    parser.add_argument("--apply", action="store_true", help="Perform the exact inventory reduction")
    args = parser.parse_args()

    api = load_client()
    config = api.load_config(CONFIG)
    product_id = PRODUCTS[args.listing]
    product_response = api.top_call(config, "alibaba.icbu.product.get", {
        "product_id": product_id, "language": "ENGLISH",
    })
    if "error_response" in product_response:
        raise RuntimeError(product_response["error_response"])
    product = product_response.get("product") or {}
    skus = (product.get("product_sku") or {}).get("skus") or []
    expected_ids = {int(row["sku_id"]) for row in skus}
    if not (
        product.get("status") == "approved"
        and product.get("display") == "Y"
        and len(skus) == len(expected_ids) == 30
        and all(str(row.get("sku_code", "")).startswith(args.listing + "-") for row in skus)
    ):
        raise RuntimeError("Product identity/status/SKU guard failed; no inventory write")

    before_response = api.top_call(config, "alibaba.icbu.product.sku.inventory.get", {
        "product_id": product_id, "language": "en_US",
    })
    before = inventory_rows(require_result(before_response, "inventory.get"))
    if len(before) != 30 or {int(x["sku_id"]) for x in before} != expected_ids:
        raise RuntimeError("Inventory SKU IDs do not match product.get; no write")
    if any(int(x["inventory"]) not in (0, 999) for x in before):
        raise RuntimeError("Inventory changed from the expected 0/999 state; no write")
    if any(x.get("inventory_code") != "CN_LOCAL_01" for x in before):
        raise RuntimeError("Unexpected warehouse code; no write")

    changes = [
        {
            "sku_id": int(x["sku_id"]),
            "inventory_code": x["inventory_code"],
            "inventory": int(x["inventory"]),
            "operate": "sub",
        }
        for x in before if int(x["inventory"]) > 0
    ]
    receipt = {
        "listing": args.listing,
        "product_id": product_id,
        "checked_at": datetime.now().astimezone().isoformat(),
        "product_request_id": product_response.get("request_id"),
        "inventory_before_request_id": before_response.get("request_id"),
        "before_count": len(before),
        "before_values": sorted({int(x["inventory"]) for x in before}),
        "changes": len(changes),
        "mode": "apply" if args.apply else "dry_run",
    }
    if args.apply and changes:
        update = api.top_call(config, "alibaba.icbu.product.inventory.update", {
            "request_param": json.dumps({
                "product_id": product_id,
                "inventory_list": changes,
            }, ensure_ascii=False, separators=(",", ":")),
        })
        receipt["update_response"] = update
        if not (update.get("result") or {}).get("success") or str((update.get("result") or {}).get("data")).lower() != "true":
            raise RuntimeError(f"Inventory update not confirmed: {update}")
    if args.apply:
        after_response = api.top_call(config, "alibaba.icbu.product.sku.inventory.get", {
            "product_id": product_id, "language": "en_US",
        })
        after = inventory_rows(require_result(after_response, "inventory.get-after"))
        receipt["inventory_after_request_id"] = after_response.get("request_id")
        receipt["after_count"] = len(after)
        receipt["after_values"] = sorted({int(x["inventory"]) for x in after})
        receipt["passed"] = len(after) == 30 and all(int(x["inventory"]) == 0 for x in after)
    else:
        receipt["passed"] = len(changes) == 30

    out = Path(__file__).with_name(f"{args.listing}_库存校正_{'正式' if args.apply else '预检'}_回执.json")
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in receipt.items() if k != "update_response"}, ensure_ascii=False))
    print(out)
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
