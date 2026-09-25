"""Bind the verified generic factory video to HR001-A with capacity gates."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
OUT = ROOT / r"02_Alibaba运营\05_扩品工程\HR系列真实货源改造_2026-09-21\HR001-A_工厂主视频绑定回执.json"
PRODUCT_ID = 1601943321794
VIDEO_ID = "6000342456358"
TARGET_MODEL = "HR001-A / 9002"


def load_client():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def refs(api, response):
    return {
        "request_id": response.get("request_id"),
        "trace_id": response.get("trace_id") or response.get("_trace_id_"),
        "error": api.api_error(response),
        "biz_success": response.get("biz_success"),
    }


def relation_ids(response):
    return [str(row.get("product_id") or "") for row in ((response.get("result") or {}).get("model") or [])]


api = load_client()
config = api.load_config(Path.home() / ".config/beiqiang/alibaba-openapi.json")
product_response = api.top_call(config, "alibaba.icbu.product.get", {"product_id": PRODUCT_ID, "language": "ENGLISH"})
product = product_response.get("product") or {}
attrs = {str(row.get("attribute_name")): row.get("value_name") for row in product.get("attributes") or []}
encrypted_id = str(product.get("product_id") or "")

before_response = api.top_call(
    config,
    "alibaba.icbu.video.relation.product.list",
    {"type": "videoId", "video_id": VIDEO_ID},
)
before_ids = relation_ids(before_response)
gates = {
    "product_approved_online": product.get("status") == "approved" and product.get("display") == "Y",
    "model_ok": attrs.get("Model Number") == TARGET_MODEL,
    "encrypted_id_available": bool(encrypted_id),
    "not_already_bound": encrypted_id not in before_ids,
    "capacity_available": len(before_ids) < 20,
}
if api.api_error(product_response) or api.api_error(before_response) or not all(gates.values()):
    raise RuntimeError(f"preflight failed: {gates}; product={refs(api, product_response)} relation={refs(api, before_response)}")

bind_response = api.top_call(
    config,
    "alibaba.icbu.video.relation.product.main",
    {"product_id": PRODUCT_ID, "video_id": VIDEO_ID},
)
if api.api_error(bind_response) or bind_response.get("biz_success") is False or bind_response.get("model") is False:
    raise RuntimeError(f"video bind failed: {refs(api, bind_response)}")

after_response = api.top_call(
    config,
    "alibaba.icbu.video.relation.product.list",
    {"type": "videoId", "video_id": VIDEO_ID},
)
after_ids = relation_ids(after_response)
receipt = {
    "product_id": PRODUCT_ID,
    "encrypted_product_id": encrypted_id,
    "video_id": VIDEO_ID,
    "gates": gates,
    "before_relation_count": len(before_ids),
    "after_relation_count": len(after_ids),
    "product_refs": refs(api, product_response),
    "before_relation_refs": refs(api, before_response),
    "bind_refs": refs(api, bind_response),
    "after_relation_refs": refs(api, after_response),
    "verified": encrypted_id in after_ids and len(after_ids) == len(before_ids) + 1 and len(after_ids) <= 20,
}
OUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(receipt, ensure_ascii=False, indent=2))
if not receipt["verified"]:
    raise RuntimeError("video binding did not verify through reverse relation list")
