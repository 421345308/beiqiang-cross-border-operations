"""Build a square Alibaba SKU thumbnail from a truthful source-photo crop."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("left", type=int)
    parser.add_argument("top", type=int)
    parser.add_argument("right", type=int)
    parser.add_argument("bottom", type=int)
    parser.add_argument("--canvas", type=int, default=1000)
    parser.add_argument("--occupancy", type=float, default=0.82)
    parser.add_argument("--background", default="#f7f7f7")
    args = parser.parse_args()

    image = Image.open(args.source).convert("RGB")
    crop = image.crop((args.left, args.top, args.right, args.bottom))
    target = max(1, round(args.canvas * args.occupancy))
    scale = min(target / crop.width, target / crop.height)
    resized = crop.resize(
        (max(1, round(crop.width * scale)), max(1, round(crop.height * scale))),
        Image.Resampling.LANCZOS,
    )

    canvas = Image.new("RGB", (args.canvas, args.canvas), args.background)
    x = (args.canvas - resized.width) // 2
    y = (args.canvas - resized.height) // 2
    canvas.paste(resized, (x, y))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.output, quality=95, subsampling=0)


if __name__ == "__main__":
    main()
