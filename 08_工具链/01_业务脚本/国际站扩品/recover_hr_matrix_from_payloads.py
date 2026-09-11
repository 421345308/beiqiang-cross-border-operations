from __future__ import annotations

import csv
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
PACK_ROOT = ROOT / "01_产品资产/01_原始数据包/热榜OEM概念款_2026-09-05"
PAYLOAD_ROOT = ROOT / "02_Alibaba运营/05_扩品工程/热榜持续扩品_2026-09-05"
MATRIX = PACK_ROOT / "00_扩品差异化矩阵.csv"
FIELDS = ["ListingID", "Model", "Intent", "LeadColor", "MainImageLocal", "Title", "Keywords", "ProductHighlights", "DetailEmphasis"]
INTENT = {"A": "Wholesale Importer", "B": "Private Label", "C": "Online Seller"}


def field(root: ET.Element, field_id: str) -> ET.Element | None:
    return next((node for node in root.findall("field") if node.get("id") == field_id), None)


def value(root: ET.Element, field_id: str) -> str:
    node = field(root, field_id)
    found = node.find(".//value") if node is not None else None
    return (found.text or "").strip() if found is not None else ""


def package_info(model: str, variant: str, root: ET.Element) -> tuple[str, str]:
    folders = list(PACK_ROOT.glob(f"{model}_*"))
    if len(folders) != 1:
        raise RuntimeError(f"Expected one package folder for {model}, got {folders}")
    folder = folders[0]
    manifest_path = folder / "package_manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        color = manifest["colors"]["ABC".index(variant)]
        local = f"{folder.name}/03_颜色图/{model}_color_{color['slug']}.png"
        return color["name"], local
    sale_prop = field(root, "saleProp")
    color_field = sale_prop.find(".//field[@id='p-191288010']") if sale_prop is not None else None
    names = [node.get("inputValue", "") for node in color_field.findall(".//value")] if color_field is not None else []
    index = "ABC".index(variant)
    lead_color = names[index] if index < len(names) else variant
    candidates = sorted((folder / "03_颜色图").glob(f"{model}_color_*.png"))
    normalized = re.sub(r"[^a-z0-9]+", "_", lead_color.lower()).strip("_")
    matched = next((p for p in candidates if normalized in p.stem.lower()), None)
    selected = matched or (candidates[index] if index < len(candidates) else candidates[0])
    return lead_color, f"{folder.name}/03_颜色图/{selected.name}"


def payload_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(PAYLOAD_ROOT.glob("HR???-?_publish.xml")):
        match = re.fullmatch(r"(HR\d{3})-([ABC])_publish\.xml", path.name)
        if not match:
            continue
        model, variant = match.groups()
        root = ET.fromstring(path.read_text(encoding="utf-8"))
        listing_id = f"{model}-{variant}"
        title = re.sub(rf"\s+Model\s+{re.escape(listing_id)}$", "", value(root, "productTitle"))
        lead_color, local = package_info(model, variant, root)
        rows.append({
            "ListingID": listing_id,
            "Model": model,
            "Intent": INTENT[variant],
            "LeadColor": lead_color,
            "MainImageLocal": local,
            "Title": title,
            "Keywords": value(root, "productKeywords"),
            "ProductHighlights": value(root, "textDesc"),
            "DetailEmphasis": "Recovered from submitted API payload",
        })
    return rows


def main() -> None:
    rows = payload_rows()
    if len(rows) < 100:
        raise RuntimeError(f"Refusing to replace matrix with only {len(rows)} recovered rows")
    temp = MATRIX.with_suffix(".csv.recovered.tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(MATRIX)
    print(json.dumps({"recovered_rows": len(rows), "matrix": str(MATRIX)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
