"""Set one reviewed HR002 B/C link's valid 2618 SKUs to 999 inquiry markers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROJECT = Path(__file__).parent
BASE = PROJECT / "set_hr002a_2618_availability.py"
PRODUCTS = {"B": 1601943393550, "C": 1601943419438}

if len(sys.argv) < 2 or sys.argv[1] not in PRODUCTS:
    raise SystemExit("Usage: set_hr002bc_2618_availability.py B|C [--apply]")
variant = sys.argv.pop(1)
spec = importlib.util.spec_from_file_location("hr002_stock_base", BASE)
assert spec and spec.loader
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.PRODUCT_ID = PRODUCTS[variant]
base.PREFIX = f"HR002-{variant}-2618-"
base.EXPECTED_MODEL = f"HR002-{variant} / 2618"
base.EXPECTED_CODES = {
    f"{base.PREFIX}{color}-{size}"
    for color in ("BLACK", "KHAKI", "DARKBROWN")
    for size in range(39, 49)
}
base.OUT = PROJECT / f"HR002-{variant}_2618_999可询货标记_接口回执.json"
base.main()
