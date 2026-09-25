"""Read-only HR002-A product/schema field inventory for safe migration planning."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT = ROOT / ".agents" / "skills" / "alibaba-openapi-operator" / "scripts" / "alibaba_openapi.py"
OUTPUT = Path(__file__).with_name("HR002-A_S6077_schema_inventory.json")
PRODUCT_ID = 1601943305914


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
if holder is not None:
    for field in holder.findall("./complex-value/field"):
        options = [
            {
                "display": option.get("displayName"),
                "value": option.get("value"),
            }
            for option in field.findall("./options/option")
            if (option.get("displayName") or "").lower() in {
                "lace-up", "lace up", "mesh", "round toe", "walking shoes", "casual", "casual shoes", "men", "male", "china"
            }
        ]
        current_values = []
        current_values.extend([
            {"text": value.text, "inputValue": value.get("inputValue"), "displayName": value.get("displayName")}
            for value in field.findall("./values/value")
        ])
        current_values.extend([
            {"text": value.text, "inputValue": value.get("inputValue"), "displayName": value.get("displayName")}
            for value in field.findall("./value")
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
        if not field.findall("./options/option"):
            continue
        sale_options[field.get("name") or field.get("id")] = [
            {"display": option.get("displayName"), "value": option.get("value")}
            for option in field.findall("./options/option")
            if (field.get("name") != "EUR Size" or option.get("displayName") in {str(value) for value in range(39, 49)})
        ]

product = product_response["product"]
def field_xml(field_id: str):
    field = root.find(f"./field[@id='{field_id}']")
    return ET.tostring(field, encoding="unicode") if field is not None else None


super_text = root.find("./field[@id='superText']/value")
data = {
    "product_id": PRODUCT_ID,
    "product_get_request_id": product_response.get("request_id"),
    "render_request_id": render_response.get("request_id"),
    "status": product.get("status"),
    "display": product.get("display"),
    "title": product.get("subject"),
    "attributes": product.get("attributes"),
    "schema_attribute_fields": attributes,
    "sale_options": sale_options,
    "schema_values": {
        "productDescType": field_xml("productDescType"),
        "superText_length": len(super_text.text or "") if super_text is not None else 0,
        "superText_has_new_detail_tokens": all(token in (super_text.text or "") for token in [
            "H16f4873206e64a20a90bfa4431ac5b98y",
            "H435695e99138472fa28febbf6f732ed47",
            "Hb32d1ebf90b74984bd10752e2b1135c0F",
            "H74a8a34983154040b7d1b50be7439e66E",
        ]) if super_text is not None else False,
        "pkgMeasure": field_xml("pkgMeasure"),
        "pkgWeight": field_xml("pkgWeight"),
        "ladderPeriod": field_xml("ladderPeriod"),
        "customMoreProperty": field_xml("customMoreProperty"),
        "imageVideo": field_xml("imageVideo"),
    },
    "top_level_field_ids": [field.get("id") for field in root.findall("./field")],
}
OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"output": str(OUTPUT), "status": data["status"], "display": data["display"], "request_id": data["render_request_id"]}, ensure_ascii=False, indent=2))
