"""Read-only HR012-A product/schema inventory for the DL20 candidate migration."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT = ROOT / ".agents" / "skills" / "alibaba-openapi-operator" / "scripts" / "alibaba_openapi.py"
OUTPUT = Path(__file__).with_name("HR012-A_DL20_schema_inventory.json")
PRODUCT_ID = 1601943445780
TARGET_SIZES = {str(value) for value in range(39, 45)}
COLOR_TOKENS = {"beige", "green", "brown", "white", "black", "khaki", "multi"}

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
sale_holder = root.find("./field[@id='saleProp']")
sale_options: dict[str, list[dict[str, str | None]]] = {}
all_color_options: list[dict[str, str | None]] = []
color_field_xml: str | None = None
if sale_holder is not None:
    for field in sale_holder.findall(".//field"):
        options = field.findall("./options/option")
        if not options:
            continue
        name = field.get("name") or field.get("id") or "unknown"
        if name == "Color":
            color_field_xml = ET.tostring(field, encoding="unicode")
            all_color_options = [
                {"display": option.get("displayName"), "value": option.get("value")}
                for option in options
            ]
        allowed = []
        for option in options:
            display = option.get("displayName") or ""
            if name == "EUR Size" and display not in TARGET_SIZES:
                continue
            if name == "Color" and not any(token in display.lower() for token in COLOR_TOKENS):
                continue
            allowed.append({"display": display, "value": option.get("value")})
        sale_options[name] = allowed

product = product_response["product"]
data = {
    "mode": "read-only",
    "target_family": "HR012 / DL20 candidate",
    "product_id": PRODUCT_ID,
    "product_get_request_id": product_response.get("request_id"),
    "render_request_id": render_response.get("request_id"),
    "status": product.get("status"),
    "display": product.get("display"),
    "title": product.get("subject"),
    "attributes": product.get("attributes"),
    "sku_count": len(product.get("sku_infos") or []),
    "target_sizes": sorted(TARGET_SIZES),
    "candidate_sale_options": sale_options,
    "all_color_options": all_color_options,
    "color_field_xml": color_field_xml,
    "top_level_field_ids": [field.get("id") for field in root.findall("./field")],
}
OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({
    "output": str(OUTPUT),
    "status": data["status"],
    "display": data["display"],
    "product_get_request_id": data["product_get_request_id"],
    "render_request_id": data["render_request_id"],
    "candidate_sale_options": data["candidate_sale_options"],
}, ensure_ascii=True, indent=2))
