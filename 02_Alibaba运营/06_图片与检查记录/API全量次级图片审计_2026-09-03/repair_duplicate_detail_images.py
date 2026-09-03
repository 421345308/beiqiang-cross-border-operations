#!/usr/bin/env python3
"""Replace detail galleries that reuse main-image URLs with verified local assets."""

from __future__ import annotations

import importlib.util
import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[3]
AUDIT_DIR = Path(__file__).resolve().parent
CLIENT_PATH = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG_PATH = Path.home() / ".config/beiqiang/alibaba-openapi.json"
ASSET_ROOT = ROOT / "01_产品资产/02_可发布素材/00_最终上传"
TARGETS = [
    {
        "product_id": 10000043763325,
        "model": "BQ013 / T55836",
        "asset_dir": ASSET_ROOT / "BQ013_T55836/02_详情页",
    },
    {
        "product_id": 10000043732626,
        "model": "BQ014 / A507",
        "asset_dir": ASSET_ROOT / "BQ014_A507/02_详情页",
    },
]
FILES = [
    ("01_size_safe.png", 150, "Product dimensions"),
    ("02_info.jpg", 350, "Other product images"),
    ("03_upper.jpg", 300, "Detail shot"),
    ("04_sole.jpg", 300, "Detail shot"),
    ("05_colors.jpg", 350, "Other product images"),
    ("06_order.jpg", 350, "Other product images"),
]


def load_client():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def failed(client, response: dict) -> bool:
    return bool(client.api_error(response)) or response.get("biz_success") is False or response.get("model") is False


def refs(client, response: dict) -> dict:
    return {
        "request_id": response.get("request_id"),
        "trace_id": response.get("trace_id") or response.get("_trace_id_"),
        "message": response.get("message") or response.get("msg_info"),
        "error": client.api_error(response),
    }


def image_key(url: str) -> str:
    source = url.replace("//", "https://", 1) if url.startswith("//") else url
    name = Path(urlparse(source).path).name
    name = re.sub(r"_\d+x\d+\.[^.]+$", "", name, flags=re.I)
    return name.rsplit(".", 1)[0]


def get_product(client, config: dict, product_id: int) -> tuple[dict, dict]:
    response = client.top_call(
        config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"}
    )
    if failed(client, response) or not response.get("product"):
        raise RuntimeError(f"product.get failed for {product_id}: {response}")
    return response, response["product"]


def stable_snapshot(product: dict) -> dict:
    keys = [
        "subject", "category_id", "language", "product_type", "keywords",
        "attributes", "product_sku", "sourcing_trade", "main_image",
        "price_type", "rts", "group_id",
    ]
    snapshot = {key: deepcopy(product.get(key)) for key in keys}
    detail = deepcopy(product.get("struct_detail") or {})
    detail.pop("detail_image", None)
    snapshot["struct_detail_without_detail_image"] = detail
    return snapshot


def detail_xml(rows: list[dict]) -> str:
    root = ET.Element("itemSchema")
    group = ET.SubElement(root, "field", {"id": "detailImage", "type": "multiComplex"})
    for row in rows:
        item = ET.SubElement(group, "complex-values")
        images = ET.SubElement(item, "field", {"id": "images", "type": "multiComplex"})
        image_item = ET.SubElement(images, "complex-values")
        image_url = ET.SubElement(image_item, "field", {"id": "imageURL", "type": "input"})
        ET.SubElement(image_url, "value").text = row["url"].replace("https:", "").replace("http:", "")
        gallery = ET.SubElement(item, "field", {"id": "gallery", "type": "singleCheck"})
        value = ET.SubElement(gallery, "value", {"displayName": row["role_name"]})
        value.text = str(row["role_id"])
    return ET.tostring(root, encoding="unicode")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-id", type=int, action="append")
    args = parser.parse_args()
    client = load_client()
    config = client.load_config(CONFIG_PATH)
    manifest = []
    selected = [target for target in TARGETS if not args.product_id or target["product_id"] in args.product_id]
    for target in selected:
        product_id = int(target["product_id"])
        before_response, before = get_product(client, config, product_id)
        before_snapshot = stable_snapshot(before)
        uploads = []
        for filename, role_id, role_name in FILES:
            path = target["asset_dir"] / filename
            if not path.is_file():
                raise RuntimeError(f"Missing verified detail image: {path}")
            response = client.upload_image(config, path, None)
            if failed(client, response) or not response.get("upload_image_response"):
                raise RuntimeError(f"Upload failed for {product_id}/{filename}: {response}")
            item = response["upload_image_response"]
            uploads.append({
                "filename": filename,
                "source": str(path),
                "role_id": role_id,
                "role_name": role_name,
                "file_id": str(item["file_id"]),
                "url": str(item["photobank_url"]),
                **refs(client, response),
            })

        update_response = client.top_call(
            config,
            "alibaba.icbu.product.schema.update",
            {
                "param_product_top_publish_request": {
                    "cat_id": int(before["category_id"]),
                    "language": "en_US",
                    "product_id": product_id,
                    "xml": detail_xml(uploads),
                }
            },
        )
        if failed(client, update_response):
            raise RuntimeError(f"Detail update failed for {product_id}: {update_response}")

        after_response, after = get_product(client, config, product_id)
        after_rows = ((after.get("struct_detail") or {}).get("detail_image") or {}).get("images") or []
        after_keys = [image_key(str(row.get("image_url", ""))) for row in after_rows]
        expected_keys = [image_key(row["url"]) for row in uploads]
        main_keys = {image_key(url) for url in (after.get("main_image") or {}).get("images", [])}
        details_verified = len(after_keys) == len(expected_keys) and set(after_keys) == set(expected_keys)
        no_main_overlap = not (set(after_keys) & main_keys)
        other_fields_preserved = stable_snapshot(after) == before_snapshot
        if not details_verified or not no_main_overlap or not other_fields_preserved:
            (AUDIT_DIR / f"{product_id}_detail_repair_failed_debug.json").write_text(
                json.dumps({
                    "expected": expected_keys,
                    "actual": after_keys,
                    "main": sorted(main_keys),
                    "update": update_response,
                    "readback": after_response,
                }, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            raise RuntimeError(
                f"Detail readback failed for {product_id}: details={details_verified}, "
                f"overlap={not no_main_overlap}, preserved={other_fields_preserved}"
            )

        (AUDIT_DIR / f"{product_id}_product_get_after_detail_repair.json").write_text(
            json.dumps(after_response, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        manifest.append({
            "productId": product_id,
            "model": target["model"],
            "detailCount": len(after_keys),
            "noMainImageOverlap": no_main_overlap,
            "otherFieldsPreserved": other_fields_preserved,
            "uploads": uploads,
            "update": refs(client, update_response),
            "readback": refs(client, after_response),
        })

    (AUDIT_DIR / "详情图重复修复记录.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
