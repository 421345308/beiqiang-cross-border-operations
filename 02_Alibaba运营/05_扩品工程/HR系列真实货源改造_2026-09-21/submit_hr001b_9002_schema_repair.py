"""Repair HR001-B using its current official Schema, including SKU availability."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG = Path.home() / ".config/beiqiang/alibaba-openapi.json"
MANIFEST = HERE / "HR001_9002_最终图片绑定清单.json"
PRODUCT_ID = 1601943493004
LINK_CODE = "HR001-B"
TITLE = "Men's Knit Slip-On Walking Shoes EVA Sole EU 38-47 Wholesale OEM Supplier Model 9002"
MODEL = "HR001-B / 9002"
HIGHLIGHTS = (
    "Verified Model 9002 uses a textile upper, slip-on no-lace structure and EVA sole. "
    "Source choices are Light Gray with Beige Sole and Dark Gray with Black Sole in EU sizes 38-47. "
    "Logo, color and packaging requests can be discussed after quantity and specification review. "
    "Freight is quoted separately. Source price, availability, size ratio, packing and lead time are rechecked before order."
)
B_D1_URL = (
    "https://sc04.alicdn.com/kf/H85b21cb197004ec69e0d67d000411ca1j/"
    "286385890/H85b21cb197004ec69e0d67d000411ca1j.jpg"
)
DETAIL_ROLES = (
    "D1_product_overview", "D2_verified_specs", "D3_colors_sizes",
    "D4_price_quote", "D5_oem_project_inputs",
)


def client():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ensure_call(api, response, name):
    error = api.api_error(response)
    if error:
        raise RuntimeError(f"{name}: {error}; request={response.get('request_id')}")
    return response


def current_field(schema, field_id):
    node = schema.find(f"./field[@id='{field_id}']")
    if node is None:
        raise RuntimeError(f"Missing current Schema field {field_id}")
    return copy.deepcopy(node)


def set_value(field, value):
    value_node = field.find("./value")
    if value_node is None:
        value_node = ET.SubElement(field, "value")
    value_node.text = value


def make_detail_field(current, assets):
    for node in list(current):
        if node.tag == "complex-values":
            current.remove(node)
    group = ET.Element("complex-values")
    images = ET.SubElement(group, "field", {"id": "images", "type": "multiComplex"})
    for role in DETAIL_ROLES:
        url = B_D1_URL if role == "D1_product_overview" else assets[role]["url"]
        if not str(url).startswith("https://sc04.alicdn.com/kf/"):
            raise RuntimeError(f"Non-official detail URL for {role}")
        item = ET.SubElement(images, "complex-values")
        image_field = ET.SubElement(item, "field", {"id": "imageURL", "type": "input"})
        ET.SubElement(image_field, "value").text = "//" + url.removeprefix("https://")
    gallery = ET.SubElement(group, "field", {"id": "gallery", "type": "singleCheck"})
    ET.SubElement(gallery, "value").text = "350"
    current.insert(0, group)
    return current


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    api = client()
    config = api.load_config(CONFIG)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    assets = {row["role"]: row for row in manifest["items"]}
    if not all(role in assets for role in DETAIL_ROLES):
        raise RuntimeError("Missing detail source asset")

    product_reply = ensure_call(api, api.top_call(config, "alibaba.icbu.product.get", {
        "product_id": PRODUCT_ID, "language": "ENGLISH",
    }), "product.get")
    product = product_reply.get("product") or {}
    skus = (product.get("product_sku") or {}).get("skus") or []
    attrs = {str(x.get("attribute_name")): x.get("value_name") for x in product.get("attributes") or []}
    if not (
        product.get("status") == "approved" and product.get("display") == "Y"
        and attrs.get("Model Number") == MODEL
        and len(skus) == 20
        and all(str(x.get("sku_code", "")).startswith(LINK_CODE + "-9002-") for x in skus)
        and len((product.get("main_image") or {}).get("images") or []) == 6
        and len(((product.get("struct_detail") or {}).get("company_image") or {}).get("images") or []) == 5
    ):
        raise RuntimeError("Formal product identity, 20-SKU, or image guard failed")

    render_reply = ensure_call(api, api.top_call(config, "alibaba.icbu.product.schema.render", {
        "param_product_top_publish_request": {"product_id": PRODUCT_ID, "language": "en_US"},
    }), "schema.render")
    xml = render_reply.get("data")
    if not isinstance(xml, str) or not xml:
        raise RuntimeError("Current editable Schema unavailable")
    schema = ET.fromstring(xml)
    sku = current_field(schema, "sku")
    rows = sku.findall("./complex-values")
    if len(rows) != 20:
        raise RuntimeError(f"Current Schema SKU rows = {len(rows)}, expected 20")
    sku_codes = set()
    for row in rows:
        code = row.findtext("./field[@id='skuOuterId']/value")
        stock = row.find("./field[@id='skuStock']")
        if not code or not code.startswith(LINK_CODE + "-9002-") or stock is None:
            raise RuntimeError(f"Unexpected Schema SKU row {code}")
        sku_codes.add(code)
        old_values = stock.findall("./values/value")
        if old_values and any(str(v.text).strip() not in ("", "0", "999") for v in old_values):
            raise RuntimeError(f"Unexpected existing stock for {code}")
        for child in list(stock):
            stock.remove(child)
        values = ET.SubElement(stock, "values")
        ET.SubElement(values, "value", {
            "srcValue": "999", "warehouseCode": "CN_LOCAL_01",
        }).text = "999"
    if sku_codes != {str(x.get("sku_code")) for x in skus}:
        raise RuntimeError("Rendered SKU codes do not match formal product readback")

    out_schema = ET.Element("itemSchema")
    for field_id in ("productTitle", "productDescType", "detailImage", "customMoreProperty", "textDesc", "sku"):
        field = sku if field_id == "sku" else current_field(schema, field_id)
        if field_id == "productTitle":
            set_value(field, TITLE)
        elif field_id == "detailImage":
            make_detail_field(field, assets)
        elif field_id == "customMoreProperty":
            for child in list(field):
                if child.tag in ("complex-value", "complex-values", "values", "value"):
                    field.remove(child)
            field.insert(0, ET.Element("complex-value"))
        elif field_id == "textDesc":
            set_value(field, HIGHLIGHTS)
        out_schema.append(field)
    update_xml = ET.tostring(out_schema, encoding="unicode")
    plan = {
        "product_id": PRODUCT_ID, "source_model": "9002",
        "checked_at": datetime.now().astimezone().isoformat(),
        "mode": "apply" if args.apply else "dry_run",
        "product_request_id": product_reply.get("request_id"),
        "render_request_id": render_reply.get("request_id"),
        "before_status": product.get("status"), "before_title": product.get("subject"),
        "before_fit_type": attrs.get("Fit Type"),
        "sku_count": len(rows), "detail_roles": DETAIL_ROLES,
        "new_title": TITLE, "new_stock_marker": 999,
        "stock_is_actual_on_hand_count": False,
        "field_ids": [x.get("id") for x in out_schema.findall("./field")],
        "xml_sha256": hashlib.sha256(update_xml.encode("utf-8")).hexdigest(),
        "xml_length": len(update_xml),
    }
    if args.apply:
        update_reply = api.top_call(config, "alibaba.icbu.product.schema.update", {
            "param_product_top_publish_request": {
                "cat_id": int(product["category_id"]),
                "language": "en_US", "product_id": PRODUCT_ID, "xml": update_xml,
            },
        })
        plan["update_request_id"] = update_reply.get("request_id")
        plan["update_trace_id"] = update_reply.get("trace_id") or update_reply.get("_trace_id_")
        plan["update_error"] = api.api_error(update_reply)
        plan["update_model"] = update_reply.get("model")
        plan["update_biz_success"] = update_reply.get("biz_success")
        if plan["update_error"] or plan["update_biz_success"] is False or plan["update_model"] is False:
            plan["passed"] = False
        else:
            after_reply = ensure_call(api, api.top_call(config, "alibaba.icbu.product.get", {
                "product_id": PRODUCT_ID, "language": "ENGLISH",
            }), "product.get-after")
            after = after_reply.get("product") or {}
            plan["after_request_id"] = after_reply.get("request_id")
            plan["after_status"] = after.get("status")
            plan["after_display"] = after.get("display")
            plan["after_title"] = after.get("subject")
            plan["after_sku_count"] = len((after.get("product_sku") or {}).get("skus") or [])
            plan["passed"] = plan["after_status"] in ("modified", "approved")
    else:
        plan["passed"] = True
    out = HERE / f"{LINK_CODE}_9002_Schema库存与详情_{'正式' if args.apply else '预检'}_回执.json"
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(plan, ensure_ascii=False))
    if not plan["passed"]:
        raise RuntimeError("Schema update was not confirmed")


if __name__ == "__main__":
    main()
