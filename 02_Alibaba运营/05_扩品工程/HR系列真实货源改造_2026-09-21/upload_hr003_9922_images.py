"""Plan or upload the audited HR003 / 9922 image set to Alibaba photobank.

Default mode only validates files and reports upload/reuse decisions. Use --apply
after HR002-A reaches PUBLIC_QA_PASS. Existing HR002 company-template assets are
reused by SHA-256 instead of uploaded again.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
PROJECT = Path(__file__).parent
CLIENT_PATH = ROOT / ".agents" / "skills" / "alibaba-openapi-operator" / "scripts" / "alibaba_openapi.py"
ASSET_ROOT = ROOT / "99_临时区" / "HR003_9922"
GALLERY = ASSET_ROOT / "04_确定性排版候选"
SKU_DIR = ASSET_ROOT / "05_SKU上传候选"
HR002_COMPANY = ROOT / "99_临时区" / "HR002_S6077" / "04_公司图候选"
HR002_MANIFEST = PROJECT / "HR002_S6077_图片银行映射.json"
RECEIPT = PROJECT / "HR003_9922_图片银行映射.json"

FILES = [
    ("main", 1, GALLERY / "M1_HERO_9922.jpg"),
    ("main", 2, GALLERY / "M2_COLORS_9922.jpg"),
    ("main", 3, GALLERY / "M3_MESH_LACE_9922.jpg"),
    ("main", 4, GALLERY / "M4_THICK_SOLE_9922.jpg"),
    ("main", 5, GALLERY / "M5_SIZE_9922.jpg"),
    ("main", 6, GALLERY / "M6_FACTORY_PROCESS.jpg"),
    ("detail", 1, GALLERY / "D1_OVERVIEW_9922.jpg"),
    ("detail", 2, GALLERY / "D2_WHITE_9922.jpg"),
    ("detail", 3, GALLERY / "D3_BLACK_9922.jpg"),
    ("detail", 4, GALLERY / "D4_ORDER_INPUTS_9922.jpg"),
    ("company", 1, HR002_COMPANY / "C1_FACTORY_ID.jpg"),
    ("company", 2, HR002_COMPANY / "C2_PROJECT_FLOW.jpg"),
    ("company", 3, HR002_COMPANY / "C3_PRODUCTION.jpg"),
    ("company", 4, HR002_COMPANY / "C4_QC_POINTS.jpg"),
    ("company", 5, HR002_COMPANY / "C5_PACK_HANDOFF.jpg"),
    ("sku", 1, SKU_DIR / "SKU_BLACK_9922.jpg"),
    ("sku", 2, SKU_DIR / "SKU_WHITE_9922.jpg"),
]


def load_client():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path, fallback: dict) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else fallback


def save_receipt(data: dict) -> None:
    data["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    RECEIPT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def refs(client, response: dict) -> dict:
    return {
        "request_id": response.get("request_id"),
        "trace_id": response.get("_trace_id_") or response.get("trace_id"),
        "error": client.api_error(response),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    missing = [str(path) for _, _, path in FILES if not path.exists()]
    too_long = [path.name for _, _, path in FILES if len(path.name) > 30]
    too_large = [path.name for _, _, path in FILES if path.exists() and path.stat().st_size > 5 * 1024 * 1024]
    if missing or too_long or too_large:
        raise SystemExit(json.dumps({"missing": missing, "too_long": too_long, "too_large": too_large}, ensure_ascii=False))

    existing = load_json(RECEIPT, {"product_family": "HR003", "source_model": "9922", "assets": []})
    prior_rows = list(existing.get("assets", []))
    if HR002_MANIFEST.exists():
        prior_rows.extend(load_json(HR002_MANIFEST, {}).get("assets", []))
    reusable = {
        row.get("sha256"): row
        for row in prior_rows
        if row.get("sha256") and row.get("url") and row.get("file_id")
    }

    plan = []
    for role, slot, path in FILES:
        sha = digest(path)
        prior = reusable.get(sha)
        plan.append({
            "role": role,
            "slot": slot,
            "file": str(path),
            "name": path.name,
            "bytes": path.stat().st_size,
            "sha256": sha,
            "status": "reuse" if prior else "upload",
            "reused_url": prior.get("url") if prior else None,
            "reused_file_id": prior.get("file_id") if prior else None,
        })

    if not args.apply:
        print(json.dumps({
            "mode": "plan",
            "count": len(plan),
            "upload_count": sum(item["status"] == "upload" for item in plan),
            "reuse_count": sum(item["status"] == "reuse" for item in plan),
            "assets": plan,
        }, ensure_ascii=False, indent=2))
        return

    client = load_client()
    config = client.load_config(Path.home() / ".config" / "beiqiang" / "alibaba-openapi.json")
    rows = []
    for item in plan:
        prior = reusable.get(item["sha256"])
        if prior:
            rows.append({
                **item,
                "status": "reused",
                "url": prior["url"],
                "file_id": prior["file_id"],
                "reused_from_family": "HR002" if prior not in existing.get("assets", []) else "HR003",
                "request_id": prior.get("request_id"),
                "trace_id": prior.get("trace_id"),
                "error": None,
            })
            continue
        last = None
        for attempt in range(1, 4):
            response = client.upload_image(config, Path(item["file"]), None)
            uploaded = response.get("upload_image_response") or {}
            if uploaded.get("photobank_url") and uploaded.get("file_id") and not client.api_error(response):
                rows.append({
                    **item,
                    "status": "uploaded",
                    "url": str(uploaded["photobank_url"]),
                    "file_id": str(uploaded["file_id"]),
                    **refs(client, response),
                })
                existing["assets"] = rows
                save_receipt(existing)
                break
            last = response
            if attempt < 3:
                time.sleep(attempt * 2)
        else:
            existing["assets"] = rows
            save_receipt(existing)
            raise RuntimeError(json.dumps({"failed": item, "response": refs(client, last or {})}, ensure_ascii=False))

    existing["assets"] = rows
    existing["counts"] = {
        role: sum(row["role"] == role for row in rows)
        for role in ("main", "detail", "company", "sku")
    }
    existing["all_uploaded"] = len(rows) == len(FILES) and all(row.get("url") and row.get("file_id") for row in rows)
    save_receipt(existing)
    print(json.dumps({"mode": "apply", "output": str(RECEIPT), "counts": existing["counts"], "all_uploaded": existing["all_uploaded"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
