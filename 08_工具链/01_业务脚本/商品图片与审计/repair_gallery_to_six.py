#!/usr/bin/env python3
"""Restore one Alibaba gallery to six verified images without changing other fields.

The plan JSON contains product_id, expected_model, expected_title and
expected_images (exactly six Alibaba image-bank URLs in the required order).
Protected source product IDs are always refused.  Default mode is dry-run;
``--apply`` performs the Schema update and strict readback.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT_DIR = ROOT / ".agents/skills/alibaba-openapi-operator/scripts"
DEFAULT_AUDIT_DIR = ROOT / "02_Alibaba运营/06_图片与检查记录/API全量图片审计_2026-09-03"
sys.path.insert(0, str(CLIENT_DIR))

from alibaba_openapi import DEFAULT_CONFIG, api_error, load_config, top_call  # noqa: E402
from batch_replace_hero import (  # noqa: E402
    failed,
    image_key,
    load_bank_map,
    rebank_existing_image,
    response_refs,
    scimages_xml,
)


PROTECTED_PRODUCT_IDS = {
    "1601825074604", "1601825021825", "1601815020244", "1601814931739",
    "10000044041008", "10000043991998",
    "1601839073314", "1601838963947", "10000042821848",
    "10000044004948", "10000044024484", "10000044041031",
    "10000043744505", "10000044028277", "10000044007878", "10000046439033",
    "10000043732626",
    "1601839105416", "1601825070472", "10000043201799", "1601825160204", "1601839062659", "1601839050756", "10000046653813", "10000044011929", "10000044021584", "10000044034049", "10000042896165", "10000043200726", "10000043725883",
}


def model_number(product: dict) -> str:
    return next(
        (str(row.get("value_name") or "") for row in product.get("attributes") or []
         if row.get("attribute_name") == "Model Number"),
        "",
    )


def stable_snapshot(product: dict) -> dict:
    excluded = {"subject", "main_image", "gmt_modified", "status", "display", "pc_detail_url"}
    return {key: deepcopy(value) for key, value in product.items() if key not in excluded}


def title_and_images_xml(title: str, urls: list[str], ids: list[str]) -> str:
    root = ET.fromstring(scimages_xml(urls, ids))
    field = ET.Element("field", {"id": "subject", "type": "input"})
    ET.SubElement(field, "value").text = title
    root.insert(0, field)
    return ET.tostring(root, encoding="unicode")


def normalize_url(url: str) -> str:
    return "https:" + url if url.startswith("//") else url


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT_DIR)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8-sig"))
    product_id = str(plan["product_id"])
    urls = [normalize_url(str(url)) for url in plan["expected_images"]]
    title = str(plan["expected_title"])
    if product_id in PROTECTED_PRODUCT_IDS:
        raise RuntimeError("Protected source product refused")
    if len(urls) != 6 or len({image_key(url) for url in urls}) != 6:
        raise RuntimeError("expected_images must contain six unique Alibaba image-bank images")

    config = load_config(args.config)
    before_response = top_call(config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
    before = (before_response.get("product_get_response") or {}).get("product") or before_response.get("product") or {}
    if not before or api_error(before_response):
        raise RuntimeError(f"product.get failed: {response_refs(before_response)}")
    if model_number(before) != str(plan["expected_model"]):
        raise RuntimeError(f"Identity mismatch: {model_number(before)!r}")
    if str(before.get("subject")) != title:
        raise RuntimeError("Current title differs from expected_title; refusing repair")

    before_snapshot = stable_snapshot(before)
    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "product_id": product_id,
        "expected_model": plan["expected_model"],
        "mode": "apply" if args.apply else "dry-run",
        "before": {
            "status": before.get("status"), "display": before.get("display"),
            "title": before.get("subject"),
            "images": (before.get("main_image") or {}).get("images") or [],
            **response_refs(before_response),
        },
        "expected_images": urls,
    }
    if not args.apply:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0

    if before.get("status") != "approved" or before.get("display") != "Y":
        raise RuntimeError("Product is not approved/Y; do not resubmit during review")

    bank = load_bank_map(args.audit_dir)
    image_ids: list[str] = []
    rebanked: list[dict] = []
    for slot, url in enumerate(urls, 1):
        item = bank.get(image_key(url))
        bank_id = (item or {}).get("file_id") or (item or {}).get("id")
        if bank_id:
            image_ids.append(str(bank_id))
            continue
        upload_response, source = rebank_existing_image(config, url, slot)
        uploaded = upload_response.get("upload_image_response") or {}
        if failed(upload_response) or not uploaded.get("file_id"):
            raise RuntimeError(f"Could not re-bank M{slot}: {response_refs(upload_response)}")
        urls[slot - 1] = normalize_url(str(uploaded["photobank_url"]))
        image_ids.append(str(uploaded["file_id"]))
        rebanked.append({"slot": slot, "source": source, "url": urls[slot - 1], "file_id": image_ids[-1], **response_refs(upload_response)})

    update_response = top_call(config, "alibaba.icbu.product.schema.update", {
        "param_product_top_publish_request": {
            "cat_id": int(before["category_id"]), "language": "en_US",
            "product_id": int(product_id), "xml": title_and_images_xml(title, urls, image_ids),
        }
    })
    if failed(update_response):
        raise RuntimeError(f"schema.update failed: {response_refs(update_response)}")

    after_response = top_call(config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
    after = (after_response.get("product_get_response") or {}).get("product") or after_response.get("product") or {}
    returned = [normalize_url(str(url)) for url in (after.get("main_image") or {}).get("images") or []]
    checks = {
        "identity_ok": model_number(after) == str(plan["expected_model"]),
        "title_unchanged": str(after.get("subject")) == title,
        "six_images_exact": [image_key(url) for url in returned] == [image_key(url) for url in urls],
        "other_fields_unchanged": stable_snapshot(after) == before_snapshot,
    }
    record.update({
        "expected_images": urls, "file_ids": image_ids, "rebanked": rebanked,
        "update": response_refs(update_response), "readback": response_refs(after_response),
        "after": {"status": after.get("status"), "display": after.get("display"), "title": after.get("subject"), "images": returned},
        "checks": checks, "ok": all(checks.values()),
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "ok": record["ok"], "checks": checks}, ensure_ascii=False))
    return 0 if record["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
