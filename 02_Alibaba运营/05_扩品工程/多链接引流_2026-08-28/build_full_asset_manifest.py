from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "02_Alibaba运营" / "05_扩品工程" / "多链接引流_2026-08-28" / "全量三链接_2026-08-28" / "159条链接总控计划.json"
RAW_ROOT = ROOT / "01_产品资产" / "01_原始数据包"
FINAL_ROOT = ROOT / "01_产品资产" / "02_可发布素材" / "00_最终上传"
OUTPUT_ROOT = ROOT / "02_Alibaba运营" / "05_扩品工程" / "多链接引流_2026-08-28" / "全量三链接_2026-08-28" / "待上传图片"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
VARIANT_ORDER = ("W1", "R1", "O1")
HERO_INDEX_OVERRIDES = {
    ("BQ001", "O1"): 1,
    ("BQ002", "O1"): 1,
}
POOL_OFFSETS = {
    # The first twelve clean-looking BQ004 photos use branded display boxes.
    # Later studio photos show the same product without third-party props.
    "BQ004": 12,
    # Skip domestic-commerce info cards / close-ups before the clean photo runs.
    "BQ007": 5,
    "BQ012": 3,
    "BQ013": 2,
    "BQ028": 2,
    "BQ030": 4,
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def image_size(path: Path) -> tuple[int, int] | None:
    try:
        with Image.open(path) as image:
            return image.size
    except Exception:
        return None


def is_square_product_image(path: Path) -> bool:
    size = image_size(path)
    if not size:
        return False
    width, height = size
    ratio = width / height
    return min(width, height) >= 700 and 0.82 <= ratio <= 1.18


def find_one(root: Path, pattern: str, code: str) -> Path:
    matches = sorted(path for path in root.glob(pattern) if path.is_dir())
    if len(matches) != 1:
        raise RuntimeError(f"{code}: expected one directory for {pattern}, found {len(matches)}")
    return matches[0]


def list_images(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(
        path for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def unique_by_content(paths: list[Path], excluded: set[str] | None = None) -> list[Path]:
    seen = set(excluded or set())
    output: list[Path] = []
    for path in paths:
        file_hash = digest(path)
        if file_hash in seen:
            continue
        seen.add(file_hash)
        output.append(path)
    return output


def natural_key(value: str) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def clean_photo_priority(path: Path) -> tuple[int, list[object], list[object]]:
    # Camera-original names and folders explicitly labelled as product photos
    # are the cleanest sources. Numeric domestic infographic sequences are kept
    # only as a final fallback and must still pass visual review.
    name = path.name
    parent = path.parent.name
    if re.search(r"^(?:DSC|IMG|R5VM|5M4A|PXL|DJI)[-_]?\d+", name, re.I):
        rank = 0
    elif (
        any(token in parent for token in ("货图", "实拍", "摄影"))
        or any(token in name for token in ("货图", "实拍"))
        # A few legacy ZIP packages were extracted with replacement characters
        # in the original Chinese "货图" folder/file name.
        or "\ufffd" in parent
        or "\ufffd" in name
    ):
        rank = 0
    elif "透明" in parent or "透明" in name:
        rank = 1
    elif re.fullmatch(r"0*\d+\.(?:jpe?g|png|webp)", name, re.I):
        number = int(Path(name).stem)
        # In several supplier packages 1-3/001-009 are domestic cover,
        # parameter and color-summary cards; later numeric files are photos.
        rank = 3 if number <= 9 else 2
    else:
        rank = 2
    return rank, natural_key(parent), natural_key(name)


def raw_main_candidates(raw_dir: Path) -> list[Path]:
    preferred_dirs = [
        path for path in raw_dir.rglob("*")
        if path.is_dir() and re.search(r"800\s*[xX×]\s*800.*主图|800.*主图", path.name)
    ]
    candidates: list[Path] = []
    for directory in preferred_dirs:
        candidates.extend(list_images(directory))
    # Some supplier packages place the 800 x 800 gallery directly in a nested
    # product folder without naming that folder. In that case the square-image
    # filter is the reliable fallback.
    if not candidates:
        candidates.extend(list_images(raw_dir))
    candidates = [path for path in candidates if is_square_product_image(path)]
    parent_counts: dict[Path, int] = defaultdict(int)
    for path in candidates:
        parent_counts[path.parent] += 1
    candidates.sort(key=lambda path: (clean_photo_priority(path)[0], -parent_counts[path.parent], *clean_photo_priority(path)[1:]))
    return unique_by_content(candidates)


def final_main_candidates(final_dir: Path) -> list[Path]:
    candidates = list_images(final_dir / "01_主图")
    return unique_by_content([path for path in candidates if is_square_product_image(path)])


def color_candidates(final_dir: Path, raw_dirs: list[Path]) -> list[Path]:
    candidates = list_images(final_dir / "03_颜色图")
    if len(candidates) < 3:
        for raw_dir in raw_dirs:
            transparent_dirs = [path for path in raw_dir.rglob("*") if path.is_dir() and "透明" in path.name]
            for directory in transparent_dirs:
                candidates.extend(list_images(directory))
    return unique_by_content([path for path in candidates if is_square_product_image(path)])


def detail_candidates(final_dir: Path) -> list[Path]:
    detail_dirs = sorted(
        (path for path in final_dir.iterdir() if path.is_dir() and path.name.startswith("02_详情页")),
        key=lambda path: ("修" not in path.name, path.name),
    )
    candidates: list[Path] = []
    for directory in detail_dirs:
        candidates.extend(list_images(directory))
    return unique_by_content(candidates)


def choose_product_assets(code: str, plan_rows: list[dict]) -> dict:
    plan_row = next(row for row in plan_rows if row["source_bq"] == code)
    final_name = Path(plan_row["asset_folder"]).name
    final_dir = FINAL_ROOT / final_name
    if not final_dir.is_dir():
        raise RuntimeError(f"{code}: final asset directory missing: {final_dir}")

    raw_dirs = sorted(path for path in RAW_ROOT.glob(f"已整理_{code}_*") if path.is_dir())
    if not raw_dirs:
        source_dir = RAW_ROOT / "待审_搜鞋网_2026-08-14" / plan_row["source_artno"]
        if source_dir.is_dir():
            raw_dirs = [source_dir]
    if not raw_dirs:
        raise RuntimeError(f"{code}: no raw source directory found for {plan_row['source_artno']}")

    colors = color_candidates(final_dir, raw_dirs)
    color_hashes = {digest(path) for path in colors}
    raw_main = unique_by_content([path for raw_dir in raw_dirs for path in raw_main_candidates(raw_dir)])
    final_main = final_main_candidates(final_dir)
    generated_main = unique_by_content([
        path for path in list_images(final_dir / "04_多链接补充主图")
        if is_square_product_image(path)
    ])
    # Raw supplier-package images are evidence, not upload-ready assets.  They
    # may contain Chinese copy, domestic-commerce layouts, collages, props or
    # third-party marks that cannot be detected reliably from filenames.  A
    # visually reviewed raw photo must first be copied/edited into the final
    # publishable asset directory before it can enter a main-image pool.
    pool = unique_by_content(final_main + generated_main, excluded=color_hashes)
    pool = pool[POOL_OFFSETS.get(code, 0) :]
    if len(pool) < 18:
        raise RuntimeError(
            f"{code}: only {len(pool)} reviewed publishable square product images; "
            "18 required. Raw-package images are intentionally blocked."
        )

    # Supplier photo sequences usually contain several angles of one color,
    # followed by the next color. Six-image chunks therefore give each traffic
    # entry a coherent but distinct photographed set.
    selected = {
        variant: pool[index * 6 : (index + 1) * 6]
        for index, variant in enumerate(VARIANT_ORDER)
    }
    for variant in VARIANT_ORDER:
        hero_index = HERO_INDEX_OVERRIDES.get((code, variant), 0)
        if hero_index:
            selected[variant] = selected[variant][hero_index:] + selected[variant][:hero_index]

    main_hashes = {digest(path) for paths in selected.values() for path in paths}
    details = unique_by_content(detail_candidates(final_dir), excluded=main_hashes)
    if len(details) < 6:
        detail_hashes = main_hashes | {digest(path) for path in details}
        supplements = unique_by_content(pool, excluded=detail_hashes)
        details.extend(supplements[: 6 - len(details)])
    if len(details) < 6:
        raise RuntimeError(f"{code}: only {len(details)} non-overlapping detail images; 6 required")

    sku_colors = unique_by_content(colors, excluded=main_hashes)
    return {
        "code": code,
        "raw_dir": [str(path) for path in raw_dirs],
        "final_dir": str(final_dir),
        "main": {variant: [str(path) for path in selected[variant]] for variant in VARIANT_ORDER},
        "detail": [str(path) for path in details[:6]],
        "sku_color": [str(path) for path in sku_colors],
        # A human/visual-model review must change each variant to PASS only
        # after checking the contact sheet against the Alibaba main-image gate.
        "visual_qa": {variant: "PENDING" for variant in VARIANT_ORDER},
    }


def stage_assets(product: dict, output: Path) -> list[dict]:
    code = product["code"]
    compact = code.lower()
    rows: list[dict] = []
    for variant in VARIANT_ORDER:
        for index, source_text in enumerate(product["main"][variant], 1):
            source = Path(source_text)
            filename = f"{compact}{variant.lower()}m{index}{source.suffix.lower().replace('.jpeg', '.jpg')}"
            destination = output / filename
            shutil.copy2(source, destination)
            rows.append({"code": code, "variant": variant, "role": f"main_{index}", "filename": filename, "source": str(source), "staged": str(destination)})
    for index, source_text in enumerate(product["detail"], 1):
        source = Path(source_text)
        filename = f"{compact}d{index}{source.suffix.lower().replace('.jpeg', '.jpg')}"
        destination = output / filename
        shutil.copy2(source, destination)
        rows.append({"code": code, "variant": "shared", "role": f"detail_{index}", "filename": filename, "source": str(source), "staged": str(destination)})
    for index, source_text in enumerate(product["sku_color"], 1):
        source = Path(source_text)
        filename = f"{compact}c{index}{source.suffix.lower().replace('.jpeg', '.jpg')}"
        destination = output / filename
        shutil.copy2(source, destination)
        rows.append({"code": code, "variant": "shared", "role": f"sku_color_{index}", "filename": filename, "source": str(source), "staged": str(destination)})
    return rows


def make_contact_sheet(product: dict, output: Path) -> Path:
    cell_width, cell_height = 240, 280
    canvas = Image.new("RGB", (cell_width * 6, cell_height * 3), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for row_index, variant in enumerate(VARIANT_ORDER):
        for col_index, source_text in enumerate(product["main"][variant]):
            with Image.open(source_text) as image:
                image = image.convert("RGB")
                image.thumbnail((220, 230))
                x = col_index * cell_width + (cell_width - image.width) // 2
                y = row_index * cell_height + 24 + (230 - image.height) // 2
                canvas.paste(image, (x, y))
            draw.text((col_index * cell_width + 8, row_index * cell_height + 6), f"{variant} main {col_index + 1}", fill="black", font=font)
    destination = output / f"{product['code']}_18张主图预览.jpg"
    canvas.save(destination, quality=90)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codes", nargs="+", required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT_ROOT / "批次01_BQ001-BQ005")
    args = parser.parse_args()

    codes = [code.upper() for code in args.codes]
    plan_rows = json.loads(PLAN.read_text(encoding="utf-8"))
    expected_codes = {row["source_bq"] for row in plan_rows}
    unknown = [code for code in codes if code not in expected_codes]
    if unknown:
        raise RuntimeError(f"Codes are not in the 159-link plan: {unknown}")

    args.output.mkdir(parents=True, exist_ok=True)
    upload_dir = args.output / "01_上传文件"
    preview_dir = args.output / "02_视觉预览"
    upload_dir.mkdir(exist_ok=True)
    preview_dir.mkdir(exist_ok=True)

    products = [choose_product_assets(code, plan_rows) for code in codes]
    rows: list[dict] = []
    previews: list[str] = []
    for product in products:
        rows.extend(stage_assets(product, upload_dir))
        previews.append(str(make_contact_sheet(product, preview_dir)))

    manifest_json = args.output / "图片上传清单.json"
    manifest_csv = args.output / "图片上传清单.csv"
    manifest_json.write_text(json.dumps({"products": products, "files": rows, "previews": previews}, ensure_ascii=False, indent=2), encoding="utf-8")
    with manifest_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["code", "variant", "role", "filename", "source", "staged"])
        writer.writeheader()
        writer.writerows(rows)

    print(json.dumps({
        "products": len(products),
        "upload_files": len(rows),
        "upload_dir": str(upload_dir),
        "manifest": str(manifest_json),
        "previews": previews,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
