"""将商品行写入国际站官方 Excel 模板，同时保留模板内部结构。

rows.json 是 JSON 数组；每个元素以 Excel 列名为键，例如：
[{"E": "Product title", "F": "https://sc04...jpg", "CE": "Black", "CG": 39}]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from validate_alibaba_batch import validate_rows


SHEET_XML = "xl/worksheets/sheet1.xml"
FIRST_DATA_ROW = 3
DEFAULT_STYLE = 122


def column_number(column: str) -> int:
    value = 0
    for char in column.upper():
        if not "A" <= char <= "Z":
            raise ValueError(f"Invalid Excel column: {column}")
        value = value * 26 + ord(char) - 64
    return value


def cell_xml(row: int, column: str, value: object) -> str:
    ref = f"{column.upper()}{row}"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{ref}" s="{DEFAULT_STYLE}"><v>{value}</v></c>'
    text = escape(str(value))
    return f'<c r="{ref}" s="{DEFAULT_STYLE}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


def row_xml(row_number: int, values: dict[str, object]) -> str:
    populated = [(column, value) for column, value in values.items() if value not in (None, "")]
    populated.sort(key=lambda pair: column_number(pair[0]))
    cells = "".join(cell_xml(row_number, column, value) for column, value in populated)
    return f'<row r="{row_number}">{cells}</row>'


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(template: Path, rows_path: Path, output: Path) -> None:
    rows = json.loads(rows_path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) for row in rows):
        raise ValueError("rows.json must be a non-empty JSON array of objects")
    validation = validate_rows(rows)
    if not validation["ok"]:
        details = "\n- ".join(validation["errors"][:30])
        raise ValueError(f"Alibaba batch preflight failed:\n- {details}")

    with zipfile.ZipFile(template, "r") as source_zip:
        infos = source_zip.infolist()
        original = {info.filename: source_zip.read(info.filename) for info in infos}
    if SHEET_XML not in original:
        raise ValueError(f"Official template is missing {SHEET_XML}")

    sheet = original[SHEET_XML].decode("utf-8")
    if sheet.count("</sheetData>") != 1:
        raise ValueError("Unexpected official template sheetData structure")
    last_row = FIRST_DATA_ROW + len(rows) - 1
    sheet, changed = re.subn(
        r'<dimension ref="[^"]+"/>', f'<dimension ref="A1:DG{last_row}"/>', sheet, count=1
    )
    if changed != 1:
        raise ValueError("Could not update official template dimension")
    data = "".join(row_xml(FIRST_DATA_ROW + index, row) for index, row in enumerate(rows))
    updated_sheet = sheet.replace("</sheetData>", data + "</sheetData>", 1).encode("utf-8")

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w") as output_zip:
        for info in infos:
            output_zip.writestr(info, updated_sheet if info.filename == SHEET_XML else original[info.filename])

    with zipfile.ZipFile(output, "r") as check_zip:
        check_infos = check_zip.infolist()
        check = {info.filename: check_zip.read(info.filename) for info in check_infos}
    if [info.filename for info in check_infos] != [info.filename for info in infos]:
        raise RuntimeError("ZIP member names/order changed")
    for name, blob in original.items():
        if name != SHEET_XML and sha256(check[name]) != sha256(blob):
            raise RuntimeError(f"Official template component changed: {name}")
    if check[SHEET_XML].decode("utf-8").count('<row r="') != FIRST_DATA_ROW - 1 + len(rows):
        raise RuntimeError("Written row count does not match manifest")
    print(json.dumps({
        "output": str(output),
        "products": validation["products"],
        "rows": len(rows),
        "preserved_parts": len(infos) - 1,
        "preflight": "passed",
    }, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--rows", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.template, args.rows, args.output)


if __name__ == "__main__":
    main()
