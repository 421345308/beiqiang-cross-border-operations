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

files = [
    PROJECT / r"01_正式主图候选\HR039-A_8025\M5_factory_quality.jpg",
    PROJECT / r"02_正式详情候选\HR039-A_8025\D3_colors_sizes.jpg",
    PROJECT / r"02_正式详情候选\HR039-A_8025\D5_oem_project_inputs.jpg",
]

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
    "purpose": "Replacement uploads after exact-duplicate removal",
    "receipts": receipts,
}

output = PROJECT / "HR039-A_8025_去重替换图上传回执.json"
output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(output)
