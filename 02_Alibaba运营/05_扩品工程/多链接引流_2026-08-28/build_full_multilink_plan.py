from __future__ import annotations

import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ASSET_ROOT = ROOT / "01_产品资产" / "02_可发布素材" / "00_最终上传"
OUTPUT_ROOT = Path(__file__).resolve().parent / "全量三链接_2026-08-28"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
TARGET_CODES = {f"BQ{number:03d}" for number in range(1, 53)} | {"BQ059"}


def first_match(text: str, patterns: list[str], default: str = "") -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I | re.S | re.M)
        if match:
            return " ".join(match.group(1).strip().split())
    return default


def clean_title(value: str) -> str:
    value = value.replace("`", " ")
    value = re.sub(r"\b(?:2026\s+New|Wholesale|Factory\s+Direct|OEM\s*/?\s*ODM|Private\s+Label)\b", " ", value, flags=re.I)
    value = re.sub(r"\s+for\s+(?:daily|travel|commuting|online|importers|brand).*?$", " ", value, flags=re.I)
    value = re.sub(r"\s+", " ", value).strip(" -")
    return value


def capped_title(parts: list[str], maximum: int = 115) -> str:
    words = " ".join(part.strip() for part in parts if part.strip()).split()
    result: list[str] = []
    for word in words:
        candidate = " ".join([*result, word])
        if len(candidate) > maximum:
            break
        result.append(word)
    return " ".join(result)


def compose_title(prefix: str, core: str, suffix: str, maximum: int = 115) -> str:
    fixed_length = len(prefix) + len(suffix) + 2
    available = max(30, maximum - fixed_length)
    core_words: list[str] = []
    for word in core.split():
        candidate = " ".join([*core_words, word])
        if len(candidate) > available:
            break
        core_words.append(word)
    return f"{prefix} {' '.join(core_words)} {suffix}".strip()


def list_images(folder: Path) -> list[str]:
    if not folder.exists():
        return []
    return [str(path.resolve()) for path in sorted(folder.rglob("*")) if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS]


def colors_from_text(text: str) -> list[str]:
    value = first_match(
        text,
        [
            r"^-\s*(?:颜色|Colors?)\s*[：:]\s*`?([^\n`]+)",
            r"\|\s*Colors?\s*\|\s*`?([^|`]+)",
        ],
    )
    if not value:
        return []
    separator = ";" if ";" in value else " / "
    values = [item.strip() for item in value.split(separator)]
    return [item for item in values if item and len(item) <= 30]


def source_title(text: str, code: str, artno: str) -> str:
    value = first_match(
        text,
        [
            r"##\s*(?:建议标题|当前标题|2\.\s*标题|标题)[^\n]*\n\s*```(?:text)?\s*(.*?)\s*```",
            r"##\s*(?:建议标题|当前标题|2\.\s*标题|标题)[^\n]*\n\s*`([^`]+)`",
            r"^-\s*当前标题\s*[：:]\s*`([^`]+)`",
            r"^-\s*标题\s*[：:]\s*`([^`]+)`",
        ],
    )
    if not value:
        value = f"Breathable Knit Casual Walking Shoes Model {artno or code}"
    return clean_title(value)


def application_intent(base_title: str) -> tuple[str, str]:
    lower = base_title.lower()
    if "kids" in lower or "children" in lower:
        return "Kids Casual Shoe Collection", "children footwear distributors and online sellers"
    if "high top" in lower or "fleece" in lower or "winter" in lower:
        return "Seasonal High Top Collection", "seasonal footwear importers and online sellers"
    if "slip on" in lower or "slip-on" in lower:
        return "Travel and Commuting Collection", "travel, commuting and daily-casual footwear buyers"
    if "lace up" in lower or "lace-up" in lower:
        return "Daily Walking Collection", "walking, commuting and casual footwear buyers"
    return "Casual Walking Collection", "importers, wholesalers and online sellers"


def build_plan() -> list[dict[str, object]]:
    products: list[tuple[str, Path]] = []
    for folder in ASSET_ROOT.iterdir():
        if not folder.is_dir():
            continue
        match = re.match(r"^(BQ\d{3})_(.+)$", folder.name)
        if not match or match.group(1) not in TARGET_CODES:
            continue
        if folder.name == "BQ052_116":
            continue
        products.append((match.group(1), folder))

    products.sort(key=lambda item: item[0])
    if len(products) != 53:
        raise SystemExit(f"Expected 53 source products, found {len(products)}")

    plan: list[dict[str, object]] = []
    for source_index, (code, folder) in enumerate(products, start=1):
        artno = folder.name.split("_", 1)[1]
        if code in {"BQ001", "BQ002"}:
            artno = code
        form = folder / "00_上架填写表.md"
        text = form.read_text(encoding="utf-8")
        base = source_title(text, code, artno)
        colors = colors_from_text(text)
        use_case, audience = application_intent(base)
        main_images = list_images(folder / "01_主图")
        detail_images = list_images(folder / "02_详情页")
        color_images = list_images(folder / "03_颜色图")

        variants = [
            {
                "suffix": "W1",
                "intent": "Importer and wholesaler core sourcing",
                "keyword_cluster": "wholesale walking shoes; factory shoe supplier; bulk casual footwear",
                "title": compose_title("Wholesale", base, "for Importers and Wholesalers"),
                "hero_angle": "clean white background, three-quarter front view, one complete pair",
                "detail_focus": "product overview, verified construction, size/color range, wholesale ordering",
            },
            {
                "suffix": "R1",
                "intent": use_case,
                "keyword_cluster": "daily walking shoes; casual shoe collection; footwear for online sellers",
                "title": compose_title("Factory Direct", base, f"{use_case} for Online Sellers"),
                "hero_angle": "light neutral background, distinct side-profile composition, one complete pair",
                "detail_focus": f"{audience}, use scenario, visible comfort structure, color collection",
            },
            {
                "suffix": "O1",
                "intent": "OEM ODM and private-label development",
                "keyword_cluster": "OEM shoes; private label footwear; custom logo shoe factory",
                "title": compose_title("OEM ODM Private Label", base, "Factory Supply for Brand Buyers"),
                "hero_angle": "clean studio background, distinct low three-quarter angle, one complete pair",
                "detail_focus": "verified product construction, sample discussion, logo/color/packing development scope",
            },
        ]

        for variant_index, variant in enumerate(variants):
            primary_color = colors[variant_index % len(colors)] if colors else f"real photographed color {variant_index + 1}"
            source_anchor = main_images[variant_index % len(main_images)] if main_images else ""
            plan.append(
                {
                    "source_order": source_index,
                    "source_bq": code,
                    "source_artno": artno,
                    "link_code": f"{code}-{variant['suffix']}",
                    "model_number": f"{code}-{variant['suffix']} / {artno}",
                    "buyer_intent": variant["intent"],
                    "keyword_cluster": variant["keyword_cluster"],
                    "title": variant["title"],
                    "primary_color": primary_color,
                    "hero_angle": variant["hero_angle"],
                    "hero_source_anchor": source_anchor,
                    "main_image_roles": "hero | differentiator | construction | use scene | color | order support",
                    "detail_focus": variant["detail_focus"],
                    "source_main_count": len(main_images),
                    "source_detail_count": len(detail_images),
                    "source_color_count": len(color_images),
                    "facts_source": str(form.resolve()),
                    "asset_folder": str(folder.resolve()),
                    "image_status": "NEEDS_6_UNIQUE_MAIN_AND_4_UNIQUE_DETAIL",
                    "cdn_status": "PENDING_ALIBABA_IMAGE_BANK",
                    "excel_status": "PENDING_IMAGE_URLS",
                }
            )
    return plan


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    plan = build_plan()
    json_path = OUTPUT_ROOT / "159条链接总控计划.json"
    csv_path = OUTPUT_ROOT / "159条链接总控计划.csv"
    json_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(plan[0]))
        writer.writeheader()
        writer.writerows(plan)

    batches = []
    for batch_number, start in enumerate(range(0, len(plan), 15), start=1):
        rows = plan[start : start + 15]
        batches.append(
            {
                "batch": batch_number,
                "links": len(rows),
                "source_products": sorted({row["source_bq"] for row in rows}),
                "first_link": rows[0]["link_code"],
                "last_link": rows[-1]["link_code"],
                "status": "BRIEF_READY_ASSETS_PENDING",
            }
        )
    (OUTPUT_ROOT / "批次接续状态.json").write_text(
        json.dumps(batches, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"source_products": 53, "links": len(plan), "batches": len(batches)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
