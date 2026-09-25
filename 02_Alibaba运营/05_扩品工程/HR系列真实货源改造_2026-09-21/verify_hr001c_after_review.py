"""Read-only approved-state verifier for HR001-C after Alibaba review."""
from __future__ import annotations

import importlib.util
from pathlib import Path


HERE = Path(__file__).resolve().parent
BASE_PATH = HERE / "verify_hr001a_after_ui_submit.py"


def load_base():
    spec = importlib.util.spec_from_file_location("hr001_approved_verifier", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


base = load_base()
base.PRODUCT_ID = 1601943474137
base.OUTPUT_CODE = "HR001-C"
base.TITLE = "Private Label Men's Textile Slip-On Walking Shoes EVA Outsole EU 38-47 Wholesale Model 9002"
base.MODEL = "HR001-C / 9002"
base.VIDEO_ID = "6000344840202"


if __name__ == "__main__":
    base.main()
