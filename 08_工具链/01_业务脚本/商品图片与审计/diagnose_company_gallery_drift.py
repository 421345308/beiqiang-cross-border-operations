from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
BASE_PATH = ROOT / "08_工具链/01_业务脚本/商品图片与审计/replace_global_company_gallery_v2.py"
CACHE_PATH = ROOT / "02_Alibaba运营/01_店铺与全店诊断/全量商品审查_2026-09-04/api_product_get_details.json"


def load_base():
    spec = importlib.util.spec_from_file_location("replace_global_company_gallery_v2", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


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
    base = load_base()
    client = base.load_client()
    config = client.load_config(base.CONFIG_PATH)
    cache = json.loads(CACHE_PATH.read_text(encoding="utf-8-sig"))
    result = {}
    for product_id in args.product_ids:
        cached = (cache.get(product_id) or {}).get("product") or {}
        _, current = base.get_product(client, config, product_id)
        result[product_id] = walk(base.stable_snapshot(cached), base.stable_snapshot(current))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
