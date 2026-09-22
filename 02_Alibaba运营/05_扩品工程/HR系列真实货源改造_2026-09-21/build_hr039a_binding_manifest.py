from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\Users\spq\Desktop\贝强")
PROJECT = ROOT / r"02_Alibaba运营\05_扩品工程\HR系列真实货源改造_2026-09-21"
ORIGINAL = PROJECT / "HR039-A_8025_图片银行上传回执.json"
REPLACEMENTS = PROJECT / "HR039-A_8025_去重替换图上传回执.json"
OUTPUT_JSON = PROJECT / "HR039-A_8025_最终图片绑定清单.json"
OUTPUT_MD = PROJECT / "HR039-A_8025_最终图片绑定清单.md"


def normalize(receipt: dict) -> dict:
    response = receipt["response"]
    upload = response["upload_image_response"]
    url = upload["photobank_url"]
    if url.startswith("//"):
        url = "https:" + url
    return {
        "role": receipt["role"],
        "local_path": receipt["local_path"],
        "sha256": receipt["sha256"],
        "file_id": str(upload["file_id"]),
        "url": url,
        "request_id": response.get("request_id"),
        "trace_id": response.get("trace_id") or response.get("_trace_id_"),
    }


original = json.loads(ORIGINAL.read_text(encoding="utf-8"))
replacements = json.loads(REPLACEMENTS.read_text(encoding="utf-8"))
by_role = {row["role"]: normalize(row) for row in original["receipts"]}
by_role.update({row["role"]: normalize(row) for row in replacements["receipts"]})

roles = [
    "M1_8025_wholesale",
    "M2_8025_colors_sizes",
    "M3_8025_construction",
    "M4_8025_oem_inputs",
    "M5_factory_quality",
    "M6_packing_quote_inputs",
    "D1_product_overview",
    "D2_verified_specs",
    "D3_colors_sizes",
    "D4_price_quote",
    "D5_oem_project_inputs",
    "C1_real_factory_identity",
    "C2_custom_project_flow",
    "C3_real_production_organization",
    "C4_real_quality_checkpoints",
    "C5_packing_order_handoff",
]
missing = [role for role in roles if role not in by_role]
if missing:
    raise SystemExit(f"Missing roles: {missing}")

items = [by_role[role] for role in roles]
for item in items:
    path = Path(item["local_path"])
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != item["sha256"]:
        raise SystemExit(f"Local/upload hash mismatch: {item['role']}")

hashes = [item["sha256"] for item in items]
if len(hashes) != len(set(hashes)):
    raise SystemExit("Final binding contains exact duplicate files")

payload = {
    "created_at": datetime.now().astimezone().isoformat(),
    "product_id": 1601943650395,
    "product": "HR039-A / 8025",
    "source_url": "https://bqgcd.sooxie.com/detail/2049703",
    "source_article": "8025",
    "source_price_cny": 58,
    "image_counts": {"main": 6, "product_detail": 5, "company": 5},
    "exact_hash_unique": True,
    "items": items,
}
OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

lines = [
    "# HR039-A / 8025 最终图片绑定清单",
    "",
    f"- 生成时间：{payload['created_at']}",
    "- 商品 ID：1601943650395",
    "- 货源：贝强工厂店 / 款号 8025 / CNY 58",
    "- 货源链接：https://bqgcd.sooxie.com/detail/2049703",
    "- 结构：6 张主图 + 5 张产品详情图 + 5 张公司能力图",
    "- 校验：16 张文件哈希全部唯一；3 张重做图已使用新上传版本",
    "",
    "| 角色 | 图片银行 ID | 本地文件 | 图片银行链接 |",
    "| --- | ---: | --- | --- |",
]
for item in items:
    lines.append(
        f"| {item['role']} | {item['file_id']} | `{Path(item['local_path']).name}` | {item['url']} |"
    )
OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(OUTPUT_JSON)
print(OUTPUT_MD)

