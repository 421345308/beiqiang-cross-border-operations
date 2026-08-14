#!/usr/bin/env python3
"""Build traceable visual-audit sheets for Sooxie candidate packages.

The script never edits source images. It creates JPEG contact sheets under the
ignored raw-package audit directory and writes cover-similarity pairs as CSV.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def natural_key(path: Path) -> tuple[int, str]:
    try:
        return int(path.stem), path.name.lower()
    except ValueError:
        return 10**9, path.name.lower()


def load_rgb(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return ImageOps.exif_transpose(image).convert("RGB")


def get_font(size: int) -> ImageFont.ImageFont:
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def dhash(image: Image.Image, hash_size: int = 16) -> int:
    sample = image.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
    pixels = list(sample.getdata())
    value = 0
    for row in range(hash_size):
        offset = row * (hash_size + 1)
        for col in range(hash_size):
            value = (value << 1) | int(pixels[offset + col] > pixels[offset + col + 1])
    return value


def hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def image_record(path: Path) -> dict[str, object]:
    image = load_rgb(path)
    return {
        "path": path,
        "sha256": file_sha256(path),
        "dhash": dhash(image),
    }


def make_sheet(artno: str, files: list[Path], output: Path) -> None:
    columns = 5
    cell_width = 320
    cell_height = 280
    label_height = 38
    rows = max(1, math.ceil(len(files) / columns))
    canvas = Image.new("RGB", (columns * cell_width, rows * cell_height), "white")
    draw = ImageDraw.Draw(canvas)
    label_font = get_font(18)

    for index, path in enumerate(files):
        row, col = divmod(index, columns)
        x = col * cell_width
        y = row * cell_height
        draw.rectangle((x, y, x + cell_width - 1, y + cell_height - 1), outline="#d0d0d0")
        image = load_rgb(path)
        fitted = ImageOps.contain(
            image,
            (cell_width - 20, cell_height - label_height - 20),
            Image.Resampling.LANCZOS,
        )
        px = x + (cell_width - fitted.width) // 2
        py = y + 10 + (cell_height - label_height - 20 - fitted.height) // 2
        canvas.paste(fitted, (px, py))
        draw.rectangle(
            (x, y + cell_height - label_height, x + cell_width, y + cell_height),
            fill="#202020",
        )
        draw.text(
            (x + 8, y + cell_height - label_height + 7),
            f"{artno} / {path.stem} / {image.width}x{image.height}",
            fill="white",
            font=label_font,
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, "JPEG", quality=88, optimize=True)


def read_candidates(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def find_cover(cover_root: Path, artno: str) -> Path | None:
    matches = sorted(
        (path for path in cover_root.glob(f"{artno}.*") if path.suffix.lower() in IMAGE_SUFFIXES),
        key=lambda path: path.name.lower(),
    )
    return matches[0] if matches else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    raw_root = workspace / "01_产品资产" / "01_原始数据包" / "待审_搜鞋网_2026-08-14"
    candidate_csv = (
        workspace
        / "02_Alibaba运营"
        / "05_扩品工程"
        / "数据"
        / "搜鞋网待去重候选_2026-08-14.csv"
    )
    sheet_root = raw_root / "_全部候选详情联系表"
    cover_root = raw_root / "_候选主图"
    similarity_csv = (
        workspace
        / "02_Alibaba运营"
        / "05_扩品工程"
        / "数据"
        / "搜鞋网候选封面相似对_2026-08-14.csv"
    )
    overlap_csv = (
        workspace
        / "02_Alibaba运营"
        / "05_扩品工程"
        / "数据"
        / "搜鞋网候选图片重合矩阵_2026-08-14.csv"
    )

    candidates = read_candidates(candidate_csv)
    covers: list[tuple[str, Path, int]] = []
    candidate_records: dict[str, list[dict[str, object]]] = {}
    image_total = 0

    for row in sorted(candidates, key=lambda item: item["artno"].lower()):
        artno = row["artno"]
        source_dir = raw_root / artno / "原图"
        files = sorted(
            (path for path in source_dir.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES),
            key=natural_key,
        )
        expected = int(row["detail_image_count"])
        if len(files) != expected:
            raise RuntimeError(f"{artno}: expected {expected} images, found {len(files)}")
        make_sheet(artno, files, sheet_root / f"{artno}.jpg")
        candidate_records[artno] = [image_record(path) for path in files]
        image_total += len(files)

        cover = find_cover(cover_root, artno)
        if cover:
            covers.append((artno, cover, dhash(load_rgb(cover))))

    pairs: list[dict[str, str | int]] = []
    for index, (left_artno, left_path, left_hash) in enumerate(covers):
        for right_artno, right_path, right_hash in covers[index + 1 :]:
            distance = hamming(left_hash, right_hash)
            if distance <= 52:
                pairs.append(
                    {
                        "left_artno": left_artno,
                        "right_artno": right_artno,
                        "dhash_distance_256": distance,
                        "left_cover": str(left_path.relative_to(workspace)),
                        "right_cover": str(right_path.relative_to(workspace)),
                    }
                )

    similarity_csv.parent.mkdir(parents=True, exist_ok=True)
    with similarity_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "left_artno",
                "right_artno",
                "dhash_distance_256",
                "left_cover",
                "right_cover",
            ],
        )
        writer.writeheader()
        writer.writerows(sorted(pairs, key=lambda item: int(item["dhash_distance_256"])))

    existing_records: dict[str, list[dict[str, object]]] = {}
    existing_root = workspace / "01_产品资产" / "01_原始数据包"
    for package in sorted(existing_root.glob("已整理_BQ*"), key=lambda path: path.name.lower()):
        match = re.match(r"已整理_(BQ\d{3})", package.name)
        if not match:
            continue
        code = match.group(1)
        files = [
            path
            for path in package.rglob("*")
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        ]
        existing_records.setdefault(code, []).extend(image_record(path) for path in files)

    overlap_rows: list[dict[str, object]] = []

    def compare_groups(
        left_type: str,
        left_code: str,
        left_images: list[dict[str, object]],
        right_type: str,
        right_code: str,
        right_images: list[dict[str, object]],
    ) -> None:
        exact = 0
        near = 0
        min_distance = 256
        right_sha = {str(item["sha256"]) for item in right_images}
        right_hashes = [int(item["dhash"]) for item in right_images]
        for left in left_images:
            if str(left["sha256"]) in right_sha:
                exact += 1
            if right_hashes:
                distance = min(hamming(int(left["dhash"]), value) for value in right_hashes)
                min_distance = min(min_distance, distance)
                if distance <= 18:
                    near += 1
        if exact > 0 or near >= 2 or min_distance <= 10:
            overlap_rows.append(
                {
                    "left_type": left_type,
                    "left_code": left_code,
                    "right_type": right_type,
                    "right_code": right_code,
                    "exact_image_matches": exact,
                    "near_image_matches": near,
                    "min_dhash_distance_256": min_distance,
                }
            )

    candidate_codes = sorted(candidate_records)
    for candidate in candidate_codes:
        for existing in sorted(existing_records):
            compare_groups(
                "candidate",
                candidate,
                candidate_records[candidate],
                "existing",
                existing,
                existing_records[existing],
            )
    for index, left in enumerate(candidate_codes):
        for right in candidate_codes[index + 1 :]:
            compare_groups(
                "candidate",
                left,
                candidate_records[left],
                "candidate",
                right,
                candidate_records[right],
            )

    with overlap_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        fieldnames = [
            "left_type",
            "left_code",
            "right_type",
            "right_code",
            "exact_image_matches",
            "near_image_matches",
            "min_dhash_distance_256",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(
            sorted(
                overlap_rows,
                key=lambda item: (
                    -int(item["exact_image_matches"]),
                    -int(item["near_image_matches"]),
                    int(item["min_dhash_distance_256"]),
                    str(item["left_code"]),
                    str(item["right_code"]),
                ),
            )
        )

    print(f"products={len(candidates)} images={image_total} sheets={len(candidates)} pairs={len(pairs)}")
    print(sheet_root)
    print(similarity_csv)
    print(f"overlap_rows={len(overlap_rows)}")
    print(overlap_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
