"""Safely replace the sales unit in Alibaba official-template data rows.

Only inline-string cells in column CL are changed. Every other ZIP member and
the ordering of workbook parts are preserved byte-for-byte.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import zipfile
from pathlib import Path


SHEET_XML = "xl/worksheets/sheet1.xml"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def patch(path: Path, old: str, new: str, expected_cells: int | None) -> int:
    with zipfile.ZipFile(path, "r") as source:
        infos = source.infolist()
        original = {info.filename: source.read(info.filename) for info in infos}
    sheet = original[SHEET_XML].decode("utf-8")
    pattern = re.compile(
        r'(<c r="CL\d+"[^>]*>.*?<t[^>]*>)' + re.escape(old) + r'(</t>.*?</c>)',
        re.DOTALL,
    )
    updated, count = pattern.subn(rf"\g<1>{new}\g<2>", sheet)
    if expected_cells is not None and count != expected_cells:
        raise RuntimeError(f"Expected {expected_cells} CL cells, found {count}")
    if count == 0:
        raise RuntimeError(f"No CL cells contained {old!r}")
    changed = dict(original)
    changed[SHEET_XML] = updated.encode("utf-8")
    temporary = path.with_suffix(path.suffix + ".tmp")
    with zipfile.ZipFile(temporary, "w") as target:
        for info in infos:
            target.writestr(info, changed[info.filename])
    with zipfile.ZipFile(temporary, "r") as check:
        check_infos = check.infolist()
        check_data = {info.filename: check.read(info.filename) for info in check_infos}
    if [info.filename for info in check_infos] != [info.filename for info in infos]:
        raise RuntimeError("ZIP member names or order changed")
    for name, data in original.items():
        if name != SHEET_XML and sha256(check_data[name]) != sha256(data):
            raise RuntimeError(f"Workbook part changed unexpectedly: {name}")
    os.replace(temporary, path)
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xlsx", type=Path, required=True)
    parser.add_argument("--old", default="Piece/Pieces")
    parser.add_argument("--new", default="Pair/Pairs")
    parser.add_argument("--expected-cells", type=int)
    args = parser.parse_args()
    count = patch(args.xlsx, args.old, args.new, args.expected_cells)
    print(f"patched_cells={count} output={args.xlsx}")


if __name__ == "__main__":
    main()
