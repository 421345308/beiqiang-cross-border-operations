"""Read-only OpenAPI verification for HR001-A after seller-UI submission.

Use ``--expect submitted`` immediately after the UI submit and
``--expect approved`` after Alibaba review.  The script never updates the
product.  It records every invariant needed before public-page QA.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
PROJECT = ROOT / r"02_Alibaba运营\05_扩品工程\HR系列真实货源改造_2026-09-21"
CLIENT = ROOT / r".agents\skills\alibaba-openapi-operator\scripts\alibaba_openapi.py"
MANIFEST = PROJECT / "HR001_9002_最终图片绑定清单.json"
PRODUCT_ID = 1601943321794
OUTPUT_CODE = "HR001-A"
TITLE = "Wholesale Men's Knit Slip-On Walking Shoes EVA Sole EU 38-47 Model 9002 for Importers"
MODEL = "HR001-A / 9002"
VIDEO_ID = "6000342456358"
SUBMISSION_RECEIPT = PROJECT / "HR001-A_详情与FitType_OpenAPI正式提交回执_2026-09-22.json"
COLORS = {"Light Gray / Beige Sole", "Dark Gray / Black Sole"}
SIZES = {str(value) for value in range(38, 48)}
PRICES = {10.90, 11.50, 11.90}


def load_client():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def refs(api, response):
    return {
        "request_id": response.get("request_id"),
        "trace_id": response.get("trace_id") or response.get("_trace_id_"),
        "error": api.api_error(response),
        "biz_success": response.get("biz_success"),
    }


def token(url: str) -> str:
    return Path(str(url or "").split("?", 1)[0]).stem.split("_")[0]


def snapshot(product: dict, schema_xml: str | None) -> dict:
    attrs = {str(row.get("attribute_name")): row.get("value_name") for row in product.get("attributes") or []}
    sku_block = product.get("product_sku") or {}
    axes = {
        str(group.get("attribute_name")): [str(row.get("system_value_name")) for row in group.get("values") or []]
        for group in sku_block.get("sku_attributes") or []
    }
    skus = sku_block.get("skus") or []
    prices = sorted({float(row.get("price")) for sku in skus for row in sku.get("bulk_discount_prices") or []})
    detail = (((product.get("struct_detail") or {}).get("detail_image") or {}).get("images") or [])
    company = (((product.get("struct_detail") or {}).get("company_image") or {}).get("images") or [])
    video = None
    if isinstance(schema_xml, str):
        root = ET.fromstring(schema_xml)
        video = root.find("./field[@id='imageVideo']/value")
    return {
        "status": product.get("status"),
        "display": product.get("display"),
        "url": product.get("pc_detail_url"),
        "title": product.get("subject"),
        "model": attrs.get("Model Number"),
        "fit_type": attrs.get("Fit Type"),
        "closure": attrs.get("Closure Type"),
        "outsole": attrs.get("Outsole Material"),
        "colors": axes.get("Color", []),
        "sizes": axes.get("EUR Size", []),
        "sku_count": len(skus),
        "prices": prices,
        "main_tokens": [token(url) for url in (product.get("main_image") or {}).get("images") or []],
        "detail_tokens": [token(row.get("image_url")) for row in detail],
        "company_count": len(company),
        "main_video_id": video.text if video is not None else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect", choices=("submitted", "approved"), required=True)
    args = parser.parse_args()

    api = load_client()
    config = api.load_config(Path.home() / ".config/beiqiang/alibaba-openapi.json")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    assets = {row["role"]: row for row in manifest["items"]}
    expected_main = [token(assets[role]["url"]) for role in manifest["role_order"]["main"]]
    expected_detail = {token(assets[role]["url"]) for role in manifest["role_order"]["detail"]}

    get_response = api.top_call(config, "alibaba.icbu.product.get", {"product_id": PRODUCT_ID, "language": "ENGLISH"})
    render_response = api.top_call(
        config,
        "alibaba.icbu.product.schema.render",
        {"param_product_top_publish_request": {"product_id": PRODUCT_ID, "language": "en_US"}},
    )
    if api.api_error(get_response) or api.api_error(render_response):
        raise RuntimeError({"get": refs(api, get_response), "render": refs(api, render_response)})
    product = get_response.get("product") or {}
    schema_xml = render_response.get("data")
    snap = snapshot(product, schema_xml)

    common_checks = {
        "title_ok": snap["title"] == TITLE,
        "model_ok": snap["model"] == MODEL,
        "closure_ok": snap["closure"] == "Slip-On",
        "outsole_ok": snap["outsole"] == "EVA",
        "colors_ok": set(snap["colors"]) == COLORS,
        "sizes_ok": set(snap["sizes"]) == SIZES,
        "sku_count_ok": snap["sku_count"] == 20,
        "prices_ok": set(snap["prices"]) == PRICES,
        "main_images_ok": snap["main_tokens"] == expected_main,
        "company_images_ok": snap["company_count"] == 5,
    }
    pending_checks = {}
    if args.expect == "submitted":
        submission = json.loads(SUBMISSION_RECEIPT.read_text(encoding="utf-8")) if SUBMISSION_RECEIPT.exists() else {}
        checks = {
            "expected_state_ok": snap["status"] == "modified" and snap["display"] == "N",
            **common_checks,
            "submission_receipt_ok": bool(submission.get("submitted_for_review"))
            and submission.get("expected_detail_tokens") == sorted(expected_detail),
        }
        pending_checks = {
            "fit_type_removed": "pending Alibaba review; product.get still exposes approved live version",
            "detail_images_ok": "pending Alibaba review; product.get still exposes approved live version",
            "main_video_ok": "schema.render may omit XML during review; unchanged field is verified after approval",
        }
    else:
        checks = {
            "expected_state_ok": snap["status"] == "approved" and snap["display"] == "Y",
            **common_checks,
            "fit_type_removed": snap["fit_type"] is None,
            "detail_images_ok": len(snap["detail_tokens"]) == 5 and set(snap["detail_tokens"]) == expected_detail,
            "main_video_ok": snap["main_video_id"] == VIDEO_ID,
        }
    receipt = {
        "mode": "read-only",
        "expect": args.expect,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "product_id": PRODUCT_ID,
        "snapshot": snap,
        "expected_detail_tokens": sorted(expected_detail),
        "checks": checks,
        "pending_checks": pending_checks,
        "all_checks_pass": all(checks.values()),
        "get_refs": refs(api, get_response),
        "render_refs": refs(api, render_response),
    }
    out = PROJECT / f"{OUTPUT_CODE}_后台提交后_{args.expect}_OpenAPI终验.json"
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(out), **receipt}, ensure_ascii=False, indent=2))
    if not receipt["all_checks_pass"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
