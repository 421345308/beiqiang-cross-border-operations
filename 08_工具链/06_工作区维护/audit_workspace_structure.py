#!/usr/bin/env python3
"""Read-only full Git inventory and entry-route audit, including mounted AGENTS.

No media, credentials or customer bodies are read. Historical evidence is counted
and preserved; missing historical links are separate from current entry failures.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import unquote

from check_workspace import markdown_targets


MOUNT_ENTRIES = (
    "05_内容与视频/03_通用AI视频实验/AGENTS.md",
    "05_内容与视频/03_通用AI视频实验/README.md",
)


def is_wire_record(data):
    """Recognize complete protocol envelopes, not normalized business summaries."""
    if not isinstance(data, dict):
        return False
    keys = set(data)
    if any(str(key).endswith("_response") for key in keys):
        return True
    if {"trace_id", "biz_success"} <= keys or "_trace_id_" in keys:
        return True
    if any(str(key).startswith("param_product_top_") for key in keys):
        return True
    response = data.get("response")
    if "response" in keys and keys.intersection({
        "observed_at", "observed_at_utc", "method", "error",
        "requested_product_id", "operation_kind",
    }):
        return True
    return isinstance(response, dict) and any(
        str(key).endswith("_response") for key in response
    )


def local_destination(document, destination, root):
    raw = unquote(destination.split("#", 1)[0].split("?", 1)[0]).strip("<>")
    if not raw or "://" in raw or raw.startswith(("mailto:", "tel:", "data:")):
        return None
    if raw.startswith("/"):
        return root / raw.lstrip("/")
    return document.parent / raw


def audit(root, wire=False):
    names = [x for x in subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=root).decode("utf8").split("\0") if x]
    domains = collections.Counter()
    suffixes = collections.Counter()
    entries, agents, missing, historical_missing, empty, raw = [], [], [], [], [], []
    hashes = collections.defaultdict(list)
    documents = 0
    paths = sorted(set(names) | {x for x in MOUNT_ENTRIES if (root / x).is_file()})
    for name in paths:
        path = root / name
        domains[name.split("/")[0]] += 1
        suffixes[path.suffix.lower() or "(none)"] += 1
        if not path.is_file():
            continue  # staged deletions and concurrent work are not recreated
        if path.stat().st_size == 0:
            empty.append(name)
        if wire and name.startswith("02_Alibaba运营/"):
            if path.suffix.lower() == ".xml":
                raw.append(name)
            elif path.suffix.lower() == ".json":
                try:
                    if is_wire_record(json.loads(path.read_text(encoding="utf-8-sig"))):
                        raw.append(name)
                except (ValueError, UnicodeError):
                    pass
        if path.suffix.lower() != ".md" or "/vendor/" in name or "/node_modules/" in name:
            continue
        documents += 1
        contents = path.read_text(encoding="utf-8-sig")
        hashes[hashlib.sha256(contents.encode()).hexdigest()].append(name)
        frozen = any(part in name for part in (
            "/最终验收/工程/", "/schema_contract_fixtures/", "/supplier_originals/",
        ))
        is_entry = not frozen and path.name.lower() in {"readme.md", "agents.md", "agent.md"}
        if is_entry:
            entries.append(name)
        if path.name.lower() in {"agents.md", "agent.md"}:
            agents.append(name)
        for target in markdown_targets(contents):
            destination = local_destination(path, target, root)
            if destination is not None and not destination.exists():
                item = {"document": name, "target": target}
                (missing if is_entry else historical_missing).append(item)
    return {
        "ok": not missing and not raw,
        "scope": "Full tracked-file inventory; all Markdown entry links; mounted generic-video entry; optional Alibaba wire-envelope check. Historical link gaps are reported separately; no platform or media acceptance is implied.",
        "tracked_files": len(names), "domains": dict(sorted(domains.items())),
        "suffixes": dict(suffixes), "markdown_documents": documents,
        "entry_documents": entries, "agent_entries": agents,
        "missing_entry_links": missing, "historical_link_gaps": historical_missing,
        "empty_files": empty, "tracked_wire_records": raw,
        "identical_markdown_groups": [v for v in hashes.values() if len(v) > 1],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--wire", action="store_true", help="also read Alibaba JSON protocol shapes")
    parser.add_argument("--output", type=Path, help="write local report; keep it outside public Git")
    args = parser.parse_args()
    report = audit(args.root, args.wire)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps({k: report[k] for k in (
        "ok", "tracked_files", "markdown_documents", "agent_entries",
        "missing_entry_links", "tracked_wire_records",
    )}, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf8")
    raise SystemExit(main())
