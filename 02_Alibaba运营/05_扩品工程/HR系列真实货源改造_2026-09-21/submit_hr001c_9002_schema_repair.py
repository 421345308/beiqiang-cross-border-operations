"""HR001-C-specific inputs for current-Schema detail and stock repair."""

from __future__ import annotations

import importlib.util
from pathlib import Path

BASE = Path(__file__).with_name("submit_hr001b_9002_schema_repair.py")
spec = importlib.util.spec_from_file_location("hr001_schema_repair", BASE)
assert spec and spec.loader
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)

repair.LINK_CODE = "HR001-C"
repair.PRODUCT_ID = 1601943474137
repair.MODEL = "HR001-C / 9002"
repair.TITLE = "Private Label Men's Textile Slip-On Walking Shoes EVA Outsole EU 38-47 Wholesale Model 9002"
repair.HIGHLIGHTS = (
    "Verified Model 9002 uses a textile upper, slip-on no-lace structure and EVA sole. "
    "Source choices are Light Gray with Beige Sole and Dark Gray with Black Sole in EU sizes 38-47. "
    "Private-label logo, color and packaging requests can be discussed after quantity and specification review. "
    "Freight is quoted separately. Source price, availability, size ratio, packing and lead time are rechecked before order."
)
repair.B_D1_URL = (
    "https://sc04.alicdn.com/kf/Hb2da07ff92fe457282a485fe35269cd9y/"
    "286385890/Hb2da07ff92fe457282a485fe35269cd9y.jpg"
)

if __name__ == "__main__":
    repair.main()
