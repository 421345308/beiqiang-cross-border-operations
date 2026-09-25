"""Build HR018/036 B2B hero candidates without touching any shoe pixels."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "99_临时区/HR018_候选核验"
OUTPUT = ROOT / "02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21/06_确定性图稿/HR018_036"
FONT = Path("C:/Windows/Fonts/arialbd.ttf")
BADGE = (18, 18, 297, 76)
TEXT = "B2B WHOLESALE"
IMAGES = {
    "HR018-A_036_M1_black.png": "路崎036_图2.jpg",
    "HR018-B_036_M1_black_scene.png": "路崎036_图4_大.jpg",
    "HR018-C_036_M1_beige_scene.png": "路崎036_图3.jpg",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(source_path: Path, output_path: Path) -> dict:
    original = Image.open(source_path).convert("RGB")
    if original.size != (800, 800):
        raise ValueError(f"Unexpected source dimensions: {source_path} {original.size}")
    canvas = original.copy()
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(BADGE, radius=12, fill=(23, 35, 46))
    font = ImageFont.truetype(str(FONT), 24)
    draw.text((34, 33), TEXT, font=font, fill=(255, 255, 255))
    difference = ImageChops.difference(original, canvas)
    changed_box = difference.getbbox()
    if changed_box is None:
        raise AssertionError("Badge produced no visible pixels")
    if not (
        BADGE[0] <= changed_box[0] <= changed_box[2] <= BADGE[2] + 1
        and BADGE[1] <= changed_box[1] <= changed_box[3] <= BADGE[3] + 1
    ):
        raise AssertionError(f"Source pixels changed outside badge: {changed_box}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)
    return {
        "source": str(source_path.relative_to(ROOT)),
        "source_sha256": sha256(source_path),
        "output": str(output_path.relative_to(ROOT)),
        "output_sha256": sha256(output_path),
        "dimensions": list(canvas.size),
        "badge_text": TEXT,
        "changed_pixel_bbox": list(changed_box),
        "all_pixels_outside_badge_unchanged": True,
        "file_bytes": output_path.stat().st_size,
    }


def main() -> None:
    rows = [build(SOURCE / source, OUTPUT / output)
            for output, source in IMAGES.items()]
    report = {
        "checked_at": datetime.now().astimezone().isoformat(),
        "status": "LOCAL_CANDIDATES_ONLY_NOT_UPLOADED",
        "source_product": "Sooxie Luqi 036",
        "items": rows,
    }
    path = OUTPUT / "像素保持核验.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
