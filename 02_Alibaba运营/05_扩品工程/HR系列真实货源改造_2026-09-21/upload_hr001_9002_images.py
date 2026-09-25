from __future__ import annotations

import hashlib
import importlib.util
import json
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
PROJECT = ROOT / r"02_Alibaba运营\05_扩品工程\HR系列真实货源改造_2026-09-21"
CLIENT = ROOT / r".agents\skills\alibaba-openapi-operator\scripts\alibaba_openapi.py"
OUTPUT = PROJECT / "HR001_9002_图片银行上传回执.json"

spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
api = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(api)
config = api.load_config(Path.home() / ".config/beiqiang/alibaba-openapi.json")

main_dir = PROJECT / r"01_正式主图候选\HR001_9002"
detail_dir = PROJECT / r"02_正式详情候选\HR001_9002"
files = sorted(main_dir.glob("M*.jpg")) + sorted(detail_dir.glob("D*.jpg")) + sorted(main_dir.glob("SKU*.jpg"))
if len(files) != 13:
    raise SystemExit(f"Expected 13 upload images, found {len(files)}")

receipts = []
for path in files:
    response = {}
    for attempt in range(8):
        response = api.upload_image(config, path, None)
        error = api.api_error(response)
        if not error:
            break
        transient = (
            error.get("code") == "ApiCallLimit"
            or error.get("type") == "ISP"
            or error.get("sub_code") == "000000"
        )
        if not transient:
            break
        time.sleep(min(2 + attempt * 2, 10))
    error = api.api_error(response)
    if error:
        raise RuntimeError({"file": str(path), "error": error, "response": response})
    receipts.append({
        "role": path.stem,
        "local_path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "response": response,
    })
    print(path.name, "uploaded")

payload = {
    "created_at": datetime.now().astimezone().isoformat(),
    "product": "HR001 / 9002",
    "expected_counts": {"main": 6, "product_detail": 5, "sku": 2},
    "receipts": receipts,
}
OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"output": str(OUTPUT), "uploaded": len(receipts)}, ensure_ascii=True))
