from __future__ import annotations

import argparse
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import re
import time
from urllib.parse import urlparse
from xml.etree import ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT_PATH = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG_PATH = Path.home() / ".config/beiqiang/alibaba-openapi.json"
ASSET_ROOT = Path(
    r"E:\贝强大文件\01_产品资产\02_可发布素材\00_最终上传\00_共用中性公司图_v2_2026-09-04"
)
RECEIPT_ROOT = ROOT / "02_Alibaba运营/01_店铺与全店诊断/全量商品审查_2026-09-04/公司图v2"
M8811_REVIEWING_ID = "1601939735063"

FILES = [
    (ASSET_ROOT / "01_factory.jpg", 400, "Company overview"),
    (ASSET_ROOT / "02_customization.jpg", 550, "Customization capabilities"),
    (ASSET_ROOT / "03_production.jpg", 600, "Production workflow"),
    (ASSET_ROOT / "04_quality.jpg", 500, "Factory profile"),
    (ASSET_ROOT / "05_packing.jpg", 700, "Packaging & shipping specifications"),
]

OLD_KEYS = {
    "Sf587c854711748af9759e77ce5aeb03c3",
    "Sfea34bbd56ae4d0583aa855838eb1454F",
    "S2a3af5690d524680824086ad8419dbc9G",
    "Sdc4e18f098e142b797df687e8befbfa14",
    "Sc1dc6ec7d435404db6a31c6938a734a0g",
    "S85b6763402114d958afb753952d130e6n",
    "S08bdd1a31b3541f78e50f4b8be26cfadA",
    "Sb785a174a04043129c63a39a19df1c2ep",
    "Hc99422065f7644c18da852e6adbd4a40u",
    "H9c98f0404800441cb760040394aa2294d",
}


def load_client():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def failed(client, response: dict) -> bool:
    return bool(client.api_error(response)) or response.get("biz_success") is False or response.get("model") is False


def top_call_retry(client, config, method: str, params: dict, attempts: int = 3) -> dict:
    """Retry transport interruptions only; business errors remain fail-fast."""
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


def refs(client, response: dict) -> dict:
    return {
        "request_id": response.get("request_id"),
        "trace_id": response.get("trace_id") or response.get("_trace_id_"),
        "message": response.get("message") or response.get("msg_info"),
        "error": client.api_error(response),
    }


def image_key(url: str) -> str:
    source = url.replace("//", "https://", 1) if url.startswith("//") else url
    name = Path(urlparse(source).path).name
    name = re.sub(r"_\d+x\d+\.[^.]+$", "", name, flags=re.I)
    return name.rsplit(".", 1)[0]


def list_products(client, config) -> list[dict]:
    first = top_call_retry(client, config, "alibaba.icbu.product.list", {
        "language": "ENGLISH", "current_page": 1, "page_size": 50
    })
    if failed(client, first):
        raise RuntimeError(f"product.list failed: {first}")
    total = int(first.get("total_item", 0))
    products = list(first.get("products", []))
    page_size = int(first.get("page_size") or len(products) or 50)
    for page in range(2, (total + page_size - 1) // page_size + 1):
        response = top_call_retry(client, config, "alibaba.icbu.product.list", {
            "language": "ENGLISH", "current_page": page, "page_size": 50
        })
        if failed(client, response):
            raise RuntimeError(f"product.list page {page} failed: {response}")
        products.extend(response.get("products", []))
    return products


def get_product(client, config, product_id: str) -> tuple[dict, dict]:
    response = top_call_retry(client, config, "alibaba.icbu.product.get", {
        "product_id": product_id, "language": "ENGLISH"
    })
    product = response.get("product")
    if failed(client, response) or not product:
        raise RuntimeError(f"product.get {product_id} failed: {response}")
    return response, product


def company_keys(product: dict) -> list[str]:
    rows = (((product.get("struct_detail") or {}).get("company_image") or {}).get("images") or [])
    return [image_key(str(row.get("image_url", ""))) for row in rows]


def stable_snapshot(product: dict) -> dict:
    copy = deepcopy(product)
    copy.pop("gmt_modified", None)
    # Incremental edits legitimately move a live item into Alibaba's modified/
    # review state while the previously approved public version remains live.
    # These workflow fields are verified separately and are not content drift.
    copy.pop("status", None)
    copy.pop("display", None)
    struct = copy.get("struct_detail") or {}
    struct.pop("company_image", None)
    return copy


def append_gallery(root: ET.Element, rows: list[dict]):
    group = ET.SubElement(root, "field", {"id": "companyImage", "type": "multiComplex"})
    for row in rows:
        item = ET.SubElement(group, "complex-values")
        images = ET.SubElement(item, "field", {"id": "images", "type": "multiComplex"})
        image_item = ET.SubElement(images, "complex-values")
        image_url = ET.SubElement(image_item, "field", {"id": "imageURL", "type": "input"})
        ET.SubElement(image_url, "value").text = row["url"].replace("https:", "").replace("http:", "")
        gallery = ET.SubElement(item, "field", {"id": "gallery", "type": "singleCheck"})
        value = ET.SubElement(gallery, "value", {"displayName": row["role_name"]})
        value.text = str(row["role_id"])


def upload_assets(client, config) -> list[dict]:
    rows = []
    for path, role_id, role_name in FILES:
        if not path.is_file():
            raise RuntimeError(f"missing asset: {path}")
        response = client.upload_image(config, path, None)
        item = response.get("upload_image_response") or {}
        if failed(client, response) or not item.get("photobank_url"):
            raise RuntimeError(f"upload failed for {path}: {response}")
        rows.append({
            "source": str(path),
            "url": str(item["photobank_url"]),
            "file_id": str(item["file_id"]),
            "role_id": role_id,
            "role_name": role_name,
            **refs(client, response),
        })
    RECEIPT_ROOT.mkdir(parents=True, exist_ok=True)
    (RECEIPT_ROOT / "图片银行映射.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return rows


def load_or_upload(client, config) -> list[dict]:
    mapping = RECEIPT_ROOT / "图片银行映射.json"
    if mapping.is_file():
        return json.loads(mapping.read_text(encoding="utf-8-sig"))
    return upload_assets(client, config)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-id", help="Exact pilot product ID")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--upload-only", action="store_true")
    args = parser.parse_args()

    client = load_client()
    config = client.load_config(CONFIG_PATH)
    assets = load_or_upload(client, config)
    if args.upload_only:
        print(json.dumps({"uploaded": len(assets), "mapping": str(RECEIPT_ROOT / '图片银行映射.json')}, ensure_ascii=False))
        return

    candidates = []
    if args.product_id:
        if args.product_id == M8811_REVIEWING_ID:
            raise RuntimeError("M8811 is under review and is excluded from this operation")
        _, product = get_product(client, config, args.product_id)
        current = company_keys(product)
        if len(current) == 5 and set(current).issubset(OLD_KEYS):
            candidates.append({
                "product_id": args.product_id,
                "model": product.get("red_model", ""),
                "title": product.get("subject", ""),
                "category_id": int(product["category_id"]),
                "old_company_keys": current,
            })
    else:
        products = list_products(client, config)
        for row in products:
            product_id = str(row.get("id", ""))
            if product_id == M8811_REVIEWING_ID:
                continue
            _, product = get_product(client, config, product_id)
            current = company_keys(product)
            if len(current) == 5 and set(current).issubset(OLD_KEYS):
                candidates.append({
                    "product_id": product_id,
                    "model": row.get("red_model", ""),
                    "title": row.get("subject", ""),
                    "category_id": int(product["category_id"]),
                    "old_company_keys": current,
                })

    RECEIPT_ROOT.mkdir(parents=True, exist_ok=True)
    (RECEIPT_ROOT / "候选商品清单.json").write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if args.dry_run:
        print(json.dumps({"candidate_count": len(candidates), "candidates": candidates}, ensure_ascii=False, indent=2))
        return
    if not args.product_id or len(candidates) != 1:
        raise RuntimeError("Write mode requires one exact --product-id that matches the old five-image gallery")

    target = candidates[0]
    before_response, before = get_product(client, config, target["product_id"])
    snapshot = stable_snapshot(before)
    xml_root = ET.Element("itemSchema")
    append_gallery(xml_root, assets)
    xml = ET.tostring(xml_root, encoding="unicode")
    update_response = top_call_retry(client, config, "alibaba.icbu.product.schema.update", {
        "param_product_top_publish_request": {
            "cat_id": target["category_id"],
            "language": "en_US",
            "product_id": int(target["product_id"]),
            "xml": xml,
        }
    })
    if failed(client, update_response):
        raise RuntimeError(f"schema.update failed: {update_response}")
    after_response, after = get_product(client, config, target["product_id"])
    expected = sorted(image_key(row["url"]) for row in assets)
    actual = sorted(company_keys(after))
    verification = {
        "company_gallery_exact": actual == expected,
        "other_fields_preserved": stable_snapshot(after) == snapshot,
        "status": after.get("status"),
        "display": after.get("display"),
    }
    receipt = {
        "target": target,
        "before": refs(client, before_response),
        "update": refs(client, update_response),
        "after": refs(client, after_response),
        "assets": assets,
        "verification": verification,
    }
    receipt_path = RECEIPT_ROOT / f"试点_{target['product_id']}.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if not verification["company_gallery_exact"] or not verification["other_fields_preserved"]:
        raise RuntimeError(f"readback verification failed: {verification}")


if __name__ == "__main__":
    main()
