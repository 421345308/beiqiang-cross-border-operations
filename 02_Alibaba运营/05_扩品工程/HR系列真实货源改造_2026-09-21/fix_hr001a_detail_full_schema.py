"""Replace HR001-A detail images inside its complete current Schema.

Run only while the product is approved/Y. The script preserves every current
field except the detailImage value groups.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
PROJECT = ROOT / r"02_Alibaba运营\05_扩品工程\HR系列真实货源改造_2026-09-21"
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
MANIFEST = PROJECT / "HR001_9002_最终图片绑定清单.json"
OUT = PROJECT / "HR001-A_9002_详情完整Schema修复回执.json"
PRODUCT_ID = 1601943321794
TITLE = "Wholesale Men's Knit Slip-On Walking Shoes EVA Sole EU 38-47 Model 9002 for Importers"
MODEL = "HR001-A / 9002"


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
    detail = (((product.get("struct_detail") or {}).get("detail_image") or {}).get("images") or [])
    skus = ((product.get("product_sku") or {}).get("skus") or [])
    return {
        "status": product.get("status"),
        "display": product.get("display"),
        "title": product.get("subject"),
        "model": attrs.get("Model Number"),
        "fit_type": attrs.get("Fit Type"),
        "sku_count": len(skus),
        "main_count": len(((product.get("main_image") or {}).get("images") or [])),
        "detail_count": len(detail),
        "detail_urls": [row.get("image_url") for row in detail],
        "company_count": len((((product.get("struct_detail") or {}).get("company_image") or {}).get("images") or [])),
    }


api = load_client()
config = api.load_config(Path.home() / ".config/beiqiang/alibaba-openapi.json")
manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
assets = {row["role"]: row for row in manifest["items"]}

before_response = api.top_call(config, "alibaba.icbu.product.get", {"product_id": PRODUCT_ID, "language": "ENGLISH"})
before = before_response.get("product") or {}
before_snap = snapshot(before)
gates = {
    "approved_online": before_snap["status"] == "approved" and before_snap["display"] == "Y",
    "title_ok": before_snap["title"] == TITLE,
    "model_ok": before_snap["model"] == MODEL,
    "sku_count_ok": before_snap["sku_count"] == 20,
    "main_and_company_ok": (before_snap["main_count"], before_snap["company_count"]) == (6, 5),
    "old_detail_count_confirmed": before_snap["detail_count"] == 4,
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
detail_field = schema.find("./field[@id='detailImage']")
if detail_field is None:
    raise RuntimeError("detailImage missing from full Schema")
for node in list(detail_field.findall("./complex-values")):
    detail_field.remove(node)

groups = [
    ("300", ["D2_verified_specs"], "Verified facts for source model 9002"),
    ("350", ["D1_product_overview", "D3_colors_sizes", "D4_price_quote", "D5_oem_project_inputs"], None),
]
expected_tokens = []
for index, (gallery_id, roles, general_text) in enumerate(groups):
    group = ET.Element("complex-values")
    images = ET.SubElement(group, "field", {"id": "images", "type": "multiComplex"})
    for role in roles:
        filename = Path(assets[role]["url"].split("?", 1)[0]).name
        expected_tokens.append(Path(filename).stem)
        image = ET.SubElement(images, "complex-values")
        image_url = ET.SubElement(image, "field", {"id": "imageURL", "type": "input"})
        ET.SubElement(image_url, "value").text = f"//sc04.alicdn.com/kf/{filename}"
        if general_text:
            general = ET.SubElement(image, "field", {"id": "generalText", "type": "input"})
            ET.SubElement(general, "value").text = general_text
    gallery = ET.SubElement(group, "field", {"id": "gallery", "type": "singleCheck"})
    ET.SubElement(gallery, "value").text = gallery_id
    detail_field.insert(index, group)

xml = ET.tostring(schema, encoding="unicode")
update_response = api.top_call(
    config,
    "alibaba.icbu.product.schema.update",
    {"param_product_top_publish_request": {
        "cat_id": int(before["category_id"]),
        "language": "en_US",
        "product_id": PRODUCT_ID,
        "xml": xml,
    }},
)
if api.api_error(update_response) or update_response.get("biz_success") is False or update_response.get("model") is False:
    raise RuntimeError(f"schema.update failed: {refs(api, update_response)}")

after_response = api.top_call(config, "alibaba.icbu.product.get", {"product_id": PRODUCT_ID, "language": "ENGLISH"})
after = after_response.get("product") or {}
after_snap = snapshot(after)
actual_tokens = [Path(str(url or "").split("?", 1)[0]).stem.split("_")[0] for url in after_snap["detail_urls"]]
receipt = {
    "product_id": PRODUCT_ID,
    "method": "full_current_target_schema_replace_detailImage_only",
    "before": before_snap,
    "gates": gates,
    "expected_tokens": sorted(expected_tokens),
    "xml_chars": len(xml),
    "xml_sha256": hashlib.sha256(xml.encode("utf-8")).hexdigest(),
    "before_refs": refs(api, before_response),
    "render_refs": refs(api, render_response),
    "update_refs": refs(api, update_response),
    "immediate_readback": after_snap,
    "actual_tokens": sorted(actual_tokens),
    "readback_refs": refs(api, after_response),
    "verified": len(actual_tokens) == 5 and set(actual_tokens) == set(expected_tokens),
    "accepted_pending_review": after_snap["status"] == "modified" and after_snap["display"] == "N",
}
OUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(receipt, ensure_ascii=False, indent=2))
if not receipt["verified"] and not receipt["accepted_pending_review"]:
    raise RuntimeError("full-schema detail fix was neither verified nor accepted for review")
