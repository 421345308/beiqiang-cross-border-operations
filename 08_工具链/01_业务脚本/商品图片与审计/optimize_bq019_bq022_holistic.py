#!/usr/bin/env python3
"""Apply evidence-backed whole-page corrections to BQ019 and BQ022.

The update changes four linked conversion/search fields in one pass:
- product title
- product keywords
- M1 while preserving M2-M6
- product highlights / inquiry hook

All price, SKU, attribute, logistics, detail-image, company and FAQ data is
snapshotted before the change and must remain identical after readback.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import xml.etree.ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
SKILL_SCRIPTS = ROOT / ".agents/skills/alibaba-openapi-operator/scripts"
sys.path.insert(0, str(SKILL_SCRIPTS))

from alibaba_openapi import DEFAULT_CONFIG, api_error, load_config, top_call, upload_image  # noqa: E402
from batch_replace_hero import image_key, rebank_existing_image  # noqa: E402


OUTPUT = (
    ROOT
    / "02_Alibaba运营/01_店铺与全店诊断/第35周整页优化_2026-09-12"
    / "BQ019_BQ022整页优化API回执.json"
)

PLAN = [
    {
        "product_id": "10000044041008",
        "model": "BQ019/A206",
        "m1": ROOT / "01_产品资产/01_原始数据包/已整理_BQ019_A206_A206情侣鞋图片/A206情侣鞋图片/主图/19.jpg",
        "title": "Wholesale Knit Textile Lace Up Walking Shoes A206 Casual Shoes EU 35-45 OEM ODM",
        "keywords": "knit textile lace up walking shoes wholesale casual shoes OEM ODM",
        "summary": (
            "A206 knit-textile lace-up walking shoe for wholesale and OEM/ODM programs. "
            "EU 35-45 with confirmed Cream, Black, Light Grey and White options. "
            "Mixed colors and sizes can be discussed for trial orders. Send target quantity, "
            "size ratio, color mix, logo and packaging requirements for a style-specific quotation. "
            "Samples can be discussed before bulk production; fee, courier cost and timing are "
            "confirmed before payment."
        ),
    },
    {
        "product_id": "10000043991998",
        "model": "BQ022/A2208",
        "m1": ROOT / "01_产品资产/01_原始数据包/已整理_BQ022_A2208_补充_A2208/A2208/主图/15.jpg",
        "title": "Wholesale Striped Knit Textile Slip On Walking Shoes A2208 Casual Shoes EU 35-45 OEM ODM",
        "keywords": "striped knit slip on walking shoes wholesale casual shoes OEM ODM",
        "summary": (
            "A2208 striped knit-textile slip-on walking shoe for wholesale and OEM/ODM programs. "
            "EU 35-45 with confirmed Black White, Black White Stripe and Light Grey options. "
            "Mixed colors and sizes can be discussed for trial orders. Send target quantity, "
            "size ratio, color mix, logo and packaging requirements for a style-specific quotation. "
            "Samples can be discussed before bulk production; fee, courier cost and timing are "
            "confirmed before payment."
        ),
    },
]


def failed(response: dict) -> bool:
    return bool(api_error(response)) or response.get("biz_success") is False or response.get("model") is False


def refs(response: dict) -> dict:
    return {
        "request_id": response.get("request_id"),
        "trace_id": response.get("trace_id") or response.get("_trace_id_"),
        "message": response.get("message") or response.get("msg_info"),
        "error": api_error(response),
    }


def call_with_retry(fn, attempts: int = 5):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(1.5 * attempt)
    raise RuntimeError(str(last_error))


def get_product(config: dict, product_id: str) -> tuple[dict | None, dict]:
    response: dict = {}
    for attempt in range(1, 6):
        response = call_with_retry(
            lambda: top_call(config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
        )
        if not failed(response) and response.get("product"):
            return response["product"], response
        if attempt < 5:
            time.sleep(2 * attempt)
    return None, response


def protected_snapshot(product: dict) -> dict:
    detail = deepcopy(product.get("struct_detail") or {})
    detail.pop("product_summary", None)
    return {
        "category_id": deepcopy(product.get("category_id")),
        "language": deepcopy(product.get("language")),
        "product_type": deepcopy(product.get("product_type")),
        "attributes": deepcopy(product.get("attributes")),
        "product_sku": deepcopy(product.get("product_sku")),
        "sourcing_trade": deepcopy(product.get("sourcing_trade")),
        "struct_detail_without_summary": detail,
        "struct_detail_product": deepcopy(product.get("struct_detail_product")),
        "price_type": deepcopy(product.get("price_type")),
        "rts": deepcopy(product.get("rts")),
        "sub_market_type": deepcopy(product.get("sub_market_type")),
        "group": deepcopy(product.get("group")),
    }


def update_xml(urls: list[str], ids: list[str], title: str, keywords: str, summary: str) -> str:
    root = ET.Element("itemSchema")

    title_field = ET.SubElement(root, "field", {"id": "productTitle", "name": "Product name", "type": "input"})
    ET.SubElement(title_field, "value").text = title

    keyword_field = ET.SubElement(root, "field", {"id": "productKeywords", "type": "complex"})
    keyword_values = ET.SubElement(keyword_field, "complex-value")
    keyword_node = ET.SubElement(keyword_values, "field", {"id": "productKeywords_0", "type": "input"})
    ET.SubElement(keyword_node, "value").text = keywords

    image_field = ET.SubElement(root, "field", {"id": "scImages", "type": "complex"})
    image_values = ET.SubElement(image_field, "complex-value")
    for index, (url, file_id) in enumerate(zip(urls, ids)):
        node = ET.SubElement(image_values, "field", {"id": f"scImages_{index}", "type": "input"})
        value = ET.SubElement(node, "value", {"fileFlag": "no", "fileId": str(file_id)})
        value.text = url.replace("https:", "").replace("http:", "")

    summary_field = ET.SubElement(root, "field", {"id": "textDesc", "type": "input"})
    ET.SubElement(summary_field, "value").text = summary
    return ET.tostring(root, encoding="unicode", short_empty_elements=True)


def process_one(config: dict, row: dict) -> dict:
    product_id = row["product_id"]
    record = {"product_id": product_id, "model": row["model"], "ok": False}
    before, before_response = get_product(config, product_id)
    if before is None:
        record.update(stage="product_get_before", response=refs(before_response))
        return record

    old_urls = list((before.get("main_image") or {}).get("images") or [])
    if len(old_urls) != 6:
        record.update(stage="gallery_precheck", error=f"expected 6 images, got {len(old_urls)}")
        return record
    if not row["m1"].is_file():
        record.update(stage="local_image_precheck", error=f"missing {row['m1']}")
        return record

    preserved_urls: list[str] = []
    preserved_ids: list[str] = []
    rebanked: list[dict] = []
    # Rebank exact live M2-M6 pixels to obtain current seller-owned file IDs.
    for slot, url in enumerate(old_urls[1:], start=2):
        upload, source = call_with_retry(lambda url=url, slot=slot: rebank_existing_image(config, url, slot))
        if failed(upload) or not upload.get("upload_image_response"):
            record.update(stage="preserved_image_rebank", slot=slot, source=source, response=refs(upload))
            return record
        item = upload["upload_image_response"]
        preserved_urls.append(str(item["photobank_url"]))
        preserved_ids.append(str(item["file_id"]))
        rebanked.append({"slot": slot, "source": source, "url": str(item["photobank_url"]), "file_id": str(item["file_id"])})

    upload = call_with_retry(lambda: upload_image(config, row["m1"], None))
    if failed(upload) or not upload.get("upload_image_response"):
        record.update(stage="new_m1_upload", response=refs(upload))
        return record
    item = upload["upload_image_response"]
    new_url, new_id = str(item["photobank_url"]), str(item["file_id"])

    requested_urls = [new_url, *preserved_urls]
    requested_ids = [new_id, *preserved_ids]
    xml = update_xml(requested_urls, requested_ids, row["title"], row["keywords"], row["summary"])
    update = call_with_retry(
        lambda: top_call(
            config,
            "alibaba.icbu.product.schema.update",
            {
                "param_product_top_publish_request": {
                    "cat_id": int(before["category_id"]),
                    "language": "en_US",
                    "product_id": int(product_id),
                    "xml": xml,
                }
            },
        )
    )
    if failed(update):
        record.update(stage="schema_update", upload={"url": new_url, "file_id": new_id, **refs(upload)}, response=refs(update))
        return record

    after = None
    after_response: dict = {}
    for attempt in range(1, 7):
        after, after_response = get_product(config, product_id)
        if after is not None:
            after_urls = list((after.get("main_image") or {}).get("images") or [])
            after_summary = str(((after.get("struct_detail") or {}).get("product_summary") or ""))
            after_keywords = [str(x).strip() for x in (after.get("keywords") or []) if str(x).strip()]
            if (
                after.get("subject") == row["title"]
                and row["keywords"] in after_keywords
                and len(after_urls) == 6
                and image_key(after_urls[0]) == image_key(new_url)
                and after_summary == row["summary"]
            ):
                break
        if attempt < 6:
            time.sleep(2 * attempt)
    if after is None:
        record.update(stage="product_get_after", response=refs(after_response))
        return record

    after_urls = list((after.get("main_image") or {}).get("images") or [])
    after_keywords = [str(x).strip() for x in (after.get("keywords") or []) if str(x).strip()]
    checks = {
        "title_verified": after.get("subject") == row["title"],
        "keywords_verified": row["keywords"] in after_keywords,
        "m1_verified": len(after_urls) == 6 and image_key(after_urls[0]) == image_key(new_url),
        "m2_m6_preserved": len(after_urls) == 6 and [image_key(x) for x in after_urls[1:]] == [image_key(x) for x in preserved_urls],
        "summary_verified": str(((after.get("struct_detail") or {}).get("product_summary") or "")) == row["summary"],
        "protected_fields_unchanged": protected_snapshot(before) == protected_snapshot(after),
    }
    ok = all(checks.values())
    record.update(
        ok=ok,
        stage="verified" if ok else "readback_mismatch",
        requested_title=row["title"],
        requested_keywords=row["keywords"],
        before_title=before.get("subject"),
        after_title=after.get("subject"),
        before_keywords=before.get("keywords"),
        after_keywords=after.get("keywords"),
        before_status=before.get("status"),
        after_status=after.get("status"),
        before_display=before.get("display"),
        after_display=after.get("display"),
        old_m1=old_urls[0],
        new_m1=after_urls[0] if after_urls else None,
        source_m1=str(row["m1"]),
        preserved_reuploads=rebanked,
        checks=checks,
        upload={"url": new_url, "file_id": new_id, **refs(upload)},
        update=refs(update),
        readback=refs(after_response),
    )
    return record


def main() -> int:
    config = load_config(DEFAULT_CONFIG)
    started = datetime.now(timezone.utc).isoformat()
    results = []
    for row in PLAN:
        try:
            result = process_one(config, row)
        except Exception as exc:
            result = {"product_id": row["product_id"], "model": row["model"], "ok": False, "stage": "exception", "error": str(exc)}
        results.append(result)
        print(f"{result['product_id']} {result['stage']} ok={result['ok']}", flush=True)

    payload = {
        "started_at": started,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "method": "high-sales benchmark whole-page correction",
        "image_policy": "AI candidate rejected when geometry or texture fidelity is uncertain; verified real source image used",
        "success_count": sum(bool(x.get("ok")) for x in results),
        "failure_count": sum(not bool(x.get("ok")) for x in results),
        "results": results,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Receipt: {OUTPUT}", flush=True)
    return 0 if payload["failure_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
