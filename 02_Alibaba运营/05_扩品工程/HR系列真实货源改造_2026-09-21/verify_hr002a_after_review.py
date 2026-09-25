"""Read-only verifier for HR002-A / S6077 after Alibaba review or UI cleanup."""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
PROJECT = ROOT / r"02_Alibaba运营\05_扩品工程\HR系列真实货源改造_2026-09-21"
CLIENT = ROOT / r".agents\skills\alibaba-openapi-operator\scripts\alibaba_openapi.py"
MANIFEST = PROJECT / "HR002_S6077_图片银行映射.json"
PRODUCT_ID = 1601943305914
TITLE = "Wholesale Men's Retro Mesh Lace-Up Walking Shoes Casual Sneakers EU 39-48 Model S6077"
MODEL = "HR002-A / S6077"
VIDEO_ID = "6000344840202"
COLORS = {"Black", "White"}
SIZES = {str(value) for value in range(39, 49)}
PRICES = {9.10, 9.20, 9.50}
FORBIDDEN_SYSTEM_ATTRS = {"Midsole Material", "Outsole Material", "Feature", "Lining Material", "Season"}


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


def field_values(root: ET.Element | None, field_id: str) -> list[str]:
    if root is None:
        return []
    field = root.find(f"./field[@id='{field_id}']")
    if field is None:
        return []
    return [str(node.text).strip() for node in field.findall(".//value") if node.text and str(node.text).strip()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect", choices=("submitted", "approved", "clean"), required=True)
    args = parser.parse_args()
    api = load_client()
    config = api.load_config(Path.home() / ".config" / "beiqiang" / "alibaba-openapi.json")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assets = {f'{row["role"]}_{row["slot"]}': row for row in manifest["assets"]}
    expected_main = [token(assets[f"main_{slot}"]["url"]) for slot in range(1, 7)]
    expected_detail = {token(assets[f"detail_{slot}"]["url"]) for slot in range(1, 5)}

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
    root = ET.fromstring(schema_xml) if isinstance(schema_xml, str) else None

    attrs = {str(row.get("attribute_name")): row.get("value_name") for row in product.get("attributes") or []}
    sku_block = product.get("product_sku") or {}
    axes = {
        str(group.get("attribute_name")): [str(row.get("system_value_name")) for row in group.get("values") or []]
        for group in sku_block.get("sku_attributes") or []
    }
    skus = sku_block.get("skus") or []
    prices = sorted({float(row.get("price")) for sku in skus for row in sku.get("bulk_discount_prices") or []})
    main_tokens = [token(url) for url in (product.get("main_image") or {}).get("images") or []]
    structured_detail = (((product.get("struct_detail") or {}).get("detail_image") or {}).get("images") or [])
    structured_company = (((product.get("struct_detail") or {}).get("company_image") or {}).get("images") or [])
    detail_urls = [str(row.get("image_url") or "") for row in structured_detail]
    detail_tokens = {token(url) for url in detail_urls}
    package_measure_values = field_values(root, "pkgMeasure")
    package_weight_values = field_values(root, "pkgWeight")
    lead_time_values = field_values(root, "ladderPeriod")
    custom_property_values = field_values(root, "customMoreProperty")

    def has_number(values: list[str], expected: float) -> bool:
        for value in values:
            try:
                if abs(float(value) - expected) < 1e-9:
                    return True
            except ValueError:
                continue
        return False

    expected_state = {
        "submitted": product.get("status") == "modified" and product.get("display") == "N",
        "approved": product.get("status") == "approved" and product.get("display") == "Y",
        "clean": product.get("status") in {"modified", "approved"},
    }[args.expect]
    common = {
        "expected_state_ok": expected_state,
        "title_ok": product.get("subject") == TITLE,
        "model_ok": attrs.get("Model Number") == MODEL,
        "closure_ok": attrs.get("Closure Type") == "Lace-up",
        "round_toe_ok": attrs.get("Toe Style") == "Round Toe",
        "walking_style_ok": attrs.get("Style") == "Walking Shoes",
        "colors_ok": set(axes.get("Color", [])) == COLORS,
        "sizes_ok": set(axes.get("EUR Size", [])) == SIZES,
        "sku_count_ok": len(skus) == 20,
        "inventory_999_absent": '999' not in json.dumps(skus, ensure_ascii=False),
        "prices_ok": set(prices) == PRICES,
        "main_images_ok": main_tokens == expected_main,
    }
    approved_schema_checks = {
        "schema_available": root is not None,
        "product_desc_type_structured": field_values(root, "productDescType") == ["4"] if root is not None else False,
        "structured_detail_images_ok": detail_tokens == expected_detail and len(detail_urls) == 4,
        "structured_detail_all_sc04": bool(detail_urls) and all("sc04.alicdn.com" in url for url in detail_urls),
        "company_images_5": len(structured_company) == 5,
        "video_ok": field_values(root, "imageVideo") == [VIDEO_ID] if root is not None else False,
        "legacy_system_attributes_removed": not (FORBIDDEN_SYSTEM_ATTRS & set(attrs)),
        "package_dimensions_preserved_34x23x13_cm": all(
            has_number(package_measure_values, value) for value in (34.0, 23.0, 13.0)
        ),
        "package_weight_preserved_0_5_kg": has_number(package_weight_values, 0.5),
        "structured_lead_time_preserved_100_31": all(
            has_number(lead_time_values, value) for value in (100.0, 31.0)
        ),
    }
    clean_checks = {
        "fit_type_removed": "Fit Type" not in attrs,
        "custom_properties_cleared": not custom_property_values if root is not None else False,
    }
    checks = dict(common)
    pending = {}
    if args.expect == "submitted" and root is None:
        pending = {key: "pending review; schema.render returned no XML" for key in [*approved_schema_checks, *clean_checks]}
    else:
        checks.update(approved_schema_checks)
        if args.expect == "clean":
            checks.update(clean_checks)
        else:
            pending.update({key: value for key, value in clean_checks.items() if not value})

    receipt = {
        "mode": "read-only",
        "expect": args.expect,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "product_id": PRODUCT_ID,
        "status": product.get("status"),
        "display": product.get("display"),
        "url": product.get("pc_detail_url"),
        "attributes": attrs,
        "colors": axes.get("Color", []),
        "sizes": axes.get("EUR Size", []),
        "sku_count": len(skus),
        "prices": prices,
        "main_tokens": main_tokens,
        "detail_tokens": sorted(detail_tokens),
        "package_measure_values": package_measure_values,
        "package_weight_values": package_weight_values,
        "lead_time_values": lead_time_values,
        "custom_property_values": custom_property_values,
        "checks": checks,
        "pending_or_failed_cleanup": pending,
        "all_checks_pass": all(checks.values()),
        "get_refs": refs(api, get_response),
        "render_refs": refs(api, render_response),
    }
    out = PROJECT / f"HR002-A_{args.expect}_OpenAPI终验.json"
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(out), **receipt}, ensure_ascii=False, indent=2))
    if not receipt["all_checks_pass"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
