from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PROFILE_PATH = Path(__file__).with_name("sooxie_prelisting_profiles_2026-08-14.json")
SOURCE_ROOT = ROOT / "01_产品资产" / "01_原始数据包" / "待审_搜鞋网_2026-08-14"


def cdn(asset_id: str, suffix: str = "png") -> str:
    return f"https://sc04.alicdn.com/kf/{asset_id}/286385890/{asset_id}.{suffix}"


COMPANY_IMAGES = {
    "T": cdn("Sf587c854711748af9759e77ce5aeb03c3"),
    "V": cdn("Sfea34bbd56ae4d0583aa855838eb1454F"),
    "W": cdn("S2a3af5690d524680824086ad8419dbc9G"),
    "X": cdn("Sdc4e18f098e142b797df687e8befbfa14"),
    "Z": cdn("Sc1dc6ec7d435404db6a31c6938a734a0g"),
}


def slug(text: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "-", text.upper()).strip("-")


def size_list(profile: dict[str, object], color: str) -> list[int]:
    source = profile["sources"][0]
    facts = json.loads((SOURCE_ROOT / source / "source.json").read_text(encoding="utf-8-sig"))
    sizes = [int(value) for value in str(facts["sizes"]).split(";")]
    match = re.search(r"EU\s*(\d+)-(\d+)", color)
    if match:
        low, high = map(int, match.groups())
        sizes = [size for size in sizes if low <= size <= high]
    return sizes


def sole_material(text: str) -> str:
    if "Rubber-Plastic" in text:
        return "Rubber;Plastic"
    if "EVA" in text:
        return "EVA"
    if "PU" in text:
        return "PU"
    if "Rubber" in text:
        return "Rubber"
    return "Other"


def closure_value(text: str) -> str:
    return {"Lace-Up": "Lace-up", "Slip-On": "Slip-on"}.get(text, text)


def build_product(profile: dict[str, object], urls: dict[str, str]) -> list[dict[str, object]]:
    publish_status = str(profile.get("publish_status", "")).upper()
    if publish_status.startswith(("BLOCK", "HOLD")):
        duplicate_of = profile.get("duplicate_of")
        reason = f"; duplicate_of={duplicate_of}" if duplicate_of else ""
        raise RuntimeError(
            f"Profile {profile['code']} is not publishable ({publish_status}){reason}. "
            "Resolve the source-identity gate instead of generating another Alibaba link."
        )
    code = str(profile["code"])
    number = str(int(code.removeprefix("BQ")))

    def image(role: str, index: int) -> str:
        name = f"q{number}{role}{index}.jpg"
        if name not in urls:
            raise RuntimeError(f"Missing confirmed image-bank URL: {name}")
        return urls[name]

    main = [image("m", index) for index in range(1, 7)]
    detail = [image("d", index) for index in range(1, 5)]
    model = str(profile["model"])
    company_desc = (
        "Quanzhou Beiqiang Footwear & Apparel Co., Ltd. supplies OEM/ODM and wholesale casual footwear "
        "for importers, wholesalers, sourcing agents and private-label buyers."
    )
    selling_points = (
        f"{profile['upper']}; {str(profile['closure']).lower()} construction; regular fit; "
        f"{profile['size_system']} sizes from the verified source range; {len(profile['colors'])} verified color options; "
        "OEM/ODM logo, color, insole and packaging options can be discussed based on quantity and final requirements."
    )

    rows: list[dict[str, object]] = []
    for color_index, color in enumerate(profile["colors"], 1):
        clean_color = re.sub(r"\s*\(EU\s*\d+-\d+\)\s*", "", str(color)).strip()
        for size in size_list(profile, str(color)):
            row: dict[str, object] = {
                "E": profile["title"], "S": selling_points, "AB": company_desc,
                "AS": "China", "AU": f"{code} / {model}", "AV": "Other", "AW": "All Seasons",
                "AX": "Walking Shoes", "AY": sole_material(str(profile["sole"])), "AZ": "Textile",
                "BB": closure_value(str(profile["closure"])), "BC": "Round Toe", "BF": "Light Weight",
                "BK": "Sole Construction", "BL": profile["sole"],
                "CE": clean_color, "CF": image("c", color_index), "CG": size, "CH": 999,
                "CJ": f"{code}-{slug(clean_color)}-{size}",
                "CK": 2, "CL": "Pair/Pairs", "CM": 2, "CN": 9.49,
                "CO": 50, "CP": 9.19, "CQ": 100, "CR": 9.09,
                "CV": 34, "CW": 23, "CX": 13, "CY": 0.5,
                "CZ": "智能运费模板", "DA": "普货", "DB": 100, "DC": 31,
            }
            for column, value in zip(("F", "G", "H", "I", "J", "K"), main):
                row[column] = value
            for column, value in zip(("O", "P", "Q", "R"), detail):
                row[column] = value
            row.update(COMPANY_IMAGES)
            rows.append(row)
    return rows


def validate(rows: list[dict[str, object]], codes: list[str]) -> None:
    if not rows:
        raise RuntimeError("No SKU rows generated")
    for code in codes:
        if not any(str(row["CJ"]).startswith(f"{code}-") for row in rows):
            raise RuntimeError(f"No rows generated for {code}")
    seen: set[str] = set()
    for row in rows:
        sku = str(row["CJ"])
        if sku in seen:
            raise RuntimeError(f"Duplicate SKU: {sku}")
        seen.add(sku)
        urls = [value for value in row.values() if isinstance(value, str) and value.startswith("http")]
        if len(urls) != 16 or any("sc04.alicdn.com" not in value for value in urls):
            raise RuntimeError(f"Invalid image URL set for {sku}")
        if len(str(row["E"])) > 128:
            raise RuntimeError(f"Title too long: {row['E']}")
    serialized = json.dumps(rows, ensure_ascii=False)
    for forbidden in ("sc01.alicdn.com", "skill.accio.com", "Wide Toe", "Orthopedic", "Yeezy", "椰子鞋", "WARRIOR"):
        if forbidden in serialized:
            raise RuntimeError(f"Forbidden content detected: {forbidden}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codes", nargs="+", required=True)
    parser.add_argument("--urls", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    codes = [code.upper() for code in args.codes]
    profiles = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))["products"]
    by_code = {profile["code"]: profile for profile in profiles}
    urls = json.loads(args.urls.read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    for code in codes:
        if code not in by_code:
            raise RuntimeError(f"Profile not found: {code}")
        rows.extend(build_product(by_code[code], urls))
    validate(rows, codes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"products": len(codes), "rows": len(rows), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
