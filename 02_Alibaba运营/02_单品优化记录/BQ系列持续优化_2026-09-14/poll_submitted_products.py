from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


CLIENT_PATH = Path(r"C:\Users\spq\Desktop\贝强\.agents\skills\alibaba-openapi-operator\scripts\alibaba_openapi.py")
PRODUCT_IDS = [
    "1601939599850",
    "1601939712176",
    "1601939631570",
    "1601939660427",
    "1601939655430",
    "1601939735063",
]


def load_client():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load OpenAPI client: {CLIENT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def model_number(product: dict) -> str | None:
    return next(
        (
            row.get("value_name")
            for row in product.get("attributes", [])
            if row.get("attribute_name") == "Model Number"
        ),
        None,
    )


def main() -> None:
    client = load_client()
    config = client.load_config(client.DEFAULT_CONFIG)
    rows = []
    product_ids = sys.argv[1:] or PRODUCT_IDS
    for product_id in product_ids:
        response = client.top_call(
            config,
            "alibaba.icbu.product.get",
            {"product_id": product_id, "language": "ENGLISH"},
        )
        product = response.get("product") or {}
        rows.append(
            {
                "product_id": product_id,
                "status": product.get("status"),
                "display": product.get("display"),
                "title": product.get("subject"),
                "model": model_number(product),
                "image_count": len((product.get("main_image") or {}).get("images", [])),
                "images": (product.get("main_image") or {}).get("images", []),
                "sku_count": len((product.get("product_sku") or {}).get("skus", [])),
                "colors": [
                    {
                        "name": value.get("system_value_name") or value.get("value_name"),
                        "image_url": value.get("image_url"),
                    }
                    for attr in (product.get("product_sku") or {}).get("sku_attributes", [])
                    if attr.get("attribute_name") == "Color"
                    for value in attr.get("values", [])
                ],
                "pc_detail_url": product.get("pc_detail_url"),
                "request_id": response.get("request_id"),
                "trace_id": response.get("_trace_id_"),
            }
        )
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
