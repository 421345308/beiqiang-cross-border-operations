"""Frame genuine Beiqiang workflow photography for an externally sourced shoe."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "02_Alibaba运营/06_图片与检查记录/公司图复用模板_v4_2026-09-21/C4_real_quality_checkpoints.jpg"
BOLD = Path("C:/Windows/Fonts/arialbd.ttf")
REG = Path("C:/Windows/Fonts/arial.ttf")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    a = p.parse_args()
    if a.output.exists() or a.report.exists():
        raise FileExistsError("Use versioned output and report paths")
    source = Image.open(SOURCE).convert("RGB")
    fitted = ImageOps.contain(source, (790, 790), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (1000, 1000), (250, 250, 248))
    d = ImageDraw.Draw(canvas)
    d.text((42, 43), "BEIQIANG ORDER REVIEW", font=ImageFont.truetype(str(BOLD), 42), fill=(25, 43, 52))
    d.text((43, 103), "General workflow | Other footwear styles shown", font=ImageFont.truetype(str(REG), 24), fill=(90, 104, 111))
    canvas.paste(fitted, ((1000 - fitted.width) // 2, 160))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(a.output, format="PNG", optimize=True)
    report = {
        "checked_at": datetime.now().astimezone().isoformat(),
        "status": "LOCAL_CANDIDATE_ONLY_NOT_UPLOADED",
        "source": str(SOURCE.relative_to(ROOT)),
        "source_sha256": sha(SOURCE),
        "output": str(a.output.resolve()),
        "output_sha256": sha(a.output),
        "method": "real company photo uniformly scaled; disclaimer outside image; no invented factory scene",
        "limit": "General Beiqiang company workflow, not proof this sourced shoe is produced in the pictured factory",
    }
    a.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
