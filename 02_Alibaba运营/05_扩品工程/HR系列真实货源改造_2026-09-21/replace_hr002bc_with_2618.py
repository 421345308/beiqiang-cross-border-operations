"""One-at-a-time HR002 B/C API-field replacement with the same sourced shoe.

Dry run by default. Structured details and actual 999 inventory rows require
separate operations and verification after platform review.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET


PROJECT = Path(__file__).parent
BASE_SCRIPT = PROJECT / "replace_hr002a_with_2618.py"
BASE_MANIFEST = PROJECT / "HR002_2618_图片银行映射.json"
BC_MANIFEST = PROJECT / "HR002_2618_BC_图片银行映射.json"
PRODUCTS = {"B": 1601943393550, "C": 1601943419438}
TITLES = {
    "B": "Wholesale Men's Black Lace Up Low Top Casual Walking Shoes Rubber Sole EU 39-48 Model 2618",
    "C": "Wholesale Men's Dark Brown Lace Up Low Top Casual Walking Shoes Rubber Sole EU 39-48 Model 2618",
}
BC_ROLES = {2: "M2_colors", 3: "M3_structure", 4: "M4_company", 5: "M5_packing", 6: "M6_sizes"}

spec = importlib.util.spec_from_file_location("hr002a_2618_base", BASE_SCRIPT)
assert spec and spec.loader
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def images(variant: str) -> dict:
    a = json.loads(BASE_MANIFEST.read_text(encoding="utf-8"))["assets"]
    bc = json.loads(BC_MANIFEST.read_text(encoding="utf-8"))["assets"]
    a_by = {(r["role"], int(r["slot"])): r for r in a}
    bc_by = {(r["variant"], r["role"]): r for r in bc}
    result = {("main_A", 1): a_by[(f"main_{variant}", 1)]}
    for slot, role in BC_ROLES.items():
        result[("main_shared", slot)] = bc_by[(variant, role)]
    for slot in (1, 2, 3):
        result[("sku", slot)] = a_by[("sku", slot)]
    for key, row in result.items():
        if not row["url"].startswith("https://sc04.alicdn.com/") or not row["file_id"]:
            raise RuntimeError({"bad_asset": key})
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("variant", choices=PRODUCTS)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    variant = args.variant
    product_id = PRODUCTS[variant]
    base.MODEL = f"HR002-{variant} / 2618"
    base.TITLE = TITLES[variant]
    base.KEYWORDS = (f"men {('black' if variant == 'B' else 'dark brown')} lace up low top "
                     "casual walking shoes rubber sole wholesale EU 39 48 model 2618")
    base.SUMMARY = (
        f"Model 2618 is a men's low-top lace-up casual shoe. This HR002-{variant} "
        f"page highlights the {('Black' if variant == 'B' else 'Dark Brown')} color; available options include "
        "Black, Khaki and Dark Brown in EU 39-48, with mesh lining and rubber midsole/outsole. "
        "Beiqiang serves B2B wholesale buyers. Confirm color-size availability, packing, "
        "quantity, customization feasibility and delivery for each order."
    )
    assets = images(variant)
    formal = base.call("alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
    product = formal.get("product") or {}
    attrs = {r.get("attribute_name"): r.get("value_name") for r in product.get("attributes") or []}
    if (product.get("status") != "approved" or product.get("display") != "Y"
            or product.get("category_id") != base.CATEGORY_ID
            or attrs.get("Model Number") not in {f"HR002-{variant}", base.MODEL}):
        raise RuntimeError({"unexpected_product_state": {"product_id": product_id,
                            "status": product.get("status"), "model": attrs.get("Model Number")}})
    render = base.call("alibaba.icbu.product.schema.render", {
        "param_product_top_publish_request": {"product_id": product_id, "language": "en_US"}
    })
    root = ET.fromstring(render["data"])
    xml = base.build_xml(root, assets).replace("HR002-A-2618-", f"HR002-{variant}-2618-")
    minimum_cny = float(base.LADDER[-1][1]) * base.USD_CNY_REFERENCE
    plan = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "apply" if args.apply else "dry_run", "variant": variant, "product_id": product_id,
        "source_url": base.SOURCE_URL, "source_price_cny": base.SOURCE_CNY,
        "minimum_usd": base.LADDER[-1][1], "minimum_cny_reference": round(minimum_cny, 2),
        "floor_cny": round(base.SOURCE_CNY * 1.30, 2),
        "price_floor_pass": minimum_cny >= base.SOURCE_CNY * 1.30,
        "title": base.TITLE, "model": base.MODEL,
        "sku_count": len(base.COLORS) * len(base.SIZES), "availability_marker": 999,
        "main_images": [assets[("main_A", 1)]["url"]] + [assets[("main_shared", n)]["url"] for n in range(2, 7)],
        "formal_request_id": formal.get("request_id"), "render_request_id": render.get("request_id"),
        "xml_sha256": hashlib.sha256(xml.encode()).hexdigest(), "xml_length": len(xml),
        "old_model_in_xml": f"HR002-{variant}</value>" in xml,
        "old_detail_in_xml": "detailImage" in xml or "companyImage" in xml,
        "structured_detail_pending_ui": True,
    }
    output = PROJECT / f"HR002-{variant}_2618_API字段预检.json"
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    if not plan["price_floor_pass"] or plan["old_model_in_xml"] or plan["old_detail_in_xml"]:
        raise RuntimeError({"preflight_failed": plan})
    if not args.apply:
        print(json.dumps({"variant": variant, "sku_count": plan["sku_count"],
                          "price_floor_pass": True, "xml_sha256": plan["xml_sha256"]}))
        return
    response = base.call("alibaba.icbu.product.schema.update", {
        "param_product_top_publish_request": {"cat_id": base.CATEGORY_ID, "language": "en_US",
                                              "product_id": product_id, "xml": xml}
    })
    readback = base.call("alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
    after = readback.get("product") or {}
    receipt = {**plan, "update_request_id": response.get("request_id"),
               "update_biz_success": response.get("biz_success"),
               "readback_request_id": readback.get("request_id"),
               "readback_status": after.get("status"), "readback_title": after.get("subject"),
               "readback_sku_count": len((after.get("product_sku") or {}).get("skus") or []),
               "readback_main_images": (after.get("main_image") or {}).get("images") or []}
    receipt_path = PROJECT / f"HR002-{variant}_2618_API字段提交回执.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"receipt": str(receipt_path), "status": receipt["readback_status"],
                      "title": receipt["readback_title"], "sku_count": receipt["readback_sku_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
