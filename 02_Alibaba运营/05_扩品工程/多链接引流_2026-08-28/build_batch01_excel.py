from __future__ import annotations

import hashlib
import json
import re
import shutil
import zipfile
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET


NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
ET.register_namespace("", NS)

ROOT = Path(__file__).resolve().parents[3]
RUN_ROOT = Path(__file__).resolve().parent / "全量三链接_2026-08-28"
MAPPING_PATH = RUN_ROOT / "待上传图片" / "批次01_BQ001-BQ005" / "图片银行正式地址.json"
PLAN_PATH = RUN_ROOT / "159条链接总控计划.json"
TEMPLATE_PATH = ROOT / "outputs" / "20260828_alibaba_multilink_pilot" / "latest_template.xlsx"
OUTPUT_DIR = ROOT / "outputs" / "20260829_bq001_bq005_batch01"
OUTPUT_PATH = OUTPUT_DIR / "批次01_BQ001-BQ005_15条链接_国际站批量发品_2026-08-29.xlsx"
REPORT_PATH = OUTPUT_DIR / "批次01_硬校验报告_2026-08-29.json"

MAIN_COLUMNS = ["F", "G", "H", "I", "J", "K"]
DETAIL_COLUMNS = ["O", "P", "Q", "R"]
FAQ_COLUMN_PAIRS = [
    ("AC", "AD"), ("AE", "AF"), ("AG", "AH"), ("AI", "AJ"),
    ("AK", "AL"), ("AM", "AN"), ("AO", "AP"), ("AQ", "AR"),
]

FAQS = [
    ("Are you a factory or a trading company?", "We are a footwear factory supplier located in Quanzhou, Fujian, China, serving overseas B2B buyers."),
    ("What is your minimum order quantity?", "The current store baseline starts from 2 pairs. Final quantity and production arrangement are confirmed according to the selected style and order requirements."),
    ("Can I mix colors and sizes in one order?", "Mixed colors and sizes can be discussed, subject to current availability, size ratio and production confirmation."),
    ("Can I order samples before a bulk order?", "Samples can be arranged for quality checking. Sample price, courier charge and preparation time are quoted separately before payment."),
    ("What is the standard packing for one pair?", "The current single-pair package baseline is 34 x 23 x 13 cm and approximately 0.5 kg. Order-specific packing is confirmed before shipment."),
    ("Do you support OEM and ODM customization?", "Logo, color, size ratio and packaging requirements can be discussed. Please provide your design and target quantity for production review."),
    ("What is the lead time?", "We respond quickly and arrange production or dispatch as soon as the order details are confirmed. For customized orders, exact timing depends on materials, quantity and requirements and is confirmed before order."),
    ("Can you provide a shipping quotation?", "Yes. Please provide the destination country, postal code, quantity and preferred trade term. Freight is confirmed separately for the current order."),
]

COMPANY_IMAGES = [
    "https://sc04.alicdn.com/kf/Sf587c854711748af9759e77ce5aeb03c3/286385890/Sf587c854711748af9759e77ce5aeb03c3.png",
    "https://sc04.alicdn.com/kf/Sfea34bbd56ae4d0583aa855838eb1454F/286385890/Sfea34bbd56ae4d0583aa855838eb1454F.png",
    "https://sc04.alicdn.com/kf/S2a3af5690d524680824086ad8419dbc9G/286385890/S2a3af5690d524680824086ad8419dbc9G.png",
    "https://sc04.alicdn.com/kf/Sdc4e18f098e142b797df687e8befbfa14/286385890/Sdc4e18f098e142b797df687e8befbfa14.png",
    "https://sc04.alicdn.com/kf/Sc1dc6ec7d435404db6a31c6938a734a0g/286385890/Sc1dc6ec7d435404db6a31c6938a734a0g.png",
]

FACTS = {
    "BQ001": {
        "artno": "BQ001", "sizes": list(range(36, 47)),
        "colors": ["Black White", "All Black", "White"],
        "upper": "Textile", "midsole": "EVA", "outsole": "EVA", "closure": "Slip-on",
        "toe": "Round Toe", "fit": "Wide Toe Box", "features": "Light Weight;Breathable",
        "details": ["bq001d2", "bq001d3", "bq001d4", "bq001d5"],
        "description_core": "Breathable knitted textile slip-on walking shoes with a verified wide toe box, lightweight EVA sole and EU 36-46 size range.",
    },
    "BQ002": {
        "artno": "BQ002", "sizes": list(range(36, 47)),
        "colors": ["Grey White", "Grey Black", "Grey Khaki"],
        "upper": "Textile", "midsole": "EVA", "outsole": "EVA", "closure": "Slip-on",
        "toe": "Round Toe", "fit": "Wide Toe Box", "features": "Light Weight;Breathable",
        "details": ["bq002d2", "bq002d3", "bq002d4", "bq002d5"],
        "description_core": "Lightweight grey knitted textile slip-on walking shoes with a verified wide toe box, EVA sole and EU 36-46 size range.",
    },
    "BQ003": {
        "artno": "R1218", "sizes": list(range(35, 46)),
        "colors": ["White", "Grey", "Pink", "Black White", "All Black"],
        "upper": "Textile", "midsole": "EVA", "outsole": "EVA", "closure": "Lace-up",
        "toe": "Round Toe", "fit": "Regular Fit", "features": "Light Weight;Breathable",
        "details": ["bq003d4", "bq003d1", "bq003d2", "bq003d3"],
        "description_core": "Breathable knitted textile lace-up walking shoes with regular fit, EVA sole and EU 35-45 size range.",
    },
    "BQ004": {
        "artno": "A502", "sizes": list(range(35, 46)),
        "colors": ["Grey Black White Sole", "Light Blue White", "Orange Black White Sole", "Grey Black Black Sole"],
        "upper": "Textile", "midsole": "EVA", "outsole": "EVA", "closure": "Lace-up",
        "toe": "Round Toe", "fit": "Regular Fit", "features": "Light Weight;Breathable",
        "details": ["bq004d2", "bq004d3", "bq004d4", "bq004d6"],
        "description_core": "Lightweight knitted textile lace-up walking shoes with regular fit, EVA sole, four photographed colorways and EU 35-45 size range.",
    },
    "BQ005": {
        "artno": "A503", "sizes": list(range(35, 46)),
        "colors": ["All Black", "Pink White", "Grey White", "White"],
        "upper": "Textile", "midsole": "EVA", "outsole": "EVA", "closure": "Lace-up",
        "toe": "Round Toe", "fit": "Regular Fit", "features": "Light Weight;Breathable",
        "details": ["bq005d2", "bq005d3", "bq005d4", "bq005d5"],
        "description_core": "Breathable summer hollow-knit lace-up walking shoes with regular fit, lightweight EVA sole and EU 35-45 size range.",
    },
}

TITLE_OVERRIDES = {
    "BQ004-W1": "Wholesale Lightweight Knit Lace Up Walking Shoes A502 EVA Sole for Importers and Wholesalers",
    "BQ004-R1": "Factory Direct Breathable Knit Lace Up Casual Walking Shoes A502 for Online Sellers",
    "BQ004-O1": "OEM ODM Private Label Lightweight Knit Walking Shoes A502 Factory Supply for Brand Buyers",
    "BQ005-W1": "Wholesale Summer Hollow Knit Lace Up Walking Shoes A503 EVA Sole for Importers and Wholesalers",
    "BQ005-R1": "Factory Direct Breathable Hollow Knit Casual Walking Shoes A503 for Online Sellers",
    "BQ005-O1": "OEM ODM Private Label Hollow Knit Walking Shoes A503 Factory Supply for Brand Buyers",
}


def column_number(column: str) -> int:
    result = 0
    for char in column:
        result = result * 26 + ord(char) - 64
    return result


def text_cell(column: str, row_number: int, value: str, style: str | None) -> ET.Element:
    attrs = {"r": f"{column}{row_number}", "t": "inlineStr"}
    if style is not None:
        attrs["s"] = style
    cell = ET.Element(f"{{{NS}}}c", attrs)
    inline = ET.SubElement(cell, f"{{{NS}}}is")
    text = ET.SubElement(inline, f"{{{NS}}}t")
    if value != value.strip() or "  " in value:
        text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    text.text = value
    return cell


def number_cell(column: str, row_number: int, value: int | float, style: str | None) -> ET.Element:
    attrs = {"r": f"{column}{row_number}"}
    if style is not None:
        attrs["s"] = style
    cell = ET.Element(f"{{{NS}}}c", attrs)
    ET.SubElement(cell, f"{{{NS}}}v").text = str(value)
    return cell


def slug(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "-", value.upper()).strip("-")


def build_rows() -> list[dict[str, object]]:
    mapping_data = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    mapping = {item["filename"]: item["url"] for item in mapping_data["items"]}
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    selected = [item for item in plan if item["source_bq"] in FACTS]
    rows: list[dict[str, object]] = []
    company_columns = ["T", "V", "W", "X", "Z"]
    focus = {
        "W1": "Prepared for importer and wholesaler sourcing, with photographed colors, verified construction and wholesale ordering support.",
        "R1": "Prepared for online sellers and daily casual walking collections, with visible construction and color selection support.",
        "O1": "Prepared for OEM, ODM and private-label discussion. Logo, color, insole and packaging requirements are reviewed by quantity before production.",
    }

    for item in selected:
        code = item["source_bq"]
        link_code = item["link_code"]
        variant = link_code.rsplit("-", 1)[1].lower()
        facts = FACTS[code]
        title = TITLE_OVERRIDES.get(link_code, item["title"])
        description = f"{facts['description_core']} {focus[variant.upper()]}"
        main = [mapping[f"{code.lower()}{variant}m{index}"] for index in range(1, 7)]
        detail = [mapping[name] for name in facts["details"]]
        colors = facts["colors"]
        color_images = [mapping[f"{code.lower()}c{index}"] for index in range(1, len(colors) + 1)]

        for color, color_image in zip(colors, color_images):
            for size in facts["sizes"]:
                row: dict[str, object] = {
                    "E": title,
                    **dict(zip(MAIN_COLUMNS, main)),
                    **dict(zip(DETAIL_COLUMNS, detail)),
                    "S": description,
                    "AB": "Quanzhou Beiqiang Footwear & Apparel Co., Ltd. supplies OEM/ODM and wholesale casual footwear for importers, wholesalers, sourcing agents and private-label buyers.",
                    "AS": "China",
                    "AU": item["model_number"],
                    "AV": facts["midsole"],
                    "AW": "All Seasons",
                    "AX": "Walking Shoes",
                    "AY": facts["outsole"],
                    "AZ": facts["upper"],
                    "BB": facts["closure"],
                    "BC": facts["toe"],
                    "BF": facts["features"],
                    "BK": "Fit Type",
                    "BL": facts["fit"],
                    "CE": color,
                    "CF": color_image,
                    "CG": size,
                    "CH": 999,
                    "CJ": f"{link_code}-{slug(color)}-{size}",
                    "CK": 2,
                    "CL": "Pair/Pairs",
                    "CM": 2,
                    "CN": 9.49,
                    "CO": 50,
                    "CP": 9.19,
                    "CQ": 100,
                    "CR": 9.09,
                    "CV": 34,
                    "CW": 23,
                    "CX": 13,
                    "CY": 0.5,
                    "CZ": "智能运费模板",
                    "DA": "普货",
                    "DB": 100,
                    "DC": 31,
                }
                row.update(dict(zip(company_columns, COMPANY_IMAGES)))
                for (question_column, answer_column), (question, answer) in zip(FAQ_COLUMN_PAIRS, FAQS):
                    row[question_column] = question
                    row[answer_column] = answer
                rows.append(row)
    return rows


def validate(rows: list[dict[str, object]]) -> dict[str, object]:
    errors: list[str] = []
    models = sorted({str(row["AU"]) for row in rows})
    titles = {model: {str(row["E"]) for row in rows if row["AU"] == model} for model in models}
    sku_codes = [str(row["CJ"]) for row in rows]
    if len(models) != 15:
        errors.append(f"Expected 15 models, found {len(models)}")
    if any(len(values) != 1 for values in titles.values()):
        errors.append("Product-level title inconsistency")
    if len(set(sku_codes)) != len(sku_codes):
        errors.append("Duplicate SKU codes")
    if any(len(next(iter(values))) > 128 for values in titles.values()):
        errors.append("Title exceeds 128 characters")

    for model in models:
        sample = next(row for row in rows if row["AU"] == model)
        main = [str(sample[column]) for column in MAIN_COLUMNS]
        detail = [str(sample[column]) for column in DETAIL_COLUMNS]
        company = [str(sample[column]) for column in ["T", "V", "W", "X", "Z"]]
        color_urls = {str(row["CF"]) for row in rows if row["AU"] == model}
        if len(set(main)) != 6:
            errors.append(f"{model}: main images not 6 unique")
        if len(set(detail)) != 4:
            errors.append(f"{model}: detail images not 4 unique")
        if len(set(company)) != 5:
            errors.append(f"{model}: company images not 5 unique")
        if set(main) & set(detail):
            errors.append(f"{model}: main/detail overlap")
        if color_urls & (set(main) | set(detail)):
            errors.append(f"{model}: color image overlaps main/detail")
        urls = main + detail + company + list(color_urls)
        if any(not url.startswith("https://sc04.alicdn.com/kf/") for url in urls):
            errors.append(f"{model}: non-sc04 image URL")

    for row in rows:
        expected = {
            "CK": 2, "CL": "Pair/Pairs", "CM": 2, "CN": 9.49,
            "CO": 50, "CP": 9.19, "CQ": 100, "CR": 9.09,
            "CV": 34, "CW": 23, "CX": 13, "CY": 0.5,
            "DA": "普货", "DB": 100, "DC": 31,
        }
        for column, value in expected.items():
            if row.get(column) != value:
                errors.append(f"{row['CJ']}: {column} mismatch")
        if row.get("CI") not in (None, ""):
            errors.append(f"{row['CJ']}: CI must be blank")

    report = {
        "status": "PASS" if not errors else "FAIL",
        "products": len(models),
        "rows": len(rows),
        "unique_skus": len(set(sku_codes)),
        "models": models,
        "errors": errors,
    }
    if errors:
        raise SystemExit(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def write_workbook(rows: list[dict[str, object]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(TEMPLATE_PATH, "r") as source_zip:
        original_entries = source_zip.infolist()
        original_parts = {item.filename: source_zip.read(item.filename) for item in original_entries}

    sheet_name = "xl/worksheets/sheet1.xml"
    root = ET.fromstring(original_parts[sheet_name])
    sheet_data = root.find(f"{{{NS}}}sheetData")
    if sheet_data is None:
        raise SystemExit("Template sheetData missing")
    template_rows = list(sheet_data)
    header_rows = [deepcopy(row) for row in template_rows if int(row.attrib.get("r", "0")) <= 2]
    base_row = next((row for row in template_rows if row.attrib.get("r") == "3"), None)
    style_by_column: dict[str, str | None] = {}
    base_row_attrs: dict[str, str] = {}
    if base_row is not None:
        for cell in base_row.findall(f"{{{NS}}}c"):
            column = re.match(r"[A-Z]+", cell.attrib["r"]).group(0)
            style_by_column[column] = cell.attrib.get("s")
        base_row_attrs = {key: value for key, value in base_row.attrib.items() if key != "r"}

    sheet_data.clear()
    for header in header_rows:
        sheet_data.append(header)
    for row_number, values in enumerate(rows, start=3):
        row_attrs = dict(base_row_attrs)
        row_attrs["r"] = str(row_number)
        row_element = ET.Element(f"{{{NS}}}row", row_attrs)
        for column in sorted(values, key=column_number):
            value = values[column]
            if value is None or value == "":
                continue
            style = style_by_column.get(column)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                row_element.append(number_cell(column, row_number, value, style))
            else:
                row_element.append(text_cell(column, row_number, str(value), style))
        sheet_data.append(row_element)

    dimension = root.find(f"{{{NS}}}dimension")
    if dimension is not None:
        dimension.set("ref", f"A1:DG{len(rows) + 2}")
    new_sheet = ET.tostring(root, encoding="utf-8", xml_declaration=True)

    with zipfile.ZipFile(OUTPUT_PATH, "w") as output_zip:
        for item in original_entries:
            data = new_sheet if item.filename == sheet_name else original_parts[item.filename]
            output_zip.writestr(item, data)

    with zipfile.ZipFile(OUTPUT_PATH, "r") as check_zip:
        output_names = check_zip.namelist()
        if output_names != [item.filename for item in original_entries]:
            raise SystemExit("ZIP member order changed")
        for item in original_entries:
            if item.filename == sheet_name:
                continue
            if check_zip.read(item.filename) != original_parts[item.filename]:
                raise SystemExit(f"Template part changed: {item.filename}")


def read_back() -> dict[str, object]:
    with zipfile.ZipFile(OUTPUT_PATH, "r") as workbook:
        root = ET.fromstring(workbook.read("xl/worksheets/sheet1.xml"))
    data_rows = [row for row in root.findall(f".//{{{NS}}}sheetData/{{{NS}}}row") if int(row.attrib["r"]) >= 3]

    def value(row: ET.Element, column: str) -> str:
        cell = row.find(f"{{{NS}}}c[@r='{column}{row.attrib['r']}']")
        if cell is None:
            return ""
        if cell.attrib.get("t") == "inlineStr":
            return "".join(node.text or "" for node in cell.findall(f".//{{{NS}}}t"))
        node = cell.find(f"{{{NS}}}v")
        return "" if node is None else node.text or ""

    return {
        "data_rows": len(data_rows),
        "first_sku": value(data_rows[0], "CJ"),
        "last_sku": value(data_rows[-1], "CJ"),
        "first_title": value(data_rows[0], "E"),
        "last_title": value(data_rows[-1], "E"),
        "first_model": value(data_rows[0], "AU"),
        "last_model": value(data_rows[-1], "AU"),
        "sha256": hashlib.sha256(OUTPUT_PATH.read_bytes()).hexdigest(),
    }


def main() -> None:
    rows = build_rows()
    report = validate(rows)
    write_workbook(rows)
    report["read_back"] = read_back()
    report["output"] = str(OUTPUT_PATH)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
