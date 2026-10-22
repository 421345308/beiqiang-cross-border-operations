"""Public company research. No login, message sending or CRM mutation."""
from __future__ import annotations

import csv
import hashlib
import html
import http.client
import io
import ipaddress
import json
import re
import socket
import ssl
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urlencode, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

AGENT = "BeiqiangCompanyResearch/0.1"
ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "04_客户开发/02_目标名单/.local/客户发现助手"
EMAIL = re.compile(r"(?<![\w.+-])[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,63}(?![\w-]|\.[A-Z0-9])", re.I)
SOCIAL = {"facebook.com", "instagram.com", "linkedin.com", "tiktok.com", "x.com", "twitter.com", "whatsapp.com", "wa.me", "google.com", "bing.com", "maps.google.com"}
QUERY_ROLES = ["footwear importer", "shoe distributor", "footwear private label brand", "footwear retailer supplier application"]
PATTERNS = {
    "footwear": r"\b(?:footwear|shoes?|sneakers?|slippers?|sandals?)\b|schoenen|schuhe|chaussures|calzature|calzado",
    "casual": r"\b(?:comfort|walking|casual|knit|slip.on|lightweight|canvas|sneakers?)\b|pantoffels",
    "distribution": r"\b(?:importer|importing|distributor|distributing|wholesale|supplying retailers|retail network)\b|groothandel|distributeur",
    "private_label": r"\bprivate[ -]label\b|\bown[ -]brands?\b|eigen merk",
    "retail": r"\b(?:retailer|retail stores?|shoe stores?|our stores?|shop online)\b",
    "manufacturing": r"\b(?:we manufacture|our factor(?:y|ies)|manufacturer|manufacturing partners|sourcing)\b",
    "specialist": r"\b(?:safety footwear|medical footwear|orthop(?:a)?edic|steel toe|EN ISO|medical devices)\b",
    "supplier_intake": r"\b(?:become a supplier|supplier application|vendor application|new vendor submission|supplier registration|submit your (?:brand|product)|prospective suppliers)\b",
    "active_demand": r"\b(?:we are (?:currently )?(?:looking for|seeking) (?:new )?(?:footwear |shoe )?(?:suppliers|manufacturers)|inviting (?:new )?suppliers to (?:apply|register))\b",
    "origin_constraint": r"\b(?:all (?:of )?our factories are in (?:Spain|Italy|Portugal|Europe)|we represent (?:Spanish|Italian|Portuguese|European) (?:footwear )?(?:factories|manufacturers)|all (?:of )?our (?:footwear|shoes) (?:is|are) made in (?:Spain|Italy|Portugal))\b",
}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean(text):
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def host_key(url):
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def normalize_url(value):
    value = value.strip()
    if re.match(r"(?:javascript|data|file|ftp|mailto|tel):", value, re.I) or ("://" in value and not re.match(r"^https?://", value, re.I)):
        raise ValueError("只接受公开 http/https 网址")
    if not re.match(r"^https?://", value, re.I):
        value = "https://" + value
    p = urlsplit(value)
    if p.scheme.lower() not in {"http", "https"} or not p.hostname or p.username is not None or p.password is not None:
        raise ValueError("只接受不含登录凭证的公开 http/https 网址")
    if p.port not in {None, 80, 443} or any(c in value for c in "\r\n\x00\\"):
        raise ValueError("不支持此网址或端口")
    host = p.hostname.encode("idna").decode("ascii").lower().rstrip(".")
    if ":" in host:
        host = "[" + host + "]"
    netloc = host + (":" + str(p.port) if p.port else "")
    return urlunsplit((p.scheme.lower(), netloc, quote(p.path or "/", safe="/%:@!$&'()*+,;=-._~"), quote(p.query, safe="%=&?/:@!$'()*+,;~-._"), ""))


def blocked_platform(url):
    host = host_key(url)
    return any(host == x or host.endswith("." + x) for x in SOCIAL)


def bounded_read(response, limit, deadline, sock=None):
    chunks, total = [], 0
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("页面读取超时，留待人工查看")
        if sock is not None:
            sock.settimeout(min(10, remaining))
        chunk = response.read1(min(65536, limit + 1 - total))
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        total += len(chunk)
        if total > limit:
            raise ValueError("页面超过读取上限，留待人工核验")


def dns_over_https(host):
    """Resolve synthetic VPN DNS answers through the documented public resolver.

    This does not change OS networking or relax private-address/TLS validation.
    Bootstrap is the resolver's published IP; certificates use its real hostname.
    """
    conn = http.client.HTTPSConnection("cloudflare-dns.com", 443, timeout=12, context=ssl.create_default_context())
    conn._create_connection = lambda address, timeout=None, source_address=None, **kw: socket.create_connection(("1.1.1.1", 443), timeout, source_address)
    try:
        conn.request("GET", "/dns-query?" + urlencode({"name": host, "type": "A"}), headers={"Accept": "application/dns-json", "User-Agent": AGENT})
        sock = conn.sock
        response = conn.getresponse()
        raw = bounded_read(response, 32000, time.monotonic() + 15, sock)
        if response.status != 200:
            raise ValueError("公开DNS解析失败，未访问目标站点")
        data = json.loads(raw)
        questions = data.get("Question", [])
        if data.get("Status") != 0 or not any(q.get("name", "").rstrip(".").lower() == host.lower() and q.get("type") == 1 for q in questions):
            raise ValueError("公开DNS没有返回对应域名记录")
        return [a["data"] for a in data.get("Answer", []) if a.get("type") == 1]
    finally:
        conn.close()


def public_addresses(host, port):
    result = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    addresses = list(dict.fromkeys(row[4][0] for row in result))
    synthetic_ranges = [ipaddress.ip_network("198.18.0.0/15"), ipaddress.ip_network("2001:2::/48")]
    is_literal = False
    try:
        ipaddress.ip_address(host)
        is_literal = True
    except ValueError:
        pass
    if addresses and not is_literal and all(any(ipaddress.ip_address(a) in net for net in synthetic_ranges) for a in addresses):
        addresses = list(dict.fromkeys(dns_over_https(host)))
    if not addresses:
        raise ValueError("域名没有可用地址")
    for addr in addresses:
        parsed = ipaddress.ip_address(addr)
        if not parsed.is_global or (parsed.version == 6 and parsed.ipv4_mapped and not parsed.ipv4_mapped.is_global):
            raise ValueError("仅访问公开互联网地址")
    return addresses


class PublicTransport:
    """Pin each connection to a validated public IP, preserving TLS hostname checks."""
    def get(self, url, limit=1_500_000, allow_redirect=None):
        for _ in range(5):
            url = normalize_url(url)
            if blocked_platform(url):
                raise ValueError("此工具不抓取社媒或搜索平台，请转到企业官网")
            p = urlsplit(url)
            port = p.port or (443 if p.scheme == "https" else 80)
            addresses = public_addresses(p.hostname, port)
            conn = http.client.HTTPSConnection(p.hostname, port, timeout=12, context=ssl.create_default_context()) if p.scheme == "https" else http.client.HTTPConnection(p.hostname, port, timeout=12)
            conn._create_connection = lambda address, timeout=None, source_address=None, **kw: socket.create_connection((addresses[0], port), timeout, source_address)
            try:
                conn.request("GET", urlunsplit(("", "", p.path, p.query, "")), headers={"User-Agent": AGENT, "Accept": "text/html,text/plain;q=0.9", "Accept-Encoding": "identity"})
                sock = conn.sock
                resp = conn.getresponse()
                headers = {k.lower(): v for k, v in resp.getheaders()}
                if resp.status in {301, 302, 303, 307, 308}:
                    target = normalize_url(urljoin(url, headers.get("location", "")))
                    if target == url:
                        raise ValueError("无效跳转")
                    if p.scheme == "https" and urlsplit(target).scheme != "https":
                        raise ValueError("不跟随降级到非加密页面的跳转")
                    if allow_redirect:
                        allow_redirect(url, target)
                    url = target
                    continue
                data = bounded_read(resp, limit, time.monotonic() + 25, sock)
                charset = re.search(r"charset=([\w-]+)", headers.get("content-type", ""), re.I)
                try:
                    body = data.decode(charset.group(1) if charset else "utf-8", errors="replace")
                except LookupError:
                    body = data.decode("utf-8", errors="replace")
                return {"url": url, "status": resp.status, "headers": headers, "body": body}
            finally:
                conn.close()
        raise ValueError("跳转次数过多")


class PageParser(HTMLParser):
    def __init__(self, url):
        super().__init__(convert_charrefs=True)
        self.url, self.parts, self.links, self.forms = url, [], [], []
        self.stack, self.skip, self.anchor, self.form = [], 0, None, None
        self.title, self.in_title = "", False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        hidden = tag in {"script", "style", "noscript", "template", "svg"} or "hidden" in attrs or attrs.get("aria-hidden") == "true" or bool(re.search(r"display\s*:\s*none|visibility\s*:\s*hidden", attrs.get("style", ""), re.I))
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append((tag, hidden))
            self.skip += int(hidden)
        if self.skip:
            return
        if tag == "title":
            self.in_title = True
        if tag == "a" and attrs.get("href"):
            self.anchor = {"url": urljoin(self.url, attrs["href"]), "label": attrs.get("aria-label", ""), "text": ""}
            self.links.append(self.anchor)
        if tag == "form":
            self.form = {"url": self.url, "action": urljoin(self.url, attrs.get("action", "")), "text": "", "fields": [], "method": attrs.get("method", "get")}
            self.forms.append(self.form)
        if self.form is not None and tag in {"input", "textarea", "select"}:
            self.form["fields"].append(attrs.get("name", "") + " " + attrs.get("placeholder", ""))

    def handle_endtag(self, tag):
        if tag == "a":
            self.anchor = None
        if tag == "form":
            self.form = None
        if tag == "title":
            self.in_title = False
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                self.skip -= sum(int(x[1]) for x in self.stack[i:])
                del self.stack[i:]
                break

    def handle_data(self, data):
        if self.skip:
            return
        data = clean(data)
        if not data:
            return
        if self.in_title:
            self.title += data + " "
            return
        self.parts.append(data)
        if self.anchor is not None:
            self.anchor["text"] += data + " "
        if self.form is not None:
            self.form["text"] += data + " "

    @property
    def text(self):
        return clean(" ".join(self.parts))


def parse_page(body, url):
    p = PageParser(url)
    p.feed(body)
    return p


def evidence(text, pattern, url):
    m = re.search(pattern, text, re.I)
    return {"url": url, "quote": clean(text[max(0, m.start() - 75):m.end() + 120])} if m else None


def contact_role(value, context=""):
    local = value.split("@", 1)[0].lower()
    if re.search(r"privacy|dpo|legal|abuse|noreply|no-reply|careers|jobs|press|media", local):
        return "不用于开发"
    if re.search(r"support|service|help|orders?|returns?", local):
        return "客服或订单"
    if re.search(r"buy(?:er|ing)|purchas|procurement|sourc|vendors?|suppliers?", local):
        return "采购相关待核"
    if re.search(r"sales|wholesale|trade", local):
        return "对外销售"
    return "通用商务待核"


def extract_contacts(page):
    contacts = {}
    def add(kind, value, context="", role=None):
        value = value.strip().strip(".,;:")
        if len(value) > 320:
            return
        if kind == "email":
            value = value.lower()
            role = contact_role(value, context)
        contacts[(kind, value)] = {"kind": kind, "value": value, "role": role or "通用商务待核", "source_url": page.url, "evidence": clean(context)[:280], "checked_at": now(), "delivery_status": "未验证", "permission": "公开入口不代表同意接收营销", "review_required": True}
    text = page.text
    for m in EMAIL.finditer(text):
        add("email", m.group(), text[max(0, m.start() - 65):m.end() + 65])
    for link in page.links:
        u, context = link["url"], clean(link["label"] + " " + link["text"])
        parsed = urlsplit(u)
        if parsed.scheme == "mailto":
            # Mailto body and subject are never harvested as contact addresses.
            for address in re.split(r"[,;]", unquote(parsed.path)):
                if EMAIL.fullmatch(address):
                    add("email", address, context or address)
        elif parsed.scheme == "tel" and re.fullmatch(r"\+?[\d\s().-]{6,30}", unquote(parsed.path)):
            add("phone", unquote(parsed.path), context, "公开电话待核")
        elif parsed.scheme in {"http", "https"} and ((parsed.hostname or "").lower() in {"wa.me", "api.whatsapp.com", "www.whatsapp.com"}):
            add("whatsapp", u, context, "须确认联系用途与接收同意")
    for form in page.forms:
        context = clean(form["text"] + " " + " ".join(form["fields"]))
        if not re.search(r"email|e-mail|message|enquiry|inquiry|company|supplier|vendor", context, re.I):
            continue
        if re.search(r"newsletter|subscribe|mailing list|search", context, re.I) and not re.search(r"message|enquiry|inquiry|supplier|vendor", context, re.I):
            continue
        purpose = clean(page.title + " " + context)
        role = "供应商申请待核" if re.search(PATTERNS["supplier_intake"], purpose, re.I) else "对外销售" if re.search(r"become (?:a |an )?(?:retailer|stockist|distributor)|trade account|wholesale account", purpose, re.I) else "官网表单待核"
        add("form", page.url, context, role)
    return list(contacts.values())


def analyse(pages):
    signals = {}
    for p in pages:
        for name, pattern in PATTERNS.items():
            item = evidence(p.text, pattern, p.url)
            if item and name not in signals:
                signals[name] = item
    # Deliberately independent dimensions, not a conversion probability or buyer identity verdict.
    product = 2 if "casual" in signals and "footwear" in signals else 1 if "footwear" in signals else 0
    business = 2 if "distribution" in signals or "private_label" in signals else 1 if "retail" in signals else 0
    opportunity = "公开寻源表述待核时效" if "active_demand" in signals else "供应商申请入口待核" if "supplier_intake" in signals else "未发现当前采购需求"
    if "origin_constraint" in signals:
        tier = "供应链范围需核对"
    elif "manufacturing" in signals and not any(k in signals for k in ("distribution", "retail")):
        tier = "供需角色需核对"
    elif not product:
        tier = "待核主营"
    elif "specialist" in signals and not "casual" in signals:
        tier = "专项能力需核对"
    elif product == 2 and business == 2:
        tier = "优先人工核验"
    else:
        tier = "保留研究"
    risks = []
    if "origin_constraint" in signals:
        risks.append("自述有特定产地或代理工厂范围；先确认是否接受中国供应链")
    if "specialist" in signals:
        risks.append("包含专业性能品类；贝强能力需逐款核对")
    if "manufacturing" in signals:
        risks.append("含制造/寻源业务；需区分潜在采购方与同行")
    return {"tier": tier, "product_fit": product, "business_fit": business, "opportunity": opportunity, "signals": signals, "risks": risks, "method": "公开文字规则初筛，非AI背调结论；不是采购意向或转化概率"}


class Crawler:
    def __init__(self, transport=None, pause=time.sleep, clock=time.monotonic):
        self.transport, self.pause, self.clock = transport or PublicTransport(), pause, clock
        self.robots, self.last = {}, {}

    def wait(self, origin, delay=2):
        remain = delay - (self.clock() - self.last.get(origin, -10000))
        if remain > 0:
            self.pause(remain)
        self.last[origin] = self.clock()

    def policy(self, url):
        p = urlsplit(url)
        origin = f"{p.scheme}://{p.netloc}"
        if origin not in self.robots:
            self.wait(origin)
            try:
                r = self.transport.get(origin + "/robots.txt", limit=256_000, allow_redirect=lambda old, new: self.robot_redirect(origin, new))
            except (ValueError, OSError, http.client.HTTPException) as exc:
                raise ValueError("robots读取失败：" + clean(str(exc))) from exc
            parser = RobotFileParser()
            if r["status"] == 404:
                parser.parse([])
            elif r["status"] == 200:
                if re.search(r"<html|<!doctype", r["body"], re.I):
                    raise ValueError("robots返回网页，访问策略待人工核验")
                parser.parse(r["body"].splitlines())
            else:
                raise ValueError(f"robots HTTP {r['status']}，暂停该站采集")
            self.robots[origin] = parser
        parser = self.robots[origin]
        if not parser.can_fetch(AGENT, url):
            raise ValueError("robots不允许该路径，保留原链接供人工查看")
        rate = parser.request_rate(AGENT)
        delay = max(2, parser.crawl_delay(AGENT) or 0, rate.seconds / rate.requests if rate and rate.requests else 0)
        if delay > 30:
            raise ValueError("站点要求较长采集间隔，留待人工查看")
        self.wait(origin, delay)

    def robot_redirect(self, origin, target):
        if host_key(origin) != host_key(target) or urlsplit(target).path != "/robots.txt":
            raise ValueError("robots跳转到不同站点或路径，待人工核验")
        self.wait(f"{urlsplit(target).scheme}://{urlsplit(target).netloc}")

    def scan(self, seed, max_pages=4, evidence_dir=None, progress=None):
        start = normalize_url(seed["website"])
        if blocked_platform(start):
            raise ValueError("请提供企业官网，不使用社媒或搜索平台作为采集目标")
        key = host_key(start)
        queue = [start]
        for u in seed.get("pages", []):
            u = normalize_url(u)
            if host_key(u) == key and u not in queue:
                queue.append(u)
        visited, pages, attempts, contacts = set(), [], [], {}
        def redirect(old, target):
            if host_key(target) != key:
                raise ValueError("跳转至不同企业域名，先核实身份")
            self.policy(target)
        while queue and len(attempts) < max(1, min(int(max_pages), 8)):
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            if progress:
                progress(f"读取第{len(attempts) + 1}页")
            attempt = {"url": url, "checked_at": now()}
            try:
                self.policy(url)
                r = self.transport.get(url, allow_redirect=redirect)
                attempt.update({"final_url": r["url"], "http_status": r["status"]})
                if r["status"] in {401, 403, 429}:
                    attempt["error"] = "遇到访问限制，已停止该站采集"
                    attempts.append(attempt)
                    break
                if r["status"] != 200:
                    raise ValueError(f"HTTP {r['status']}")
                if not any(t in r["headers"].get("content-type", "").lower() for t in ("text/html", "application/xhtml+xml")):
                    raise ValueError("非HTML页面，留待人工阅读")
                if re.search(r"just a moment|verify you are human|access denied|<title[^>]*>[^<]*captcha", r["body"][:15000], re.I) and len(parse_page(r["body"], r["url"]).text) < 2000:
                    attempt["error"] = "遇到验证页面，已停止该站采集"
                    attempts.append(attempt)
                    break
                page = parse_page(r["body"], r["url"])
                if len(page.text) < 80:
                    attempt["warning"] = "正文较少，可能需要人工查看动态页面"
                pages.append(page)
                attempt["text_sha256"] = hashlib.sha256(page.text.encode()).hexdigest()
                attempt["title"] = clean(page.title)
                if evidence_dir:
                    evidence_dir.mkdir(parents=True, exist_ok=True)
                    name = hashlib.sha256(r["url"].encode()).hexdigest()[:20]
                    # Plain JSON only; untrusted HTML is never served or executed locally.
                    (evidence_dir / (name + ".json")).write_text(json.dumps({"url": page.url, "checked_at": attempt["checked_at"], "title": page.title, "text": page.text, "sha256": attempt["text_sha256"]}, ensure_ascii=False, indent=2), encoding="utf-8")
                for c in extract_contacts(page):
                    k = (c["kind"], c["value"])
                    if k not in contacts:
                        contacts[k] = c
                        contacts[k]["sources"] = [c["source_url"]]
                    elif c["source_url"] not in contacts[k]["sources"]:
                        contacts[k]["sources"].append(c["source_url"])
                candidates = []
                for link in page.links:
                    u = link["url"]
                    if not u.startswith(("http://", "https://")):
                        continue
                    try:
                        u = normalize_url(u)
                    except ValueError:
                        continue
                    if host_key(u) != key or urlsplit(u).query or re.search(r"login|account|cart|checkout|privacy|terms|\.pdf$", u, re.I):
                        continue
                    words = u + " " + link["text"] + " " + link["label"]
                    if re.search(r"contact|about|supplier|vendor|private.label|wholesale|over.ons|kontakt|contatt|contac", words, re.I):
                        priority = 0 if re.search(r"supplier|vendor|contact|kontakt|contac", words, re.I) else 1
                        candidates.append((priority, u))
                for _, u in sorted(candidates, key=lambda x: x[0]):
                    if u not in queue and u not in visited:
                        queue.append(u)
            except (ValueError, OSError, http.client.HTTPException) as exc:
                attempt["error"] = clean(str(exc))[:220]
                if "robots" in str(exc).lower():
                    attempts.append(attempt)
                    break
            attempts.append(attempt)
        result = analyse(pages)
        return {"analysis": result, "contacts": list(contacts.values()), "pages": attempts, "research_status": "已采集待核" if pages else "访问受限或读取失败", "checked_at": now(), "current_demand_confirmed": False}


def search_plan(market="United States", direction="comfort casual footwear"):
    market, direction = clean(market)[:100], clean(direction)[:120]
    queries = [f'{market} {direction} {role}' for role in QUERY_ROLES]
    return [{"query": q, "search_url": "https://www.google.com/search?" + urlencode({"q": q}), "purpose": "寻找企业官网；搜索摘要只作发现，不作联系方式证据"} for q in queries]


def new_candidate(seed):
    if not isinstance(seed, dict) or not isinstance(seed.get("website"), str):
        raise ValueError("每家候选须包含字符串形式的企业官网")
    if not isinstance(seed.get("pages", []), list) or not all(isinstance(u, str) for u in seed.get("pages", [])):
        raise ValueError("pages须为官网页面网址列表")
    website = normalize_url(str(seed.get("website", "")))
    if blocked_platform(website):
        raise ValueError("候选网址必须是企业官网")
    if not str(seed.get("website", "")).strip():
        raise ValueError("缺少企业官网")
    pages = [normalize_url(str(u)) for u in seed.get("pages", [])[:8]]
    source = str(seed.get("source_url", website))
    source = normalize_url(source)
    return {"id": "web-" + hashlib.sha256(host_key(website).encode()).hexdigest()[:16], "company": clean(str(seed.get("company", host_key(website))))[:180], "website": website, "market_hint": clean(str(seed.get("market_hint", "待核")))[:100], "source_url": source, "discovery_note": clean(str(seed.get("discovery_note", "")))[:600], "discovered_at": now(), "pages_to_read": pages, "research_status": "待采集", "review": {"state": "未核验", "note": ""}, "contacts": [], "analysis": {}, "pages": []}


def csv_export(records):
    out = io.StringIO(newline="")
    fields = ["候选ID", "公司", "官网", "市场线索待核", "初筛", "采购需求", "人工状态", "人工备注", "渠道", "公开入口", "入口用途", "来源", "核查时间", "联系条件", "CRM核对", "CRM匹配", "CRM Lead ID", "CRM停止状态", "CRM停止原值", "CRM最近动作记录（不等于触达）", "CRM匹配出处", "CRM核对时间", "CRM文件SHA256", "CRM下一步", "CRM未定日期及历史", "CRM门槛类别", "本地人工停止"]
    writer = csv.writer(out)
    writer.writerow(fields)
    for row in records:
        crm = row.get("crm", {})
        matches = crm.get("matches", [])
        crm_values = [crm.get("match_status", "未核验"), "; ".join(m["lead_id"] for m in matches), crm.get("stop_state", "未知"), "; ".join(m["lead_id"] + ": " + (m["stop_raw"] or "[空值]") for m in matches), "; ".join(m["lead_id"] + ": " + (m["latest_touch"]["raw_date"] if m.get("latest_touch") else "无可排序日期；不代表未触达") for m in matches), "; ".join(f'{m["sheet"]}!{m["row"]} ' + ",".join(x["method"] for x in m["methods"]) for m in matches), crm.get("checked_at", ""), crm.get("sha256", ""), crm.get("next_action", "未核验"), json.dumps([{"lead_id": m["lead_id"], "undated_touches": m.get("undated_touches", []), "history": m.get("history", [])} for m in matches], ensure_ascii=False), "; ".join(m["lead_id"] + ": " + m.get("stop_reason", "未知") for m in matches), "是" if crm.get("local_stop") else "否"]
        for c in row.get("contacts", []) or [{}]:
            values = [row["id"], row["company"], row["website"], row.get("market_hint", ""), row.get("analysis", {}).get("tier", ""), row.get("analysis", {}).get("opportunity", ""), row["review"]["state"], row["review"]["note"], c.get("kind", ""), c.get("value", ""), c.get("role", ""), c.get("source_url", ""), c.get("checked_at", ""), c.get("permission", ""), "须在正式CRM查重及核对停止联系状态；不是发送名单"]
            writer.writerow(["'" + str(v) if str(v).lstrip().startswith(("=", "+", "-", "@")) else v for v in values + crm_values])
    return "\ufeff" + out.getvalue()
