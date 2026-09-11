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
    ET.SubElement(node, "value").text = keywords.replace(";", " ")
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


def values_only(full_root: ET.Element) -> ET.Element:
    keep_ids = {
        "catId", "icbuCatProp", "saleProp", "sku", "productTitle", "productKeywords", "scImages",
        "pkgMeasure", "pkgWeight", "ladderPeriod", "priceUnit", "shippingTemplate", "productGroup",
        "ladderPrice", "customMoreProperty", "saleType", "scPrice", "minOrderQuantity", "productDescType",
        "detailImage", "textDesc", "companyImage", "companyDesc", "companyFaqDesc", "logisticsProperty",
        "semiManagedPeriod",
    }
    root = ET.Element("itemSchema")
    for field in full_root.findall("./field"):
        if field.attrib.get("id") not in keep_ids:
            continue
        clone = deepcopy(field)
        for tag in ("rules", "options", "fields", "label-group"):
            for child in list(clone.findall(f"./{tag}")):
                clone.remove(child)
        for sku_id in list(clone.findall(".//field[@id='skuId']")):
            for parent in clone.iter():
                if sku_id in list(parent):
                    parent.remove(sku_id)
                    break
        root.append(clone)
    return root


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


def api_submit(client, config, listing: dict, draft: bool, update_product_id: str | None = None) -> dict:
    category_id = int(listing.get("category_id") or CATEGORY_ID)
    if update_product_id:
        method = "alibaba.icbu.product.schema.update"
        payload = {"cat_id": category_id, "language": "en_US", "product_id": int(update_product_id), "xml": listing["xml"]}
    else:
        method = "alibaba.icbu.product.schema.add.draft" if draft else "alibaba.icbu.product.schema.add"
        payload = {"cat_id": category_id, "language": "en_US", "xml": listing["xml"]}
    response = top_retry(client, config, method, {"param_product_top_publish_request": payload})
    return {"method": method, "response": response, "refs": refs(client, response), "product_id": extract_product_id(response)}


def main() -> int:
    global UPLOAD_CACHE_PATH
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["prepare", "draft", "publish", "update"], default="prepare")
    parser.add_argument("--variant", choices=["A", "B", "C"], default="A")
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--product-id")
    args = parser.parse_args()
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
        if args.mode in ("draft", "publish", "update"):
            if args.mode == "update" and (len(models) != 1 or not args.product_id):
                raise RuntimeError("--mode update requires exactly one --only and --product-id")
            result = api_submit(client, config, listing, draft=args.mode == "draft", update_product_id=args.product_id if args.mode == "update" else None)
            row["submit"] = result
            if failed(client, result["response"]):
                receipt["products"].append(row)
                break
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
