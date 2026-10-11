from __future__ import annotations

import argparse
import time
from copy import deepcopy
import importlib.util
import json
from pathlib import Path


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT_PATH = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG_PATH = Path.home() / ".config/beiqiang/alibaba-openapi.json"
CACHE_PATH = ROOT / "02_Alibaba运营/01_店铺与全店诊断/全量商品审查_2026-09-04/api_product_get_details.json"


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

def get_product(client, config, product_id: str) -> tuple[dict, dict]:
    response = top_call_retry(client, config, "alibaba.icbu.product.get", {
        "product_id": product_id, "language": "ENGLISH"
    })
    product = response.get("product")
    if failed(client, response) or not product:
        raise RuntimeError(f"product.get {product_id} failed: {response}")
    return response, product

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
    # Alibaba may reorder detail-image rows after an incremental update while
    # preserving the exact image URLs and semantic roles. Compare their content,
    # not the platform-controlled presentation order.
    detail_rows = ((struct.get("detail_image") or {}).get("images") or [])
    if detail_rows:
        detail_rows.sort(key=lambda row: (
            str(row.get("image_url", "")),
            str((row.get("image_set") or {}).get("id", "")),
            str((row.get("image_set") or {}).get("name", "")),
        ))
    return copy

def walk(before, after, path=""):
    if type(before) is not type(after):
        return [{"path": path, "before": before, "after": after}]
    if isinstance(before, dict):
        rows = []
        for key in sorted(set(before) | set(after)):
            rows.extend(walk(before.get(key, "<missing>"), after.get(key, "<missing>"), f"{path}.{key}".strip(".")))
        return rows
    if isinstance(before, list):
        if before != after:
            return [{"path": path, "before": before, "after": after}]
        return []
    return [] if before == after else [{"path": path, "before": before, "after": after}]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("product_ids", nargs="+")
    args = parser.parse_args()
    client = load_client()
    config = client.load_config(CONFIG_PATH)
    cache = json.loads(CACHE_PATH.read_text(encoding="utf-8-sig"))
    result = {}
    for product_id in args.product_ids:
        cached = (cache.get(product_id) or {}).get("product") or {}
        _, current = get_product(client, config, product_id)
        result[product_id] = walk(stable_snapshot(cached), stable_snapshot(current))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
