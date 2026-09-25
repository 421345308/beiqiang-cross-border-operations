"""Read-only Alibaba quality-score check for HR023 A/B/C."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG = Path.home() / ".config/beiqiang/alibaba-openapi.json"
PRODUCTS = {
    "HR023-A": 1601943614240,
    "HR023-B": 1601943629102,
    "HR023-C": 1601943547591,
}


def main() -> None:
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
    assert spec and spec.loader
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    config = api.load_config(CONFIG)
    receipt = {"mode": "read-only", "checked_at_utc": datetime.now(timezone.utc).isoformat(), "products": {}}
    for listing, product_id in PRODUCTS.items():
        response = api.top_call(config, "alibaba.icbu.product.score.get", {"product_id": product_id})
        error = api.api_error(response)
        if error:
            raise RuntimeError(f"{listing} score.get: {error}")
        problem = json.loads((response.get("result") or {}).get("problem_map") or "{}")
        receipt["products"][listing] = {
            "product_id": product_id,
            "request_id": response.get("request_id"),
            "trace_id": response.get("trace_id") or response.get("_trace_id_"),
            "final_score": (response.get("result") or {}).get("final_score"),
            "extend_problem_map": problem.get("extendProblemMap"),
            "error_reason_list": problem.get("errorReasonList"),
        }
    output = Path(__file__).with_name("HR023_质量分_只读回执.json")
    output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=True))


if __name__ == "__main__":
    main()
