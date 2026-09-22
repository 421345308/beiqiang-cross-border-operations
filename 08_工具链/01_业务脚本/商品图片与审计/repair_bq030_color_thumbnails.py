#!/usr/bin/env python3
"""Repair only BQ030/A811 expansion SKU color thumbnail bindings.

The shared implementation enforces source protection, approved/Y gating,
model/category/SKU identity, SKU-code freeze and non-image-field readback.
"""

from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
import repair_bq028_color_thumbnails as base  # noqa: E402


base.SOURCE_PRODUCT_ID = "1601839050756"
base.EXPECTED_SKU_COUNT = 40
base.PRODUCTS = {
    "1601939672381": "BQ030-W1 / A811",
    "1601939679363": "BQ030-R1 / A811",
    "1601939615744": "BQ030-O1 / A811",
}
base.TARGET = {
    "216016296": {
        "name": "Green",
        "image_url": "https://sc04.alicdn.com/kf/S4b39d8d97c2d4abfadc534a9ffde7d70u.jpg",
    },
    "3483425": {
        "name": "Grey",
        "image_url": "https://sc04.alicdn.com/kf/Sc69e5819f5e941948c6fa7102227a28dl.jpg",
    },
    "3851110": {
        "name": "Purple",
        "image_url": "https://sc04.alicdn.com/kf/Se37387c09d3e4f59b9112440a3d48d215.jpg",
    },
    "3328925": {
        "name": "Pink",
        "image_url": "https://sc04.alicdn.com/kf/S249c57b03c3b4ae492a756b38db06344W.jpg",
    },
}


if __name__ == "__main__":
    raise SystemExit(base.main())
