"""电商商品与订单管理系统 V1.0 — 本地运行，无外部平台写入。"""
from __future__ import annotations

import argparse
import csv
import io
import html
import hashlib
import time
import threading
import json
import secrets
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie, CookieError
from pathlib import Path
from urllib.parse import urlsplit

BASE = Path(__file__).resolve().parent
CATALOG = BASE.parents[1] / "02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json"
NAME = "电商商品与订单管理系统"
VERSION = "V1.0"
DEMO_PASSWORD = 'Demo-Only-8766'


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def required(value, label, limit=200):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ValueError(f"{label}不能为空，且不能超过{limit}字")
    return value.strip()


def integer(value, label, minimum=None):
    if isinstance(value, bool):
        raise ValueError(f"{label}必须为整数")
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number != number.to_integral_value() or abs(number) > 1_000_000_000:
            raise ValueError()
        result = int(number)
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"{label}必须为整数") from None
    if minimum is not None and result < minimum:
        raise ValueError(f"{label}超出允许范围")
    return result


def cents(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount > 1_000_000:
            raise ValueError()
        if amount * 100 != (amount * 100).to_integral_value():
            raise ValueError()
        return int(amount * 100)
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("价格须为非负金额，最多两位小数") from None


def safe_cell(value):
    text = str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")) else text


class Store:
    def __init__(self, path, demo=False, catalog=CATALOG):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.demo = demo
        self.catalog = Path(catalog)
        with closing(self.connect()) as con, con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS skus (
                    code TEXT PRIMARY KEY, model TEXT NOT NULL, title TEXT NOT NULL,
                    color TEXT NOT NULL, size TEXT NOT NULL, price_cents INTEGER NOT NULL CHECK(price_cents>=0),
                    stock INTEGER NOT NULL DEFAULT 0 CHECK(stock>=0), updated TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS movements (
                    id INTEGER PRIMARY KEY, sku TEXT NOT NULL REFERENCES skus(code),
                    delta INTEGER NOT NULL, balance INTEGER NOT NULL, note TEXT NOT NULL, created TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS orders (
                    number TEXT PRIMARY KEY, status TEXT NOT NULL CHECK(status IN ('待发货','已发货','已取消')),
                    note TEXT NOT NULL, tracking TEXT NOT NULL DEFAULT '', created TEXT NOT NULL, updated TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS order_lines (
                    number TEXT NOT NULL REFERENCES orders(number), sku TEXT NOT NULL REFERENCES skus(code),
                    quantity INTEGER NOT NULL CHECK(quantity>0), unit_cents INTEGER NOT NULL CHECK(unit_cents>=0),
                    PRIMARY KEY(number,sku));
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY, action TEXT NOT NULL, object_id TEXT NOT NULL,
                    detail TEXT NOT NULL, created TEXT NOT NULL);
            """)
            mode = con.execute("SELECT value FROM settings WHERE key='mode'").fetchone()
            wanted = "demo" if demo else "production"
            if mode and mode[0] != wanted:
                raise ValueError("演示库与正式库不可混用")
            con.execute("INSERT OR IGNORE INTO settings VALUES ('mode',?)", (wanted,))
        if demo and not self.has_password():
            self.set_password(DEMO_PASSWORD)

    def connect(self):
        con = sqlite3.connect(self.path, timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        return con

    @contextmanager
    def transaction(self):
        con = self.connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def models(self):
        if self.demo:
            return ["DEMO-001"]
        if not self.catalog.exists():
            return []
        catalog = json.loads(self.catalog.read_text(encoding="utf-8-sig"))
        return sorted({p["id"] for p in catalog.get("products", [])})

    def log(self, con, action, object_id, detail):
        con.execute("INSERT INTO audit(action,object_id,detail,created) VALUES (?,?,?,?)",
                    (action, object_id, json.dumps(detail, ensure_ascii=False), now()))

    def has_password(self):
        with closing(self.connect()) as con:
            return con.execute("SELECT 1 FROM settings WHERE key='password_hash'").fetchone() is not None

    def set_password(self, password):
        if not isinstance(password, str) or not 12 <= len(password) <= 200:
            raise ValueError('首次设置的密码须为12至200个字符')
        salt = secrets.token_hex(24)
        value = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode(), 600_000).hex()
        with self.transaction() as con:
            if con.execute("SELECT 1 FROM settings WHERE key='password_hash'").fetchone():
                raise ValueError('密码已设置，不能从首次设置入口覆盖')
            con.execute("INSERT INTO settings VALUES ('password_salt',?)", (salt,))
            con.execute("INSERT INTO settings VALUES ('password_hash',?)", (value,))

    def verify_password(self, password):
        if not isinstance(password, str) or not 1 <= len(password) <= 200:
            return False
        with closing(self.connect()) as con:
            settings = dict(con.execute("SELECT key,value FROM settings WHERE key IN ('password_hash','password_salt')"))
        if not settings.get('password_hash'):
            return False
        value = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), settings['password_salt'].encode(), 600_000).hex()
        return secrets.compare_digest(value, settings['password_hash'])

    def normalized_sku(self, item):
        model = required(item.get("model"), "本店型号", 80)
        if model not in self.models():
            raise ValueError("型号不在现有产品台账中；请先在产品事实源确认身份")
        return (required(item.get("code"), "SKU编码", 80), model,
                required(item.get("title"), "渠道商品名称", 120),
                required(item.get("color"), "颜色", 50), required(item.get("size"), "尺码", 30),
                cents(item.get("price")))

    def save_sku(self, item):
        values = self.normalized_sku(item)
        with self.transaction() as con:
            self.write_sku(con, values)
        return {"message": "SKU已保存；库存通过库存流水单独登记"}

    def write_sku(self, con, values):
        old = con.execute("SELECT * FROM skus WHERE code=?", (values[0],)).fetchone()
        if old and (old['model'], old['color'], old['size']) != (values[1], values[3], values[4]):
            raise ValueError("已有SKU的型号、颜色和尺码不可改绑，请使用新编码")
        con.execute("""INSERT INTO skus(code,model,title,color,size,price_cents,updated) VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(code) DO UPDATE SET title=excluded.title,
            price_cents=excluded.price_cents,updated=excluded.updated""", (*values, now()))
        self.log(con, "保存SKU", values[0], {"before": dict(old) if old else None, "fields": values})

    def import_csv(self, content):
        if not isinstance(content, str) or len(content) > 1_000_000:
            raise ValueError("CSV过大或格式错误")
        reader = csv.DictReader(io.StringIO(content.lstrip('\ufeff')))
        columns = ["code", "model", "title", "color", "size", "price"]
        if reader.fieldnames != columns:
            raise ValueError("CSV列须依次为 code,model,title,color,size,price")
        rows = list(reader)
        if not rows or len(rows) > 1000:
            raise ValueError("每批导入1至1000行")
        normalized = [self.normalized_sku(row) for row in rows]
        if len({row[0] for row in normalized}) != len(rows):
            raise ValueError("同一批CSV存在重复SKU编码")
        with self.transaction() as con:
            for values in normalized:
                self.write_sku(con, values)
        return {"message": f"已导入{len(rows)}行；库存未被覆盖"}

    def movement(self, con, code, delta, note):
        row = con.execute("SELECT stock FROM skus WHERE code=?", (code,)).fetchone()
        if not row:
            raise ValueError("SKU不存在")
        balance = row[0] + delta
        if balance < 0:
            raise ValueError(f"{code}可用库存不足")
        if balance > 1_000_000_000:
            raise ValueError("库存超出允许范围")
        con.execute("UPDATE skus SET stock=?,updated=? WHERE code=?", (balance, now(), code))
        con.execute("INSERT INTO movements(sku,delta,balance,note,created) VALUES (?,?,?,?,?)",
                    (code, delta, balance, note, now()))
        return balance

    def adjust(self, item):
        code = required(item.get('code'), "SKU编码", 80)
        delta = integer(item.get('delta'), "库存变化量")
        if not delta:
            raise ValueError("库存变化量不能为0")
        note = required(item.get('note'), "实盘或凭证说明", 500)
        with self.transaction() as con:
            balance = self.movement(con, code, delta, note)
            self.log(con, "库存调整", code, {"delta": delta, "balance": balance, "note": note})
        return {"message": f"可用库存已更新为{balance}"}

    def create_order(self, item):
        number = required(item.get('number'), "订单编号", 80)
        note = required(item.get('note'), "订单来源说明", 500)
        lines = item.get('lines')
        if not isinstance(lines, list) or not 1 <= len(lines) <= 100:
            raise ValueError("订单须包含1至100行")
        normalized = [(required(x.get('code'), "SKU编码", 80), integer(x.get('quantity'), "数量", 1))
                      for x in lines if isinstance(x, dict)]
        if len(normalized) != len(lines) or len(set(x[0] for x in normalized)) != len(lines):
            raise ValueError("订单行格式错误或SKU重复")
        with self.transaction() as con:
            if con.execute("SELECT 1 FROM orders WHERE number=?", (number,)).fetchone():
                raise ValueError("订单编号已存在，未重复扣库存")
            con.execute("INSERT INTO orders(number,status,note,created,updated) VALUES (?,'待发货',?,?,?)",
                        (number, note, now(), now()))
            for code, quantity in normalized:
                row = con.execute("SELECT price_cents FROM skus WHERE code=?", (code,)).fetchone()
                if not row:
                    raise ValueError(f"{code}不存在")
                self.movement(con, code, -quantity, f"订单预留：{number}")
                con.execute("INSERT INTO order_lines VALUES (?,?,?,?)", (number, code, quantity, row[0]))
            self.log(con, "创建订单", number, {"lines": normalized, "note": note})
        return {"message": "订单已登记，商品数量从可用库存中预留"}

    def transition(self, item):
        number = required(item.get('number'), "订单编号", 80)
        status = item.get('status')
        if status not in ('已取消', '已发货'):
            raise ValueError("只支持取消或登记发货")
        tracking = required(item.get('tracking'), "物流或发货凭证", 150) if status == '已发货' else ''
        with self.transaction() as con:
            order = con.execute("SELECT * FROM orders WHERE number=?", (number,)).fetchone()
            if not order or order['status'] != '待发货':
                raise ValueError("仅待发货订单可变更，已处理订单不会重复调整库存")
            if status == '已取消':
                for line in con.execute("SELECT * FROM order_lines WHERE number=?", (number,)).fetchall():
                    self.movement(con, line['sku'], line['quantity'], f"取消返还：{number}")
            con.execute("UPDATE orders SET status=?,tracking=?,updated=? WHERE number=?",
                        (status, tracking, now(), number))
            self.log(con, "订单状态", number, {"from": order['status'], "to": status, "tracking": tracking})
        return {"message": f"订单已登记为{status}；未向任何平台发送通知"}

    def snapshot(self):
        with closing(self.connect()) as con:
            data = {key: [dict(row) for row in con.execute(sql)] for key, sql in {
                "skus": "SELECT * FROM skus ORDER BY model,code",
                "orders": "SELECT o.*,COALESCE(SUM(l.quantity*l.unit_cents),0) AS total_cents FROM orders o LEFT JOIN order_lines l USING(number) GROUP BY o.number ORDER BY o.created DESC",
                "lines": "SELECT * FROM order_lines ORDER BY number,sku",
                "movements": "SELECT * FROM movements ORDER BY id DESC LIMIT 200",
                "audit": "SELECT * FROM audit ORDER BY id DESC LIMIT 200",
            }.items()}
        return {**data, "models": self.models(), "demo": self.demo, "name": NAME, "version": VERSION,
                "platform_status": "抖店未连接", "catalog": str(self.catalog)}

    def export_csv(self):
        out = io.StringIO(newline='')
        writer = csv.writer(out)
        writer.writerow(["code", "model", "title", "color", "size", "price", "available_stock"])
        for row in self.snapshot()['skus']:
            writer.writerow([safe_cell(row[k]) for k in ('code', 'model', 'title', 'color', 'size')] +
                            [f"{row['price_cents']/100:.2f}", row['stock']])
        return ('\ufeff' + out.getvalue()).encode('utf-8')

    def backup(self, destination):
        """用SQLite备份接口形成一致性副本，不直接复制正在写入的库。"""
        destination = Path(destination).resolve()
        if destination == self.path.resolve() or destination.exists():
            raise ValueError('备份目标必须为新的文件，不能覆盖原库或已有备份')
        destination.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as source, closing(sqlite3.connect(destination)) as target:
            source.backup(target)
        return destination

    def seed(self):
        if not self.demo or self.snapshot()['skus']:
            return
        for color, size, code, price in [('米色','38','DEMO-B38','129.00'), ('米色','39','DEMO-B39','129.00'),
                                         ('黑色','40','DEMO-K40','139.00')]:
            self.save_sku(dict(code=code, model='DEMO-001', title='演示商品 用于功能测试', color=color, size=size, price=price))
            self.adjust(dict(code=code, delta=12, note='演示数量 非实物库存'))
        self.create_order(dict(number='DEMO-ORDER-001', note='演示订单 非真实交易', lines=[dict(code='DEMO-B38', quantity=2)]))


def server_for(store, port=8766):
    csrf = secrets.token_urlsafe(32)
    host = f"127.0.0.1:{port}"
    sessions = {}
    auth_lock = threading.Lock()
    failures = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def respond(self, body, status=200, kind='application/json; charset=utf-8', cookie=None):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            if cookie:
                self.send_header('Set-Cookie', cookie)
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def allowed(self):
            return self.headers.get('Host') == host

        def authenticated(self):
            try:
                cookies = SimpleCookie(self.headers.get('Cookie', ''))
                token = cookies.get('local_session')
                with auth_lock:
                    expired = [key for key, expiry in sessions.items() if expiry < time.monotonic()]
                    for key in expired:
                        sessions.pop(key, None)
                    return bool(token and token.value in sessions)
            except CookieError:
                return False

        def do_GET(self):
            if not self.allowed():
                return self.respond({'error': '访问来源不允许'}, 403)
            path = urlsplit(self.path).path
            if path == '/api/health':
                return self.respond({'name': NAME, 'version': VERSION, 'demo': store.demo})
            if path == '/login.js':
                return self.respond((BASE / 'login.js').read_bytes(), kind='application/javascript; charset=utf-8')
            if path == '/':
                filename = 'index.html' if self.authenticated() else 'login.html'
                page = (BASE / filename).read_text(encoding='utf-8').replace('__CSRF__', csrf)
                page = page.replace('__SETUP__', 'false' if store.has_password() else 'true')
                page = page.replace('__MODE_NOTICE__',
                    '演示模式：账号admin，密码Demo-Only-8766。仅含测试数据。' if store.demo else
                    ('正式本地库：使用已设置的本机密码登录。' if store.has_password() else
                     '正式本地库首次运行：请由负责人设置12至200字符密码。'))
                return self.respond(page.encode('utf-8'), kind='text/html; charset=utf-8')
            if path == '/style.css':
                return self.respond((BASE / 'style.css').read_bytes(), kind='text/css; charset=utf-8')
            if not self.authenticated():
                return self.respond({'error': '请先登录本机系统'}, 401)
            if path == '/api/state':
                return self.respond(store.snapshot())
            if path == '/integration-source':
                source = html.escape((BASE / 'doudian_adapter.py').read_text(encoding='utf-8'))
                page = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>接口适配源码</title>'
                        '<style>body{margin:24px;font:14px/1.55 Consolas,monospace;color:#17314d}'
                        'pre{white-space:pre-wrap;background:#f3f6f8;padding:18px}</style>'
                        '<h1>电商商品与订单管理系统 V1.0 · 接口适配源码</h1>'
                        '<p>实际文件 doudian_adapter.py：离线构造与签名，未向抖店发送请求。完整文件另附。</p>'
                        '<pre>' + source + '</pre></html>')
                return self.respond(page.encode('utf-8'), kind='text/html; charset=utf-8')
            if path in ('/client.js', '/style.css'):
                kind = 'application/javascript; charset=utf-8' if path.endswith('.js') else 'text/css; charset=utf-8'
                return self.respond((BASE / path[1:]).read_bytes(), kind=kind)
            if path == '/export.csv':
                return self.respond(store.export_csv(), kind='text/csv; charset=utf-8')
            return self.respond({'error': '页面不存在'}, 404)

        def do_POST(self):
            if not self.allowed() or self.headers.get('X-CSRF-Token') != csrf:
                return self.respond({'error': '访问来源不允许'}, 403)
            if self.headers.get('Origin') not in (None, 'http://' + host):
                return self.respond({'error': '访问来源不允许'}, 403)
            routes = {'/api/sku': store.save_sku, '/api/import': lambda x: store.import_csv(x.get('csv')),
                      '/api/stock': store.adjust, '/api/order': store.create_order, '/api/transition': store.transition}
            route = routes.get(urlsplit(self.path).path)
            path = urlsplit(self.path).path
            if route is None and path not in ('/api/login', '/api/setup', '/api/logout'):
                return self.respond({'error': '接口不存在'}, 404)
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 2_000_000:
                    raise ValueError('请求过大或为空')
                value = json.loads(self.rfile.read(length))
                if not isinstance(value, dict):
                    raise ValueError('请求须为对象')
                if path in ('/api/login', '/api/setup'):
                    password = value.get('password')
                    with auth_lock:
                        recent = time.monotonic() - 60
                        failures[:] = [stamp for stamp in failures if stamp >= recent]
                        if len(failures) >= 5:
                            return self.respond({'error': '尝试过于频繁，请一分钟后再试'}, 429)
                    if value.get('username') != 'admin':
                        raise ValueError('账号或密码错误')
                    if path == '/api/setup':
                        if store.demo:
                            raise ValueError('演示模式不提供正式密码设置')
                        store.set_password(password)
                    if not store.verify_password(password):
                        with auth_lock:
                            failures.append(time.monotonic())
                        return self.respond({'error': '账号或密码错误'}, 401)
                    token = secrets.token_urlsafe(32)
                    with auth_lock:
                        sessions[token] = time.monotonic() + 8 * 3600
                    return self.respond({'message': '已登录'}, cookie=f'local_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800')
                if not self.authenticated():
                    return self.respond({'error': '请先登录本机系统'}, 401)
                if path == '/api/logout':
                    cookies = SimpleCookie(self.headers.get('Cookie', ''))
                    with auth_lock:
                        sessions.pop(cookies['local_session'].value, None)
                    return self.respond({'message': '已退出'}, cookie='local_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
                return self.respond(route(value))
            except (ValueError, KeyError, TypeError, sqlite3.IntegrityError) as exc:
                return self.respond({'error': str(exc)}, 400)
            except Exception:
                return self.respond({'error': '系统处理失败，请检查本地运行环境'}, 500)

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description=NAME)
    parser.add_argument('--demo', action='store_true', help='独立演示数据库，样例不代表真实商品或交易')
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--db', type=Path)
    parser.add_argument('--catalog', type=Path, default=CATALOG, help='只读产品身份台账JSON，products项内含id')
    parser.add_argument('--backup', type=Path, help='创建一致性数据库备份后退出')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('端口必须在1024至65535之间')
    path = args.db or BASE / '.local' / ('demo.db' if args.demo else 'production.db')
    if args.backup and not path.exists():
        parser.error('源数据库不存在，不能备份')
    store = Store(path, args.demo, args.catalog)
    store.seed()
    if args.backup:
        print(store.backup(args.backup))
        return
    server = server_for(store, args.port)
    print(f'{NAME} {VERSION} http://127.0.0.1:{args.port}  模式：' + ('演示' if args.demo else '正式本地'))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
