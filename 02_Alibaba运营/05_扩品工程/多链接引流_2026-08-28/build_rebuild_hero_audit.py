from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    files = sorted((args.asset_root / "main").glob("BQ*/bq*_m1.jpg"))
    if len(files) != 159:
        raise RuntimeError(f"expected 159 hero images, found {len(files)}")
    thumb_w, thumb_h, label_h = 250, 210, 28
    cols = 3
    args.output.parent.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default()
    products_per_page = 10
    for page, start in enumerate(range(0, 53, products_per_page), 1):
        page_files = files[start * 3 : min(53, start + products_per_page) * 3]
        rows = len(page_files) // 3
        canvas = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + label_h)), "white")
        draw = ImageDraw.Draw(canvas)
        for index, path in enumerate(page_files):
            row, col = divmod(index, cols)
            with Image.open(path) as image:
                image = image.convert("RGB")
                image.thumbnail((thumb_w, thumb_h))
                x = col * thumb_w + (thumb_w - image.width) // 2
                y = row * (thumb_h + label_h) + (thumb_h - image.height) // 2
                canvas.paste(image, (x, y))
            draw.text((col * thumb_w + 6, row * (thumb_h + label_h) + thumb_h + 4), path.stem, fill="black", font=font)
        destination = args.output.with_name(f"{args.output.stem}_{page:02d}{args.output.suffix}")
        canvas.save(destination, quality=92)
        print(destination)


if __name__ == "__main__":
    main()
