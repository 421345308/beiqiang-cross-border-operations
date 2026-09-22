from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\Users\spq\Desktop\贝强")
PROJECT = ROOT / r"02_Alibaba运营\05_扩品工程\HR系列真实货源改造_2026-09-21"
CLIENT = ROOT / r".agents\skills\alibaba-openapi-operator\scripts\alibaba_openapi.py"

spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

config = module.load_config(Path.home() / ".config/beiqiang/alibaba-openapi.json")

files = []
files.extend(sorted((PROJECT / "01_正式主图候选" / "HR039-A_8025").glob("M*.jpg")))
files.extend(sorted((PROJECT / "02_正式详情候选" / "HR039-A_8025").glob("D*.jpg")))
files.extend(sorted((ROOT / r"02_Alibaba运营\06_图片与检查记录\公司图复用模板_v4_2026-09-21").glob("C*.jpg")))

if len(files) != 16:
    raise SystemExit(f"Expected 16 upload images, found {len(files)}")

receipts = []
for path in files:
    response = module.upload_image(config, path, None)
    receipts.append(
        {
            "role": path.stem,
            "local_path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "response": response,
        }
    )
    print(path.name, "uploaded")

payload = {
    "created_at": datetime.now().astimezone().isoformat(),
    "product": "HR039-A / 8025",
    "expected_counts": {"main": 6, "product_detail": 5, "company": 5},
    "receipts": receipts,
}

output = PROJECT / "HR039-A_8025_图片银行上传回执.json"
output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(output)
