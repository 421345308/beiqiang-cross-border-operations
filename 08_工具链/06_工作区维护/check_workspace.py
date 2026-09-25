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
    ".workbuddy", "outputs",
}
MEMORY_FIELDS = {"type", "title", "description", "status", "privacy", "tags", "timestamp"}
MEMORY_TYPES = {"Identity", "Principle", "Preference", "Context", "Skill", "Experience", "Learning"}
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

    def root_entries(self) -> None:
        for path in self.root.iterdir():
            if path.name not in ROOT_ALLOWED:
                self.issue("root", path, "unexpected root entry; place it in the matching business directory")
        for name in BUSINESS + (".agents", ".git", "AGENTS.md", "README.md", ".gitignore", "skills-lock.json"):
            if not (self.root / name).exists():
                self.issue("root", self.root / name, "required workspace entry missing")

    def memory(self) -> None:
        memory = self.root / "07_知识库与Skills/05_项目记忆系统"
        index = memory / "INDEX.md"
        index_text = self.read(index, "memory")
        self.read(memory / "README.md", "memory")
        indexed = set(self.links(index, index_text, "memory") if index_text else [])
        active = 0
        total = 0
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
                text = self.read(path, "memory")
                if text is None:
                    continue
                fields, issues = frontmatter(text)
                if set(fields) != MEMORY_FIELDS:
                    issues.append("formal memory must have exactly the seven required metadata fields")
                for key in MEMORY_FIELDS - {"tags"}:
                    if not fields.get(key):
                        issues.append(f"empty or missing metadata field: {key}")
                if fields.get("type") not in MEMORY_TYPES:
                    issues.append("invalid memory type")
                if fields.get("status") not in {"active", "archived"}:
                    issues.append("status must be active or archived")
                if fields.get("privacy") not in {"internal", "public"}:
                    issues.append("privacy must be internal or public")
                try:
                    dt.date.fromisoformat(fields.get("timestamp", ""))
                except ValueError:
                    issues.append("timestamp must be a valid YYYY-MM-DD date")
                for message in issues:
                    self.issue("memory", path, message)
                if fields.get("status") == "active":
                    active += 1
                    if path not in indexed:
                        self.issue("memory", path, "active memory missing from INDEX.md")
                elif path in indexed:
                    self.issue("memory", path, "archived memory is linked from the default index", warning=True)
        self.counts.update(memory_entries=total, active_memories=active)

    def skills(self) -> None:
        skill_root = self.root / ".agents/skills"
        count = 0
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
            for base, dirs, files in os.walk(folder, followlinks=False):
                dirs[:] = [d for d in dirs if d not in PRUNE and not reparse(Path(base) / d)]
                for name in files:
                    reference = Path(base) / name
                    if reference.suffix.lower() == ".md" and reference != path:
                        contents = self.read(reference, "skills")
                        if contents is not None:
                            self.links(reference, contents, "skills")
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
        self.counts["active_entry_documents"] = len(paths)

    def junctions(self) -> None:
        count = 0
        for base, dirs, files in os.walk(self.root, followlinks=False):
            folder = Path(base)
            depth = len(folder.relative_to(self.root).parts)
            # Broken directory links can be classified as files by os.walk.
            for name in files:
                path = folder / name
                if reparse(path):
                    count += 1
                    if not path.exists():
                        self.issue("junctions", path, "link target is missing or unavailable")
            for name in dirs[:]:
                path = folder / name
                if reparse(path):
                    count += 1
                    if not path.exists():
                        self.issue("junctions", path, "directory link target is missing or unavailable")
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
        for check in (self.root_entries, self.memory, self.skills, self.active_links, self.junctions, self.git_paths):
            try:
                check()
            except OSError:
                self.issue(check.__name__, self.root, "filesystem check failed; no file contents were printed")
        return {
            "ok": not self.errors, "root": str(self.root), "counts": self.counts,
            "errors": self.errors, "warnings": self.warnings,
            "scope": "Read-only: active governance links, local skill links, memory structure, directory links through depth 4, and Git filenames. Historical records and secret contents are not scanned.",
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
