"""Read-only exact identity checks against the original local CRM workbook."""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from core import EMAIL, ROOT, blocked_platform, now

CRM_PATH = ROOT / "04_客户开发/01_线索与CRM/outputs/01a0a569-4d14-7a43-b384-bdd1bb8d08a2/主动获客_规模化流水线_2026-09-17.xlsx"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
ACCOUNT_FIELDS = {"Lead ID", "Website / identity source", "Business email/form", "CRM stage", "Last touch", "Stop / opt-out"}
OUTREACH_FIELDS = {"Lead ID", "Actual date", "Status", "Outcome"}


def domains(value):
    """Exact published hosts only; never guess parent domains or identity from a name."""
    result = set()
    for token in re.split(r"[\s;；,，<>\"']+", str(value)):
        token = token.strip("()[]{}。")
        if not token or "@" in token:
            continue
        try:
            parsed = urlsplit(token if "://" in token else "https://" + token)
            host = (parsed.hostname or "").encode("idna").decode("ascii").lower().rstrip(".").removeprefix("www.")
            if parsed.scheme in {"http", "https"} and "." in host and not parsed.username and not blocked_platform("https://" + host):
                result.add(host)
        except (ValueError, UnicodeError):
            continue
    return result


def stop_state(value):
    raw = str(value).strip()
    token = re.sub(r"[\s_-]+", " ", raw).lower()
    if token in {"yes", "y", "true", "1", "stop", "do not contact", "dnc", "opt out", "unsubscribed", "unsubscribe", "是", "停止", "停止联系", "退订", "拒绝联系"}:
        return "明确停止"
    if token in {"no", "n", "false", "0", "否", "未停止", "未退订"}:
        return "未发现明确停止"
    return "未知"


def stop_reason(value):
    raw = str(value).strip()
    gates = {"TECHNICAL_GATE": "技术门槛待解决", "EMAIL_INVALID": "联系入口无效", "CATEGORY_MISMATCH": "品类不匹配", "PAUSED_NOT_NOW": "时机暂缓"}
    return gates.get(raw.upper(), "停止联系标记" if stop_state(raw) == "明确停止" else "未标记停止，仍须核范围" if stop_state(raw) == "未发现明确停止" else "空值待核" if not raw else "其他原始门槛或歧义待核")


def _date(value, date1904=False):
    value = str(value).strip()
    try:
        if re.fullmatch(r"\d+(?:\.\d+)?", value):
            serial = float(value)
            if not 1 <= serial <= 150000:
                return ""
            return ((datetime(1904, 1, 1) if date1904 else datetime(1899, 12, 30)) + timedelta(days=serial)).isoformat(timespec="seconds")
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None).isoformat(timespec="seconds")
    except (ValueError, OverflowError):
        return ""


def _table(archive, path, strings, required):
    root = ET.fromstring(archive.read(path))
    header = None
    output = []
    for row in root.findall("m:sheetData/m:row", NS):
        cells = {}
        for cell in row.findall("m:c", NS):
            # A formula is not an identity or stop decision, even with a cached value.
            if cell.find("m:f", NS) is not None:
                text = "[公式未核验]"
            else:
                value = cell.find("m:v", NS)
                inline = cell.find("m:is", NS)
                text = value.text or "" if value is not None else "".join(inline.itertext()) if inline is not None else ""
                if cell.get("t") == "s":
                    text = strings[int(text)]
            cells[re.sub(r"\d", "", cell.get("r", ""))] = text
        if header is None:
            if "Lead ID" in cells.values():
                header = cells
                if not required.issubset(set(header.values())):
                    raise ValueError("CRM表头缺失：" + ", ".join(sorted(required - set(header.values()))))
            continue
        record = {name: cells.get(col, "") for col, name in header.items() if name}
        if record.get("Lead ID", "").strip():
            record["_row"] = int(row.get("r", "0"))
            output.append(record)
    if header is None:
        raise ValueError("未找到CRM Lead ID表头")
    return output


class CRMReader:
    def __init__(self, path=CRM_PATH):
        self.path = Path(path)
        self.signature = None
        self.accounts, self.actions = [], []
        self.meta = {"status": "未核验"}

    def load(self):
        try:
            stat = self.path.stat()
            signature = (stat.st_mtime_ns, stat.st_size)
            if signature == self.signature:
                return
            if stat.st_size > 30_000_000:
                raise ValueError("CRM文件超过只读核对上限")
            raw = self.path.read_bytes()
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                if sum(i.file_size for i in archive.infolist()) > 100_000_000:
                    raise ValueError("CRM解压内容超过核对上限")
                strings = ["".join(s.itertext()) for s in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("m:si", NS)] if "xl/sharedStrings.xml" in archive.namelist() else []
                workbook = ET.fromstring(archive.read("xl/workbook.xml"))
                relations = {r.get("Id"): r.get("Target") for r in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels")) if r.get("TargetMode") != "External"}
                sheets = {s.get("name"): relations.get(s.get(RID)) for s in workbook.findall("m:sheets/m:sheet", NS)}
                def target(name):
                    value = sheets.get(name)
                    if not value:
                        raise ValueError("CRM缺少工作表：" + name)
                    path = value.lstrip("/") if value.startswith("/") else "xl/" + value
                    if ".." in PurePosixPath(path).parts:
                        raise ValueError("CRM工作表引用无效")
                    return path
                accounts = _table(archive, target("Account Pool"), strings, ACCOUNT_FIELDS)
                actions = _table(archive, target("Outreach Log"), strings, OUTREACH_FIELDS)
                props = workbook.find("m:workbookPr", NS)
                self.date1904 = props is not None and props.get("date1904") in {"1", "true"}
            self.accounts, self.actions = accounts, actions
            self.signature = signature
            self.meta = {"status": "已读取", "workbook": str(self.path), "sha256": hashlib.sha256(raw).hexdigest(), "file_modified_at": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"), "loaded_at": now(), "coverage": "仅核对本工作簿；不覆盖独立发送回执、其他客户项目或未登记退订"}
        except (OSError, ValueError, KeyError, IndexError, zipfile.BadZipFile, ET.ParseError) as exc:
            self.signature = None
            self.accounts, self.actions = [], []
            self.meta = {"status": "读取失败", "workbook": str(self.path), "error": "CRM文件不存在" if isinstance(exc, FileNotFoundError) else str(exc)[:240], "loaded_at": now()}

    def check(self, candidate):
        self.load()
        base = {**self.meta, "checked_at": now(), "matches": [], "stop_state": "未知", "local_stop": candidate.get("review", {}).get("state") == "停止联系", "contact_permission": "未确认；核对结果不代表营销同意或当前采购需求"}
        if self.meta["status"] != "已读取":
            return {**base, "match_status": "读取失败", "next_action": "本地已停止联系；CRM读取失败不取消停止状态" if base["local_stop"] else "恢复CRM读取后再核对，不按新客户处理"}
        hosts = domains(candidate.get("website", ""))
        emails = {str(c.get("value", "")).lower() for c in candidate.get("contacts", []) if c.get("kind") == "email"}
        matches = []
        domain_leads, email_leads = set(), set()
        for account in self.accounts:
            domain_hit = hosts & (domains(account.get("Website / identity source", "")) | domains(account.get("Business email/form", "")))
            email_hit = emails & {m.group().lower() for m in EMAIL.finditer(account.get("Business email/form", ""))}
            if not domain_hit and not email_hit:
                continue
            lead = account["Lead ID"]
            if domain_hit:
                domain_leads.add(lead)
            if email_hit:
                email_leads.add(lead)
            touches, history = [], []
            if account.get("Last touch"):
                touches.append({"sheet": "Account Pool", "row": account["_row"], "raw_date": account["Last touch"], "date": _date(account["Last touch"], self.date1904), "basis": "CRM Last touch字段；不推断送达或真人回复"})
            for action in self.actions:
                if action["Lead ID"] != lead:
                    continue
                history.append({"sheet": "Outreach Log", "row": action["_row"], "actual_date_raw": action.get("Actual date", ""), "status": action.get("Status", ""), "outcome": action.get("Outcome", ""), "notes": action.get("Notes", ""), "evidence": action.get("Evidence / URL", "")})
                if not action.get("Actual date"):
                    continue
                touches.append({"sheet": "Outreach Log", "row": action["_row"], "raw_date": action["Actual date"], "date": _date(action["Actual date"], self.date1904), "status": action.get("Status", ""), "outcome": action.get("Outcome", ""), "basis": "CRM Actual date记录；原始发送回执仍待核"})
            dated = [t for t in touches if t["date"]]
            methods = [{"method": "域名exact", "field": field, "values": sorted(hosts & domains(account.get(field, "")))} for field in ("Website / identity source", "Business email/form") if hosts & domains(account.get(field, ""))]
            if email_hit:
                methods.append({"method": "邮箱exact", "field": "Business email/form", "values": sorted(email_hit)})
            matches.append({"lead_id": lead, "sheet": "Account Pool", "row": account["_row"], "methods": methods, "stage": account.get("CRM stage", ""), "stop_raw": account.get("Stop / opt-out", ""), "stop_state": stop_state(account.get("Stop / opt-out", "")), "stop_reason": stop_reason(account.get("Stop / opt-out", "")), "latest_touch": max(dated, key=lambda t: t["date"]) if dated else None, "undated_touches": [t for t in touches if not t["date"]], "history": history, "next_action_raw": account.get("Next action", "")})
        if not matches:
            return {**base, "match_status": "未匹配", "next_action": "本地已停止联系；本文件未匹配不取消停止状态" if base["local_stop"] else "本文件未匹配，非新增或可联系确认；继续核对品牌异名与独立发送记录"}
        conflict = len(matches) > 1 or bool(domain_leads and email_leads and domain_leads != email_leads)
        stop = "明确停止" if any(m["stop_state"] == "明确停止" for m in matches) else "未知" if any(m["stop_state"] == "未知" for m in matches) else "未发现明确停止"
        local_stop = base["local_stop"]
        return {**base, "matches": matches, "match_status": "冲突待核" if conflict else "已匹配", "stop_state": stop, "next_action": "停止联系，不进入建议联系" if stop == "明确停止" or local_stop else "多条身份命中，先人工核对归属与停止范围" if conflict else "停止状态未知，先核原CRM与发送回执" if stop == "未知" else "已有CRM记录，先回收历史触达结果并核独立停止清单；不自动外发"}

    def annotate(self, candidates):
        return [{**row, "crm": self.check(row)} for row in candidates]
