from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT_PATH = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG_PATH = Path.home() / ".config/beiqiang/alibaba-openapi.json"


def main(product_id: int = 1601939651515) -> None:
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    config = module.load_config(CONFIG_PATH)
    response = module.top_call(
        config,
        "alibaba.icbu.product.schema.render",
        {"param_product_top_publish_request": {"product_id": product_id, "language": "en_US"}},
    )
    xml_text = response.get("data")
    if not isinstance(xml_text, str):
        raise RuntimeError(json.dumps(response, ensure_ascii=False))
    root = ET.fromstring(xml_text)
    rows = []
    for field in root.iter("field"):
        field_id = field.get("id", "")
        name = field.get("name", "")
        if any(token in (field_id + " " + name).lower() for token in ("summary", "selling", "highlight", "亮点", "卖点")):
            value = field.find("value")
            rows.append({
                "id": field_id,
                "name": name,
                "type": field.get("type"),
                "value": value.text if value is not None else None,
                "rules": [{"name": rule.get("name"), "value": rule.get("value")} for rule in field.findall("./rules/rule")],
            })
    images = root.find(".//field[@id='scImages']")
    if images is not None:
        rows.append({"id": "scImages", "xml": ET.tostring(images, encoding="unicode")})
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
