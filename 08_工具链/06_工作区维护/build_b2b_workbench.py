"""Render the B2B workbench from task tables in the original business documents.

Run from any directory. Task facts stay in each source's `## 工作台任务` table.
Use --source <project-relative.md> to include another business source; --check
verifies the saved view without writing it. This script does not run agents.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import html
import os
from pathlib import Path
import re
from urllib.parse import quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "00_总控台/国际B2B工作台.html"
STATUS = ROOT / "00_总控台/当前状态.md"
ROADMAP = ROOT / "00_总控台/全渠道增长总控.md"
# Navigation only: business task content is never maintained in this script.
SOURCES = (
    STATUS,
    ROOT / "04_客户开发/获客研究与送达率治理.md",
    ROOT / "02_Alibaba运营/02_单品优化记录/BQ系列持续优化_2026-09-14/主推采购承接.md",
)
HEADERS = ["任务", "状态", "主办", "当前结果", "下一步", "依赖/需你决定", "成果与证据"]
TZ = timezone(timedelta(hours=8))


def section(text: str, title: str) -> str:
    match = re.search(r"^## " + re.escape(title) + r"\s*$", text, re.M)
    if not match:
        return ""
    rest = text[match.end():]
    end = re.search(r"^## ", rest, re.M)
    return rest[:end.start()] if end else rest


def table(text: str) -> tuple[list[str], list[list[str]]]:
    lines = [line.strip() for line in text.splitlines()]
    start = next((i for i, line in enumerate(lines) if line.startswith("|")), None)
    if start is None:
        return [], []
    rows = []
    for line in lines[start:]:
        if not line.startswith("|"):
            break
        cells = [cell.strip().replace(r"\|", "|") for cell in re.split(r"(?<!\\)\|", line.strip("|"))]
        if all(re.fullmatch(r":?-+:?", cell) for cell in cells):
            continue
        rows.append(cells)
    return (rows[0], rows[1:]) if rows else ([], [])


def href(target: str, source: Path) -> str:
    target = unquote(target.strip().strip("<>"))
    parsed = urlsplit(target)
    if parsed.scheme in {"http", "https", "mailto"}:
        return target
    if parsed.scheme:
        raise ValueError(f"Unsupported link scheme in {source.name}: {target}")
    path = Path(os.path.normpath(source.parent / parsed.path)) if parsed.path else source
    relative = os.path.relpath(path, OUTPUT.parent).replace(os.sep, "/")
    return quote(relative, safe="/-._~") + ("#" + quote(parsed.fragment) if parsed.fragment else "")


def inline(value: str, source: Path) -> str:
    links: list[str] = []

    def link(match: re.Match) -> str:
        label, target = match.groups()
        url = html.escape(href(target, source), quote=True)
        suffix = '<span class="local">本地</span>' if "/.local/" in target else ""
        links.append(f'<a href="{url}">{html.escape(label)}{suffix}</a>')
        return f"@@LINK{len(links)-1}@@"

    value = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, value)
    value = html.escape(value)
    value = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", value)
    value = re.sub(r"`([^`]+)`", r"<code>\1</code>", value)
    value = value.replace("&lt;br&gt;", "<br>").replace("&lt;br/&gt;", "<br>")
    for i, item in enumerate(links):
        value = value.replace(f"@@LINK{i}@@", item)
    return value


def category(state: str) -> str:
    if state in {"已交付", "已完成"}:
        return "done"
    if state in {"进行中", "执行中"}:
        return "active"
    if "授权" in state or "决定" in state or "确认" in state:
        return "decision"
    return "next"


def build(sources: list[Path], stamp: str) -> tuple[str, int]:
    missing = [p for p in sources if not p.exists()]
    texts = {p: p.read_text(encoding="utf-8-sig") for p in dict.fromkeys([STATUS, ROADMAP, *sources]) if p.exists()}
    digest = hashlib.sha256("\n".join(str(p.relative_to(ROOT)) + "\n" + text for p, text in texts.items()).encode()).hexdigest()
    tasks = []
    for source in sources:
        if source in missing:
            continue
        headers, rows = table(section(texts[source], "工作台任务"))
        if not headers:
            continue
        if headers != HEADERS:
            raise ValueError(f"{source.relative_to(ROOT)} task headers must be {HEADERS}")
        for row in rows:
            if len(row) != len(HEADERS):
                raise ValueError(f"Incomplete task row in {source.name}: {row}")
            tasks.append((source, dict(zip(headers, row))))

    status = texts[STATUS]
    goal = re.search(r"国际B2B具体要成为：\*\*(.+?)\*\*", status)
    phase = re.search(r"\*\*当前位置：(.+?)\*\*", status)
    if not goal or not phase:
        raise ValueError("Current status must include the B2B long-term goal and current phase")
    goal_html = inline(goal.group(1), STATUS)
    phase_html = inline(phase.group(1), STATUS)
    counts = Counter(category(task["状态"]) for _, task in tasks)
    cards = []
    for i, (source, task) in enumerate(tasks, 1):
        cat = category(task["状态"])
        dependency = task["依赖/需你决定"]
        need = dependency not in {"", "无", "—", "-", "暂无", "暂无需负责人决定"}
        dependency_html = f'<div class="dependency"><span>依赖 / 需你决定</span><p>{inline(dependency, source)}</p></div>' if need else ""
        cards.append(f'''<article class="task" data-category="{cat}">
          <div class="task-top"><span class="eyebrow">{html.escape(source.stem)} · {i:02d}</span><span class="badge {cat}">{html.escape(task["状态"])}</span></div>
          <h3>{inline(task["任务"], source)}</h3>
          <p class="owner">负责人 <strong>{inline(task["主办"], source)}</strong></p>
          <div class="task-body"><div><span class="label">现在做到哪</span><p>{inline(task["当前结果"], source)}</p></div>
          <div class="next-step"><span class="label">下一步</span><p>{inline(task["下一步"], source)}</p></div>{dependency_html}</div>
          <div class="evidence"><span class="label">成果与证据</span><div>{inline(task["成果与证据"], source)}</div></div>
          <a class="source-link" href="{html.escape(href(source.name + '#工作台任务', source), quote=True)}">查看原任务记录 ↗</a>
        </article>''')
    _, stages = table(section(texts[ROADMAP], "执行顺序与阶段完成标准"))
    phases = []
    for i, row in enumerate(stages[:4]):
        letter = row[0].split()[0]
        current = letter + "阶段" in phase.group(1)
        phases.append(f'<li class="{"current" if current else ""}"><span class="stage-letter">{html.escape(letter)}</span><div><strong>{html.escape(row[0][len(letter):].strip())}</strong><small>{"当前阶段" if current else "按成果接续"}</small></div></li>')
    source_links = "".join(f'<li><a href="{html.escape(href(p.name, p), quote=True)}">{html.escape(p.stem)}</a><span>源文件更新 {datetime.fromtimestamp(p.stat().st_mtime, TZ):%m-%d %H:%M}</span></li>' for p in texts)
    source_links += "".join(f'<li>{html.escape(p.stem)}<span>未接入：源文件尚未创建</span></li>' for p in missing)
    pending = '<p class="pending">尚未接入：' + '、'.join(html.escape(p.stem) for p in missing) + '。相关任务未计入汇总。</p>' if missing else ''
    document = TEMPLATE.replace("{{STAMP}}", html.escape(stamp)).replace("{{DIGEST}}", digest)
    values = {
        "GOAL": goal_html, "PHASE": phase_html, "STAGES": "".join(phases),
        "CARDS": "".join(cards), "TOTAL": str(len(tasks)), "ACTIVE": str(counts["active"]),
        "DECISION": str(counts["decision"]), "DONE": str(counts["done"]), "SOURCES": source_links, "PENDING": pending,
    }
    for key, value in values.items():
        document = document.replace("{{" + key + "}}", value)
    return document, len(tasks)


TEMPLATE = '''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="source-digest" content="{{DIGEST}}"><meta name="generated-at" content="{{STAMP}}">
<title>贝强 · 国际B2B经营工作台</title>
<style>
:root{--bg:#f3f5f0;--ink:#1b302b;--muted:#64756d;--line:#dbe3d9;--green:#205e49;--soft:#e6eee6;--gold:#866230}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif}a{color:var(--green);text-underline-offset:3px}button,input{font:inherit}button{cursor:pointer}button:focus-visible,a:focus-visible,input:focus-visible{outline:3px solid #7ba98c;outline-offset:3px}.wrap{max-width:1280px;margin:auto;padding:0 32px}.topbar{border-bottom:1px solid var(--line);background:#fafbf8}.topbar .wrap{display:flex;align-items:center;justify-content:space-between;gap:20px;padding-top:19px;padding-bottom:19px}.brand{font-size:18px;font-weight:760;letter-spacing:.06em}.brand small{font-size:12px;font-weight:500;color:var(--muted);margin-left:15px;letter-spacing:.1em}.topbar a{font-size:13px;text-decoration:none}.hero{padding-top:44px;padding-bottom:30px;display:grid;grid-template-columns:1.5fr 1fr;gap:50px;align-items:start}.eyebrow{font-size:11px;letter-spacing:.08em;color:var(--muted);font-weight:650}.hero h1{font-size:36px;letter-spacing:-.03em;line-height:1.25;margin:8px 0 16px}.goal{font-size:17px;line-height:1.8;max-width:720px;margin:0}.phase{margin:22px 0 0;padding:12px 16px;border-left:3px solid #41765d;background:var(--soft);font-size:14px}.snapshot{padding:23px 25px;background:#fff;border:1px solid var(--line);border-radius:14px}.snapshot h2{font-size:16px;margin:0 0 8px}.snapshot p{font-size:13px;color:var(--muted);margin:8px 0}.time{font-variant-numeric:tabular-nums;color:var(--green);font-size:13px}.stages{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:0;margin:0 0 32px;list-style:none}.stages li{display:flex;align-items:center;gap:12px;border-top:2px solid var(--line);padding:14px 10px;color:var(--muted)}.stages li.current{border-color:var(--green);color:var(--green)}.stage-letter{font:600 23px/1.2 Georgia,serif}.stages strong{font-size:13px;display:block}.stages small{font-size:11px;display:block}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line);border-radius:13px;overflow:hidden;margin-bottom:34px}.stat{background:#fafbf8;padding:18px 23px;display:flex;gap:13px;align-items:center}.stat b{font-size:30px;line-height:1.2;font-weight:600}.stat span{font-size:13px;color:var(--muted)}.section-head{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:17px}.section-head h2{font-size:22px;margin:0}.section-head p{margin:4px 0 0;color:var(--muted);font-size:13px}.filters{display:flex;gap:6px;flex-wrap:wrap}.filters button{border:1px solid var(--line);border-radius:25px;padding:7px 13px;background:transparent;color:var(--muted);font-size:12px}.filters button[aria-pressed=true]{background:var(--green);color:#fff;border-color:var(--green)}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.task{background:#fff;border:1px solid var(--line);border-radius:14px;padding:24px;display:flex;flex-direction:column}.task[hidden]{display:none}.task-top{display:flex;align-items:center;justify-content:space-between;gap:10px}.badge{white-space:nowrap;font-size:11px;line-height:1.5;padding:4px 9px;border-radius:20px;background:#eff1ed;color:#637269}.badge.active{background:#e4f0e8;color:#205e49}.badge.decision{background:#fff0d9;color:#8b6023}.badge.done{background:#e9eef5;color:#48657c}.task h3{font-size:19px;line-height:1.5;margin:13px 0 7px}.owner{font-size:12px;color:var(--muted);margin:0 0 20px}.owner strong{margin-left:5px;font-weight:600;color:var(--ink)}.task-body{flex:1}.label,.dependency>span{display:block;font-size:11px;font-weight:650;color:var(--muted);margin-bottom:5px}.task-body p{font-size:14px;line-height:1.75;margin:0}.next-step{margin-top:16px;padding-top:14px;border-top:1px solid #edf0ea}.dependency{margin-top:17px;padding:12px 14px;border-radius:8px;background:#fbf5e9}.dependency>span{color:var(--gold)}.dependency p{font-size:13px}.evidence{margin-top:22px;padding-top:16px;border-top:1px solid var(--line);font-size:13px}.evidence a{display:inline-block;margin:3px 8px 3px 0}.local{font-size:9px;color:var(--muted);background:#eef1ec;padding:2px 4px;margin-left:5px;border-radius:3px}.source-link{align-self:flex-start;margin-top:12px;font-size:11px;color:var(--muted)}.empty{padding:40px;border:1px dashed var(--line);text-align:center;color:var(--muted);border-radius:12px}.commands{margin-top:38px;padding:28px;background:#e6ede5;border:1px solid #d5dfd2;border-radius:14px;display:grid;grid-template-columns:1fr 1.6fr;gap:34px}.commands h2{margin:0 0 9px;font-size:20px}.commands p{font-size:13px;color:var(--muted);margin:0}.command-list{display:grid;gap:9px}.command{background:#fff;border:1px solid #cfdbcd;border-radius:8px;padding:11px 13px;display:flex;align-items:center;justify-content:space-between;gap:12px}.command span{font-size:13px}.command button{border:0;background:transparent;color:var(--green);font-size:12px;white-space:nowrap}.command:first-child{border-color:#8eaa91}.command-note{font-size:12px!important;margin-top:15px!important}#copy-status{min-height:20px;font-size:12px;color:var(--green);margin-top:7px}.sources{margin:30px 0 16px;padding-top:20px;border-top:1px solid var(--line)}.sources summary{cursor:pointer;color:var(--muted);font-size:13px}.sources ul{list-style:none;padding:0;display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.sources li{font-size:12px;display:flex;flex-wrap:wrap;gap:10px;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--line)}.sources li span{color:var(--muted)}footer{padding:6px 0 30px;font-size:11px;color:var(--muted)}code{font-size:12px;background:#f0f3ed;padding:1px 4px;border-radius:3px}@media(max-width:820px){.hero{grid-template-columns:1fr;gap:20px;padding-top:28px}.hero h1{font-size:30px}.section-head{display:block}.filters{margin-top:14px}.commands{grid-template-columns:1fr;gap:18px}.task{padding:20px}.stats .stat{padding:14px;display:block}.stat span{display:block}.stages{gap:5px}.stages li{padding:10px 3px;gap:7px}.stages strong{font-size:11px}}@media(max-width:580px){.wrap{padding-left:18px;padding-right:18px}.topbar .wrap{padding-top:14px;padding-bottom:14px}.brand small{display:none}.grid{grid-template-columns:1fr}.goal{font-size:15px}.snapshot{padding:18px}.stats{margin-bottom:26px}.stat b{font-size:25px}.stages{grid-template-columns:repeat(2,1fr);margin-bottom:20px}.sources ul{grid-template-columns:1fr}.commands{padding:20px}.command{align-items:start}.hero h1{font-size:28px}.task-top .eyebrow{font-size:10px}}@media print{.filters,.command button{display:none}.task{break-inside:avoid}.grid{display:block}.task{margin-bottom:15px}.hero{padding-top:15px}.commands{break-inside:avoid}}
.quicknav{display:flex;flex-wrap:wrap;gap:8px;margin:-12px 0 28px}.quicknav a{border:1px solid var(--line);border-radius:8px;padding:7px 11px;font-size:12px;text-decoration:none;background:#fafbf8}.pending{padding:12px 16px;background:#fbf5e9;font-size:13px;border-radius:8px;margin-bottom:20px}</style></head><body>
<header class="topbar"><div class="wrap"><div class="brand">贝强 <small>国际业务工作台</small></div><a href="当前状态.md">全局目标与优先级 ↗</a></div></header>
<main class="wrap">
<section class="hero"><div><span class="eyebrow">从选款到订单，再到持续复购</span><h1>一起把生意往前推进。</h1><p class="goal">{{GOAL}}</p><p class="phase">{{PHASE}}</p></div><aside class="snapshot"><h2>这份工作台代表什么</h2><div class="time">生成于 {{STAMP}} · 北京时间</div><p>任务、成果和下一步来自各自的项目文档。这里是一份生成时快照，不代表所有 Agent 正在后台运行。</p><p>继续指令启动后，由统筹核实状态、并行推进独立任务，完成后刷新本页。</p></aside></section>
<ol class="stages" aria-label="经营阶段">{{STAGES}}</ol>
<nav class="quicknav" aria-label="常用业务入口"><a href="产品中心/产品矩阵与供货能力.md">产品与合作条件 ↗</a><a href="../03_独立站/02_开发记录/独立站产品与架构设计.md">网站项目 ↗</a><a href="../04_客户开发/07_RFQ专岗/README.md">RFQ 独立专岗 ↗</a><a href="https://www.beiqiang.online/" target="_blank" rel="noopener">访问实际网站 ↗</a></nav>{{PENDING}}
<section class="stats" aria-label="任务状态汇总"><div class="stat"><b>{{TOTAL}}</b><span>已登记任务</span></div><div class="stat"><b>{{ACTIVE}}</b><span>进行中记录</span></div><div class="stat"><b>{{DECISION}}</b><span>待授权 / 决定</span></div><div class="stat"><b>{{DONE}}</b><span>已交付</span></div></section>
<section aria-labelledby="tasks-title"><div class="section-head"><div><h2 id="tasks-title">每条工作线，现在做到哪</h2><p>看实际交付和下一动作，不用完成百分比代替经营结果。</p></div><nav class="filters" aria-label="筛选任务"><button data-filter="all" aria-pressed="true">全部</button><button data-filter="active" aria-pressed="false">进行中</button><button data-filter="decision" aria-pressed="false">需我决定</button><button data-filter="next" aria-pressed="false">待接续 / 验证</button><button data-filter="done" aria-pressed="false">已交付</button></nav></div><div class="grid">{{CARDS}}</div><p class="empty" id="empty" hidden>这个分类暂时没有登记任务。</p><p id="filter-status" aria-live="polite" class="eyebrow"></p></section>
<section class="commands"><div><h2>怎样让我继续推进</h2><p>复制一条指令，回到当前 Codex 对话发送。统筹会读取原项目、核对任务归属，再推进能独立执行的工作。</p><p class="command-note">页面按钮只复制文字，不会发客户邮件、启动 Agent 或自动修改项目。</p></div><div><div class="command-list"><div class="command"><span>继续推进工作台，完成当前可执行任务并更新进度。</span><button type="button" data-copy>复制指令</button></div><div class="command"><span>只看需要我决定的事项，把具体选项和材料列出来。</span><button type="button" data-copy>复制指令</button></div><div class="command"><span>优先推进指定任务，并回写结果与下一步。</span><button type="button" data-copy>复制指令</button></div></div><div id="copy-status" aria-live="polite"></div></div></section>
<details class="sources"><summary>资料从哪里来 · 查看唯一业务源</summary><ul>{{SOURCES}}</ul></details>
<footer>只在业务源更新事实与状态，再生成此视图。标记“本地”的材料需在这台工作电脑打开；客户明细不嵌入此页面。</footer>
</main><script>
const cards=[...document.querySelectorAll('.task')];
function filterTasks(key){let count=0;cards.forEach(card=>{const show=key==='all'||card.dataset.category===key;card.hidden=!show;if(show)count++;});document.querySelectorAll('[data-filter]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.filter===key)));document.getElementById('empty').hidden=count>0;document.getElementById('filter-status').textContent=`显示 ${count} / ${cards.length} 项任务`;}
document.querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>filterTasks(button.dataset.filter)));
document.querySelectorAll('[data-copy]').forEach(button=>button.addEventListener('click',async()=>{const label=button.previousElementSibling;const text=label.textContent;try{await navigator.clipboard.writeText(text);document.getElementById('copy-status').textContent='已复制。回到当前对话粘贴并发送即可。';}catch{const range=document.createRange();range.selectNodeContents(label);const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);document.getElementById('copy-status').textContent='已选中文字，请复制后发到当前对话。';}}));
filterTasks('all');
</script></body></html>
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", default=[], help="Additional project-relative Markdown task source")
    parser.add_argument("--check", action="store_true", help="Verify saved HTML without writing")
    args = parser.parse_args()
    sources = list(dict.fromkeys([*SOURCES, *(ROOT / p for p in args.source)]))
    stamp = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    if args.check:
        existing = OUTPUT.read_text(encoding="utf-8")
        match = re.search(r'<meta name="generated-at" content="([^"]+)">', existing)
        if not match:
            raise SystemExit("Workbench missing generated-at metadata")
        stamp = match.group(1)
    document, count = build(sources, stamp)
    if args.check:
        if document != existing:
            raise SystemExit("Workbench differs from source documents; regenerate it")
        print(f"Workbench current: {count} tasks, {len(sources)} task sources")
    else:
        OUTPUT.write_text(document, encoding="utf-8")
        print(f"Generated {OUTPUT.relative_to(ROOT)}: {count} tasks, {len(sources)} task sources")


if __name__ == "__main__":
    main()
