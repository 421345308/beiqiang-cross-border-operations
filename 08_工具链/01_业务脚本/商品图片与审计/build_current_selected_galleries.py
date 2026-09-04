from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
DETAILS = ROOT / "02_Alibaba运营/01_店铺与全店诊断/全量商品审查_2026-09-04/api_product_get_details.json"
OUT = Path(r"E:\贝强大文件\01_产品资产\02_可发布素材\00_全店统一升级_2026-09-04\03_当前六图复核")
TARGETS = [
    "1601839105416", "1601924292931", "1601924347721", "1601939638522",
    "1601939705262", "1601939726170", "1601939736061", "10000042821848",
    "10000042896165", "10000043201799", "10000046705043", "10000047198577",
    "10000047208726", "10000047216427", "10000047220568", "10000047221334",
    "10000047392343", "10000047396313",
]


def fetch(url: str) -> Image.Image:
    for attempt in range(1, 6):
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=60) as response:
                data = response.read()
            source = Image.open(BytesIO(data)).convert("RGBA")
            white = Image.new("RGBA", source.size, (255, 255, 255, 255))
            white.alpha_composite(source)
            return white.convert("RGB")
        except Exception:
            if attempt == 5:
                raise
            time.sleep(attempt)
    raise RuntimeError("unreachable")


def main() -> None:
    data = json.loads(DETAILS.read_text(encoding="utf-8-sig"))
    OUT.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 17)

    def build(pid: str) -> str:
        product = data[pid]["product"]
        urls = list((product.get("main_image") or {}).get("images") or [])
        sheet = Image.new("RGB", (1500, 620), (245, 247, 248))
        draw = ImageDraw.Draw(sheet)
        draw.text((20, 10), f"{pid} | {product.get('subject')}", fill=(15, 23, 42), font=font)
        for slot, url in enumerate(urls, 1):
            image = fetch(url)
            image.thumbnail((230, 500), Image.Resampling.LANCZOS)
            x = (slot - 1) * 250 + 10
            sheet.paste(image, (x, 55 + (500 - image.height) // 2))
            draw.text((x + 98, 570), f"M{slot}", fill=(15, 23, 42), font=font)
        sheet.save(OUT / f"{pid}.jpg", quality=92)
        return pid

    with ThreadPoolExecutor(max_workers=6) as pool:
        jobs = [pool.submit(build, pid) for pid in TARGETS]
        for job in as_completed(jobs):
            print(job.result(), flush=True)


if __name__ == "__main__":
    main()
