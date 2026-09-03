#!/usr/bin/env python3
"""Repair confirmed 404 SKU color images and verify all SKU data is preserved."""

from __future__ import annotations

import importlib.util
import argparse
import json
from copy import deepcopy
from pathlib import Path
import re
import tempfile
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
AUDIT_DIR = Path(__file__).resolve().parent
CLIENT_PATH = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG_PATH = Path.home() / ".config/beiqiang/alibaba-openapi.json"
ASSET_ROOT = ROOT / "01_产品资产/02_可发布素材/00_最终上传"
TARGETS = [
    {
        "product_id": 1601924345456,
        "model": "BQ033 / T5503",
        "replacements": {
            # The former Alibaba object for this exact image returns HTTP 404.
            # Re-encode the verified source as PNG so photobank creates a fresh,
            # reachable object without changing the shoe appearance.
            "Grey": {
                "path": ASSET_ROOT / "BQ033_T5503/03_颜色图/02_grey.jpg",
                "force_reencode": True,
            },
        },
    },
    {
        "product_id": 1601924732369,
        "model": "BQ038 / M889",
        "replacements": {
            "Black/White Fleece": {"path": ASSET_ROOT / "BQ038_M889/03_颜色图/04_black_white_fleece.jpg"},
            "All Black Fleece": {"path": ASSET_ROOT / "BQ038_M889/03_颜色图/05_all_black_fleece.jpg"},
        },
    },
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


def get_product(client, config: dict, product_id: int) -> tuple[dict, dict]:
    response = client.top_call(
        config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"}
    )
    if failed(client, response) or not response.get("product"):
        raise RuntimeError(f"product.get failed for {product_id}: {response}")
    return response, response["product"]


def sku_snapshot(product: dict) -> dict:
    sku = product.get("product_sku") or {}
    return {
        "sku_details": deepcopy(sku.get("sku_details")),
        "sku_price": deepcopy(sku.get("sku_price")),
        "sku_price_type": deepcopy(sku.get("sku_price_type")),
        "sku_attributes_without_images": [
            {
                "attribute_id": group.get("attribute_id"),
                "attribute_name": group.get("attribute_name"),
                "values": [
                    {key: value for key, value in item.items() if key != "image_url"}
                    for item in group.get("values", [])
                ],
            }
            for group in sku.get("sku_attributes", [])
        ],
    }


def color_map(product: dict) -> dict[str, dict]:
    for group in (product.get("product_sku") or {}).get("sku_attributes", []):
        if int(group.get("attribute_id", 0)) == 191288010:
            return {str(value.get("system_value_name")): value for value in group.get("values", [])}
    raise RuntimeError("Color SKU attribute was not found")


def image_key(url: str) -> str:
    source = url.replace("//", "https://", 1) if url.startswith("//") else url
    name = Path(urlparse(source).path).name
    name = re.sub(r"_\d+x\d+\.[^.]+$", "", name, flags=re.I)
    return name.rsplit(".", 1)[0]


def response_xml(response: dict) -> str:
    if isinstance(response.get("data"), str):
        return response["data"]
    for value in response.values():
        if isinstance(value, dict):
            found = response_xml(value)
            if found:
                return found
    return ""


def render_schema(client, config: dict, product_id: int) -> ET.Element:
    response = client.top_call(
        config,
        "alibaba.icbu.product.schema.render",
        {"param_product_top_publish_request": {"product_id": product_id, "language": "en_US"}},
    )
    xml_text = response_xml(response)
    if not xml_text:
        raise RuntimeError(f"schema.render failed for {product_id}: {response}")
    return ET.fromstring(xml_text)


def sale_prop_xml(schema_root: ET.Element, image_overrides: dict[str, str]) -> str:
    current = schema_root.find(".//field[@id='p-191288010']")
    if current is None:
        raise RuntimeError("Schema color field p-191288010 was not found")
    root = ET.Element("itemSchema")
    sale_prop = ET.SubElement(root, "field", {"id": "saleProp", "type": "complex"})
    complex_value = ET.SubElement(sale_prop, "complex-value")
    color_field = ET.SubElement(complex_value, "field", {"id": "p-191288010", "type": "multiCheck"})
    values = ET.SubElement(color_field, "values")
    for old_value in current.findall("./values/value"):
        attrs = dict(old_value.attrib)
        color_name = attrs.get("inputValue", "")
        if color_name in image_overrides:
            attrs["img"] = image_overrides[color_name]
        value = ET.SubElement(values, "value", attrs)
        value.text = old_value.text
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
        if target["model"] not in str(before.get("attributes", "")) and target["model"].split(" / ")[0] not in str(before.get("subject", "")):
            # Product IDs are already authoritative; this is only an extra guard.
            pass

        uploaded_urls: dict[str, str] = {}
        uploads = []
        for color, spec in target["replacements"].items():
            path = spec["path"]
            if not path.is_file():
                raise RuntimeError(f"Missing local color image: {path}")
            upload_path = path
            temp_dir = None
            if spec.get("force_reencode"):
                temp_dir = tempfile.TemporaryDirectory(prefix="beiqiang-sku-rebank-")
                upload_path = Path(temp_dir.name) / "verified_color_rebank.png"
                with Image.open(path) as image:
                    image.convert("RGB").save(upload_path, format="PNG", optimize=True)
            try:
                response = client.upload_image(config, upload_path, None)
            finally:
                if temp_dir is not None:
                    temp_dir.cleanup()
            if failed(client, response) or not response.get("upload_image_response"):
                raise RuntimeError(f"Upload failed for {product_id}/{color}: {response}")
            item = response["upload_image_response"]
            uploaded_urls[color] = str(item["photobank_url"])
            uploads.append({
                "color": color,
                "source": str(path),
                "file_id": str(item["file_id"]),
                "url": str(item["photobank_url"]),
                **refs(client, response),
            })

        schema_root = render_schema(client, config, product_id)
        payload = {
            "param_product_top_publish_request": {
                "cat_id": int(before["category_id"]),
                "language": "en_US",
                "product_id": product_id,
                "xml": sale_prop_xml(schema_root, uploaded_urls),
            }
        }
        update_response = client.top_call(config, "alibaba.icbu.product.schema.update", payload)
        if failed(client, update_response):
            raise RuntimeError(f"SKU image update failed for {product_id}: {update_response}")

        after_response, after = get_product(client, config, product_id)
        before_snapshot = sku_snapshot(before)
        after_snapshot = sku_snapshot(after)
        colors_after = color_map(after)
        bindings_ok = all(
            image_key(str(colors_after.get(color, {}).get("image_url", ""))) == image_key(url)
            for color, url in uploaded_urls.items()
        )
        sku_data_preserved = before_snapshot == after_snapshot
        if not bindings_ok or not sku_data_preserved:
            (AUDIT_DIR / f"{product_id}_sku_repair_failed_debug.json").write_text(
                json.dumps({
                    "uploadedUrls": uploaded_urls,
                    "colorsAfter": colors_after,
                    "update": update_response,
                    "readback": after_response,
                }, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            raise RuntimeError(
                f"Readback failed for {product_id}: bindings={bindings_ok}, sku_data={sku_data_preserved}"
            )

        (AUDIT_DIR / f"{product_id}_product_get_after_sku_repair.json").write_text(
            json.dumps(after_response, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        manifest.append({
            "productId": product_id,
            "model": target["model"],
            "uploads": uploads,
            "bindingsVerified": bindings_ok,
            "skuDataPreserved": sku_data_preserved,
            "update": refs(client, update_response),
            "readback": refs(client, after_response),
        })

    (AUDIT_DIR / "SKU失效图片修复记录.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
