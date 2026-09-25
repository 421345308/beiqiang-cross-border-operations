"""Read-only Alibaba OpenAPI check for accidental buyer-facing source disclosures."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
PRODUCTS = {
    "HR002-A": 1601943305914,
    "HR002-B": 1601943393550,
    "HR002-C": 1601943419438,
    "HR016-A": 1601943514625,
    "HR016-B": 1601943535517,
    "HR016-C": 1601943523535,
}
TERMS = re.compile(r"externally sourced|external supplier|external supply|sourcing|supplied by|外采|外部货源|搜鞋网|路崎", re.I)

spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
assert spec and spec.loader
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)
config = api.load_config(Path.home() / ".config/beiqiang/alibaba-openapi.json")


def call(method: str, params: dict) -> dict:
    response = api.top_call(config, method, params)
    error = api.api_error(response)
    if error:
        raise RuntimeError({"method": method, "error": error})
    return response


def main() -> None:
    findings = []
    for label, product_id in PRODUCTS.items():
        formal = call("alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
        product = formal.get("product") or {}
        fields = []
        def scan(value: object, path: str) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    scan(item, f"{path}.{key}")
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    scan(item, f"{path}[{index}]")
            elif isinstance(value, str):
                matches = sorted(set(m.group(0) for m in TERMS.finditer(value)), key=str.lower)
                if matches:
                    fields.append({"field": path, "matches": matches, "excerpt": value[:400]})
        scan(product, "product")
        rendered = call("alibaba.icbu.product.schema.render", {
            "param_product_top_publish_request": {"product_id": product_id, "language": "en_US"}
        })
        if rendered.get("data"):
            root = ET.fromstring(rendered["data"])
            for field in root.findall(".//field"):
                field_id = field.attrib.get("id", "")
                if field_id not in {"textDesc", "superText", "productTitle", "productKeywords"}:
                    continue
                value = " ".join((node.text or "") for node in field.findall(".//value"))
                matches = sorted(set(m.group(0) for m in TERMS.finditer(value)), key=str.lower)
                if matches:
                    fields.append({"field": f"schema.{field_id}", "matches": matches, "excerpt": value[:400]})
        findings.append({"label": label, "id": product_id, "status": product.get("status"),
                         "display": product.get("display"), "matches": fields,
                         "formal_request_id": formal.get("request_id"), "schema_request_id": rendered.get("request_id"),
                         "schema_render_error": (rendered.get("result") or {}).get("error_message")})
        print(json.dumps(findings[-1], ensure_ascii=False))


if __name__ == "__main__":
    main()
