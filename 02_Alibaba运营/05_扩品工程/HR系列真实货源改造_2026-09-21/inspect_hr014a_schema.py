"""Read-only Alibaba Schema preflight for the HR014 / 5566-1 candidate."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
PRODUCT_ID = 1601943417982
TARGET_SIZES = {str(size) for size in range(36, 47)}
COLOR_TOKENS = {"black", "white", "grey", "gray", "blue", "navy"}


spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
api = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(api)
config = api.load_config(Path.home() / ".config/beiqiang/alibaba-openapi.json")

get_response = api.top_call(
    config,
    "alibaba.icbu.product.get",
    {"product_id": PRODUCT_ID, "language": "ENGLISH"},
)
render_response = api.top_call(
    config,
    "alibaba.icbu.product.schema.render",
    {"param_product_top_publish_request": {"product_id": PRODUCT_ID, "language": "en_US"}},
)
if api.api_error(get_response) or not get_response.get("product"):
    raise RuntimeError({"step": "product.get", "error": api.api_error(get_response)})
if api.api_error(render_response) or not isinstance(render_response.get("data"), str):
    raise RuntimeError({"step": "schema.render", "error": api.api_error(render_response)})

root = ET.fromstring(render_response["data"])
sale_holder = root.find("./field[@id='saleProp']")
sale_options = {}
color_field = None
size_field = None
if sale_holder is not None:
    for field in sale_holder.findall(".//field"):
        options = field.findall("./options/option")
        if not options:
            continue
        name = field.get("name") or field.get("id") or "unknown"
        if name == "Color":
            color_field = ET.tostring(field, encoding="unicode")
        if name == "EUR Size":
            size_field = ET.tostring(field, encoding="unicode")
        relevant = []
        for option in options:
            label = option.get("displayName") or ""
            if name == "EUR Size" and label not in TARGET_SIZES:
                continue
            if name == "Color" and not any(token in label.lower() for token in COLOR_TOKENS):
                continue
            relevant.append({"display": label, "value": option.get("value")})
        sale_options[name] = relevant

product = get_response["product"]
print(json.dumps({
    "mode": "read-only",
    "candidate": "HR014 / 5566-1",
    "product_id": PRODUCT_ID,
    "status": product.get("status"),
    "display": product.get("display"),
    "category_id": product.get("category_id"),
    "get_request_id": get_response.get("request_id"),
    "render_request_id": render_response.get("request_id"),
    "get_trace_id": get_response.get("trace_id") or get_response.get("_trace_id_"),
    "render_trace_id": render_response.get("trace_id") or render_response.get("_trace_id_"),
    "target_sizes": sorted(TARGET_SIZES, key=int),
    "sale_options": sale_options,
    "color_field_xml": color_field,
    "size_field_xml": size_field,
}, ensure_ascii=False, indent=2))
