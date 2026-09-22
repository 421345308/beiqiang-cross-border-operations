#!/usr/bin/env python3
"""Repair BQ024 expansion color labels, thumbnails, and SKU codes safely.

The BQ024 source product is read-only.  Each expansion keeps its four existing
custom color IDs and all 36 color/size combinations; this script only changes
their human-readable color semantics, color thumbnails, and SKU code color
segments.  Default mode is dry-run; ``--apply`` submits products sequentially.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import xml.etree.ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT_DIR = ROOT / ".agents/skills/alibaba-openapi-operator/scripts"
DEFAULT_AUDIT_DIR = ROOT / "02_Alibaba运营/06_图片与检查记录/API全量图片审计_2026-09-03"
sys.path.insert(0, str(CLIENT_DIR))

from alibaba_openapi import DEFAULT_CONFIG, api_error, load_config, top_call, upload_image  # noqa: E402
from batch_replace_hero import image_key, response_refs  # noqa: E402


SOURCE_PRODUCT_ID = "10000044041031"
PRODUCTS = {
    "1601939691342": "BQ024-W1 / A830",
    "1601939684371": "BQ024-R1 / A830",
    "1601939691340": "BQ024-O1 / A830",
}
EXPECTED_OLD = {
    "-1": "Dark Grey",
    "-20": "Light Grey",
    "-39": "Yellow Sole",
    "-58": "All Black",
}
TARGET = {
    # Legacy local filenames were checked against the source contact sheet.
    # Keep the factual mapping explicit instead of trusting those filenames.
    "-1": {"name": "All Black", "slug": "ALL-BLACK", "local_file": ROOT / "01_产品资产/02_可发布素材/00_最终上传/BQ024_A830/03_颜色图/dark_grey.jpg"},
    "-20": {"name": "Beige Grey", "slug": "BEIGE-GREY", "local_file": ROOT / "01_产品资产/02_可发布素材/00_最终上传/BQ024_A830/03_颜色图/light_grey.jpg"},
    "-39": {"name": "Black Yellow", "slug": "BLACK-YELLOW", "local_file": ROOT / "01_产品资产/02_可发布素材/00_最终上传/BQ024_A830/03_颜色图/yellow_sole.jpg"},
    "-58": {"name": "Black White", "slug": "BLACK-WHITE", "local_file": ROOT / "01_产品资产/02_可发布素材/00_最终上传/BQ024_A830/03_颜色图/all_black.jpg"},
}


def failed(response: dict) -> bool:
    return bool(api_error(response)) or response.get("biz_success") is False or response.get("model") is False


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare_target_images(config: dict, apply: bool, reuse_receipt: Path | None = None) -> list[dict]:
    reused = {}
    if reuse_receipt:
        data = json.loads(reuse_receipt.read_text(encoding="utf-8-sig"))
        reused = {str(x["color_id"]): x for x in data.get("color_image_uploads") or []}
    uploads = []
    for cid, row in TARGET.items():
        path = Path(row["local_file"])
        if not path.is_file() or path.stat().st_size > 5 * 1024 * 1024:
            raise RuntimeError(f"Invalid BQ024 color image: {path}")
        item = {"color_id": cid, "color": row["name"], "local_file": str(path),
                "sha256": sha256(path), "bytes": path.stat().st_size, "planned": not apply}
        reusable = reused.get(cid)
        if apply and reusable and reusable.get("sha256") == item["sha256"] and reusable.get("image_url") and reusable.get("file_id"):
            row["image_url"] = str(reusable["image_url"])
            item.update({"planned": False, "reused": True, "image_url": row["image_url"], "file_id": str(reusable["file_id"])})
        elif apply:
            response = upload_image(config, path, None)
            uploaded = response.get("upload_image_response") or {}
            if failed(response) or not uploaded.get("file_id") or not uploaded.get("photobank_url"):
                raise RuntimeError(f"Color image upload failed for {cid}: {response_refs(response)}")
            row["image_url"] = "https:" + str(uploaded["photobank_url"]) if str(uploaded["photobank_url"]).startswith("//") else str(uploaded["photobank_url"])
            item.update({"planned": False, "image_url": row["image_url"], "file_id": str(uploaded["file_id"]), **response_refs(response)})
        else:
            # Dry-run uses the protected source's current thumbnail URL only to
            # construct and validate XML locally; live mode replaces it with a
            # fresh seller-image-bank upload before any product write.
            source_alias = {
                "-1": "https://sc04.alicdn.com/kf/S71343b8d4d7c410fb969539cbcf5881eY.jpg",
                "-20": "https://sc04.alicdn.com/kf/Sfbbcf454c2754b4eacc3170c7fad8555r.jpg",
                "-39": "https://sc04.alicdn.com/kf/S65295bf2182f4bc29622900947cda1d7E.jpg",
                "-58": "https://sc04.alicdn.com/kf/S71b8fd1bbef643a4835e6344b599963d0.jpg",
            }[cid]
            row["image_url"] = source_alias
        uploads.append(item)
    return uploads


def call_retry(config: dict, method: str, params: dict, attempts: int = 3) -> dict:
    for attempt in range(1, attempts + 1):
        try:
            return top_call(config, method, params)
        except Exception as exc:
            transient = any(x in str(exc).lower() for x in ("ssl", "eof", "timed out", "connection reset"))
            if not transient or attempt == attempts:
                raise
            time.sleep(attempt * 2)
    raise RuntimeError("unreachable")


def get_product(config: dict, product_id: str) -> tuple[dict, dict]:
    response = call_retry(config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
    product = (response.get("product_get_response") or {}).get("product") or response.get("product") or {}
    if failed(response) or not product:
        raise RuntimeError(f"product.get failed for {product_id}: {response_refs(response)}")
    return response, product


def model_number(product: dict) -> str:
    return next((str(x.get("value_name") or "") for x in product.get("attributes") or []
                 if x.get("attribute_name") == "Model Number"), "")


def color_rows(product: dict) -> dict[str, dict]:
    for group in (product.get("product_sku") or {}).get("sku_attributes") or []:
        if int(group.get("attribute_id") or 0) == 191288010:
            return {str(x.get("value_id")): x for x in group.get("values") or []}
    return {}


def normalized_snapshot(product: dict) -> dict:
    copy = deepcopy(product)
    for key in ("status", "display", "gmt_modified", "pc_detail_url"):
        copy.pop(key, None)
    sku = copy.get("product_sku") or {}
    for row in sku.get("skus") or []:
        row.pop("sku_code", None)
    if sku.get("skus"):
        sku["skus"].sort(key=lambda row: int(row.get("sku_id") or 0))
    for group in sku.get("sku_attributes") or []:
        if int(group.get("attribute_id") or 0) == 191288010:
            for value in group.get("values") or []:
                value.pop("system_value_name", None)
                value.pop("image_url", None)
        if group.get("values"):
            group["values"].sort(key=lambda value: int(value.get("value_id") or 0))
    if sku.get("sku_attributes"):
        sku["sku_attributes"].sort(key=lambda group: int(group.get("attribute_id") or 0))
    return copy


def render(config: dict, product_id: str) -> tuple[dict, ET.Element]:
    response = call_retry(config, "alibaba.icbu.product.schema.render", {
        "param_product_top_publish_request": {"product_id": int(product_id), "language": "en_US"}
    })
    data = response.get("data")
    if failed(response) or not isinstance(data, str):
        raise RuntimeError(f"schema.render failed for {product_id}: {response_refs(response)}")
    return response, ET.fromstring(data)


def target_state(product: dict, prefix: str) -> bool:
    colors = color_rows(product)
    if set(colors) != set(TARGET):
        return False
    if any(colors[cid].get("system_value_name") != row["name"] or
           image_key(str(colors[cid].get("image_url") or "")) != image_key(row["image_url"])
           for cid, row in TARGET.items()):
        return False
    for sku in (product.get("product_sku") or {}).get("skus") or []:
        attrs = json.loads(sku.get("attr2_value") or "{}")
        cid = str(attrs.get("191288010"))
        size = str(attrs.get("222038415"))
        # attr2_value stores IDs, so derive the human size from the SKU suffix.
        expected_prefix = f"{prefix}-{TARGET[cid]['slug']}-"
        if not str(sku.get("sku_code") or "").startswith(expected_prefix):
            return False
    return True


def build_xml(rendered: ET.Element, prefix: str) -> tuple[str, list[dict]]:
    sale_prop = rendered.find("./field[@id='saleProp']")
    sku_field = rendered.find("./field[@id='sku']")
    if sale_prop is None or sku_field is None:
        raise RuntimeError("Current rendered Schema lacks saleProp or sku")
    sale_prop = deepcopy(sale_prop)
    sku_field = deepcopy(sku_field)

    color_field = sale_prop.find("./complex-value/field[@id='p-191288010']")
    values = color_field.findall("./values/value") if color_field is not None else []
    found = {str(v.text): str(v.attrib.get("inputValue") or "") for v in values}
    if found not in (EXPECTED_OLD, {cid: row["name"] for cid, row in TARGET.items()}):
        raise RuntimeError(f"Unexpected live color mapping: {found}")
    for value in values:
        row = TARGET[str(value.text)]
        value.attrib["inputValue"] = row["name"]
        value.attrib["img"] = row["image_url"]

    sku_manifest = []
    for item in sku_field.findall("./complex-values"):
        prop_values = item.findall("./field[@id='props']/values/value")
        color = next((v for v in prop_values if v.attrib.get("propId") == "191288010"), None)
        size = next((v for v in prop_values if v.attrib.get("propId") == "222038415"), None)
        outer = item.find("./field[@id='skuOuterId']/value")
        if color is None or size is None or outer is None:
            raise RuntimeError("Malformed SKU row in current Schema")
        cid = str(color.attrib["propValueId"])
        if cid not in TARGET:
            raise RuntimeError(f"Unexpected color ID in SKU: {cid}")
        size_name = str(size.attrib["propValueName"])
        color.attrib["propValueName"] = TARGET[cid]["name"]
        outer.text = f"{prefix}-{TARGET[cid]['slug']}-{size_name}"
        sku_manifest.append({"color_id": cid, "color": TARGET[cid]["name"], "size": size_name, "sku_code": outer.text})
    if len(sku_manifest) != 36 or len({x["sku_code"] for x in sku_manifest}) != 36:
        raise RuntimeError("Expected exactly 36 unique BQ024 SKU rows")
    root = ET.Element("itemSchema")
    root.append(sale_prop)
    root.append(sku_field)
    return ET.tostring(root, encoding="unicode"), sku_manifest


def process(config: dict, product_id: str, expected_model: str, apply: bool) -> dict:
    before_response, before = get_product(config, product_id)
    prefix = expected_model.split(" / ", 1)[0]
    record = {"product_id": product_id, "expected_model": expected_model, "before": response_refs(before_response),
              "before_status": before.get("status"), "before_display": before.get("display"), "mode": "apply" if apply else "dry-run"}
    if model_number(before) != expected_model or int(before.get("category_id") or 0) != 201334413:
        raise RuntimeError(f"Identity/category mismatch for {product_id}")
    if len((before.get("product_sku") or {}).get("skus") or []) != 36:
        raise RuntimeError(f"Expected 36 SKUs for {product_id}")
    if target_state(before, prefix):
        record.update(stage="verified_existing", ok=True)
        return record
    if before.get("status") != "approved" or before.get("display") != "Y":
        record.update(stage="auditing_no_resubmit", ok=False)
        return record
    current = {cid: str(row.get("system_value_name") or "") for cid, row in color_rows(before).items()}
    if current != EXPECTED_OLD:
        raise RuntimeError(f"Unexpected pre-update color state for {product_id}: {current}")

    schema_response, rendered = render(config, product_id)
    xml, sku_manifest = build_xml(rendered, prefix)
    record.update(stage="prepared", render=response_refs(schema_response), sku_manifest=sku_manifest,
                  target_colors={cid: {key: str(value) if isinstance(value, Path) else value for key, value in row.items()}
                                 for cid, row in TARGET.items()})
    if not apply:
        record.update(ok=True)
        return record

    before_snapshot = normalized_snapshot(before)
    update_response = call_retry(config, "alibaba.icbu.product.schema.update", {
        "param_product_top_publish_request": {
            "cat_id": 201334413, "language": "en_US", "product_id": int(product_id), "xml": xml,
        }
    })
    if failed(update_response):
        raise RuntimeError(f"schema.update failed for {product_id}: {response_refs(update_response)}")
    after_response, after = get_product(config, product_id)
    checks = {
        "identity_ok": model_number(after) == expected_model,
        "target_state_ok": target_state(after, prefix),
        "sku_count_36": len((after.get("product_sku") or {}).get("skus") or []) == 36,
        "non_target_fields_unchanged": normalized_snapshot(after) == before_snapshot,
    }
    record.update(stage="submitted", update=response_refs(update_response), readback=response_refs(after_response),
                  after_status=after.get("status"), after_display=after.get("display"), checks=checks, ok=all(checks.values()))
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT_DIR)
    parser.add_argument("--product-id", choices=sorted(PRODUCTS))
    parser.add_argument("--reuse-images-from", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = load_config(args.config)

    uploads = prepare_target_images(config, args.apply, args.reuse_images_from)

    schema_get = call_retry(config, "alibaba.icbu.product.schema.get", {
        "param_product_top_publish_request": {"cat_id": 201334413, "language": "en_US"}
    })
    if failed(schema_get) or not isinstance(schema_get.get("data"), str):
        raise RuntimeError(f"Current category Schema unavailable: {response_refs(schema_get)}")

    results = []
    selected = {args.product_id: PRODUCTS[args.product_id]} if args.product_id else PRODUCTS
    for product_id, expected_model in selected.items():
        results.append(process(config, product_id, expected_model, args.apply))
    receipt = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(), "source_product_id_protected": SOURCE_PRODUCT_ID,
        "mode": "apply" if args.apply else "dry-run", "current_schema": {**response_refs(schema_get), "bytes": len(schema_get["data"])},
        "color_image_uploads": uploads,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "results": {r["product_id"]: r["stage"] for r in results}}, ensure_ascii=False))
    return 0 if all(r.get("ok") for r in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
