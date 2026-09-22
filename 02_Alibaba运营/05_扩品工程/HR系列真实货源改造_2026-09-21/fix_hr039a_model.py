"""Fix HR039-A's display model without re-cloning another product schema."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
OUT = ROOT / "02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21/HR039-A_型号修正_API回执.json"
PRODUCT_ID = 1601943650395
TARGET_MODEL = "HR039-A / 8025"

spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
api = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(api)
config = api.load_config(Path.home() / ".config/beiqiang/alibaba-openapi.json")

before_response = api.top_call(
    config,
    "alibaba.icbu.product.get",
    {"product_id": PRODUCT_ID, "language": "ENGLISH"},
)
before_product = before_response.get("product") or {}
model_before = next(
    (row.get("value_name") for row in before_product.get("attributes", []) if row.get("attribute_name") == "Model Number"),
    None,
)

# The official update guide specifies incremental updates: send only fields
# that should change. For an input-type category property, the typed value is
# held in inputValue while the node text remains the custom-value marker -2.
xml = (
    '<itemSchema>'
    '<field id="p-3" name="Model Number" type="input">'
    f'<value inputValue="{TARGET_MODEL}">-2</value>'
    '</field>'
    '</itemSchema>'
)
update = api.top_call(
    config,
    "alibaba.icbu.product.schema.update",
    {
        "param_product_top_publish_request": {
            "cat_id": 201334413,
            "language": "en_US",
            "product_id": PRODUCT_ID,
            "xml": xml,
        }
    },
)
error = api.api_error(update)
if error or update.get("biz_success") is False or update.get("model") is False:
    raise RuntimeError({"error": error, "response": update})

readback = api.top_call(
    config,
    "alibaba.icbu.product.get",
    {"product_id": PRODUCT_ID, "language": "ENGLISH"},
)
product = readback.get("product") or {}
model_after = next(
    (row.get("value_name") for row in product.get("attributes", []) if row.get("attribute_name") == "Model Number"),
    None,
)
receipt = {
    "product_id": PRODUCT_ID,
    "model_before": model_before,
    "model_target": TARGET_MODEL,
    "model_after": model_after,
    "update_mode": "incremental_single_field",
    "status": product.get("status"),
    "display": product.get("display"),
    "url": product.get("pc_detail_url"),
    "update_request_id": update.get("request_id"),
    "update_trace_id": update.get("trace_id") or update.get("_trace_id_"),
    "readback_request_id": readback.get("request_id"),
    "readback_trace_id": readback.get("trace_id") or readback.get("_trace_id_"),
    "verified": model_after == TARGET_MODEL,
}
OUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(receipt, ensure_ascii=False, indent=2))
if not receipt["verified"]:
    raise RuntimeError("Model fix did not verify")
