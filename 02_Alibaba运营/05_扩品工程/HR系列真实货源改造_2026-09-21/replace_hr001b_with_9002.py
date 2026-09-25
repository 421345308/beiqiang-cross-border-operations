"""Prepare or submit HR001-B as the same verified source model 9002.

Default invocation is read-only. Use --apply only after HR001-A reaches
PUBLIC_QA_PASS.
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
base.PRODUCT_ID = 1601943493004
base.LINK_CODE = "HR001-B"
base.TARGET_MODEL = "HR001-B / 9002"
base.ALLOWED_MODELS = {"HR001", "HR001-B", "HR001-B / 9002"}
base.MAIN_VIDEO_ID = "6000344840202"
base.PLAN_PATH = HERE / "HR001-B_9002_提交前预检.json"
base.RECEIPT_PATH = HERE / "HR001-B_替换为9002_API回执.json"
base.TITLE = "Men's Knit Slip-On Walking Shoes EVA Sole EU 38-47 Wholesale OEM Supplier Model 9002"
base.KEYWORDS = (
    "wholesale men knit slip on walking shoes EU 38-47 casual shoes "
    "EVA sole model 9002 OEM footwear supplier"
)
base.HIGHLIGHTS = (
    "Verified Model 9002 uses a textile upper, slip-on no-lace structure and EVA sole. "
    "Source choices are Light Gray with Beige Sole and Dark Gray with Black Sole in EU sizes 38-47. "
    "Logo, color and packaging requests can be discussed after quantity and specification review. "
    "Freight is quoted separately. Source price, availability, size ratio, packing and lead time are rechecked before order."
)


if __name__ == "__main__":
    base.main()
