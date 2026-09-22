from __future__ import annotations

import importlib.util
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"

spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)
config = module.load_config(Path.home() / ".config/beiqiang/alibaba-openapi.json")
response = module.top_call(
    config,
    "alibaba.icbu.product.schema.render",
    {"param_product_top_publish_request": {"product_id": 1601943650395, "language": "en_US"}},
)
root = ET.fromstring(response["data"])

for item in root.iter("field"):
    label = f"{item.get('id', '')} {item.get('name', '')}".lower()
    if "video" in label:
        print(item.get("id"), item.get("name"), [(node.text or "")[:200] for node in item.findall("./value")])

model_field = root.find(".//field[@id='p-3']")
print("MODEL_XML", ET.tostring(model_field, encoding="unicode") if model_field is not None else "MISSING")
