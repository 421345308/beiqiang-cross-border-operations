"""Repair only the productKeywords field after the whole-page update."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import time
import xml.etree.ElementTree as ET

ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
OUT = ROOT / "02_Alibaba运营/01_店铺与全店诊断/第35周整页优化_2026-09-12/BQ019_BQ022关键词修复回执.json"
ROWS = {
    10000044041008: "knit lace up walking shoes\nwholesale casual textile shoes\nOEM ODM walking sneakers",
    10000043991998: "striped knit slip on walking shoes\nwholesale casual textile shoes\nOEM ODM slip on sneakers",
}

spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
api = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(api)


def snapshot(product: dict) -> dict:
    return {key: deepcopy(product.get(key)) for key in (
        "subject", "category_id", "attributes", "product_sku", "sourcing_trade",
        "struct_detail", "struct_detail_product", "price_type", "rts",
        "sub_market_type", "group", "main_image",
    )}


def keyword_xml(value: str) -> str:
    root = ET.Element("itemSchema")
    field = ET.SubElement(root, "field", {"id": "productKeywords", "name": "Product keywords ", "type": "complex"})
    cv = ET.SubElement(field, "complex-value")
    node = ET.SubElement(cv, "field", {"id": "productKeywords_0", "name": "Product keywords ", "type": "input"})
    ET.SubElement(node, "value").text = value
    return ET.tostring(root, encoding="unicode")


def normalized(value) -> str:
    if isinstance(value, list):
        value = "\n".join(str(x) for x in value)
    return " ".join(str(value or "").split()).lower()


def refs(response: dict) -> dict:
    return {
        "request_id": response.get("request_id"),
        "trace_id": response.get("trace_id") or response.get("_trace_id_"),
        "message": response.get("message") or response.get("msg_info"),
        "error": api.api_error(response),
    }


def main() -> int:
    config = api.load_config(api.DEFAULT_CONFIG)
    results = []
    for product_id, keywords in ROWS.items():
        before_response = {}
        before = {}
        for attempt in range(1, 6):
            before_response = api.top_call(config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
            before = before_response.get("product") or {}
            if before.get("category_id"):
                break
            if attempt < 5:
                time.sleep(2 * attempt)
        if not before.get("category_id"):
            results.append({"product_id": str(product_id), "ok": False, "stage": "product_get_before", "response": refs(before_response)})
            continue
        protected = snapshot(before)
        update = api.top_call(config, "alibaba.icbu.product.schema.update", {
            "param_product_top_publish_request": {
                "cat_id": int(before["category_id"]), "language": "en_US",
                "product_id": product_id, "xml": keyword_xml(keywords),
            }
        })
        after = {}
        after_response = {}
        for attempt in range(1, 7):
            after_response = api.top_call(config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
            after = after_response.get("product") or {}
            if normalized(after.get("keywords")) == normalized(keywords):
                break
            if attempt < 6:
                time.sleep(2 * attempt)
        checks = {
            "keywords_verified": normalized(after.get("keywords")) == normalized(keywords),
            "other_fields_unchanged": snapshot(after) == protected,
        }
        results.append({
            "product_id": str(product_id), "requested_keywords": keywords,
            "before_keywords": before.get("keywords"), "after_keywords": after.get("keywords"),
            "status": after.get("status"), "display": after.get("display"),
            "checks": checks, "ok": all(checks.values()),
            "update": refs(update), "readback": refs(after_response),
        })
        print(f"{product_id} keywords={checks['keywords_verified']} protected={checks['other_fields_unchanged']}", flush=True)
    payload = {
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
        "success_count": sum(bool(x["ok"]) for x in results),
        "failure_count": sum(not bool(x["ok"]) for x in results),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Receipt: {OUT}")
    return 0 if payload["failure_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
