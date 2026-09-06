"""Consolidate the authoritative post-publish audit for HR001-HR067."""
from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
FIRST = ROOT / "02_Alibaba运营/05_扩品工程/热榜8款API上架_2026-09-05"
CONT = ROOT / "02_Alibaba运营/05_扩品工程/热榜持续扩品_2026-09-05"
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG = Path.home() / ".config/beiqiang/alibaba-openapi.json"


def load_rows(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")).get("products", [])


def refresh_score(row: dict, api, config) -> None:
    if row.get("quality_score") == "5.00":
        return
    response = api.top_call(
        config,
        "alibaba.icbu.product.score.get",
        {"product_id": int(row["product_id"])},
    )
    result = response.get("result") or {}
    row["quality_score"] = result.get("final_score")
    problem_map = json.loads(result.get("problem_map") or "{}") if result else {}
    row["quality_problem_map"] = problem_map
    row["quality_problems"] = problem_map.get("extendProblemMap") or {}


def collect_receipt_assets() -> dict[str, dict]:
    rows: dict[str, dict] = {}
    paths = [FIRST / "publish_receipt.json", FIRST / "update_receipt.json"]
    paths += [FIRST / "publish_B_receipt.json", FIRST / "publish_C_receipt.json"]
    paths += sorted(CONT.glob("publish_[ABC]*_receipt.json"))
    for path in paths:
        if not path.is_file():
            continue
        for row in json.loads(path.read_text(encoding="utf-8")).get("products", []):
            if row.get("listing_id") and row.get("main"):
                rows[row["listing_id"]] = row
    return rows


def is_official_cdn(url: str) -> bool:
    host = urlparse(str(url or "")).hostname or ""
    return host == "alicdn.com" or host.endswith(".alicdn.com")


def asset_id(asset: dict) -> str:
    return str(asset.get("sha256") or asset.get("file_id") or asset.get("url") or "")


def main() -> None:
    merged: dict[str, dict] = {}

    # The 23-row current audit excludes HR001-A because that first link was
    # finalized through an incremental update receipt. Its exact current audit
    # is loaded immediately afterwards.
    for row in load_rows(FIRST / "最终全链路回读_24条.json"):
        merged[row["listing_id"]] = row
    for row in load_rows(FIRST / "最终回读_HR001-A.json"):
        merged[row["listing_id"]] = row

    # Load the broad continuation audit first, then let repair audits override
    # rows whose inventory was synchronized after the first readback.
    for name in (
        "全链路回读_009_028.json",
        "全链路回读_029_048.json",
        "全链路回读_049_067.json",
        "修复回读_025_027.json",
        "修复回读_045_052.json",
        "修复回读_053_060.json",
        "修复回读_061_067.json",
    ):
        for row in load_rows(CONT / name):
            merged[row["listing_id"]] = row

    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
    api = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(api)
    config = api.load_config(CONFIG)
    for row in merged.values():
        refresh_score(row, api, config)

    products = [merged[key] for key in sorted(merged)]
    expected = {f"HR{model:03d}-{variant}" for model in range(1, 68) for variant in "ABC"}
    actual = set(merged)
    checks = {
        "expected_count": 201,
        "actual_count": len(products),
        "missing": sorted(expected - actual),
        "unexpected": sorted(actual - expected),
        "all_approved": all(row.get("status") == "approved" for row in products),
        "all_displayed": all(row.get("display") == "Y" for row in products),
        "all_inventory_pass": all(row.get("inventory_pass") is True for row in products),
        "all_content_pass": all(row.get("content_pass") is True for row in products),
        "all_score_5": all(row.get("quality_score") == "5.00" for row in products),
        "score_distribution": dict(Counter(str(row.get("quality_score")) for row in products)),
    }
    receipts = collect_receipt_assets()
    asset_failures = []
    for listing_id in sorted(expected):
        row = receipts.get(listing_id) or {}
        main = row.get("main") or []
        details = row.get("details") or []
        colors = row.get("colors") or []
        main_hashes = [asset_id(x) for x in main]
        detail_hashes = [asset_id(x) for x in details]
        title = str(row.get("title") or "")
        keywords = str(row.get("keywords") or "")
        reasons = []
        if len(main) != 6 or len(set(main_hashes)) != 6:
            reasons.append("main_images")
        if not main or "_b2b" not in Path(str(main[0].get("source") or "")).stem.lower():
            reasons.append("first_main_b2b")
        if len(details) != 4 or len(set(detail_hashes)) != 4:
            reasons.append("detail_images")
        if set(main_hashes) & set(detail_hashes):
            reasons.append("main_detail_overlap")
        if len(colors) != 3:
            reasons.append("color_images")
        urls = [x.get("url") for x in main + details]
        urls += [((x.get("asset") or {}).get("url")) for x in colors]
        if not urls or not all(is_official_cdn(url) for url in urls):
            reasons.append("non_official_url")
        if not title or len(title) > 128:
            reasons.append("title")
        if not keywords or any(char in keywords for char in ",.:"):
            reasons.append("keywords")
        if reasons:
            asset_failures.append({"listing_id": listing_id, "reasons": reasons})
    receipt_titles = [str(row.get("title") or "") for row in receipts.values()]
    receipt_keywords = [str(row.get("keywords") or "") for row in receipts.values()]
    asset_checks = {
        "receipt_count": len(receipts),
        "all_asset_checks_pass": not asset_failures and len(receipts) == 201,
        "all_titles_unique": len(receipt_titles) == len(set(receipt_titles)) == 201,
        "all_keywords_unique": len(receipt_keywords) == len(set(receipt_keywords)) == 201,
        "failures": asset_failures,
    }
    report = {"checks": checks, "asset_checks": asset_checks, "products": products}
    out = CONT / "HR001-HR067_201条最终全链路回读.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    print(json.dumps(asset_checks, ensure_ascii=False, indent=2))
    print(out)


if __name__ == "__main__":
    main()
