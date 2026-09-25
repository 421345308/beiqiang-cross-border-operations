"""Set HR001-B/9002 SKU availability marker to 999 after identity checks."""

from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG = Path.home() / ".config/beiqiang/alibaba-openapi.json"
PRODUCT_ID = 1601943493004
LISTING = "HR001-B"
SKU_PREFIX = "HR001-B-9002-"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
    assert spec and spec.loader
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    config = api.load_config(CONFIG)

    product_reply = api.top_call(config, "alibaba.icbu.product.get", {
        "product_id": PRODUCT_ID, "language": "ENGLISH",
    })
    if product_reply.get("error_response"):
        raise RuntimeError(product_reply["error_response"])
    product = product_reply.get("product") or {}
    skus = (product.get("product_sku") or {}).get("skus") or []
    sku_ids = {int(x["sku_id"]) for x in skus}
    if not (
        (product.get("status"), product.get("display")) in (("approved", "Y"), ("modified", "N"))
        and "9002" in str(product.get("subject", ""))
        and len(skus) == len(sku_ids) == 20
        and all(str(x.get("sku_code", "")).startswith(SKU_PREFIX) for x in skus)
    ):
        raise RuntimeError(f"{LISTING}/9002 identity, status, or SKU guard failed")
    if args.apply and (product.get("status"), product.get("display")) != ("approved", "Y"):
        raise RuntimeError("Product is under review; no inventory mutation until approved/Y")

    before_reply = api.top_call(config, "alibaba.icbu.product.sku.inventory.get", {
        "product_id": PRODUCT_ID, "language": "en_US",
    })
    result = before_reply.get("result") or {}
    if result.get("success") is not True:
        raise RuntimeError(f"inventory.get failed: {before_reply}")
    rows = result.get("data_list") or []
    if isinstance(rows, dict):
        rows = rows.get("data") or []
    if isinstance(rows, dict):
        rows = [rows]
    if rows and (len(rows) != 20 or {int(x["sku_id"]) for x in rows} != sku_ids):
        raise RuntimeError("Partial or mismatched inventory rows")
    if any(int(x["inventory"]) < 0 or int(x["inventory"]) > 999 for x in rows):
        raise RuntimeError("Unexpected inventory exceeds target marker")
    if any(x.get("inventory_code") != "CN_LOCAL_01" for x in rows):
        raise RuntimeError("Missing inventory warehouse code")
    if not rows:
        raise RuntimeError("Inventory records are absent; use current Schema SKU stock fields, not inventory.update")
    changes = [{
        "sku_id": int(x["sku_id"]),
        "inventory_code": x["inventory_code"],
        "inventory": 999 - int(x["inventory"]),
        "operate": "plus",
    } for x in rows if int(x["inventory"]) < 999]

    receipt = {
        "listing": LISTING, "source_model": "9002", "product_id": PRODUCT_ID,
        "checked_at": datetime.now().astimezone().isoformat(),
        "mode": "apply" if args.apply else "dry_run",
        "product_request_id": product_reply.get("request_id"),
        "inventory_before_request_id": before_reply.get("request_id"),
        "sku_count": len(rows), "before_values": sorted({int(x["inventory"]) for x in rows}),
        "planned_changes": len(changes),
        "marker_semantics": "999 is a seller-side availability marker, not actual on-hand inventory",
    }
    if args.apply and changes:
        update = api.top_call(config, "alibaba.icbu.product.inventory.update", {
            "request_param": json.dumps({
                "product_id": PRODUCT_ID, "inventory_list": changes,
            }, ensure_ascii=False, separators=(",", ":")),
        })
        receipt["update_request_id"] = update.get("request_id")
        if not (update.get("result") or {}).get("success") or str((update.get("result") or {}).get("data")).lower() != "true":
            raise RuntimeError(f"Inventory update not confirmed: {update}")
    if args.apply:
        after_reply = api.top_call(config, "alibaba.icbu.product.sku.inventory.get", {
            "product_id": PRODUCT_ID, "language": "en_US",
        })
        after_result = after_reply.get("result") or {}
        if after_result.get("success") is not True:
            raise RuntimeError(f"inventory.get-after failed: {after_reply}")
        after = after_result.get("data_list") or []
        if isinstance(after, dict):
            after = after.get("data") or []
        if isinstance(after, dict):
            after = [after]
        receipt["inventory_after_request_id"] = after_reply.get("request_id")
        receipt["after_values"] = sorted({int(x["inventory"]) for x in after})
        receipt["passed"] = len(after) == 20 and all(int(x["inventory"]) == 999 for x in after)
    else:
        receipt["passed"] = True
    out = Path(__file__).with_name(f"{LISTING}_9002_999可询货标记_{'正式' if args.apply else '预检'}_回执.json")
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
