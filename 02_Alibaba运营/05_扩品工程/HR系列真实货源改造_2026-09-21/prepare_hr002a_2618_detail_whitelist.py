"""Build the exact seller-editor replacement whitelist; no Alibaba write."""
from __future__ import annotations

import json
import re
from pathlib import Path

PROJECT = Path(__file__).parent
IMAGES = json.loads((PROJECT / "HR002_2618_图片银行映射.json").read_text(encoding="utf-8-sig"))
COMPANY = json.loads((PROJECT / "HR002_S6077_图片银行映射.json").read_text(encoding="utf-8-sig"))
FORMAL = json.loads((PROJECT / "HR002-A_2618_提交后OpenAPI核验.json").read_text(encoding="utf-8-sig"))
OUT = PROJECT / "HR002-A_2618_结构化详情替换白名单.json"
CDN = re.compile(r"^https://sc04\.alicdn\.com/kf/([^/]+)/286385890/\1\.(?:jpg|png|webp)$", re.I)


def official(url: str) -> str:
    url = "https:" + url if url.startswith("//") else url
    if not CDN.fullmatch(url):
        raise ValueError(f"not official image-bank URL: {url}")
    return url


def old_url(url: str) -> str:
    if not url.startswith("https://sc04.alicdn.com/kf/"):
        raise ValueError(f"unexpected old gallery URL: {url}")
    return url


source = {(row["role"], int(row["slot"])): row for row in IMAGES["assets"]}
company = {(row["role"], int(row["slot"])): row for row in COMPANY["assets"]}
detail_ids = (350, 150, 300, 350)
company_ids = (400, 550, 600, 500, 700)
detail = [
    {
        "slot": number,
        "gallery_id": detail_ids[number - 1],
        "url": official(source[("detail", number)]["url"]),
        "file_id": source[("detail", number)]["file_id"],
    }
    for number in range(1, 5)
]
company_rows = [
    {
        "slot": number,
        "gallery_id": company_ids[number - 1],
        "url": official(company[("company", number)]["url"]) if number < 5
        else official("https://sc04.alicdn.com/kf/Hecd5dd9f4eb94add8fb8a2436dab13c27/286385890/Hecd5dd9f4eb94add8fb8a2436dab13c27.png"),
        "file_id": company[("company", number)]["file_id"] if number < 5 else "33626689160",
        "claim_scope": "Beiqiang company-level process, not model 2618 own-factory production",
    }
    for number in range(1, 6)
]
old_detail = [old_url(row["image_url"]) for row in FORMAL["detail_images"]]
old_company = [old_url(row["image_url"]) for row in FORMAL["company_images"]]
if len(old_detail) != 4 or len(old_company) != 5:
    raise RuntimeError({"unexpected_old_counts": [len(old_detail), len(old_company)]})
if len({row["url"] for row in detail + company_rows}) != 9:
    raise RuntimeError("new detail/company URLs not unique")
if set(old_detail) & {row["url"] for row in detail}:
    raise RuntimeError("old product image retained")

plan = {
    "product_id": 1601943305914,
    "source_model": "2618",
    "stage": "WAIT_REVIEW_THEN_SELLER_EDITOR",
    "formal_product_request_id": FORMAL["formal_request_id"],
    "delete_original_detail_urls": old_detail,
    "add_detail_images": detail,
    "delete_original_company_urls": old_company,
    "add_company_images": company_rows,
    "after_edit_gates": [
        "4 current-shoe detail images only",
        "5 company-level images only",
        "old Fit Type custom attribute removed",
        "FAQ and summary contain no unverified 2618 sample/customization or fixed lead-time claims",
        "seller draft saved and independently reread before submit",
        "formal product.get and public page checked after approval",
    ],
}
OUT.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"output": str(OUT), "old_detail": len(old_detail), "new_detail": len(detail), "old_company": len(old_company), "new_company": len(company_rows)}, ensure_ascii=False))
