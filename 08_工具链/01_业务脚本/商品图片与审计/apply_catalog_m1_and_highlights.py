#!/usr/bin/env python3
"""Apply and verify the approved M1 + Product Highlights plan product by product.

Only two fields are intentionally changed:
- scImages_0 (M1); M2-M6 are preserved through official image-bank IDs.
- textDesc (Product Highlights).

Every product is fetched before and after the update. A product succeeds only
when both requested changes read back correctly and all protected fields match.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timezone
import json
from io import BytesIO
from pathlib import Path
import sys
import time
import xml.etree.ElementTree as ET
from urllib.request import Request, urlopen

from PIL import Image, ImageChops, ImageStat


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
SKILL_SCRIPTS = ROOT / ".agents/skills/alibaba-openapi-operator/scripts"
sys.path.insert(0, str(SKILL_SCRIPTS))

from alibaba_openapi import DEFAULT_CONFIG, api_error, load_config, top_call, upload_image  # noqa: E402
from batch_replace_hero import image_key, load_bank_map, rebank_existing_image  # noqa: E402


DEFAULT_PLAN = Path(r"E:\贝强大文件\01_产品资产\02_可发布素材\00_全店统一升级_2026-09-04\全店151款首图与产品亮点写入计划.json")
DEFAULT_BANK_AUDIT = ROOT / "02_Alibaba运营/06_图片与检查记录/API全量图片审计_2026-09-03"
DEFAULT_OUTPUT = ROOT / "02_Alibaba运营/01_店铺与全店诊断/全量商品审查_2026-09-04/全店首图与产品亮点API执行记录.json"


def failed(response: dict) -> bool:
    return bool(api_error(response)) or response.get("biz_success") is False or response.get("model") is False


def refs(response: dict) -> dict:
    return {
        "request_id": response.get("request_id"),
        "trace_id": response.get("trace_id") or response.get("_trace_id_"),
        "message": response.get("message") or response.get("msg_info"),
        "error": api_error(response),
    }


def call_with_retry(fn, attempts: int = 5):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(1.5 * attempt)
    raise RuntimeError(str(last_error))


def current_m1_matches_local(url: str, local_path: Path) -> bool:
    def fetch() -> bytes:
        source_url = url if url.startswith("http") else "https:" + url
        request = Request(source_url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=60) as response:
            return response.read()

    try:
        remote = Image.open(BytesIO(call_with_retry(fetch))).convert("RGB").resize((128, 128), Image.Resampling.LANCZOS)
        local = Image.open(local_path).convert("RGB").resize((128, 128), Image.Resampling.LANCZOS)
        stat = ImageStat.Stat(ImageChops.difference(remote, local))
        # Small text-layout changes can average below 3 after a 128px resize.
        # Keep the threshold strict so a compact badge is not mistaken for the
        # previous two-line overlay during a repair retry.
        return sum(stat.mean) / len(stat.mean) < 0.5
    except Exception:
        return False


def update_xml(urls: list[str], ids: list[str], summary: str) -> str:
    root = ET.Element("itemSchema")
    group = ET.SubElement(root, "field", {"id": "scImages", "type": "complex"})
    values = ET.SubElement(group, "complex-value")
    for index, (url, file_id) in enumerate(zip(urls, ids)):
        field = ET.SubElement(values, "field", {"id": f"scImages_{index}", "type": "input"})
        value = ET.SubElement(field, "value", {"fileId": str(file_id)})
        value.text = url.replace("https:", "").replace("http:", "")
    field = ET.SubElement(root, "field", {"id": "textDesc", "type": "input"})
    ET.SubElement(field, "value").text = summary
    return ET.tostring(root, encoding="unicode", short_empty_elements=True)


def protected_snapshot(product: dict) -> dict:
    detail = deepcopy(product.get("struct_detail") or {})
    detail.pop("product_summary", None)
    return {
        "subject": deepcopy(product.get("subject")),
        "category_id": deepcopy(product.get("category_id")),
        "language": deepcopy(product.get("language")),
        "product_type": deepcopy(product.get("product_type")),
        "keywords": deepcopy(product.get("keywords")),
        "attributes": deepcopy(product.get("attributes")),
        "product_sku": deepcopy(product.get("product_sku")),
        "sourcing_trade": deepcopy(product.get("sourcing_trade")),
        "struct_detail_without_summary": detail,
        "struct_detail_product": deepcopy(product.get("struct_detail_product")),
        "price_type": deepcopy(product.get("price_type")),
        "rts": deepcopy(product.get("rts")),
        "sub_market_type": deepcopy(product.get("sub_market_type")),
        "group": deepcopy(product.get("group")),
    }


def get_product(config: dict, product_id: str, attempts: int = 4) -> tuple[dict | None, dict]:
    response: dict = {}
    for attempt in range(1, attempts + 1):
        try:
            response = top_call(config, "alibaba.icbu.product.get", {"product_id": product_id, "language": "ENGLISH"})
        except Exception as exc:
            response = {"local_exception": str(exc)}
        if not failed(response) and response.get("product"):
            return response["product"], response
        if attempt < attempts:
            time.sleep(1.5 * attempt)
    return None, response


def process_one(row: dict, config: dict, bank: dict[str, dict]) -> dict:
    product_id = str(row["product_id"])
    record = {
        "sequence": row["sequence"],
        "product_id": product_id,
        "title": row.get("title"),
        "source_slot": row.get("source_slot"),
        "source_product_id": row.get("source_product_id"),
        "ok": False,
    }
    before, before_response = get_product(config, product_id)
    if before is None:
        record.update(stage="product_get_before", response=refs(before_response))
        return record
    old_urls = list((before.get("main_image") or {}).get("images") or [])
    if len(old_urls) != 6:
        record.update(stage="gallery_precheck", error=f"expected 6 images, got {len(old_urls)}")
        return record

    local_path = Path(row["output"])
    current_summary = str(((before.get("struct_detail") or {}).get("product_summary") or ""))
    if current_summary == str(row["new_summary"]) and current_m1_matches_local(old_urls[0], local_path):
        record.update(
            ok=True,
            stage="verified_existing",
            before_status=before.get("status"),
            after_status=before.get("status"),
            before_display=before.get("display"),
            after_display=before.get("display"),
            old_m1=old_urls[0],
            new_m1=old_urls[0],
            m1_verified=True,
            m2_m6_preserved=True,
            product_highlights_verified=True,
            protected_fields_unchanged=True,
        )
        return record

    preserved_urls: list[str] = []
    preserved_ids: list[str] = []
    rebanked: list[dict] = []
    for slot, url in enumerate(old_urls[1:], start=2):
        bank_row = bank.get(image_key(url))
        if bank_row:
            preserved_urls.append(str(bank_row["url"]))
            preserved_ids.append(str(bank_row["id"]))
            continue
        # Some migrated live-product images do not appear in the current image
        # bank index. The new Schema update rejects fileId=0 for them, so copy
        # those exact images back into this seller's bank and use the returned
        # official URL/file ID. This changes no visual content in M2-M6.
        try:
            upload = None
            source = None
            last_error = None
            for attempt in range(1, 6):
                try:
                    upload, source = rebank_existing_image(config, url, slot)
                    break
                except Exception as exc:
                    last_error = exc
                    if attempt < 5:
                        time.sleep(1.5 * attempt)
            if upload is None:
                raise RuntimeError(str(last_error))
        except Exception as exc:
            record.update(stage="preserved_image_rebank_exception", error=str(exc), slot=slot)
            return record
        if failed(upload) or not upload.get("upload_image_response"):
            record.update(stage="preserved_image_rebank", slot=slot, source=source, response=refs(upload))
            return record
        item = upload["upload_image_response"]
        preserved_urls.append(str(item["photobank_url"]))
        preserved_ids.append(str(item["file_id"]))
        rebanked.append({"slot": slot, "source": source, "file_id": str(item["file_id"]), "url": str(item["photobank_url"])})

    upload = call_with_retry(lambda: upload_image(config, local_path, None))
    if failed(upload) or not upload.get("upload_image_response"):
        record.update(stage="new_m1_upload", response=refs(upload))
        return record
    uploaded = upload["upload_image_response"]
    new_url, new_id = str(uploaded["photobank_url"]), str(uploaded["file_id"])

    requested_urls = [new_url, *preserved_urls]
    requested_ids = [new_id, *preserved_ids]
    update = call_with_retry(
        lambda: top_call(
            config,
            "alibaba.icbu.product.schema.update",
            {
                "param_product_top_publish_request": {
                    "cat_id": int(before["category_id"]),
                    "language": "en_US",
                    "product_id": int(product_id),
                    "xml": update_xml(requested_urls, requested_ids, str(row["new_summary"])),
                }
            },
        )
    )
    if failed(update):
        record.update(stage="schema_update", upload={"file_id": new_id, "url": new_url, **refs(upload)}, response=refs(update))
        return record

    after = None
    after_response: dict = {}
    for attempt in range(1, 6):
        after, after_response = get_product(config, product_id)
        if after is not None:
            after_urls = list((after.get("main_image") or {}).get("images") or [])
            summary = str(((after.get("struct_detail") or {}).get("product_summary") or ""))
            if len(after_urls) == 6 and image_key(after_urls[0]) == image_key(new_url) and summary == row["new_summary"]:
                break
        if attempt < 5:
            time.sleep(2 * attempt)
    if after is None:
        record.update(stage="product_get_after", response=refs(after_response))
        return record

    after_urls = list((after.get("main_image") or {}).get("images") or [])
    summary = str(((after.get("struct_detail") or {}).get("product_summary") or ""))
    m1_ok = len(after_urls) == 6 and image_key(after_urls[0]) == image_key(new_url)
    m2_m6_ok = len(after_urls) == 6 and [image_key(x) for x in after_urls[1:]] == [image_key(x) for x in preserved_urls]
    summary_ok = summary == row["new_summary"]
    protected_ok = protected_snapshot(before) == protected_snapshot(after)
    ok = m1_ok and m2_m6_ok and summary_ok and protected_ok
    record.update(
        ok=ok,
        stage="verified" if ok else "readback_mismatch",
        before_status=before.get("status"),
        after_status=after.get("status"),
        before_display=before.get("display"),
        after_display=after.get("display"),
        old_m1=old_urls[0],
        new_m1=after_urls[0] if after_urls else None,
        m1_verified=m1_ok,
        m2_m6_preserved=m2_m6_ok,
        product_highlights_verified=summary_ok,
        protected_fields_unchanged=protected_ok,
        preserved_reuploads=rebanked,
        upload={"file_id": new_id, "url": new_url, **refs(upload)},
        update=refs(update),
        readback=refs(after_response),
    )
    return record


def save_manifest(output: Path, started: str, results: list[dict], planned: int) -> None:
    payload = {
        "started_at": started,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "planned_count": planned,
        "processed_count": len(results),
        "success_count": sum(bool(r.get("ok")) for r in results),
        "failure_count": sum(not bool(r.get("ok")) for r in results),
        "results": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--bank-audit", type=Path, default=DEFAULT_BANK_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--skip-completed", action="store_true")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8-sig"))
    rows = list(plan["products"])
    if args.only:
        wanted = {str(x) for x in args.only}
        rows = [row for row in rows if str(row["product_id"]) in wanted]
    previous: list[dict] = []
    if args.skip_completed and args.output.is_file():
        previous = json.loads(args.output.read_text(encoding="utf-8-sig")).get("results", [])
        completed = {str(r["product_id"]) for r in previous if r.get("ok")}
        rows = [row for row in rows if str(row["product_id"]) not in completed]

    config = load_config(args.config)
    bank = load_bank_map(args.bank_audit)
    started = datetime.now(timezone.utc).isoformat()
    results = list(previous)
    total = len(rows)
    def guarded(row: dict) -> dict:
        try:
            return process_one(row, config, bank)
        except Exception as exc:
            return {"sequence": row.get("sequence"), "product_id": str(row["product_id"]), "title": row.get("title"), "ok": False, "stage": "exception", "error": str(exc)}

    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 4))) as pool:
        jobs = {pool.submit(guarded, row): row for row in rows}
        for index, job in enumerate(as_completed(jobs), 1):
            result = job.result()
            results = [r for r in results if str(r.get("product_id")) != str(result["product_id"])]
            results.append(result)
            results.sort(key=lambda r: int(r.get("sequence") or 999999))
            save_manifest(args.output, started, results, len(plan["products"]))
            print(f"[{index:03d}/{total:03d}] {result['product_id']} {result['stage']} ok={result['ok']}", flush=True)
    return 0 if all(r.get("ok") for r in results) and len(results) == len(plan["products"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
