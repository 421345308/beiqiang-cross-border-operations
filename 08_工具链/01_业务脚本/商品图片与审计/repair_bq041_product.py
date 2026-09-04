"""Prepare/apply the BQ041/202 image repair through the Alibaba Schema API.

Default mode is local-only dry-run.  Nothing reaches Alibaba unless --apply is
passed explicitly.  The script intentionally changes only main images, color
SKU image bindings, product detail galleries, and the five neutral company
galleries.  Commercial fields are snapshotted and must remain unchanged; no
material attribute is invented here.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import time
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT_PATH = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG_PATH = Path.home() / ".config/beiqiang/alibaba-openapi.json"
PRODUCT_ID = 10000047127570
MODEL = "BQ041 / 202"
ASSET_ROOT = Path(r"E:\贝强大文件\01_产品资产\02_可发布素材\00_最终上传\BQ041_202")
COMPANY_ROOT = Path(r"E:\贝强大文件\01_产品资产\02_可发布素材\00_最终上传\00_共用中性公司图_v2_2026-09-04")
AUDIT_ROOT = ROOT / "02_Alibaba运营/01_店铺与全店诊断/全量商品审查_2026-09-04"
CACHE_PATH = AUDIT_ROOT / "bq041_image_bank_cache.json"
RECEIPT_PATH = AUDIT_ROOT / "bq041_repair_receipt.json"
GLOBAL_COMPANY_MAPPING = AUDIT_ROOT / "公司图v2/图片银行映射.json"

EXPECTED_COLORS = {
    # Keep Alibaba's existing SKU value names; only repair their thumbnails.
    "Black": ASSET_ROOT / "03_颜色图/01_black_sku.jpg",
    "Blue": ASSET_ROOT / "03_颜色图/02_blue_sku.jpg",
    "Purple": ASSET_ROOT / "03_颜色图/03_purple_sku.jpg",
}
MAIN_FILES = [
    ASSET_ROOT / "01_主图/01_main_square_clean.png",
    ASSET_ROOT / "01_主图/02_upper_clean.png",
    ASSET_ROOT / "01_主图/03_structure_clean.png",
    ASSET_ROOT / "01_主图/04_sole_clean.png",
    ASSET_ROOT / "01_主图/05_colors_clean.png",
    ASSET_ROOT / "01_主图/06_scene.jpg",
]
DETAIL_FILES = [
    (ASSET_ROOT / "02_详情页/01_product_overview_clean.png", 350, "Other product images"),
    (ASSET_ROOT / "02_详情页/02_specifications_clean.png", 300, "Detail shot"),
    (ASSET_ROOT / "02_详情页/03_size_range_clean.png", 150, "Product dimensions"),
    # The local 04_color_options_clean.png is byte-identical to main image 05.
    # Exclude it because Alibaba rejects main/detail image duplication.
    (ASSET_ROOT / "02_详情页/05_order_support_clean.png", 350, "Other product images"),
    (ASSET_ROOT / "02_详情页/06_oem_inquiry.jpg", 350, "Other product images"),
]
COMPANY_FILES = [
    (COMPANY_ROOT / "01_factory.jpg", 400, "Company overview"),
    (COMPANY_ROOT / "02_customization.jpg", 550, "Customization capabilities"),
    (COMPANY_ROOT / "03_production.jpg", 600, "Production workflow"),
    (COMPANY_ROOT / "04_quality.jpg", 500, "Factory profile"),
    (COMPANY_ROOT / "05_packing.jpg", 700, "Packaging & shipping specifications"),
]

# Confirmed in the BQ041/202 local upload sheet. These are recorded for the
# receipt and guard checks only; this repair does not overwrite them.
COMMERCIAL_BASELINE = {
    "moq": "2 pairs",
    "price_ladder": {"2": "9.49", "50": "9.19", "100": "9.09"},
    "lead_time": "31 days for 100 pairs",
    "package": "34 x 23 x 13 cm / 0.5 kg / 1 pair",
    "cargo_type": "General cargo",
    "packing": "Standard shoe box or plastic bag",
}


def load_client():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def refs(client, response: dict) -> dict:
    return {"request_id": response.get("request_id"), "trace_id": response.get("trace_id") or response.get("_trace_id_"), "message": response.get("message") or response.get("msg_info"), "error": client.api_error(response)}


def failed(client, response: dict) -> bool:
    return bool(client.api_error(response)) or response.get("biz_success") is False or response.get("model") is False


def top_call_retry(client, config, method: str, params: dict, attempts: int = 3) -> dict:
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return client.top_call(config, method, params)
        except Exception as exc:
            last_error = exc
            text = str(exc).lower()
            transient = any(token in text for token in ("ssl", "eof", "timed out", "connection reset"))
            if not transient or attempt == attempts:
                raise
            time.sleep(attempt * 2)
    raise RuntimeError(f"API transport failed after retries: {last_error}")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def validate_assets() -> list[dict]:
    rows = []
    all_files = list(EXPECTED_COLORS.values()) + MAIN_FILES + [row[0] for row in DETAIL_FILES] + [row[0] for row in COMPANY_FILES]
    if len(set(all_files)) != len(all_files):
        raise RuntimeError("asset list contains duplicate paths")
    for path in all_files:
        if not path.is_file():
            raise FileNotFoundError(path)
        size = path.stat().st_size
        if size > 5 * 1024 * 1024:
            raise RuntimeError(f"asset exceeds 5 MB upload limit: {path}")
        rows.append({"path": str(path), "sha256": sha256(path), "bytes": size})
    main_hashes = {sha256(path) for path in MAIN_FILES}
    detail_hashes = {sha256(path) for path, _, _ in DETAIL_FILES}
    if main_hashes & detail_hashes:
        raise RuntimeError("main/detail images contain byte-identical content")
    return rows


def image_key(url: str) -> str:
    source = url.replace("//", "https://", 1) if url.startswith("//") else url
    name = Path(urlparse(source).path).name
    return re.sub(r"_\d+x\d+\.[^.]+$", "", name, flags=re.I).rsplit(".", 1)[0]


def get_product(client, config):
    response = top_call_retry(client, config, "alibaba.icbu.product.get", {"product_id": PRODUCT_ID, "language": "ENGLISH"})
    if failed(client, response) or not response.get("product"):
        raise RuntimeError(f"product.get failed: {refs(client, response)}")
    return response, response["product"]


def render_schema(client, config):
    response = top_call_retry(client, config, "alibaba.icbu.product.schema.render", {"param_product_top_publish_request": {"product_id": PRODUCT_ID, "language": "en_US"}})
    xml_text = response.get("data")
    if not isinstance(xml_text, str):
        raise RuntimeError(f"schema.render failed: {refs(client, response)}")
    return response, ET.fromstring(xml_text)


def stable_snapshot(product: dict) -> dict:
    # Images are deliberately excluded; every other listed field is protected.
    keys = ["subject", "category_id", "language", "product_type", "keywords", "attributes", "sourcing_trade", "price_type", "rts", "group_id", "product_sku"]
    snap = {key: deepcopy(product.get(key)) for key in keys}
    for group in (snap.get("product_sku") or {}).get("sku_attributes", []):
        for value in group.get("values", []):
            value.pop("image_url", None)
    return snap


def formal_url(url: str) -> bool:
    normalized = "https:" + url if url.startswith("//") else url
    # Alibaba currently returns both /kf/<file> and
    # /kf/<file>/<member>/<file> for valid image-bank uploads.
    return bool(re.match(r"^https://sc\d+\.alicdn\.com/kf/(?:[^/]+/286385890/)?[^/]+\.(?:jpg|jpeg|png|webp)$", normalized, re.I))


def upload_image_retry(client, config, path: Path, attempts: int = 3) -> dict:
    for attempt in range(1, attempts + 1):
        try:
            return client.upload_image(config, path, None)
        except Exception as exc:
            text = str(exc).lower()
            transient = any(token in text for token in ("ssl", "eof", "timed out", "connection reset"))
            if not transient or attempt == attempts:
                raise
            time.sleep(attempt * 2)
    raise RuntimeError("unreachable")


def upload_or_cache(client, config, path: Path, cache: dict, apply: bool) -> dict:
    digest = sha256(path)
    cached = cache.get(digest)
    if cached and cached.get("url") and formal_url(cached["url"]):
        return {**cached, "source": str(path), "sha256": digest, "cached": True}
    if not apply:
        return {"source": str(path), "sha256": digest, "bytes": path.stat().st_size, "planned": True}
    response = upload_image_retry(client, config, path)
    item = response.get("upload_image_response") or {}
    url = str(item.get("photobank_url") or "")
    if url.startswith("//"):
        url = "https:" + url
    if failed(client, response) or not formal_url(url) or not item.get("file_id"):
        raise RuntimeError(f"image upload failed or non-canonical URL for {path}: {refs(client, response)}")
    result = {"source": str(path), "sha256": digest, "bytes": path.stat().st_size, "url": url, "file_id": str(item["file_id"]), "cached": False, "refs": refs(client, response)}
    cache[digest] = result
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def seed_shared_company_cache(cache: dict) -> None:
    """Reuse the already uploaded global company v2 assets instead of duplicating them."""
    if not GLOBAL_COMPANY_MAPPING.is_file():
        return
    known = json.loads(GLOBAL_COMPANY_MAPPING.read_text(encoding="utf-8-sig"))
    by_source = {str(Path(row["source"]).resolve()): row for row in known}
    for path, _, _ in COMPANY_FILES:
        row = by_source.get(str(path.resolve()))
        if not row:
            continue
        url = str(row["url"])
        if url.startswith("//"):
            url = "https:" + url
        cache[sha256(path)] = {
            "source": str(path), "sha256": sha256(path), "bytes": path.stat().st_size,
            "url": url, "file_id": str(row["file_id"]), "cached": True,
        }


def append_gallery(root: ET.Element, field_id: str, rows: list[dict]):
    group = ET.SubElement(root, "field", {"id": field_id, "type": "multiComplex"})
    for row in rows:
        item = ET.SubElement(group, "complex-values")
        images = ET.SubElement(item, "field", {"id": "images", "type": "multiComplex"})
        image_item = ET.SubElement(images, "complex-values")
        image_url = ET.SubElement(image_item, "field", {"id": "imageURL", "type": "input"})
        ET.SubElement(image_url, "value").text = row["url"].replace("https:", "").replace("http:", "")
        gallery = ET.SubElement(item, "field", {"id": "gallery", "type": "singleCheck"})
        value = ET.SubElement(gallery, "value", {"displayName": row["role_name"]})
        value.text = str(row["role_id"])


def build_xml(schema: ET.Element, color_rows: dict[str, dict], main_rows: list[dict], details: list[dict], companies: list[dict]) -> str:
    color_field = schema.find(".//field[@id='p-191288010']")
    if color_field is None:
        raise RuntimeError("schema color field p-191288010 not found; refusing to guess attribute IDs")
    live_values = {v.attrib.get("inputValue", "") : v for v in color_field.findall("./values/value")}
    if set(live_values) != set(color_rows):
        raise RuntimeError(f"live/schema color set mismatch: live={sorted(live_values)} local={sorted(color_rows)}")
    root = ET.Element("itemSchema")
    sale_prop = ET.SubElement(root, "field", {"id": "saleProp", "type": "complex"})
    cv = ET.SubElement(sale_prop, "complex-value")
    cf = ET.SubElement(cv, "field", {"id": "p-191288010", "type": "multiCheck"})
    values = ET.SubElement(cf, "values")
    for name, old in live_values.items():
        attrs = dict(old.attrib)
        attrs["img"] = color_rows[name]["url"]
        item = ET.SubElement(values, "value", attrs)
        item.text = old.text
    for i, row in enumerate(main_rows):
        field = ET.SubElement(root, "field", {"id": f"scImages_{i}", "type": "input"})
        value = ET.SubElement(field, "value", {"fileFlag": "no", "fileId": str(row["file_id"])})
        value.text = row["url"].replace("https:", "").replace("http:", "")
    append_gallery(root, "detailImage", details)
    append_gallery(root, "companyImage", companies)
    return ET.tostring(root, encoding="unicode")


def gallery_keys(product: dict, key: str) -> list[str]:
    rows = (((product.get("struct_detail") or {}).get(key) or {}).get("images") or [])
    return [image_key(str(row.get("image_url", ""))) for row in rows]


def color_keys(product: dict) -> dict[str, str]:
    for group in (product.get("product_sku") or {}).get("sku_attributes", []):
        if int(group.get("attribute_id", 0)) == 191288010:
            return {str(v.get("system_value_name")): image_key(str(v.get("image_url", ""))) for v in group.get("values", [])}
    return {}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="perform API uploads/update; omitted means local dry-run")
    args = parser.parse_args()
    assets = validate_assets()
    cache = json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.is_file() else {}
    seed_shared_company_cache(cache)
    plan = {"product_id": PRODUCT_ID, "model": MODEL, "mode": "apply" if args.apply else "dry-run", "assets": assets, "commercial_baseline_to_preserve": COMMERCIAL_BASELINE, "main_count": len(MAIN_FILES), "detail_count": len(DETAIL_FILES), "company_count": len(COMPANY_FILES), "material_policy": "Do not write material attributes; local sheet supports knitted textile upper and Foamed Cushion Sole only."}
    if not args.apply:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    client = load_client()
    config = client.load_config(CONFIG_PATH)
    before_response, before = get_product(client, config)
    if MODEL not in str(before.get("attributes", "")) and MODEL not in str(before.get("subject", "")):
        raise RuntimeError(f"identity check failed; expected {MODEL}")
    before_snapshot = stable_snapshot(before)
    render_response, schema = render_schema(client, config)
    color_rows = {name: upload_or_cache(client, config, path, cache, True) for name, path in EXPECTED_COLORS.items()}
    main_rows = [upload_or_cache(client, config, path, cache, True) for path in MAIN_FILES]
    detail_rows = [{**upload_or_cache(client, config, path, cache, True), "role_id": role_id, "role_name": role_name} for path, role_id, role_name in DETAIL_FILES]
    company_rows = [{**upload_or_cache(client, config, path, cache, True), "role_id": role_id, "role_name": role_name} for path, role_id, role_name in COMPANY_FILES]
    xml = build_xml(schema, color_rows, main_rows, detail_rows, company_rows)
    update_response = top_call_retry(client, config, "alibaba.icbu.product.schema.update", {"param_product_top_publish_request": {"cat_id": int(before["category_id"]), "language": "en_US", "product_id": PRODUCT_ID, "xml": xml}})
    if failed(client, update_response):
        raise RuntimeError(f"schema.update failed: {refs(client, update_response)}")
    after_response, after = get_product(client, config)
    expected_colors = {name: image_key(row["url"]) for name, row in color_rows.items()}
    verification = {"identity_ok": MODEL in str(after.get("attributes", "")) or MODEL in str(after.get("subject", "")), "main_count_ok": len((after.get("main_image") or {}).get("images", [])) == 6, "colors_ok": color_keys(after) == expected_colors, "details_ok": set(gallery_keys(after, "detail_image")) == {image_key(row["url"]) for row in detail_rows}, "companies_ok": set(gallery_keys(after, "company_image")) == {image_key(row["url"]) for row in company_rows}, "commercial_fields_preserved": stable_snapshot(after) == before_snapshot}
    receipt = {"product_id": PRODUCT_ID, "model": MODEL, "before": refs(client, before_response), "render": refs(client, render_response), "update": refs(client, update_response), "readback": refs(client, after_response), "commercial_baseline": COMMERCIAL_BASELINE, "uploaded": {"colors": color_rows, "main": main_rows, "details": detail_rows, "companies": company_rows}, "verification": verification}
    RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT_PATH.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if not all(verification.values()):
        raise RuntimeError(f"readback verification failed; receipt={RECEIPT_PATH}")


if __name__ == "__main__":
    main()
