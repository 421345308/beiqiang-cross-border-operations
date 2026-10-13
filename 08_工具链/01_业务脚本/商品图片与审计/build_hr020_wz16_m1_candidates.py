#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""HR020 WZ16 首图(M1)候选生成器。

约束(按 Root 2026-10-01 首轮视觉指导 与 唯一 SOP 第3节):
- 只做裁切、留白、构图与尺寸统一; 不重画鞋型/外底/颜色/结构, 不做抠图换背景。
- 首图为无字方图, 完整实鞋为视觉主体, 保留自然接触阴影, 使用纯白或克制中性背景。
- 同时输出原件同屏对照图, 供 Root 主审。

用法:
  python build_hr020_wz16_m1_candidates.py --src <01.webp> --out <dir>

产出:
  A_M1_v1_white_1000.jpg   鞋体约占画布 86% 宽, 居中
  A_M1_v2_white_1000.jpg   鞋体约占画布 76% 宽, 略低, 留白更克制
  A_M1_原件对照.jpg         原图 | v1 | v2 同屏
  m1_candidates_manifest.json
"""
import argparse
import hashlib
import json
import os

from PIL import Image

CANVAS = 1000
WHITE = (255, 255, 255)
# 背景判定: 亮度足够高且接近中性, 视为白底/可丢弃区域
LUM_BG = 244
NEUTRAL_SPREAD = 12


def subject_bbox(im: Image.Image) -> tuple:
    """返回非背景像素的外接框(含真实接触阴影)。"""
    w, h = im.size
    px = im.load()
    minx, miny, maxx, maxy = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            lum = (r * 299 + g * 587 + b * 114) // 1000
            spread = max(r, g, b) - min(r, g, b)
            if lum < LUM_BG or spread > NEUTRAL_SPREAD:
                if x < minx:
                    minx = x
                if y < miny:
                    miny = y
                if x > maxx:
                    maxx = x
                if y > maxy:
                    maxy = y
    if maxx < 0:
        return (0, 0, w, h)
    return (minx, miny, maxx + 1, maxy + 1)


def compose(src_im: Image.Image, bbox: tuple, target_ratio: float,
            vertical_shift: float) -> Image.Image:
    """把裁出的鞋体等比缩放到画布 target_ratio 宽, 居中并允许纵向偏移。"""
    x0, y0, x1, y1 = bbox
    crop = src_im.crop(bbox)
    cw, ch = crop.size
    target_w = int(CANVAS * target_ratio)
    scale = target_w / cw
    target_h = max(1, int(round(ch * scale)))
    if target_h > int(CANVAS * 0.96):
        scale = int(CANVAS * 0.96) / ch
        target_h = int(CANVAS * 0.96)
        target_w = max(1, int(round(cw * scale)))
    crop = crop.resize((target_w, target_h), Image.LANCZOS)

    canvas = Image.new("RGB", (CANVAS, CANVAS), WHITE)
    left = (CANVAS - target_w) // 2
    top = (CANVAS - target_h) // 2 + int(CANVAS * vertical_shift)
    top = max(0, min(CANVAS - target_h, top))
    canvas.paste(crop, (left, top))
    return canvas


def sha256(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="WZ16 01.webp 原图路径")
    ap.add_argument("--out", required=True, help="输出目录")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    src = Image.open(args.src)
    src.load()
    src_rgb = src.convert("RGB")
    bbox = subject_bbox(src_rgb)
    print("source", src.size, "subject_bbox", bbox)

    variants = [
        ("A_M1_v1_white_1000.jpg", 0.92, 0.00),
        ("A_M1_v2_white_1000.jpg", 0.80, 0.01),
    ]
    manifest = {
        "source": args.src,
        "source_size": list(src.size),
        "source_sha256": sha256(args.src),
        "subject_bbox": list(bbox),
        "canvas": CANVAS,
        "background": "pure white",
        "text": "none",
        "product_facts_changed": False,
        "variants": [],
    }
    made = []
    for name, ratio, shift in variants:
        im = compose(src_rgb, bbox, ratio, shift)
        p = os.path.join(args.out, name)
        im.save(p, "JPEG", quality=93, subsampling=0)
        manifest["variants"].append({
            "file": name,
            "target_width_ratio": ratio,
            "vertical_shift_ratio": shift,
            "sha256": sha256(p),
        })
        made.append(p)
        print("wrote", p)

    # 原件同屏对照
    tiles = [src_rgb.resize((CANVAS, CANVAS), Image.LANCZOS)]
    for p in made:
        tiles.append(Image.open(p).convert("RGB"))
    sheet = Image.new("RGB", (CANVAS * len(tiles), CANVAS), WHITE)
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * CANVAS, 0))
    sheet_path = os.path.join(args.out, "A_M1_原件对照.jpg")
    sheet.resize((CANVAS * len(tiles) // 2, CANVAS // 2), Image.LANCZOS).save(
        sheet_path, "JPEG", quality=90, subsampling=0)
    manifest["contact_sheet"] = {"file": "A_M1_原件对照.jpg", "sha256": sha256(sheet_path)}
    print("wrote", sheet_path)

    mp = os.path.join(args.out, "m1_candidates_manifest.json")
    with open(mp, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print("wrote", mp)


if __name__ == "__main__":
    main()
