"""Upload the audited HR002 / S6077 image set to Alibaba photobank.

Default mode is read-only planning. Use --apply for the authorized upload.
The receipt is resumable: already successful SHA-256/file pairs are reused.
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
CLIENT_PATH = ROOT / ".agents" / "skills" / "alibaba-openapi-operator" / "scripts" / "alibaba_openapi.py"
ASSET_ROOT = ROOT / "99_临时区" / "HR002_S6077"
MAIN_DIR = ASSET_ROOT / "03_确定性排版候选"
COMPANY_DIR = ASSET_ROOT / "04_公司图候选"
SOURCE_DIR = ASSET_ROOT / "01_标准化审图副本"
RECEIPT = Path(__file__).with_name("HR002_S6077_图片银行映射.json")

FILES = [
    ("main", 1, MAIN_DIR / "M1_HERO_S6077.jpg"),
    ("main", 2, MAIN_DIR / "M2_COLORS_S6077.jpg"),
    ("main", 3, MAIN_DIR / "M3_MESH_LACE_S6077.jpg"),
    ("main", 4, MAIN_DIR / "M4_OUTSOLE_S6077.jpg"),
    ("main", 5, MAIN_DIR / "M5_SIZE_S6077.jpg"),
    ("main", 6, MAIN_DIR / "M6_FACTORY_PROCESS.jpg"),
    ("detail", 1, MAIN_DIR / "D1_OVERVIEW_S6077.jpg"),
    ("detail", 2, MAIN_DIR / "D2_COLORS_S6077.jpg"),
    ("detail", 3, MAIN_DIR / "D3_MESH_LACE_S6077.jpg"),
    ("detail", 4, MAIN_DIR / "D4_OUTSOLE_SIZE_S6077.jpg"),
    ("company", 1, COMPANY_DIR / "C1_FACTORY_ID.jpg"),
    ("company", 2, COMPANY_DIR / "C2_PROJECT_FLOW.jpg"),
    ("company", 3, COMPANY_DIR / "C3_PRODUCTION.jpg"),
    ("company", 4, COMPANY_DIR / "C4_QC_POINTS.jpg"),
    ("company", 5, COMPANY_DIR / "C5_PACK_HANDOFF.jpg"),
    ("sku", 1, SOURCE_DIR / "06_5e3752_gallery.jpg"),
    ("sku", 2, SOURCE_DIR / "05_ae58e1_gallery.jpg"),
]


def load_client():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_existing() -> dict:
    if RECEIPT.exists():
        return json.loads(RECEIPT.read_text(encoding="utf-8"))
    return {"product_family": "HR002", "source_model": "S6077", "assets": []}


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
    too_large = [path.name for _, _, path in FILES if path.stat().st_size > 5 * 1024 * 1024]
    if missing or too_long or too_large:
        raise SystemExit(json.dumps({"missing": missing, "too_long": too_long, "too_large": too_large}, ensure_ascii=False))

    existing = load_existing()
    successful = {
        (row.get("sha256"), row.get("role"), row.get("slot")): row
        for row in existing.get("assets", [])
        if row.get("url") and row.get("file_id")
    }
    plan = []
    for role, slot, path in FILES:
        digest = sha256(path)
        prior = successful.get((digest, role, slot))
        plan.append({
            "role": role,
            "slot": slot,
            "file": str(path),
            "name": path.name,
            "bytes": path.stat().st_size,
            "sha256": digest,
            "status": "reuse" if prior else "upload",
        })

    if not args.apply:
        print(json.dumps({"mode": "plan", "count": len(plan), "assets": plan}, ensure_ascii=False, indent=2))
        return

    client = load_client()
    config = client.load_config(Path.home() / ".config" / "beiqiang" / "alibaba-openapi.json")
    rows = []
    for item in plan:
        key = (item["sha256"], item["role"], item["slot"])
        if key in successful:
            rows.append(successful[key])
            continue
        last = None
        for attempt in range(1, 4):
            response = client.upload_image(config, Path(item["file"]), None)
            uploaded = response.get("upload_image_response") or {}
            if uploaded.get("photobank_url") and uploaded.get("file_id") and not client.api_error(response):
                row = {
                    **item,
                    "status": "uploaded",
                    "url": str(uploaded["photobank_url"]),
                    "file_id": str(uploaded["file_id"]),
                    **refs(client, response),
                }
                rows.append(row)
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
        "main": sum(row["role"] == "main" for row in rows),
        "detail": sum(row["role"] == "detail" for row in rows),
        "company": sum(row["role"] == "company" for row in rows),
        "sku": sum(row["role"] == "sku" for row in rows),
    }
    existing["all_uploaded"] = len(rows) == len(FILES) and all(row.get("url") and row.get("file_id") for row in rows)
    save_receipt(existing)
    print(json.dumps({"mode": "apply", "output": str(RECEIPT), "counts": existing["counts"], "all_uploaded": existing["all_uploaded"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
