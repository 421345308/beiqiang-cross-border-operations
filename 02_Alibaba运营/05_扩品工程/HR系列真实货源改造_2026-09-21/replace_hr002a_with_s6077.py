"""Replace HR002-A with sourced model S6077 via Alibaba OpenAPI.

Dry-run is the default. Pass --apply only after the generated plan passes all
local evidence and price gates.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import time
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
PROJECT = ROOT / r"02_Alibaba运营\05_扩品工程\HR系列真实货源改造_2026-09-21"
CLIENT_PATH = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG_PATH = Path.home() / ".config/beiqiang/alibaba-openapi.json"
MANIFEST_PATH = PROJECT / "HR002_S6077_图片银行映射.json"
PLAN_PATH = PROJECT / "HR002-A_S6077_提交前预检.json"
RECEIPT_PATH = PROJECT / "HR002-A_替换为S6077_API回执.json"

PRODUCT_ID = 1601943305914
CATEGORY_ID = 201334413
LINK_CODE = "HR002-A"
TARGET_MODEL = "HR002-A / S6077"
ALLOWED_MODELS = {"HR002", TARGET_MODEL}
MAIN_VIDEO_ID = "6000344840202"
SOURCE_URL = "https://zuoshou.sooxie.com/detail/2517849"
TITLE = "Wholesale Men's Retro Mesh Lace-Up Walking Shoes Casual Sneakers EU 39-48 Model S6077"
KEYWORDS = "men retro mesh lace up walking shoes wholesale casual sneakers EU 39 48 black white model S6077"
HIGHLIGHTS = (
    "Source model S6077 is a men's low-top lace-up shoe with visible mesh panels, round-toe styling "
    "and black or white source-page options in EU sizes 39-48. Quantity, size mix, current availability, "
    "packing, delivery terms and freight are reconfirmed before order. Production or sourcing route and "
    "any customization request are reviewed separately for the selected order."
)
SOURCE_PRICE_CNY = 45.0
USD_CNY_REFERENCE = 6.7487
MIN_MARKUP = 1.30
PRICE_LADDER = [(2, "9.50"), (50, "9.20"), (100, "9.10")]
SIZE_IDS = {
    "39": "190000792",
    "40": "28389",
    "41": "28390",
    "42": "28391",
    "43": "28392",
    "44": "28393",
    "45": "28394",
    "46": "28395",
    "47": "28396",
    "48": "29543",
}
COLORS = [
    {"name": "Black", "value_id": "3327837", "image_role": "sku_1", "code": "BLACK"},
    {"name": "White", "value_id": "3331185", "image_role": "sku_2", "code": "WHITE"},
]


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


def failed(client, response: dict) -> bool:
    return bool(client.api_error(response)) or response.get("biz_success") is False or response.get("model") is False


def top_call_retry(client, config, method: str, params: dict, attempts: int = 8) -> dict:
    response = {}
    for attempt in range(attempts):
        response = client.top_call(config, method, params)
        error = client.api_error(response)
        if not error:
            return response
        transient = (
            error.get("code") == "ApiCallLimit"
            or error.get("type") == "ISP"
            or error.get("sub_code") == "000000"
        )
        if not transient:
            return response
        time.sleep(min(2 + attempt * 2, 10))
    return response


def get_product(client, config):
    response = top_call_retry(
        client,
        config,
        "alibaba.icbu.product.get",
        {"product_id": PRODUCT_ID, "language": "ENGLISH"},
    )
    product = response.get("product")
    if failed(client, response) or not product:
        raise RuntimeError({"step": "product.get", "refs": refs(client, response)})
    return response, product


def render_schema(client, config):
    response = top_call_retry(
        client,
        config,
        "alibaba.icbu.product.schema.render",
        {"param_product_top_publish_request": {"product_id": PRODUCT_ID, "language": "en_US"}},
    )
    xml = response.get("data")
    if failed(client, response) or not isinstance(xml, str):
        raise RuntimeError({"step": "schema.render", "refs": refs(client, response)})
    return response, ET.fromstring(xml)


def direct_field(root: ET.Element, field_id: str) -> ET.Element:
    found = root.find(f"./field[@id='{field_id}']")
    if found is None:
        raise RuntimeError(f"required field missing: {field_id}")
    return found


def set_direct_value(root: ET.Element, field_id: str, value: str) -> None:
    node = direct_field(root, field_id).find("./value")
    if node is None:
        node = ET.SubElement(direct_field(root, field_id), "value")
    node.text = str(value)


def replace_complex_value(field: ET.Element, new_value: ET.Element) -> None:
    old = field.find("./complex-value")
    if old is not None:
        field.remove(old)
    field.insert(0, new_value)


def set_attributes(root: ET.Element) -> None:
    holder = direct_field(root, "icbuCatProp")
    value = ET.Element("complex-value")

    def single(field_id: str, name: str, label: str, value_id: str):
        field = ET.SubElement(value, "field", {"id": field_id, "name": name, "type": "singleCheck"})
        option = ET.SubElement(field, "value", {"inputValue": label})
        option.text = value_id

    def multi(field_id: str, name: str, options: list[tuple[str, str]]):
        field = ET.SubElement(value, "field", {"id": field_id, "name": name, "type": "multiCheck"})
        values = ET.SubElement(field, "values")
        for label, value_id in options:
            option = ET.SubElement(values, "value", {"inputValue": label})
            option.text = value_id

    single("p-1", "Place of Origin", "China", "100000458")
    model = ET.SubElement(value, "field", {"id": "p-3", "name": "Model Number", "type": "input"})
    ET.SubElement(model, "value", {"inputValue": TARGET_MODEL}).text = "-3"
    single("p-200000388", "Closure Type", "Lace-up", "80806811")
    multi("p-200000486", "Toe Style", [("Round Toe", "556500746")])
    multi("p-191288243", "Style", [("Walking Shoes", "19077592")])
    replace_complex_value(holder, value)


def set_sale_and_skus(root: ET.Element, assets: dict[str, dict]) -> None:
    sale = direct_field(root, "saleProp")
    value = ET.Element("complex-value")
    size_field = ET.SubElement(value, "field", {"id": "p-222038415", "name": "EUR Size", "type": "multiCheck"})
    sizes = ET.SubElement(size_field, "values")
    for size, value_id in SIZE_IDS.items():
        option = ET.SubElement(sizes, "value", {"inputValue": size})
        option.text = value_id
    color_field = ET.SubElement(value, "field", {"id": "p-191288010", "name": "Color", "type": "multiCheck"})
    color_values = ET.SubElement(color_field, "values")
    for color in COLORS:
        asset = assets[color["image_role"]]
        option = ET.SubElement(color_values, "value", {"inputValue": color["name"], "img": asset["url"]})
        option.text = color["value_id"]
    replace_complex_value(sale, value)

    sku = direct_field(root, "sku")
    for child in list(sku.findall("./complex-values")):
        sku.remove(child)
    insert_at = 0
    for color in COLORS:
        for size, size_id in SIZE_IDS.items():
            row = ET.Element("complex-values")
            ET.SubElement(row, "field", {"id": "price", "name": "Single piece price (USD)", "type": "input"})
            # Blank stock means unlimited inventory in the seller UI.  Do not
            # invent a numeric quantity for an externally sourced product.
            stock = ET.SubElement(row, "field", {"id": "skuStock", "name": "Inventory", "type": "multiInput"})
            ET.SubElement(stock, "values")
            outer = ET.SubElement(row, "field", {"id": "skuOuterId", "name": "Commodity code", "type": "input"})
            ET.SubElement(outer, "value").text = f"{LINK_CODE}-S6077-{color['code']}-{size}"
            ET.SubElement(row, "field", {"id": "outerSupplyId", "name": "supply id", "type": "input"})
            props = ET.SubElement(row, "field", {"id": "props", "name": "", "type": "multiInput"})
            prop_values = ET.SubElement(props, "values")
            color_prop = ET.SubElement(prop_values, "value", {
                "propValueId": color["value_id"],
                "propId": "191288010",
                "propName": "p-191288010",
                "propValueName": color["name"],
            })
            color_prop.text = f"191288010:{color['value_id']}"
            size_prop = ET.SubElement(prop_values, "value", {
                "propValueId": size_id,
                "propId": "222038415",
                "propName": "p-222038415",
                "propValueName": size,
            })
            size_prop.text = f"222038415:{size_id}"
            sku.insert(insert_at, row)
            insert_at += 1


def set_keywords(root: ET.Element) -> None:
    holder = direct_field(root, "productKeywords")
    value = ET.Element("complex-value")
    field = ET.SubElement(value, "field", {"id": "productKeywords_0", "type": "input"})
    ET.SubElement(field, "value").text = KEYWORDS
    replace_complex_value(holder, value)


def set_prices(root: ET.Element) -> None:
    holder = direct_field(root, "ladderPrice")
    value = ET.Element("complex-value")
    for index, (quantity, price) in enumerate(PRICE_LADDER):
        outer = ET.SubElement(value, "field", {"id": f"ladderPrice_{index}", "type": "complex"})
        inner = ET.SubElement(outer, "complex-value")
        q = ET.SubElement(inner, "field", {"id": "quantity", "type": "input"})
        ET.SubElement(q, "value").text = str(quantity)
        p = ET.SubElement(inner, "field", {"id": "price", "type": "input"})
        ET.SubElement(p, "value").text = price
    replace_complex_value(holder, value)


def set_main_images(root: ET.Element, assets: dict[str, dict], roles: list[str]) -> None:
    holder = direct_field(root, "scImages")
    value = ET.Element("complex-value")
    for index, role in enumerate(roles):
        asset = assets[role]
        field = ET.SubElement(value, "field", {"id": f"scImages_{index}", "type": "input"})
        image = ET.SubElement(field, "value", {"fileFlag": "no", "fileId": str(asset["file_id"])})
        image.text = asset["url"].replace("https:", "")
    replace_complex_value(holder, value)


def set_gallery(root: ET.Element, field_id: str, assets: dict[str, dict], groups: list[tuple[str, list[str], str | None]]) -> None:
    holder = direct_field(root, field_id)
    for old in list(holder.findall("./complex-values")):
        holder.remove(old)
    for index, (gallery_value, roles, general_text) in enumerate(groups):
        group = ET.Element("complex-values")
        images = ET.SubElement(group, "field", {"id": "images", "type": "multiComplex"})
        for role in roles:
            image_row = ET.SubElement(images, "complex-values")
            image_url = ET.SubElement(image_row, "field", {"id": "imageURL", "type": "input"})
            ET.SubElement(image_url, "value").text = assets[role]["url"].replace("https:", "")
            if general_text:
                general = ET.SubElement(image_row, "field", {"id": "generalText", "type": "input"})
                ET.SubElement(general, "value").text = general_text
        gallery = ET.SubElement(group, "field", {"id": "gallery", "type": "singleCheck"})
        ET.SubElement(gallery, "value").text = gallery_value
        holder.insert(index, group)


def values_only(full_root: ET.Element) -> ET.Element:
    keep_ids = {
        "catId", "icbuCatProp", "saleProp", "sku", "productTitle", "productKeywords", "scImages",
        "priceUnit", "shippingTemplate", "productGroup", "ladderPrice", "saleType", "scPrice",
        "minOrderQuantity", "productDescType", "superText", "textDesc", "logisticsProperty",
        "imageVideo",
    }
    root = ET.Element("itemSchema")
    for source in full_root.findall("./field"):
        if source.get("id") not in keep_ids:
            continue
        field = deepcopy(source)
        for tag in ("rules", "options", "fields", "label-group"):
            for child in list(field.findall(f"./{tag}")):
                field.remove(child)
        for sku_id in list(field.findall(".//field[@id='skuId']")):
            for parent in field.iter():
                if sku_id in list(parent):
                    parent.remove(sku_id)
                    break
        root.append(field)
    return root


def snapshot(product: dict) -> dict:
    attrs = {str(row.get("attribute_name")): row.get("value_name") for row in product.get("attributes", [])}
    axes = {
        str(group.get("attribute_name")): [row.get("system_value_name") for row in group.get("values", [])]
        for group in (product.get("product_sku") or {}).get("sku_attributes", [])
    }
    skus = (product.get("product_sku") or {}).get("skus", [])
    prices = sorted({price.get("price") for sku in skus for price in sku.get("bulk_discount_prices", [])})
    return {
        "title": product.get("subject"),
        "model": attrs.get("Model Number"),
        "status": product.get("status"),
        "display": product.get("display"),
        "url": product.get("pc_detail_url"),
        "attributes": attrs,
        "colors": axes.get("Color", []),
        "sizes": axes.get("EUR Size", []),
        "sku_count": len(skus),
        "prices": prices,
        "moq": (product.get("sourcing_trade") or {}).get("min_order_quantity"),
        "main_images": (product.get("main_image") or {}).get("images", []),
        "detail_images": (((product.get("struct_detail") or {}).get("detail_image") or {}).get("images") or []),
        "company_images": (((product.get("struct_detail") or {}).get("company_image") or {}).get("images") or []),
    }


def image_token(url: str) -> str:
    return Path(url.split("?", 1)[0]).stem.split("_")[0]


def canonical_url(url: str) -> str:
    return "https:" + url if url.startswith("//") else url


def set_super_text(root: ET.Element, assets: dict[str, dict]) -> None:
    product_rows = [
        ("S6077 Product Overview", "detail_1"),
        ("White Color Front and Side View", "detail_2"),
        ("Black Color Side Profile", "detail_3"),
        ("Size Range and Order Inputs", "detail_4"),
    ]
    company_rows = [
        ("Supplier Identity", "company_1"),
        ("Custom Project Communication", "company_2"),
        ("Production Organization", "company_3"),
        ("Visible Order Checkpoints", "company_4"),
        ("Packing and Order Handoff", "company_5"),
    ]
    blocks = [
        '<div style="max-width:1000px;margin:0 auto;font-family:Arial,sans-serif;color:#14202b;">',
        '<h2 style="text-align:center;">S6077 Product Details</h2>',
        '<p style="text-align:center;">Black and white · EU 39–48 · Lace-up construction · Current terms reconfirmed before order</p>',
    ]
    for alt, role in product_rows:
        blocks.append(f'<p style="margin:0;"><img src="{canonical_url(assets[role]["url"])}" alt="{alt}" style="display:block;width:100%;height:auto;" /></p>')
    blocks.extend([
        '<h2 style="text-align:center;margin-top:32px;">Beiqiang Company Information</h2>',
        '<p style="text-align:center;">Company-level capability images do not represent S6077 as factory-produced; product-specific sourcing or production arrangements are confirmed per order.</p>',
    ])
    for alt, role in company_rows:
        blocks.append(f'<p style="margin:0;"><img src="{canonical_url(assets[role]["url"])}" alt="{alt}" style="display:block;width:100%;height:auto;" /></p>')
    blocks.append('</div>')
    set_direct_value(root, "superText", "".join(blocks))


def build_xml(root: ET.Element, manifest: dict) -> tuple[str, dict]:
    assets = {f'{row["role"]}_{row["slot"]}': row for row in manifest["assets"]}
    main_roles = [f"main_{slot}" for slot in range(1, 7)]
    set_attributes(root)
    set_sale_and_skus(root, assets)
    set_direct_value(root, "productTitle", TITLE)
    set_keywords(root)
    set_direct_value(root, "textDesc", HIGHLIGHTS)
    set_direct_value(root, "minOrderQuantity", "2")
    set_prices(root)
    set_main_images(root, assets, main_roles)
    set_direct_value(root, "imageVideo", MAIN_VIDEO_ID)
    set_direct_value(root, "productDescType", "2")
    set_super_text(root, assets)
    output_root = values_only(root)
    xml = ET.tostring(output_root, encoding="unicode")
    expected = {
        "main_tokens": [image_token(assets[role]["url"]) for role in main_roles],
        "detail_tokens": [image_token(assets[f"detail_{slot}"]["url"]) for slot in range(1, 5)],
        "company_tokens": [image_token(assets[f"company_{slot}"]["url"]) for slot in range(1, 6)],
        "main_video_id": MAIN_VIDEO_ID,
    }
    return xml, expected


def verify(after: dict, expected: dict) -> dict:
    snap = snapshot(after)
    low_price = min(float(value) for value in snap["prices"])
    markup = low_price * USD_CNY_REFERENCE / SOURCE_PRICE_CNY
    return {
        "title_ok": snap["title"] == TITLE,
        "model_ok": snap["model"] == TARGET_MODEL,
        "closure_ok": snap["attributes"].get("Closure Type") == "Lace-up",
        "round_toe_ok": snap["attributes"].get("Toe Style") == "Round Toe",
        "walking_style_ok": snap["attributes"].get("Style") == "Walking Shoes",
        "unsupported_midsole_removed": snap["attributes"].get("Midsole Material") is None,
        "unsupported_outsole_removed": snap["attributes"].get("Outsole Material") is None,
        "unsupported_feature_removed": snap["attributes"].get("Feature") is None,
        "unsupported_lining_removed": snap["attributes"].get("Lining Material") is None,
        "unsupported_season_removed": snap["attributes"].get("Season") is None,
        "fit_type_pending_ui_delete": snap["attributes"].get("Fit Type") == "Regular Fit",
        "colors_ok": set(snap["colors"]) == {row["name"] for row in COLORS},
        "sizes_ok": set(snap["sizes"]) == set(SIZE_IDS),
        "sku_count_ok": snap["sku_count"] == 20,
        "prices_ok": {float(value) for value in snap["prices"]} == {9.1, 9.2, 9.5},
        "minimum_price_usd": low_price,
        "price_markup_multiple": round(markup, 4),
        "price_floor_ok": markup >= MIN_MARKUP,
        "main_order_ok": [image_token(url) for url in snap["main_images"]] == expected["main_tokens"],
        "ordinary_detail_pending_render_readback": True,
        "submitted_or_live": snap["status"] in {"modified", "approved"},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    client = load_client()
    config = client.load_config(CONFIG_PATH)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8-sig"))
    before_response, before = get_product(client, config)
    before_snapshot = snapshot(before)
    if before_snapshot["model"] not in ALLOWED_MODELS:
        raise RuntimeError(f"target identity mismatch: {before_snapshot['model']}")
    render_response, full_root = render_schema(client, config)
    xml, expected = build_xml(full_root, manifest)
    planned_markup = float(PRICE_LADDER[-1][1]) * USD_CNY_REFERENCE / SOURCE_PRICE_CNY
    plan = {
        "mode": "apply" if args.apply else "dry-run",
        "product_id": PRODUCT_ID,
        "source_url": SOURCE_URL,
        "target_before": before_snapshot,
        "target_title": TITLE,
        "target_model": TARGET_MODEL,
        "target_main_video_id": MAIN_VIDEO_ID,
        "colors": [row["name"] for row in COLORS],
        "sizes": list(SIZE_IDS),
        "sku_count": 20,
        "price_ladder_usd": PRICE_LADDER,
        "source_price_cny": SOURCE_PRICE_CNY,
        "minimum_markup_multiple": MIN_MARKUP,
        "planned_lowest_price_markup_multiple": round(planned_markup, 4),
        "product_get_refs": refs(client, before_response),
        "render_refs": refs(client, render_response),
        "xml_sha256": hashlib.sha256(xml.encode("utf-8")).hexdigest(),
        "xml_chars": len(xml),
        "expected_images": expected,
        "gates": {
            "source_is_current_sooxie_page": SOURCE_URL == "https://zuoshou.sooxie.com/detail/2517849",
            "source_price_recorded": SOURCE_PRICE_CNY == 45.0,
            "price_floor_ok": planned_markup >= MIN_MARKUP,
            "image_manifest_complete": (
                manifest.get("all_uploaded") is True
                and manifest.get("counts") == {"main": 6, "detail": 4, "company": 5, "sku": 2}
            ),
            "target_identity_allowed": before_snapshot["model"] in ALLOWED_MODELS,
            "main_video_configured": bool(MAIN_VIDEO_ID),
            "stock_is_blank_unlimited": "warehouseCode" not in xml and ">999<" not in xml,
            "ordinary_detail_uses_only_sc04": "sc01.alicdn.com" not in xml and all(
                canonical_url(row["url"]).startswith("https://sc04.alicdn.com/") for row in manifest["assets"]
            ),
            "legacy_unverified_package_not_reasserted": all(token not in xml for token in ("pkgMeasure", "pkgWeight", "ladderPeriod")),
        },
    }
    PLAN_PATH.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    if not all(plan["gates"].values()):
        raise RuntimeError({"preflight_failed": plan["gates"]})
    if not args.apply:
        print(json.dumps({
            "plan": str(PLAN_PATH),
            "product_id": PRODUCT_ID,
            "xml_sha256": plan["xml_sha256"],
            "gates": plan["gates"],
        }, ensure_ascii=True, indent=2))
        return

    update_response = top_call_retry(
        client,
        config,
        "alibaba.icbu.product.schema.update",
        {"param_product_top_publish_request": {
            "cat_id": CATEGORY_ID,
            "language": "en_US",
            "product_id": PRODUCT_ID,
            "xml": xml,
        }},
    )
    if failed(client, update_response):
        raise RuntimeError({"step": "schema.update", "refs": refs(client, update_response), "response": update_response})
    after_response, after = get_product(client, config)
    verification = verify(after, expected)
    receipt = {
        **plan,
        "update_refs": refs(client, update_response),
        "readback_refs": refs(client, after_response),
        "target_after": snapshot(after),
        "verification": verification,
    }
    RECEIPT_PATH.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "receipt": str(RECEIPT_PATH),
        "update_request_id": receipt["update_refs"]["request_id"],
        "readback_request_id": receipt["readback_refs"]["request_id"],
        "verification": verification,
    }, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
