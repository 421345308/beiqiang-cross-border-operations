from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import importlib.util
import json
from pathlib import Path
import re
import time


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT_PATH = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG_PATH = Path.home() / ".config/beiqiang/alibaba-openapi.json"
VIDEO_BANK = ROOT / "02_Alibaba运营/06_图片与检查记录/API全量图片审计_2026-09-03/video_bank.json"
CATALOG_CSV = ROOT / "02_Alibaba运营/01_店铺与全店诊断/全量商品审查_2026-09-04/full_product_audit.csv"
OUTPUT_DIR = ROOT / "02_Alibaba运营/01_店铺与全店诊断/全量商品审查_2026-09-04/视频对应审计"


def load_client():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def relation(client, config, video):
    last_error = None
    for attempt in range(1, 4):
        try:
            response = client.top_call(config, "alibaba.icbu.video.relation.product.list", {
                "type": "videoId", "video_id": str(video["video_id"])
            })
            break
        except Exception as exc:
            last_error = exc
            if attempt == 3:
                raise
            time.sleep(attempt * 2)
    else:
        raise RuntimeError(last_error)
    model = (response.get("result") or {}).get("model") or []
    return video, response, [str(row.get("product_id", "")) for row in model]


def main():
    client = load_client()
    config = client.load_config(CONFIG_PATH)
    video_data = json.loads(VIDEO_BANK.read_text(encoding="utf-8-sig"))
    videos = [row for row in video_data.get("result", {}).get("model", {}).get("list", []) if row.get("status") == "approved"]
    bindings = {}
    relation_receipts = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(relation, client, config, video) for video in videos]
        for job in as_completed(jobs):
            video, response, product_ids = job.result()
            relation_receipts.append({
                "video_id": video.get("video_id"), "title": video.get("title"),
                "product_ids": product_ids, "request_id": response.get("request_id"),
                "trace_id": response.get("trace_id") or response.get("_trace_id_"),
                "error": client.api_error(response),
            })
            for product_id in product_ids:
                bindings.setdefault(product_id, []).append(video)

    rows = list(csv.DictReader(CATALOG_CSV.open(encoding="utf-8-sig", newline="")))
    audit = []
    for row in rows:
        encrypted = row.get("encryptedProductId", "")
        expected_match = re.search(r"BQ(\d{3})", row.get("modelNumber", ""), flags=re.I)
        expected = expected_match.group(1) if expected_match else None
        related = bindings.get(encrypted, [])
        specific = []
        generic = []
        mismatched = []
        for video in related:
            match = re.search(r"BQ(\d{3})", str(video.get("title", "")), flags=re.I)
            if match:
                specific.append(video)
                if expected and match.group(1) != expected:
                    mismatched.append(video)
            else:
                generic.append(video)
        if mismatched:
            status = "WRONG_PRODUCT_VIDEO"
        elif specific:
            status = "PRODUCT_VIDEO_MATCH"
        elif generic:
            status = "GENERIC_FACTORY_VIDEO"
        else:
            status = "NO_VIDEO_BINDING"
        audit.append({
            "productId": row.get("productId"), "encryptedProductId": encrypted,
            "modelNumber": row.get("modelNumber"), "title": row.get("title"),
            "expectedBQ": expected or "", "status": status,
            "videoTitles": " | ".join(str(video.get("title", "")) for video in related),
            "videoIds": " | ".join(str(video.get("video_id", "")) for video in related),
        })

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fields = list(audit[0])
    with (OUTPUT_DIR / "全店视频对应审计.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(audit)
    summary = {status: sum(row["status"] == status for row in audit) for status in (
        "PRODUCT_VIDEO_MATCH", "GENERIC_FACTORY_VIDEO", "WRONG_PRODUCT_VIDEO", "NO_VIDEO_BINDING"
    )}
    (OUTPUT_DIR / "视频反向绑定回执.json").write_text(json.dumps(relation_receipts, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT_DIR / "视频审计摘要.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
