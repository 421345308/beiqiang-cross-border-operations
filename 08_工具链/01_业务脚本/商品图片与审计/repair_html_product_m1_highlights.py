#!/usr/bin/env python3
"""Repair the one legacy HTML-detail product that blocks partial Schema updates."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
SCRIPTS = ROOT / "08_工具链/01_业务脚本/商品图片与审计"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / ".agents/skills/alibaba-openapi-operator/scripts"))

from alibaba_openapi import DEFAULT_CONFIG, load_config, top_call, upload_image  # noqa: E402
from apply_catalog_m1_and_highlights import call_with_retry, current_m1_matches_local, get_product, image_key, refs  # noqa: E402
from batch_replace_hero import load_bank_map, rebank_existing_image  # noqa: E402


PRODUCT_ID = "12000003229472"
PLAN = Path(r"E:\贝强大文件\01_产品资产\02_可发布素材\00_全店统一升级_2026-09-04\全店151款首图与产品亮点写入计划.json")
BANK_DIR = ROOT / "02_Alibaba运营/06_图片与检查记录/API全量图片审计_2026-09-03"
COMPANY_MAP = ROOT / "02_Alibaba运营/01_店铺与全店诊断/全量商品审查_2026-09-04/公司图v2/图片银行映射.json"
OUTPUT = ROOT / "02_Alibaba运营/01_店铺与全店诊断/全量商品审查_2026-09-04/HTML商品专项修复_12000003229472.json"


def append_gallery(root: ET.Element, field_id: str, rows: list[dict]) -> None:
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


def main() -> int:
    config = load_config(DEFAULT_CONFIG)
    plan = json.loads(PLAN.read_text(encoding="utf-8-sig"))
    row = next(item for item in plan["products"] if str(item["product_id"]) == PRODUCT_ID)
    before, before_response = get_product(config, PRODUCT_ID, attempts=8)
    if before is None:
        raise RuntimeError(json.dumps(before_response, ensure_ascii=False))
    old_images = list((before.get("main_image") or {}).get("images") or [])
    if len(old_images) != 6:
        raise RuntimeError(f"expected six main images, got {len(old_images)}")

    local_m1 = Path(row["output"])
    current_summary = str(((before.get("struct_detail") or {}).get("product_summary") or ""))
    if current_summary == row["new_summary"] and current_m1_matches_local(old_images[0], local_m1):
        result = {"product_id": PRODUCT_ID, "ok": True, "stage": "verified_existing", "readback": refs(before_response)}
        OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))
        return 0

    bank = load_bank_map(BANK_DIR)
    gallery_urls: list[str] = []
    gallery_ids: list[str] = []
    for index, url in enumerate(old_images[1:], 2):
        item = bank.get(image_key(url))
        if item is None:
            upload, _ = call_with_retry(lambda: rebank_existing_image(config, url, index))
            item = {"url": upload["upload_image_response"]["photobank_url"], "id": upload["upload_image_response"]["file_id"]}
        gallery_urls.append(str(item["url"]))
        gallery_ids.append(str(item["id"]))
    uploaded = call_with_retry(lambda: upload_image(config, local_m1, None))["upload_image_response"]
    all_urls = [str(uploaded["photobank_url"]), *gallery_urls]
    all_ids = [str(uploaded["file_id"]), *gallery_ids]

    html_urls = re.findall(r'<img\s+src="([^"]+)"', str(before.get("description") or ""), flags=re.I)
    product_urls = html_urls[:4]
    if len(product_urls) != 4:
        raise RuntimeError(f"expected at least four HTML product images, got {len(product_urls)}")
    detail_roles = [(350, "Other product images"), (350, "Other product images"), (300, "Detail shot"), (300, "Detail shot")]
    detail_rows = []
    for url, (role_id, role_name) in zip(product_urls, detail_roles):
        item = bank.get(image_key(url))
        if item is None:
            raise RuntimeError(f"HTML product image not found in current image bank: {url}")
        detail_rows.append({"url": str(item["url"]), "role_id": role_id, "role_name": role_name})
    company_rows = json.loads(COMPANY_MAP.read_text(encoding="utf-8-sig"))

    root = ET.Element("itemSchema")
    main = ET.SubElement(root, "field", {"id": "scImages", "type": "complex"})
    values = ET.SubElement(main, "complex-value")
    for index, (url, file_id) in enumerate(zip(all_urls, all_ids)):
        field = ET.SubElement(values, "field", {"id": f"scImages_{index}", "type": "input"})
        value = ET.SubElement(field, "value", {"fileId": file_id})
        value.text = url.replace("https:", "").replace("http:", "")
    text = ET.SubElement(root, "field", {"id": "textDesc", "type": "input"})
    ET.SubElement(text, "value").text = row["new_summary"]
    append_gallery(root, "detailImage", detail_rows)
    append_gallery(root, "companyImage", company_rows)

    update = call_with_retry(lambda: top_call(config, "alibaba.icbu.product.schema.update", {
        "param_product_top_publish_request": {
            "cat_id": int(before["category_id"]), "language": "en_US", "product_id": int(PRODUCT_ID),
            "xml": ET.tostring(root, encoding="unicode", short_empty_elements=True),
        }
    }))
    after, after_response = get_product(config, PRODUCT_ID, attempts=8)
    if after is None:
        raise RuntimeError(json.dumps(after_response, ensure_ascii=False))
    after_images = list((after.get("main_image") or {}).get("images") or [])
    struct = after.get("struct_detail") or {}
    detail_count = len(((struct.get("detail_image") or {}).get("images") or []))
    company_count = len(((struct.get("company_image") or {}).get("images") or []))
    ok = (
        len(after_images) == 6
        and image_key(after_images[0]) == image_key(str(uploaded["photobank_url"]))
        and str(struct.get("product_summary") or "") == row["new_summary"]
        and detail_count >= 4
        and company_count >= 5
    )
    result = {
        "product_id": PRODUCT_ID, "ok": ok, "stage": "verified" if ok else "readback_mismatch",
        "detail_count": detail_count, "company_count": company_count,
        "main_count": len(after_images), "m1_matches": image_key(after_images[0]) == image_key(str(uploaded["photobank_url"])) if after_images else False,
        "summary_matches": str(struct.get("product_summary") or "") == row["new_summary"],
        "update": refs(update), "readback": refs(after_response),
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
