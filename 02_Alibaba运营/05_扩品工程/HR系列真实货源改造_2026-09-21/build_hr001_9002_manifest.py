from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
PROJECT = ROOT / r"02_Alibaba运营\05_扩品工程\HR系列真实货源改造_2026-09-21"
UPLOAD = PROJECT / "HR001_9002_图片银行上传回执.json"
COMPANY = PROJECT / "HR039-A_8025_最终图片绑定清单.json"
OUT_JSON = PROJECT / "HR001_9002_最终图片绑定清单.json"
OUT_MD = PROJECT / "HR001_9002_最终图片绑定清单.md"

upload = json.loads(UPLOAD.read_text(encoding="utf-8-sig"))
company_manifest = json.loads(COMPANY.read_text(encoding="utf-8-sig"))
items = []
for row in upload["receipts"]:
    result = row["response"]["upload_image_response"]
    items.append({
        "role": row["role"],
        "local_path": row["local_path"],
        "sha256": row["sha256"],
        "file_id": str(result["file_id"]),
        "url": "https:" + result["photobank_url"] if result["photobank_url"].startswith("//") else result["photobank_url"],
        "request_id": row["response"].get("request_id"),
        "trace_id": row["response"].get("trace_id") or row["response"].get("_trace_id_"),
    })

company_items = [row for row in company_manifest["items"] if row["role"].startswith("C")]
items.extend(company_items)

payload = {
    "product_family": "HR001",
    "source_model": "9002",
    "source_url": "https://bqgcd.sooxie.com/detail/2536154",
    "source_price_cny": 55.0,
    "source_checked_at": "2026-09-22",
    "source_facts": {
        "target": "Men",
        "upper": "Textile",
        "outsole": "EVA",
        "closure": "Slip-On / No Laces",
        "season": "Autumn 2026",
        "colors": ["Light Gray / Beige Sole", "Dark Gray / Black Sole"],
        "eur_sizes": list(range(38, 48)),
        "supplier_page_original_claim": True,
        "supplier_inventory_claim": False,
    },
    "pricing": {
        "usd_cny_reference": 6.7487,
        "minimum_130pct_cny": 71.5,
        "minimum_130pct_usd": 10.5946,
        "planned_tiers_usd": [[2, 11.9], [50, 11.5], [100, 10.9]],
        "planned_low_price_cny": 73.56083,
        "planned_low_markup_ratio": 1.3374696,
        "freight": "quoted separately",
    },
    "planned_titles": {
        "HR001-A": "Wholesale Men's Knit Slip-On Walking Shoes EVA Sole EU 38-47 Model 9002 for Importers",
        "HR001-B": "Men's Big Size Knit Slip-On Walking Shoes EU 38-47 Casual OEM Model 9002",
        "HR001-C": "Private Label Men's Textile Slip-On Walking Shoes EVA Outsole EU 38-47 Wholesale Model 9002",
    },
    "demand_evidence": [
        {
            "observed_at": "2026-09-22",
            "url": "https://www.alibaba.com/product-detail/big-size-40-47-light-weight_1601224450912.html",
            "observation": "Public Alibaba listing uses big-size 40-47, breathable mesh, slip-on and walking-shoe intent.",
            "boundary": "Demand direction only; competitor materials, claims, prices and service promises are not copied.",
        },
        {
            "observed_at": "2026-09-22",
            "url": "https://www.alibaba.com/wholesale/slip-running-shoes-men.html",
            "observation": "Public wholesale results include men's knit slip-on thick-sole walking/running-shoe demand.",
            "boundary": "Keyword/demand signal only.",
        },
    ],
    "role_order": {
        "main": [
            "M1_9002_b2b",
            "M2_9002_colors_sizes",
            "M3_9002_construction",
            "M4_9002_oem_inputs",
            "M5_factory_quality",
            "M6_packing_quote",
        ],
        "detail": [
            "D1_product_overview",
            "D2_verified_specs",
            "D3_colors_sizes",
            "D4_price_quote",
            "D5_oem_project_inputs",
        ],
        "sku": ["SKU_9002_light", "SKU_9002_dark"],
        "company": [
            "C1_real_factory_identity",
            "C2_custom_project_flow",
            "C3_real_production_organization",
            "C4_real_quality_checkpoints",
            "C5_packing_order_handoff",
        ],
    },
    "items": items,
}
OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

by_role = {row["role"]: row for row in items}
lines = [
    "# HR001 / 9002 最终图片绑定清单",
    "",
    "- 真实货源：[搜鞋网·贝强工厂店 9002](https://bqgcd.sooxie.com/detail/2536154)",
    "- 页面价：CNY 55/双；130% 底线 CNY 71.50，折合 USD 10.5946（按 6.7487）。",
    "- 计划最低档：USD 10.90，折合约 CNY 73.56，较货源价高约 33.75%。",
    "- 真实选项：浅灰/杏底、深灰/黑底；EU 38–47；男款；纺织鞋面；EVA 鞋底；不系带套脚。",
    "- 不承诺搜鞋网页面的实时库存或固定交期，接单前复核。",
    "",
    "## 图片银行绑定",
    "",
    "| 角色 | fileId | URL |",
    "| --- | ---: | --- |",
]
for role in (
    payload["role_order"]["main"]
    + payload["role_order"]["detail"]
    + payload["role_order"]["sku"]
    + payload["role_order"]["company"]
):
    row = by_role[role]
    lines.append(f"| {role} | `{row['file_id']}` | {row['url']} |")

lines.extend([
    "",
    "## A/B/C 标题分工",
    "",
    "- A：`Wholesale Men's Knit Slip-On Walking Shoes EVA Sole EU 38-47 Model 9002 for Importers`",
    "- B：`Men's Big Size Knit Slip-On Walking Shoes EU 38-47 Casual OEM Model 9002`",
    "- C：`Private Label Men's Textile Slip-On Walking Shoes EVA Outsole EU 38-47 Wholesale Model 9002`",
    "",
    "A/B/C 共用同一 9002 产品事实和 SKU；只分化搜索意图与首图构图，不换鞋。",
])
OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(json.dumps({"json": str(OUT_JSON), "markdown": str(OUT_MD), "items": len(items)}, ensure_ascii=True))
