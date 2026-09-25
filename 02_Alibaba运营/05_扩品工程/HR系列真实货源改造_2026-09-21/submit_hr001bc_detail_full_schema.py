"""Submit verified 9002 details and remove Fit Type when minimal Schema did not persist."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
MANIFEST = HERE / "HR001_9002_最终图片绑定清单.json"
CONFIG = Path.home() / ".config/beiqiang/alibaba-openapi.json"
PRODUCTS = {
    "HR001-B": {
        "id": 1601943493004,
        "title": "Men's Knit Slip-On Walking Shoes EVA Sole EU 38-47 Wholesale OEM Supplier Model 9002",
        "d1": "https://sc04.alicdn.com/kf/H85b21cb197004ec69e0d67d000411ca1j/286385890/H85b21cb197004ec69e0d67d000411ca1j.jpg",
    },
    "HR001-C": {
        "id": 1601943474137,
        "title": "Private Label Men's Textile Slip-On Walking Shoes EVA Outsole EU 38-47 Wholesale Model 9002",
        "d1": "https://sc04.alicdn.com/kf/Hb2da07ff92fe457282a485fe35269cd9y/286385890/Hb2da07ff92fe457282a485fe35269cd9y.jpg",
    },
}


def load_client():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
    assert spec and spec.loader
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    return api


def detail_group(urls):
    group = ET.Element("complex-values")
    images = ET.SubElement(group, "field", {"id": "images", "type": "multiComplex"})
    for url in urls:
        if not url.startswith("https://sc04.alicdn.com/kf/"):
            raise RuntimeError("Detail image is not an official CDN URL")
        image = ET.SubElement(images, "complex-values")
        field = ET.SubElement(image, "field", {"id": "imageURL", "type": "input"})
        ET.SubElement(field, "value").text = "//" + url.removeprefix("https://")
    gallery = ET.SubElement(group, "field", {"id": "gallery", "type": "singleCheck"})
    ET.SubElement(gallery, "value").text = "350"
    return group


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("listing", choices=sorted(PRODUCTS))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    target = PRODUCTS[args.listing]
    api = load_client()
    config = api.load_config(CONFIG)
    product_reply = api.top_call(config, "alibaba.icbu.product.get", {
        "product_id": target["id"], "language": "ENGLISH",
    })
    if api.api_error(product_reply):
        raise RuntimeError(f"product.get: {api.api_error(product_reply)}")
    product = product_reply.get("product") or {}
    attrs = {str(x.get("attribute_name")): x.get("value_name") for x in product.get("attributes") or []}
    skus = (product.get("product_sku") or {}).get("skus") or []
    if not (
        (product.get("status"), product.get("display")) == ("approved", "Y")
        and product.get("subject") == target["title"]
        and attrs.get("Model Number") == args.listing + " / 9002"
        and len(skus) == 20
        and all(str(x.get("sku_code", "")).startswith(args.listing + "-9002-") for x in skus)
        and len((product.get("main_image") or {}).get("images") or []) == 6
        and len((((product.get("struct_detail") or {}).get("company_image") or {}).get("images") or [])) == 5
    ):
        raise RuntimeError("Product identity/status/images/SKU guard failed")
    inv_reply = api.top_call(config, "alibaba.icbu.product.sku.inventory.get", {
        "product_id": target["id"], "language": "en_US",
    })
    result = inv_reply.get("result") or {}
    if result.get("success") is not True:
        raise RuntimeError(f"inventory.get: {inv_reply}")
    inventory = result.get("data_list") or []
    if isinstance(inventory, dict):
        inventory = inventory.get("data") or []
    if isinstance(inventory, dict):
        inventory = [inventory]
    if len(inventory) != 20 or any(int(x["inventory"]) != 999 for x in inventory):
        raise RuntimeError("20/20 stock marker is not 999; no full-Schema repair")

    render_reply = api.top_call(config, "alibaba.icbu.product.schema.render", {
        "param_product_top_publish_request": {
            "product_id": target["id"], "language": "en_US",
        },
    })
    if api.api_error(render_reply) or not isinstance(render_reply.get("data"), str):
        raise RuntimeError(f"schema.render unavailable: {api.api_error(render_reply)}")
    schema = ET.fromstring(render_reply["data"])
    stock_rows = schema.findall("./field[@id='sku']/complex-values/field[@id='skuStock']")
    if len(stock_rows) != 20 or any(
        row.findtext("./values/value") != "999" for row in stock_rows
    ):
        raise RuntimeError("Rendered Schema does not retain 20/20 stock marker")
    video = schema.findtext("./field[@id='imageVideo']/value")
    if video not in ("6000344840202", None, ""):
        raise RuntimeError(f"Unexpected main video in current Schema: {video}")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    assets = {row["role"]: row for row in manifest["items"]}
    urls = [target["d1"]] + [assets[role]["url"] for role in (
        "D2_verified_specs", "D3_colors_sizes", "D4_price_quote", "D5_oem_project_inputs"
    )]
    detail = schema.find("./field[@id='detailImage']")
    custom = schema.find("./field[@id='customMoreProperty']")
    if detail is None or custom is None:
        raise RuntimeError("Current structured detail or custom properties missing")
    for row in list(detail.findall("./complex-values")):
        detail.remove(row)
    detail.insert(0, detail_group(urls))
    for child in list(custom):
        if child.tag in ("complex-value", "complex-values", "value", "values"):
            custom.remove(child)
    custom.insert(0, ET.Element("complex-value"))

    xml = ET.tostring(schema, encoding="unicode")
    receipt = {
        "listing": args.listing, "product_id": target["id"],
        "checked_at": datetime.now().astimezone().isoformat(),
        "mode": "apply" if args.apply else "dry_run",
        "product_request_id": product_reply.get("request_id"),
        "inventory_request_id": inv_reply.get("request_id"),
        "render_request_id": render_reply.get("request_id"),
        "before_fit_type": attrs.get("Fit Type"),
        "before_detail_count": len((((product.get("struct_detail") or {}).get("detail_image") or {}).get("images") or [])),
        "stock_marker_count": len(stock_rows),
        "detail_urls": urls, "video_in_schema": video,
        "xml_sha256": hashlib.sha256(xml.encode("utf-8")).hexdigest(),
        "xml_length": len(xml),
    }
    if args.apply:
        reply = api.top_call(config, "alibaba.icbu.product.schema.update", {
            "param_product_top_publish_request": {
                "cat_id": int(product["category_id"]), "language": "en_US",
                "product_id": target["id"], "xml": xml,
            },
        })
        receipt["update_request_id"] = reply.get("request_id")
        receipt["update_trace_id"] = reply.get("trace_id") or reply.get("_trace_id_")
        receipt["update_error"] = api.api_error(reply)
        receipt["update_biz_success"] = reply.get("biz_success")
        if receipt["update_error"] or receipt["update_biz_success"] is False or reply.get("model") is False:
            receipt["passed"] = False
        else:
            after_reply = api.top_call(config, "alibaba.icbu.product.get", {
                "product_id": target["id"], "language": "ENGLISH",
            })
            after = after_reply.get("product") or {}
            receipt["after_request_id"] = after_reply.get("request_id")
            receipt["after_status"] = after.get("status")
            receipt["after_display"] = after.get("display")
            receipt["passed"] = after.get("status") in ("modified", "approved")
    else:
        receipt["passed"] = True
    out = HERE / f"{args.listing}_9002_详情与旧属性全Schema_{'正式' if args.apply else '预检'}_回执.json"
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in receipt.items() if k != "detail_urls"}, ensure_ascii=False))
    if not receipt["passed"]:
        raise RuntimeError("Full current-Schema repair not confirmed")


if __name__ == "__main__":
    main()
