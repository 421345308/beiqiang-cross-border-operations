"""Fetch HR001-HR008 quality scores concurrently and persist the evidence."""
from __future__ import annotations

import argparse
import importlib.util
import json
import time
from pathlib import Path

ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG = Path.home() / ".config/beiqiang/alibaba-openapi.json"
OUTPUT_DIR = ROOT / "02_Alibaba运营/05_扩品工程/热榜8款API上架_2026-09-05"
PRODUCTS = {
    "HR001": 1601943321794, "HR002": 1601943305914,
    "HR003": 1601943312845, "HR004": 1601943397351,
    "HR005": 1601943335751, "HR006": 1601943439124,
    "HR007": 1601943463020, "HR008": 1601943348656,
}


def products_for_variant(variant: str) -> dict[str, int]:
    if variant == "A":
        return {f"{model}-A": product_id for model, product_id in PRODUCTS.items()}
    receipt = json.loads((OUTPUT_DIR / f"publish_{variant}_receipt.json").read_text(encoding="utf-8"))
    return {row["listing_id"]: int(row["submit"]["product_id"]) for row in receipt["products"]}


def load_client():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=["A", "B", "C"], default="A")
    args = parser.parse_args()
    api = load_client()
    config = api.load_config(CONFIG)

    def fetch(item):
        model, product_id = item
        response = None
        for attempt in range(1, 6):
            response = api.top_call(config, "alibaba.icbu.product.score.get", {"product_id": product_id})
            error = response.get("error_response") or {}
            if not error:
                break
            if error.get("code") not in {"ApiCallLimit", "15"}:
                break
            time.sleep(1.5 * attempt)
        result = response.get("result") or {}
        problem = json.loads(result.get("problem_map") or "{}") if result else {}
        return model, {
            "product_id": str(product_id),
            "score": result.get("final_score"),
            "problems": problem.get("extendProblemMap") or {},
            "response": response,
        }

    data = {}
    for item in products_for_variant(args.variant).items():
        model, row = fetch(item)
        data[model] = row
        print(model, row["score"], flush=True)
        time.sleep(1.2)
    payload = {"all_5_0": all(row.get("score") == "5.00" for row in data.values()),
               "products": {key: data[key] for key in sorted(data)}}
    OUT = OUTPUT_DIR / f"质量分回读_{args.variant}.json"
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
