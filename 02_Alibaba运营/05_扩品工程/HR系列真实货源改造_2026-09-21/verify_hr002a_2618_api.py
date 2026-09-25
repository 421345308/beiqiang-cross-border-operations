"""Read-only formal and inventory checks after the HR002-A/2618 update."""
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
OUT = Path(__file__).with_name("HR002-A_2618_提交后OpenAPI核验.json")
PRODUCT_ID = 1601943305914
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


formal = call("alibaba.icbu.product.get", {"product_id": PRODUCT_ID, "language": "ENGLISH"})
inventory = call("alibaba.icbu.product.sku.inventory.get", {"product_id": PRODUCT_ID, "language": "en_US"})
product = formal.get("product") or {}
attrs = {str(row.get("attribute_name")): row.get("value_name") for row in product.get("attributes") or []}
sku = product.get("product_sku") or {}
axes = {row.get("attribute_name"): [item.get("system_value_name") for item in row.get("values") or []]
        for row in sku.get("sku_attributes") or []}
skus = sku.get("skus") or []
inv_rows = (inventory.get("result") or {}).get("data_list") or []
if isinstance(inv_rows, dict):
    inv_rows = inv_rows.get("data") or []
prices = sorted({float(row.get("price")) for item in skus for row in item.get("bulk_discount_prices") or [] if row.get("price") is not None})
detail = product.get("struct_detail") or {}
result = {
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "product_id": PRODUCT_ID,
    "formal_request_id": formal.get("request_id"),
    "inventory_request_id": inventory.get("request_id"),
    "status": product.get("status"),
    "display": product.get("display"),
    "title": product.get("subject"),
    "attributes": attrs,
    "axes": axes,
    "sku_count": len(skus),
    "sku_codes": [item.get("sku_code") for item in skus],
    "price_values": prices,
    "main_images": (product.get("main_image") or {}).get("images") or [],
    "detail_images": ((detail.get("detail_image") or {}).get("images") or []),
    "company_images": ((detail.get("company_image") or {}).get("images") or []),
    "inventory_rows": inv_rows,
    "inventory_values": sorted({int(item.get("inventory") or 0) for item in inv_rows}),
}
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({
    "status": result["status"], "display": result["display"],
    "model": attrs.get("Model Number"), "colors": axes.get("Color"),
    "sizes": axes.get("EUR Size"), "sku_count": len(skus),
    "prices": prices, "inventory_rows": len(inv_rows),
    "inventory_values": result["inventory_values"],
    "detail_count": len(result["detail_images"]),
    "company_count": len(result["company_images"]),
    "formal_request_id": result["formal_request_id"],
    "inventory_request_id": result["inventory_request_id"],
}, ensure_ascii=False, indent=2))
