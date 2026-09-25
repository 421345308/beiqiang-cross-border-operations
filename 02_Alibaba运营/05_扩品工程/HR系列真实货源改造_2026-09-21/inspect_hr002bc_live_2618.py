"""Read-only formal product and inventory status for the two HR002 sibling links."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
OUTPUT = Path(__file__).with_name("HR002-BC_换款前正式字段核验.json")
PRODUCTS = {"B": 1601943393550, "C": 1601943419438}

spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
assert spec and spec.loader
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)
config = api.load_config(Path.home() / ".config/beiqiang/alibaba-openapi.json")


def call(method, params):
    result = api.top_call(config, method, params)
    error = api.api_error(result)
    if error:
        raise RuntimeError({"method": method, "error": error, "request_id": result.get("request_id")})
    return result


rows = {}
for variant, product_id in PRODUCTS.items():
    result = call("alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
    product = result.get("product") or {}
    attrs = {x.get("attribute_name"): x.get("value_name") for x in product.get("attributes") or []}
    sku = (product.get("product_sku") or {}).get("skus") or []
    rows[variant] = {
        "product_id": product_id,
        "request_id": result.get("request_id"),
        "status": product.get("status"), "display": product.get("display"),
        "title": product.get("subject"), "category_id": product.get("category_id"),
        "model": attrs.get("Model Number"), "attributes": attrs,
        "sku_count": len(sku),
        "sku_codes": [x.get("sku_code") for x in sku],
        "main_images": (product.get("main_image") or {}).get("images") or [],
        "detail_images": (product.get("product_details") or {}).get("detail_image") or [],
        "product_desc_type": (product.get("product_details") or {}).get("product_desc_type"),
    }

OUTPUT.write_text(json.dumps({"timestamp_utc": datetime.now(timezone.utc).isoformat(), "products": rows},
                             ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({v: {k: row[k] for k in ("product_id", "status", "display", "title", "model", "sku_count")}
                  for v, row in rows.items()}, ensure_ascii=False, indent=2))
