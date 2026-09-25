"""Upload reviewed B/C galleries for the same sourced model 2618.

Image-bank upload only; product bindings are handled separately.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
CLIENT = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
ASSETS = ROOT / "99_临时区/HR002_2618_货源候选_2026-09-24/本地候选_v1"
RECEIPT = Path(__file__).with_name("HR002_2618_BC_图片银行映射.json")
ROLES = ("M2_colors", "M3_structure", "M4_company", "M5_packing", "M6_sizes",
         "D1_overview", "D2_options", "D3_components", "D4_inquiry")


def load_client():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
    if not spec or not spec.loader:
        raise RuntimeError("OpenAPI client not available")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def save(rows):
    RECEIPT.write_text(json.dumps({"family": "HR002", "source_model": "2618",
                                   "updated_at_utc": datetime.now(timezone.utc).isoformat(),
                                   "assets": rows}, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    files = []
    for variant in ("B", "C"):
        for role in ROLES:
            name = f"{variant}_{role}_2618.jpg"
            path = ASSETS / name
            if not path.is_file() or path.stat().st_size > 5 * 1024 * 1024 or len(name) > 30:
                raise RuntimeError(f"Invalid asset: {path}")
            files.append({"variant": variant, "role": role, "file": str(path), "name": name,
                          "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    previous = json.loads(RECEIPT.read_text(encoding="utf-8")) if RECEIPT.exists() else {}
    done = {r["sha256"]: r for r in previous.get("assets", []) if r.get("url") and r.get("file_id")}
    if not args.apply:
        print(json.dumps({"total": len(files), "to_upload": sum(f["sha256"] not in done for f in files),
                          "files": files}, ensure_ascii=False, indent=2))
        return
    client = load_client()
    config = client.load_config(Path.home() / ".config/beiqiang/alibaba-openapi.json")
    rows = []
    for i, item in enumerate(files, 1):
        if item["sha256"] in done:
            prior = done[item["sha256"]]
            rows.append({**item, "url": prior["url"], "file_id": prior["file_id"],
                         "request_id": prior.get("request_id")})
            print(f"{i}/{len(files)} reuse {item['name']}", flush=True)
            continue
        response = client.upload_image(config, Path(item["file"]), None)
        result = response.get("upload_image_response") or {}
        error = client.api_error(response)
        if error or not result.get("photobank_url") or not result.get("file_id"):
            save(rows)
            raise RuntimeError({"failed": item["name"], "error": error,
                                "request_id": response.get("request_id")})
        url = str(result["photobank_url"])
        rows.append({**item, "url": "https:" + url if url.startswith("//") else url,
                     "file_id": str(result["file_id"]), "request_id": response.get("request_id")})
        save(rows)
        print(f"{i}/{len(files)} uploaded {item['name']}", flush=True)
    print(json.dumps({"complete": len(rows), "receipt": str(RECEIPT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
