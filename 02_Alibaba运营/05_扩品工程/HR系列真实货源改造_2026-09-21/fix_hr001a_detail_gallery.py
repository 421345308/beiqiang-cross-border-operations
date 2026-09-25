from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
PROJECT = ROOT / r"02_Alibaba运营\05_扩品工程\HR系列真实货源改造_2026-09-21"
CLIENT_PATH = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
MANIFEST_PATH = PROJECT / "HR001_9002_最终图片绑定清单.json"
OUTPUT = PROJECT / "HR001-A_9002_详情五图修复回执.json"
PRODUCT_ID = 1601943321794
CATEGORY_ID = 201334413

spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT_PATH)
api = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(api)
config = api.load_config(Path.home() / ".config/beiqiang/alibaba-openapi.json")
manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8-sig"))
assets = {row["role"]: row for row in manifest["items"]}


def call(method: str, params: dict) -> dict:
    response = {}
    for attempt in range(8):
        response = api.top_call(config, method, params)
        error = api.api_error(response)
        if not error:
            return response
        transient = error.get("code") == "ApiCallLimit" or error.get("type") == "ISP" or error.get("sub_code") == "000000"
        if not transient:
            return response
        time.sleep(min(2 + attempt * 2, 10))
    return response


root = ET.Element("itemSchema")
detail = ET.SubElement(root, "field", {"id": "detailImage", "name": "Details of the picture", "type": "multiComplex"})
groups = [
    ("300", ["D2_verified_specs"], "Verified facts for source model 9002"),
    ("350", ["D1_product_overview", "D3_colors_sizes", "D4_price_quote", "D5_oem_project_inputs"], None),
]
expected_tokens = []
for gallery_id, roles, general_text in groups:
    group = ET.SubElement(detail, "complex-values")
    images = ET.SubElement(group, "field", {"id": "images", "type": "multiComplex"})
    for role in roles:
        image = ET.SubElement(images, "complex-values")
        url = ET.SubElement(image, "field", {"id": "imageURL", "type": "input"})
        # detailImage has no fileId field. Use the public flat CDN path, not the
        # image-bank account directory URL returned by the upload endpoint.
        filename = Path(assets[role]["url"].split("?", 1)[0]).name
        expected_tokens.append(Path(filename).stem)
        ET.SubElement(url, "value").text = f"//sc04.alicdn.com/kf/{filename}"
        if general_text:
            general = ET.SubElement(image, "field", {"id": "generalText", "type": "input"})
            ET.SubElement(general, "value").text = general_text
    gallery = ET.SubElement(group, "field", {"id": "gallery", "type": "singleCheck"})
    ET.SubElement(gallery, "value").text = gallery_id

xml = ET.tostring(root, encoding="unicode")
update = call(
    "alibaba.icbu.product.schema.update",
    {"param_product_top_publish_request": {
        "cat_id": CATEGORY_ID,
        "language": "en_US",
        "product_id": PRODUCT_ID,
        "xml": xml,
    }},
)
error = api.api_error(update)
if error or update.get("biz_success") is False or update.get("model") is False:
    raise RuntimeError({"error": error, "response": update})

readback = call("alibaba.icbu.product.get", {"product_id": PRODUCT_ID, "language": "ENGLISH"})
product = readback.get("product") or {}
details = (((product.get("struct_detail") or {}).get("detail_image") or {}).get("images") or [])
actual_tokens = [Path(str(row.get("image_url") or "").split("?", 1)[0]).stem.split("_")[0] for row in details]
receipt = {
    "product_id": PRODUCT_ID,
    "update_request_id": update.get("request_id"),
    "update_trace_id": update.get("trace_id") or update.get("_trace_id_"),
    "readback_request_id": readback.get("request_id"),
    "readback_trace_id": readback.get("trace_id") or readback.get("_trace_id_"),
    "status": product.get("status"),
    "display": product.get("display"),
    "detail_count": len(details),
    "detail_urls": [row.get("image_url") for row in details],
    "expected_tokens": sorted(expected_tokens),
    "actual_tokens": sorted(actual_tokens),
    "verified": len(details) == 5 and set(actual_tokens) == set(expected_tokens),
}
OUTPUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(receipt, ensure_ascii=True, indent=2))
if not receipt["verified"]:
    raise RuntimeError(f"detail gallery did not verify: {OUTPUT}")
