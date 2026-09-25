"""Replace HR039-A with the verified BQ036/8025 product through Alibaba Schema API.

Default mode is a read-only dry run. Pass --apply to update only product
1601943650395. The source product 1601924292931 is never modified.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import time
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT_PATH = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG_PATH = Path.home() / ".config/beiqiang/alibaba-openapi.json"
OUT_DIR = ROOT / "02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21"
RECEIPT_PATH = OUT_DIR / "HR039-A_替换为BQ036_8025_API回执.json"

SOURCE_PRODUCT_ID = 1601924292931
TARGET_PRODUCT_ID = 1601943650395
SOURCE_MODEL = "BQ036 / 8025"
TARGET_MODEL = "HR039-A / 8025"
ALLOWED_TARGET_MODELS = {"HR039-A", "BQ036 / 8025", TARGET_MODEL}
SOURCE_PRICE_CNY = 58.00
USD_CNY_REFERENCE = 6.7487  # SAFE/CFETS central parity, 2026-09-21
MIN_MARKUP = 1.30
PRICE_LADDER = [(2, "12.90"), (50, "12.50"), (100, "12.00")]
TITLE = (
    "Wholesale Model 8025 High Top Knit Slip-On Casual Walking Shoes "
    "EVA Sole EU 35-45 for Importers and Wholesalers"
)
KEYWORDS = (
    "high top knit slip on walking shoes wholesale sock sneakers "
    "EVA sole casual shoes model 8025 footwear supplier"
)
HIGHLIGHTS = (
    "Verified Model 8025 uses a high-top knitted textile upper, slip-on "
    "construction and EVA sole. Available source colors are Black/White and "
    "All Black in EU sizes 35-45. Logo, insole, color and packaging requests "
    "can be discussed after quantity and specification review. Freight is "
    "quoted separately according to destination and order quantity."
)


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
        "message": response.get("message") or response.get("msg_info"),
        "error": client.api_error(response),
    }


def failed(client, response: dict) -> bool:
    return bool(client.api_error(response)) or response.get("biz_success") is False or response.get("model") is False


def top_call_retry(client, config, method: str, params: dict, attempts: int = 3) -> dict:
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return client.top_call(config, method, params)
        except Exception as exc:
            last_error = exc
            transient = any(token in str(exc).lower() for token in ("ssl", "eof", "timed out", "connection reset"))
            if not transient or attempt == attempts:
                raise
            time.sleep(attempt * 2)
    raise RuntimeError(f"API transport failed after retries: {last_error}")


def get_product(client, config, product_id: int):
    response = top_call_retry(
        client,
        config,
        "alibaba.icbu.product.get",
        {"product_id": product_id, "language": "ENGLISH"},
    )
    product = response.get("product")
    if failed(client, response) or not product:
        raise RuntimeError(f"product.get failed for {product_id}: {refs(client, response)}")
    return response, product


def render_schema(client, config, product_id: int):
    response = top_call_retry(
        client,
        config,
        "alibaba.icbu.product.schema.render",
        {"param_product_top_publish_request": {"product_id": product_id, "language": "en_US"}},
    )
    xml_text = response.get("data")
    if not isinstance(xml_text, str):
        raise RuntimeError(f"schema.render failed for {product_id}: {refs(client, response)}")
    return response, ET.fromstring(xml_text)


def field(root: ET.Element, field_id: str) -> ET.Element:
    found = root.find(f".//field[@id='{field_id}']")
    if found is None:
        raise RuntimeError(f"required schema field missing: {field_id}")
    return found


def set_single_value(root: ET.Element, field_id: str, value: str) -> None:
    node = field(root, field_id).find("./value")
    if node is None:
        raise RuntimeError(f"schema field has no direct value: {field_id}")
    node.text = value


def set_all_values(root: ET.Element, field_id: str, value: str) -> None:
    nodes = root.findall(f".//field[@id='{field_id}']/value")
    if not nodes:
        raise RuntimeError(f"schema field has no value nodes: {field_id}")
    for node in nodes:
        node.text = value


def replace_keyword_value(root: ET.Element) -> None:
    keywords = field(root, "productKeywords")
    values = keywords.findall(".//field/value")
    if not values:
        # Some older live products render an empty complex field because their
        # legacy keyword value was blank. Rebuild the current nested shape.
        for child in list(keywords):
            keywords.remove(child)
        keywords.set("type", "complex")
        complex_value = ET.SubElement(keywords, "complex-value")
        keyword_field = ET.SubElement(
            complex_value,
            "field",
            {"id": "productKeywords_0", "type": "input"},
        )
        ET.SubElement(keyword_field, "value").text = KEYWORDS
        return
    values[0].text = KEYWORDS
    for extra in values[1:]:
        extra.text = ""


def replace_prices(root: ET.Element) -> None:
    ladder = field(root, "ladderPrice")
    candidates = [node for node in ladder.findall(".//field[@type='complex']") if (node.attrib.get("id") or "").startswith("ladderPrice_")]
    rows = {}
    for node in candidates:
        quantity_node = node.find(".//field[@id='quantity']/value")
        price_node = node.find(".//field[@id='price']/value")
        if quantity_node is not None and price_node is not None:
            rows[node.attrib["id"]] = node
    expected = {"ladderPrice_0", "ladderPrice_1", "ladderPrice_2"}
    if not expected.issubset(rows):
        raise RuntimeError(f"unexpected ladder row IDs: {sorted(rows)}")
    # Alibaba validates by the numeric field suffix, not XML document order.
    for index, (quantity, price) in enumerate(PRICE_LADDER):
        row = rows[f"ladderPrice_{index}"]
        quantity_node = row.find(".//field[@id='quantity']/value")
        price_node = row.find(".//field[@id='price']/value")
        if quantity_node is None or price_node is None:
            raise RuntimeError(f"incomplete ladder row: ladderPrice_{index}")
        quantity_node.text = str(quantity)
        price_node.text = price
    # The current schema exposes an optional fourth empty row. Keep it empty.
    for row_id, row in rows.items():
        if row_id in expected:
            continue
        for node in row.findall(".//field[@id='quantity']/value") + row.findall(".//field[@id='price']/value"):
            node.text = ""


def replace_sku_codes(root: ET.Element) -> None:
    nodes = root.findall(".//field[@id='skuOuterId']/value")
    if len(nodes) != 22:
        raise RuntimeError(f"expected 22 source SKUs, got {len(nodes)}")
    seen = set()
    for node in nodes:
        old = node.text or ""
        if not old.startswith("BQ036-"):
            raise RuntimeError(f"unexpected source SKU code: {old}")
        node.text = old.replace("BQ036-", "HR039-A-8025-", 1)
        if node.text in seen:
            raise RuntimeError(f"duplicate target SKU code: {node.text}")
        seen.add(node.text)


def build_target_xml(source_schema: ET.Element) -> str:
    root = deepcopy(source_schema)
    set_single_value(root, "productTitle", TITLE)
    set_all_values(root, "p-3", TARGET_MODEL)
    set_single_value(root, "textDesc", HIGHLIGHTS)
    replace_keyword_value(root)
    replace_prices(root)
    replace_sku_codes(root)
    return ET.tostring(root, encoding="unicode")


def ladder_debug(xml: str) -> list[dict]:
    root = ET.fromstring(xml)
    ladder = field(root, "ladderPrice")
    result = []
    for node in ladder.findall(".//field[@type='complex']"):
        quantity = node.find(".//field[@id='quantity']/value")
        price = node.find(".//field[@id='price']/value")
        if quantity is not None or price is not None:
            result.append(
                {
                    "field_id": node.attrib.get("id"),
                    "quantity": quantity.text if quantity is not None else None,
                    "price": price.text if price is not None else None,
                }
            )
    return result


def product_snapshot(product: dict) -> dict:
    attrs = {str(row.get("attribute_name")): row.get("value_name") for row in product.get("attributes", [])}
    colors = []
    sizes = []
    for group in (product.get("product_sku") or {}).get("sku_attributes", []):
        names = [str(row.get("system_value_name")) for row in group.get("values", [])]
        if group.get("attribute_name") == "Color":
            colors = names
        if group.get("attribute_name") == "EUR Size":
            sizes = names
    skus = (product.get("product_sku") or {}).get("skus", [])
    prices = sorted({p.get("price") for sku in skus for p in sku.get("bulk_discount_prices", [])})
    return {
        "subject": product.get("subject"),
        "category_id": product.get("category_id"),
        "status": product.get("status"),
        "display": product.get("display"),
        "url": product.get("pc_detail_url"),
        "model": attrs.get("Model Number"),
        "colors": colors,
        "sizes": sizes,
        "sku_count": len(skus),
        "prices": prices,
        "moq": (product.get("sourcing_trade") or {}).get("min_order_quantity"),
        "main_image_count": len((product.get("main_image") or {}).get("images", [])),
        "detail_image_count": len((((product.get("struct_detail") or {}).get("detail_image") or {}).get("images") or [])),
        "company_image_count": len((((product.get("struct_detail") or {}).get("company_image") or {}).get("images") or [])),
    }


def verify(after: dict, source: dict) -> dict:
    snap = product_snapshot(after)
    source_snap = product_snapshot(source)
    low_price = min(float(value) for value in snap["prices"])
    markup = low_price * USD_CNY_REFERENCE / SOURCE_PRICE_CNY
    return {
        "target_model_ok": snap["model"] == TARGET_MODEL,
        "title_ok": snap["subject"] == TITLE,
        "category_matches_source": snap["category_id"] == source_snap["category_id"],
        "colors_match_source": set(snap["colors"]) == set(source_snap["colors"]),
        "sizes_match_source": set(snap["sizes"]) == set(source_snap["sizes"]),
        "sku_count_matches_source": snap["sku_count"] == source_snap["sku_count"] == 22,
        "gallery_complete": snap["main_image_count"] == 6 and snap["detail_image_count"] >= 4 and snap["company_image_count"] == 5,
        "minimum_price_usd": low_price,
        "price_markup_multiple_at_reference_fx": round(markup, 4),
        "price_floor_ok": markup >= MIN_MARKUP,
        "submitted_or_live": snap["status"] in {"modified", "approved"},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="submit the target product update")
    args = parser.parse_args()
    client = load_client()
    config = client.load_config(CONFIG_PATH)

    source_response, source = get_product(client, config, SOURCE_PRODUCT_ID)
    target_response, before = get_product(client, config, TARGET_PRODUCT_ID)
    source_snap = product_snapshot(source)
    before_snap = product_snapshot(before)
    if source_snap["model"] != SOURCE_MODEL:
        raise RuntimeError(f"source identity mismatch: {source_snap['model']}")
    if before_snap["model"] not in ALLOWED_TARGET_MODELS:
        raise RuntimeError(f"target identity mismatch: {before_snap['model']}")
    if source_snap["main_image_count"] != 6 or source_snap["detail_image_count"] < 4 or source_snap["company_image_count"] != 5:
        raise RuntimeError(f"source gallery gate failed: {source_snap}")

    render_response, source_schema = render_schema(client, config, SOURCE_PRODUCT_ID)
    xml = build_target_xml(source_schema)
    planned_markup = float(PRICE_LADDER[-1][1]) * USD_CNY_REFERENCE / SOURCE_PRICE_CNY
    plan = {
        "mode": "apply" if args.apply else "dry-run",
        "source": {"product_id": SOURCE_PRODUCT_ID, **source_snap},
        "target_before": {"product_id": TARGET_PRODUCT_ID, **before_snap},
        "target_title": TITLE,
        "target_model": TARGET_MODEL,
        "price_ladder_usd": PRICE_LADDER,
        "source_price_cny": SOURCE_PRICE_CNY,
        "usd_cny_reference": USD_CNY_REFERENCE,
        "minimum_markup_multiple": MIN_MARKUP,
        "planned_lowest_price_markup_multiple": round(planned_markup, 4),
        "source_refs": refs(client, source_response),
        "target_before_refs": refs(client, target_response),
        "render_refs": refs(client, render_response),
        "xml_chars": len(xml),
        "target_ladder_nodes": ladder_debug(xml),
    }
    if not args.apply:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return

    update_response = top_call_retry(
        client,
        config,
        "alibaba.icbu.product.schema.update",
        {
            "param_product_top_publish_request": {
                "cat_id": int(source["category_id"]),
                "language": "en_US",
                "product_id": TARGET_PRODUCT_ID,
                "xml": xml,
            }
        },
    )
    if failed(client, update_response):
        raise RuntimeError(f"schema.update failed: {refs(client, update_response)}")

    after_response, after = get_product(client, config, TARGET_PRODUCT_ID)
    verification = verify(after, source)
    receipt = {
        **plan,
        "update_refs": refs(client, update_response),
        "readback_refs": refs(client, after_response),
        "target_after": product_snapshot(after),
        "verification": verification,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RECEIPT_PATH.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if not all(value for key, value in verification.items() if key not in {"minimum_price_usd", "price_markup_multiple_at_reference_fx"}):
        raise RuntimeError(f"readback verification failed; receipt={RECEIPT_PATH}")


if __name__ == "__main__":
    main()
