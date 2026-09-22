from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT_PATH = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG_PATH = Path.home() / ".config/beiqiang/alibaba-openapi.json"
OUT_PATH = ROOT / "02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21/HR039-BC_OpenAPI只读回读.json"
TARGETS = {
    "HR039-B": 1601943670292,
    "HR039-C": 1601943583746,
}


def load_client():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def refs(client, response: dict) -> dict:
    return {
        "request_id": response.get("request_id"),
        "trace_id": response.get("trace_id") or response.get("_trace_id_"),
        "error": client.api_error(response),
    }


def attr_map(product: dict) -> dict:
    return {
        str(row.get("attribute_name")): row.get("value_name")
        for row in product.get("attributes", [])
    }


def snapshot(product: dict) -> dict:
    groups = (product.get("product_sku") or {}).get("sku_attributes", [])
    sku_axes = {
        str(group.get("attribute_name")): [
            row.get("system_value_name") or row.get("value_name")
            for row in group.get("values", [])
        ]
        for group in groups
    }
    skus = (product.get("product_sku") or {}).get("skus", [])
    prices = sorted(
        {
            row.get("price")
            for sku in skus
            for row in sku.get("bulk_discount_prices", [])
            if row.get("price") is not None
        }
    )
    return {
        "subject": product.get("subject"),
        "category_id": product.get("category_id"),
        "status": product.get("status"),
        "display": product.get("display"),
        "pc_detail_url": product.get("pc_detail_url"),
        "attributes": attr_map(product),
        "sku_axes": sku_axes,
        "sku_count": len(skus),
        "prices": prices,
        "moq": (product.get("sourcing_trade") or {}).get("min_order_quantity"),
        "main_images": (product.get("main_image") or {}).get("images", []),
        "detail_images": (((product.get("struct_detail") or {}).get("detail_image") or {}).get("images") or []),
        "company_images": (((product.get("struct_detail") or {}).get("company_image") or {}).get("images") or []),
    }


def schema_fields(xml_text: str) -> dict:
    root = ET.fromstring(xml_text)
    result = {}
    for field_id in ("productTitle", "p-3", "imageVideo", "detailVideo", "scImages", "detailImage", "companyImage"):
        field = root.find(f".//field[@id='{field_id}']")
        if field is not None:
            result[field_id] = ET.tostring(field, encoding="unicode")
    return result


def main() -> None:
    client = load_client()
    config = client.load_config(CONFIG_PATH)
    result = {"mode": "read-only", "targets": {}}
    for listing_id, product_id in TARGETS.items():
        get_response = client.top_call(
            config,
            "alibaba.icbu.product.get",
            {"product_id": product_id, "language": "ENGLISH"},
        )
        product = get_response.get("product")
        if client.api_error(get_response) or not product:
            raise RuntimeError(f"product.get failed for {product_id}: {refs(client, get_response)}")
        render_response = client.top_call(
            config,
            "alibaba.icbu.product.schema.render",
            {"param_product_top_publish_request": {"product_id": product_id, "language": "en_US"}},
        )
        xml_text = render_response.get("data")
        if client.api_error(render_response) or not isinstance(xml_text, str):
            raise RuntimeError(f"schema.render failed for {product_id}: {refs(client, render_response)}")
        result["targets"][listing_id] = {
            "product_id": product_id,
            "product": snapshot(product),
            "schema_fields": schema_fields(xml_text),
            "get_refs": refs(client, get_response),
            "render_refs": refs(client, render_response),
        }
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
