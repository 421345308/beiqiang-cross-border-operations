"""Offline trade-research review using the existing candidate store and CRM reader.

No network, credentials, CRM writes or messaging. Research inputs and outputs stay
in the existing ignored local candidate area. Source assertions remain human work.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date
from pathlib import Path

from app import Store
from core import DATA, host_key, new_candidate, normalize_url, now
from crm import CRMReader

WEIGHTS = {"product": 30, "bulk": 25, "active": 15, "brand": 15, "contact": 10, "potential": 5}
READABLE_WEBSITE = {"public_page", "official_page", "公开正文已打开"}


def private_path(value):
    target = Path(value).resolve()
    if not target.is_relative_to(DATA.resolve()):
        raise ValueError("研究输入和输出必须留在现有客户发现助手.local目录")
    return target


def validate(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("leads"), list) or not payload["leads"]:
        raise ValueError("输入须含非空leads列表")
    for lead in payload["leads"]:
        if not lead.get("company") or not lead.get("verification_status") or not lead.get("next_action"):
            raise ValueError("每家公司须有名称、核验状态及下一步")
        sources = lead.get("sources", [])
        if not sources:
            raise ValueError("缺少来源")
        source_urls = set()
        for source in sources:
            source_urls.add(normalize_url(source["url"]))
            date.fromisoformat(source["checked_at"][:10])
            if not source.get("access_level") or not source.get("evidence"):
                raise ValueError("来源须区分实读、索引、受阻并保留证据")
        if set(lead.get("score", {})) != set(WEIGHTS):
            raise ValueError("须按六个维度保留评分，不能仅填总分")
        for key, maximum in WEIGHTS.items():
            item = lead["score"][key]
            points = item.get("points")
            if isinstance(points, bool) or not isinstance(points, (float, int)) or not 0 <= points <= maximum:
                raise ValueError("评分超出范围：" + key)
            if not str(item.get("reason", "")).strip():
                raise ValueError("评分缺少依据：" + key)
            refs = item.get("source_urls", [])
            if points and (not refs or any(normalize_url(url) not in source_urls for url in refs)):
                raise ValueError("正分须指向本公司已列来源：" + key)
        for record in lead.get("trade_records", []):
            normalize_url(record["source_url"])
            if record.get("shipment_date"):
                date.fromisoformat(record["shipment_date"])
        if lead.get("website"):
            new_candidate({"company": lead["company"], "website": lead["website"]})
        if lead.get("website_verified") is True:
            proof = normalize_url(lead.get("website_source_url", ""))
            if not lead.get("website") or proof not in source_urls or host_key(proof) != host_key(lead["website"]):
                raise ValueError("已核官网须指向本公司已列同域来源")
            if not any(normalize_url(source["url"]) == proof and source["access_level"] in READABLE_WEBSITE for source in sources):
                raise ValueError("索引、摘要或受阻页面不能确认官网")
    return payload


def build(payload, reader, existing=()):
    validate(payload)
    known = {row["id"]: row for row in existing}
    seeds, reviewed = [], []
    for lead in payload["leads"]:
        row = {**lead, "total_score": sum(item["points"] for item in lead["score"].values())}
        if lead.get("website") and lead.get("website_verified") is True:
            seed = {"company": lead["company"], "website": lead["website"],
                    "market_hint": lead.get("country", "待核"), "source_url": lead["sources"][0]["url"],
                    "discovery_note": "贸易反查研究；" + lead.get("relationship_type", "关系待核") + "；" + lead["verification_status"] + "；评分仅决定研究投入；详细证据见海关反查/leads.json。"}
            candidate = new_candidate(seed)
            row["candidate_id"] = candidate["id"]
            candidate = known.get(candidate["id"], candidate)
            row["crm"] = reader.check(candidate)
            seeds.append(seed)
        else:
            row["candidate_id"] = ""
            row["crm"] = {"match_status": "缺已核官网未作精确匹配", "stop_state": "未知", "matches": [], "next_action": "先核实体及官网；不能按公司名猜匹配或导入"}
        reviewed.append(row)
    return {"checked_at": now(), "source_checked_at": payload.get("checked_at", ""),
            "scope": "研究排序；不是发送名单、当前需求或联系许可；正式CRM只读，别名和独立回执另核",
            "leads": reviewed}, {"candidates": seeds}


def csv_cell(value):
    value = str(value)
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def run(input_path, output_dir, import_candidates=False):
    input_path, output_dir = private_path(input_path), private_path(output_dir)
    raw = input_path.read_bytes()
    payload = json.loads(raw.decode("utf-8-sig"))
    store, reader = Store(), CRMReader()
    reviewed, seeds = build(payload, reader, store.read())
    reviewed["input_sha256"] = hashlib.sha256(raw).hexdigest()
    reader.load()
    before = reader.meta.get("sha256")
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in (("crm_review.json", reviewed), ("candidate_import.json", seeds)):
        (output_dir / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = ["company", "website", "country", "relationship_type", "tier", "total_score", "verification_status", "next_action", "candidate_id", "CRM核对", "Lead ID", "CRM停止状态", "CRM下一步", "CRM文件SHA256", "逐项评分与证据"]
    with (output_dir / "客户复核.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for lead in reviewed["leads"]:
            crm = lead["crm"]
            values = {key: lead.get(key, "") for key in fields}
            values.update({"CRM核对": crm["match_status"], "Lead ID": ";".join(m["lead_id"] for m in crm["matches"]),
                           "CRM停止状态": crm["stop_state"], "CRM下一步": crm["next_action"], "CRM文件SHA256": crm.get("sha256", ""),
                           "逐项评分与证据": json.dumps(lead["score"], ensure_ascii=False)})
            writer.writerow({key: csv_cell(value) for key, value in values.items()})
    added = store.add(seeds["candidates"]) if import_candidates and seeds["candidates"] else 0
    reader.load()
    if before and reader.meta.get("sha256") != before:
        raise RuntimeError("核对期间CRM原件有变化；须重新复核")
    return {"reviewed": len(reviewed["leads"]), "with_website": len(seeds["candidates"]), "added_to_existing_store": added,
            "crm_unchanged": bool(before and reader.meta.get("sha256") == before), "crm_status": reader.meta["status"], "output": str(output_dir)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="离线核验贸易研究字段，复用既有CRM与候选库")
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--import-candidates", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.input, args.output, args.import_candidates), ensure_ascii=False))
