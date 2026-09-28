#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""量化低曝光款 M1 首图质量（对照项目 M1 标准：干净浅底、大主体、少文字）"""
from __future__ import annotations
import csv, json, re
from pathlib import Path
from statistics import median

from PIL import Image

OUT = Path("/Users/shepeiqiang/WorkBuddy/2026-09-25-09-28-49/beiqiang_体检")
IMG = OUT / "主图_低曝光"
rows = json.load(open(OUT / "低曝光款_主图清单.json", encoding="utf-8"))


def safe(name):
    return re.sub(r"[^0-9A-Za-z\-_.]", "_", name)[:60]


def corner_bg(im):
    """四角各取 6% 区域的中位色作为背景色"""
    W, H = im.size
    w, h = max(4, W // 16), max(4, H // 16)
    boxes = [(0, 0, w, h), (W - w, 0, W, h), (0, H - h, w, H), (W - w, H - h, W, H)]
    px = []
    for b in boxes:
        px += list(im.crop(b).convert("RGB").getdata())
    px.sort(key=lambda c: sum(c))
    return px[len(px) // 2]


def analyze(fp):
    im = Image.open(fp).convert("RGB")
    W, H = im.size
    small = im.resize((min(W, 400), min(H, 400)))
    w, h = small.size
    bg = corner_bg(small)
    data = list(small.getdata())

    def d(c):
        return ((c[0] - bg[0]) ** 2 + (c[1] - bg[1]) ** 2 + (c[2] - bg[2]) ** 2) ** 0.5

    # 产品像素
    mask = [d(c) > 26 for c in data]
    prod = sum(mask)
    # 包围盒
    xs = [i % w for i, m in enumerate(mask) if m]
    ys = [i // w for i, m in enumerate(mask) if m]
    if xs:
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        bbox = ((x1 - x0 + 1) * (y1 - y0 + 1)) / (w * h)
        mtop, mbot = y0 / h, (h - y1) / h
        mleft, mright = x0 / w, (w - x1) / w
    else:
        bbox = mtop = mbot = mleft = mright = 0.0
    # 顶部色带检测（型号标签）：顶部 18% 区域与背景差异大的像素比例
    top = slice(0, int(h * 0.18))
    top_px = [data[i] for i in range(w * h) if (i // w) < int(h * 0.18)]
    top_diff = sum(1 for c in top_px if d(c) > 40) / max(1, len(top_px))
    white_dist = ((255 - bg[0]) ** 2 + (255 - bg[1]) ** 2 + (255 - bg[2]) ** 2) ** 0.5
    return dict(W=W, H=H, bg=bg, white_dist=round(white_dist, 1),
                product_ratio=round(prod / (w * h), 3), bbox_ratio=round(bbox, 3),
                margin_top=round(mtop, 3), margin_bottom=round(mbot, 3),
                margin_side=round((mleft + mright) / 2, 3), top_band=round(top_diff, 3))


out = []
for r in rows:
    m = str(r["型号"])
    fp = IMG / f"{safe(m)}_M1.jpg"
    if not fp.exists():
        out.append({"型号": m, "分组": r["分组"], "曝光": r["搜索曝光"], "_状态": "无首图"})
        continue
    try:
        a = analyze(fp)
    except Exception as e:
        out.append({"型号": m, "分组": r["分组"], "曝光": r["搜索曝光"], "_状态": f"读取失败 {e}"})
        continue
    out.append({"型号": m, "分组": r["分组"], "曝光": r["搜索曝光"],
                "尺寸": f"{a['W']}x{a['H']}", "背景色": "/".join(map(str, a["bg"])),
                "背景白度距": a["white_dist"], "产品占比": a["product_ratio"],
                "包围盒占比": a["bbox_ratio"], "上留白": a["margin_top"],
                "下留白": a["margin_bottom"], "左右留白": a["margin_side"],
                "顶部色带": a["top_band"], "_状态": "ok"})

with open(OUT / "低曝光款_M1质量指标.csv", "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
    w.writeheader(); w.writerows(out)

ok = [x for x in out if x["_状态"] == "ok"]
print(f"分析完成 {len(ok)}/{len(out)}\n")
print("=== 背景是否纯白（白度距越小越白；>40 明显偏色）===")
nb = [x for x in ok if x["背景白度距"] > 40]
print(f"  非纯白背景: {len(nb)}/{len(ok)} 款 ({len(nb)/len(ok)*100:.0f}%)")
for x in sorted(nb, key=lambda z: -z["背景白度距"])[:8]:
    print(f"    {x['型号'][:24]:<25} 背景 {x['背景色']:<14} 距 {x['背景白度距']}")
print("\n=== 产品占比（M1 要求大主体）===")
for lo, hi, lab in [(0, .15, "<15% 偏小"), (.15, .25, "15-25% 一般"), (.25, 1, ">25% 良好")]:
    n = [x for x in ok if lo <= x["包围盒占比"] < hi]
    print(f"  {lab:<12}{len(n):>3} 款 ({len(n)/len(ok)*100:.0f}%)")
print(f"  包围盒占比中位: {median(x['包围盒占比'] for x in ok):.3f}")
print("\n=== 上下留白 ===")
print(f"  上留白中位 {median(x['上留白'] for x in ok):.3f} / 下留白中位 {median(x['下留白'] for x in ok):.3f}")
many = [x for x in ok if x["上留白"] + x["下留白"] > 0.55]
print(f"  上下留白合计 >55%（产品被挤在中间）: {len(many)} 款")

print("\n=== 顶部色带（型号标签痕迹，>0.10 说明顶部有实心标签）===")
tb = [x for x in ok if x["顶部色带"] > 0.10]
print(f"  {len(tb)}/{len(ok)} 款 ({len(tb)/len(ok)*100:.0f}%)")
for x in sorted(tb, key=lambda z: -z["顶部色带"])[:6]:
    print(f"    {x['型号'][:24]:<25} 顶部色带占比 {x['顶部色带']:.3f}")
