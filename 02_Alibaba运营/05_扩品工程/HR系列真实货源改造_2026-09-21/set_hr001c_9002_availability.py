"""Use the verified HR001-B stock updater for HR001-C after review."""

from __future__ import annotations

import importlib.util
from pathlib import Path

BASE = Path(__file__).with_name("set_hr001b_9002_availability.py")
spec = importlib.util.spec_from_file_location("hr001_stock", BASE)
assert spec and spec.loader
stock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stock)
stock.PRODUCT_ID = 1601943474137
stock.LISTING = "HR001-C"
stock.SKU_PREFIX = "HR001-C-9002-"

if __name__ == "__main__":
    raise SystemExit(stock.main())
