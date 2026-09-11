"""Repair BQ001/BQ002 galleries through the guarded BQ041 Schema workflow.

Only main images, existing SKU color thumbnails, product-detail galleries and
the neutral company gallery are replaced.  All commercial/SKU fields are
protected by the base script's before/after snapshot check.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
BASE_PATH = ROOT / "08_工具链/01_业务脚本/商品图片与审计/repair_bq041_product.py"
AUDIT_ROOT = ROOT / "02_Alibaba运营/01_店铺与全店诊断/全量商品审查_2026-09-04"
ASSET_PARENT = Path(r"E:\贝强大文件\01_产品资产\02_可发布素材\00_最终上传")


PRODUCTS = {
    "BQ001": {
        "product_id": 10000042821848,
        "model": "BQ-001",
        "root": ASSET_PARENT / "BQ001_数据包1",
        # Alibaba currently exposes these existing value names.  Keep them
        # unchanged and only replace their corresponding thumbnails.
        "colors": {
            "Black": "03_颜色图/all_black.jpg",
            "White": "03_颜色图/white.jpg",
            "Ivory": "03_颜色图/black_white.jpg",
        },
        "main": [
            "01_主图/01_main.jpg",
            "01_主图/02_toe.jpg",
            "01_主图/03_walk.jpg",
            "01_主图/05_light.jpg",
            "01_主图/06_top_view.jpg",
            "01_主图/07_outsole.jpg",
        ],
    },
    "BQ002": {
        "product_id": 10000042896165,
        "model": "BQ-002",
        "root": ASSET_PARENT / "BQ002_数据包2",
        "colors": {
            "Grey Black": "03_颜色图/grey_black.jpg",
            "Grey White": "03_颜色图/grey_white.jpg",
            "Grey Khaki": "03_颜色图/grey_khaki.jpg",
        },
        "main": [
            "01_主图/01_main.jpg",
            "01_主图/02_toe.jpg",
            "01_主图/03_walk.jpg",
            "01_主图/05_light.jpg",
            "01_主图/06_top_view.jpg",
            "01_主图/07_outsole.jpg",
        ],
    },
}


DETAILS = [
    ("02_详情页/02_info.jpg", 350, "Other product images"),
    ("02_详情页/03_upper.jpg", 300, "Detail shot"),
    ("02_详情页/04_sole.jpg", 300, "Detail shot"),
    ("02_详情页/01_size_safe.png", 150, "Product dimensions"),
    ("02_详情页/05_colors.jpg", 350, "Other product images"),
    ("02_详情页/06_order.jpg", 350, "Other product images"),
]


def load_base():
    spec = importlib.util.spec_from_file_location("repair_bq041_base", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sku", choices=sorted(PRODUCTS))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    cfg = PRODUCTS[args.sku]
    base = load_base()
    base.PRODUCT_ID = cfg["product_id"]
    base.MODEL = cfg["model"]
    base.ASSET_ROOT = cfg["root"]
    base.EXPECTED_COLORS = {name: cfg["root"] / rel for name, rel in cfg["colors"].items()}
    base.MAIN_FILES = [cfg["root"] / rel for rel in cfg["main"]]
    base.DETAIL_FILES = [(cfg["root"] / rel, role_id, role_name) for rel, role_id, role_name in DETAILS]
    base.CACHE_PATH = AUDIT_ROOT / f"{args.sku.lower()}_image_bank_cache.json"
    base.RECEIPT_PATH = AUDIT_ROOT / f"{args.sku.lower()}_repair_receipt.json"
    base.COMMERCIAL_BASELINE = {
        "moq": "preserve current live value",
        "price_ladder": "preserve current live value",
        "lead_time": "preserve current live value",
        "package": "preserve current live value",
    }
    sys.argv = [str(BASE_PATH)] + (["--apply"] if args.apply else [])
    base.main()


if __name__ == "__main__":
    main()
