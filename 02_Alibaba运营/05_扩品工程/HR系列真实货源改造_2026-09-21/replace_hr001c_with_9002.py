"""Prepare or submit HR001-C as the same verified source model 9002.

Default invocation is read-only. Use --apply only after HR001-A and HR001-B
reach PUBLIC_QA_PASS in sequence.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


HERE = Path(__file__).resolve().parent
BASE_PATH = HERE / "replace_hr001a_with_9002.py"


def load_base():
    spec = importlib.util.spec_from_file_location("hr001_9002_base", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


base = load_base()
base.PRODUCT_ID = 1601943474137
base.LINK_CODE = "HR001-C"
base.TARGET_MODEL = "HR001-C / 9002"
base.ALLOWED_MODELS = {"HR001", "HR001-C", "HR001-C / 9002"}
base.MAIN_VIDEO_ID = "6000344840202"
base.PLAN_PATH = HERE / "HR001-C_9002_提交前预检.json"
base.RECEIPT_PATH = HERE / "HR001-C_替换为9002_API回执.json"
base.TITLE = "Private Label Men's Textile Slip-On Walking Shoes EVA Outsole EU 38-47 Wholesale Model 9002"
base.KEYWORDS = (
    "private label men textile slip on walking shoes wholesale EU 38-47 "
    "EVA outsole model 9002 OEM footwear supplier"
)
base.HIGHLIGHTS = (
    "Verified Model 9002 uses a textile upper, slip-on no-lace structure and EVA sole. "
    "Source choices are Light Gray with Beige Sole and Dark Gray with Black Sole in EU sizes 38-47. "
    "Private-label logo, color and packaging requests can be discussed after quantity and specification review. "
    "Freight is quoted separately. Source price, availability, size ratio, packing and lead time are rechecked before order."
)


if __name__ == "__main__":
    base.main()
