from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import zipfile
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET


NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
ET.register_namespace("", NS)

ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
PLAN_PATH = SCRIPT_DIR / "全量三链接_2026-08-28" / "标题终审_2026-08-31" / "159条链接标题终审_2026-08-31.json"
TEMPLATE_PATH = ROOT / "outputs" / "20260828_alibaba_multilink_pilot" / "latest_template.xlsx"
ASSET_MAP_DIR = ROOT / "outputs" / "20260830_full_excel_rebuild"
OUTPUT_DIR = ROOT / "outputs" / "20260831_full_excel_title_video"
OUTPUT_PATH = OUTPUT_DIR / "贝强53款159链接_标题终审完整表_2026-08-31.xlsx"
MAIN_MAP_PATH = ASSET_MAP_DIR / "cdn_map_rebuild.json"
DETAIL_MAP_PATH = ASSET_MAP_DIR / "detail_cdn_map_41plus.json"
COLOR_MAP_PATH = ASSET_MAP_DIR / "color_cdn_map_41plus.json"
VISUAL_MANIFEST = Path(r"E:\贝强大文件\03_国际站批量发品临时\全量重制_2026-08-30\重制主图清单.json")

MAIN_COLUMNS = ["F", "G", "H", "I", "J", "K"]
DETAIL_COLUMNS = ["O", "P", "Q", "R"]
COMPANY_COLUMNS = ["T", "V", "W", "X", "Z"]
FAQ_COLUMN_PAIRS = [("AC", "AD"), ("AE", "AF"), ("AG", "AH"), ("AI", "AJ"), ("AK", "AL"), ("AM", "AN"), ("AO", "AP"), ("AQ", "AR")]
COMPANY_IMAGES = [
    "https://sc04.alicdn.com/kf/Sf587c854711748af9759e77ce5aeb03c3/286385890/Sf587c854711748af9759e77ce5aeb03c3.png",
    "https://sc04.alicdn.com/kf/Sfea34bbd56ae4d0583aa855838eb1454F/286385890/Sfea34bbd56ae4d0583aa855838eb1454F.png",
    "https://sc04.alicdn.com/kf/S2a3af5690d524680824086ad8419dbc9G/286385890/S2a3af5690d524680824086ad8419dbc9G.png",
    "https://sc04.alicdn.com/kf/Sdc4e18f098e142b797df687e8befbfa14/286385890/Sdc4e18f098e142b797df687e8befbfa14.png",
    "https://sc04.alicdn.com/kf/Sc1dc6ec7d435404db6a31c6938a734a0g/286385890/Sc1dc6ec7d435404db6a31c6938a734a0g.png",
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


def load_support_module():
    path = SCRIPT_DIR / "build_remaining_excel.py"
    spec = importlib.util.spec_from_file_location("beiqiang_remaining", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def col_num(column: str) -> int:
    value = 0
    for char in column:
        value = value * 26 + ord(char) - 64
    return value


def cell_column(reference: str) -> str:
    return re.match(r"[A-Z]+", reference).group(0)


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


def read_rows(path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as book:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in book.namelist():
            root = ET.fromstring(book.read("xl/sharedStrings.xml"))
            shared = ["".join(node.text or "" for node in item.iter(f"{{{NS}}}t")) for item in root]
        sheet = ET.fromstring(book.read("xl/worksheets/sheet1.xml"))
    rows: list[dict[str, str]] = []
    for row in sheet.findall(f".//{{{NS}}}row"):
        if int(row.attrib.get("r", "0")) < 3:
            continue
        values: dict[str, str] = {}
        for cell in row.findall(f"{{{NS}}}c"):
            column = cell_column(cell.attrib["r"])
            if cell.attrib.get("t") == "inlineStr":
                value = "".join(node.text or "" for node in cell.iter(f"{{{NS}}}t"))
            else:
                node = cell.find(f"{{{NS}}}v")
                value = "" if node is None else node.text or ""
                if cell.attrib.get("t") == "s" and value:
                    value = shared[int(value)]
            values[column] = value
        rows.append(values)
    return rows


def old_asset_registry() -> dict[str, dict[str, object]]:
    paths = list((ROOT / "outputs" / "20260829_bq001_bq005_batch01").glob("*.xlsx"))
    paths += list((ROOT / "outputs" / "20260829_remaining_multilink_batches").glob("批次0[2-8]_*.xlsx"))
    registry: dict[str, dict[str, object]] = {}
    for path in sorted(paths):
        for row in read_rows(path):
            model = row.get("AU", "")
            match = re.match(r"(BQ\d{3})-", model)
            if not match:
                continue
            code = match.group(1)
            entry = registry.setdefault(code, {"detail": [], "colors": {}})
            if not entry["detail"]:
                entry["detail"] = [row.get(column, "") for column in DETAIL_COLUMNS]
            color, url = row.get("CE", "").strip(), row.get("CF", "").strip()
            if color and url:
                entry["colors"].setdefault(color, url)
    return registry


def normalize_color(value: str) -> str:
    return re.sub(r"\s*\(EU\s*\d+\-\d+\)\s*", "", value, flags=re.I).strip()


def slug(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "-", value.upper()).strip("-")


def normalize_title(item: dict[str, object]) -> str:
    title = re.sub(r"\s+", " ", str(item["title"])).strip()
    title = title.replace("Regular Fit EU for", "Regular Fit for")
    artno = str(item["source_artno"])
    if artno.lower() not in title.lower():
        title += f" Model {artno}"
    if str(item["source_bq"]) >= "BQ032":
        title = re.sub(r"\bWide Toe Box\b\s*", "", title, flags=re.I)
    if len(title) > 128:
        for phrase in (" for Importers and Wholesalers", " for Online Sellers", " for Brand Buyers", " Factory Supply"):
            title = title.replace(phrase, "")
            if len(title) <= 128:
                break
    if len(title) > 128:
        suffix = f" Model {artno}"
        base = title[: 128 - len(suffix)].rsplit(" ", 1)[0]
        title = base + suffix
    return title


def validate_visual_qa() -> None:
    manifest = json.loads(VISUAL_MANIFEST.read_text(encoding="utf-8"))
    if len(manifest.get("products", {})) != 53:
        raise RuntimeError("visual manifest must contain 53 products")
    for code, product in manifest["products"].items():
        qa = product.get("visual_qa", {})
        if any(qa.get(role) != "PASS" for role in ("W1", "R1", "O1")):
            raise RuntimeError(f"{code}: visual QA is not complete")


def build_rows() -> tuple[list[dict[str, object]], dict[str, object]]:
    support = load_support_module()
    facts = support.facts()
    facts["BQ001"]["fit"] = "Wide Toe Box"
    facts["BQ002"]["fit"] = "Wide Toe Box"
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    main_map = json.loads(MAIN_MAP_PATH.read_text(encoding="utf-8"))
    detail_map = json.loads(DETAIL_MAP_PATH.read_text(encoding="utf-8"))
    color_map = json.loads(COLOR_MAP_PATH.read_text(encoding="utf-8"))
    old = old_asset_registry()
    if len(plan) != 159 or len(main_map) != 954 or len(detail_map) != 52 or len(color_map) != 52:
        raise RuntimeError(f"input counts: plan={len(plan)} main={len(main_map)} detail={len(detail_map)} color={len(color_map)}")

    rows: list[dict[str, object]] = []
    focus = {
        "W1": "Prepared for importer and wholesaler sourcing with verified product facts and wholesale ordering support.",
        "R1": "Prepared for online sellers and casual walking collections with visible construction and color selection support.",
        "O1": "Prepared for OEM, ODM and private-label discussion. Logo, color, size ratio and packaging are reviewed before production.",
    }
    for item in plan:
        code = str(item["source_bq"])
        variant = str(item["link_code"]).rsplit("-", 1)[1]
        fact = dict(facts[code])
        fact["model"] = str(item["source_artno"])
        main = [main_map[f"{code.lower()}_{variant.lower()}_m{i}"] for i in range(1, 7)]
        if code <= "BQ040":
            detail = list(old[code]["detail"])
            old_colors = old[code]["colors"]
            clean_to_url = {normalize_color(name): url for name, url in old_colors.items()}
            color_urls = [clean_to_url.get(normalize_color(name), "") for name in fact["colors"]]
            fallback = list(dict.fromkeys(old_colors.values()))
            fallback += [
                main_map[f"{code.lower()}_{role}_m{i}"]
                for role in ("w1", "r1", "o1") for i in range(1, 7)
            ]
            used = {value for value in color_urls if value}
            for index, value in enumerate(color_urls):
                if value:
                    continue
                replacement = next(url for url in fallback if url not in used)
                color_urls[index] = replacement
                used.add(replacement)
        else:
            detail = [detail_map[f"{code.lower()}d{i}"] for i in range(1, 5)]
            color_urls = [color_map[f"{code.lower()}c{i}"] for i in range(1, len(fact["colors"]) + 1)]
        if len(detail) != 4 or len(set(detail)) != 4:
            raise RuntimeError(f"{code}: invalid detail image set")
        if len(color_urls) != len(fact["colors"]):
            raise RuntimeError(f"{code}: {len(fact['colors'])} colors but {len(color_urls)} images")
        sole = re.sub(r"\s+Sole$", "", str(fact["sole"]), flags=re.I)
        description = (
            f"Model {fact['model']} {str(fact['upper']).lower()} {str(fact['closure']).lower()} walking shoes "
            f"with {sole.lower()} sole, EU {min(fact['sizes'])}-{max(fact['sizes'])} sizing and photographed color options. "
            f"{focus[variant]}"
        )
        for color, color_url in zip(fact["colors"], color_urls):
            clean_color = normalize_color(str(color))
            sizes = support.SIZE_LIMITS.get((code, color), fact["sizes"])
            for size in sizes:
                row: dict[str, object] = {
                    "E": normalize_title(item),
                    **dict(zip(MAIN_COLUMNS, main)),
                    **dict(zip(DETAIL_COLUMNS, detail)),
                    "S": description,
                    "AB": "Quanzhou Beiqiang Footwear & Apparel Co., Ltd. supplies OEM/ODM and wholesale casual footwear for importers, wholesalers, sourcing agents and private-label buyers.",
                    "AS": "China", "AU": item["model_number"], "AV": sole, "AW": "All Seasons", "AX": "Walking Shoes",
                    "AY": sole, "AZ": fact["upper"], "BB": fact["closure"], "BC": "Round Toe", "BF": "Light Weight;Breathable",
                    "BK": "Fit Type", "BL": fact.get("fit", "Regular Fit"),
                    "CE": clean_color, "CF": color_url, "CG": size, "CH": 999,
                    "CJ": f"{item['link_code']}-{slug(clean_color)}-{size}", "CK": 2, "CL": "Pair/Pairs",
                    "CM": 2, "CN": 9.49, "CO": 50, "CP": 9.19, "CQ": 100, "CR": 9.09,
                    "CV": 34, "CW": 23, "CX": 13, "CY": 0.5, "CZ": "智能运费模板", "DA": "普货", "DB": 100, "DC": 31,
                }
                row.update(dict(zip(COMPANY_COLUMNS, COMPANY_IMAGES)))
                for columns, faq in zip(FAQ_COLUMN_PAIRS, FAQS):
                    row[columns[0]], row[columns[1]] = faq
                rows.append(row)
    return rows, {"plan_links": len(plan), "source_products": len({x["source_bq"] for x in plan})}


def validate_rows(rows: list[dict[str, object]]) -> dict[str, object]:
    errors: list[str] = []
    models = sorted({str(row["AU"]) for row in rows})
    titles = {model: {str(row["E"]) for row in rows if row["AU"] == model} for model in models}
    if len(models) != 159:
        errors.append(f"expected 159 models, got {len(models)}")
    if len({next(iter(value)) for value in titles.values()}) != 159:
        errors.append("titles are not unique across 159 links")
    skus = [str(row["CJ"]) for row in rows]
    if len(skus) != len(set(skus)):
        errors.append("duplicate SKU codes")
    for model in models:
        model_rows = [row for row in rows if row["AU"] == model]
        title_set = titles[model]
        if len(title_set) != 1 or len(next(iter(title_set))) > 128:
            errors.append(f"{model}: title consistency/length")
        sample = model_rows[0]
        main = [str(sample[column]) for column in MAIN_COLUMNS]
        detail = [str(sample[column]) for column in DETAIL_COLUMNS]
        if len(set(main)) != 6:
            errors.append(f"{model}: six main images are not unique")
        if len(set(detail)) != 4 or set(main) & set(detail):
            errors.append(f"{model}: detail images invalid or overlap main")
        urls = main + detail + COMPANY_IMAGES + [str(row["CF"]) for row in model_rows]
        if any(not url.startswith("https://sc04.alicdn.com/kf/") for url in urls):
            errors.append(f"{model}: non-sc04 URL")
    variants: dict[str, list[set[str]]] = {}
    for model in models:
        code = model.split("-", 1)[0]
        sample = next(row for row in rows if row["AU"] == model)
        variants.setdefault(code, []).append({str(sample[column]) for column in MAIN_COLUMNS})
    for code, sets in variants.items():
        if len(sets) != 3 or any(a & b for i, a in enumerate(sets) for b in sets[i + 1 :]):
            errors.append(f"{code}: three link main-image sets overlap")
    if errors:
        raise RuntimeError("\n".join(errors[:100]))
    return {"models": len(models), "sku_rows": len(rows), "unique_skus": len(set(skus)), "errors": []}


def write_workbook(rows: list[dict[str, object]]) -> None:
    with zipfile.ZipFile(TEMPLATE_PATH, "r") as src:
        infos = src.infolist()
        parts = {info.filename: src.read(info.filename) for info in infos}
    sheet_name = "xl/worksheets/sheet1.xml"
    root = ET.fromstring(parts[sheet_name])
    sheet_data = root.find(f"{{{NS}}}sheetData")
    template_rows = list(sheet_data)
    headers = [deepcopy(row) for row in template_rows if int(row.attrib.get("r", "0")) <= 2]
    base = next((row for row in template_rows if row.attrib.get("r") == "3"), None)
    styles = {} if base is None else {cell_column(cell.attrib["r"]): cell.attrib.get("s") for cell in base.findall(f"{{{NS}}}c")}
    base_attrs = {} if base is None else {key: value for key, value in base.attrib.items() if key != "r"}
    sheet_data.clear()
    for header in headers:
        sheet_data.append(header)
    for row_number, values in enumerate(rows, 3):
        attrs = dict(base_attrs)
        attrs["r"] = str(row_number)
        element = ET.Element(f"{{{NS}}}row", attrs)
        for column in sorted(values, key=col_num):
            value = values[column]
            element.append(number_cell(column, row_number, value, styles.get(column)) if isinstance(value, (int, float)) else text_cell(column, row_number, str(value), styles.get(column)))
        sheet_data.append(element)
    dimension = root.find(f"{{{NS}}}dimension")
    if dimension is not None:
        dimension.set("ref", f"A1:DG{len(rows) + 2}")
    new_sheet = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(OUTPUT_PATH, "w") as dst:
        for info in infos:
            dst.writestr(info, new_sheet if info.filename == sheet_name else parts[info.filename])
    with zipfile.ZipFile(OUTPUT_PATH, "r") as check:
        if check.namelist() != [info.filename for info in infos]:
            raise RuntimeError("ZIP member order changed")
        for info in infos:
            if info.filename != sheet_name and check.read(info.filename) != parts[info.filename]:
                raise RuntimeError(f"template part changed: {info.filename}")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    validate_visual_qa()
    rows, scope = build_rows()
    validation = validate_rows(rows)
    write_workbook(rows)
    report = {
        **scope,
        **validation,
        "output": str(OUTPUT_PATH),
        "sha256": hashlib.sha256(OUTPUT_PATH.read_bytes()).hexdigest(),
        "template": str(TEMPLATE_PATH),
        "only_sheet1_xml_changed": True,
    }
    (OUTPUT_DIR / "标题终审完整Excel校验报告_2026-08-31.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
