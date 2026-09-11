from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ASSET_ROOT = ROOT / "01_产品资产" / "02_可发布素材" / "00_最终上传"


def find_product(code: str) -> Path:
    matches = sorted(ASSET_ROOT.glob(f"{code}_*"))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one asset directory for {code}, found {len(matches)}")
    return matches[0]


def stage(code: str, output: Path) -> dict[str, str]:
    product = find_product(code)
    short = str(int(code.removeprefix("BQ")))
    mapping: dict[str, str] = {}
    groups = (
        ("01_主图", "m", 6),
        ("02_详情页", "d", 4),
        ("03_颜色图", "c", None),
    )
    for directory, role, limit in groups:
        files = sorted((product / directory).glob("*.jpg"))
        if limit is not None:
            files = files[:limit]
        expected = limit if limit is not None else 1
        if len(files) < expected:
            raise RuntimeError(f"Insufficient {directory} images for {code}: {len(files)}")
        for index, source in enumerate(files, 1):
            name = f"q{short}{role}{index}.jpg"
            if len(name) > 30:
                raise RuntimeError(f"Alibaba image-bank filename is too long: {name}")
            destination = output / name
            shutil.copy2(source, destination)
            mapping[name] = str(source)
    return mapping


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codes", nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, str] = {}
    for raw_code in args.codes:
        code = raw_code.upper()
        if not re.fullmatch(r"BQ\d{3}", code):
            raise ValueError(f"Invalid product code: {raw_code}")
        mapping.update(stage(code, args.output))

    manifest = args.output / "manifest.json"
    manifest.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"products": len(args.codes), "images": len(mapping), "manifest": str(manifest)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
