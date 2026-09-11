from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
PACK_ROOT = ROOT / "01_产品资产/01_原始数据包/热榜OEM概念款_2026-09-05"
MATRIX = PACK_ROOT / "00_扩品差异化矩阵.csv"
META = PACK_ROOT / "00_扩品样式元数据.json"
FIELDS = ["ListingID", "Model", "Intent", "LeadColor", "MainImageLocal", "Title", "Keywords", "ProductHighlights", "DetailEmphasis"]


def highlights(intent: str, product_sentence: str) -> str:
    if intent == "Wholesale Importer":
        lead = "Factory-direct OEM/ODM supply with competitive order-based pricing. "
        tail = " Quality checks cover appearance workmanship sizes and quantity before shipment."
    elif intent == "Private Label":
        lead = "Private-label development supports logo color insole label and packaging discussions from 2 pairs. "
        tail = " Customized timing depends on materials quantity and requirements."
    else:
        lead = "Factory-direct wholesale supply combines competitive quotations with OEM/ODM color logo insole label and packaging support. "
        tail = " Production and dispatch are arranged promptly after specifications are confirmed."
    return lead + product_sentence.strip() + tail


def write_package(spec: dict) -> None:
    model = spec["model"]
    folder = PACK_ROOT / spec["folder"]
    folder.mkdir(parents=True, exist_ok=True)
    colors = spec["colors"]
    manifest = {
        "model": model,
        "product_root": folder.as_posix(),
        "grid_cols": 2,
        "grid_rows": 3,
        "role_cells": {"hero": [0, 0], "lateral": [1, 0], "outsole": [0, 1], "upper": [1, 1], "lifestyle": [0, 2], "heel": [1, 2]},
        "colors": [],
    }
    for idx, color in enumerate(colors):
        item = {
            "name": color["name"], "slug": color["slug"],
            "sheet": spec["color_sheet"], "grid_cols": 3, "grid_rows": 1, "cell": [idx, 0],
        }
        if idx == 0:
            item["main_sheet"] = spec["main_sheet"]
        manifest["colors"].append(item)
    (folder / "package_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    detail = {
        "model": model, "product_root": folder.as_posix(),
        "overview_bg": f"05_AI候选/{model}_overview_bg_v1.png",
        "overview_title": spec["overview_title"], "overview_subtitle": spec["overview_subtitle"],
        "structure_image": f"01_主图/{model}_main_02_lateral.png",
        "structure_items": spec["structure_items"],
        "colors": [{"name": c["name"], "image": f"03_颜色图/{model}_color_{c['slug']}.png"} for c in colors],
        "size_range": "EU 36-45", "oem_bg": f"05_AI候选/{model}_oem_bg_v1.png",
        "moq": "2 PAIRS", "lead_time": "PRODUCTION TIMING CONFIRMED BY ORDER",
        "package": "34 × 23 × 13 CM  /  0.5 KG  /  1 PAIR",
    }
    (folder / "detail_config.json").write_text(json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8")
    doc = f"# {model} {spec['name_cn']}\n\n{spec['identity']}\n\n- EU 36–45；{spec['color_cn']}。可讨论标志、配色、鞋垫、标签和包装。\n- MOQ 2 双；34 × 23 × 13 cm，0.5 kg，1 双。定制交期按材料、数量和要求确认。\n- 验收：六图结构一致；颜色图完整无字；四张详情信息互补；五张公司图、30 SKU、图片银行、质量分和公开页通过。\n"
    (folder / "商品资料与验收.md").write_text(doc, encoding="utf-8")


def update_meta(specs: list[dict]) -> None:
    data = json.loads(META.read_text(encoding="utf-8-sig")) if META.is_file() else {}
    for spec in specs:
        data[spec["model"]] = spec["style_meta"]
    META.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def update_matrix(specs: list[dict]) -> None:
    with MATRIX.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    positions = {row["ListingID"]: index for index, row in enumerate(rows)}
    for spec in specs:
        for row in spec["listings"]:
            listing_id = f"{spec['model']}-{row['variant']}"
            color = spec["colors"]["ABC".index(row["variant"])]
            matrix_row = {
                "ListingID": listing_id, "Model": spec["model"], "Intent": row["intent"],
                "LeadColor": color["name"],
                "MainImageLocal": f"{spec['folder']}/03_颜色图/{spec['model']}_color_{color['slug']}.png",
                "Title": row["title"], "Keywords": re.sub(r"[,.:;]+", " ", row["keywords"]),
                "ProductHighlights": highlights(row["intent"], row["product_sentence"]),
                "DetailEmphasis": row["differentiation"],
            }
            if listing_id in positions:
                rows[positions[listing_id]] = matrix_row
            else:
                positions[listing_id] = len(rows)
                rows.append(matrix_row)
    temp_matrix = MATRIX.with_suffix(".csv.tmp")
    with temp_matrix.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader(); writer.writerows(rows)
    temp_matrix.replace(MATRIX)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("spec")
    args = parser.parse_args()
    data = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    specs = data if isinstance(data, list) else [data]
    for spec in specs:
        write_package(spec)
    update_meta(specs)
    update_matrix(specs)
    print(json.dumps({"created": [s["model"] for s in specs]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
