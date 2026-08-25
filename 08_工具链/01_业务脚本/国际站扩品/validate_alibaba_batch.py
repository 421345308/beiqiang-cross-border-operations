"""国际站批量发品 rows.json / 官方模板输出硬校验。

默认规则对应贝强慢走休闲鞋当前确认基线。任何一项失败都返回非零退出码，
禁止继续上传。SKU 特定事实若覆盖基线，应先更新配置正本和本校验参数。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET


SHEET_XML = "xl/worksheets/sheet1.xml"
FIRST_DATA_ROW = 3
MAIN_IMAGE_COLUMNS = ("F", "G", "H", "I", "J", "K")
DETAIL_IMAGE_COLUMNS = ("O", "P", "Q", "R")
COMPANY_IMAGE_COLUMNS = ("T", "V", "W", "X", "Z")
IMAGE_COLUMNS = MAIN_IMAGE_COLUMNS + DETAIL_IMAGE_COLUMNS + COMPANY_IMAGE_COLUMNS + ("CF",)
SKU_COLUMNS = {"CE", "CF", "CG", "CH", "CI", "CJ"}
EXPECTED_LADDER = {"CM": 2, "CN": 9.49, "CO": 50, "CP": 9.19, "CQ": 100, "CR": 9.09}
EXPECTED_LOGISTICS = {
    "CK": 2,
    "CL": "Pair/Pairs",
    "CV": 34,
    "CW": 23,
    "CX": 13,
    "CY": 0.5,
    "CZ": "智能运费模板",
    "DA": "Ordinary goods",
    "DB": 100,
    "DC": 31,
}
FORBIDDEN_PATTERNS = (
    "sc01.alicdn.com",
    "skill.accio.com",
    "file://",
    "wide toe box",
    "orthopedic",
    "medical",
)


def _number_equal(actual: object, expected: object) -> bool:
    if isinstance(expected, (int, float)):
        try:
            return abs(float(actual) - float(expected)) < 1e-9
        except (TypeError, ValueError):
            return False
    return actual == expected


def validate_rows(rows: list[dict[str, object]]) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    if not rows or not all(isinstance(row, dict) for row in rows):
        return {"ok": False, "errors": ["rows.json 必须是非空对象数组"], "warnings": []}

    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    seen_skus: set[str] = set()
    seen_titles: dict[str, str] = {}

    serialized = json.dumps(rows, ensure_ascii=False).lower()
    for token in FORBIDDEN_PATTERNS:
        if token in serialized:
            errors.append(f"发现禁用内容：{token}")
    if re.search(r"[a-z]:\\", serialized):
        errors.append("发现本地 Windows 路径")

    for index, row in enumerate(rows, start=FIRST_DATA_ROW):
        model = str(row.get("AU", "")).strip()
        title = str(row.get("E", "")).strip()
        sku = str(row.get("CJ", "")).strip()
        if not model:
            errors.append(f"第 {index} 行缺少型号 AU")
            continue
        groups[model].append(row)
        if not title:
            errors.append(f"{model} 第 {index} 行缺少标题 E")
        if not sku:
            errors.append(f"{model} 第 {index} 行缺少 SKU 编码 CJ")
        elif sku in seen_skus:
            errors.append(f"SKU 编码重复：{sku}")
        else:
            seen_skus.add(sku)
        if title in seen_titles and seen_titles[title] != model:
            errors.append(f"不同型号使用相同标题：{seen_titles[title]} / {model}")
        elif title:
            seen_titles[title] = model

        if row.get("CI") not in (None, ""):
            errors.append(f"{model} / {sku}：CI SKU 单价必须留空")
        for column, expected in {**EXPECTED_LADDER, **EXPECTED_LOGISTICS}.items():
            if not _number_equal(row.get(column), expected):
                errors.append(f"{model} / {sku}：{column} 应为 {expected!r}，实际为 {row.get(column)!r}")
        for column in ("DD", "DE", "DF", "DG"):
            if row.get(column) not in (None, ""):
                errors.append(f"{model} / {sku}：交期附加列 {column} 必须留空，只允许 DB/DC=100/31")
        for column in IMAGE_COLUMNS:
            value = str(row.get(column, "")).strip()
            if not value.startswith("https://sc04.alicdn.com/"):
                errors.append(f"{model} / {sku}：图片列 {column} 不是正式 sc04 CDN 地址")

    for model, product_rows in groups.items():
        first = product_rows[0]
        invariant = {key: value for key, value in first.items() if key not in SKU_COLUMNS}
        for row in product_rows[1:]:
            current = {key: value for key, value in row.items() if key not in SKU_COLUMNS}
            if current != invariant:
                errors.append(f"{model}：同款不同 SKU 的产品级字段不一致")
                break

        main = [str(first.get(column, "")) for column in MAIN_IMAGE_COLUMNS]
        detail = [str(first.get(column, "")) for column in DETAIL_IMAGE_COLUMNS]
        company = [str(first.get(column, "")) for column in COMPANY_IMAGE_COLUMNS]
        if len(set(main)) != 6:
            errors.append(f"{model}：6 张主图存在缺失或重复 URL")
        if len(set(detail)) != 4:
            errors.append(f"{model}：4 张产品详情图存在缺失或重复 URL")
        if len(set(company)) != 5:
            errors.append(f"{model}：5 张公司图存在缺失或重复 URL")

        color_to_image: dict[str, set[str]] = defaultdict(set)
        combinations: set[tuple[str, str]] = set()
        for row in product_rows:
            color = str(row.get("CE", "")).strip()
            image = str(row.get("CF", "")).strip()
            size = str(row.get("CG", "")).strip()
            color_to_image[color].add(image)
            pair = (color, size)
            if pair in combinations:
                errors.append(f"{model}：颜色尺码组合重复：{color} / {size}")
            combinations.add(pair)
            if image in main or image in detail:
                errors.append(f"{model} / {color}：颜色图复用了主图或详情图 URL")
        for color, images in color_to_image.items():
            if not color:
                errors.append(f"{model}：存在空颜色名")
            if len(images) != 1:
                errors.append(f"{model} / {color}：同一颜色绑定了多个颜色图")

    return {
        "ok": not errors,
        "products": len(groups),
        "rows": len(rows),
        "skus": len(seen_skus),
        "errors": errors,
        "warnings": warnings,
    }


def _xlsx_summary(path: Path) -> tuple[int, list[str]]:
    with zipfile.ZipFile(path, "r") as archive:
        root = ET.fromstring(archive.read(SHEET_XML))
    namespace = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    data_rows = [
        row
        for row in root.findall(".//m:sheetData/m:row", namespace)
        if int(row.attrib["r"]) >= FIRST_DATA_ROW
    ]
    units: list[str] = []
    for row in data_rows:
        unit_cell = next(
            (cell for cell in row.findall("m:c", namespace) if cell.attrib.get("r", "").startswith("CL")),
            None,
        )
        if unit_cell is None:
            units.append("")
            continue
        units.append("".join(text.text or "" for text in unit_cell.findall(".//m:t", namespace)))
    return len(data_rows), units


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=Path, required=True)
    parser.add_argument("--xlsx", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    rows = json.loads(args.rows.read_text(encoding="utf-8"))
    result = validate_rows(rows)
    if args.xlsx:
        result["xlsx"] = str(args.xlsx)
        try:
            written_rows, written_units = _xlsx_summary(args.xlsx)
            result["xlsx_data_rows"] = written_rows
            if written_rows != len(rows):
                result["ok"] = False
                result["errors"].append(f"Excel 数据行数 {written_rows} 与 rows.json {len(rows)} 不一致")
            expected_units = [str(row.get("CL", "")) for row in rows]
            if written_units != expected_units:
                result["ok"] = False
                mismatch = next(
                    (
                        index
                        for index, (actual, expected) in enumerate(zip(written_units, expected_units), FIRST_DATA_ROW)
                        if actual != expected
                    ),
                    FIRST_DATA_ROW + min(len(written_units), len(expected_units)),
                )
                result["errors"].append(
                    f"Excel CL 计量单位与 rows.json 不一致，首个差异位于第 {mismatch} 行"
                )
        except Exception as exc:  # noqa: BLE001 - report exact workbook failure
            result["ok"] = False
            result["errors"].append(f"Excel 结构读取失败：{exc}")

    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    if not result["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
