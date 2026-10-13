#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""HR020 WZ16 颜色 SKU 图生成器。

约束(按唯一 SOP 第4节 颜色图验收 与 Root 2026-10-01 视觉指导):
- 每个颜色只展示当前款的一个真实颜色; 统一角度、统一比例、干净中性背景。
- 禁止多角度拼图、文字卖点、改色生成来源未证明的颜色。
- 只做裁切、留白、构图与尺寸统一; 不重画鞋型/鞋底/配色。

用法:
  python build_hr020_wz16_sku_colors.py --black 03.webp --brown 04.webp --out <dir>
"""
import argparse
import hashlib
import json
import os

from PIL import Image

CANVAS = 1000
WHITE = (255, 255, 255)
LUM_BG = 244
NEUTRAL_SPREAD = 12
TARGET_RATIO = 0.90


def subject_bbox(im: Image.Image) -> tuple:
    w, h = im.size
    px = im.load()
    minx, miny, maxx, maxy = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            lum = (r * 299 + g * 587 + b * 114) // 1000
            spread = max(r, g, b) - min(r, g, b)
            if lum < LUM_BG or spread > NEUTRAL_SPREAD:
                minx = min(minx, x); miny = min(miny, y)
                maxx = max(maxx, x); maxy = max(maxy, y)
    return (0, 0, w, h) if maxx < 0 else (minx, miny, maxx + 1, maxy + 1)


def compose(path: str, target_ratio: float = TARGET_RATIO) -> Image.Image:
    im = Image.open(path)
    im.load()
    rgb = im.convert("RGB")
    crop = rgb.crop(subject_bbox(rgb))
    cw, ch = crop.size
    tw = int(CANVAS * target_ratio)
    th = max(1, int(round(ch * (tw / cw))))
    crop = crop.resize((tw, th), Image.LANCZOS)
    canvas = Image.new("RGB", (CANVAS, CANVAS), WHITE)
    canvas.paste(crop, ((CANVAS - tw) // 2, (CANVAS - th) // 2))
    return canvas


def sha256(p: str) -> str:
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--black", required=True)
    ap.add_argument("--brown", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    manifest = {"canvas": CANVAS, "background": "pure white", "text": "none",
                "angle_consistency": "both from the same source camera angle (03/04)",
                "product_facts_changed": False, "files": []}
    for label, src in (("Black", args.black), ("Brown", args.brown)):
        out = os.path.join(args.out, f"SKU_{label}.jpg")
        compose(src).save(out, "JPEG", quality=93, subsampling=0)
        manifest["files"].append({
            "label": label, "file": os.path.basename(out),
            "source": os.path.basename(src), "source_sha256": sha256(src),
            "sha256": sha256(out),
        })
        print("wrote", out)

    mp = os.path.join(args.out, "sku_colors_manifest.json")
    with open(mp, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print("wrote", mp)


if __name__ == "__main__":
    main()
