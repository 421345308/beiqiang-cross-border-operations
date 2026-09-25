"""Fix only HR039-C's Model Number after the 8025 migration."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
OUT = ROOT / "02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21/HR039-C_型号修正_API回执.json"
PRODUCT_ID = 1601943583746
TARGET_MODEL = "HR039-C / 8025"

spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
api = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(api)
config = api.load_config(Path.home() / ".config/beiqiang/alibaba-openapi.json")

before_response = api.top_call(config, "alibaba.icbu.product.get", {"product_id": PRODUCT_ID, "language": "ENGLISH"})
before = before_response.get("product") or {}
attrs_before = {str(row.get("attribute_name")): row.get("value_name") for row in before.get("attributes") or []}
if before.get("status") != "approved" or before.get("display") != "Y" or attrs_before.get("Model Number") != "HR039-A / 8025":
    raise RuntimeError(f"unexpected preflight state: {before.get('status')}, {attrs_before.get('Model Number')}")

xml = (
    '<itemSchema><field id="p-3" name="Model Number" type="input">'
    f'<value inputValue="{TARGET_MODEL}">-2</value>'
    '</field></itemSchema>'
)
update = api.top_call(
    config,
    "alibaba.icbu.product.schema.update",
    {"param_product_top_publish_request": {"cat_id": 201334413, "language": "en_US", "product_id": PRODUCT_ID, "xml": xml}},
)
if api.api_error(update) or update.get("biz_success") is False or update.get("model") is False:
    raise RuntimeError({"error": api.api_error(update), "response": update})

readback = api.top_call(config, "alibaba.icbu.product.get", {"product_id": PRODUCT_ID, "language": "ENGLISH"})
product = readback.get("product") or {}
attrs_after = {str(row.get("attribute_name")): row.get("value_name") for row in product.get("attributes") or []}
receipt = {
    "product_id": PRODUCT_ID,
    "model_before": attrs_before.get("Model Number"),
    "model_target": TARGET_MODEL,
    "model_after": attrs_after.get("Model Number"),
    "update_mode": "incremental_single_field_inputValue",
    "status": product.get("status"),
    "display": product.get("display"),
    "title": product.get("subject"),
    "url": product.get("pc_detail_url"),
    "update_request_id": update.get("request_id"),
    "update_trace_id": update.get("trace_id") or update.get("_trace_id_"),
    "readback_request_id": readback.get("request_id"),
    "readback_trace_id": readback.get("trace_id") or readback.get("_trace_id_"),
    "verified": attrs_after.get("Model Number") == TARGET_MODEL,
    "accepted_pending_review": product.get("status") == "modified" and product.get("display") == "N",
}
OUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(receipt, ensure_ascii=False, indent=2))
if not receipt["verified"] and not receipt["accepted_pending_review"]:
    raise RuntimeError("HR039-C model fix was neither verified nor accepted for review")
