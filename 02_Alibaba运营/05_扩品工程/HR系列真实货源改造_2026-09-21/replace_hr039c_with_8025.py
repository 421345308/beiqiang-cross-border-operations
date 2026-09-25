"""Prepare or submit HR039-C as the same verified Model 8025 product.

The default invocation is read-only. Use --apply only after HR039-B has
passed OpenAPI and public-page QA.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


HERE = Path(__file__).resolve().parent
BASE_PATH = HERE / "replace_hr039a_with_bq036_8025.py"


def load_base():
    spec = importlib.util.spec_from_file_location("hr039_8025_base", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


base = load_base()
base.SOURCE_PRODUCT_ID = 1601943650395
base.TARGET_PRODUCT_ID = 1601943583746
base.SOURCE_MODEL = "HR039-A / 8025"
base.TARGET_MODEL = "HR039-C / 8025"
base.ALLOWED_TARGET_MODELS = {"HR039-C", "HR039-C / 8025"}
base.RECEIPT_PATH = HERE / "HR039-C_替换为8025_API回执.json"
base.TITLE = "Unisex High Top Knit Sock Sneakers Slip-On EVA Sole EU 35-45 Wholesale OEM Casual Shoes"
base.KEYWORDS = (
    "unisex knit sock sneakers high top slip on casual shoes wholesale "
    "EVA sole EU 35-45 OEM footwear supplier"
)
base.HIGHLIGHTS = (
    "Verified Model 8025 uses a high-top knitted textile upper, slip-on "
    "construction and EVA sole. Available source colors are Black/White and "
    "All Black in EU sizes 35-45. Logo, insole, color and packaging requests "
    "can be discussed after quantity and specification review. Freight is "
    "quoted separately according to destination and order quantity."
)


def set_all_values(root, field_id, value):
    nodes = root.findall(f".//field[@id='{field_id}']/value")
    if not nodes:
        raise RuntimeError(f"schema field has no value nodes: {field_id}")
    for node in nodes:
        if "inputValue" in node.attrib:
            node.set("inputValue", value)
        else:
            node.text = value


def replace_sku_codes(root):
    nodes = root.findall(".//field[@id='skuOuterId']/value")
    if len(nodes) != 22:
        raise RuntimeError(f"expected 22 source SKUs, got {len(nodes)}")
    seen = set()
    for node in nodes:
        old = node.text or ""
        if not old.startswith("HR039-A-8025-"):
            raise RuntimeError(f"unexpected source SKU code: {old}")
        node.text = old.replace("HR039-A-8025-", "HR039-C-8025-", 1)
        if node.text in seen:
            raise RuntimeError(f"duplicate target SKU code: {node.text}")
        seen.add(node.text)


base.set_all_values = set_all_values
base.replace_sku_codes = replace_sku_codes


if __name__ == "__main__":
    base.main()
