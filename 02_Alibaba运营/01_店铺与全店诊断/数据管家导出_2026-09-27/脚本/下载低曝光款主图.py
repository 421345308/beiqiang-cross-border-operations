#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""下载最低曝光 BQ 款的主图（纯本地清单，无需 API）"""
from __future__ import annotations
import csv, json, re, sys, urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

OUT = Path("/Users/shepeiqiang/WorkBuddy/2026-09-25-09-28-49/beiqiang_体检")
IMG = OUT / "主图_低曝光"
if not IMG.is_dir():
    raise SystemExit(f"目录不存在，请先创建: {IMG}")

raw = json.loads((OUT / "raw_product_list.json").read_text())
by_id = {str(p["id"]): p for p in raw}

plan = list(csv.DictReader(open(OUT / "BQ标题总方案_第三轮.csv", encoding="utf-8-sig")))
targets = [x for x in plan if int(x["搜索曝光"]) <= 20]
print(f"目标 {len(targets)} 款（曝光 ≤ 20）", file=sys.stderr)


def safe(name):
    return re.sub(r"[^0-9A-Za-z\-_.]", "_", name)[:60]


def dl(url, fp):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=25).read()
        if len(data) > 2000:
            fp.write_bytes(data)
            return len(data)
    except Exception:
        pass
    return 0


def one(x):
    pid = str(x["产品ID"])
    p = by_id.get(pid)
    if not p:
        return {**x, "_错误": "清单中无此 ID"}
    imgs = (p.get("main_image") or {}).get("images") or []
    urls = [u for u in imgs if isinstance(u, str) and u.startswith("http")]
    saved, n = [], 0
    for i, u in enumerate(urls[:6], 1):
        fp = IMG / f"{safe(x['型号'])}_M{i}.jpg"
        if dl(u, fp):
            saved.append(fp.name); n += 1
    return {**x, "_主图URL_1": urls[0] if urls else "", "_URL数": len(urls), "_下载数": n, "_文件": saved}


rows = []
with ThreadPoolExecutor(max_workers=8) as ex:
    futs = {ex.submit(one, x): x for x in targets}
    for i, fu in enumerate(as_completed(futs), 1):
        rows.append(fu.result())
        if i % 15 == 0:
            print(f"  {i}/{len(targets)}", file=sys.stderr)

ok = [r for r in rows if r.get("_下载数", 0) > 0]
print(f"\n完成：{len(ok)}/{len(rows)} 款下载到主图", file=sys.stderr)
(OUT / "低曝光款_主图清单.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))

urls = Counter(r.get("_主图URL_1", "") for r in rows if r.get("_主图URL_1"))
print(f"\n=== 首图 URL 复用（唯一 {len(urls)} / 有图 {len([r for r in rows if r.get('_主图URL_1')])} 款）===", file=sys.stderr)
for u, c in urls.most_common(15):
    if c > 1:
        ms = [r["型号"] for r in rows if r.get("_主图URL_1") == u]
        print(f"  ×{c}  {', '.join(ms)}", file=sys.stderr)

# 完整六图重复
allimgs = Counter()
for r in rows:
    p = by_id.get(str(r["产品ID"]))
    for u in ((p or {}).get("main_image") or {}).get("images") or []:
        if isinstance(u, str):
            allimgs[u] += 1
reused = {u: c for u, c in allimgs.items() if c > 1}
print(f"\n=== 六图层面：{len(reused)} 张图被多款共用（共 {sum(reused.values())} 次引用）===", file=sys.stderr)

# 同款家族（同一供货型号）内部六图重合度
fam = {}
for r in rows:
    m = str(r["型号"])
    base = re.match(r"^(BQ[-\s]?\d+)", m)
    if base:
        fam.setdefault(base.group(1).replace(" ", ""), []).append(r)
print("\n=== 同款家族内部首图差异 ===", file=sys.stderr)
for k, vs in sorted(fam.items()):
    if len(vs) < 2:
        continue
    us = [v.get("_主图URL_1", "") for v in vs]
    uniq = len(set(u for u in us if u))
    flag = "⚠️ 全部共用" if uniq == 1 else ("△ 部分重合" if uniq < len(vs) else "✅ 各自独立")
    print(f"  {k}: {len(vs)} 款链接，唯一首图 {uniq} 张  {flag}", file=sys.stderr)
