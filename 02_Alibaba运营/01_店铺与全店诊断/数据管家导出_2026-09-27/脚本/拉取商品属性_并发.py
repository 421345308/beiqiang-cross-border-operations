#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全量 BQ 181 款：拉取真实商品属性（只读，并发）"""
from __future__ import annotations
import csv, importlib.util, json, re, sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE = Path("/Users/shepeiqiang/WorkBuddy/2026-09-25-09-28-49")
OUT = BASE / "beiqiang_体检"
CLIENT = BASE / "beiqiang-cross-border-operations/.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"

spec = importlib.util.spec_from_file_location("bq", CLIENT)
client = importlib.util.module_from_spec(spec); spec.loader.exec_module(client)
CFG = client.load_config(client.DEFAULT_CONFIG)

raw = json.loads((OUT / "raw_product_list.json").read_text())
bq = [p for p in raw if re.match(r"^\s*BQ", str(p.get("red_model") or ""))]
print(f"BQ 款: {len(bq)}", file=sys.stderr)

# 绩效数据（曝光/点击/询盘）
perf = {}
for r in csv.DictReader(open(OUT / "BQ逐款标题强度.csv", encoding="utf-8-sig")):
    perf[str(r["产品ID"])] = r


def call(m, params):
    try:
        r = client.top_call(CFG, m, params, True)
    except Exception as e:
        return None, str(e)[:200]
    if isinstance(r.get("error_response"), dict):
        return None, r["error_response"]
    return r, None


def parse_sku(sk):
    skus = (sk or {}).get("skus") or []
    colors, sizes = Counter(), set()
    for s in skus:
        code = str(s.get("sku_code") or "")
        parts = code.split("-")
        if parts and re.fullmatch(r"\d{2,3}", parts[-1]):
            sizes.add(int(parts[-1]))
        if len(parts) >= 2:
            colors[parts[-2]] += 1
    return [c for c, _ in colors.most_common()], sorted(sizes)


def one(p):
    pid = str(p["id"])
    eid = str(p.get("product_id"))
    r, err = call("alibaba.icbu.product.get", {"product_id": eid, "language": "ENGLISH"})
    if err:
        f = perf.get(pid, {})
        return {"产品ID": pid, "型号": p.get("red_model"), "分组": p.get("group_name"),
                "状态": p.get("status"), "当前标题": p.get("subject"),
                "搜索曝光": f.get("曝光", ""), "搜索点击": f.get("点击", ""),
                "点击率": f.get("CTR", ""), "询盘人数": f.get("询盘人数", ""),
                "_颜色": "", "_SKU色数": 0, "_尺码": "", "_主图数": 0, "_更新": "",
                "_属性": {}, "_错误": str(err)[:160]}
    d = r.get("product") or {}
    attrs = {}
    for a in d.get("attributes") or []:
        n, v = a.get("attribute_name"), a.get("value_name")
        if not n or not v:
            continue
        attrs[n] = (attrs[n] + " / " + str(v)) if n in attrs else str(v)
    colors, sizes = parse_sku(d.get("product_sku"))
    st = d.get("sourcing_trade") or {}
    imgs = ((d.get("main_image") or {}).get("images") or [])
    f = perf.get(pid, {})
    return {
        "产品ID": pid,
        "型号": p.get("red_model"),
        "分组": p.get("group_name"),
        "状态": p.get("status"),
        "当前标题": d.get("subject") or p.get("subject"),
        "搜索曝光": f.get("曝光", ""),
        "搜索点击": f.get("点击", ""),
        "点击率": f.get("CTR", ""),
        "询盘人数": f.get("询盘人数", ""),
        "_颜色": "/".join(colors),
        "_SKU色数": len(colors),
        "_尺码": f"{sizes[0]}-{sizes[-1]}" if sizes else "",
        "_主图数": len(imgs),
        "_更新": str(d.get("gmt_modified") or "")[:10],
        "_属性": attrs,
    }


rows = []
with ThreadPoolExecutor(max_workers=6) as ex:
    futs = {ex.submit(one, p): p for p in bq}
    for i, fu in enumerate(as_completed(futs), 1):
        rows.append(fu.result())
        if i % 30 == 0:
            print(f"  {i}/{len(bq)}", file=sys.stderr)

err = [x for x in rows if "_错误" in x]
print(f"完成 {len(rows)}，错误 {len(err)}", file=sys.stderr)
if err:
    for e in err[:5]:
        print("  ERR", e["型号"], e["_错误"][:100], file=sys.stderr)

(OUT / "BQ全量属性.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))

ATTR_KEYS = ["Style", "Closure Type", "Upper Material", "Midsole Material", "Outsole Material",
             "Lining Material", "Toe Style", "Feature", "Season", "Fit Type", "Pattern",
             "Sole Construction", "Size", "US Size", "Model Number"]
with open(OUT / "BQ全量属性.csv", "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh)
    w.writerow(["产品ID", "型号", "分组", "搜索曝光", "搜索点击", "点击率", "询盘人数",
                "当前标题", "颜色", "SKU色数", "尺码", "主图数", "更新日"] + ATTR_KEYS)
    for x in rows:
        a = x.get("_属性") or {}
        w.writerow([x["产品ID"], x["型号"], x["分组"], x["搜索曝光"], x["搜索点击"], x["点击率"],
                    x["询盘人数"], x["当前标题"], x["_颜色"], x["_SKU色数"], x["_尺码"], x["_主图数"], x["_更新"]]
                   + [a.get(k, "") for k in ATTR_KEYS])
print("已写出 BQ全量属性.csv / .json", file=sys.stderr)
