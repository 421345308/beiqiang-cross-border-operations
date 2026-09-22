#!/usr/bin/env python3
"""Repair only BQ007/L0017 expansion SKU color thumbnail bindings.

This specialization reuses the strict BQ028 saleProp-only implementation:
the traffic-bearing source stays protected and title, gallery, pricing,
attributes, SKU codes, SKU count and every non-image field are frozen.
"""

from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
import repair_bq028_color_thumbnails as base  # noqa: E402


base.SOURCE_PRODUCT_ID = "1601825070472"
base.PRODUCTS = {
    "1601939585913": "BQ007-W1 / L0017",
    "1601939711161": "BQ007-R1 / L0017",
    "1601939701201": "BQ007-O1 / L0017",
}
base.TARGET = {
    "3558409": {
        "name": "Orange",
        "image_url": "https://sc04.alicdn.com/kf/H45c4d98bb5824ab79f299a04151cf0bfH.jpg",
    },
    "-80": {
        "name": "White Khaki",
        "image_url": "https://sc04.alicdn.com/kf/H6b0948b966e8477f9204ff3d32058ca5h.jpg",
    },
    "3331185": {
        "name": "White",
        "image_url": "https://sc04.alicdn.com/kf/H5c8be9c9aa0c41fabb70d7e5a9430ac5F.jpg",
    },
    "-57": {
        "name": "Black White",
        "image_url": "https://sc04.alicdn.com/kf/H7a3f2b0702824b78b00b0a5236e66ef9x.jpg",
    },
    "-34": {
        "name": "All Black",
        "image_url": "https://sc04.alicdn.com/kf/Hd0edb11e1a8c44ccbd3e38bd06277bf3U.jpg",
    },
}


if __name__ == "__main__":
    raise SystemExit(base.main())
