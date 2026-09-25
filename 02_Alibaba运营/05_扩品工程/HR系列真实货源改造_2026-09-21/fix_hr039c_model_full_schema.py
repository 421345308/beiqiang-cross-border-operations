"""Fix HR039-C Model Number inside its own complete current Schema."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
OUT = ROOT / "02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21/HR039-C_型号完整Schema修正回执.json"
PRODUCT_ID = 1601943583746
TITLE = "Unisex High Top Knit Sock Sneakers Slip-On EVA Sole EU 35-45 Wholesale OEM Casual Shoes"
TARGET_MODEL = "HR039-C / 8025"


def load_client():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def refs(api, response):
    return {
        "request_id": response.get("request_id"),
        "trace_id": response.get("trace_id") or response.get("_trace_id_"),
        "error": api.api_error(response),
        "biz_success": response.get("biz_success"),
    }


def snapshot(product):
    attrs = {str(row.get("attribute_name")): row.get("value_name") for row in product.get("attributes") or []}
    detail = product.get("struct_detail") or {}
    skus = ((product.get("product_sku") or {}).get("skus") or [])
    prices = sorted({row.get("price") for sku in skus for row in sku.get("bulk_discount_prices") or [] if row.get("price") is not None})
    return {
        "status": product.get("status"),
        "display": product.get("display"),
        "title": product.get("subject"),
        "model": attrs.get("Model Number"),
        "pattern": attrs.get("Pattern Type"),
        "sku_count": len(skus),
        "prices": prices,
        "main_images": len(((product.get("main_image") or {}).get("images") or [])),
        "detail_images": len((((detail.get("detail_image") or {}).get("images")) or [])),
        "company_images": len((((detail.get("company_image") or {}).get("images")) or [])),
    }


api = load_client()
config = api.load_config(Path.home() / ".config/beiqiang/alibaba-openapi.json")
before_response = api.top_call(config, "alibaba.icbu.product.get", {"product_id": PRODUCT_ID, "language": "ENGLISH"})
before = before_response.get("product") or {}
before_snap = snapshot(before)
gates = {
    "approved_online": before_snap["status"] == "approved" and before_snap["display"] == "Y",
    "title_ok": before_snap["title"] == TITLE,
    "old_model_present": before_snap["model"] == "HR039-A / 8025",
    "pattern_ok": before_snap["pattern"] == "Solid",
    "sku_count_ok": before_snap["sku_count"] == 22,
    "price_ok": before_snap["prices"] == ["12.00", "12.50", "12.90"],
    "gallery_ok": (before_snap["main_images"], before_snap["detail_images"], before_snap["company_images"]) == (6, 5, 5),
}
if api.api_error(before_response) or not all(gates.values()):
    raise RuntimeError(f"preflight failed: {gates}; refs={refs(api, before_response)}")

render_response = api.top_call(
    config,
    "alibaba.icbu.product.schema.render",
    {"param_product_top_publish_request": {"product_id": PRODUCT_ID, "language": "en_US"}},
)
xml_before = render_response.get("data")
if api.api_error(render_response) or not isinstance(xml_before, str):
    raise RuntimeError(f"schema.render failed: {refs(api, render_response)}")
schema = ET.fromstring(xml_before)
p3 = schema.find(".//field[@id='p-3']")
value = p3.find("./value") if p3 is not None else None
if value is None or value.get("inputValue") != "HR039-A / 8025":
    raise RuntimeError(f"unexpected p-3: {ET.tostring(p3, encoding='unicode') if p3 is not None else None}")
before_p3_xml = ET.tostring(p3, encoding="unicode")
value.set("inputValue", TARGET_MODEL)
value.text = "-2"

sku_codes = [node.text or "" for node in schema.findall(".//field[@id='skuOuterId']/value")]
if len(sku_codes) != 22 or len(set(sku_codes)) != 22 or not all(code.startswith("HR039-C-8025-") for code in sku_codes):
    raise RuntimeError(f"SKU code gate failed: {sku_codes}")
xml = ET.tostring(schema, encoding="unicode")
update_response = api.top_call(
    config,
    "alibaba.icbu.product.schema.update",
    {"param_product_top_publish_request": {"cat_id": int(before["category_id"]), "language": "en_US", "product_id": PRODUCT_ID, "xml": xml}},
)
if api.api_error(update_response) or update_response.get("biz_success") is False or update_response.get("model") is False:
    raise RuntimeError(f"schema.update failed: {refs(api, update_response)}")

after_response = api.top_call(config, "alibaba.icbu.product.get", {"product_id": PRODUCT_ID, "language": "ENGLISH"})
after = after_response.get("product") or {}
after_snap = snapshot(after)
receipt = {
    "product_id": PRODUCT_ID,
    "method": "full_current_target_schema_change_p3_inputValue_only",
    "before": before_snap,
    "gates": gates,
    "before_p3_xml": before_p3_xml,
    "target_p3_xml": ET.tostring(p3, encoding="unicode"),
    "preserved_sku_count": len(sku_codes),
    "xml_chars": len(xml),
    "xml_sha256": hashlib.sha256(xml.encode("utf-8")).hexdigest(),
    "before_refs": refs(api, before_response),
    "render_refs": refs(api, render_response),
    "update_refs": refs(api, update_response),
    "immediate_readback": after_snap,
    "readback_refs": refs(api, after_response),
    "verified": after_snap["model"] == TARGET_MODEL,
    "accepted_pending_review": after_snap["status"] == "modified" and after_snap["display"] == "N",
}
OUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(receipt, ensure_ascii=False, indent=2))
if not receipt["verified"] and not receipt["accepted_pending_review"]:
    raise RuntimeError("full-schema model fix was neither verified nor accepted for review")
