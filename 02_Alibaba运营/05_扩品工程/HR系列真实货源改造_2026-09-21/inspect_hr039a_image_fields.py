from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
OUT = ROOT / r"02_Alibaba运营\05_扩品工程\HR系列真实货源改造_2026-09-21\HR039-A_当前图片字段结构.json"

spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
api = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(api)
config = api.load_config(Path.home() / ".config/beiqiang/alibaba-openapi.json")

response = api.top_call(
    config,
    "alibaba.icbu.product.schema.render",
    {"param_product_top_publish_request": {"product_id": 1601943650395, "language": "en_US"}},
)
root = ET.fromstring(response["data"])
matches = []
for field in root.iter("field"):
    label = f"{field.get('id', '')} {field.get('name', '')}".lower()
    xml = ET.tostring(field, encoding="unicode")
    if any(token in label for token in ("image", "picture", "detail", "description", "company")):
        matches.append(
            {
                "id": field.get("id"),
                "name": field.get("name"),
                "type": field.get("type"),
                "xml": xml,
            }
        )

OUT.write_text(
    json.dumps(
        {
            "product_id": 1601943650395,
            "request_id": response.get("request_id"),
            "trace_id": response.get("trace_id") or response.get("_trace_id_"),
            "matches": matches,
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
for item in matches:
    print(item["id"], item["name"], item["type"])
print(OUT)
