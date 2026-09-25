"""Migrate HR002-A's API-supported fields to sourced model 2618.

Dry run by default. Structured detail remains a separate seller-editor step;
do not call the product complete merely because this API update succeeds.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
PROJECT = Path(__file__).parent
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
MANIFEST = PROJECT / "HR002_2618_图片银行映射.json"
PRODUCT_ID = 1601943305914
CATEGORY_ID = 201334413
SOURCE_URL = "https://luqi.sooxie.com/detail/2434016"
TITLE = "Wholesale Men's Lace Up Low Top Casual Walking Shoes Rubber Sole EU 39-48 Model 2618"
MODEL = "HR002-A / 2618"
KEYWORDS = "men lace up low top casual walking shoes rubber sole wholesale EU 39 48 model 2618"
SUMMARY = (
    "Model 2618 is a men's low-top lace-up casual shoe offered in Black, Khaki and Dark Brown, "
    "EU 39-48, with mesh lining and rubber midsole/outsole. Beiqiang serves B2B wholesale buyers; "
    "color-size mix, quantity, packing, delivery and any customization request are confirmed "
    "against the order requirements before quotation."
)
SOURCE_CNY = 68.0
USD_CNY_REFERENCE = 6.7019  # BOC 2026-09-24 spot-buy reference, CNY per USD
LADDER = ((2, "16.90"), (50, "16.40"), (100, "15.90"))
SIZES = tuple(range(39, 49))
COLORS = (
    ("Black", "3327837", "BLACK", 1),
    ("Khaki", "-2", "KHAKI", 2),
    ("Dark Brown", "-3", "DARKBROWN", 3),
)
PLAN = PROJECT / "HR002-A_2618_整页换款_API字段预检.json"
RECEIPT = PROJECT / "HR002-A_2618_整页换款_API字段提交回执.json"

spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
assert spec and spec.loader
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)
config = api.load_config(Path.home() / ".config/beiqiang/alibaba-openapi.json")


def call(method: str, params: dict) -> dict:
    response = api.top_call(config, method, params)
    error = api.api_error(response)
    if error:
        raise RuntimeError({"method": method, "error": error, "request_id": response.get("request_id")})
    return response


def field(root: ET.Element, field_id: str) -> ET.Element:
    found = root.find(f"./field[@id='{field_id}']")
    if found is None:
        raise RuntimeError(f"missing Schema field: {field_id}")
    return found


def set_value(root: ET.Element, field_id: str, value: str) -> None:
    holder = field(root, field_id)
    node = holder.find("./value")
    if node is None:
        node = ET.SubElement(holder, "value")
    node.text = value


def replace_complex(holder: ET.Element, replacement: ET.Element) -> None:
    previous = holder.find("./complex-value")
    if previous is not None:
        holder.remove(previous)
    holder.insert(0, replacement)


def build_attributes(root: ET.Element) -> None:
    holder = field(root, "icbuCatProp")
    value = ET.Element("complex-value")

    def one(field_id: str, name: str, label: str, option_id: str) -> None:
        node = ET.SubElement(value, "field", {"id": field_id, "name": name, "type": "singleCheck"})
        ET.SubElement(node, "value", {"inputValue": label}).text = option_id

    def many(field_id: str, name: str, label: str, option_id: str) -> None:
        node = ET.SubElement(value, "field", {"id": field_id, "name": name, "type": "multiCheck"})
        ET.SubElement(ET.SubElement(node, "values"), "value", {"inputValue": label}).text = option_id

    one("p-1", "Place of Origin", "China", "100000458")
    node = ET.SubElement(value, "field", {"id": "p-3", "name": "Model Number", "type": "input"})
    ET.SubElement(node, "value", {"inputValue": MODEL}).text = "-3"
    one("p-200000388", "Closure Type", "Lace-up", "80806811")
    many("p-191290426", "Outsole Material", "Rubber", "3338114")
    many("p-20700", "Midsole Material", "Rubber", "3338114")
    many("p-191290430", "Lining Material", "Mesh", "6821988")
    many("p-200000486", "Toe Style", "Round Toe", "556500746")
    many("p-191288243", "Style", "Walking Shoes", "19077592")
    replace_complex(holder, value)


def build_variants(root: ET.Element, assets: dict[tuple[str, int], dict]) -> None:
    holder = field(root, "saleProp")
    value = ET.Element("complex-value")
    size_field = ET.SubElement(value, "field", {"id": "p-222038415", "name": "EUR Size", "type": "multiCheck"})
    size_values = ET.SubElement(size_field, "values")
    for index, size in enumerate(SIZES, start=2):
        ET.SubElement(size_values, "value", {"inputValue": f"EU {size}"}).text = f"-{index}"
    color_field = ET.SubElement(value, "field", {"id": "p-191288010", "name": "Color", "type": "multiCheck"})
    color_values = ET.SubElement(color_field, "values")
    for label, option_id, _, slot in COLORS:
        ET.SubElement(color_values, "value", {
            "inputValue": label, "img": assets[("sku", slot)]["url"]
        }).text = option_id
    replace_complex(holder, value)

    sku_holder = field(root, "sku")
    for child in list(sku_holder.findall("./complex-values")):
        sku_holder.remove(child)
    for color_label, color_id, code, _ in COLORS:
        for index, size in enumerate(SIZES, start=2):
            size_id = f"-{index}"
            row = ET.SubElement(sku_holder, "complex-values")
            ET.SubElement(row, "field", {"id": "price", "name": "Single piece price (USD)", "type": "input"})
            stock = ET.SubElement(row, "field", {"id": "skuStock", "name": "Inventory", "type": "multiInput"})
            ET.SubElement(ET.SubElement(stock, "values"), "value", {
                "srcValue": "999", "warehouseCode": "CN_LOCAL_01"
            }).text = "999"
            outer = ET.SubElement(row, "field", {"id": "skuOuterId", "name": "Commodity code", "type": "input"})
            ET.SubElement(outer, "value").text = f"HR002-A-2618-{code}-{size}"
            ET.SubElement(row, "field", {"id": "outerSupplyId", "name": "supply id", "type": "input"})
            props = ET.SubElement(row, "field", {"id": "props", "name": "", "type": "multiInput"})
            pair = ET.SubElement(props, "values")
            ET.SubElement(pair, "value", {
                "propValueId": color_id, "propId": "191288010", "propName": "p-191288010", "propValueName": color_label
            }).text = f"191288010:{color_id}"
            ET.SubElement(pair, "value", {
                "propValueId": size_id, "propId": "222038415", "propName": "p-222038415", "propValueName": f"EU {size}"
            }).text = f"222038415:{size_id}"


def build_prices(root: ET.Element) -> None:
    holder = field(root, "ladderPrice")
    value = ET.Element("complex-value")
    for index, (quantity, price) in enumerate(LADDER):
        outer = ET.SubElement(value, "field", {"id": f"ladderPrice_{index}", "type": "complex"})
        inner = ET.SubElement(outer, "complex-value")
        q = ET.SubElement(inner, "field", {"id": "quantity", "type": "input"})
        ET.SubElement(q, "value").text = str(quantity)
        p = ET.SubElement(inner, "field", {"id": "price", "type": "input"})
        ET.SubElement(p, "value").text = price
    replace_complex(holder, value)


def build_images(root: ET.Element, assets: dict[tuple[str, int], dict]) -> None:
    holder = field(root, "scImages")
    value = ET.Element("complex-value")
    for index, asset in enumerate([assets[("main_A", 1)]] + [assets[("main_shared", n)] for n in range(2, 7)]):
        image_field = ET.SubElement(value, "field", {"id": f"scImages_{index}", "type": "input"})
        ET.SubElement(image_field, "value", {"fileFlag": "no", "fileId": str(asset["file_id"])}).text = asset["url"].replace("https:", "")
    replace_complex(holder, value)


def build_xml(render_root: ET.Element, assets: dict[tuple[str, int], dict]) -> str:
    build_attributes(render_root)
    build_variants(render_root, assets)
    build_prices(render_root)
    build_images(render_root, assets)
    set_value(render_root, "productTitle", TITLE)
    set_value(render_root, "textDesc", SUMMARY)
    set_value(render_root, "minOrderQuantity", "2")
    keywords = field(render_root, "productKeywords")
    value = ET.Element("complex-value")
    item = ET.SubElement(value, "field", {"id": "productKeywords_0", "type": "input"})
    ET.SubElement(item, "value").text = KEYWORDS
    replace_complex(keywords, value)

    update = ET.Element("itemSchema")
    keep = {"productTitle", "icbuCatProp", "saleProp", "sku", "ladderPrice", "scImages", "textDesc", "minOrderQuantity", "productKeywords"}
    for source in render_root.findall("./field"):
        if source.get("id") not in keep:
            continue
        clone = deepcopy(source)
        for tag in ("rules", "options", "fields", "label-group"):
            for child in list(clone.findall(f"./{tag}")):
                clone.remove(child)
        for sku_id in list(clone.findall(".//field[@id='skuId']")):
            for parent in clone.iter():
                if sku_id in list(parent):
                    parent.remove(sku_id)
                    break
        update.append(clone)
    return ET.tostring(update, encoding="unicode")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    assets = {(row["role"], int(row["slot"])): row for row in manifest["assets"]}
    expected = {("main_A", 1), *( ("main_shared", n) for n in range(2, 7) ), *( ("sku", n) for n in range(1, 4) )}
    if not expected <= assets.keys():
        raise RuntimeError({"missing_assets": list(expected - assets.keys())})
    for key in expected:
        item = assets[key]
        if not item["url"].startswith("https://sc04.alicdn.com/") or not item["file_id"]:
            raise RuntimeError({"invalid_asset": key})

    formal = call("alibaba.icbu.product.get", {"product_id": PRODUCT_ID, "language": "ENGLISH"})
    product = formal.get("product") or {}
    attrs = {row.get("attribute_name"): row.get("value_name") for row in product.get("attributes") or []}
    if product.get("status") != "approved" or product.get("display") != "Y" or attrs.get("Model Number") not in {"HR002-A / S6077", MODEL}:
        raise RuntimeError({"unexpected_product_state": {"status": product.get("status"), "model": attrs.get("Model Number")}})
    render = call("alibaba.icbu.product.schema.render", {
        "param_product_top_publish_request": {"product_id": PRODUCT_ID, "language": "en_US"}
    })
    root = ET.fromstring(render["data"])
    video_node = root.find("./field[@id='imageVideo']/value")
    xml = build_xml(root, assets)
    price_cny = float(LADDER[-1][1]) * USD_CNY_REFERENCE
    plan = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "apply" if args.apply else "dry-run",
        "product_id": PRODUCT_ID,
        "source_url": SOURCE_URL,
        "source_price_cny": SOURCE_CNY,
        "usd_cny_reference": USD_CNY_REFERENCE,
        "minimum_price_usd": LADDER[-1][1],
        "minimum_price_cny_reference": round(price_cny, 2),
        "markup_pct_reference": round((price_cny / SOURCE_CNY - 1) * 100, 2),
        "target_title": TITLE,
        "target_model": MODEL,
        "target_colors": [color[0] for color in COLORS],
        "target_sizes": [f"EU {size}" for size in SIZES],
        "target_sku_count": len(COLORS) * len(SIZES),
        "target_stock_marker": 999,
        "target_main_image_urls": [assets[("main_A", 1)]["url"]] + [assets[("main_shared", n)]["url"] for n in range(2, 7)],
        "structured_detail_pending_ui": True,
        "existing_main_video_id": video_node.text if video_node is not None else None,
        "formal_request_id": formal.get("request_id"),
        "render_request_id": render.get("request_id"),
        "xml_sha256": hashlib.sha256(xml.encode()).hexdigest(),
        "xml_length": len(xml),
        "price_floor_pass": price_cny >= SOURCE_CNY * 1.30,
        "xml_has_old_model": "S6077" in xml,
        "xml_has_old_detail": "detailImage" in xml or "companyImage" in xml,
    }
    PLAN.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    if not plan["price_floor_pass"] or plan["xml_has_old_model"] or plan["xml_has_old_detail"]:
        raise RuntimeError({"preflight_failed": plan})
    if not args.apply:
        print(json.dumps({"plan": str(PLAN), "price_floor_pass": True, "sku_count": plan["target_sku_count"], "xml_sha256": plan["xml_sha256"]}, ensure_ascii=False))
        return

    response = call("alibaba.icbu.product.schema.update", {
        "param_product_top_publish_request": {
            "cat_id": CATEGORY_ID, "language": "en_US", "product_id": PRODUCT_ID, "xml": xml
        }
    })
    readback = call("alibaba.icbu.product.get", {"product_id": PRODUCT_ID, "language": "ENGLISH"})
    after = readback.get("product") or {}
    receipt = {
        **plan,
        "update_request_id": response.get("request_id"),
        "update_trace_id": response.get("trace_id"),
        "update_biz_success": response.get("biz_success"),
        "update_model": response.get("model"),
        "readback_request_id": readback.get("request_id"),
        "readback_status": after.get("status"),
        "readback_title": after.get("subject"),
        "readback_sku_count": len((after.get("product_sku") or {}).get("skus") or []),
        "readback_main_images": (after.get("main_image") or {}).get("images"),
    }
    RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"receipt": str(RECEIPT), "update_request_id": receipt["update_request_id"], "readback_status": receipt["readback_status"], "readback_title": receipt["readback_title"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
