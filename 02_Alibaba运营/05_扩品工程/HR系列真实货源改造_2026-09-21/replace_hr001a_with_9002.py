"""Replace HR001-A with verified Beiqiang source model 9002 via Alibaba OpenAPI.

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
MANIFEST_PATH = PROJECT / "HR001_9002_最终图片绑定清单.json"
PLAN_PATH = PROJECT / "HR001-A_9002_提交前预检.json"
RECEIPT_PATH = PROJECT / "HR001-A_替换为9002_API回执.json"

PRODUCT_ID = 1601943321794
CATEGORY_ID = 201334413
LINK_CODE = "HR001-A"
TARGET_MODEL = "HR001-A / 9002"
ALLOWED_MODELS = {"HR001", TARGET_MODEL}
MAIN_VIDEO_ID = "6000342456358"
TITLE = "Wholesale Men's Knit Slip-On Walking Shoes EVA Sole EU 38-47 Model 9002 for Importers"
KEYWORDS = "men knit slip on walking shoes wholesale big size casual shoes EVA sole model 9002 OEM footwear supplier"
HIGHLIGHTS = (
    "Verified Model 9002 uses a textile upper, slip-on no-lace structure and EVA sole. "
    "Source choices are Light Gray with Beige Sole and Dark Gray with Black Sole in EU sizes 38-47. "
    "Logo, color and packaging requests can be discussed after quantity and specification review. "
    "Freight is quoted separately. Source price, availability, size ratio, packing and lead time are rechecked before order."
)
SOURCE_PRICE_CNY = 55.0
USD_CNY_REFERENCE = 6.7487
MIN_MARKUP = 1.30
PRICE_LADDER = [(2, "11.90"), (50, "11.50"), (100, "10.90")]
SIZE_IDS = {
    "38": "28388",
    "39": "190000792",
    "40": "28389",
    "41": "28390",
    "42": "28391",
    "43": "28392",
    "44": "28393",
    "45": "28394",
    "46": "28395",
    "47": "28396",
}
COLORS = [
    {"name": "Light Gray / Beige Sole", "value_id": "-401", "image_role": "SKU_9002_light", "code": "LIGHT"},
    {"name": "Dark Gray / Black Sole", "value_id": "-402", "image_role": "SKU_9002_dark", "code": "DARK"},
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
    single("p-3", "Model Number", TARGET_MODEL, "-3")
    single("p-200000388", "Closure Type", "Slip-On", "13325270")
    multi("p-20700", "Midsole Material", [("EVA", "3376399")])
    multi("p-210200060", "Feature", [("Cushioning", "158583747")])
    multi("p-191288212", "Season", [("Autumn", "8168102")])
    multi("p-191290426", "Outsole Material", [("EVA", "3376399")])
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
            ET.SubElement(outer, "value").text = f"{LINK_CODE}-9002-{color['code']}-{size}"
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


def set_package(root: ET.Element) -> None:
    pkg = direct_field(root, "pkgMeasure").find("./complex-value")
    if pkg is None:
        raise RuntimeError("pkgMeasure complex value missing")
    values = {field.get("id"): field.find("./value") for field in pkg.findall("./field")}
    # Confirmed universal Alibaba single-pair packaging baseline. A SKU-specific
    # measured value may override this later, but an old listing must not.
    for key, value in {"length": "34", "width": "23", "height": "13"}.items():
        if values.get(key) is None:
            raise RuntimeError(f"pkgMeasure field missing: {key}")
        values[key].text = value
    set_direct_value(root, "pkgWeight", "0.5")


def request_clear_custom_properties(root: ET.Element) -> None:
    holder = direct_field(root, "customMoreProperty")
    for child in list(holder):
        if child.tag in {"complex-value", "complex-values", "values", "value"}:
            holder.remove(child)


def values_only(full_root: ET.Element) -> ET.Element:
    keep_ids = {
        "catId", "icbuCatProp", "saleProp", "sku", "productTitle", "productKeywords", "scImages",
        "pkgMeasure", "pkgWeight", "ladderPeriod", "priceUnit", "shippingTemplate", "productGroup",
        "ladderPrice", "customMoreProperty", "saleType", "scPrice", "minOrderQuantity", "productDescType",
        "detailImage", "textDesc", "companyImage", "companyDesc", "companyFaqDesc", "logisticsProperty",
        "imageVideo",
        "semiManagedPeriod",
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


def build_xml(root: ET.Element, manifest: dict) -> tuple[str, dict]:
    assets = {row["role"]: row for row in manifest["items"]}
    main_roles = manifest["role_order"]["main"]
    set_attributes(root)
    set_sale_and_skus(root, assets)
    set_direct_value(root, "productTitle", TITLE)
    set_keywords(root)
    set_direct_value(root, "textDesc", HIGHLIGHTS)
    set_direct_value(root, "minOrderQuantity", "2")
    set_prices(root)
    set_package(root)
    set_main_images(root, assets, main_roles)
    set_direct_value(root, "imageVideo", MAIN_VIDEO_ID)
    set_gallery(root, "detailImage", assets, [
        ("350", ["D1_product_overview"], None),
        ("300", ["D2_verified_specs"], "Verified facts for source model 9002"),
        ("150", ["D3_colors_sizes"], None),
        ("350", ["D4_price_quote"], None),
        ("350", ["D5_oem_project_inputs"], None),
    ])
    set_gallery(root, "companyImage", assets, [
        ("400", ["C1_real_factory_identity"], None),
        ("550", ["C2_custom_project_flow", "C3_real_production_organization", "C4_real_quality_checkpoints"], None),
        ("700", ["C5_packing_order_handoff"], None),
    ])
    request_clear_custom_properties(root)
    output_root = values_only(root)
    xml = ET.tostring(output_root, encoding="unicode")
    expected = {
        "main_tokens": [image_token(assets[role]["url"]) for role in main_roles],
        "detail_count": 5,
        "company_count": 5,
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
        "closure_ok": snap["attributes"].get("Closure Type") == "Slip-On",
        "outsole_ok": snap["attributes"].get("Outsole Material") == "EVA",
        "season_ok": snap["attributes"].get("Season") == "Autumn",
        "old_laceup_removed": snap["attributes"].get("Closure Type") != "Lace-up",
        "old_rubber_removed": snap["attributes"].get("Outsole Material") != "Rubber",
        "fit_type_cleared": snap["attributes"].get("Fit Type") is None,
        "colors_ok": set(snap["colors"]) == {row["name"] for row in COLORS},
        "sizes_ok": set(snap["sizes"]) == set(SIZE_IDS),
        "sku_count_ok": snap["sku_count"] == 20,
        "prices_ok": {float(value) for value in snap["prices"]} == {10.9, 11.5, 11.9},
        "minimum_price_usd": low_price,
        "price_markup_multiple": round(markup, 4),
        "price_floor_ok": markup >= MIN_MARKUP,
        "main_order_ok": [image_token(url) for url in snap["main_images"]] == expected["main_tokens"],
        "detail_count_ok": len(snap["detail_images"]) == expected["detail_count"],
        "company_count_ok": len(snap["company_images"]) == expected["company_count"],
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
        "source_url": manifest["source_url"],
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
            "source_is_current_beiqiang_store_page": manifest["source_url"] == "https://bqgcd.sooxie.com/detail/2536154",
            "source_price_recorded": manifest["source_price_cny"] == SOURCE_PRICE_CNY,
            "price_floor_ok": planned_markup >= MIN_MARKUP,
            "image_manifest_complete": len(manifest["role_order"]["main"]) == 6 and len(manifest["role_order"]["detail"]) == 5,
            "target_identity_allowed": before_snapshot["model"] in ALLOWED_MODELS,
            "main_video_configured": bool(MAIN_VIDEO_ID),
            "stock_is_blank_unlimited": "warehouseCode" not in xml and ">999<" not in xml,
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
