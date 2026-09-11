from __future__ import annotations

import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RUN_ROOT = Path(__file__).resolve().parent / "全量三链接_2026-08-28"
SOURCE_PLAN = RUN_ROOT / "159条链接总控计划.json"
ASSET_ROOT = ROOT / "01_产品资产" / "02_可发布素材" / "00_最终上传"
OUTPUT_DIR = RUN_ROOT / "标题终审_2026-08-31"
OUTPUT_JSON = OUTPUT_DIR / "159条链接标题终审_2026-08-31.json"
OUTPUT_CSV = OUTPUT_DIR / "159条链接标题终审_2026-08-31.csv"
AUDIT_JSON = OUTPUT_DIR / "标题终审校验报告_2026-08-31.json"

TARGET_CODES = {f"BQ{i:03d}" for i in range(1, 53)} | {"BQ059"}

FIXED_BASE = {
    "BQ001": "Breathable Knit Slip-On Wide Toe Box Walking Shoes Lightweight EVA Sole",
    "BQ002": "Lightweight Knit Slip-On Wide Toe Box Walking Shoes EVA Sole",
}

CORE_OVERRIDE = {
    "BQ028": "Knit Slip-On Biscuit Sole Casual Walking Shoes",
    "BQ040": "Men's Knit Slip-On Walking Shoes MD Foam Segmented Sole Lightweight Casual Sneakers",
}

USE_TAIL = {
    "BQ001": "Travel Commuting and Daily Walking",
    "BQ002": "Travel Commuting and Daily Walking",
    "BQ003": "Summer Daily Walking and Casual Wear",
    "BQ004": "Travel Commuting and Daily Wear",
    "BQ005": "Daily Walking and Casual Wear",
    "BQ006": "Daily Walking and Seasonal Casual Collections",
    "BQ007": "Travel Commuting and Daily Wear",
    "BQ008": "Athletic Walking and Everyday Training",
    "BQ009": "Athletic Walking and Everyday Training",
    "BQ010": "Daily Walking and Casual Streetwear",
    "BQ011": "Commuting and Daily Walking",
    "BQ012": "Men's Daily Walking and Casual Wear",
    "BQ013": "Travel Commuting and Daily Wear",
    "BQ014": "Travel Commuting and Daily Wear",
    "BQ015": "Autumn Winter Walking and Casual Wear",
    "BQ016": "Girls School and Daily Walking",
    "BQ017": "Daily Walking and Casual Wear",
    "BQ018": "Daily Walking and Casual Wear",
    "BQ019": "Daily Walking and Casual Wear",
    "BQ020": "Daily Walking and Casual Wear",
    "BQ021": "Travel Commuting and Daily Wear",
    "BQ022": "Travel Commuting and Daily Wear",
    "BQ023": "Travel Commuting and Daily Wear",
    "BQ024": "Men's Travel Commuting and Daily Wear",
    "BQ025": "Travel Commuting and Daily Wear",
    "BQ026": "Daily Walking and Casual Wear",
    "BQ027": "Daily Walking and Casual Wear",
    "BQ028": "Travel Commuting and Daily Wear",
    "BQ029": "Autumn Winter Casual Walking",
    "BQ030": "Kids School and Daily Walking",
    "BQ031": "Wide Fit Daily Walking",
    "BQ032": "Large Size Daily Walking and Casual Wear",
    "BQ033": "Daily Walking and Casual Wear",
    "BQ034": "Travel Commuting and Daily Wear",
    "BQ035": "Travel Commuting and Casual Wear",
    "BQ036": "High Top Casual Walking and Streetwear",
    "BQ037": "Autumn Winter Walking and Casual Wear",
    "BQ038": "Autumn Winter Walking and Casual Wear",
    "BQ039": "High Top Casual Walking and Streetwear",
    "BQ040": "Travel Commuting and Daily Wear",
    "BQ041": "Kids School and Daily Walking",
    "BQ042": "Daily Walking and Casual Wear",
    "BQ043": "Daily Walking and Casual Wear",
    "BQ044": "Daily Walking and Casual Wear",
    "BQ045": "Men's High Top Casual Walking",
    "BQ046": "High Top Casual Walking and Streetwear",
    "BQ047": "Men's High Top Casual Walking",
    "BQ048": "Autumn Winter Walking and Casual Wear",
    "BQ049": "Daily Walking and Casual Wear",
    "BQ050": "Daily Walking and Casual Wear",
    "BQ051": "Travel Commuting and Daily Wear",
    "BQ052": "Large Size Daily Walking and Casual Wear",
    "BQ059": "High Top Casual Walking and Streetwear",
}


def listing_form(code: str) -> Path:
    candidates = [p for p in ASSET_ROOT.glob(f"{code}_*") if p.is_dir()]
    if code == "BQ052":
        candidates = [p for p in candidates if p.name == "BQ052_9212"]
    if len(candidates) != 1:
        raise RuntimeError(f"{code}: expected one asset folder, got {[p.name for p in candidates]}")
    return candidates[0] / "00_上架填写表.md"


def extract_recommended_title(code: str) -> str:
    if code in FIXED_BASE:
        return FIXED_BASE[code]
    text = listing_form(code).read_text(encoding="utf-8")
    patterns = [
        r"(?:##\s*(?:建议标题|推荐标题|修复标题|当前标题|标题选项|2\.\s*标题|标题)[^\n]*\n)(.*?)(?=\n##|\Z)",
        r"^-\s*当前标题\s*[：:]\s*`([^`]+)`",
        r"^-\s*标题\s*[：:]\s*`([^`]+)`",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I | re.S | re.M)
        if not match:
            continue
        block = match.group(1)
        candidates = re.findall(r"`([^\n`]{30,180})`", block)
        if candidates:
            return candidates[0]
        fenced = re.search(r"```(?:text)?\s*([^\n`]{30,180})", block, flags=re.I)
        if fenced:
            return fenced.group(1).strip()
        lines = [line.strip(" -*") for line in block.splitlines() if len(line.strip(" -*`")) >= 30]
        if lines:
            return lines[0].strip(" `")
    raise RuntimeError(f"{code}: no reviewed source title found")


def compact_core(title: str, artno: str) -> str:
    value = re.sub(r"^Wholesale\s+", "", title.strip(), flags=re.I)
    value = re.sub(r"\s+OEM\s*/?\s*ODM\s*$", "", value, flags=re.I)
    value = re.sub(rf"\bModel\s+{re.escape(artno)}\b", "", value, flags=re.I)
    value = re.sub(rf"\b{re.escape(artno)}\b", "", value, flags=re.I)
    value = re.sub(r"\bEU\s*\d{2}\s*[-–]\s*\d{2}\b", "", value, flags=re.I)
    value = value.replace("Knitted Textile", "Knit").replace("Knit Textile", "Knit")
    value = value.replace("Textile Lace-Up", "Knit Lace-Up")
    value = value.replace("Textile Slip-On", "Knit Slip-On")
    value = value.replace("Rubber-Plastic", "Rubber Plastic")
    value = value.replace("for Men and Women", "Unisex")
    value = value.replace("for Men", "Men's")
    value = value.replace("Kids Girls", "Girls'")
    value = re.sub(r"\s+for\s+(?:Daily Wear|Daily Commuting)$", "", value, flags=re.I)
    value = re.sub(r"\bwith\s*$", "", value, flags=re.I)
    value = re.sub(r"\s+", " ", value).strip(" -")
    if artno == "BISCUIT":
        value = re.sub(r"\b7212\b", "", value)
        value = re.sub(r"\s+", " ", value).strip()
    return value


def cap_title(value: str, artno: str, maximum: int = 128) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    optional = [
        " for Online Shoe Sellers", " Factory Supply", " Shoe Supplier", " Footwear Supplier",
        " and Casual Wear", " and Daily Wear", " and Streetwear", " Lightweight", " Casual",
    ]
    for phrase in optional:
        if len(value) <= maximum:
            break
        value = value.replace(phrase, "")
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) <= maximum:
        return value
    suffix = f" {artno}"
    body = value[:-len(suffix)].strip() if value.endswith(suffix) else value
    words: list[str] = []
    for word in body.split():
        candidate = " ".join([*words, word]) + suffix
        if len(candidate) > maximum:
            break
        words.append(word)
    return " ".join(words) + suffix


def keyword_family(core: str) -> list[str]:
    lower = core.lower()
    if "wide toe box" in lower:
        return ["wide toe box walking shoes", "wide fit walking sneakers", "knit comfort walking shoes"]
    if "kids" in lower or "girls" in lower:
        return ["kids walking shoes", "children casual sneakers", "school shoes wholesale"]
    if "high top" in lower or "sock sneakers" in lower:
        return ["high top knit sneakers", "sock sneakers slip on", "casual walking shoes wholesale"]
    if "mule" in lower or "backless" in lower or "clogs" in lower:
        return ["backless slip on shoes", "men's knit mule shoes", "casual walking clogs"]
    if "athletic" in lower:
        return ["athletic walking shoes", "breathable mesh sneakers", "thick sole walking shoes"]
    if "slip-on" in lower or "slip on" in lower:
        return ["slip on walking shoes", "knit casual sneakers", "lightweight walking shoes"]
    return ["lace up walking shoes", "knit casual sneakers", "breathable walking shoes"]


def make_titles(code: str, artno: str, core: str) -> dict[str, dict[str, str]]:
    use_tail = USE_TAIL[code]
    family = keyword_family(core)
    raw = {
        "W1": f"Wholesale {core} Factory Supply Model {artno}",
        "R1": f"{core} for {use_tail} Model {artno}",
        "O1": f"Custom Logo {core} OEM ODM Private Label Footwear Supplier Model {artno}",
    }
    intents = {
        "W1": "Core wholesale sourcing",
        "R1": use_tail,
        "O1": "OEM ODM custom logo and private-label sourcing",
    }
    clusters = {
        "W1": "; ".join([f"wholesale {family[0]}", f"factory supply {family[1]}", f"bulk {family[2]}"]),
        "R1": "; ".join([family[0], family[1], use_tail.lower()]),
        "O1": "; ".join([f"custom logo {family[0]}", "OEM shoes", "private label footwear supplier"]),
    }
    return {
        variant: {
            "title": cap_title(title, artno),
            "buyer_intent": intents[variant],
            "keyword_cluster": clusters[variant],
        }
        for variant, title in raw.items()
    }


def main() -> None:
    source_plan = json.loads(SOURCE_PLAN.read_text(encoding="utf-8"))
    by_code: dict[str, list[dict[str, object]]] = {}
    for item in source_plan:
        by_code.setdefault(str(item["source_bq"]), []).append(item)
    if set(by_code) != TARGET_CODES:
        raise RuntimeError(f"unexpected source set: {sorted(set(by_code) ^ TARGET_CODES)}")

    reviewed: list[dict[str, object]] = []
    errors: list[str] = []
    for code in sorted(by_code):
        source_items = sorted(by_code[code], key=lambda x: str(x["link_code"]))
        if len(source_items) != 3:
            errors.append(f"{code}: expected 3 links")
            continue
        artno = str(source_items[0]["source_artno"])
        source_title = extract_recommended_title(code)
        core = CORE_OVERRIDE.get(code, compact_core(source_title, artno))
        titles = make_titles(code, artno, core)
        for item in source_items:
            variant = str(item["link_code"]).rsplit("-", 1)[1]
            result = dict(item)
            result.update(titles[variant])
            result["title_review"] = {
                "status": "PASS",
                "verified_core": core,
                "source_title": source_title,
                "primary_keyword_first": keyword_family(core)[0],
                "review_date": "2026-08-31",
            }
            reviewed.append(result)

    all_titles = [str(x["title"]) for x in reviewed]
    for item in reviewed:
        code = str(item["source_bq"])
        title = str(item["title"])
        artno = str(item["source_artno"])
        if not 60 <= len(title) <= 128:
            errors.append(f"{item['link_code']}: title length {len(title)}")
        if artno.lower() not in title.lower():
            errors.append(f"{item['link_code']}: missing article number {artno}")
        if re.search(r"\b(Flyknit|Orthopedic|Medical|Waterproof|Certified|R118)\b", title, flags=re.I):
            errors.append(f"{item['link_code']}: risky or wrong term")
        if re.search(r"with\s+for|EU\s+for|for\s+for|Collection\s+for", title, flags=re.I):
            errors.append(f"{item['link_code']}: mechanical grammar defect")
        if code >= "BQ032" and "wide toe" in title.lower():
            errors.append(f"{item['link_code']}: unsupported wide-toe claim")
        if code == "BQ031" and "wide toe box" not in title.lower():
            errors.append(f"{item['link_code']}: missing confirmed wide-toe term")
    if len(set(all_titles)) != 159:
        errors.append(f"title uniqueness failed: {len(set(all_titles))}/159")
    if errors:
        raise RuntimeError("\n".join(errors[:100]))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(reviewed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    flat_rows = []
    for item in reviewed:
        flat_rows.append({
            "source_bq": item["source_bq"], "source_artno": item["source_artno"],
            "link_code": item["link_code"], "model_number": item["model_number"],
            "buyer_intent": item["buyer_intent"], "keyword_cluster": item["keyword_cluster"],
            "title": item["title"], "title_length": len(str(item["title"])),
            "verified_core": item["title_review"]["verified_core"],
            "facts_source": item["facts_source"],
        })
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(flat_rows[0]))
        writer.writeheader()
        writer.writerows(flat_rows)
    audit = {
        "source_products": len(by_code), "links": len(reviewed), "unique_titles": len(set(all_titles)),
        "length_min": min(map(len, all_titles)), "length_max": max(map(len, all_titles)),
        "mechanical_grammar_errors": 0, "risky_claim_errors": 0,
        "strategy": {
            "W1": "core wholesale search terms",
            "R1": "SKU-specific use case and product-type search terms",
            "O1": "custom logo, OEM ODM and private-label sourcing terms",
        },
        "output_json": str(OUTPUT_JSON), "output_csv": str(OUTPUT_CSV), "errors": [],
    }
    AUDIT_JSON.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
