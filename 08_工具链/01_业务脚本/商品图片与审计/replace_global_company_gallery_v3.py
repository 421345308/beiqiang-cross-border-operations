from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
BASE_PATH = ROOT / "08_工具链/01_业务脚本/商品图片与审计/replace_global_company_gallery_v2.py"
ASSET_ROOT = Path(
    r"E:\贝强大文件\01_产品资产\02_可发布素材\00_最终上传\00_共用中性公司图_v3_2026-09-04"
)
RECEIPT_ROOT = ROOT / "02_Alibaba运营/01_店铺与全店诊断/全量商品审查_2026-09-04/公司图v3"
V2_MAPPING = ROOT / "02_Alibaba运营/01_店铺与全店诊断/全量商品审查_2026-09-04/公司图v2/图片银行映射.json"
V3_INITIAL_MAPPING = RECEIPT_ROOT / "图片银行映射_试点初版.json"


def load_base():
    spec = importlib.util.spec_from_file_location("replace_global_company_gallery_v2", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def configure(base):
    accepted_keys = set(base.OLD_KEYS)
    for mapping in (V2_MAPPING, V3_INITIAL_MAPPING):
        if mapping.is_file():
            for row in json.loads(mapping.read_text(encoding="utf-8-sig")):
                accepted_keys.add(base.image_key(str(row["url"])))

    base.ASSET_ROOT = ASSET_ROOT
    base.RECEIPT_ROOT = RECEIPT_ROOT
    base.FILES = [
        (ASSET_ROOT / "01_factory_profile.jpg", 400, "Company overview"),
        (ASSET_ROOT / "02_oem_odm_workflow.jpg", 550, "Customization capabilities"),
        (ASSET_ROOT / "03_production_process.jpg", 600, "Production workflow"),
        (ASSET_ROOT / "04_quality_control.jpg", 500, "Quality control"),
        (ASSET_ROOT / "05_packing_inquiry.jpg", 700, "Packaging & shipping specifications"),
    ]
    base.OLD_KEYS = accepted_keys
    return base


def main():
    base = configure(load_base())
    base.main()


if __name__ == "__main__":
    main()
