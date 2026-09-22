#!/usr/bin/env python3
"""Repair only BQ004/A502 expansion SKU color thumbnail bindings.

This specialization reuses the strict BQ028 saleProp-only implementation:
source protection, approved/Y gate, model/category/SKU checks, SKU-code freeze,
and full non-image-field readback all remain active.
"""

from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
import repair_bq028_color_thumbnails as base  # noqa: E402


base.SOURCE_PRODUCT_ID = "10000043201799"
base.PRODUCTS = {
    "1601939626612": "BQ004-W1 / A502",
    "1601939738037": "BQ004-R1 / A502",
    "1601939700200": "BQ004-O1 / A502",
}
base.TARGET = {
    "-93": {
        "name": "All Black",
        "image_url": "https://sc04.alicdn.com/kf/Sbf3aa096e6c54c4ba0f86efd6fd8faa1T.jpg",
    },
    "-24": {
        "name": "Light Blue",
        "image_url": "https://sc04.alicdn.com/kf/S1b1e52c3b116467abf116198ff7eb0a4G.jpg",
    },
    "-1": {
        "name": "Grey Black",
        "image_url": "https://sc04.alicdn.com/kf/S8e19e6bdc841467eb865ad01bc1ec72cP.jpg",
    },
    "-70": {
        "name": "Black White",
        "image_url": "https://sc04.alicdn.com/kf/S93d2b8951c704936a42a784fa1d6d4eet.jpg",
    },
    "-47": {
        "name": "Orange Black",
        "image_url": "https://sc04.alicdn.com/kf/S5908d9a1ab51461db81cbbdcbe6d88f1r.jpg",
    },
}


if __name__ == "__main__":
    raise SystemExit(base.main())
