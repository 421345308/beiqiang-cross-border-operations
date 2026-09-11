"""Read back and verify the eight HR A listings after Schema publication."""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import time
from pathlib import Path

ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG = Path.home() / ".config/beiqiang/alibaba-openapi.json"
OUTPUT_DIR = ROOT / "02_Alibaba运营/05_扩品工程/热榜8款API上架_2026-09-05"
PRODUCTS = {
    "HR001": "1601943321794", "HR002": "1601943305914", "HR003": "1601943312845", "HR004": "1601943397351",
    "HR005": "1601943335751", "HR006": "1601943439124", "HR007": "1601943463020", "HR008": "1601943348656",
}


def products_for_variant(variant: str) -> dict[str, str]:
    if variant == "A":
        return {f"{model}-A": product_id for model, product_id in PRODUCTS.items()}
    receipt = json.loads((OUTPUT_DIR / f"publish_{variant}_receipt.json").read_text(encoding="utf-8"))
    return {row["listing_id"]: str(row["submit"]["product_id"]) for row in receipt["products"]}


def load_client():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def call_retry(api, config, method, params, attempts=3):
    last = None
    for n in range(1, attempts + 1):
        try:
            return api.top_call(config, method, params)
        except Exception as exc:
            last = str(exc)
            time.sleep(n * 1.5)
    return {"local_error": last}


def norm(url):
    url = str(url or "")
    if url.startswith("//"):
        url = "https:" + url
    return re.sub(r"_\d+x\d+\.[^.]+$", "", url)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=["A", "B", "C"], default="A")
    args = parser.parse_args()
    api = load_client()
    config = api.load_config(CONFIG)
    rows = []
    for model, product_id in products_for_variant(args.variant).items():
        got = call_retry(api, config, "alibaba.icbu.product.get", {"product_id": int(product_id), "language": "ENGLISH"})
        product = got.get("product") or {}
        attrs = product.get("attributes") or []
        model_value = next((str(a.get("value_name")) for a in attrs if str(a.get("attribute_name")).lower() == "model number"), "")
        sku_attrs = (product.get("product_sku") or {}).get("sku_attributes") or []
        colors = next((a.get("values") or [] for a in sku_attrs if int(a.get("attribute_id") or 0) == 191288010), [])
        sizes = next((a.get("values") or [] for a in sku_attrs if int(a.get("attribute_id") or 0) == 222038415), [])
        detail = product.get("struct_detail") or {}
        mains = [norm(x) for x in (product.get("main_image") or {}).get("images", [])]
        details = [norm(x.get("image_url")) for x in (detail.get("detail_image") or {}).get("images", [])]
        companies = [norm(x.get("image_url")) for x in (detail.get("company_image") or {}).get("images", [])]
        trade = product.get("sourcing_trade") or {}
        checks = {
            "identity": model_value == model,
            "title_has_core_query": any(term in str(product.get("subject")) for term in (
                "Walking Shoes", "Walking Sneakers", "Casual Shoes", "Casual Sneakers", "Mule Shoes", "Dad Shoes"
            )),
            "main_images_6": len(mains) == 6,
            "colors_3": len(colors) == 3,
            "color_images_complete": len(colors) == 3 and all(norm(c.get("image_url")) for c in colors),
            "sizes_36_45": {str(v.get("system_value_name")) for v in sizes} == {str(i) for i in range(36, 46)},
            "detail_images_4": len(details) == 4,
            "company_images_5": len(companies) == 5,
            "no_main_detail_duplicate": not bool(set(mains) & set(details)),
            "highlight_is_b2b": "Factory-direct" in str(detail.get("product_summary")) and "OEM/ODM" in str(detail.get("product_summary")),
            "moq_2": str(trade.get("min_order_quantity")) in {"2", "2.0"},
            "lead_31_for_100": {"quantity": 100, "process_period": 31} in (trade.get("deliver_periods") or []),
        }
        score = call_retry(api, config, "alibaba.icbu.product.score.get", {"product_id": int(product_id)}, attempts=1)
        rows.append({
            "model": model, "product_id": product_id, "title": product.get("subject"), "display": product.get("display"),
            "status": product.get("status"), "url": product.get("pc_detail_url"), "checks": checks,
            "all_content_checks_pass": all(checks.values()),
            # The relation-list API is video-centric and cannot query by product
            # ID.  Video source upload/binding is tracked in the separate binding
            # manifest instead of reporting a false API error here.
            "video_binding_status": "pending_source_upload",
            "score": score,
            "readback_request_id": got.get("request_id"),
        })
        print(model, product.get("display"), product.get("status"), all(checks.values()), flush=True)
    payload = {
        "count": len(rows), "all_content_checks_pass": all(r["all_content_checks_pass"] for r in rows),
        "pending_review": [r["model"] for r in rows if r["display"] != "Y"], "products": rows,
    }
    OUT = OUTPUT_DIR / f"发布后API回读_{args.variant}.json"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
