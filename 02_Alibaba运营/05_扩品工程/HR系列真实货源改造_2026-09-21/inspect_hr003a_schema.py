"""Read-only HR003-A product/schema inventory for the planned 9922 migration."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT = ROOT / ".agents" / "skills" / "alibaba-openapi-operator" / "scripts" / "alibaba_openapi.py"
OUTPUT = Path(__file__).with_name("HR003-A_9922_schema_inventory.json")
PRODUCT_ID = 1601943312845


spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
api = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(api)
config = api.load_config(Path.home() / ".config" / "beiqiang" / "alibaba-openapi.json")

product_response = api.top_call(config, "alibaba.icbu.product.get", {"product_id": PRODUCT_ID, "language": "ENGLISH"})
render_response = api.top_call(
    config,
    "alibaba.icbu.product.schema.render",
    {"param_product_top_publish_request": {"product_id": PRODUCT_ID, "language": "en_US"}},
)
if api.api_error(product_response) or not product_response.get("product"):
    raise RuntimeError({"step": "product.get", "error": api.api_error(product_response)})
if api.api_error(render_response) or not render_response.get("data"):
    raise RuntimeError({"step": "schema.render", "error": api.api_error(render_response)})

root = ET.fromstring(render_response["data"])
holder = root.find("./field[@id='icbuCatProp']")
attributes = []
wanted_attribute_values = {
    "lace-up", "lace up", "mesh", "round toe", "walking shoes", "casual",
    "casual shoes", "men", "male", "china",
}
if holder is not None:
    for field in holder.findall("./complex-value/field"):
        options = [
            {"display": option.get("displayName"), "value": option.get("value")}
            for option in field.findall("./options/option")
            if (option.get("displayName") or "").lower() in wanted_attribute_values
        ]
        current_values = []
        for path in ("./values/value", "./value"):
            current_values.extend([
                {
                    "text": value.text,
                    "inputValue": value.get("inputValue"),
                    "displayName": value.get("displayName"),
                }
                for value in field.findall(path)
            ])
        attributes.append({
            "id": field.get("id"),
            "name": field.get("name"),
            "type": field.get("type"),
            "current": current_values,
            "matching_options": options,
        })

sale_holder = root.find("./field[@id='saleProp']")
sale_options = {}
if sale_holder is not None:
    for field in sale_holder.findall(".//field"):
        options = field.findall("./options/option")
        if not options:
            continue
        name = field.get("name") or field.get("id")
        allowed = []
        for option in options:
            display = option.get("displayName")
            if name == "EUR Size" and display not in {str(value) for value in range(39, 45)}:
                continue
            if name == "Color" and (display or "").lower() not in {"black", "white"}:
                continue
            allowed.append({"display": display, "value": option.get("value")})
        sale_options[name] = allowed

product = product_response["product"]


def field_xml(field_id: str):
    field = root.find(f"./field[@id='{field_id}']")
    return ET.tostring(field, encoding="unicode") if field is not None else None


data = {
    "mode": "read-only",
    "target_family": "HR003 / 9922",
    "product_id": PRODUCT_ID,
    "product_get_request_id": product_response.get("request_id"),
    "render_request_id": render_response.get("request_id"),
    "status": product.get("status"),
    "display": product.get("display"),
    "title": product.get("subject"),
    "attributes": product.get("attributes"),
    "sku_count": len(product.get("sku_infos") or []),
    "sale_options": sale_options,
    "schema_attribute_fields": attributes,
    "schema_values": {
        "productDescType": field_xml("productDescType"),
        "pkgMeasure": field_xml("pkgMeasure"),
        "pkgWeight": field_xml("pkgWeight"),
        "ladderPeriod": field_xml("ladderPeriod"),
        "customMoreProperty": field_xml("customMoreProperty"),
        "imageVideo": field_xml("imageVideo"),
        "detailImage": field_xml("detailImage"),
        "companyImage": field_xml("companyImage"),
    },
    "top_level_field_ids": [field.get("id") for field in root.findall("./field")],
}
OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({
    "output": str(OUTPUT),
    "status": data["status"],
    "display": data["display"],
    "product_get_request_id": data["product_get_request_id"],
    "render_request_id": data["render_request_id"],
}, ensure_ascii=False, indent=2))
