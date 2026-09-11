"""Synchronize HR001-HR008 SKU inventory to the verified store baseline.

The Schema publish endpoint currently drops submitted skuStock values to zero.
This script uses Alibaba's dedicated inventory API, calculates a delta from the
live value, applies only the required plus/sub operation, and verifies the
result.  It is therefore safe to rerun.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import time
from pathlib import Path


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG = Path.home() / ".config/beiqiang/alibaba-openapi.json"
OUTPUT_DIR = ROOT / "02_Alibaba运营/05_扩品工程/热榜8款API上架_2026-09-05"
TARGET = 999
PRODUCTS = {
    "HR001": 1601943321794,
    "HR002": 1601943305914,
    "HR003": 1601943312845,
    "HR004": 1601943397351,
    "HR005": 1601943335751,
    "HR006": 1601943439124,
    "HR007": 1601943463020,
    "HR008": 1601943348656,
}


def products_for_variant(variant: str) -> dict[str, int]:
    if variant == "A":
        return {f"{model}-A": product_id for model, product_id in PRODUCTS.items()}
    receipt = json.loads((OUTPUT_DIR / f"publish_{variant}_receipt.json").read_text(encoding="utf-8"))
    return {row["listing_id"]: int(row["submit"]["product_id"]) for row in receipt["products"]}


def load_client():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def call_retry(api, config, method, params, attempts=4):
    last = None
    for attempt in range(1, attempts + 1):
        try:
            response = api.top_call(config, method, params)
            if "error_response" not in response:
                return response
            last = response
        except Exception as exc:  # network retry only; preserved in receipt
            last = {"local_error": str(exc)}
        time.sleep(1.5 * attempt)
    return last


def rows(response):
    result = response.get("result") or {}
    value = result.get("data_list") or []
    if isinstance(value, dict):
        value = value.get("data") or []
    return value if isinstance(value, list) else [value]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=["A", "B", "C"], default="A")
    args = parser.parse_args()
    api = load_client()
    config = api.load_config(CONFIG)
    receipt = {"target_inventory": TARGET, "products": []}
    for model, product_id in products_for_variant(args.variant).items():
        before_response = call_retry(
            api, config, "alibaba.icbu.product.sku.inventory.get",
            {"product_id": product_id, "language": "en_US"},
        )
        before = rows(before_response)
        changes = []
        for item in before:
            current = int(item.get("inventory") or 0)
            delta = TARGET - current
            if not delta:
                continue
            changes.append({
                "sku_id": int(item["sku_id"]),
                "inventory_code": item.get("inventory_code") or "CN_LOCAL_01",
                "inventory": abs(delta),
                "operate": "plus" if delta > 0 else "sub",
            })
        update_response = None
        if changes:
            request_param = json.dumps(
                {"product_id": product_id, "inventory_list": changes},
                ensure_ascii=False, separators=(",", ":"),
            )
            update_response = call_retry(
                api, config, "alibaba.icbu.product.inventory.update",
                {"request_param": request_param},
            )
        after_response = call_retry(
            api, config, "alibaba.icbu.product.sku.inventory.get",
            {"product_id": product_id, "language": "en_US"},
        )
        after = rows(after_response)
        passed = len(after) == 30 and all(int(x.get("inventory") or 0) == TARGET for x in after)
        receipt["products"].append({
            "model": model,
            "product_id": product_id,
            "sku_count": len(after),
            "changed_sku_count": len(changes),
            "before_values": sorted({int(x.get("inventory") or 0) for x in before}),
            "after_values": sorted({int(x.get("inventory") or 0) for x in after}),
            "update_response": update_response,
            "passed": passed,
        })
        print(model, len(changes), passed, flush=True)
    receipt["all_passed"] = all(x["passed"] for x in receipt["products"])
    OUT = OUTPUT_DIR / f"库存同步回执_{args.variant}.json"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUT)
    raise SystemExit(0 if receipt["all_passed"] else 1)


if __name__ == "__main__":
    main()
