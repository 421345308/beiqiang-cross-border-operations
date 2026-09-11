"""Run the verified HR Schema publisher against the continuation package.

The implementation intentionally reuses the already validated XML builder and
only redirects its package, matrix, URL map and receipt locations.  This keeps
the old HR001-HR008 receipts reproducible while letting HR009+ advance in
small, independently verified batches.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
BASE = ROOT / "08_工具链/01_业务脚本/国际站扩品/publish_hot_rank_hr_a_batch.py"


def load_base():
    spec = importlib.util.spec_from_file_location("hot_rank_publisher", BASE)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    publisher = load_base()
    publisher.PACK_ROOT = ROOT / "01_产品资产/01_原始数据包/热榜OEM概念款_2026-09-05"
    publisher.MATRIX = publisher.PACK_ROOT / "00_扩品差异化矩阵.csv"
    publisher.URL_MAP_PATH = publisher.PACK_ROOT / "00_图片银行URL映射.json"
    publisher.OUTPUT = ROOT / "02_Alibaba运营/05_扩品工程/热榜持续扩品_2026-09-05"
    publisher.PER_MODEL_RECEIPTS = True
    raise SystemExit(publisher.main())
