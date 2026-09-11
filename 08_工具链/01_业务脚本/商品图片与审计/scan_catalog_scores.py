from __future__ import annotations

import argparse
import importlib.util
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
AUDIT = ROOT / "02_Alibaba运营/01_店铺与全店诊断/全量商品审查_2026-09-04"
DETAILS = AUDIT / "api_product_get_details.json"
OUTPUT = AUDIT / "质量分全量回读_2026-09-05.json"
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG = Path(r"C:\Users\spq\.config\beiqiang\alibaba-openapi.json")


def load_client():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load Alibaba OpenAPI client")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--only", action="append", default=[])
    args = parser.parse_args()
    api = load_client()
    config = api.load_config(CONFIG)
    details = json.loads(DETAILS.read_text(encoding="utf-8-sig"))
    def scan_one(index: int, product_id: str) -> dict:
        product = (details[product_id] or {}).get("product") or {}
        model = next(
            (
                str(row.get("value") or "")
                for row in product.get("attributes") or []
                if str(row.get("name") or "").strip().lower()
                in {"model number", "model no.", "model"}
            ),
            "",
        )
        last_error = None
        for attempt in range(1, 4):
            try:
                response = api.top_call(
                    config,
                    "alibaba.icbu.product.score.get",
                    {"product_id": product_id},
                )
                result = response.get("result") or {}
                problem_map = result.get("problem_map") or "{}"
                if isinstance(problem_map, str):
                    problem_map = json.loads(problem_map)
                return {
                    "sequence": index,
                    "product_id": product_id,
                    "encrypted_product_id": product.get("product_id"),
                    "model": model,
                    "title": product.get("subject"),
                    "final_score": result.get("final_score"),
                    "boutique_tag": result.get("boutique_tag"),
                    "problem_map": problem_map,
                    "request_id": response.get("request_id"),
                    "trace_id": response.get("_trace_id_"),
                }
            except Exception as exc:
                last_error = str(exc)
                time.sleep(attempt * 1.5)
        return {
            "sequence": index,
            "product_id": product_id,
            "encrypted_product_id": product.get("product_id"),
            "model": model,
            "title": product.get("subject"),
            "error": last_error,
        }

    rows = []
    product_ids = sorted(details, key=int)
    if args.only:
        wanted = {str(value) for value in args.only}
        product_ids = [product_id for product_id in product_ids if product_id in wanted]
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            pool.submit(scan_one, index, product_id): product_id
            for index, product_id in enumerate(product_ids, 1)
        }
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            print(f"[{len(rows):03d}/{len(product_ids):03d}] {row['product_id']} {row['model']}", flush=True)
    rows.sort(key=lambda row: row["sequence"])

    low = [row for row in rows if float(row.get("final_score") or 0) < 5.0]
    payload = {
        "product_count": len(rows),
        "low_score_count": len(low),
        "score_distribution": {
            score: sum(1 for row in rows if row.get("final_score") == score)
            for score in sorted({str(row.get("final_score")) for row in rows if row.get("final_score")})
        },
        "low_score_products": low,
        "products": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["score_distribution"], ensure_ascii=False))
    print(args.output)


if __name__ == "__main__":
    main()
