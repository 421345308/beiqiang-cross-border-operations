"""Submit HR001-A's verified detail gallery and remove the unsupported Fit Type.

The seller UI can save these edits as a draft, but its newer SKU-stock validator
blocks submission of this pre-existing opportunity product.  This script uses the
authorized full current Schema and changes only detailImage and
customMoreProperty, leaving the 20-SKU commercial structure untouched.
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
CONFIG = Path.home() / ".config/beiqiang/alibaba-openapi.json"
MANIFEST = PROJECT / "HR001_9002_最终图片绑定清单.json"
OUT = PROJECT / "HR001-A_详情与FitType_OpenAPI正式提交回执_2026-09-22.json"
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
    attrs = {str(x.get("attribute_name")): x.get("value_name") for x in product.get("attributes") or []}
    detail = (((product.get("struct_detail") or {}).get("detail_image") or {}).get("images") or [])
    return {
        "status": product.get("status"),
        "display": product.get("display"),
        "title": product.get("subject"),
        "model": attrs.get("Model Number"),
        "fit_type": attrs.get("Fit Type"),
        "sku_count": len(((product.get("product_sku") or {}).get("skus") or [])),
        "main_count": len(((product.get("main_image") or {}).get("images") or [])),
        "detail_count": len(detail),
        "detail_urls": [x.get("image_url") for x in detail],
        "company_count": len((((product.get("struct_detail") or {}).get("company_image") or {}).get("images") or [])),
        "video_id": ((product.get("main_video") or {}).get("video_id")),
    }


def gallery_group(gallery_id: str, roles: list[str], assets: dict[str, dict], text: str | None = None):
    group = ET.Element("complex-values")
    images = ET.SubElement(group, "field", {"id": "images", "type": "multiComplex"})
    for role in roles:
        filename = Path(assets[role]["url"].split("?", 1)[0]).name
        image = ET.SubElement(images, "complex-values")
        image_url = ET.SubElement(image, "field", {"id": "imageURL", "type": "input"})
        ET.SubElement(image_url, "value").text = f"//sc04.alicdn.com/kf/{filename}"
        if text:
            general = ET.SubElement(image, "field", {"id": "generalText", "type": "input"})
            ET.SubElement(general, "value").text = text
    gallery = ET.SubElement(group, "field", {"id": "gallery", "type": "singleCheck"})
    ET.SubElement(gallery, "value").text = gallery_id
    return group


def main():
    api = load_client()
    config = api.load_config(CONFIG)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    assets = {x["role"]: x for x in manifest["items"]}
    expected_roles = [
        "D1_product_overview", "D2_verified_specs", "D3_colors_sizes",
        "D4_price_quote", "D5_oem_project_inputs",
    ]
    expected_tokens = sorted(Path(assets[x]["url"].split("?", 1)[0]).stem for x in expected_roles)

    before_response = api.top_call(config, "alibaba.icbu.product.get", {"product_id": PRODUCT_ID, "language": "ENGLISH"})
    before = before_response.get("product") or {}
    before_snap = snapshot(before)
    gates = {
        "approved_online": before_snap["status"] == "approved" and before_snap["display"] == "Y",
        "title_ok": before_snap["title"] == TITLE,
        "model_ok": before_snap["model"] == MODEL,
        "sku_count_ok": before_snap["sku_count"] == 20,
        "main_company_ok": (before_snap["main_count"], before_snap["company_count"]) == (6, 5),
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
    custom_field = schema.find("./field[@id='customMoreProperty']")
    if detail_field is None or custom_field is None:
        raise RuntimeError("required detailImage/customMoreProperty field missing")
    for node in list(detail_field.findall("./complex-values")):
        detail_field.remove(node)
    for index, group in enumerate([
        gallery_group("300", ["D2_verified_specs"], assets, "Verified specifications for source model 9002"),
        gallery_group("350", ["D1_product_overview", "D4_price_quote", "D5_oem_project_inputs"], assets),
        gallery_group("150", ["D3_colors_sizes"], assets),
    ]):
        detail_field.insert(index, group)

    for node in list(custom_field.findall("./complex-value")):
        custom_field.remove(node)
    custom_field.insert(0, ET.Element("complex-value"))

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
    after_snap = snapshot(after_response.get("product") or {})
    actual_tokens = sorted(Path(str(x or "").split("?", 1)[0]).stem.split("_")[0] for x in after_snap["detail_urls"])
    receipt = {
        "product_id": PRODUCT_ID,
        "method": "full_current_schema_detail_replace_and_custom_property_clear",
        "before": before_snap,
        "gates": gates,
        "expected_detail_tokens": expected_tokens,
        "submitted_xml_chars": len(xml),
        "submitted_xml_sha256": hashlib.sha256(xml.encode("utf-8")).hexdigest(),
        "before_refs": refs(api, before_response),
        "render_refs": refs(api, render_response),
        "update_refs": refs(api, update_response),
        "immediate_readback": after_snap,
        "actual_detail_tokens": actual_tokens,
        "readback_refs": refs(api, after_response),
        "submitted_for_review": after_snap["status"] == "modified" and after_snap["display"] == "N",
    }
    OUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if not receipt["submitted_for_review"]:
        raise RuntimeError("update was not accepted into the modified/N review state")


if __name__ == "__main__":
    main()
