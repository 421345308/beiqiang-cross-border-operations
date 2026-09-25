"""Resumable upload of locally reviewed model-2618 candidate images.

This only adds images to the seller's image bank. It does not change products.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT = ROOT / ".agents" / "skills" / "alibaba-openapi-operator" / "scripts" / "alibaba_openapi.py"
ASSET = ROOT / "99_临时区" / "HR002_2618_货源候选_2026-09-24" / "本地候选_v1"
RECEIPT = Path(__file__).with_name("HR002_2618_图片银行映射.json")
NAMES = [
    ("main_A", 1, "M1A_2618_khaki.jpg"),
    ("main_B", 1, "M1B_2618_black.jpg"),
    ("main_C", 1, "M1C_2618_brown.jpg"),
    ("main_shared", 2, "M2_2618_colors.jpg"),
    ("main_shared", 3, "M3_2618_structure.jpg"),
    ("main_shared", 4, "M4_2618_onfoot.jpg"),
    ("main_shared", 5, "M5_2618_company.jpg"),
    ("main_shared", 6, "M6_2618_brief.jpg"),
    ("detail", 1, "D1_2618_overview.jpg"),
    ("detail", 2, "D2_2618_options.jpg"),
    ("detail", 3, "D3_2618_materials.jpg"),
    ("detail", 4, "D4_2618_quote.jpg"),
    ("sku", 1, "SKU_2618_black.jpg"),
    ("sku", 2, "SKU_2618_khaki.jpg"),
    ("sku", 3, "SKU_2618_brown.jpg"),
]


def client_module():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_receipt(rows: list[dict]):
    data = {
        "family": "HR002", "source_model": "2618",
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "assets": rows,
    }
    RECEIPT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def https_url(value: str) -> str:
    return "https:" + value if value.startswith("//") else value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    files = []
    for role, slot, name in NAMES:
        path = ASSET / name
        if not path.exists() or len(name) > 30 or path.stat().st_size > 5 * 1024 * 1024:
            raise RuntimeError({"invalid": str(path)})
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append({"role": role, "slot": slot, "file": str(path), "name": name,
                      "bytes": path.stat().st_size, "sha256": digest})
    prior = json.loads(RECEIPT.read_text(encoding="utf-8")) if RECEIPT.exists() else {}
    done = {row.get("sha256"): row for row in prior.get("assets", []) if row.get("url") and row.get("file_id")}
    if not args.apply:
        print(json.dumps({"total": len(files), "upload": sum(row["sha256"] not in done for row in files),
                          "files": files}, ensure_ascii=False, indent=2))
        return
    module = client_module()
    config = module.load_config(Path.home() / ".config" / "beiqiang" / "alibaba-openapi.json")
    rows = []
    for n, item in enumerate(files, 1):
        if item["sha256"] in done:
            rows.append({**item, "url": https_url(done[item["sha256"]]["url"]),
                         "file_id": done[item["sha256"]]["file_id"],
                         "request_id": done[item["sha256"]].get("request_id")})
            print(f"{n}/{len(files)} reuse {item['name']}", flush=True)
            continue
        response = module.upload_image(config, Path(item["file"]), None)
        uploaded = response.get("upload_image_response") or {}
        error = module.api_error(response)
        if error or not uploaded.get("photobank_url") or not uploaded.get("file_id"):
            write_receipt(rows)
            raise RuntimeError({"failed": item["name"], "error": error, "request_id": response.get("request_id")})
        rows.append({**item, "url": https_url(str(uploaded["photobank_url"])), "file_id": str(uploaded["file_id"]),
                     "request_id": response.get("request_id")})
        write_receipt(rows)
        print(f"{n}/{len(files)} uploaded {item['name']}", flush=True)
    write_receipt(rows)
    print(json.dumps({"complete": len(rows), "receipt": str(RECEIPT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
