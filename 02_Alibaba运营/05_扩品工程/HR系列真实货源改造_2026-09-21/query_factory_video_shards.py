from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT_PATH = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG_PATH = Path.home() / ".config/beiqiang/alibaba-openapi.json"
OUT = ROOT / (
    "02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21/"
    "通用工厂视频容量分片_OpenAPI回读.json"
)


def load_client():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def call_with_backoff(client, config, method: str, params: dict) -> dict:
    response = {}
    for attempt in range(6):
        response = client.top_call(config, method, params)
        error = client.api_error(response)
        if not error:
            return response
        if error.get("code") != "ApiCallLimit" and error.get("type") != "ISP":
            return response
        time.sleep(min(2 + attempt * 2, 10))
    return response


def main() -> None:
    client = load_client()
    config = client.load_config(CONFIG_PATH)
    videos: list[dict] = []
    query_refs: list[dict] = []
    page = 1
    while True:
        response = call_with_backoff(
            client,
            config,
            "alibaba.icbu.video.query",
            {"current_page": page, "page_size": 50},
        )
        error = client.api_error(response)
        if error:
            raise RuntimeError(f"video.query failed on page {page}: {error}")
        model = (response.get("result") or {}).get("model") or {}
        rows = model.get("list") or []
        videos.extend(rows)
        query_refs.append(
            {
                "page": page,
                "request_id": response.get("request_id"),
                "trace_id": response.get("trace_id") or response.get("_trace_id_"),
                "returned": len(rows),
            }
        )
        total = int(model.get("total") or model.get("total_count") or len(videos))
        if not rows or len(videos) >= total or len(rows) < 50:
            break
        page += 1

    # Only these verified duplicate-capacity entries belong to this shard set.
    # Do not query every video whose title happens to contain "factory": that is
    # both slow and semantically wrong because product-specific BQ videos are a
    # different evidence class.
    verified_title_prefix = "beiqiang footwear factory overview 42s"
    candidates = [
        row
        for row in videos
        if str(row.get("title", "")).strip().lower().startswith(verified_title_prefix)
    ]
    shards = []
    for row in candidates:
        video_id = str(row.get("video_id") or "")
        relation = call_with_backoff(
            client,
            config,
            "alibaba.icbu.video.relation.product.list",
            {"type": "videoId", "video_id": video_id},
        )
        error = client.api_error(relation)
        if error:
            raise RuntimeError(f"relation query failed for {video_id}: {error}")
        bound = (relation.get("result") or {}).get("model") or []
        shards.append(
            {
                "video_id": video_id,
                "title": row.get("title"),
                "status": row.get("status"),
                "duration": row.get("duration"),
                "gmt_create": row.get("gmt_create"),
                "bound_count": len(bound),
                "bound_product_ids": [str(item.get("product_id") or "") for item in bound],
                "relation_request_id": relation.get("request_id"),
                "relation_trace_id": relation.get("trace_id") or relation.get("_trace_id_"),
            }
        )

    result = {
        "mode": "read-only",
        "query_refs": query_refs,
        "video_total": len(videos),
        "factory_candidates": shards,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
