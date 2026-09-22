#!/usr/bin/env python3
"""Build labeled contact sheets for visual review without changing source images."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


def font(size: int) -> ImageFont.ImageFont:
    candidates = (
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/msyh.ttc"),
    )
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def main() -> int:
    parser = argparse.ArgumentParser(description="Create numbered, filename-labeled image contact sheets.")
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--columns", type=int, default=5)
    parser.add_argument("--per-sheet", type=int, default=25)
    parser.add_argument("--thumb", type=int, default=320)
    args = parser.parse_args()

    extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    paths = sorted(
        (p for p in args.input_dir.iterdir() if p.is_file() and p.suffix.lower() in extensions),
        key=lambda p: p.name.lower(),
    )
    if not paths:
        raise SystemExit(f"No supported images in {args.input_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    label_h = 48
    gap = 12
    cell_w = args.thumb + gap * 2
    cell_h = args.thumb + label_h + gap * 2
    label_font = font(22)

    for sheet_no, start in enumerate(range(0, len(paths), args.per_sheet), 1):
        batch = paths[start : start + args.per_sheet]
        rows = math.ceil(len(batch) / args.columns)
        canvas = Image.new("RGB", (args.columns * cell_w, rows * cell_h), "white")
        draw = ImageDraw.Draw(canvas)
        for offset, path in enumerate(batch):
            row, col = divmod(offset, args.columns)
            x, y = col * cell_w + gap, row * cell_h + gap
            with Image.open(path) as src:
                tile = ImageOps.contain(src.convert("RGB"), (args.thumb, args.thumb), Image.Resampling.LANCZOS)
            px = x + (args.thumb - tile.width) // 2
            py = y + (args.thumb - tile.height) // 2
            canvas.paste(tile, (px, py))
            label = f"{start + offset + 1:02d}  {path.name}"
            draw.text((x, y + args.thumb + 8), label, fill="#111827", font=label_font)
            draw.rectangle((x - 1, y - 1, x + args.thumb + 1, y + args.thumb + 1), outline="#d1d5db", width=2)
        out = args.output_dir / f"contact_{sheet_no:02d}.jpg"
        canvas.save(out, quality=92, subsampling=0)
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
