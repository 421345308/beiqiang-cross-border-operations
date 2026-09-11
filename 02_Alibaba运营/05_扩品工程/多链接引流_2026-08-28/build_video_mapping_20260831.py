from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
VIDEO_DIR = Path(r"E:\贝强大文件\05_内容与视频\01_贝强商品视频\alibaba_real_video_batch_20260828\edit\platform_45s")
OUT = ROOT / "outputs" / "20260831_full_excel_title_video"
UNIVERSAL = VIDEO_DIR / "Beiqiang_Factory_Universal_42s_20260828.mp4"

UNIVERSAL_VIDEO_NAME = "Beiqiang Footwear Factory Overview 42s"
UNIVERSAL_VIDEO_VID = "6000342456358"
SPECIFIC_VIDEO_VIDS = {
    "BQ003": "6000342452658",
    "BQ004": "6000342458004",
    "BQ005": "6000342448821",
    "BQ006": "6000342476773",
    "BQ007": "6000342472988",
    "BQ008": "6000342486240",
    "BQ009": "6000342486274",
    "BQ010": "6000342480664",
    "BQ011": "6000342486278",
    "BQ012": "6000342478704",
    "BQ013": "6000342478708",
    "BQ014": "6000342478709",
    "BQ015": "6000342486316",
    "BQ016": "6000342486320",
    "BQ017": "6000342474924",
    "BQ018": "6000342488091",
    "BQ019": "6000342474934",
    "BQ020": "6000342478785",
    "BQ021": "6000342474941",
    "BQ022": "6000342474946",
    "BQ023": "6000342474948",
    "BQ025": "6000342478797",
    "BQ026": "6000342480763",
    "BQ027": "6000342488124",
    "BQ028": "6000342486368",
}
REVIEWING_SKUS = {"BQ027", "BQ028"}


def main() -> None:
    specific = {p.name[:5]: p for p in VIDEO_DIR.glob("BQ???_Alibaba_43s_20260828.mp4")}
    if not UNIVERSAL.exists():
        raise FileNotFoundError(UNIVERSAL)
    rows = []
    for number in list(range(1, 53)) + [59]:
        code = f"BQ{number:03d}"
        path = specific.get(code, UNIVERSAL)
        is_specific = code in specific
        video_name = f"{code} Product and Factory Overview 43s" if is_specific else UNIVERSAL_VIDEO_NAME
        video_vid = SPECIFIC_VIDEO_VIDS[code] if is_specific else UNIVERSAL_VIDEO_VID
        review_status = "审核中" if code in REVIEWING_SKUS else "审核通过"
        rows.append({
            "sku": code,
            "video_role": "SKU product video" if is_specific else "universal factory video",
            "file_name": path.name,
            "local_path": str(path),
            "duration_seconds": 43.021 if is_specific else 42.021,
            "resolution": "1920x1080",
            "video_codec": "H.264",
            "audio_codec": "AAC",
            "excel_field": "L / 产品视频",
            "video_name": video_name,
            "video_vid": video_vid,
            "review_status": review_status,
            "video_bank_url": "",
            "status": "VIDEO_BANK_REVIEWING" if code in REVIEWING_SKUS else "VIDEO_BANK_APPROVED",
        })
    OUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUT / "53款商品主图视频映射_2026-08-31.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    payload = {
        "policy": "Use the matching SKU video when available; otherwise use the 42-second universal factory video. Write only an official Alibaba video-bank URL to Excel column L.",
        "specific_video_skus": sorted(specific),
        "specific_video_count": len(specific),
        "universal_video_sku_count": len(rows) - len(specific),
        "video_bank_upload_completed_at": "2026-09-01",
        "universal_video_name": UNIVERSAL_VIDEO_NAME,
        "universal_video_vid": UNIVERSAL_VIDEO_VID,
        "reviewing_skus": sorted(REVIEWING_SKUS),
        "rows": rows,
    }
    (OUT / "53款商品主图视频映射_2026-08-31.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"products": len(rows), "specific": len(specific), "universal": len(rows) - len(specific), "csv": str(csv_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
