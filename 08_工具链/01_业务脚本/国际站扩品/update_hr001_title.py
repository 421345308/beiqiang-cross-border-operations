"""Append the missing model suffix to HR001 with a minimal Schema update."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG = Path.home() / ".config/beiqiang/alibaba-openapi.json"
OUT = ROOT / "02_Alibaba运营/05_扩品工程/热榜8款API上架_2026-09-05/HR001标题增量修复回执.json"
PRODUCT_ID = 1601943321794
TITLE = "OEM Breathable Mesh Walking Shoes Lightweight Cushioned Lace Up Casual Sneakers EU 36-45 Model HR001"

spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
api = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(api)
config = api.load_config(CONFIG)
xml = f'<itemSchema><field id="productTitle" name="Product name" type="input"><value>{TITLE}</value></field></itemSchema>'
response = api.top_call(config, "alibaba.icbu.product.schema.update", {
    "param_product_top_publish_request": {
        "cat_id": 201334413,
        "language": "en_US",
        "product_id": PRODUCT_ID,
        "xml": xml,
    }
})
readback = api.top_call(config, "alibaba.icbu.product.get", {"product_id": PRODUCT_ID, "language": "ENGLISH"})
inventory = api.top_call(config, "alibaba.icbu.product.sku.inventory.get", {"product_id": PRODUCT_ID, "language": "en_US"})
values = (inventory.get("result") or {}).get("data_list") or []
receipt = {
    "product_id": str(PRODUCT_ID), "requested_title": TITLE, "update_response": response,
    "readback_title": (readback.get("product") or {}).get("subject"),
    "inventory_values": sorted({int(x.get("inventory") or 0) for x in values}),
}
receipt["passed"] = receipt["readback_title"] == TITLE and receipt["inventory_values"] == [999]
OUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(receipt, ensure_ascii=False, indent=2))
raise SystemExit(0 if receipt["passed"] else 1)
