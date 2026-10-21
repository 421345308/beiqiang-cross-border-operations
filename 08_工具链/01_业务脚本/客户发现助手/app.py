"""Local review workbench and CLI for public company research."""
from __future__ import annotations

import argparse
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from core import Crawler, DATA, csv_export, new_candidate, now, search_plan

LOCK = threading.RLock()
JOB = {"running": False, "message": ""}


class Store:
    def __init__(self, directory=DATA):
        self.directory = Path(directory)
        self.path = self.directory / "candidates.json"

    def read(self):
        with LOCK:
            return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else []

    def write(self, rows):
        with LOCK:
            self.directory.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(self.path)

    def add(self, seeds):
        if not isinstance(seeds, list) or not 1 <= len(seeds) <= 100:
            raise ValueError("每次导入1至100家企业")
        # Validate entire batch before writing anything.
        candidates = [new_candidate(seed) for seed in seeds]
        with LOCK:
            rows = self.read()
            ids = {r["id"] for r in rows}
            count = 0
            for c in candidates:
                if c["id"] not in ids:
                    rows.append(c)
                    ids.add(c["id"])
                    count += 1
                else:
                    existing = next(r for r in rows if r["id"] == c["id"])
                    for u in c["pages_to_read"]:
                        if u not in existing["pages_to_read"]:
                            existing["pages_to_read"].append(u)
            self.write(rows)
            return count

    def review(self, candidate_id, state, note):
        allowed = {"未核验", "值得继续", "暂缓", "不匹配", "停止联系"}
        if state not in allowed:
            raise ValueError("无效核验状态")
        with LOCK:
            rows = self.read()
            row = next((r for r in rows if r["id"] == candidate_id), None)
            if row is None:
                raise ValueError("未找到候选企业")
            row["review"] = {"state": state, "note": str(note)[:4000], "updated_at": now()}
            self.write(rows)

    def scan(self, ids, max_pages=4, callback=None):
        crawler = Crawler()
        for candidate_id in ids:
            row = next((r for r in self.read() if r["id"] == candidate_id), None)
            if not row or row["review"]["state"] == "停止联系":
                continue
            if callback:
                callback("正在核查 " + row["company"])
            try:
                result = crawler.scan({"website": row["website"], "pages": row["pages_to_read"]}, max_pages=max_pages, evidence_dir=self.directory / "evidence" / candidate_id, progress=(lambda message: callback(row["company"] + " · " + message)) if callback else None)
            except Exception as exc:
                result = {"research_status": "读取失败", "pages": [{"error": str(exc)[:240]}], "checked_at": now(), "analysis": {}, "contacts": []}
            with LOCK:
                rows = self.read()
                current = next(r for r in rows if r["id"] == candidate_id)
                # A rescan cannot overwrite human reviews or silently keep stale contacts.
                current.update(result)
                self.write(rows)


def handler_class(store, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, value, mime="application/json; charset=utf-8"):
            raw = value.encode("utf-8") if isinstance(value, str) else json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'nonce-" + token + "'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def valid_request(self, api=False):
            expected = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") != expected:
                self.reply(403, {"error": "仅允许本机地址访问"})
                return False
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + expected:
                self.reply(403, {"error": "请求来源不匹配"})
                return False
            if api and not secrets.compare_digest(self.headers.get("X-Workbench-Token", ""), token):
                self.reply(403, {"error": "请从本机工作台打开"})
                return False
            return True

        def do_GET(self):
            path = urlsplit(self.path).path
            if not self.valid_request(api=path.startswith("/api/")):
                return
            if path == "/":
                content = Path(__file__).with_name("index.html").read_text(encoding="utf-8").replace("__TOKEN__", token)
                self.reply(200, content, "text/html; charset=utf-8")
            elif path == "/api/state":
                self.reply(200, {"candidates": store.read(), "job": JOB, "storage": str(store.directory), "crm_status": "候选暂存；未同步正式CRM和停止联系清单"})
            elif path == "/api/export":
                self.reply(200, csv_export(store.read()), "text/csv; charset=utf-8")
            else:
                self.reply(404, {"error": "未找到页面"})

        def do_POST(self):
            if not self.valid_request(api=True):
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 1_000_000 or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise ValueError("请求格式或大小不符合要求")
                body = json.loads(self.rfile.read(size))
                path = urlsplit(self.path).path
                if path == "/api/import":
                    self.reply(200, {"added": store.add(body["candidates"])})
                elif path == "/api/plan":
                    self.reply(200, search_plan(body.get("market", "United States"), body.get("direction", "comfort casual footwear")))
                elif path == "/api/review":
                    store.review(body["id"], body["state"], body.get("note", ""))
                    self.reply(200, {"ok": True})
                elif path == "/api/scan":
                    ids = body.get("ids", [])
                    max_pages = int(body.get("max_pages", 4))
                    if not isinstance(ids, list) or not 1 <= len(ids) <= 20 or not 1 <= max_pages <= 8:
                        raise ValueError("请选择1至20家企业；每家读取1至8页")
                    with LOCK:
                        if JOB["running"]:
                            self.reply(409, {"error": "已有采集任务正在进行"})
                            return
                        JOB.update(running=True, message="准备核查")
                    def run():
                        try:
                            store.scan(ids, max_pages, lambda message: JOB.update(message=message))
                            JOB.update(message="本轮核查完成；结果仍需人工审核")
                        except Exception:
                            JOB.update(message="任务中断，请检查候选数据")
                        finally:
                            JOB.update(running=False)
                    threading.Thread(target=run, daemon=True).start()
                    self.reply(202, {"ok": True})
                else:
                    self.reply(404, {"error": "未找到操作"})
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                self.reply(400, {"error": str(exc)[:240]})
    return Handler


def main():
    parser = argparse.ArgumentParser(description="贝强客户发现助手：发现、公开入口采集、人工核验")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=8766)
    imp = sub.add_parser("import")
    imp.add_argument("path", type=Path)
    scan = sub.add_parser("scan")
    scan.add_argument("--id", action="append")
    scan.add_argument("--max-pages", type=int, default=4, choices=range(1, 9))
    plan = sub.add_parser("plan")
    plan.add_argument("--market", default="United States")
    plan.add_argument("--direction", default="comfort casual footwear")
    export = sub.add_parser("export")
    export.add_argument("path", type=Path)
    args = parser.parse_args()
    store = Store()
    if args.command == "serve":
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_class(store, secrets.token_urlsafe(32)))
        print(f"客户发现助手：http://127.0.0.1:{args.port}", flush=True)
        server.serve_forever()
    elif args.command == "import":
        data = json.loads(args.path.read_text(encoding="utf-8-sig"))
        print(json.dumps({"added": store.add(data["candidates"] if isinstance(data, dict) else data)}, ensure_ascii=False))
    elif args.command == "scan":
        ids = args.id or [r["id"] for r in store.read() if r["research_status"] == "待采集"]
        store.scan(ids, args.max_pages, lambda message: print(message, flush=True))
        print("核查完成", flush=True)
    elif args.command == "plan":
        print(json.dumps(search_plan(args.market, args.direction), ensure_ascii=False, indent=2))
    elif args.command == "export":
        target = args.path.resolve()
        # Contact exports may only be written under the ignored local candidate area.
        if not target.is_relative_to(DATA.resolve()):
            raise ValueError("联系人导出须保存在本工具.local目录中")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(csv_export(store.read()), encoding="utf-8")
        print(str(target))


if __name__ == "__main__":
    main()
