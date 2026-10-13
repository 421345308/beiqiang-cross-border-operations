"""Prepare or publish verified HR hot-rank colour-led listings via Schema API.

Each A/B/C page has a different lead colour, buyer intent, title and first
image while retaining the same verified style, colour range and factory proof.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import re
import time
import tempfile
from datetime import datetime, timezone
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
PACK_ROOT = ROOT / "01_产品资产/01_原始数据包/热榜OEM概念款_2026-09-02"
MATRIX = PACK_ROOT / "00_24链接差异化矩阵.csv"
URL_MAP_PATH = PACK_ROOT / "00_图片银行URL映射.json"
SOURCE_XML = ROOT / ".tmp/source_product.xml"
CLIENT_PATH = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG_PATH = Path.home() / ".config/beiqiang/alibaba-openapi.json"
PHOTO_CACHE_DIR = ROOT / "02_Alibaba运营/06_图片与检查记录/API全量图片审计_2026-09-03"
OUTPUT = ROOT / "02_Alibaba运营/05_扩品工程/热榜8款API上架_2026-09-05"
PER_MODEL_RECEIPTS = False
UPLOAD_CACHE_PATH: Path | None = None
CATEGORY_ID = 201334413
CATEGORY_BY_STYLE = {
    # Platform quality diagnostics consistently classify this ankle-height
    # quilted side-zip style under Ankle & Bootie rather than Walking Style
    # Shoes.  Keep other HR styles on the walking-shoe leaf by default.
    "HR039": 201768405,
}
SOURCE_PRODUCT_ID = 1601939658415

SIZE_IDS = {
    "36": "190000105", "37": "29542", "38": "28388", "39": "190000792",
    "40": "28389", "41": "28390", "42": "28391", "43": "28392",
    "44": "28393", "45": "28394",
}

STYLE_META = {
    "HR001": {"closure": ("Lace-up", "80806811"), "lining": "Mesh", "upper": "Mesh", "features": ["Breathable", "Light Weight"]},
    "HR002": {"closure": ("Lace-up", "80806811"), "lining": "Mesh", "upper": "Mesh", "features": ["Breathable", "Light Weight"]},
    "HR003": {"closure": ("Lace-up", "80806811"), "lining": "Mesh", "upper": "Mesh and Synthetic Suede", "features": ["Breathable"]},
    "HR004": {"closure": ("Lace-up", "80806811"), "lining": "Mesh", "upper": "Textile and Synthetic PU", "features": ["Breathable", "Light Weight"]},
    "HR005": {"closure": ("Slip-On", "13325270"), "lining": "Mesh", "upper": "Mesh", "features": ["Breathable", "Light Weight"]},
    "HR006": {"closure": ("Dial Closure", "-201"), "lining": "Mesh", "upper": "Engineered Knit", "features": ["Breathable"]},
    "HR007": {"closure": ("Lace-up", "80806811"), "lining": "Textile", "upper": "Synthetic Suede", "features": []},
    "HR008": {"closure": ("Lace-up", "80806811"), "lining": "Textile", "upper": "Synthetic Leather", "features": []},
    "HR009": {"closure": ("Lace-up", "80806811"), "lining": "Mesh", "upper": "Engineered Knit", "features": ["Breathable", "Light Weight"]},
    "HR010": {"closure": ("Lace-up", "80806811"), "lining": "Mesh", "upper": "Synthetic Leather and Mesh", "features": ["Breathable", "Light Weight"]},
    "HR011": {"closure": ("Lace-up", "80806811"), "lining": "Mesh", "upper": "Engineered Knit", "features": ["Breathable", "Light Weight"]},
    "HR012": {"closure": ("Lace-up", "80806811"), "lining": "Mesh", "upper": "Mesh and Synthetic Leather", "features": ["Breathable", "Light Weight"]},
    "HR013": {"closure": ("Slip-On", "13325270"), "lining": "Mesh", "upper": "Mesh", "features": ["Breathable", "Light Weight"]},
    "HR014": {"closure": ("Lace-up", "80806811"), "lining": "Mesh", "upper": "Mesh and Synthetic Leather", "features": ["Breathable", "Light Weight"]},
    "HR015": {"closure": ("Lace-up", "80806811"), "lining": "Mesh", "upper": "Synthetic Leather", "features": ["Breathable", "Light Weight"]},
    "HR016": {"closure": ("Lace-up", "80806811"), "lining": "Mesh", "upper": "Mesh and Synthetic Leather", "features": ["Breathable", "Light Weight"]},
    "HR017": {"closure": ("Lace-up", "80806811"), "lining": "Mesh", "upper": "Mesh and Synthetic Suede", "features": ["Breathable", "Light Weight"]},
    "HR018": {"closure": ("Lace-up", "80806811"), "lining": "Mesh", "upper": "Mesh and Synthetic Leather", "features": ["Breathable", "Light Weight"]},
    "HR019": {"closure": ("Slip-On", "13325270"), "lining": "Mesh", "upper": "Flyknit", "features": ["Breathable", "Light Weight"]},
    "HR020": {"closure": ("Slip-On", "13325270"), "lining": "Mesh", "upper": "Microfiber Leather", "features": ["Breathable", "Light Weight"]},
    "HR021": {"closure": ("Hook-and-Loop Strap", "-201"), "lining": "Mesh", "upper": "Engineered Knit", "features": ["Breathable", "Light Weight"]},
    "HR022": {"closure": ("Elastic Lace", "-201"), "lining": "Mesh", "upper": "Mesh and Synthetic Leather", "features": ["Breathable", "Light Weight"]},
    "HR023": {"closure": ("Lace-up", "80806811"), "lining": "Mesh", "upper": "Microfiber Leather and Synthetic Suede", "features": ["Breathable"]},
    "HR024": {"closure": ("Lace-up", "80806811"), "lining": "Mesh", "upper": "Mesh and Synthetic Suede", "features": ["Breathable", "Light Weight"]},
    "HR025": {"closure": ("Side Zipper and Elastic Lace", "-201"), "lining": "Mesh", "upper": "Engineered Knit", "features": ["Breathable", "Light Weight"]},
    "HR026": {"closure": ("Lace-up", "80806811"), "lining": "Mesh", "upper": "Mesh and Synthetic Suede", "features": ["Breathable", "Light Weight"]},
    "HR027": {"closure": ("Lace-up", "80806811"), "lining": "Mesh", "upper": "Mesh and Synthetic Leather", "features": ["Breathable", "Light Weight"]},
    "HR028": {"closure": ("Hook-and-Loop Strap", "-201"), "lining": "Mesh", "upper": "Mesh and Microfiber Leather", "features": ["Breathable", "Light Weight"]},
    "HR029": {"closure": ("Lace-up", "80806811"), "lining": "Mesh", "upper": "Mesh and Microfiber Leather", "features": ["Breathable", "Light Weight"]},
    "HR030": {"closure": ("Lace-up", "80806811"), "lining": "Textile", "upper": "Canvas and Microfiber Leather", "features": []},
    "HR031": {"closure": ("Lace-up", "80806811"), "lining": "Mesh", "upper": "Microfiber Leather", "features": ["Breathable"]},
    "HR032": {"closure": ("Lace-up", "80806811"), "lining": "Mesh", "upper": "Mesh and Microfiber Leather", "features": ["Breathable"]},
    "HR033": {"closure": ("Hook-and-Loop Strap", "-201"), "lining": "Textile", "upper": "Engineered Knit", "features": ["Breathable"]},
    "HR034": {"closure": ("Double Hook-and-Loop Strap", "-201"), "lining": "Mesh", "upper": "Mesh and Microfiber Leather", "features": ["Breathable"]},
    "HR035": {"closure": ("Slip-On", "13325270"), "lining": "Mesh", "upper": "Engineered Mesh and Microfiber Leather", "features": ["Breathable"]},
    "HR036": {"closure": ("Slip-On", "13325270"), "lining": "Textile", "upper": "Engineered Knit and Microfiber Leather", "features": ["Breathable", "Light Weight"]},
    "HR037": {"closure": ("Lace-up", "80806811"), "lining": "Textile", "upper": "Microfiber Leather and Synthetic Suede", "features": []},
    "HR038": {"closure": ("Lace-up", "80806811"), "lining": "Mesh", "upper": "Mesh and Synthetic Suede", "features": ["Breathable"]},
    "HR039": {"closure": ("Side Zipper and Lace-up", "-201"), "lining": "Textile", "upper": "Quilted Textile and Microfiber Leather", "features": []},
    "HR040": {"closure": ("Double Hook-and-Loop Strap", "-201"), "lining": "Textile", "upper": "Engineered Knit", "features": ["Breathable", "Light Weight"]},
    "HR041": {"closure": ("Side Zipper and Lace-up", "-201"), "lining": "Textile", "upper": "Microfiber Leather", "features": ["Breathable"]},
    "HR042": {"closure": ("Slip-On", "13325270"), "lining": "Textile", "upper": "Microfiber Leather", "features": ["Breathable"]},
    "HR043": {"closure": ("Elastic Lace", "-201"), "lining": "Mesh", "upper": "Engineered Mesh and Microfiber Leather", "features": ["Breathable", "Light Weight"]},
    "HR044": {"closure": ("Lace-up", "80806811"), "lining": "Textile", "upper": "Microfiber Leather", "features": ["Breathable"]},
    "HR045": {"closure": ("Elastic Strap", "-201"), "lining": "Textile", "upper": "Engineered Knit", "features": ["Breathable", "Light Weight"]},
    "HR046": {"closure": ("Lace-up", "80806811"), "lining": "Mesh", "upper": "Engineered Mesh and Microfiber Leather", "features": ["Breathable", "Light Weight"]},
    "HR047": {"closure": ("Slip-On", "13325270"), "lining": "Textile", "upper": "Canvas", "features": ["Light Weight"]},
    "HR048": {"closure": ("Side Zipper and Lace-up", "-201"), "lining": "Textile", "upper": "Microfiber Leather", "features": ["Breathable"]},
    "HR049": {"closure": ("Lace-up", "80806811"), "lining": "Mesh", "upper": "Mesh and Synthetic Suede", "features": ["Breathable"]},
    "HR050": {"closure": ("Lace-up", "80806811"), "lining": "Textile", "upper": "Microfiber Leather", "features": ["Breathable"]},
    "HR051": {"closure": ("Hook-and-Loop Strap", "-201"), "lining": "Mesh", "upper": "Mesh and Microfiber Leather", "features": ["Breathable", "Light Weight"]},
    "HR052": {"closure": ("Slip-On", "13325270"), "lining": "Textile", "upper": "Microfiber Leather", "features": ["Breathable", "Light Weight"]},
}


FEATURE_IDS = {"Light Weight": "46649883", "Breathable": "42283793"}
DETAIL_ROLES = [(350, "Other product images"), (300, "Detail shot"), (350, "Other product images"), (350, "Other product images")]
HIGHLIGHTS = (
    "Factory-direct footwear supply with competitive wholesale quotations based on style, quantity, materials, size ratio and packing. "
    "OEM/ODM support covers custom logo, colors, labels, insoles and packaging after requirement review. "
    "Pre-shipment quality checks cover appearance, workmanship, size assortment and order quantity. "
    "Production and dispatch are arranged promptly after specifications are confirmed; customized-order timing depends on materials, quantity and requirements. "
    "Samples can be discussed for product, fit and branding evaluation before bulk orders."
)


def load_client():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def failed(client, response: dict) -> bool:
    return bool(client.api_error(response)) or response.get("biz_success") is False or response.get("model") is False


def refs(client, response: dict) -> dict:
    return {
        "request_id": response.get("request_id"),
        "trace_id": response.get("trace_id") or response.get("_trace_id_"),
        "message": response.get("message") or response.get("msg_info"),
        "error": client.api_error(response),
    }


def top_retry(client, config, method: str, params: dict, attempts: int = 4) -> dict:
    last = None
    for attempt in range(1, attempts + 1):
        try:
            result = client.top_call(config, method, params)
            if not failed(client, result) or attempt == attempts:
                return result
            last = result
        except Exception as exc:
            last = exc
        time.sleep(attempt * 2)
    raise RuntimeError(f"{method} failed: {last}")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical_url(url: str) -> str:
    url = str(url or "")
    if url.startswith("//"):
        url = "https:" + url
    return re.sub(r"_\d+x\d+\.[^.]+$", "", url)


def image_key(url: str) -> str:
    return Path(urlparse(canonical_url(url)).path).name.rsplit(".", 1)[0]


def product_dirs() -> dict[str, Path]:
    result = {}
    for path in PACK_ROOT.iterdir():
        if path.is_dir() and re.match(r"HR\d{3}_", path.name):
            result[path.name[:5]] = path
    return result


def rows_variant(variant: str) -> dict[str, dict]:
    with MATRIX.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return {row["Model"]: row for row in rows if row["ListingID"].endswith(f"-{variant}")}


def build_b2b_m1(model: str, folder: Path, variant: str, matrix: dict) -> Path:
    preferred = PACK_ROOT / matrix["MainImageLocal"]
    if preferred.stem.endswith("_b2b") and preferred.is_file():
        return preferred
    if variant == "A":
        source = folder / "01_主图" / f"{model}_main_02_lateral.png"
    else:
        source = PACK_ROOT / matrix["MainImageLocal"]
        if source.stem.endswith("_b2b") and source.is_file():
            return source
    target = source.with_name(f"{source.stem}_b2b.png")
    with Image.open(source) as im:
        canvas = im.convert("RGB").resize((1000, 1000), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(canvas)
    bold = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 20)
    # Keep the search hero product-first.  The current live-publishing gate
    # permits one restrained service label and rejects dense badges, price,
    # lead-time or capacity claims on the first image.
    line1 = "CUSTOM LOGO / OEM/ODM"
    label_box = draw.textbbox((0, 0), line1, font=bold)
    label_width = label_box[2] - label_box[0]
    draw.rounded_rectangle((30, 30, 47 + label_width, 70), radius=8, fill=(245, 249, 247))
    draw.rounded_rectangle((30, 30, 37, 70), radius=4, fill=(28, 105, 83))
    draw.text((48, 39), line1, font=bold, fill=(24, 68, 57))
    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target, format="PNG", optimize=True)
    return target


def load_bank_index() -> dict[str, dict]:
    result = {}
    for path in PHOTO_CACHE_DIR.glob("photobank_page*_500.json"):
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        for row in (data.get("pagination_query_list") or {}).get("list", []):
            url = canonical_url(row.get("url"))
            if url:
                result[image_key(url)] = {"url": url, "file_id": str(row.get("id")), "source": "bank-index"}
    return result


def upload_image(client, config, path: Path, cache: dict) -> dict:
    digest = sha256(path)
    if digest in cache:
        return cache[digest]
    response = None
    last_error = None
    for attempt in range(1, 5):
        try:
            response = client.upload_image(config, path, None)
            break
        except Exception as exc:
            last_error = exc
            if attempt == 4:
                raise
            # Alibaba occasionally returns its HTML WAF page instead of JSON.
            # Back off more slowly for that transient response; ordinary network
            # errors keep the shorter retry cadence.
            wait = attempt * 10 if "waf_block" in str(exc) else attempt * 2
            time.sleep(wait)
    if response is None:
        raise RuntimeError(f"photobank upload failed for {path}: {last_error}")
    item = response.get("upload_image_response") or {}
    url = canonical_url(item.get("photobank_url"))
    if failed(client, response) or not url or not item.get("file_id"):
        raise RuntimeError(f"photobank upload failed for {path}: {refs(client, response)}")
    row = {"url": url, "file_id": str(item["file_id"]), "source": str(path), "sha256": digest, "refs": refs(client, response)}
    cache[digest] = row
    if UPLOAD_CACHE_PATH is not None:
        tmp = UPLOAD_CACHE_PATH.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, UPLOAD_CACHE_PATH)
    return row


def url_asset(key: str, url_map: dict, bank: dict, client, config, local: Path, upload_cache: dict) -> dict:
    url = canonical_url(url_map.get(key))
    indexed = bank.get(image_key(url)) if url else None
    if indexed and indexed.get("file_id") not in (None, "", "0"):
        return {**indexed, "source": str(local)}
    return upload_image(client, config, local, upload_cache)


def direct_field(root: ET.Element, field_id: str) -> ET.Element:
    found = root.find(f"./field[@id='{field_id}']")
    if found is None:
        raise KeyError(field_id)
    return found


def set_direct_value(root: ET.Element, field_id: str, text: str) -> None:
    field = direct_field(root, field_id)
    value = field.find("./value")
    if value is None:
        value = ET.SubElement(field, "value")
    value.text = str(text)


def replace_complex_value(field: ET.Element, new_value: ET.Element) -> None:
    old = field.find("./complex-value")
    if old is not None:
        field.remove(old)
    field.insert(0, new_value)


def set_attribute_values(root: ET.Element, model: str, listing_id: str) -> None:
    meta = STYLE_META[model]
    field = direct_field(root, "icbuCatProp")
    cv = ET.Element("complex-value")

    def single(fid, name, label, vid):
        node = ET.SubElement(cv, "field", {"id": fid, "name": name, "type": "singleCheck"})
        value = ET.SubElement(node, "value", {"inputValue": label})
        value.text = str(vid)

    def multi(fid, name, values):
        node = ET.SubElement(cv, "field", {"id": fid, "name": name, "type": "multiCheck"})
        vals = ET.SubElement(node, "values")
        for label, vid in values:
            value = ET.SubElement(vals, "value", {"inputValue": label})
            value.text = str(vid)

    single("p-1", "Place of Origin", "China", "100000458")
    single("p-3", "Model Number", listing_id, "-302")
    if model == "HR039":
        # The Ankle & Bootie leaf uses multi-check attributes and a different
        # option set from Walking Style Shoes.  Only submit confirmed visual
        # construction; optional unmeasured heel-height data stays omitted.
        multi("p-200000388", "Closure Type", [("Side zipper", "76674982")])
        multi("p-191290430", "Lining Material", [("Textile", "-301")])
        multi("p-20700", "Midsole Material", [("EVA", "3376399")])
        multi("p-191288212", "Season", [("All Seasons", "27034893")])
        multi("p-191290426", "Outsole Material", [("Rubber", "3338114")])
        multi("p-200000486", "Toe Style", [("Round Toe", "556500746")])
        multi("p-191288243", "Style", [("Classic", "190091255")])
        multi("p-200000475", "Boot Height", [("Ankle", "6233079")])
        multi("p-200000480", "Heel Type", [("Flat Heel", "1981567257")])
        multi("p-210194982", "Upper Material", [("Quilted Textile and Microfiber Leather", "-303")])
        multi("p-200000329", "pattern", [("Quilted", "-304")])
    else:
        single("p-200000388", "Closure Type", *meta["closure"])
        multi("p-191290430", "Lining Material", [(meta["lining"], "-301")])
        multi("p-20700", "Midsole Material", [("EVA", "3376399")])
        multi("p-210200060", "Feature", [(f, FEATURE_IDS[f]) for f in meta["features"]])
        multi("p-191288212", "Season", [("All Seasons", "27034893")])
        multi("p-191290426", "Outsole Material", [("Rubber", "3338114")])
        multi("p-200000486", "Toe Style", [("Round Toe", "556500746")])
        multi("p-191288243", "Style", [("Walking Shoes", "19077592")])
    # The category does not expose an upper-material field in its current
    # schema.  Keep the confirmed/proposed upper wording in title/details only.
    replace_complex_value(field, cv)


def set_sale_and_skus(root: ET.Element, model: str, variant: str, colors: list[dict], color_assets: list[dict]) -> None:
    sale = direct_field(root, "saleProp")
    cv = ET.Element("complex-value")
    sizes_field = ET.SubElement(cv, "field", {"id": "p-222038415", "name": "EUR Size", "type": "multiCheck"})
    sizes = ET.SubElement(sizes_field, "values")
    for size, value_id in SIZE_IDS.items():
        value = ET.SubElement(sizes, "value", {"inputValue": size})
        value.text = value_id
    color_field = ET.SubElement(cv, "field", {"id": "p-191288010", "name": "Color", "type": "multiCheck"})
    color_values = ET.SubElement(color_field, "values")
    color_ids = []
    boot_color_ids = {
        "WARM TAUPE": "5715155",      # Beige
        "CLASSIC BLACK": "3327837",   # Black
        "MUTED BURGUNDY": "3331260",  # Red
    }
    boot_color_names = {
        "WARM TAUPE": "Beige",
        "CLASSIC BLACK": "Black",
        "MUTED BURGUNDY": "Red",
    }
    for index, (color, asset) in enumerate(zip(colors, color_assets), 1):
        value_id = boot_color_ids.get(color["name"].upper()) if model == "HR039" else None
        value_id = value_id or str(-400 - index)
        color_ids.append(value_id)
        color_label = boot_color_names.get(color["name"].upper(), color["name"].title()) if model == "HR039" else color["name"].title()
        value = ET.SubElement(color_values, "value", {"inputValue": color_label, "img": asset["url"]})
        value.text = value_id
    replace_complex_value(sale, cv)

    sku = direct_field(root, "sku")
    for child in list(sku.findall("./complex-values")):
        sku.remove(child)
    insert_at = 0
    for color, color_id in zip(colors, color_ids):
        cname = boot_color_names.get(color["name"].upper(), color["name"].title()) if model == "HR039" else color["name"].title()
        for size, size_id in SIZE_IDS.items():
            item = ET.Element("complex-values")
            ET.SubElement(item, "field", {"id": "price", "name": "Single piece price (USD)", "type": "input"})
            stock = ET.SubElement(item, "field", {"id": "skuStock", "name": "Inventory", "type": "multiInput"})
            values = ET.SubElement(stock, "values")
            v = ET.SubElement(values, "value", {"srcValue": "999", "warehouseCode": "CN_LOCAL_01"})
            v.text = "999"
            outer = ET.SubElement(item, "field", {"id": "skuOuterId", "name": "Commodity code", "type": "input"})
            ET.SubElement(outer, "value").text = f"{model}-{variant}-{re.sub(r'[^A-Z0-9]+', '-', color['name'].upper()).strip('-')}-{size}"
            ET.SubElement(item, "field", {"id": "outerSupplyId", "name": "supply id", "type": "input"})
            props = ET.SubElement(item, "field", {"id": "props", "name": "", "type": "multiInput"})
            pvalues = ET.SubElement(props, "values")
            pv = ET.SubElement(pvalues, "value", {"propValueId": color_id, "propId": "191288010", "propName": "p-191288010", "propValueName": cname})
            pv.text = f"191288010:{color_id}"
            pv = ET.SubElement(pvalues, "value", {"propValueId": size_id, "propId": "222038415", "propName": "p-222038415", "propValueName": size})
            pv.text = f"222038415:{size_id}"
            sku.insert(insert_at, item)
            insert_at += 1


def set_main_images(root: ET.Element, assets: list[dict]) -> None:
    field = direct_field(root, "scImages")
    cv = ET.Element("complex-value")
    for index, asset in enumerate(assets):
        node = ET.SubElement(cv, "field", {"id": f"scImages_{index}", "type": "input"})
        value = ET.SubElement(node, "value", {"fileFlag": "no", "fileId": str(asset["file_id"])})
        value.text = asset["url"].replace("https:", "")
    replace_complex_value(field, cv)


def set_gallery(root: ET.Element, field_id: str, assets: list[dict], roles: list[tuple[int, str]]) -> None:
    field = direct_field(root, field_id)
    for old in list(field.findall("./complex-values")):
        field.remove(old)
    insert_at = 0
    for asset, (role_id, role_name) in zip(assets, roles):
        item = ET.Element("complex-values")
        images = ET.SubElement(item, "field", {"id": "images", "type": "multiComplex"})
        image = ET.SubElement(images, "complex-values")
        url = ET.SubElement(image, "field", {"id": "imageURL", "type": "input"})
        ET.SubElement(url, "value").text = asset["url"].replace("https:", "")
        gallery = ET.SubElement(item, "field", {"id": "gallery", "type": "singleCheck"})
        value = ET.SubElement(gallery, "value", {"displayName": role_name})
        value.text = str(role_id)
        field.insert(insert_at, item)
        insert_at += 1


def set_keywords(root: ET.Element, keywords: str) -> None:
    field = direct_field(root, "productKeywords")
    old = field.find("./complex-value")
    if old is not None:
        field.remove(old)
    cv = ET.Element("complex-value")
    node = ET.SubElement(cv, "field", {"id": "productKeywords_0", "type": "input"})
    ET.SubElement(node, "value").text = keywords
    field.insert(0, cv)


def set_ladder_prices(root: ET.Element, model: str, variant: str) -> None:
    # Small truthful style-dependent variation; MOQ and structure stay fixed.
    variant_offset = {"A": 0.00, "B": 0.02, "C": -0.01}[variant]
    offset = (int(model[-1]) - 1) * 0.01 + variant_offset
    prices = [(2, 9.49 + offset), (50, 9.19 + offset), (100, 9.09 + offset)]
    field = direct_field(root, "ladderPrice")
    cv = ET.Element("complex-value")
    for index, (quantity, price) in enumerate(prices):
        outer = ET.SubElement(cv, "field", {"id": f"ladderPrice_{index}", "type": "complex"})
        inner = ET.SubElement(outer, "complex-value")
        q = ET.SubElement(inner, "field", {"id": "quantity", "type": "input"})
        ET.SubElement(q, "value").text = str(quantity)
        p = ET.SubElement(inner, "field", {"id": "price", "type": "input"})
        ET.SubElement(p, "value").text = f"{price:.2f}"
    replace_complex_value(field, cv)


# Load the sibling contract by path: continuation/external spec imports need
# not add this script directory to sys.path.
_contract_spec = importlib.util.spec_from_file_location(
    "beiqiang_schema_publish_contract", Path(__file__).with_name("schema_publish_contract.py"))
assert _contract_spec and _contract_spec.loader
_contract = importlib.util.module_from_spec(_contract_spec)
_contract_spec.loader.exec_module(_contract)
values_only = _contract.values_only
classify_result = _contract.classify_result
safe_exception_evidence = _contract.safe_exception_evidence
require_differentiation_review = _contract.require_differentiation_review
verify_content = _contract.verify_content
verify_content_details = _contract.verify_content_details
field_snapshot = _contract.field_snapshot
prepare_scoped_listing = _contract.prepare_scoped_listing
post_publish_acceptance = _contract.post_publish_acceptance
serialize_product_attribute = _contract.serialize_product_attribute
serialize_product_model = _contract.serialize_product_model
validate_model_payload = _contract.validate_model_payload
validate_create_inventory_payload = _contract.validate_create_inventory_payload


def extract_product_id(response: dict) -> str | None:
    for key in ("product_id", "productId", "id"):
        if response.get(key):
            return str(response[key])
    data = response.get("data")
    if isinstance(data, (str, int)) and str(data).isdigit():
        return str(data)
    if isinstance(data, dict):
        for key in ("product_id", "productId", "id"):
            if data.get(key):
                return str(data[key])
    model = response.get("model")
    if isinstance(model, dict):
        for key in ("product_id", "productId", "id"):
            if model.get(key):
                return str(model[key])
    return None


def prepare_listing(model: str, variant: str, client, config, url_map: dict, bank: dict, upload_cache: dict) -> dict:
    folders = product_dirs()
    matrix = rows_variant(variant)[model]
    folder = folders[model]
    listing_id = f"{model}-{variant}"
    detail = json.loads((folder / "detail_config.json").read_text(encoding="utf-8-sig"))
    first = upload_image(client, config, build_b2b_m1(model, folder, variant, matrix), upload_cache)

    main_keys = [f"{model}_main_01_hero", f"{model}_main_03_outsole", f"{model}_main_04_upper", f"{model}_main_05_lifestyle", f"{model}_main_06_heel"]
    main_locals = [folder / "01_主图" / f"{key}.png" for key in main_keys]
    mains = [first] + [url_asset(key, url_map, bank, client, config, local, upload_cache) for key, local in zip(main_keys, main_locals)]
    detail_files = sorted((folder / "02_详情页").glob(f"{model}_d0[1-4]_*.png"))
    details = [url_asset(path.stem, url_map, bank, client, config, path, upload_cache) for path in detail_files]
    color_assets = [url_asset(Path(row["image"]).stem, url_map, bank, client, config, folder / row["image"], upload_cache) for row in detail["colors"]]
    if len(mains) != 6 or len(details) != 4 or len(color_assets) != 3:
        raise RuntimeError(f"asset gate failed for {model}: mains={len(mains)} details={len(details)} colors={len(color_assets)}")
    main_keys_seen = {image_key(row["url"]) for row in mains}
    detail_keys_seen = {image_key(row["url"]) for row in details}
    if main_keys_seen & detail_keys_seen:
        raise RuntimeError(f"main/detail duplicate gate failed for {model}")

    category_id = CATEGORY_BY_STYLE.get(model, CATEGORY_ID)
    root = ET.fromstring(SOURCE_XML.read_text(encoding="utf-8"))
    set_direct_value(root, "catId", str(category_id))
    final_title = f"{matrix['Title']} Model {listing_id}"
    if len(final_title.encode("ascii")) > 128:
        raise RuntimeError(f"title exceeds 128 bytes for {model}: {final_title}")
    set_direct_value(root, "productTitle", final_title)
    set_keywords(root, matrix["Keywords"])
    set_direct_value(root, "textDesc", matrix.get("ProductHighlights") or HIGHLIGHTS)
    set_attribute_values(root, model, listing_id)
    set_sale_and_skus(root, model, variant, detail["colors"], color_assets)
    set_main_images(root, mains)
    set_gallery(root, "detailImage", details, DETAIL_ROLES)
    set_ladder_prices(root, model, variant)
    # Keep the store baseline logistics and company proof modules from the
    # verified source product.  Do not carry its product video to another shoe.
    xml_root = values_only(root)
    xml_text = ET.tostring(xml_root, encoding="unicode")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / f"{listing_id}_publish.xml").write_text(xml_text, encoding="utf-8")
    return {
        "model": model, "listing_id": listing_id, "category_id": category_id, "title": final_title, "keywords": matrix["Keywords"],
        "main": mains, "details": details, "colors": [{**row, "asset": asset} for row, asset in zip(detail["colors"], color_assets)],
        "xml": xml_text,
    }


def api_submit(client, config, listing: dict, draft: bool, update_product_id: str | None = None,
               formal_readback: dict | None = None, *, publish_draft_id: str | None = None,
               draft_readback: dict | None = None) -> dict:
    """One write attempt; an exception never triggers another creation/update.

    A separately collected formal snapshot may be provided for value checks.
    Without it, content remains pending even after business acceptance.
    """
    operation = "update" if update_product_id else ("createDraft" if draft else "create")
    if draft and update_product_id:
        raise ValueError('draft creation and update target are mutually exclusive')
    if listing.get("operation") != operation or not listing.get("prepared_from_current_schema"):
        raise ValueError("submission requires an explicit listing prepared against current Schema")
    root = ET.fromstring(listing["xml"])
    allowed = set(listing["field_ids"]) | set(listing["dependency_ids"])
    if {f.get("id") for f in root.findall("./field")} != allowed:
        raise ValueError("unrelated or missing fields in submission payload")
    if update_product_id and str(listing.get("target_product_id")) != str(update_product_id):
        raise ValueError("listing target differs from update product ID")
    actual_expected = {k: v for k, v in field_snapshot(root).items() if k in listing['field_ids']}
    if actual_expected != listing.get('expected_fields'):
        raise ValueError('payload differs from the reviewed expected fields')
    if operation != 'update' or listing.get('model_serialization'):
        validate_model_payload(root, listing.get('model_serialization'))
    if operation != 'update':
        validate_create_inventory_payload(root, listing.get('inventory_input'))
    require_differentiation_review(root, listing, operation=operation)
    category_id = int(listing.get("category_id") or CATEGORY_ID)
    if publish_draft_id is not None:
        if operation != 'create' or not str(publish_draft_id).isdigit():
            raise ValueError('draft promotion requires formal create and an explicit numeric draft ID')
        evidence = draft_readback or {}
        if str(evidence.get('product_id')) != str(publish_draft_id) or not evidence.get('request_id') or not evidence.get('xml'):
            raise ValueError('draft promotion requires independent target-bound draft render evidence')
        observed = datetime.fromisoformat(evidence['acquired_at'])
        if observed.tzinfo is None or not 0 <= (datetime.now(timezone.utc)-observed).total_seconds() <= 86400:
            raise ValueError('draft render evidence must be recent and timezone-aware')
        draft_root = ET.fromstring(evidence['xml'])
        model = draft_root.find("./field[@id='icbuCatProp']/complex-value/field[@id='p-3']/value")
        if model is None or model.get('inputValue') != listing['model_serialization']['expected_model']:
            raise ValueError('draft model differs from prepared formal model')
    if update_product_id:
        method = "alibaba.icbu.product.schema.update"
        payload = {"cat_id": category_id, "language": "en_US", "product_id": int(update_product_id), "xml": listing["xml"]}
    else:
        method = "alibaba.icbu.product.schema.add.draft" if draft else "alibaba.icbu.product.schema.add"
        payload = {"cat_id": category_id, "language": "en_US", "xml": listing["xml"]}
        if publish_draft_id is not None:
            payload['product_id'] = int(publish_draft_id)
    attempted_at = datetime.now(timezone.utc).isoformat()
    try:
        # The server may have committed a timed-out mutation. No automatic retry.
        response = client.top_call(config, method, {"param_product_top_publish_request": payload})
    except Exception as exc:
        failure_evidence = safe_exception_evidence(exc, config)
        return {"method": method, "operation": operation, "status": "write_outcome_unknown",
                "content_status": "unverified_content", "response": None,
                "post_publish_acceptance": post_publish_acceptance({'formal_fields':False}) if operation != 'createDraft' else {'phase':'before_publish','status':'not_applicable_yet','target_score':5.0},
                "refs": failure_evidence["business_refs"], "product_id": update_product_id,
                "attempted_at": attempted_at, "expected_fields": listing['expected_fields'],
                "inventory_input": listing.get('inventory_input'),
                "exception_type": type(exc).__name__, "failure_evidence": failure_evidence,
                "task_pack":listing.get("task_pack"),"replacement_plan":listing.get("replacement_plan"),
                "replacement_transition": (listing.get("differentiation_review") or {}).get("replacement_transition"),
                "next_step": "stop_and_reconcile_target_or_creation_before_any_retry"}
    status = classify_result(operation, response)
    expected = listing["expected_fields"]
    verification = verify_content_details(status, expected, formal_readback, operation=operation)
    content_status = verification['content_status']
    replacement_plan=deepcopy(listing.get('replacement_plan'))
    if replacement_plan:
        replacement_plan['new_product_id']=extract_product_id(response) if status=='submitted_needs_readback' else None
        replacement_plan['new_submission_status']=status
    return {"method": method, "operation": operation, "status": status,
            "content_status": content_status, "expected_fields": expected,
            "sku_verification": verification["sku_verification"],
            "task_pack":listing.get("task_pack"),"replacement_plan":replacement_plan,
            "replacement_transition": (listing.get("differentiation_review") or {}).get("replacement_transition"),
            "inventory_input": listing.get('inventory_input'),
            "post_publish_acceptance": post_publish_acceptance({'formal_fields': content_status == 'formal_fields_verified'}) if operation != 'createDraft' else {'phase':'before_publish','status':'not_applicable_yet','target_score':5.0},
            "attempted_at": attempted_at,
            "response": response, "refs": refs(client, response) if isinstance(response, dict) else {},
            "product_id": (extract_product_id(response) if isinstance(response, dict) else None) or update_product_id}


def load_local_differentiation_review(path, manifest):
    """Read saved catalog pages and selected projections of existing source records."""
    name = manifest.get('differentiation_review')
    if not name:return None
    review_path = path.parent / name
    raw = review_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest.get('differentiation_review_sha256'):
        raise ValueError('differentiation review hash differs from manifest')
    context = json.loads(raw)
    provenance = []
    catalog = {}
    reported_totals, saved_rows = set(), 0
    acceptance_records=[]; accepted_payloads=[]; acceptance_paths=set()
    selected = context.get('source_records') or {}
    for source in context.get('evidence_files') or []:
        file = review_path.parent / source['path']
        data = file.read_bytes()
        if hashlib.sha256(data).hexdigest() != source.get('sha256'):
            raise ValueError('differentiation evidence hash differs: '+str(file))
        provenance.append({'path':str(file.resolve()),'sha256':source['sha256'],'kind':source.get('kind')})
        if source.get('kind')=='replacement_accepted_payload':
            accepted_payloads.append(data.decode('utf-8-sig'))
        if source.get('kind')=='replacement_acceptance_record':
            acceptance_paths.add(str(file.resolve()))
            record=json.loads(data).get('replacement_content_acceptance')
            if not isinstance(record,dict):continue # A success-only receipt is never acceptance.
            formal=record.get('formal_readback') or {}
            if not formal.get('schema_file'):continue # Require actual saved formal XML, never inline review self-report.
            if formal.get('schema_file'):
                schema_file=file.parent/formal['schema_file'];schema_data=schema_file.read_bytes()
                if hashlib.sha256(schema_data).hexdigest()!=formal.get('schema_sha256'):
                    raise ValueError('replacement formal evidence hash differs')
                formal=dict(formal,xml=schema_data.decode('utf-8'))
            media=dict(record.get('media_acceptance') or {})
            checks=[]
            for check in media.get('checks') or []:
                check=dict(check)
                for prefix in ('source','actual'):
                    if check.get(prefix+'_file'):
                        artifact=file.parent/check[prefix+'_file'];artifact_data=artifact.read_bytes()
                        if hashlib.sha256(artifact_data).hexdigest()!=check.get(prefix+'_sha256'):
                            raise ValueError('replacement media evidence hash differs')
                        check[prefix+'_bytes']=artifact_data
                checks.append(check)
            media['checks']=checks
            acceptance_records.append(dict(record,formal_readback=formal,media_acceptance=media))
        if source.get('kind') != 'catalog_snapshot':continue
        saved = json.loads(data)
        if not isinstance(saved,dict) or not ('products' in saved or 'product' in saved):
            raise ValueError('local catalog snapshot has no supported product records: '+str(file))
        if type(saved.get('total_item')) is int:reported_totals.add(saved['total_item'])
        products = saved.get('products') or ([saved['product']] if 'product' in saved else [])
        saved_rows += len(products)
        for product in products:
            product_id = str(product.get('id') or product.get('product_id') or '')
            if not product_id:continue
            model = product.get('red_model') or next((a.get('value_name') for a in product.get('attributes',[])
                if a.get('attribute_name') == 'Model Number'),None)
            images = (product.get('main_image') or {}).get('images') or []
            metadata = selected.get(product_id) or {}
            # Source metadata cannot overwrite actual catalog ID/model/hero.
            record = {k:metadata[k] for k in ('source','search_intent','hero_review','existing_family') if k in metadata}
            record.update(product_id=product_id,model_number=model,title=product.get('subject'),
                hero_url=images[0] if images else None,snapshot_request_id=saved.get('request_id'))
            catalog[product_id]=record
    if not any(p.get('kind')=='catalog_snapshot' for p in provenance):
        raise ValueError('differentiation review requires existing local catalog snapshots')
    if not any(p.get('kind')=='source_register' for p in provenance):
        raise ValueError('differentiation review requires existing source registry evidence')
    replacement=context.get('replacement')
    requested_old=manifest.get('replacement_source_product_id')
    if requested_old is not None or replacement is not None:
        if not replacement or requested_old is None or str(replacement.get('replacement_source_product_id'))!=str(requested_old):
            raise ValueError('replacement requires explicit matching manifest/review source product ID')
        if len(accepted_payloads)!=1:
            raise ValueError('replacement requires exactly one hash-verified accepted payload evidence file')
        replacement=dict(replacement,accepted_payload_xml=accepted_payloads[0],
            acceptance_records=acceptance_records)
        mapping=replacement.get('acceptance_map') or {}
        linked={str((review_path.parent/entry).resolve()) for entry in mapping.get('evidence') or []}
        if not linked or not linked<=acceptance_paths:
            raise ValueError('replacement acceptance map must link the hash-verified acceptance records')
    return {'replacement':replacement,'candidate':context.get('candidate') or {},'catalog':list(catalog.values()),
            'provenance':{'review_path':str(review_path.resolve()),'review_sha256':manifest['differentiation_review_sha256'],
                          'files':provenance,'catalog_records':len(catalog),'saved_rows':saved_rows,
                          'reported_totals':sorted(reported_totals),
                          'counts_match_reported_total':len(reported_totals)==1 and len(catalog)==next(iter(reported_totals)),
                          'observed_at':context.get('observed_at'),
                          'coverage_limit':context.get('coverage_limit')}}


def load_task_pack_contract(path, manifest, context, operation, product_id):
    """Explicit JSON projection of canonical A-G taskpack, bound to its original.

    Does not parse prose into facts, write product state, or retire old products.
    Strategic different-shoe replacement never receives same-shoe duplicate waiver.
    """
    name=manifest.get('task_pack')
    if not name:
        if manifest.get('task_pack_sha256'):raise ValueError('task_pack path required with hash')
        return context,None,None
    file=path.parent/name;raw=file.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=manifest.get('task_pack_sha256'):raise ValueError('task_pack hash differs from manifest')
    pack=json.loads(raw);provenance=[];mappings=[];kinds=set()
    canonical=Path(__file__).resolve().parents[3]/'02_Alibaba运营/05_扩品工程/工厂店外新款数据采集模板.md'
    for evidence in pack.get('evidence_files') or []:
        original=file.parent/evidence['path'];data=original.read_bytes()
        if hashlib.sha256(data).hexdigest()!=evidence.get('sha256'):raise ValueError('task_pack evidence hash differs')
        kind=evidence.get('kind');kinds.add(kind)
        if kind=='task_pack_template' and original.resolve()!=canonical.resolve():raise ValueError('task_pack must use canonical A-G collection template')
        if kind=='replacement_mapping':mappings.extend(json.loads(data).get('rows') or [])
        provenance.append({'path':str(original.resolve()),'sha256':evidence['sha256'],'kind':kind})
    if not {'task_pack_template','task_pack_document'}<=kinds:raise ValueError('task_pack requires hash-bound canonical template and single-product document')
    role=pack.get('role');phase=pack.get('phase')
    if role not in ('NEW','REPLACE','OPTIMIZE','TEST') or not all(pack.get(k) for k in ('task_id','phase','writer','next_action')):raise ValueError('task_pack explicit role/phase/task/writer/next action required')
    if not pack.get('public_model') or (manifest.get('expected_model') is not None and pack['public_model']!=manifest['expected_model']) or pack.get('category_id')!=manifest.get('category_id'):raise ValueError('task_pack model/category differs from manifest')
    assigned=pack.get('product_id')
    if operation in ('create','createDraft') and (assigned is not None or role=='OPTIMIZE'):raise ValueError('task_pack already has product ID or optimize role; never recreate published product')
    if operation in ('update','inspect_existing') and (assigned is None or str(assigned)!=str(product_id)):raise ValueError('task_pack update must bind existing product ID')
    if not context:raise ValueError('task_pack requires existing catalog/source/visual differentiation review')
    context=dict(context);candidate=dict(context.get('candidate') or {})
    for key,target in [('source_identity','source'),('search_intent','search_intent'),('hero_review','hero_review')]:
        value=pack.get(key)
        if not isinstance(value,dict) or not value:raise ValueError('task_pack missing factual projection: '+key)
        if candidate.get(target) is not None and candidate[target]!=value:raise ValueError('task_pack factual projection conflicts with differentiation review: '+key)
        candidate[target]=value
    context['candidate']=candidate
    plan=pack.get('replacement_plan')
    if role=='REPLACE' and not plan:raise ValueError('REPLACE task_pack requires explicit replacement_plan')
    if plan:
        if role!='REPLACE' and not (operation=='inspect_existing' and role=='NEW' and assigned):raise ValueError('replacement_plan requires REPLACE role; existing NEW history may only inspect its subsequent reservation')
        old_ids=[str(x) for x in plan.get('old_product_ids') or []]
        if len(old_ids)!=1 or not old_ids[0].isdigit():raise ValueError('strategic task_pack currently requires exact one-to-one old_product_ids')
        selected=[row for row in mappings if str(row.get('candidate'))==str(plan.get('candidate')) and str(row.get('old_product_id'))==old_ids[0]]
        if len(selected)!=1:raise ValueError('task_pack old IDs not bound to one existing strategic mapping row')
        row=selected[0]
        # Read compatibility for the existing abbreviated strategic label. Both
        # denote different-shoe plans; all target/protection/source checks below
        # still apply. Never edit the business mapping or grant a duplicate waiver.
        if row.get('match_type') not in {'STRATEGIC_RETIRE_AND_REAL_SOURCE_REPLACEMENT_NOT_IDENTICAL_SHOE', 'STRATEGIC_RETIRE_NOT_IDENTICAL_SHOE'}:raise ValueError('task_pack mapping is not strategic different-shoe replacement; use existing clean-rebuild contract separately')
        if row.get('protected') is not False or row.get('growth_tier')!='普通品' or not row.get('authorization_scope'):raise ValueError('strategic mapping target is protected/unknown or lacks scoped authorization')
        if row.get('source_url')!=pack['source_identity'].get('reference'):raise ValueError('strategic mapping candidate source differs from task_pack')
        if operation in ('create','createDraft') and row.get('new_product_id') is not None:raise ValueError('strategic mapping already has new ID; never recreate historical successful product')
        if operation in ('update','inspect_existing') and str(row.get('new_product_id'))!=str(product_id):raise ValueError('strategic mapping update new ID mismatch')
        if context.get('replacement') or manifest.get('replacement_source_product_id') is not None:raise ValueError('strategic replacement cannot use same-shoe duplicate waiver')
        known={str(r.get('product_id')) for r in context.get('catalog') or []}
        if not set(old_ids)<=known:raise ValueError('task_pack selected old ID missing from scoped catalog evidence')
        siblings=row.get('retained_siblings') or []
        if set(old_ids)&{str(r.get('product_id')) for r in siblings}:raise ValueError('strategic old target conflicts with retained sibling')
        plan={'match_type':row['match_type'],'old_product_ids':old_ids,'new_product_id':assigned,
              'phase':'OLD_RETIREMENT_PENDING_NO_AUTOMATIC_ACTION','old_action':row.get('old_action','UNKNOWN'),
              'protected':row['protected'],'classification_observed_at':row.get('growth_observed_at_utc'),
              'reservation_status':row.get('reservation_status'),'authorization_scope':row['authorization_scope'],
              'retained_siblings':siblings,'whole_family_complete':False,
              'finish_requirements':{'target_score':5.0,'full_content_acceptance':True,'public_qa':True,
                 'fresh_old_classification_associations_and_owner_ack':True,'separate_authorized_old_off':True},
              'limits':'Binding only; no duplicate waiver, no automatic old-off, no order/history transfer or inquiry/promotion clearance.'}
    summary={'task_id':pack['task_id'],'role':role,'phase':phase,'writer':pack['writer'],'next_action':pack['next_action'],
             'product_id':assigned,'path':str(file.resolve()),'sha256':manifest['task_pack_sha256'],'evidence_files':provenance}
    return context,summary,plan


def inspect_existing_submission_manifest(path, product_id):
    """Read-only evidence binding for an already-created product; never submit."""
    from schema_publish_contract import prepare_differentiation_review
    manifest=json.loads(path.read_text(encoding='utf-8-sig'))
    if not product_id or str(manifest.get('existing_product_id'))!=str(product_id):raise ValueError('inspect-existing requires explicitly bound existing product ID')
    def bound_file(name):
        file=path.parent/manifest[name];raw=file.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=manifest.get(name+'_sha256'):raise ValueError('existing evidence hash differs: '+name)
        return file,raw
    original_path,raw=bound_file('original_manifest');original=json.loads(raw)
    receipt_path,raw=bound_file('existing_submission_receipt');receipt=json.loads(raw)
    if str(extract_product_id(receipt))!=str(product_id) or receipt.get('status')!='submitted_needs_readback':raise ValueError('existing original submission receipt not bound/accepted')
    expected_path=original_path.parent/original['payload_xml'];expected_bytes=expected_path.read_bytes()
    if hashlib.sha256(expected_bytes).hexdigest()!=manifest.get('existing_payload_sha256'):raise ValueError('existing payload hash differs')
    payload=ET.fromstring(expected_bytes)
    if manifest.get('category_id')!=original.get('category_id') or manifest.get('expected_model')!=original.get('expected_model'):raise ValueError('existing model/category differs from original manifest')
    context,pack,plan=load_task_pack_contract(path,manifest,load_local_differentiation_review(path,manifest),'inspect_existing',product_id)
    review=prepare_differentiation_review(payload,context,operation='update',target_product_id=product_id)
    return {'status':'EXISTING_EVIDENCE_BOUND_NEW_CREATION_DISABLED','existing_product_id':str(product_id),
            'create_allowed':False,'platform_calls':0,'task_pack':pack,'replacement_plan':plan,
            'differentiation_review':review,'original_manifest':str(original_path.resolve()),
            'original_manifest_sha256':manifest['original_manifest_sha256'],
            'existing_submission_receipt':str(receipt_path.resolve()),
            'existing_submission_receipt_sha256':manifest['existing_submission_receipt_sha256'],
            'historical_result_limits':'Binding existing evidence does not rerun creation, downgrade prior verified results, revalidate all catalog, complete keyword followup or authorize old-off.'}


def load_submission_manifest(path: Path, operation: str, product_id: str | None):
    """Require reviewed target data and bind current Schema to its provenance."""
    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    if manifest.get("operation") != operation or not manifest.get("facts_reviewed"):
        raise ValueError("manifest must identify operation and reviewed product facts")
    if not manifest.get("source_evidence"):
        raise ValueError("manifest must identify current product/source evidence")
    if operation == "update" and str(manifest.get("product_id")) != str(product_id):
        raise ValueError("manifest must be bound to the requested product ID")
    schema_path = path.parent / manifest["current_schema"]
    payload_path = path.parent / manifest["payload_xml"]
    schema_bytes = schema_path.read_bytes()
    if hashlib.sha256(schema_bytes).hexdigest() != manifest.get("current_schema_sha256"):
        raise ValueError("current Schema hash differs from manifest")
    if not manifest.get("schema_request_id") or not manifest.get("schema_acquired_at"):
        raise ValueError("current Schema requires request ID and acquisition timestamp")
    acquired_at = datetime.fromisoformat(manifest['schema_acquired_at'])
    if acquired_at.tzinfo is None:
        raise ValueError('Schema acquisition timestamp must have a timezone')
    age = (datetime.now(timezone.utc) - acquired_at).total_seconds()
    if age < 0 or age > 24 * 60 * 60:
        raise ValueError('retrieve the current Schema again; this entry accepts snapshots within 24 hours')
    context,task_pack,replacement_plan=load_task_pack_contract(path,manifest,load_local_differentiation_review(path,manifest),operation,product_id)
    listing = prepare_scoped_listing(ET.fromstring(schema_bytes), ET.parse(payload_path).getroot(),
        operation=operation, category_id=manifest["category_id"], target_product_id=product_id,
        field_ids=manifest.get("field_ids", []), dependency_ids=manifest.get("dependency_ids", []),
        expected_model=manifest.get('expected_model'),
        differentiation_context=context)
    listing["task_pack"]=task_pack
    listing["replacement_plan"]=replacement_plan
    listing["schema_provenance"] = {k: manifest[k] for k in
        ("schema_request_id", "schema_acquired_at", "current_schema_sha256", "source_evidence")}
    return listing


def atomic_verification_receipt(path, receipt):
    """Commit a separate verification ledger; never replace submission evidence."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                prefix=path.name + '.', suffix='.tmp', delete=False) as file:
            temporary = Path(file.name)
            json.dump(receipt, file, ensure_ascii=False, indent=2)
            file.write('\n')
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def run_verify_cli(args):
    if not args.receipt or not args.formal_readback or not args.product_id:
        raise ValueError('verify requires --receipt, --formal-readback and --product-id')
    receipt_path = Path(args.receipt)
    verification_path = Path(args.verification_receipt) if args.verification_receipt else receipt_path.with_name(receipt_path.name + '.verification.json')
    evidence_path = Path(args.formal_readback)
    evidence = json.loads(evidence_path.read_text(encoding='utf-8-sig'))
    protected = (receipt_path, evidence_path, evidence_path.parent / evidence['schema_file'])
    if any(verification_path.resolve() == path.resolve() for path in protected):
        raise ValueError('verification output must be separate from original submission/readback evidence')
    # Serialize read/compare/commit so concurrent verifiers cannot discard the
    # first binding. A crash leaves the lock for explicit reconciliation.
    lock_path = verification_path.with_name(verification_path.name + '.lock')
    with lock_path.open('x', encoding='utf-8'):
        pass
    try:
        return verify_and_save(args, receipt_path, verification_path)
    finally:
        lock_path.unlink()


def verify_and_save(args, receipt_path, verification_path):
    if not args.receipt or not args.formal_readback or not args.product_id:
        raise ValueError("verify requires --receipt, --formal-readback and --product-id")
    source_bytes = receipt_path.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    receipt = json.loads(source_bytes.decode('utf-8-sig'))
    prior = json.loads(verification_path.read_text(encoding='utf-8')) if verification_path.exists() else None
    if prior is not None and prior.get('submission_receipt_sha256') != source_hash:
        raise ValueError('verification ledger belongs to a different/changed submission receipt')
    if str(receipt.get("product_id")) != str(args.product_id):
        raise ValueError("receipt does not match formal-readback target")
    evidence_path = Path(args.formal_readback)
    evidence = json.loads(evidence_path.read_text(encoding='utf-8-sig'))
    if str(evidence.get('product_id')) != str(args.product_id) or not evidence.get('request_id'):
        raise ValueError('formal evidence must identify target and independent read request')
    acquired = datetime.fromisoformat(evidence['acquired_at'])
    attempted = datetime.fromisoformat(receipt['attempted_at'])
    if acquired.tzinfo is None or acquired <= attempted:
        raise ValueError('formal evidence must be acquired after this submission')
    formal_bytes = (evidence_path.parent / evidence['schema_file']).read_bytes()
    if hashlib.sha256(formal_bytes).hexdigest() != evidence.get('schema_sha256'):
        raise ValueError('formal Schema hash differs from evidence')
    formal = field_snapshot(ET.fromstring(formal_bytes))
    operation = receipt.get('operation') or {v:k for k,v in _contract.METHODS.items()}.get(receipt.get('method'))
    if operation is None:
        raise ValueError('verify receipt must identify its operation')
    previous_skus = receipt.get('sku_verification') or {}
    established = prior.get('established_sku_bindings') if prior else None
    if established is None and previous_skus.get('status') == 'verified':
        established = previous_skus.get('bindings')
    versioned_content = None
    profile = evidence.get('content_version')
    if profile is not None:
        def read_bound(name):
            file = evidence_path.parent / profile[name + '_file']
            raw = file.read_bytes()
            if hashlib.sha256(raw).hexdigest() != profile.get(name + '_sha256'):
                raise ValueError('content-version evidence hash differs: ' + name)
            return json.loads(raw.decode('utf-8-sig'))
        saved_get = read_bound('formal_get')
        saved_public = read_bound('public_text')
        public_text = ' '.join(str(r.get('name','')) for r in saved_public.get('rows',[]) if not r.get('offscreen'))
        versioned_content = _contract.evaluate_versioned_content(
            ET.fromstring(formal_bytes), saved_get.get('response') or saved_get, public_text,
            product_id=args.product_id, category_id=profile['category_id'],
            editor_observation_id=profile['editor_observation_id'], observed_at=evidence['acquired_at'])
    verification = verify_content_details(receipt['status'], receipt['expected_fields'], formal,
        operation=operation, sku_bindings=established, versioned_content=versioned_content)
    receipt.update(verification)
    checks = dict(evidence.get('content_checks') or {})
    checks['formal_fields'] = receipt['content_status'] == 'formal_fields_verified'
    if operation == 'create' and 'sku' in receipt['expected_fields']:
        # API identity binding is derived, not accepted from a caller flag.
        # Other image/source/public checks remain independently evidenced.
        checks['sku_binding'] = (receipt.get('sku_verification') or {}).get('status') == 'verified'
    score = evidence.get('post_publish_score') or {}
    receipt['post_publish_acceptance'] = post_publish_acceptance(checks,
        actual_score=score.get('actual_score'), observed_at=score.get('observed_at'),
        score_source=score.get('score_source'), diagnostics=score.get('diagnostics'),
        versioned_content=versioned_content)
    if score.get('actual_score') is not None:
        try:
            score_observed = datetime.fromisoformat(score.get('observed_at'))
            if score_observed.tzinfo is None or score_observed <= attempted:
                receipt['post_publish_acceptance']['score_status']='pending_score_evidence'
                receipt['post_publish_acceptance']['overall_status']='PENDING_SCORE_EVIDENCE'
        except (ValueError,TypeError):
            pass # The shared gate already classifies missing/bad timestamps.
    current_skus = receipt.get('sku_verification') or {}
    if established is None and current_skus.get('status') == 'verified':
        established = current_skus['bindings']
    # Keep the first verified binding even after a later failed read. A failure
    # must not reset identity history and let a third call accept the swapped IDs.
    receipt['established_sku_bindings'] = established
    receipt['submission_receipt_path'] = str(receipt_path.resolve())
    receipt['submission_receipt_sha256'] = source_hash
    receipt['verification_receipt_path'] = str(verification_path.resolve())
    receipt['formal_readback_provenance'] = {
        'path':str(evidence_path.resolve()), 'request_id':evidence['request_id'],
        'acquired_at':evidence['acquired_at'], 'schema_sha256':evidence['schema_sha256']}
    atomic_verification_receipt(verification_path, receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0 if receipt['post_publish_acceptance']['overall_status'] == 'PASS' else 2


def run_scoped_cli(args):
    """Live modes bypass the historical batch builder and its inherited defaults."""
    if args.mode == 'verify':
        return run_verify_cli(args)
    if not args.input_manifest or not args.receipt:
        raise ValueError("live mode requires --input-manifest and --receipt; legacy batch inputs are not a write source")
    if args.mode == "update" and not args.product_id:
        raise ValueError("update requires --product-id")
    operation = {"draft": "createDraft", "publish": "create", "update": "update"}[args.mode]
    # Validate all inputs before loading credentials or invoking any client.
    listing = load_submission_manifest(Path(args.input_manifest), operation, args.product_id)
    require_differentiation_review(ET.fromstring(listing['xml']), listing, operation=operation)
    receipt_path = Path(args.receipt)
    # Reserve the ledger before a possible write; repeating the same CLI command
    # must reconcile its existing receipt rather than create another product.
    with receipt_path.open('x', encoding='utf-8') as file:
        json.dump({'status':'write_attempt_reserved','operation':operation,
                   'product_id':args.product_id,'expected_fields':listing['expected_fields'],
                   'inventory_input':listing.get('inventory_input')},file,ensure_ascii=False,indent=2)
    client = load_client()
    config = client.load_config(CONFIG_PATH)
    result = api_submit(client, config, listing, draft=args.mode == "draft",
                        update_product_id=args.product_id if args.mode == "update" else None)
    receipt_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: result.get(k) for k in ("method","status","content_status","product_id")}, ensure_ascii=False))
    if result["status"] not in ("draft_created_needs_readback", "submitted_needs_readback"):
        return 1
    # Business acceptance is a pending delivery until independently read back.
    return 2


def main() -> int:
    global UPLOAD_CACHE_PATH
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["prepare", "draft", "publish", "update", "verify", "inspect-existing"], default="prepare")
    parser.add_argument("--variant", choices=["A", "B", "C"], default="A")
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--product-id")
    parser.add_argument("--input-manifest", help="Reviewed current-Schema payload manifest for live modes")
    parser.add_argument("--receipt", help="Explicit output receipt, or input receipt for verify")
    parser.add_argument("--verification-receipt", help="Separate atomic verify ledger; defaults to <receipt>.verification.json and is reused on later verification")
    parser.add_argument("--formal-readback", help="Independent formal snapshot provenance JSON for verify")
    args = parser.parse_args()
    if args.mode == "inspect-existing":
        if not args.input_manifest or not args.product_id:raise ValueError("inspect-existing requires --input-manifest and --product-id")
        print(json.dumps(inspect_existing_submission_manifest(Path(args.input_manifest),args.product_id),ensure_ascii=False,indent=2))
        return 0
    if args.mode != "prepare":
        return run_scoped_cli(args)
    # PACK_ROOT may be redirected by the continuation wrapper after this module
    # is imported, so load extensible style metadata here rather than at import.
    external_meta_path = PACK_ROOT / "00_扩品样式元数据.json"
    if external_meta_path.is_file():
        STYLE_META.update(json.loads(external_meta_path.read_text(encoding="utf-8-sig")))
    models = args.only or [f"HR{i:03d}" for i in range(1, 9)]
    client = load_client()
    config = client.load_config(CONFIG_PATH)
    url_map = json.loads(URL_MAP_PATH.read_text(encoding="utf-8-sig"))
    bank = load_bank_index()
    upload_cache_path = OUTPUT / "upload_cache.json"
    UPLOAD_CACHE_PATH = upload_cache_path
    upload_cache = json.loads(upload_cache_path.read_text(encoding="utf-8")) if upload_cache_path.is_file() else {}
    receipt = {"mode": args.mode, "source_product_id": SOURCE_PRODUCT_ID, "category_id": CATEGORY_ID, "products": []}
    for model in models:
        listing = prepare_listing(model, args.variant, client, config, url_map, bank, upload_cache)
        upload_cache_path.write_text(json.dumps(upload_cache, ensure_ascii=False, indent=2), encoding="utf-8")
        row = {key: value for key, value in listing.items() if key != "xml"}
        receipt["products"].append(row)
    if PER_MODEL_RECEIPTS and len(models) == 1:
        out = OUTPUT / f"{args.mode}_{args.variant}_{models[0]}_receipt.json"
    else:
        out = OUTPUT / f"{args.mode}_{args.variant}_receipt.json"
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    if PER_MODEL_RECEIPTS and len(models) > 1:
        for product_row in receipt["products"]:
            model_out = OUTPUT / f"{args.mode}_{args.variant}_{product_row['model']}_receipt.json"
            model_receipt = {**receipt, "products": [product_row]}
            model_out.write_text(json.dumps(model_receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"receipt": str(out), "products": [{"model": r["model"], "product_id": (r.get("submit") or {}).get("product_id"), "error": ((r.get("submit") or {}).get("refs") or {}).get("error")} for r in receipt["products"]]}, ensure_ascii=False, indent=2))
    return 1 if any((r.get("submit") or {}).get("status") in ("business_rejected", "unverified_business_result") for r in receipt["products"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
