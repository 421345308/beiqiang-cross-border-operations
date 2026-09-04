#!/usr/bin/env python3
"""Refresh the local Alibaba image-bank URL/file-id index."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
sys.path.insert(0, str(ROOT / ".agents/skills/alibaba-openapi-operator/scripts"))
from alibaba_openapi import DEFAULT_CONFIG, api_error, load_config, top_call  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--page-size", type=int, default=500)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    config = load_config(args.config)
    total = 0
    for page in range(1, 100):
        response = None
        for attempt in range(1, 6):
            try:
                response = top_call(
                    config,
                    "alibaba.icbu.photobank.list",
                    {"current_page": page, "page_size": args.page_size, "location_type": "ALL_GROUP"},
                )
                if not api_error(response) and response.get("pagination_query_list") is not None:
                    break
            except Exception:
                response = None
            time.sleep(attempt * 1.5)
        rows = (response or {}).get("pagination_query_list", {}).get("list", [])
        if not rows:
            break
        path = args.output / f"photobank_page{page}_500.json"
        path.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")
        total += len(rows)
        print(f"page={page} count={len(rows)} total={total}", flush=True)
        if len(rows) < args.page_size:
            break
    print(f"indexed={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
