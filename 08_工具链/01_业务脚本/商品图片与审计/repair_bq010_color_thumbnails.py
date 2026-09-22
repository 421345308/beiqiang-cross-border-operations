#!/usr/bin/env python3
"""Repair only BQ010/R1601 expansion SKU color thumbnail bindings.

The shared implementation enforces source protection, approved/Y gating,
model/category/SKU identity, SKU-code freeze and non-image-field readback.
"""

from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
import repair_bq028_color_thumbnails as base  # noqa: E402


base.SOURCE_PRODUCT_ID = "1601825160204"
base.EXPECTED_SKU_COUNT = 22
base.PRODUCTS = {
    "1601939589876": "BQ010-W1 / R1601",
    "1601939734070": "BQ010-R1 / R1601",
    "1601939573998": "BQ010-O1 / R1601",
}
base.TARGET = {
    "-1": {
        "name": "White Sole Black",
        "image_url": "https://sc04.alicdn.com/kf/S131c1295cf36499b8d244c05a4bddfd7l.jpg",
    },
    "-24": {
        "name": "All Black",
        "image_url": "https://sc04.alicdn.com/kf/H88a70f03f531404088345b094a830e14a.jpg",
    },
}


if __name__ == "__main__":
    raise SystemExit(base.main())
