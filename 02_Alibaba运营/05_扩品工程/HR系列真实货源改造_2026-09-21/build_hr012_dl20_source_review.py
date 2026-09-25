from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parent / "HR012_DL20_原始证据_2026-09-23"
MANIFEST = ROOT / "browser_asset_manifest.json"
NORMALIZED = ROOT / "01_逐张原图"

MAIN_IDS = [
    "1e266761b02f82e2",
    "c1e95bfcc0e22002",
    "00ceb7acebbc99dd",
    "a3db3aab5f2fe66a",
    "a6872ce716db3413",
]

DETAIL_IDS = [
    "b04ccc8599130dc3", "233451bf2f8469f5", "f40f9213e03a47ec", "c8be87f2761358f8",
    "d24e8eea18429fc0", "f0f224cb2548f6ef", "4cd8e2c79edff429", "8e09b0c046fc9bdf",
    "b381addb30cf2876", "b1a4625b8136f409", "e20b92929bc17eaf", "d753217dbb572160",
    "a4029f61e0b2e2db", "3564deabbcc30b87", "7d428a8f35f455b2", "e1fd9e91689f37e0",
    "75f48cbad1e9613b", "a4e4e33ceb2ff830", "01eb1e6463ba3966", "38ee7c2d8577404c",
    "27ea5a4da14c9efe", "64dfcc1368533bb5", "7813a9b29b554320", "36bc58b77f534a3c",
    "3451c2d0d23d6617", "a39329eed7b32b0b", "2e86d4f0e2576f1f", "28258784a3505f9d",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_path(asset_id: str) -> Path:
    matches = [path for path in ROOT.iterdir() if path.is_file() and path.name.startswith(asset_id)]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one local file for {asset_id}, got {matches}")
    return matches[0]


def normalize(asset_id: str, label: str) -> dict[str, object]:
    src = source_path(asset_id)
    dst = NORMALIZED / f"{label}.jpg"
    with Image.open(src) as image:
        image.load()
        original_size = image.size
        rgb = image.convert("RGB")
        rgb.save(dst, "JPEG", quality=96, subsampling=0)
    return {
        "label": label,
        "asset_id": asset_id,
        "source_file": src.name,
        "normalized_file": dst.name,
        "width": original_size[0],
        "height": original_size[1],
        "source_sha256": sha256(src),
    }


def contact_sheet(rows: list[dict[str, object]], filename: str, columns: int = 4) -> None:
    tile_w, tile_h, label_h = 360, 360, 42
    page_rows = (len(rows) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * tile_w, page_rows * (tile_h + label_h)), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=22)
    for index, row in enumerate(rows):
        x = (index % columns) * tile_w
        y = (index // columns) * (tile_h + label_h)
        with Image.open(NORMALIZED / str(row["normalized_file"])) as image:
            thumb = ImageOps.contain(image.convert("RGB"), (tile_w - 18, tile_h - 18))
        px = x + (tile_w - thumb.width) // 2
        py = y + (tile_h - thumb.height) // 2
        sheet.paste(thumb, (px, py))
        draw.rectangle((x, y, x + tile_w - 1, y + tile_h + label_h - 1), outline="#c8c8c8", width=2)
        draw.text((x + 10, y + tile_h + 8), str(row["label"]), fill="#111111", font=font)
    sheet.save(ROOT / filename, "JPEG", quality=92, subsampling=0)


def main() -> None:
    NORMALIZED.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    url_by_id = {row["id"]: row["url"] for row in manifest["assets"]}

    rows: list[dict[str, object]] = []
    for index, asset_id in enumerate(MAIN_IDS, 1):
        rows.append(normalize(asset_id, f"M{index:02d}"))
    for index, asset_id in enumerate(DETAIL_IDS, 1):
        rows.append(normalize(asset_id, f"D{index:02d}"))

    for row in rows:
        row["source_url"] = url_by_id[str(row["asset_id"])]

    with (ROOT / "source_index.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    main_rows = [row for row in rows if str(row["label"]).startswith("M")]
    detail_rows = [row for row in rows if str(row["label"]).startswith("D")]
    contact_sheet(main_rows, "CONTACT_DL20_MAIN.jpg")
    contact_sheet(detail_rows[:14], "CONTACT_DL20_DETAIL_01-14.jpg")
    contact_sheet(detail_rows[14:], "CONTACT_DL20_DETAIL_15-28.jpg")

    print(json.dumps({
        "main_count": len(main_rows),
        "detail_count": len(detail_rows),
        "contact_sheets": [
            str(ROOT / "CONTACT_DL20_MAIN.jpg"),
            str(ROOT / "CONTACT_DL20_DETAIL_01-14.jpg"),
            str(ROOT / "CONTACT_DL20_DETAIL_15-28.jpg"),
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
