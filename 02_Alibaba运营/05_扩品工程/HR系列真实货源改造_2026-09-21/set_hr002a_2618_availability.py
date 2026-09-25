"""Set only verified HR002-A/2618 SKUs to the owner's 999 inquiry marker."""
from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
OUT = Path(__file__).with_name("HR002-A_2618_999可询货标记_接口回执.json")
PRODUCT_ID = 1601943305914
PREFIX = "HR002-A-2618-"
EXPECTED_MODEL = "HR002-A / 2618"
EXPECTED_CODES = {
    f"{PREFIX}{color}-{size}"
    for color in ("BLACK", "KHAKI", "DARKBROWN")
    for size in range(39, 49)
}

spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
assert spec and spec.loader
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)
config = api.load_config(Path.home() / ".config/beiqiang/alibaba-openapi.json")


def call(method: str, params: dict) -> dict:
    response = api.top_call(config, method, params)
    error = api.api_error(response)
    if error:
        raise RuntimeError({"method": method, "error": error, "request_id": response.get("request_id")})
    return response


def rows(response: dict) -> list[dict]:
    result = response.get("result") or {}
    if result.get("success") is not True:
        raise RuntimeError({"inventory_business_failure": response.get("request_id"), "result": result})
    found = result.get("data_list") or []
    if isinstance(found, dict):
        found = found.get("data") or []
    if isinstance(found, dict):
        found = [found]
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    formal = call("alibaba.icbu.product.get", {"product_id": PRODUCT_ID, "language": "ENGLISH"})
    product = formal.get("product") or {}
    skus = (product.get("product_sku") or {}).get("skus") or []
    sku_ids = {int(row["sku_id"]) for row in skus}
    codes = {row.get("sku_code") for row in skus}
    attrs = {row.get("attribute_name"): row.get("value_name") for row in product.get("attributes") or []}
    if not (
        product.get("status") in {"modified", "approved"}
        and attrs.get("Model Number") == EXPECTED_MODEL
        and "Model 2618" in str(product.get("subject"))
        and len(skus) == len(sku_ids) == len(codes) == 30
        and codes == EXPECTED_CODES
    ):
        raise RuntimeError({"product_identity_guard_failed": {"status": product.get("status"), "model": attrs.get("Model Number"), "sku_count": len(skus)}})
    if args.apply and (product.get("status"), product.get("display")) != ("approved", "Y"):
        raise RuntimeError("Product is under review; wait for approved/Y before inventory mutation")

    before = call("alibaba.icbu.product.sku.inventory.get", {"product_id": PRODUCT_ID, "language": "en_US"})
    stock = rows(before)
    if len(stock) != 30 or {int(row["sku_id"]) for row in stock} != sku_ids:
        raise RuntimeError("Inventory rows do not exactly match the 30 current 2618 SKUs")
    if any(row.get("inventory_code") != "CN_LOCAL_01" or not 0 <= int(row.get("inventory") or 0) <= 999 for row in stock):
        raise RuntimeError("Unexpected warehouse code or quantity")
    changes = [{
        "sku_id": int(row["sku_id"]),
        "inventory_code": row["inventory_code"],
        "inventory": 999 - int(row["inventory"]),
        "operate": "plus",
    } for row in stock if int(row["inventory"]) < 999]
    receipt = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "apply" if args.apply else "dry_run",
        "product_id": PRODUCT_ID,
        "source_model": "2618",
        "formal_request_id": formal.get("request_id"),
        "status": product.get("status"),
        "display": product.get("display"),
        "before_request_id": before.get("request_id"),
        "sku_count": len(skus),
        "before_values": sorted({int(row["inventory"]) for row in stock}),
        "planned_changes": len(changes),
        "semantics": "999 is an inquiry marker, not actual physical stock",
    }
    if args.apply and changes:
        update = call("alibaba.icbu.product.inventory.update", {
            "request_param": json.dumps({"product_id": PRODUCT_ID, "inventory_list": changes}, separators=(",", ":"))
        })
        model = update.get("result") or {}
        receipt["update_request_id"] = update.get("request_id")
        receipt["update_result"] = {"success": model.get("success"), "data": model.get("data")}
        if model.get("success") is not True or str(model.get("data")).lower() != "true":
            raise RuntimeError({"inventory_update_not_accepted": receipt})
    if args.apply:
        after = call("alibaba.icbu.product.sku.inventory.get", {"product_id": PRODUCT_ID, "language": "en_US"})
        final = rows(after)
        receipt["after_request_id"] = after.get("request_id")
        receipt["after_values"] = sorted({int(row["inventory"]) for row in final})
        receipt["passed"] = len(final) == 30 and all(int(row["inventory"]) == 999 for row in final)
    else:
        receipt["passed"] = True
    OUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))
    if not receipt["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
