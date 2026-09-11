from __future__ import annotations

import hashlib
import json
import re
import zipfile
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET


NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
ET.register_namespace("", NS)

ROOT = Path(__file__).resolve().parents[3]
RUN_ROOT = Path(__file__).resolve().parent / "全量三链接_2026-08-28"
PLAN_PATH = RUN_ROOT / "159条链接总控计划.json"
MAP_DIR = RUN_ROOT / "图片银行映射_2026-08-29"
TEMPLATE_PATH = ROOT / "outputs" / "20260828_alibaba_multilink_pilot" / "latest_template.xlsx"
OUTPUT_DIR = ROOT / "outputs" / "20260829_remaining_multilink_batches"
STAGING_ROOT = Path(r"E:\贝强大文件\03_国际站批量发品临时\全量三链接_2026-08-29")
CATALOG_PATH = ROOT / "04_客户开发" / "05_客户项目" / "历史客户资料" / "Gabriel_Beiqiang_catalog_20260630" / "_build" / "catalog_data_ready.json"
PROFILE_PATH = ROOT / "08_工具链" / "01_业务脚本" / "国际站扩品" / "sooxie_prelisting_profiles_2026-08-14.json"

BATCHES = {
    2: ("BQ006", "BQ010"), 3: ("BQ011", "BQ015"), 4: ("BQ016", "BQ020"),
    5: ("BQ021", "BQ025"), 6: ("BQ026", "BQ030"), 7: ("BQ031", "BQ035"),
    8: ("BQ036", "BQ040"), 9: ("BQ041", "BQ045"), 10: ("BQ046", "BQ050"),
    11: ("BQ051", "BQ059"),
}

MAIN_COLUMNS = ["F", "G", "H", "I", "J", "K"]
DETAIL_COLUMNS = ["O", "P", "Q", "R"]
FAQ_COLUMN_PAIRS = [("AC", "AD"), ("AE", "AF"), ("AG", "AH"), ("AI", "AJ"), ("AK", "AL"), ("AM", "AN"), ("AO", "AP"), ("AQ", "AR")]
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

FACT_OVERRIDES = {
    "BQ006": {"closure": "Lace-Up"},
    "BQ010": {"closure": "Lace-Up", "upper": "Stretch Textile Upper", "sole": "EVA"},
    "BQ013": {"model": "T55836", "sizes": list(range(35, 46))},
    "BQ015": {"closure": "Slip-On with Lace Detail"},
    "BQ020": {"model": "A218"},
    "BQ031": {"model": "ZX2116", "sizes": list(range(38, 48)), "colors": ["All Black", "Black/White", "Grey/White", "Off White", "Green/White"], "upper": "Knitted Textile Upper", "sole": "EVA", "closure": "Lace-Up", "fit": "Wide Toe Box"},
}
SIZE_LIMITS = {
    ("BQ006", "White Purple"): list(range(35, 41)),
    ("BQ006", "White Pink"): list(range(35, 41)),
    ("BQ037", "Purple (EU 35-40)"): list(range(35, 41)),
}
SIZE_RANGE_OVERRIDES = {"BQ013": list(range(35, 46)), "BQ023": list(range(35, 46))}
PROFILE_SIZE_RANGES = {
    "BQ032": (38, 47), "BQ033": (35, 45), "BQ034": (35, 45), "BQ035": (37, 45),
    "BQ036": (35, 45), "BQ037": (35, 45), "BQ038": (35, 45), "BQ039": (35, 45),
    "BQ040": (39, 45), "BQ041": (31, 40), "BQ042": (35, 45), "BQ043": (35, 45),
    "BQ044": (35, 45), "BQ045": (39, 45), "BQ046": (35, 45), "BQ047": (39, 45),
    "BQ048": (35, 45), "BQ049": (35, 45), "BQ050": (35, 45), "BQ051": (35, 45),
    "BQ052": (38, 47), "BQ059": (35, 45),
}


def col_num(column: str) -> int:
    value = 0
    for char in column:
        value = value * 26 + ord(char) - 64
    return value


def text_cell(column: str, row_number: int, value: str, style: str | None) -> ET.Element:
    attrs = {"r": f"{column}{row_number}", "t": "inlineStr"}
    if style is not None:
        attrs["s"] = style
    cell = ET.Element(f"{{{NS}}}c", attrs)
    inline = ET.SubElement(cell, f"{{{NS}}}is")
    node = ET.SubElement(inline, f"{{{NS}}}t")
    node.text = value
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


def parse_size_range(text: str) -> list[int]:
    match = re.search(r"(\d{2})\s*[\-\u2013]\s*(\d{2})", text)
    if not match:
        raise ValueError(f"Cannot parse size range: {text}")
    return list(range(int(match.group(1)), int(match.group(2)) + 1))


def facts() -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for item in json.loads(CATALOG_PATH.read_text(encoding="utf-8")):
        code = item["code"]
        result[code] = {
            "model": item["model"], "sizes": SIZE_RANGE_OVERRIDES.get(code) or parse_size_range(item["sizeRange"]),
            "colors": [x.strip() for x in item["colors"].split(",")],
            "upper": item["upper"], "sole": item["outsole"], "closure": item["closure"],
            "fit": "Regular Fit",
        }
    for item in json.loads(PROFILE_PATH.read_text(encoding="utf-8"))["products"]:
        evidence = item.get("evidence_note", "")
        lo, hi = PROFILE_SIZE_RANGES.get(item["code"], (None, None))
        result[item["code"]] = {
            "model": item["model"], "sizes": list(range(lo, hi + 1)) if lo is not None else parse_size_range(evidence),
            "colors": item["colors"], "upper": item["upper"], "sole": item["sole"],
            "closure": item["closure"], "fit": "Regular Fit",
        }
    for code, override in FACT_OVERRIDES.items():
        result.setdefault(code, {}).update(override)
    return result


def file_hash(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def asset_resolver(manifest: dict, mapping: dict[str, str]):
    exact: dict[str, str] = {}
    by_hash: dict[str, str] = {}
    for item in manifest["files"]:
        key = Path(item["filename"]).stem
        if key not in mapping:
            continue
        exact[str(Path(item["source"]).resolve()).lower()] = mapping[key]
        by_hash[file_hash(item["source"])] = mapping[key]

    def resolve(source: str) -> str:
        normalized = str(Path(source).resolve()).lower()
        if normalized in exact:
            return exact[normalized]
        digest = file_hash(source)
        if digest in by_hash:
            return by_hash[digest]
        raise KeyError(f"No uploaded URL for {source}")

    return resolve


def build_batch(batch_no: int, all_facts: dict[str, dict[str, object]], plan: list[dict]) -> tuple[list[dict[str, object]], dict]:
    first, last = BATCHES[batch_no]
    batch_dir = next(STAGING_ROOT.glob(f"批次{batch_no:02d}_*"))
    manifest = json.loads((batch_dir / "图片上传清单.json").read_text(encoding="utf-8"))
    mapping_path = next(MAP_DIR.glob(f"批次{batch_no:02d}_*.json"))
    mapping_data = json.loads(mapping_path.read_text(encoding="utf-8"))
    mapping = {item["filename"]: item["url"] for item in mapping_data["items"]}
    resolve = asset_resolver(manifest, mapping)
    products = {item["code"]: item for item in manifest["products"]}
    selected = [item for item in plan if first <= item["source_bq"] <= last and item["source_bq"] in products]
    if batch_no == 11:
        selected = [item for item in plan if item["source_bq"] in {"BQ051", "BQ052", "BQ059"}]
    rows: list[dict[str, object]] = []
    company_cols = ["T", "V", "W", "X", "Z"]
    focus = {
        "W1": "Prepared for importer and wholesaler sourcing with verified product facts and wholesale ordering support.",
        "R1": "Prepared for online sellers and casual walking collections with visible construction and color selection support.",
        "O1": "Prepared for OEM, ODM and private-label discussion. Logo, color, size ratio and packaging are reviewed before production.",
    }
    errors: list[str] = []
    for item in selected:
        code = item["source_bq"]
        variant = item["link_code"].rsplit("-", 1)[1]
        product = products[code]
        fact = all_facts[code]
        visual_qa = product.get("visual_qa", {})
        if visual_qa.get(variant) != "PASS":
            errors.append(
                f"{item['link_code']}: visual QA is not PASS; Excel export is blocked"
            )
            continue
        raw_root = str((ROOT / "01_产品资产" / "01_原始数据包").resolve()).lower()
        raw_main_sources = [
            source for source in product["main"][variant]
            if str(Path(source).resolve()).lower().startswith(raw_root)
        ]
        if raw_main_sources:
            errors.append(
                f"{item['link_code']}: raw-package files cannot be used as main images"
            )
            continue
        main = [resolve(x) for x in product["main"][variant]]
        detail_candidates = []
        for source in product["detail"]:
            url = resolve(source)
            if url not in main and url not in detail_candidates:
                detail_candidates.append(url)
        detail = detail_candidates[:4]
        colors = list(fact["colors"])
        color_urls = [resolve(x) for x in product["sku_color"]]
        if not color_urls:
            fallback_urls = []
            for role in ("W1", "R1", "O1"):
                for source in product["main"][role]:
                    url = resolve(source)
                    if url not in fallback_urls:
                        fallback_urls.append(url)
            color_urls = fallback_urls[:len(colors)]
        elif len(color_urls) < len(colors):
            for role in ("W1", "R1", "O1"):
                for source in product["main"][role]:
                    url = resolve(source)
                    if url not in color_urls:
                        color_urls.append(url)
                    if len(color_urls) == len(colors):
                        break
                if len(color_urls) == len(colors):
                    break
        if len(colors) != len(color_urls):
            errors.append(f"{code}: {len(colors)} colors but {len(color_urls)} color images")
            continue
        if len(main) != 6 or len(set(main)) != 6:
            errors.append(f"{item['link_code']}: main images are not 6 unique")
            continue
        if len(detail) != 4:
            errors.append(f"{item['link_code']}: detail images are not 4 unique/disjoint")
            continue
        sole = re.sub(r"\s+Sole$", "", str(fact["sole"]), flags=re.I)
        desc = f"Model {fact['model']} {str(fact['upper']).lower()} {str(fact['closure']).lower()} walking shoes with {sole.lower()} sole, EU {min(fact['sizes'])}-{max(fact['sizes'])} sizing and photographed color options. {focus[variant]}"
        for color, color_url in zip(colors, color_urls):
            clean_color = re.sub(r"\s*\(EU\s*\d+\-\d+\)\s*", "", color, flags=re.I).strip()
            sizes = SIZE_LIMITS.get((code, color), fact["sizes"])
            for size in sizes:
                row: dict[str, object] = {
                    "E": item["title"], **dict(zip(MAIN_COLUMNS, main)), **dict(zip(DETAIL_COLUMNS, detail)),
                    "S": desc,
                    "AB": "Quanzhou Beiqiang Footwear & Apparel Co., Ltd. supplies OEM/ODM and wholesale casual footwear for importers, wholesalers, sourcing agents and private-label buyers.",
                    "AS": "China", "AU": item["model_number"], "AV": sole, "AW": "All Seasons", "AX": "Walking Shoes",
                    "AY": sole, "AZ": fact["upper"], "BB": fact["closure"], "BC": "Round Toe", "BF": "Light Weight;Breathable",
                    "BK": "Fit Type", "BL": fact.get("fit", "Regular Fit"),
                    "CE": clean_color, "CF": color_url, "CG": size, "CH": 999,
                    "CJ": f"{item['link_code']}-{slug(clean_color)}-{size}", "CK": 2, "CL": "Pair/Pairs",
                    "CM": 2, "CN": 9.49, "CO": 50, "CP": 9.19, "CQ": 100, "CR": 9.09,
                    "CV": 34, "CW": 23, "CX": 13, "CY": 0.5, "CZ": "智能运费模板", "DA": "普货", "DB": 100, "DC": 31,
                }
                row.update(dict(zip(company_cols, COMPANY_IMAGES)))
                for pair, faq in zip(FAQ_COLUMN_PAIRS, FAQS):
                    row[pair[0]], row[pair[1]] = faq
                rows.append(row)
    report = {"batch": batch_no, "source_products": len({str(r["AU"]).split("-")[0].strip() for r in rows}), "links": len({r["AU"] for r in rows}), "rows": len(rows), "errors": errors}
    if errors:
        raise RuntimeError(json.dumps(report, ensure_ascii=False, indent=2))
    return rows, report


def validate_rows(rows: list[dict[str, object]]) -> None:
    errors: list[str] = []
    models = sorted({str(row["AU"]) for row in rows})
    skus = [str(row["CJ"]) for row in rows]
    if len(skus) != len(set(skus)):
        errors.append("duplicate SKU codes")
    for model in models:
        model_rows = [row for row in rows if row["AU"] == model]
        titles = {str(row["E"]) for row in model_rows}
        if len(titles) != 1 or len(next(iter(titles))) > 128:
            errors.append(f"{model}: title inconsistency or length")
        sample = model_rows[0]
        main = [str(sample[col]) for col in MAIN_COLUMNS]
        detail = [str(sample[col]) for col in DETAIL_COLUMNS]
        color_urls = {str(row["CF"]) for row in model_rows}
        if len(set(main)) != 6:
            errors.append(f"{model}: main uniqueness")
        if len(set(detail)) != 4 or set(main) & set(detail):
            errors.append(f"{model}: detail uniqueness/overlap")
        all_urls = main + detail + COMPANY_IMAGES + list(color_urls)
        if any(not url.startswith("https://sc04.alicdn.com/kf/") for url in all_urls):
            errors.append(f"{model}: non-sc04 URL")
    if errors:
        raise RuntimeError("; ".join(errors))


def write_workbook(rows: list[dict[str, object]], batch_no: int, first: str, last: str) -> Path:
    output = OUTPUT_DIR / f"批次{batch_no:02d}_{first}-{last}_{len({r['AU'] for r in rows})}条链接_国际站批量发品_2026-08-29.xlsx"
    with zipfile.ZipFile(TEMPLATE_PATH, "r") as src:
        infos = src.infolist()
        parts = {i.filename: src.read(i.filename) for i in infos}
    sheet_name = "xl/worksheets/sheet1.xml"
    root = ET.fromstring(parts[sheet_name])
    sheet_data = root.find(f"{{{NS}}}sheetData")
    template_rows = list(sheet_data)
    headers = [deepcopy(r) for r in template_rows if int(r.attrib.get("r", "0")) <= 2]
    base = next((r for r in template_rows if r.attrib.get("r") == "3"), None)
    styles = {} if base is None else {re.match(r"[A-Z]+", c.attrib["r"]).group(0): c.attrib.get("s") for c in base.findall(f"{{{NS}}}c")}
    base_attrs = {} if base is None else {k: v for k, v in base.attrib.items() if k != "r"}
    sheet_data.clear()
    for header in headers:
        sheet_data.append(header)
    for row_no, values in enumerate(rows, 3):
        attrs = dict(base_attrs)
        attrs["r"] = str(row_no)
        element = ET.Element(f"{{{NS}}}row", attrs)
        for column in sorted(values, key=col_num):
            value = values[column]
            element.append(number_cell(column, row_no, value, styles.get(column)) if isinstance(value, (int, float)) else text_cell(column, row_no, str(value), styles.get(column)))
        sheet_data.append(element)
    dimension = root.find(f"{{{NS}}}dimension")
    if dimension is not None:
        dimension.set("ref", f"A1:DG{len(rows)+2}")
    new_sheet = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(output, "w") as dst:
        for info in infos:
            dst.writestr(info, new_sheet if info.filename == sheet_name else parts[info.filename])
    with zipfile.ZipFile(output, "r") as check:
        if check.namelist() != [i.filename for i in infos]:
            raise RuntimeError("ZIP member order changed")
        for info in infos:
            if info.filename != sheet_name and check.read(info.filename) != parts[info.filename]:
                raise RuntimeError(f"Template part changed: {info.filename}")
    return output


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_facts = facts()
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    reports = []
    for batch_no in range(2, 12):
        first, last = BATCHES[batch_no]
        if not list(MAP_DIR.glob(f"批次{batch_no:02d}_*.json")):
            reports.append({"batch": batch_no, "status": "BLOCKED_MISSING_IMAGE_MAPPING"})
            continue
        rows, report = build_batch(batch_no, all_facts, plan)
        validate_rows(rows)
        output = write_workbook(rows, batch_no, first, last)
        report.update({"status": "PASS", "output": str(output), "sha256": hashlib.sha256(output.read_bytes()).hexdigest()})
        reports.append(report)
    (OUTPUT_DIR / "批次生成报告_2026-08-29.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(reports, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
