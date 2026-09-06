"""Inventory, quality-score and content readback for HR continuation receipts."""
from __future__ import annotations

import argparse
import importlib.util
import json
import time
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG = Path.home() / ".config/beiqiang/alibaba-openapi.json"
DEFAULT_DIR = ROOT / "02_Alibaba运营/05_扩品工程/热榜持续扩品_2026-09-05"
TARGET_INVENTORY = 999


def load_client():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def call(api, config, method, params, attempts=6):
    last = None
    for attempt in range(1, attempts + 1):
        try:
            last = api.top_call(config, method, params)
        except Exception as exc:
            last = {"local_error": str(exc)}
        error = last.get("error_response") or {}
        transient = bool(last.get("local_error")) or str(error.get("code") or "") in {"ApiCallLimit", "15"}
        if not error and not transient:
            return last
        if not transient:
            return last
        time.sleep(2.0 * attempt)
    return last


def inventory_rows(response):
    value = (response.get("result") or {}).get("data_list") or []
    if isinstance(value, dict):
        value = value.get("data") or []
    return value if isinstance(value, list) else [value]


def canonical(url):
    url = str(url or "")
    if url.startswith("//"):
        url = "https:" + url
    return url.split("_350x350", 1)[0]


def key(url):
    return Path(urlparse(canonical(url)).path).name.rsplit(".", 1)[0]


def receipt_products(folder: Path):
    result = []
    seen = set()
    for variant in "ABC":
        paths = sorted(folder.glob(f"publish_{variant}_*_receipt.json"))
        legacy = folder / ("publish_receipt.json" if variant == "A" else f"publish_{variant}_receipt.json")
        if legacy.is_file():
            paths.append(legacy)
        for path in paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            for row in payload.get("products", []):
                product_id = ((row.get("submit") or {}).get("product_id"))
                marker = (row.get("listing_id"), str(product_id))
                if product_id and marker not in seen:
                    seen.add(marker)
                    result.append((row["listing_id"], int(product_id)))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", default=str(DEFAULT_DIR))
    parser.add_argument("--sync-inventory", action="store_true")
    parser.add_argument("--touch-inventory", action="store_true", help="Touch one already-correct SKU down/up to refresh Alibaba's stale inventory score cache")
    parser.add_argument("--only", action="append", help="Check only listing IDs or model prefixes, for example HR011")
    parser.add_argument("--product", action="append", help="Add an exact listing/product pair, for example HR001-A:1601943321794")
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--output", help="Optional report filename inside the receipt folder")
    args = parser.parse_args()
    folder = Path(args.folder)
    api = load_client()
    config = api.load_config(CONFIG)
    report = {"products": []}

    selected = receipt_products(folder)
    if args.product:
        known = set(selected)
        for value in args.product:
            listing_id, product_id = value.rsplit(":", 1)
            pair = (listing_id, int(product_id))
            if pair not in known:
                selected.append(pair)
                known.add(pair)
    if args.only:
        wanted = tuple(args.only)
        selected = [(listing_id, product_id) for listing_id, product_id in selected if listing_id.startswith(wanted)]

    for listing_id, product_id in selected:
        inv_before_response = call(api, config, "alibaba.icbu.product.sku.inventory.get", {"product_id": product_id, "language": "en_US"})
        inv_before = inventory_rows(inv_before_response)
        update_response = None
        if args.sync_inventory and len(inv_before) == 30:
            changes = []
            for item in inv_before:
                current = int(item.get("inventory") or 0)
                delta = TARGET_INVENTORY - current
                if delta:
                    changes.append({
                        "sku_id": int(item["sku_id"]),
                        "inventory_code": item.get("inventory_code") or "CN_LOCAL_01",
                        "inventory": abs(delta),
                        "operate": "plus" if delta > 0 else "sub",
                    })
            if changes:
                update_response = call(api, config, "alibaba.icbu.product.inventory.update", {
                    "request_param": json.dumps({"product_id": product_id, "inventory_list": changes}, ensure_ascii=False, separators=(",", ":")),
                })
            elif args.touch_inventory:
                item = inv_before[0]
                base = {
                    "sku_id": int(item["sku_id"]),
                    "inventory_code": item.get("inventory_code") or "CN_LOCAL_01",
                    "inventory": 1,
                }
                down = call(api, config, "alibaba.icbu.product.inventory.update", {
                    "request_param": json.dumps({"product_id": product_id, "inventory_list": [{**base, "operate": "sub"}]}, ensure_ascii=False, separators=(",", ":")),
                })
                time.sleep(1.5)
                up = call(api, config, "alibaba.icbu.product.inventory.update", {
                    "request_param": json.dumps({"product_id": product_id, "inventory_list": [{**base, "operate": "plus"}]}, ensure_ascii=False, separators=(",", ":")),
                })
                update_response = {"refresh_down": down, "refresh_up": up}
                time.sleep(3.0)
        inv_after_response = call(api, config, "alibaba.icbu.product.sku.inventory.get", {"product_id": product_id, "language": "en_US"})
        inv_after = inventory_rows(inv_after_response)
        product_response = call(api, config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "en_US"})
        product = product_response.get("product") or {}
        score_response = call(api, config, "alibaba.icbu.product.score.get", {"product_id": product_id})
        score_result = score_response.get("result") or {}
        problems = json.loads(score_result.get("problem_map") or "{}") if score_result else {}
        main = [canonical(x) for x in ((product.get("main_image") or {}).get("images") or [])]
        struct = product.get("struct_detail") or {}
        details = [canonical(x.get("image_url")) for x in (((struct.get("detail_image") or {}).get("images")) or [])]
        companies = [canonical(x.get("image_url")) for x in (((struct.get("company_image") or {}).get("images")) or [])]
        # The current product.get response omits sku_infos for Schema-created
        # products even though the inventory endpoint returns every bound SKU.
        # Inventory rows are therefore the authoritative SKU-binding readback.
        skus = product.get("sku_infos") or []
        sku_count = max(len(skus), len(inv_after))
        row = {
            "listing_id": listing_id,
            "product_id": str(product_id),
            "status": product.get("status"),
            "display": product.get("display"),
            "subject": product.get("subject"),
            "main_count": len(main),
            "main_unique": len({key(x) for x in main}) == 6,
            "detail_count": len(details),
            "detail_unique": len({key(x) for x in details}) == 4,
            "main_detail_disjoint": not ({key(x) for x in main} & {key(x) for x in details}),
            "company_count": len(companies),
            "sku_count": sku_count,
            "inventory_values": sorted({int(x.get("inventory") or 0) for x in inv_after}),
            "inventory_pass": len(inv_after) == 30 and all(int(x.get("inventory") or 0) == TARGET_INVENTORY for x in inv_after),
            "quality_score": score_result.get("final_score"),
            "quality_problems": (problems.get("extendProblemMap") or {}),
            "quality_problem_map": problems,
            "update_error": (update_response or {}).get("error_response"),
        }
        row["content_pass"] = all((
            row["main_count"] == 6, row["main_unique"], row["detail_count"] == 4,
            row["detail_unique"], row["main_detail_disjoint"], row["company_count"] == 5,
            row["sku_count"] == 30,
        ))
        report["products"].append(row)
        print(listing_id, row["status"], row["display"], row["inventory_pass"], row["quality_score"], row["content_pass"], flush=True)
        time.sleep(args.delay)

    report["all_inventory_pass"] = all(x["inventory_pass"] for x in report["products"])
    report["all_content_pass"] = all(x["content_pass"] for x in report["products"])
    report["all_score_5"] = all(x["quality_score"] == "5.00" for x in report["products"])
    out = folder / (args.output or "全链路回读.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
