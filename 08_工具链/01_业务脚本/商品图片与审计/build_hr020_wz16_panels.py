#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""HR020 WZ16 主图 M2-M6 与详情图 D1-D4 版面生成器（纯位图合成）。

约束（唯一 SOP 第3/4节 + Root 2026-10-01 首轮视觉指导）：
- 只用 WZ16 六张真实原图像素；不做抠图、不改色、不重画鞋型/鞋底/结构。
- 每张图回答一个买家问题、带一项具体证据；避免尺码/颜色卡片重复占位。
- 不写未证实的性能、包装尺寸、定制承诺或供货承诺；最终价未冻结前图内不出现报价数字。
- 无中文、无水印、无第三方品牌、无联系方式、无价格标签。

用法：
  python build_hr020_wz16_panels.py --imgs <原图目录> --out <输出目录>
"""
import argparse
import hashlib
import json
import os

from PIL import Image, ImageDraw, ImageFont

FONT_R = r"C:\Windows\Fonts\arial.ttf"
FONT_B = r"C:\Windows\Fonts\arialbd.ttf"
INK = (26, 26, 26)
BODY = (60, 60, 60)
RULE = (214, 214, 214)
WHITE = (255, 255, 255)
MAX_SCALE = 1.3      # 放大上限：低分辨率来源不得超过约 1.3 倍，避免像素化


def font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_B if bold else FONT_R, size)


def load(base: str, idx: int) -> Image.Image:
    im = Image.open(os.path.join(base, f"{idx:02d}.webp"))
    im.load()
    return im.convert("RGB")


def contain(img: Image.Image, bw: int, bh: int, max_scale: float = None) -> Image.Image:
    """等比缩放到框内；max_scale 限制放大倍数，避免低分辨率来源像素化。"""
    w, h = img.size
    s = min(bw / w, bh / h)
    if max_scale is not None and s > max_scale:
        s = max_scale
    return img.resize((max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)


def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def build(spec, imgs, outdir):
    C = spec["canvas"]
    canvas = Image.new("RGB", (C, C), WHITE)
    d = ImageDraw.Draw(canvas)
    m = int(C * 0.055)                      # 页边距
    f_kicker = font(False, int(C * 0.023))
    f_title = font(True, int(C * 0.038))
    f_body = font(False, int(C * 0.029))
    line_h = int(C * 0.040)
    t_gap = int(C * 0.048)

    # 先按实际换行数算正文块高度，避免底部大面积空白
    bw = C - 2 * m
    wrapped = []
    for ln in spec["lines"]:
        wrapped.extend(wrap(d, ln, f_body, bw))
    body_h = len(wrapped) * line_h

    y = m
    if spec.get("kicker"):
        d.text((m, y), spec["kicker"].upper(), font=f_kicker, fill=(120, 120, 120))
        y += int(C * 0.040)
    d.text((m, y), spec["title"], font=f_title, fill=INK)
    y += t_gap

    photo_top = y
    photo_bottom = C - m - body_h - int(C * 0.030)
    bh = max(60, photo_bottom - photo_top)

    photos = spec["photos"]
    if spec.get("tint"):
        d.rectangle((m, photo_top, C - m, photo_bottom), fill=(246, 246, 246))

    ms = spec.get("max_scale", MAX_SCALE)
    if len(photos) == 1:
        src, box = photos[0]
        img = imgs[src] if not box else imgs[src].crop(box)
        t = contain(img, bw, bh, ms)
        canvas.paste(t, (m + (bw - t.width) // 2, photo_top + (bh - t.height) // 2))
    else:
        gap = int(C * 0.028)
        cw = (bw - gap * (len(photos) - 1)) // len(photos)
        lf = font(True, int(C * 0.026))
        lab_h = int(C * 0.044) if spec.get("photo_labels") else 0
        for i, (src, box) in enumerate(photos):
            img = imgs[src] if not box else imgs[src].crop(box)
            t = contain(img, cw, bh - lab_h, ms)
            x0 = m + i * (cw + gap) + (cw - t.width) // 2
            canvas.paste(t, (x0, photo_top + (bh - lab_h - t.height) // 2))
            labels = spec.get("photo_labels") or []
            if i < len(labels):
                lbl = labels[i]
                tw = d.textlength(lbl, font=lf)
                d.text((x0 + (t.width - tw) / 2, photo_top + bh - int(C * 0.034)), lbl, font=lf, fill=INK)

    ry = photo_bottom + int(C * 0.022)
    d.line((m, ry, C - m, ry), fill=RULE, width=1)
    ty = ry + int(C * 0.024)
    for seg in wrapped:
        d.text((m, ty), seg, font=f_body, fill=BODY)
        ty += line_h

    path = os.path.join(outdir, spec["file"])
    canvas.save(path, "JPEG", quality=93, subsampling=0)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--imgs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="", help="逗号分隔的槽位，如 M2,D2,D3,D4；留空=全部")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    LACING = (300, 200, 700, 680)   # 01 的系带/开放鞋带片区（扩大裁切范围，保留更多鞋体）
    SOLE = (60, 215, 800, 759)      # 03 的鞋面缝线+外底侧面+鞋跟构成区（保留整鞋可见）
    BAND6 = (0, 0, 750, 684)        # 06 去除底部中文横条（原像素矩形裁切）

    imgs = {i: load(args.imgs, i) for i in range(1, 7)}

    specs = [
        # ---- 主图 M2-M5（M6 直接复用 v3 公司图原件，不由本脚本生成）----
        # M2：整鞋 + 小局部；特写放大不超过来源约 1.3 倍；文案只解释开放式系带
        dict(key="M2", file="A_M2_laceup_construction_1000.jpg", canvas=1000, tint=True,
             kicker="Closure & Construction", title="Lace-Up Derby Construction",
             photos=[(1, None), (1, LACING)], photo_labels=["Full view", "Closure detail"],
             lines=["Open lacing with an adjustable tie.",
                    "Two facing quarters with a stitched edge."]),
        dict(key="M3", file="A_M3_available_colours_1000.jpg", canvas=1000,
             kicker="Product Options", title="Available Colours",
             photos=[(3, None), (4, None)], photo_labels=["Black", "Brown"],
             lines=["Black and Brown are the listed colourways.",
                    "Confirm your colour assortment per order."]),
        dict(key="M4", file="A_M4_material_specification_1000.jpg", canvas=1000,
             kicker="Specification", title="Material Specification",
             photos=[(5, None)],
             lines=["Upper: Genuine Leather", "Lining: Faux Leather",
                    "Midsole: Rubber", "Outsole: Rubber"]),
        dict(key="M5", file="A_M5_wholesale_ordering_1000.jpg", canvas=1000, tint=True,
             kicker="Purchasing", title="Wholesale Ordering",
             photos=[(2, None)],
             lines=["Minimum order: 2 pairs.",
                    "Quantity tiers: 2 / 30 / 300 pairs.",
                    "Share your size and colour mix for a quotation.",
                    "Final price confirmed per order."]),
        # ---- 详情图 D1-D4 ----
        dict(key="D1", file="A_D1_product_overview_1200.jpg", canvas=1200,
             kicker="Detail", title="Product Overview",
             photos=[(5, None)],
             lines=["Men's low-top lace-up Derby shoe.",
                    "Rounded plain toe, low heel and a clean plain vamp.",
                    "Listed in Black and Brown, EU 39-44."]),
        # D2：无制作过程说明；限制放大倍数
        dict(key="D2", file="A_D2_construction_detail_1200.jpg", canvas=1200,
             kicker="Detail", title="Construction & Stitching Detail",
             photos=[(3, SOLE)],
             lines=["Stitched seam running from the lacing to the heel.",
                    "Ribbed sole edge with a low heel block.",
                    "Plain vamp with no brogue perforation."]),
        # D3：去掉 orderable combinations 表述
        dict(key="D3", file="A_D3_colours_and_sizes_1200.jpg", canvas=1200,
             kicker="Detail", title="Colours and Sizes",
             photos=[(4, None), (3, None)], photo_labels=["Brown", "Black"],
             lines=["Colours: Black and Brown.",
                    "Sizes: EU 39, 40, 41, 42, 43, 44.",
                    "Select from two colours and EU 39-44."]),
        # D4：改为买家输入措辞；删除本款未验证的流程承诺
        dict(key="D4", file="A_D4_ordering_and_enquiry_1200.jpg", canvas=1200, tint=True,
             kicker="Detail", title="Ordering & Enquiry",
             photos=[(2, None)],
             lines=["Minimum order: 2 pairs.",
                    "Send model, quantity and size mix for a quotation.",
                    "Send logo, sample and packing requirements for review."]),
    ]

    only = {x.strip().upper() for x in (args.only or "").split(",") if x.strip()}

    manifest = {"note": "只做裁切/缩放/白底构图与英文版面；未改鞋型/鞋底/配色/结构；无中文；无价格数字。"
                        "放大倍数上限 %.1f，避免低分辨率来源像素化。" % MAX_SCALE,
                "files": []}
    for spec in specs:
        if only and spec["key"] not in only:
            continue
        p = build(spec, imgs, args.out)
        manifest["files"].append({
            "slot": spec["key"], "file": spec["file"], "canvas": spec["canvas"], "title": spec["title"],
            "buyer_question": spec.get("kicker"), "lines": spec["lines"],
            "sources": [f"{s:02d}.webp" for s, _ in spec["photos"]],
            "max_scale": spec.get("max_scale", MAX_SCALE),
            "sha256": hashlib.sha256(open(p, "rb").read()).hexdigest(),
            "bytes": os.path.getsize(p)})
        print("wrote", p)

    mpath = os.path.join(args.out, "panels_manifest.json")
    if os.path.exists(mpath):
        prev = json.load(open(mpath, encoding="utf-8"))
        by_slot = {f.get("slot") or f.get("file"): f for f in prev.get("files", [])}
        for f in manifest["files"]:
            by_slot[f.get("slot") or f["file"]] = f
        order = ["M2", "M3", "M4", "M5", "M6", "D1", "D2", "D3", "D4"]
        merged = [by_slot[k] for k in order if k in by_slot]
        merged += [v for k, v in by_slot.items() if k not in order]
        manifest["files"] = merged
    with open(mpath, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print("wrote panels_manifest.json (%d entries)" % len(manifest["files"]))


if __name__ == "__main__":
    main()
