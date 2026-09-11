from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("asset_builder", HERE / "build_full_asset_manifest.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def candidate_pool(code: str, plan_rows: list[dict]) -> list[Path]:
    row = next(item for item in plan_rows if item["source_bq"] == code)
    final_dir = MODULE.FINAL_ROOT / Path(row["asset_folder"]).name
    raw_dirs = sorted(path for path in MODULE.RAW_ROOT.glob(f"已整理_{code}_*") if path.is_dir())
    source_dir = MODULE.RAW_ROOT / "待审_搜鞋网_2026-08-14" / row["source_artno"]
    raw_dirs = raw_dirs or ([source_dir] if source_dir.is_dir() else [])
    colors = MODULE.color_candidates(final_dir, raw_dirs)
    excluded = {MODULE.digest(path) for path in colors}
    final_main = MODULE.final_main_candidates(final_dir)
    generated = MODULE.unique_by_content([
        path for path in MODULE.list_images(final_dir / "04_多链接补充主图")
        if MODULE.is_square_product_image(path)
    ])
    raw = MODULE.unique_by_content([
        path for raw_dir in raw_dirs for path in MODULE.raw_main_candidates(raw_dir)
    ])
    return MODULE.unique_by_content(raw + final_main + generated, excluded=excluded)


def make_sheet(code: str, paths: list[Path], destination: Path) -> None:
    cols = 6
    cell_w, cell_h = 240, 280
    rows = (len(paths) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * cell_w, rows * cell_h), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for index, path in enumerate(paths):
        row, col = divmod(index, cols)
        with Image.open(path) as image:
            image = image.convert("RGB")
            image.thumbnail((220, 220))
            x = col * cell_w + (cell_w - image.width) // 2
            y = row * cell_h + 36 + (220 - image.height) // 2
            canvas.paste(image, (x, y))
        label = f"{index:02d} {path.parent.name}/{path.name}"
        draw.text((col * cell_w + 5, row * cell_h + 5), label[:38], fill="black", font=font)
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, quality=90)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codes", nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--index-json", type=Path)
    args = parser.parse_args()
    plan_rows = json.loads(MODULE.PLAN.read_text(encoding="utf-8"))
    index_payload: dict[str, list[dict[str, object]]] = {}
    for code in args.codes:
        paths = candidate_pool(code.upper(), plan_rows)
        make_sheet(code.upper(), paths, args.output / f"{code.upper()}_候选池.jpg")
        index_payload[code.upper()] = [
            {
                "index": index,
                "path": str(path),
                "source": (
                    "generated"
                    if "04_多链接补充主图" in str(path)
                    else "final"
                    if "02_可发布素材" in str(path)
                    else "raw"
                ),
            }
            for index, path in enumerate(paths)
        ]
        print(json.dumps({"code": code.upper(), "candidates": len(paths)}, ensure_ascii=False))
    if args.index_json:
        args.index_json.parent.mkdir(parents=True, exist_ok=True)
        args.index_json.write_text(json.dumps(index_payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
