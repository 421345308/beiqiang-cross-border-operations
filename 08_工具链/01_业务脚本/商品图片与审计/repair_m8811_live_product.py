from __future__ import annotations

import importlib.util
import json
import re
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT_PATH = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG_PATH = Path.home() / ".config/beiqiang/alibaba-openapi.json"
PRODUCT_ID = 1601939735063
MODEL = "BQ006-O1 / M8811"
ASSET_ROOT = Path(r"E:\贝强大文件\01_产品资产\02_可发布素材\00_最终上传\BQ006_M8811\04_修复_2026-09-04")
RECEIPT = ROOT / "02_Alibaba运营/02_单品优化记录/BQ006_M8811_颜色与详情修复回执_2026-09-04.json"

COLOR_FILES = {
    "White Pink": ASSET_ROOT / "03_sku_colors/white_pink.jpg",
    "White Purple": ASSET_ROOT / "03_sku_colors/white_purple.jpg",
    "White Grey": ASSET_ROOT / "03_sku_colors/white_grey.jpg",
    "All Black": ASSET_ROOT / "03_sku_colors/all_black.jpg",
    "Black White": ASSET_ROOT / "03_sku_colors/black_white.jpg",
    "White Green": ASSET_ROOT / "03_sku_colors/white_green.jpg",
    "All White": ASSET_ROOT / "03_sku_colors/all_white.jpg",
}
DETAIL_FILES = [
    (ASSET_ROOT / "01_product_detail/01_overview.jpg", 350, "Other product images"),
    (ASSET_ROOT / "01_product_detail/02_structure.jpg", 300, "Detail shot"),
    (ASSET_ROOT / "01_product_detail/03_size_colors.jpg", 150, "Product dimensions"),
    (ASSET_ROOT / "01_product_detail/04_order_support.jpg", 350, "Other product images"),
]
COMPANY_FILES = [
    (ASSET_ROOT / "02_company_detail/01_factory.jpg", 400, "Company overview"),
    (ASSET_ROOT / "02_company_detail/02_customization.jpg", 550, "Customization capabilities"),
    (ASSET_ROOT / "02_company_detail/03_production.jpg", 600, "Production workflow"),
    (ASSET_ROOT / "02_company_detail/04_quality.jpg", 500, "Factory profile"),
    (ASSET_ROOT / "02_company_detail/05_packing.jpg", 700, "Packaging & shipping specifications"),
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


def get_product(client, config):
    response = client.top_call(config, "alibaba.icbu.product.get", {"product_id": PRODUCT_ID, "language": "ENGLISH"})
    if failed(client, response) or not response.get("product"):
        raise RuntimeError(f"product.get failed: {response}")
    return response, response["product"]


def render_schema(client, config):
    response = client.top_call(config, "alibaba.icbu.product.schema.render", {
        "param_product_top_publish_request": {"product_id": PRODUCT_ID, "language": "en_US"}
    })
    xml_text = response.get("data")
    if not isinstance(xml_text, str):
        raise RuntimeError(f"schema.render failed: {response}")
    return response, ET.fromstring(xml_text)


def stable_snapshot(product: dict) -> dict:
    keys = ["subject", "category_id", "language", "product_type", "keywords", "attributes", "sourcing_trade", "main_image", "price_type", "rts", "group_id"]
    sku = deepcopy(product.get("product_sku") or {})
    for group in sku.get("sku_attributes", []):
        for value in group.get("values", []):
            value.pop("image_url", None)
    return {**{key: deepcopy(product.get(key)) for key in keys}, "product_sku_without_images": sku}


def upload(client, config, path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError(f"Missing asset: {path}")
    response = client.upload_image(config, path, None)
    item = response.get("upload_image_response") or {}
    if failed(client, response) or not item.get("photobank_url"):
        raise RuntimeError(f"Upload failed for {path}: {response}")
    return {"source": str(path), "url": str(item["photobank_url"]), "file_id": str(item["file_id"]), **refs(client, response)}


def append_gallery(root, field_id: str, rows: list[dict]):
    group = ET.SubElement(root, "field", {"id": field_id, "type": "multiComplex"})
    for row in rows:
        item = ET.SubElement(group, "complex-values")
        images = ET.SubElement(item, "field", {"id": "images", "type": "multiComplex"})
        image_item = ET.SubElement(images, "complex-values")
        image_url = ET.SubElement(image_item, "field", {"id": "imageURL", "type": "input"})
        ET.SubElement(image_url, "value").text = row["url"].replace("https:", "").replace("http:", "")
        gallery = ET.SubElement(item, "field", {"id": "gallery", "type": "singleCheck"})
        value = ET.SubElement(gallery, "value", {"displayName": row["role_name"]})
        value.text = str(row["role_id"])


def build_xml(schema_root: ET.Element, color_urls: dict[str, str], details: list[dict], companies: list[dict]) -> str:
    root = ET.Element("itemSchema")
    current = schema_root.find(".//field[@id='p-191288010']")
    if current is None:
        raise RuntimeError("Schema color field p-191288010 was not found")
    sale_prop = ET.SubElement(root, "field", {"id": "saleProp", "type": "complex"})
    complex_value = ET.SubElement(sale_prop, "complex-value")
    color_field = ET.SubElement(complex_value, "field", {"id": "p-191288010", "type": "multiCheck"})
    values = ET.SubElement(color_field, "values")
    seen = set()
    for old_value in current.findall("./values/value"):
        attrs = dict(old_value.attrib)
        color_name = attrs.get("inputValue", "")
        if color_name not in color_urls:
            raise RuntimeError(f"No approved image for live color: {color_name}")
        attrs["img"] = color_urls[color_name]
        value = ET.SubElement(values, "value", attrs)
        value.text = old_value.text
        seen.add(color_name)
    if seen != set(color_urls):
        raise RuntimeError(f"Color mismatch: live={seen}, prepared={set(color_urls)}")
    append_gallery(root, "detailImage", details)
    append_gallery(root, "companyImage", companies)
    return ET.tostring(root, encoding="unicode")


def gallery_keys(product: dict, key: str) -> list[str]:
    rows = (((product.get("struct_detail") or {}).get(key) or {}).get("images") or [])
    return [image_key(str(row.get("image_url", ""))) for row in rows]


def color_keys(product: dict) -> dict[str, str]:
    for group in (product.get("product_sku") or {}).get("sku_attributes", []):
        if int(group.get("attribute_id", 0)) == 191288010:
            return {str(v.get("system_value_name")): image_key(str(v.get("image_url", ""))) for v in group.get("values", [])}
    return {}


def main():
    client = load_client()
    config = client.load_config(CONFIG_PATH)
    before_response, before = get_product(client, config)
    if MODEL not in str(before.get("attributes", "")):
        raise RuntimeError(f"Product identity check failed: expected {MODEL}")
    snapshot = stable_snapshot(before)
    render_response, schema = render_schema(client, config)

    colors = {name: upload(client, config, path) for name, path in COLOR_FILES.items()}
    details = []
    for path, role_id, role_name in DETAIL_FILES:
        details.append({**upload(client, config, path), "role_id": role_id, "role_name": role_name})
    companies = []
    for path, role_id, role_name in COMPANY_FILES:
        companies.append({**upload(client, config, path), "role_id": role_id, "role_name": role_name})

    xml = build_xml(schema, {name: row["url"] for name, row in colors.items()}, details, companies)
    update_response = client.top_call(config, "alibaba.icbu.product.schema.update", {
        "param_product_top_publish_request": {
            "cat_id": int(before["category_id"]), "language": "en_US", "product_id": PRODUCT_ID, "xml": xml
        }
    })
    if failed(client, update_response):
        raise RuntimeError(f"schema.update failed: {update_response}")

    after_response, after = get_product(client, config)
    expected_colors = {name: image_key(row["url"]) for name, row in colors.items()}
    expected_details = [image_key(row["url"]) for row in details]
    expected_companies = [image_key(row["url"]) for row in companies]
    actual_colors = color_keys(after)
    actual_details = gallery_keys(after, "detail_image")
    actual_companies = gallery_keys(after, "company_image")
    verification = {
        "identity_ok": MODEL in str(after.get("attributes", "")),
        "colors_ok": actual_colors == expected_colors,
        # Alibaba may reorder structured gallery rows by role id on readback.
        # Validate the exact image membership here; role correctness is fixed by
        # the render schema and must be checked separately in the rendered XML.
        "details_ok": sorted(actual_details) == sorted(expected_details),
        "companies_ok": sorted(actual_companies) == sorted(expected_companies),
        "other_fields_preserved": stable_snapshot(after) == snapshot,
        "main_detail_overlap": bool(set(image_key(u) for u in (after.get("main_image") or {}).get("images", [])) & set(actual_details)),
    }
    receipt = {
        "product_id": PRODUCT_ID,
        "model": MODEL,
        "before": refs(client, before_response),
        "render": refs(client, render_response),
        "colors": colors,
        "details": details,
        "companies": companies,
        "update": refs(client, update_response),
        "readback": refs(client, after_response),
        "verification": verification,
        "actual_colors": actual_colors,
        "actual_details": actual_details,
        "actual_companies": actual_companies,
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if not all([verification["identity_ok"], verification["colors_ok"], verification["details_ok"], verification["companies_ok"], verification["other_fields_preserved"]]) or verification["main_detail_overlap"]:
        raise RuntimeError(f"Readback verification failed: {verification}")


if __name__ == "__main__":
    main()
