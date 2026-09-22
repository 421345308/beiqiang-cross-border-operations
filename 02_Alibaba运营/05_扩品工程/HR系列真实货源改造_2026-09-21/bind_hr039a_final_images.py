from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(r"C:\Users\spq\Desktop\贝强")
PROJECT = ROOT / r"02_Alibaba运营\05_扩品工程\HR系列真实货源改造_2026-09-21"
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
MANIFEST = PROJECT / "HR039-A_8025_最终图片绑定清单.json"
OUT = PROJECT / "HR039-A_8025_图片绑定_API回执.json"
PRODUCT_ID = 1601943650395
CAT_ID = 201334413

spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
api = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(api)
config = api.load_config(Path.home() / ".config/beiqiang/alibaba-openapi.json")

manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
items = {item["role"]: item for item in manifest["items"]}
main_roles = [
    "M1_8025_wholesale",
    "M2_8025_colors_sizes",
    "M3_8025_construction",
    "M4_8025_oem_inputs",
    "M5_factory_quality",
    "M6_packing_quote_inputs",
]
detail_groups = [
    ("350", "D1_product_overview", None),
    ("300", "D2_verified_specs", "Verified specifications for model 8025"),
    ("150", "D3_colors_sizes", None),
    ("350", "D4_price_quote", None),
    ("350", "D5_oem_project_inputs", None),
]
company_groups = [
    ("400", ["C1_real_factory_identity"]),
    (
        "550",
        [
            "C2_custom_project_flow",
            "C3_real_production_organization",
            "C4_real_quality_checkpoints",
        ],
    ),
    ("700", ["C5_packing_order_handoff"]),
]


def add_image(parent: ET.Element, role: str) -> None:
    image_row = ET.SubElement(parent, "complex-values")
    image_url = ET.SubElement(image_row, "field", {"id": "imageURL", "type": "input"})
    ET.SubElement(image_url, "value").text = items[role]["url"]


root = ET.Element("itemSchema")

sc_images = ET.SubElement(root, "field", {"id": "scImages", "name": "Product images", "type": "complex"})
sc_value = ET.SubElement(sc_images, "complex-value")
for index, role in enumerate(main_roles):
    field = ET.SubElement(sc_value, "field", {"id": f"scImages_{index}", "type": "input"})
    value = ET.SubElement(
        field,
        "value",
        {"fileFlag": "no", "fileId": items[role]["file_id"]},
    )
    value.text = items[role]["url"]

detail = ET.SubElement(root, "field", {"id": "detailImage", "name": "Details of the picture", "type": "multiComplex"})
for gallery_value, role, general_text in detail_groups:
    group = ET.SubElement(detail, "complex-values")
    images = ET.SubElement(group, "field", {"id": "images", "type": "multiComplex"})
    add_image(images, role)
    if general_text:
        images[0].append(ET.Element("field", {"id": "generalText", "type": "input"}))
        ET.SubElement(images[0][-1], "value").text = general_text
    gallery = ET.SubElement(group, "field", {"id": "gallery", "type": "singleCheck"})
    ET.SubElement(gallery, "value").text = gallery_value

company = ET.SubElement(root, "field", {"id": "companyImage", "name": "Company Picture", "type": "multiComplex"})
for gallery_value, roles in company_groups:
    group = ET.SubElement(company, "complex-values")
    images = ET.SubElement(group, "field", {"id": "images", "type": "multiComplex"})
    for role in roles:
        add_image(images, role)
    gallery = ET.SubElement(group, "field", {"id": "gallery", "type": "singleCheck"})
    ET.SubElement(gallery, "value").text = gallery_value

xml = ET.tostring(root, encoding="unicode")
update = api.top_call(
    config,
    "alibaba.icbu.product.schema.update",
    {
        "param_product_top_publish_request": {
            "cat_id": CAT_ID,
            "language": "en_US",
            "product_id": PRODUCT_ID,
            "xml": xml,
        }
    },
)
error = api.api_error(update)
if error or update.get("biz_success") is False or update.get("model") is False:
    raise RuntimeError({"error": error, "response": update})

render = api.top_call(
    config,
    "alibaba.icbu.product.schema.render",
    {"param_product_top_publish_request": {"product_id": PRODUCT_ID, "language": "en_US"}},
)
render_root = ET.fromstring(render["data"])


def rendered_urls(field_id: str) -> list[str]:
    node = render_root.find(f".//field[@id='{field_id}']")
    if node is None:
        return []
    return [value.text or "" for value in node.findall(".//field[@id='imageURL']/value")]


main_node = render_root.find(".//field[@id='scImages']")
main_urls = [] if main_node is None else [
    value.text or "" for value in main_node.findall("./complex-value/field/value")
]
detail_urls = rendered_urls("detailImage")
company_urls = rendered_urls("companyImage")


def token(url: str) -> str:
    return Path(url.split("?")[0]).stem.split("_")[0]


expected = {
    "main": [items[role]["url"] for role in main_roles],
    "detail": [items[role]["url"] for _, role, _ in detail_groups],
    "company": [items[role]["url"] for _, roles in company_groups for role in roles],
}
actual = {"main": main_urls, "detail": detail_urls, "company": company_urls}
verification = {}
for section in expected:
    expected_tokens = [token(url) for url in expected[section]]
    actual_tokens = [token(url) for url in actual[section]]
    verification[section] = {
        "expected_count": len(expected_tokens),
        "actual_count": len(actual_tokens),
        "expected_tokens": expected_tokens,
        "actual_tokens": actual_tokens,
        "ok": expected_tokens == actual_tokens,
    }

product_get = api.top_call(
    config,
    "alibaba.icbu.product.get",
    {"product_id": PRODUCT_ID, "language": "ENGLISH"},
)
product = product_get.get("product") or {}
receipt = {
    "product_id": PRODUCT_ID,
    "update_mode": "incremental_image_fields_only",
    "xml_chars": len(xml),
    "update_request_id": update.get("request_id"),
    "update_trace_id": update.get("trace_id") or update.get("_trace_id_"),
    "render_request_id": render.get("request_id"),
    "render_trace_id": render.get("trace_id") or render.get("_trace_id_"),
    "readback_request_id": product_get.get("request_id"),
    "readback_trace_id": product_get.get("trace_id") or product_get.get("_trace_id_"),
    "status": product.get("status"),
    "display": product.get("display"),
    "url": product.get("pc_detail_url"),
    "verification": verification,
    "verified": all(section["ok"] for section in verification.values()),
}
OUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(receipt, ensure_ascii=False, indent=2))
if not receipt["verified"]:
    raise RuntimeError("Image binding did not verify")
