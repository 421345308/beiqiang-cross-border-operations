"""Clear HR039-B's obsolete custom Fit Type through a minimal Schema update."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT_PATH = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG_PATH = Path.home() / ".config/beiqiang/alibaba-openapi.json"
OUT_PATH = ROOT / "02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21/HR039-B_FitType显式清空回执.json"
PRODUCT_ID = 1601943670292
TITLE = "Men's High Top Knit Slip-On Walking Shoes EVA Sole EU 35-45 Wholesale OEM for Daily Wear"
MODEL = "HR039-B / 8025"


def load_client():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def refs(client, response):
    return {
        "request_id": response.get("request_id"),
        "trace_id": response.get("trace_id") or response.get("_trace_id_"),
        "error": client.api_error(response),
        "biz_success": response.get("biz_success"),
    }


def attr_map(product):
    return {str(row.get("attribute_name")): row.get("value_name") for row in product.get("attributes") or []}


def snapshot(product):
    attrs = attr_map(product)
    detail = product.get("struct_detail") or {}
    return {
        "status": product.get("status"),
        "display": product.get("display"),
        "subject": product.get("subject"),
        "model": attrs.get("Model Number"),
        "pattern": attrs.get("Pattern Type"),
        "fit_type": attrs.get("Fit Type"),
        "sku_count": len(((product.get("product_sku") or {}).get("skus") or [])),
        "main_images": len(((product.get("main_image") or {}).get("images") or [])),
        "detail_images": len((((detail.get("detail_image") or {}).get("images")) or [])),
        "company_images": len((((detail.get("company_image") or {}).get("images")) or [])),
    }


def render(client, config):
    response = client.top_call(
        config,
        "alibaba.icbu.product.schema.render",
        {"param_product_top_publish_request": {"product_id": PRODUCT_ID, "language": "en_US"}},
    )
    xml = response.get("data")
    if client.api_error(response) or not isinstance(xml, str):
        raise RuntimeError(f"schema.render failed: {refs(client, response)}")
    return response, ET.fromstring(xml)


def main():
    client = load_client()
    config = client.load_config(CONFIG_PATH)
    before_response = client.top_call(
        config,
        "alibaba.icbu.product.get",
        {"product_id": PRODUCT_ID, "language": "ENGLISH"},
    )
    before = before_response.get("product") or {}
    before_snap = snapshot(before)
    gates = {
        "approved_and_online": before_snap["status"] == "approved" and before_snap["display"] == "Y",
        "title_ok": before_snap["subject"] == TITLE,
        "model_ok": before_snap["model"] == MODEL,
        "pattern_ok": before_snap["pattern"] == "Solid",
        "fit_type_present": before_snap["fit_type"] == "Regular Fit",
        "sku_count_ok": before_snap["sku_count"] == 22,
        "gallery_ok": (before_snap["main_images"], before_snap["detail_images"], before_snap["company_images"]) == (6, 5, 5),
    }
    if client.api_error(before_response) or not all(gates.values()):
        raise RuntimeError(f"preflight failed: {gates}; refs={refs(client, before_response)}")

    render_response, schema = render(client, config)
    custom = schema.find(".//field[@id='customMoreProperty']")
    if custom is None:
        raise RuntimeError("customMoreProperty field missing")
    value_node = custom.find("./complex-value")
    before_value_xml = ET.tostring(value_node, encoding="unicode") if value_node is not None else None
    if "Fit Type" not in (before_value_xml or "") or "Regular Fit" not in (before_value_xml or ""):
        raise RuntimeError(f"unexpected custom property value: {before_value_xml}")

    root = ET.Element("itemSchema")
    clear_field = ET.SubElement(root, "field", {"id": "customMoreProperty", "type": "complex"})
    ET.SubElement(clear_field, "complex-value")
    xml = ET.tostring(root, encoding="unicode")
    update_response = client.top_call(
        config,
        "alibaba.icbu.product.schema.update",
        {
            "param_product_top_publish_request": {
                "cat_id": int(before["category_id"]),
                "language": "en_US",
                "product_id": PRODUCT_ID,
                "xml": xml,
            }
        },
    )
    if client.api_error(update_response) or update_response.get("biz_success") is False or update_response.get("model") is False:
        raise RuntimeError(f"schema.update failed: {refs(client, update_response)}")

    after_response = client.top_call(
        config,
        "alibaba.icbu.product.get",
        {"product_id": PRODUCT_ID, "language": "ENGLISH"},
    )
    after = after_response.get("product") or {}
    receipt = {
        "product_id": PRODUCT_ID,
        "method": "minimal_incremental_explicit_empty_customMoreProperty",
        "before": before_snap,
        "gates": gates,
        "before_value_xml": before_value_xml,
        "submitted_xml": xml,
        "xml_sha256": hashlib.sha256(xml.encode("utf-8")).hexdigest(),
        "before_refs": refs(client, before_response),
        "render_refs": refs(client, render_response),
        "update_refs": refs(client, update_response),
        "immediate_readback": snapshot(after),
        "readback_refs": refs(client, after_response),
    }
    OUT_PATH.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
