"""Replace HR002-A legacy details and unsupported attributes through full Schema.

The request keeps the confirmed store packaging baseline (0.5 kg,
34 x 23 x 13 cm) and the existing structured opportunity-product lead-time
baseline.  It changes only the legacy product attributes, custom Fit Type and
the product detail gallery; the already verified S6077 title, gallery, SKUs,
prices, video and company section stay untouched.
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
MAPPING = PROJECT / "HR002_S6077_图片银行映射.json"
OUT = PROJECT / "HR002-A_详情与旧属性_OpenAPI正式提交回执_2026-09-23.json"
PRODUCT_ID = 1601943305914
TITLE = "Wholesale Men's Retro Mesh Lace-Up Walking Shoes Casual Sneakers EU 39-48 Model S6077"
MODEL = "HR002-A / S6077"

# These values came from the retired concept shoe and have no S6077 supplier evidence.
LEGACY_PROP_IDS = {
    "p-191290426": "Outsole Material / Rubber",
    "p-20700": "Midsole Material / EVA",
    "p-191290430": "Lining Material / Mesh",
    "p-210200060": "Feature / Breathable + Light Weight",
    "p-191288212": "Season / All Seasons",
}


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
    attrs = {}
    for item in product.get("attributes") or []:
        attrs.setdefault(str(item.get("attribute_name")), []).append(item.get("value_name"))
    detail = (((product.get("struct_detail") or {}).get("detail_image") or {}).get("images") or [])
    return {
        "status": product.get("status"),
        "display": product.get("display"),
        "title": product.get("subject"),
        "model": (attrs.get("Model Number") or [None])[0],
        "attributes": attrs,
        "sku_count": len(((product.get("product_sku") or {}).get("skus") or [])),
        "main_count": len(((product.get("main_image") or {}).get("images") or [])),
        "detail_count": len(detail),
        "detail_urls": [x.get("image_url") for x in detail],
        "company_count": len((((product.get("struct_detail") or {}).get("company_image") or {}).get("images") or [])),
        "video_id": ((product.get("main_video") or {}).get("video_id")),
    }


def gallery_group(gallery_id: str, items: list[dict]):
    group = ET.Element("complex-values")
    images = ET.SubElement(group, "field", {"id": "images", "type": "multiComplex"})
    for item in items:
        image = ET.SubElement(images, "complex-values")
        image_url = ET.SubElement(image, "field", {"id": "imageURL", "type": "input"})
        ET.SubElement(image_url, "value").text = item["url"]
    gallery = ET.SubElement(group, "field", {"id": "gallery", "type": "singleCheck"})
    ET.SubElement(gallery, "value").text = gallery_id
    return group


def clear_field_values(field: ET.Element) -> int:
    removed = 0
    for parent in list(field.iter()):
        for child in list(parent):
            if child.tag in {"value", "values", "complex-value", "complex-values"}:
                # Keep option metadata; only current-value containers are direct
                # children of the product field or its current values container.
                if parent is field or parent.tag in {"values", "complex-value", "complex-values"}:
                    parent.remove(child)
                    removed += 1
    return removed


def main():
    api = load_client()
    config = api.load_config(CONFIG)
    mapping = json.loads(MAPPING.read_text(encoding="utf-8-sig"))
    details = sorted((x for x in mapping["assets"] if x["role"] == "detail"), key=lambda x: x["slot"])
    expected_tokens = sorted(Path(x["url"].split("?", 1)[0]).stem for x in details)

    before_response = api.top_call(config, "alibaba.icbu.product.get", {"product_id": PRODUCT_ID, "language": "ENGLISH"})
    before = before_response.get("product") or {}
    before_snap = snapshot(before)
    gates = {
        "approved_online": before_snap["status"] == "approved" and before_snap["display"] == "Y",
        "title_ok": before_snap["title"] == TITLE,
        "model_ok": before_snap["model"] == MODEL,
        "sku_count_ok": before_snap["sku_count"] == 20,
        "main_company_ok": (before_snap["main_count"], before_snap["company_count"]) == (6, 5),
        "detail_mapping_ok": len(details) == 4 and all(x.get("status") == "uploaded" for x in details),
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
    detail_field.insert(0, gallery_group("300", [details[2]]))
    detail_field.insert(1, gallery_group("350", [details[0], details[1], details[3]]))

    for node in list(custom_field):
        if node.tag in {"complex-value", "complex-values"}:
            custom_field.remove(node)
    custom_field.insert(0, ET.Element("complex-value"))

    removed_props = {}
    for field_id, label in LEGACY_PROP_IDS.items():
        field = schema.find(f".//field[@id='{field_id}']")
        if field is None:
            removed_props[label] = "field_missing"
            continue
        removed_props[label] = clear_field_values(field)

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

    after_response = api.top_call(config, "alibaba.icbu.product.get", {"product_id": PRODUCT_ID, "language": "ENGLISH"})
    after_snap = snapshot(after_response.get("product") or {})
    actual_tokens = sorted(Path(str(x or "").split("?", 1)[0]).stem.split("_")[0] for x in after_snap["detail_urls"])
    legacy_names = {"Outsole Material", "Midsole Material", "Lining Material", "Feature", "Season", "Fit Type"}
    remaining_legacy = {k: v for k, v in after_snap["attributes"].items() if k in legacy_names}
    receipt = {
        "product_id": PRODUCT_ID,
        "method": "full_current_schema_detail_replace_and_legacy_attribute_clear",
        "before": before_snap,
        "gates": gates,
        "expected_detail_tokens": expected_tokens,
        "removed_property_nodes": removed_props,
        "submitted_xml_chars": len(xml),
        "submitted_xml_sha256": hashlib.sha256(xml.encode("utf-8")).hexdigest(),
        "before_refs": refs(api, before_response),
        "render_refs": refs(api, render_response),
        "update_refs": refs(api, update_response),
        "immediate_readback": after_snap,
        "actual_detail_tokens": actual_tokens,
        "remaining_legacy_attributes": remaining_legacy,
        "readback_refs": refs(api, after_response),
        "submitted_for_review": after_snap["status"] == "modified" and after_snap["display"] == "N",
    }
    OUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if api.api_error(update_response) or update_response.get("biz_success") is False or update_response.get("model") is False:
        raise RuntimeError(f"schema.update failed: {refs(api, update_response)}")
    if not receipt["submitted_for_review"]:
        raise RuntimeError("update was not accepted into modified/N review state")


if __name__ == "__main__":
    main()
