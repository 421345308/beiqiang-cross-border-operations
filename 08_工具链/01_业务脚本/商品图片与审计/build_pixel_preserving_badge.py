"""Add a B2B badge to empty image space without changing other decoded pixels."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


BADGE = (18, 18, 297, 76)
FONT = Path("C:/Windows/Fonts/arialbd.ttf")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--text", default="B2B WHOLESALE")
    args = parser.parse_args()

    if not args.source.is_file():
        raise FileNotFoundError(args.source)
    if args.output.exists() or args.report.exists():
        raise FileExistsError("Use new output/report paths; never overwrite an existing asset")
    if not FONT.is_file():
        raise FileNotFoundError(FONT)
    original = Image.open(args.source).convert("RGB")
    if original.size != (800, 800):
        raise ValueError(f"Expected 800x800 source, got {original.size}")

    # The badge is allowed only in genuinely empty white source-photo space.
    region = original.crop(BADGE)
    if any(channel < 245 for channel in region.tobytes()):
        raise ValueError("Badge area is not blank white in the source image")

    font = ImageFont.truetype(str(FONT), 24)
    text_box = ImageDraw.Draw(original).textbbox((0, 0), args.text, font=font)
    if text_box[2] - text_box[0] > BADGE[2] - BADGE[0] - 24:
        raise ValueError("Badge text does not fit")

    output = original.copy()
    draw = ImageDraw.Draw(output)
    draw.rounded_rectangle(BADGE, radius=12, fill=(23, 35, 46))
    draw.text((34, 33), args.text, font=font, fill=(255, 255, 255))
    changed = ImageChops.difference(original, output).getbbox()
    if changed is None or not (
        BADGE[0] <= changed[0] <= changed[2] <= BADGE[2] + 1
        and BADGE[1] <= changed[1] <= changed[3] <= BADGE[3] + 1
    ):
        raise AssertionError(f"Unexpected changed pixel bounding box: {changed}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    output.save(args.output, format="PNG", optimize=True)
    reopened = Image.open(args.output).convert("RGB")
    if ImageChops.difference(original, reopened).getbbox() != changed:
        raise AssertionError("Saved output changed pixels unexpectedly")
    result = {
        "checked_at": datetime.now().astimezone().isoformat(),
        "status": "LOCAL_CANDIDATE_ONLY_NOT_UPLOADED",
        "source": str(args.source.resolve()),
        "source_sha256": digest(args.source),
        "output": str(args.output.resolve()),
        "output_sha256": digest(args.output),
        "dimensions": list(output.size),
        "badge": list(BADGE),
        "badge_text": args.text,
        "changed_pixel_bbox": list(changed),
        "all_pixels_outside_badge_unchanged": True,
        "output_bytes": args.output.stat().st_size,
    }
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
