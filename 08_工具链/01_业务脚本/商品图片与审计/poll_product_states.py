#!/usr/bin/env python3
"""Read compact Alibaba product states concurrently; never writes platform data."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys
import threading
import time


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
sys.path.insert(0, str(ROOT / ".agents/skills/alibaba-openapi-operator/scripts"))
from alibaba_openapi import DEFAULT_CONFIG, api_error, load_config, top_call  # noqa: E402


_RATE_LOCK = threading.Lock()
_LAST_CALL_AT = 0.0


def throttled_top_call(config: dict, api_name: str, params: dict, min_interval: float) -> dict:
    """Serialize calls so Alibaba's one-request-per-second limit is respected."""
    global _LAST_CALL_AT
    with _RATE_LOCK:
        wait_for = min_interval - (time.monotonic() - _LAST_CALL_AT)
        if wait_for > 0:
            time.sleep(wait_for)
        response = top_call(config, api_name, params)
        _LAST_CALL_AT = time.monotonic()
        return response


def model_number(product: dict) -> str:
    return next((str(x.get("value_name") or "") for x in product.get("attributes") or []
                 if x.get("attribute_name") == "Model Number"), "")


def named_attribute(product: dict, name: str) -> dict | None:
    row = next((x for x in product.get("attributes") or [] if x.get("attribute_name") == name), None)
    if not row:
        return None
    return {"id": row.get("attribute_id"), "value_id": row.get("value_id"), "value": row.get("value_name")}


def one(config: dict, product_id: str, retries: int, retry_delay: float, min_interval: float) -> dict:
    response = {}
    for attempt in range(retries + 1):
        response = throttled_top_call(
            config,
            "alibaba.icbu.product.get",
            {"product_id": product_id, "language": "ENGLISH"},
            min_interval,
        )
        error = api_error(response)
        if not error or "ApiCallLimit" not in str(error):
            break
        if attempt < retries:
            time.sleep(retry_delay * (attempt + 1))
    product = (response.get("product_get_response") or {}).get("product") or response.get("product") or {}
    colors = []
    for group in (product.get("product_sku") or {}).get("sku_attributes") or []:
        if int(group.get("attribute_id") or 0) == 191288010:
            colors = [{"name": x.get("system_value_name"), "id": x.get("value_id"), "image_url": x.get("image_url")}
                      for x in group.get("values") or []]
    return {
        "product_id": product_id, "error": api_error(response),
        "request_id": response.get("request_id"),
        "trace_id": response.get("trace_id") or response.get("_trace_id_"),
        "status": product.get("status"), "display": product.get("display"),
        "title": product.get("subject"), "model": model_number(product),
        "closure_type": named_attribute(product, "Closure Type"),
        "image_count": len((product.get("main_image") or {}).get("images") or []),
        "images": (product.get("main_image") or {}).get("images") or [],
        "sku_count": len((product.get("product_sku") or {}).get("skus") or []),
        "colors": colors,
        "category_id": product.get("category_id"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("product_ids", nargs="+")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--retry-delay", type=float, default=1.5)
    parser.add_argument("--min-interval", type=float, default=1.1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    rows = []
    with ThreadPoolExecutor(max_workers=min(args.workers, len(args.product_ids))) as pool:
        jobs = {
            pool.submit(one, config, pid, args.retries, args.retry_delay, args.min_interval): pid
            for pid in args.product_ids
        }
        for job in as_completed(jobs):
            try:
                rows.append(job.result())
            except Exception as exc:
                rows.append({"product_id": jobs[job], "error": str(exc)})
    order = {pid: i for i, pid in enumerate(args.product_ids)}
    rows.sort(key=lambda row: order[row["product_id"]])
    text = json.dumps(rows, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)
    return 1 if any(row.get("error") for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
