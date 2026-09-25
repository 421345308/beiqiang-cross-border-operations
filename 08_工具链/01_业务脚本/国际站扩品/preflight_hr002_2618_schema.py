"""Read-only current Alibaba material/variant preflight for HR002/2618."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT = ROOT / ".agents" / "skills" / "alibaba-openapi-operator" / "scripts" / "alibaba_openapi.py"
PRODUCT_IDS = (1601943305914, 1601943393550, 1601943419438)
CATEGORY_ID = 201334413

spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
assert spec and spec.loader
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)
config = api.load_config(Path.home() / ".config" / "beiqiang" / "alibaba-openapi.json")


def call(method: str, params: dict) -> dict:
    result = api.top_call(config, method, params)
    error = api.api_error(result)
    if error:
        raise RuntimeError({"method": method, "error": error, "request_id": result.get("request_id")})
    return result


schema = call("alibaba.icbu.product.schema.get", {
    "param_product_top_publish_request": {"cat_id": CATEGORY_ID, "language": "en_US"}
})
root = ET.fromstring(schema["data"])
terms = ("midsole", "outsole", "lining", "closure", "shoe size", "eur size", "color")
fields = []
for field in root.iter("field"):
    name = field.get("name") or ""
    if not any(term in name.lower() for term in terms):
        continue
    options = []
    for option in field.findall("./options/option"):
        display = option.get("displayName") or ""
        if any(token in display.lower() for token in ("rubber", "mesh", "black", "khaki", "brown", "lace", "39", "48")):
            options.append({"display": display, "value": option.get("value")})
    fields.append({
        "name": name,
        "id": field.get("id"),
        "type": field.get("type"),
        "required": field.get("required"),
        "options": options[:35],
    })

sale = root.find("./field[@id='saleProp']")
sale_fields = []
color_field_shape = None
if sale is not None:
    for field in sale.iter("field"):
        if field.get("id") == "p-191288010":
            color_field_shape = {
                "attributes": dict(field.attrib),
                "direct_children": [child.tag for child in field],
                "custom_options": [dict(option.attrib) for option in field.findall("./options/option")
                                   if (option.get("value") or "").startswith("-") or "custom" in (option.get("displayName") or "").lower()],
            }
        options = []
        for option in field.findall("./options/option"):
            display = option.get("displayName") or ""
            if any(token in display.lower() for token in ("black", "brown", "khaki", "beige", "39", "40", "47", "48")):
                options.append({"display": display, "value": option.get("value")})
        if options or field.get("name"):
            sale_fields.append({"name": field.get("name"), "id": field.get("id"), "type": field.get("type"), "options": options[:40]})

products = []
for product_id in PRODUCT_IDS:
    response = call("alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
    product = response.get("product") or {}
    products.append({
        "id": product_id,
        "request_id": response.get("request_id"),
        "status": product.get("status"),
        "display": product.get("display"),
        "category_id": product.get("category_id"),
        "title": product.get("subject"),
    })

known_custom_color = call("alibaba.icbu.product.schema.render", {
    "param_product_top_publish_request": {"product_id": 1601943514625, "language": "en_US"}
})
known_root = ET.fromstring(known_custom_color["data"])
known_sale = known_root.find("./field[@id='saleProp']")
known_colors = []
if known_sale is not None:
    for field in known_sale.iter("field"):
        if field.get("id") == "p-191288010":
            known_colors = [dict(value.attrib) | {"value": value.text} for value in field.findall(".//value")]
known_product_response = call("alibaba.icbu.product.get", {"product_id": 1601943514625, "language": "ENGLISH"})
known_axes = (known_product_response.get("product") or {}).get("product_sku") or {}

print(json.dumps({
    "schema_request_id": schema.get("request_id"),
    "category_id": CATEGORY_ID,
    "fields": fields,
    "sale_fields": sale_fields,
    "color_field_shape": color_field_shape,
    "known_HR016_A_color_request_id": known_custom_color.get("request_id"),
    "known_HR016_A_color_values": known_colors,
    "known_HR016_A_sku_axes": known_axes.get("sku_attributes"),
    "products": products,
}, ensure_ascii=False, indent=2))
