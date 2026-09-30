#!/usr/bin/env python3
"""Read-only workspace checks. Run with --json for a machine-readable report.

Uses only Python's standard library. Checks filenames and selected governance
documents, never credentials, browser storage, business payloads or media bodies.
Historical reports are deliberately outside the active-link check.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from urllib.parse import unquote


BUSINESS = (
    "00_总控台", "01_产品资产", "02_Alibaba运营", "03_独立站", "04_客户开发",
    "05_内容与视频", "06_市场研究", "07_知识库与Skills", "08_工具链", "90_归档", "99_临时区",
)
ROOT_ALLOWED = set(BUSINESS) | {
    ".agents", ".git", ".gitignore", ".gitattributes", "AGENTS.md", "README.md", "skills-lock.json", "_codex_work",
    # Tool-managed entries. ".workbuddy" is the WorkBuddy session/memory store and must stay at the
    # workspace root; "outputs" is WorkBuddy's default deliverable staging dir. Neither is a business
    # directory: business results must still be relocated into the matching business directory, and
    # derived dumps must be moved to 99_临时区 (see 00_总控台/工作区维护.md).
    ".workbuddy", "outputs", ".workctl",
}
MEMORY_REQUIRED = {"id", "type", "title", "description", "status", "scope", "source", "privacy", "tags", "timestamp"}
MEMORY_OPTIONAL = {"supersedes", "verify_when", "review_after"}
MEMORY_TYPES = {"Authorization", "Preference", "Decision", "Experience"}
MEMORY_STATES = {"active", "superseded", "disputed", "archived"}
ACTIVE_CONTROL = (
    "当前状态.md", "产品经营主表.md", "资产索引.md", "跨渠道经营总览.md", "工作区维护.md",
)
PRUNE = {
    ".git", "node_modules", "browser_data", ".venv", "venv", "__pycache__",
    ".next", ".cache", "dist", "build", "_codex_work",
}
BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".svg",
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".mp3", ".wav", ".flac", ".m4a",
    ".zip", ".7z", ".rar", ".gz", ".tar", ".pdf", ".docx", ".xlsx", ".xls", ".pptx",
    ".exe", ".dll", ".pyd", ".pyc", ".so", ".whl", ".wasm", ".blend", ".blend1",
    ".glb", ".fbx", ".sqlite", ".sqlite3", ".db", ".pkl", ".npz",
    ".ico", ".ttf", ".otf", ".woff", ".woff2", ".npy", ".task", ".aac", ".ogg",
    ".doc", ".ppt", ".xlsm", ".ods", ".odt",
}
NESTED_ROOTS = ("03_独立站/03_网站源码/", "08_工具链/02_视频工具/opencut-classic/")
RESIDUE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico", ".pyc", ".pyo", ".log", ".cache"}


def reparse(path: Path) -> bool:
    """Windows junctions and symlinks must not be recursively traversed."""
    try:
        return path.is_symlink() or bool(
            getattr(path.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        )
    except OSError:
        return False


def frontmatter(text: str) -> tuple[dict[str, str], list[str]]:
    """Validate simple top-level fields without claiming to parse all YAML."""
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, ["missing YAML frontmatter"]
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}, ["unclosed YAML frontmatter"]
    fields: dict[str, str] = {}
    issues: list[str] = []
    for line in lines[1:end]:
        match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$", line)
        if not match:
            continue  # Nested list/block scalar lines are not top-level fields.
        key, value = match.groups()
        if key in fields:
            issues.append(f"duplicate metadata field: {key}")
        fields[key] = value.strip().strip("\"'")
    return fields, issues


def skill_residue_only(folder: Path) -> bool:
    """Identify empty/icon/cache leftovers by names without reading their bodies."""
    if reparse(folder):
        return False
    unreadable = []
    for base, dirs, files in os.walk(folder, followlinks=False, onerror=unreadable.append):
        if any(reparse(Path(base) / name) for name in dirs):
            return False
        for name in files:
            path = Path(base) / name
            if reparse(path) or (
                path.suffix.lower() not in RESIDUE_SUFFIXES
                and name.lower() not in {"desktop.ini", "thumbs.db", ".ds_store"}
            ):
                return False
    return not unreadable


def markdown_targets(text: str) -> list[str]:
    """Extract inline/reference link destinations outside fenced code blocks."""
    visible = []
    fence = None
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            continue
        if fence is None:
            visible.append(line)
    body = "\n".join(visible)
    destinations = re.findall(r"\]\(\s*(<[^>]+>|[^\n]*?)\s*\)", body)
    destinations += re.findall(r"^\s{0,3}\[[^\]]+\]:\s*(.+)$", body, re.MULTILINE)
    result = []
    for value in destinations:
        value = value.strip()
        if value.startswith("<"):
            value = value[1:value.find(">")]
        else:
            value = re.sub(r"\s+[\"'].*[\"']\s*$", "", value)
        value = value.replace("\\ ", " ").strip()
        if value and not value.startswith("#") and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", value):
            result.append(unquote(value.split("#", 1)[0].split("?", 1)[0]))
    return result


def declared_reads(text: str) -> tuple[list[str], list[str]]:
    """Only explicit skill sections create mandatory dependencies; ordinary links do not."""
    required: list[str] = []
    conditional: list[str] = []
    section = ""
    for line in text.splitlines():
        heading = re.match(r"^##\s+(.+?)\s*$", line)
        if heading:
            section = heading.group(1).lower()
            continue
        if not re.match(r"^\s*[-*]\s+", line):
            continue
        targets = markdown_targets(line)
        if section == "required reads":
            required.extend(targets)
        elif section.startswith("conditional reads") or section.startswith("conditional execution"):
            conditional.extend(targets)
    return required, conditional


def required_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Return cycles in mandatory skill calls; conditional links are excluded."""
    cycles: list[list[str]] = []
    visited: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> None:
        if node in stack:
            cycle = stack[stack.index(node):] + [node]
            if cycle not in cycles:
                cycles.append(cycle)
            return
        if node in visited:
            return
        visited.add(node)
        stack.append(node)
        for neighbor in sorted(graph.get(node, ())):
            visit(neighbor)
        stack.pop()

    for name in sorted(graph):
        visit(name)
    return cycles


def ids_field(value: str) -> list[str]:
    return [part.strip().strip("\"'") for part in value.strip("[]").split(",") if part.strip()]


def literal_paths(text: str) -> list[str]:
    """Find explicit workspace paths in inline code, not placeholders or examples."""
    visible = []
    fence = False
    for line in text.splitlines():
        if re.match(r"^\s{0,3}(`{3,}|~{3,})", line):
            fence = not fence
            continue
        if not fence:
            visible.append(line)
    prefixes = (*BUSINESS, ".agents", "references", "scripts")
    result = []
    for value in re.findall(r"`([^`\n]+)`", "\n".join(visible)):
        path = value.replace("\\", "/")
        if any(mark in path for mark in ("<", ">", "{", "}", "*", "?", "...", "://")):
            continue
        if "/" in path and path.split("/", 1)[0] in prefixes:
            result.append(path)
    return result


class WorkspaceCheck:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.errors: list[dict[str, str]] = []
        self.warnings: list[dict[str, str]] = []
        self.counts: dict[str, int] = {}

    def label(self, path: Path) -> str:
        try:
            return path.relative_to(self.root).as_posix()
        except ValueError:
            return str(path)

    def issue(self, check: str, path: Path, message: str, warning: bool = False) -> None:
        (self.warnings if warning else self.errors).append(
            {"check": check, "path": self.label(path), "message": message}
        )

    def read(self, path: Path, check: str) -> str | None:
        try:
            return path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            self.issue(check, path, "required document missing or unreadable as UTF-8")
            return None

    def links(self, path: Path, text: str, check: str) -> list[Path]:
        linked = []
        for destination in markdown_targets(text):
            target = self.root / destination.lstrip("/") if destination.startswith("/") else path.parent / destination
            # Keep the lexical route; resolving a junction changes it to another drive.
            target = Path(os.path.abspath(target))
            linked.append(target)
            if not target.exists():
                self.issue(check, path, f"missing local link: {destination}")
        return linked

    def code_links(self, path: Path, text: str, check: str) -> None:
        for destination in literal_paths(text):
            head = destination.split("/", 1)[0]
            target = (self.root if head in set(BUSINESS) | {".agents"} else path.parent) / destination
            target = Path(os.path.abspath(target))
            if not target.exists():
                self.issue(check, path, f"missing inline-code path: {destination}")

    def root_entries(self) -> None:
        for path in self.root.iterdir():
            if path.name not in ROOT_ALLOWED:
                self.issue("root", path, "unexpected root entry; place it in the matching business directory")
        for name in BUSINESS + (".agents", ".git", "AGENTS.md", "README.md", ".gitignore", "skills-lock.json"):
            if not (self.root / name).exists():
                self.issue("root", self.root / name, "required workspace entry missing")

    def governance(self) -> None:
        status = self.root / "00_总控台/当前状态.md"
        text = self.read(status, "governance")
        if text is not None:
            if not text.lstrip("\ufeff\n\r \t").startswith("# 当前状态"):
                self.issue("governance", status, "current status must start with its heading; replace old status instead of prepending updates")
            if len(text.encode("utf-8")) > 12 * 1024:
                self.issue("governance", status, "current status is too long; move dated execution detail to business records", warning=True)
        for folder in (self.root / "00_总控台", self.root / "07_知识库与Skills"):
            for path in folder.iterdir():
                if path.is_file() and re.search(r"(?i)v\d+|最终版|新版|备份", path.stem):
                    self.issue("governance", path, "versioned active guidance; update the stable document and retain versions only as dated evidence")

    def memory(self) -> None:
        memory = self.root / "07_知识库与Skills/05_项目记忆系统"
        index = memory / "INDEX.md"
        index_text = self.read(index, "memory")
        self.read(memory / "README.md", "memory")
        linked = self.links(index, index_text, "memory") if index_text else []
        indexed = set(linked)
        if len(linked) != len(indexed):
            self.issue("memory", index, "duplicate link in default memory index")
        indexed_types: dict[Path, str] = {}
        if index_text:
            for line in index_text.splitlines():
                cells = [cell.strip() for cell in line.strip().split("|")]
                if len(cells) < 4 or cells[1] not in MEMORY_TYPES:
                    continue
                for destination in markdown_targets(line):
                    indexed_types[Path(os.path.abspath(index.parent / destination))] = cells[1]
        active = 0
        pending_sources = 0
        total = 0
        entries: dict[str, tuple[Path, dict[str, str]]] = {}
        seen_paths: set[Path] = set()
        for base, dirs, files in os.walk(memory, followlinks=False):
            folder = Path(base)
            depth = len(folder.relative_to(memory).parts)
            for name in dirs[:]:
                child = folder / name
                if reparse(child):
                    self.issue("memory", child, "memory directories must be real directories, not links")
                    dirs.remove(name)
                elif depth >= 2:
                    self.issue("memory", child, "memory tree exceeds two directory levels")
                    dirs.remove(name)
            for name in files:
                path = folder / name
                if name in {"README.md", "INDEX.md"}:
                    continue
                if depth != 2 or path.suffix.lower() != ".md":
                    self.issue("memory", path, "formal memories must be first-level/second-level/file.md")
                    continue
                total += 1
                seen_paths.add(path)
                text = self.read(path, "memory")
                if text is None:
                    continue
                fields, issues = frontmatter(text)
                missing = MEMORY_REQUIRED - set(fields)
                extra = set(fields) - MEMORY_REQUIRED - MEMORY_OPTIONAL
                if missing:
                    issues.append(f"missing required metadata: {', '.join(sorted(missing))}")
                if extra:
                    issues.append(f"unknown metadata: {', '.join(sorted(extra))}")
                for key in MEMORY_REQUIRED - {"tags"}:
                    if not fields.get(key):
                        issues.append(f"empty or missing metadata field: {key}")
                identifier = fields.get("id", "")
                if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", identifier):
                    issues.append("id must be a stable lowercase hyphenated identifier")
                elif identifier in entries:
                    issues.append(f"duplicate memory id; first used by {self.label(entries[identifier][0])}")
                else:
                    entries[identifier] = (path, fields)
                if fields.get("type") not in MEMORY_TYPES:
                    issues.append("invalid memory type")
                if fields.get("status") not in MEMORY_STATES:
                    issues.append("invalid memory status")
                if fields.get("privacy") not in {"internal", "public"}:
                    issues.append("privacy must be internal or public")
                for date_key in ("timestamp", "review_after"):
                    if date_key not in fields:
                        continue
                    try:
                        dt.date.fromisoformat(fields[date_key])
                    except ValueError:
                        issues.append(f"{date_key} must be a valid YYYY-MM-DD date")
                source = fields.get("source", "")
                if source == "pending":
                    pending_sources += 1
                    message = "original source pending; verify the stated scope before use"
                    if fields.get("type") == "Authorization":
                        message = "authorization source pending; verify recipient, action and current scope before external or paid action"
                    self.issue("memory", path, message, warning=True)
                elif source:
                    source_path = Path(source.replace("\\", "/"))
                    if source_path.is_absolute() or ".." in source_path.parts or ":" in source:
                        issues.append("source must be a repository-relative path or pending")
                    elif not (self.root / source_path).exists():
                        issues.append(f"source path missing: {source}")
                for message in issues:
                    self.issue("memory", path, message)
                if fields.get("status") == "active":
                    active += 1
                    if path not in indexed:
                        self.issue("memory", path, "active memory missing from INDEX.md")
                    if indexed_types.get(path) != fields.get("type"):
                        self.issue("memory", index, f"index type differs from memory: {self.label(path)}")
                elif path in indexed:
                    self.issue("memory", path, "non-active memory linked from the default index")
        for path in indexed - seen_paths:
            self.issue("memory", index, f"index target is not a formal memory: {self.label(path)}")
        replacement_graph: dict[str, set[str]] = {}
        for identifier, (path, fields) in entries.items():
            replaced = ids_field(fields.get("supersedes", ""))
            replacement_graph[identifier] = set(replaced)
            for old_id in replaced:
                if old_id == identifier:
                    self.issue("memory", path, "memory cannot supersede itself")
                elif old_id not in entries:
                    self.issue("memory", path, f"supersedes id missing: {old_id}")
                elif entries[old_id][1].get("status") == "active":
                    self.issue("memory", path, f"superseded entry remains active: {old_id}")
        for cycle in required_cycles(replacement_graph):
            self.issue("memory", memory, f"supersedes cycle: {' -> '.join(cycle)}")
        self.counts.update(memory_entries=total, active_memories=active, memory_sources_pending=pending_sources)

    def skills(self) -> None:
        skill_root = self.root / ".agents/skills"
        count = 0
        dependency_graph: dict[str, set[str]] = {}
        if not skill_root.is_dir():
            self.issue("skills", skill_root, "project skills directory missing")
            return
        for folder in sorted(skill_root.iterdir()):
            if not folder.is_dir():
                continue
            path = folder / "SKILL.md"
            if not path.exists() and skill_residue_only(folder):
                self.issue("skills", folder, "retired/incomplete skill residue; not discoverable", warning=True)
                continue
            text = self.read(path, "skills")
            if text is None:
                continue
            count += 1
            dependency_graph[folder.name] = set()
            fields, issues = frontmatter(text)
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", fields.get("name", "")):
                issues.append("skill name must use lowercase letters, digits and hyphens")
            if fields.get("name") != folder.name:
                issues.append("skill name must match its installation directory")
            if not fields.get("description"):
                issues.append("skill description is required")
            for message in issues:
                self.issue("skills", path, message)
            self.links(path, text, "skills")
            self.code_links(path, text, "skills")
            required, _conditional = declared_reads(text)
            for destination in required:
                target = Path(os.path.abspath(path.parent / destination))
                if target.name == "SKILL.md" and target.parent.parent == skill_root:
                    dependency_graph[folder.name].add(target.parent.name)
            for base, dirs, files in os.walk(folder, followlinks=False):
                dirs[:] = [d for d in dirs if d not in PRUNE and not reparse(Path(base) / d)]
                for name in files:
                    reference = Path(base) / name
                    if reference.suffix.lower() == ".md" and reference != path:
                        contents = self.read(reference, "skills")
                        if contents is not None:
                            self.links(reference, contents, "skills")
                            self.code_links(reference, contents, "skills")
        self.counts["mandatory_skill_edges"] = sum(len(edges) for edges in dependency_graph.values())
        for cycle in required_cycles(dependency_graph):
            self.issue("skills", skill_root, f"mandatory skill read cycle: {' -> '.join(cycle)}")
        catalog = self.root / "07_知识库与Skills/03_Skills清单.md"
        catalog_text = self.read(catalog, "skills")
        if catalog_text is not None:
            catalog_links = self.links(catalog, catalog_text, "skills")
            catalog_skills = {path.parent.name for path in catalog_links if path.name == "SKILL.md" and path.parent.parent == skill_root}
            installed_skills = set(dependency_graph)
            for name in sorted(installed_skills - catalog_skills):
                self.issue("skills", catalog, f"project skill absent from catalog: {name}")
            for name in sorted(catalog_skills - installed_skills):
                self.issue("skills", catalog, f"catalog names missing project skill: {name}")
        self.counts["project_skills"] = count

    def active_links(self) -> None:
        paths = [self.root / "README.md", self.root / "AGENTS.md"]
        paths += [self.root / "00_总控台" / name for name in ACTIVE_CONTROL]
        for folder in BUSINESS:
            for filename in ("README.md", "AGENTS.md"):
                path = self.root / folder / filename
                if path.is_file():
                    paths.append(path)
        for path in paths:
            text = self.read(path, "active_links")
            if text is not None:
                self.links(path, text, "active_links")
                self.code_links(path, text, "active_links")
        self.counts["active_entry_documents"] = len(paths)

    def junctions(self) -> None:
        count = 0

        def unavailable_link(path: Path) -> None:
            resolved = path.resolve(strict=False)
            try:
                resolved.relative_to(self.root)
                outside = False
            except ValueError:
                outside = True
            if outside:
                self.issue("junctions", path, "external link target unavailable in this environment; not confirmed broken", warning=True)
            else:
                self.issue("junctions", path, "local link target is missing")

        for base, dirs, files in os.walk(self.root, followlinks=False):
            folder = Path(base)
            depth = len(folder.relative_to(self.root).parts)
            # Broken directory links can be classified as files by os.walk.
            for name in files:
                path = folder / name
                if reparse(path):
                    count += 1
                    if not path.exists():
                        unavailable_link(path)
            for name in dirs[:]:
                path = folder / name
                if reparse(path):
                    count += 1
                    if not path.exists():
                        unavailable_link(path)
                    dirs.remove(name)
                elif name in PRUNE or depth >= 3:
                    dirs.remove(name)
        self.counts["directory_links_checked"] = count

    def git_paths(self) -> None:
        try:
            result = subprocess.run(
                ["git", "ls-files", "--stage", "-z"], cwd=self.root,
                capture_output=True, check=True, timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            self.issue("git", self.root / ".git", "unable to read Git tracked paths")
            return
        count = 0
        nested_cache: dict[Path, bool] = {}
        for record in result.stdout.decode("utf-8", errors="replace").split("\0"):
            if not record:
                continue
            metadata, name = record.split("\t", 1)
            mode = metadata.split(" ", 1)[0]
            path = Path(name)
            parts = {part.lower() for part in path.parts}
            filename = path.name.lower()
            sample = any(word in filename for word in ("example", "template", "sample"))
            reasons = []
            parent = (self.root / name).parent
            if parent not in nested_cache:
                nested_cache[parent] = any(
                    (ancestor / ".git").exists()
                    for ancestor in (parent, *parent.parents)
                    if ancestor != self.root and self.root in ancestor.parents
                )
            if "node_modules" in parts or "browser_data" in parts:
                reasons.append("dependency or browser profile is tracked")
            if mode == "160000" or any(name.startswith(prefix) for prefix in NESTED_ROOTS) or ".git" in parts or nested_cache[parent]:
                reasons.append("nested repository content is tracked by the root repository")
            if path.suffix.lower() in BINARY_SUFFIXES:
                reasons.append("binary/media deliverable is tracked")
            if not sample and (
                filename == ".env" or filename.startswith(".env.")
                or bool(parts & {"credentials", "secrets", ".ssh"})
                or filename in {"credentials.json", "credentials.toml", "token.json", "tokens.json", "cookies.json", "auth.json", "alibaba-openapi.json"}
                or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}
            ):
                reasons.append("credential-like filename is tracked; contents were not read")
            if "__pycache__" in parts or name.startswith(("99_临时区/", "_codex_work/")):
                reasons.append("temporary runtime content is tracked")
            for message in reasons:
                self.issue("git", self.root / name, message)
            count += 1
        self.counts["git_tracked_entries"] = count

    def run(self) -> dict:
        for check in (self.root_entries, self.governance, self.memory, self.skills, self.active_links, self.junctions, self.git_paths):
            try:
                check()
            except OSError:
                self.issue(check.__name__, self.root, "filesystem check failed; no file contents were printed")
        return {
            "ok": not self.errors, "root": str(self.root), "counts": self.counts,
            "errors": self.errors, "warnings": self.warnings,
            "scope": "Read-only structural checks: active and inline-code paths, skill catalog and declared mandatory edges, memory IDs, scope presence, source paths, replacement and index, shallow link targets, and Git filenames. No semantic judgment, agent behavior replay, historical payload or secret-body scan.",
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--json", action="store_true", help="print the complete structured report")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    report = WorkspaceCheck(args.root).run()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        status = "PASS" if report["ok"] else "FAIL"
        print(f"{status}: {len(report['errors'])} error(s), {len(report['warnings'])} warning(s)")
        print("; ".join(f"{key}={value}" for key, value in report["counts"].items()))
        for severity, entries in (("ERROR", report["errors"]), ("WARN", report["warnings"])):
            for item in entries[:15]:
                print(f"{severity} [{item['check']}] {item['path']}: {item['message']}")
            if len(entries) > 15:
                print(f"... {len(entries) - 15} more {severity.lower()} items; use --json for all paths")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
