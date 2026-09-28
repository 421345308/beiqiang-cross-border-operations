#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BQ 全量标题重构（第三轮 · 定稿 v4）
纪律：事实只来自 ① 系统 attributes ② 作者旧标题已断言的内容；
      不跨品类借词；品牌词排除；标题不含型号；组内多维轮换保证不重复。
"""
from __future__ import annotations
import csv, json, re
from collections import Counter
from pathlib import Path
from statistics import median

OUT = Path("/Users/shepeiqiang/WorkBuddy/2026-09-25-09-28-49/beiqiang_体检")
MAXLEN, T_MIN = 128, 75          # 热榜完整标题中位 75；取 75 为下限，不强行凑长

BRANDS = re.compile(r"\b(nike|adidas|jordan|puma|skechers|vans|converse|reebok|new balance|asics|under armour)\b", re.I)
MODEL_RE = re.compile(r"\bBQ[-\s]?\d|\bZX\d+|\b[KMRLT]\d{4,5}\b|\bA\d{3}\b")

UPPER_MAP = {
    "stretch fabric": "Stretch Fabric", "knitted textile upper": "Knitted Textile",
    "knitted textile": "Knitted Textile", "knitted": "Knitted",
    "stretch knitted textile upper": "Stretch Knitted", "textile": "Textile",
    "high top knitted textile upper": "Knitted Textile",
}
LINING_MAP = {
    "mesh": "Mesh Lining", "textile": "Textile Lining",
    "textile / knitted upper": "Textile Lining", "knitted textile upper": "Textile Lining",
    "stretch textile upper": "Textile Lining", "textile upper": "Textile Lining",
    "breathable knitted upper": "Breathable Knit", "soft textile upper": "Soft Textile",
}
MIDSOLE_MAP = {
    "eva": "EVA Midsole", "md": "MD Midsole", "rubber": "Rubber Midsole",
    "chunky cushion": "Chunky Cushion Midsole", "cushion": "Cushion Midsole",
    "flexible cushion": "Flexible Cushion Midsole", "foamed material": "Foam Midsole",
}
CLOSURE_MAP = {"lace-up": "Lace Up", "slip-on": "Slip On", "elastic band": "Elastic Band"}
FEATURE_MAP = {
    "light weight": "Light Weight", "lightweight": "Light Weight", "breathable": "Breathable",
    "anti-slip": "Anti Slip", "comfort": "Comfortable", "comfortable": "Comfortable",
    "soft": "Soft", "anti-odor": "Anti Odor",
}

STYLE = ["Casual", "Fashion", "Classic", "Trendy", "Comfortable", "Modern", "Retro",
         "Minimalist", "Simple", "Sporty", "Elegant", "Daily"]
PRICE = ["High Quality", "New Design", "2026 New", "Fashion Design", "Premium Quality",
         "Best Quality", "New Arrival", "Hot Style"]
SCENE = ["Daily Wear", "Outdoor", "Indoor", "Office", "School", "Travel", "Home", "Walking Use"]

PINKISH = {"PINK", "RED", "RD", "PK", "APRICOT", "LAVENDER", "ROSE", "FUCHSIA", "WINE", "CORAL"}
CARRY = [("thick sole", "Thick Sole"), ("chunky", "Chunky"), ("anti-slip", "Anti Slip"),
         ("non-slip", "Non Slip"), ("retro", "Retro"), ("versatile", "Versatile"),
         ("soft sole", "Soft Sole"), ("canvas", "Canvas"), ("leather", "Leather")]

attrs = json.load(open(OUT / "BQ全量属性.json", encoding="utf-8"))
rows = list(csv.reader(open(OUT / "exports/Products-2026-09-19.csv", encoding="utf-8-sig")))
hdr = [h.strip() for h in rows[5]]
perf = {}
for r in rows[6:]:
    if not any(r):
        continue
    d = {hdr[i]: (r[i] if i < len(r) else "") for i in range(len(hdr))}
    if d.get("产品ID"):
        perf[d["产品ID"]] = d


def num(x):
    s = str(x or "").replace(",", "").replace("%", "").strip()
    try:
        return float(s)
    except Exception:
        return 0.0


def clean(v):
    return str(v or "").strip()


def norm(v):
    return clean(v).lower().replace("_", " ").strip()


def pick_cat(group, i):
    """按分组选品类主词 —— 保形态词、保 walking/casual 权重"""
    if re.search(r"high ?top|sock", group, re.I):
        return ["High Top Sneakers", "Casual Sneakers", "High Top Walking Shoes", "Sock Sneakers"][i % 4]
    if re.search(r"wide ?toe", group, re.I):
        return ["Wide Toe Box Walking Shoes", "Wide Toe Box Casual Shoes", "Wide Toe Box Sneakers"][i % 3]
    if re.search(r"regular ?fit", group, re.I):
        return ["Regular Fit Walking Shoes", "Regular Fit Casual Shoes", "Regular Fit Sneakers"][i % 3]
    if re.search(r"backless|mule", group, re.I):
        return ["Backless Walking Shoes", "Backless Casual Shoes", "Mule Sneakers"][i % 3]
    if re.search(r"kids|children|child", group, re.I):
        return ["Kids Walking Shoes", "Casual Sneakers", "Children Shoes", "Kids Shoes"][i % 4]
    if re.search(r"athletic|running|sport", group, re.I):
        return ["Sporty Walking Shoes", "Casual Sneakers", "Walking Sneakers", "Casual Shoes"][i % 4]
    # Slip-On / Lace-Up / 默认 —— shoes 覆盖优先（热榜常同时出现 shoes 与 sneakers）
    return ["Walking Shoes", "Casual Sneakers", "Walking Shoes", "Casual Shoes",
            "Walking Shoes", "Casual Walking Shoes", "Walking Shoes", "Casual Sneakers"][i % 8]


def h(s):
    """确定性散列（避免 PYTHONHASHSEED 随机化导致每次运行结果不同）"""
    return sum(ord(c) * (i + 1) for i, c in enumerate(str(s)))


def gender_of(x, group):
    title = clean(x.get("当前标题"))
    if re.search(r"kids|children|child", group, re.I):
        return "Kids", "分组为童鞋"
    if "BQ003-W1" in clean(x.get("型号")):
        return "Women's", "负责人确认（粉色针织女款）"
    if re.search(r"\bwomen'?s\b|\bladies\b", title, re.I) and not re.search(r"\bmen\b|\bmens\b", title, re.I):
        return "Women's", "旧标题已断言女款"
    if re.search(r"\bmen'?s\b|\bmens\b", title, re.I) and not re.search(r"women", title, re.I):
        return "Men's", "旧标题已断言男款"
    cols = [c.strip().upper() for c in (x.get("_颜色") or "").split("/") if c.strip()]
    if cols and all(c in PINKISH for c in cols):
        return "Women's", f"配色全为粉/红系（{'/'.join(cols)}）"
    if h(clean(x.get("型号"))) % 10 < 2:
        return "Mens", "男女同款（Mens 变体，覆盖 mens 词族 —— mens casual sneakers 指数 491）"
    return "Men and Women", "休闲鞋默认男女同款（负责人口径）"


WORDS = re.compile(r"[a-z']+")


def append_ok(parts, cand, extra=()):
    have = set(WORDS.findall((" ".join(parts) + " " + " ".join(extra)).lower()))
    return not any(w in have for w in WORDS.findall(cand.lower()))


result = []
by_group = {}
for x in attrs:
    by_group.setdefault(clean(x.get("分组")) or "(空)", []).append(x)

for gname, items in by_group.items():
    items.sort(key=lambda z: str(z.get("型号")))
    for i, x in enumerate(items):
        a = x.get("_属性") or {}
        old = clean(x.get("当前标题"))
        pid = str(x["产品ID"])
        d = perf.get(pid, {})
        parts, src = [], []

        g, greason = gender_of(x, gname)
        parts.append(g)
        src.append(f"性别={g}｜{greason}")

        cat = pick_cat(gname, i)
        is_kids = bool(re.search(r"kids|children|child", gname, re.I))
        if is_kids and cat == "Children Shoes":
            parts[0] = "Boys Girls"
            src.append("性别改为 Boys Girls 以承载 Children Shoes（热榜词指数 194）")

        # 风格词：避开与品类词撞词
        style = STYLE[(i * 5 + i // 3) % len(STYLE)]
        if not (append_ok(parts, style) and append_ok([cat], style)):
            for alt in STYLE:
                if append_ok(parts, alt) and append_ok([cat], alt):
                    style = alt
                    break
        if append_ok(parts, style) and append_ok([cat], style):
            parts.append(style)
        src.append(f"风格={style}（结构位，热榜 66% 使用）")

        # 闭合方式：属性优先，缺失则用分组名（弱事实）；与形态词组合时插到形态词之后
        cl = CLOSURE_MAP.get(norm(a.get("Closure Type")))
        cl_src = "属性 Closure Type"
        if not cl:
            if re.search(r"slip-?on", gname, re.I):
                cl, cl_src = "Slip On", "分组名（弱事实）"
            elif re.search(r"lace-?up", gname, re.I):
                cl, cl_src = "Lace Up", "分组名（弱事实）"
        cat_final = cat
        if cl:
            m = re.match(r"^(High Top|Wide Toe Box|Regular Fit|Backless|Sock)\s+(.*)$", cat)
            cat_final = f"{m.group(1)} {cl} {m.group(2)}" if m else f"{cl} {cat}"
            src.append(f"闭合={cl}（{cl_src}）")
        if "wide toe box" in norm(a.get("Fit Type")) and "wide toe box" not in cat_final.lower():
            cat_final = "Wide Toe Box " + cat_final
            src.append("属性 Fit Type=Wide Toe Box")
        parts.append(cat_final)
        src.append(f"品类={cat_final}（按分组词位分工）")

        # ---- 备选特色维度：按款轮换重点（热榜也是每款突出不同维度）----
        mat = UPPER_MAP.get(norm(a.get("Upper Material")))
        msrc = f"属性 Upper Material={a.get('Upper Material')}"
        if not mat:
            mat = LINING_MAP.get(norm(a.get("Lining Material")))
            msrc = f"属性 Lining Material={a.get('Lining Material')}"
        feats = [f.strip() for f in clean(a.get("Feature")).split("/") if f.strip()]
        fmapped = [FEATURE_MAP[f.lower()] for f in feats if FEATURE_MAP.get(f.lower())]
        fw = fmapped[h(clean(x.get("型号"))) % len(fmapped)] if fmapped else None
        ms = MIDSOLE_MAP.get(norm(a.get("Midsole Material")))
        ms = ms if (ms and ms != "EVA Midsole") else None
        carry = next((w for k, w in CARRY if k in old.lower()), None)
        season_ok = "all season" in clean(a.get("Season")).lower()
        lib = {
            "mat": (mat, f"材质={mat}（{msrc}）"),
            "feat": (fw, f"功能={fw}（属性 Feature={a.get('Feature')}）"),
            "scene": (SCENE[(i + i // 3) % len(SCENE)], "场景词（热榜 66% 使用，我方原仅 1%）"),
            "price": (PRICE[(i // 2) % len(PRICE)], "价格信号（热榜 38% 使用，我方原仅 3%）"),
            "season": ("All Seasons", "季节=All Seasons（属性一致）" if season_ok
                       else "季节=All Seasons（负责人口径；属性现非四季，建议同步改）"),
            "carry": (carry, f"保留旧标题断言={carry}"),
            "mid": (ms, f"中底={ms}（属性）"),
        }
        # 每款取 2 个特色维度，6 种组合均匀轮换 → 各维度覆盖约 50%（贴合热榜）
        POOL_KEYS = ["mat", "feat", "scene", "price"]
        COMBOS = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
        ci, cj = COMBOS[i % 6]
        keys = [POOL_KEYS[ci], POOL_KEYS[cj]]
        if i % 2 == 0:
            keys.append("season")
        if carry:
            keys.append("carry")
        added = []
        for key in keys:
            w, why = lib[key]
            if not w or w in added:
                continue
            if append_ok(parts, w):
                parts.append(w)
                added.append(w)
                src.append(why)
        # 兜底：至少 2 个特色维度，避免结构被随机补齐词淹没
        for key in ("season", "mat", "feat", "price", "scene", "carry"):
            if len(added) >= 2:
                break
            w, why = lib[key]
            if not w or w in added:
                continue
            if append_ok(parts, w):
                parts.append(w)
                added.append(w)
                src.append(why)

        # 品类同义词补充：热榜常同时出现 shoes 与 sneakers，提高 sneakers 词族覆盖
        if i % 5 < 2 and append_ok(parts, "Sneakers"):
            parts.append("Sneakers")
            src.append("补品类同义词=Sneakers（提高 sneakers 词族覆盖）")

        def join(ps):
            return re.sub(r"\s+", " ", " ".join(ps)).strip()

        t = join(parts)
        if len(t) < T_MIN:
            for f in ["Sneakers", "Outdoor", "Travel", "Comfortable", "School", "Home", "Office", "Daily Wear"]:
                if len(t) >= T_MIN:
                    break
                if append_ok(parts, f):
                    parts.insert(-1, f)
                    t = join(parts)
                    src.append(f"补词={f}（长度不足）")
        while len(t) > MAXLEN and len(parts) > 5:
            for drop in [d for d in (lib["price"][0], lib["scene"][0], "All Seasons") if d]:
                if drop in parts:
                    parts.remove(drop)
                    src.append(f"超长移除「{drop}」")
                    break
            else:
                parts.pop(-2)
            t = join(parts)

        exp, clk = num(d.get("搜索曝光次数")), num(d.get("搜索点击次数"))
        ctr = clean(d.get("搜索点击率")) or (f"{clk/exp*100:.2f}%" if exp else "-")
        orders, inq = num(d.get("提交订单个数")), num(d.get("询盘人数"))
        p = "P0" if (exp >= 100 or orders > 0 or inq > 0) else ("P1" if exp >= 1 else "P2")
        gaps = [k for k in ("Closure Type", "Upper Material", "Fit Type") if not clean(a.get(k))]

        result.append({
            "优先级": p, "产品ID": pid, "型号": clean(x.get("型号")), "分组": gname,
            "搜索曝光": int(exp), "搜索点击": int(clk), "点击率": ctr, "询盘人数": int(inq),
            "订单": int(orders), "GMV": clean(d.get("RTS线上实收GMV")) or "0",
            "是否P4P": clean(d.get("是否P4P")), "是否橱窗": clean(d.get("是否橱窗")),
            "旧标题": old, "新标题": t, "旧长度": len(old), "新长度": len(t),
            "品牌词": "Y" if BRANDS.search(t) else "",
            "属性缺口": "/".join(gaps) or "无",
            "季节待同步": "Y" if "all season" not in clean(a.get("Season")).lower() else "",
            "事实依据": "；".join(src),
        })

order = {"P0": 0, "P1": 1, "P2": 2}
result.sort(key=lambda r: (order[r["优先级"]], -r["搜索曝光"]))

seen = set()
for r in result:
    if r["新标题"] in seen:
        for sc in SCENE + ["Comfort", "Soft", "Breathable Design", "Fashion Style"]:
            cand = re.sub(r"\s+", " ", r["新标题"] + " " + sc).strip()
            if cand not in seen and len(cand) <= MAXLEN and append_ok(r["新标题"].split(), sc):
                r["新标题"], r["新长度"] = cand, len(cand)
                break
    seen.add(r["新标题"])

with open(OUT / "BQ标题总方案_第三轮.csv", "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=list(result[0].keys()))
    w.writeheader()
    w.writerows(result)

with open(OUT / "BQ属性待补清单.csv", "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=["优先级", "型号", "分组", "搜索曝光", "属性缺口", "季节待同步"])
    w.writeheader()
    for r in result:
        if r["属性缺口"] != "无" or r["季节待同步"] == "Y":
            w.writerow({k: r[k] for k in w.fieldnames})

print("=" * 80)
print("自动复检")
print("=" * 80)
dup = len(result) - len({r["新标题"] for r in result})
bad_b = [r["型号"] for r in result if r["品牌词"]]
bad_m = [r["型号"] for r in result if MODEL_RE.search(r["新标题"])]
bad_l = [r["型号"] for r in result if r["新长度"] > MAXLEN]
short = [r["型号"] for r in result if r["新长度"] < T_MIN]
dbl = [r["型号"] for r in result if re.search(r"\b(\w+)\s+\1\b", r["新标题"], re.I)]
print(f"① 品牌词     : {len(bad_b)}  {'✅' if not bad_b else bad_b[:4]}")
print(f"② 含型号     : {len(bad_m)}  {'✅' if not bad_m else bad_m[:4]}")
print(f"③ 超 {MAXLEN}   : {len(bad_l)}  {'✅' if not bad_l else bad_l[:4]}")
print(f"④ 短于 {T_MIN}   : {len(short)}  {'✅' if not short else short[:4]}")
print(f"⑤ 标题重复   : {dup}  {'✅' if dup == 0 else '❌'}")
print(f"⑥ 相邻重复词 : {len(dbl)}  {'✅' if not dbl else dbl[:4]}")
print(f"⑦ 长度       : {min(r['新长度'] for r in result)}–{max(r['新长度'] for r in result)}，中位 {median(r['新长度'] for r in result):.0f}（旧中位 {median(r['旧长度'] for r in result):.0f}，热榜 75）")
print(f"⑧ 优先级     : {dict(Counter(r['优先级'] for r in result))}")
print(f"⑨ 季节待同步 : {sum(1 for r in result if r['季节待同步']=='Y')} 款")
print(f"⑩ 有属性缺口 : {sum(1 for r in result if r['属性缺口']!='无')} 款")
print("\n=== 分组复核 ===")
for k, v in Counter(r["分组"] for r in result).most_common():
    print(f"  {v:>4}  {k}")
print("\n=== 结构要素覆盖（对比热榜）===")
BENCH = {"性别": 86, "价格信号": 38, "场景": 66, "材质": 51, "功能": 42, "季节": 33}
G = {
    "性别": r"\b(men|women|mens|womens|kid|children|boys|girls|lady|ladies)\b",
    "价格信号": r"\b(high quality|new design|fashion design|premium|best quality|new arrival|hot style|20\d{2} new)\b",
    "场景": r"\b(daily|outdoor|indoor|office|school|travel|home|walking use)\b",
    "材质": r"\b(mesh|knit\w*|textile|stretch|canvas|leather|fabric)\b",
    "功能": r"\b(breathable|anti slip|light weight|comfortable|soft)\b",
    "季节": r"\ball seasons\b",
}
for k, p in G.items():
    n = sum(1 for r in result if re.search(p, r["新标题"], re.I))
    print(f"  {k:<8} 热榜{BENCH[k]:>3}%  我方{n/len(result)*100:>3.0f}%")
print("\n=== P0 样本 ===")
for r in [x for x in result if x["优先级"] == "P0"][:6]:
    print(f"\n【{r['型号']}】{r['分组']}  曝光{r['搜索曝光']} CTR{r['点击率']} 询盘{r['询盘人数']} 单{r['订单']}")
    print(f"  旧({r['旧长度']}): {r['旧标题']}")
    print(f"  新({r['新长度']}): {r['新标题']}")
