"""Small, isolated fixtures for the read-only governance checker."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from check_workspace import WorkspaceCheck, declared_reads, literal_paths, required_cycles


def memory_text(identifier: str, status: str = "active", extra: str = "") -> str:
    return (
        "---\n"
        f"id: {identifier}\n"
        "type: Preference\n"
        "title: Fixture preference\n"
        "description: Fixture only\n"
        f"status: {status}\n"
        "scope: fixture task only\n"
        "source: evidence.md\n"
        "privacy: internal\n"
        "tags: [fixture]\n"
        "timestamp: 2026-08-27\n"
        f"{extra}"
        "---\n\n# Fixture\n"
    )


class MemoryFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.memory = self.root / "07_知识库与Skills/05_项目记忆系统"
        self.folder = self.memory / "preferences/collaboration"
        self.folder.mkdir(parents=True)
        (self.root / "evidence.md").write_text("source", encoding="utf-8")
        (self.memory / "README.md").write_text("# Protocol", encoding="utf-8")

    def entry(self, filename: str, body: str, indexed: bool = True) -> None:
        (self.folder / filename).write_text(body, encoding="utf-8")
        if indexed:
            index = self.memory / "INDEX.md"
            prior = index.read_text(encoding="utf-8") if index.exists() else "# Index\n"
            index.write_text(prior + f"| Preference | fixture | [entry](preferences/collaboration/{filename}) |\n", encoding="utf-8")

    def check(self) -> WorkspaceCheck:
        checker = WorkspaceCheck(self.root)
        checker.memory()
        return checker

    def test_valid_entry_and_relative_index(self) -> None:
        self.entry("one.md", memory_text("one"))
        checker = self.check()
        self.assertEqual(checker.errors, [])
        self.assertEqual(checker.counts["active_memories"], 1)

    def test_duplicate_id_and_bad_source(self) -> None:
        self.entry("one.md", memory_text("same"))
        self.entry("two.md", memory_text("same").replace("source: evidence.md", "source: missing.md"))
        messages = "\n".join(item["message"] for item in self.check().errors)
        self.assertIn("duplicate memory id", messages)
        self.assertIn("source path missing", messages)

    def test_replacement_and_default_index(self) -> None:
        self.entry("new.md", memory_text("new", extra="supersedes: old\n"))
        self.entry("old.md", memory_text("old", "superseded"), indexed=False)
        self.assertEqual(self.check().errors, [])
        # A historical entry must not remain in the default index.
        index = self.memory / "INDEX.md"
        index.write_text(index.read_text(encoding="utf-8") + "| Preference | old | [old](preferences/collaboration/old.md) |\n", encoding="utf-8")
        messages = "\n".join(item["message"] for item in self.check().errors)
        self.assertIn("non-active memory linked", messages)

    def test_missing_and_active_replacement_fail(self) -> None:
        self.entry("new.md", memory_text("new", extra="supersedes: old, missing\n"))
        self.entry("old.md", memory_text("old"))
        messages = "\n".join(item["message"] for item in self.check().errors)
        self.assertIn("superseded entry remains active", messages)
        self.assertIn("supersedes id missing", messages)

    def test_index_type_mismatch_and_disputed_exclusion(self) -> None:
        self.entry("one.md", memory_text("one"))
        self.entry("old.md", memory_text("old", "disputed"), indexed=False)
        index = self.memory / "INDEX.md"
        index.write_text(index.read_text(encoding="utf-8").replace("| Preference |", "| Experience |"), encoding="utf-8")
        messages = "\n".join(item["message"] for item in self.check().errors)
        self.assertIn("index type differs", messages)
        self.assertNotIn("old.md", messages)


class SkillFixture(unittest.TestCase):
    def test_required_cycle_but_conditional_links_do_not_count(self) -> None:
        a = "## Required reads\n- [b](../b/SKILL.md)\n"
        b = "## Conditional reads\n- [a](../a/SKILL.md)\n"
        self.assertEqual(len(declared_reads(a)[0]), 1)
        self.assertEqual(declared_reads(b)[0], [])
        self.assertEqual(required_cycles({"a": {"b"}, "b": set()}), [])
        self.assertTrue(required_cycles({"a": {"b"}, "b": {"a"}}))

    def test_literal_path_ignores_placeholder(self) -> None:
        paths = literal_paths("Use `references/check.md`; write to `99_临时区/<任务>/`; see `E:/assets/file.md`.")
        self.assertEqual(paths, ["references/check.md"])

    def test_inline_code_path_is_checked(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = root / "AGENTS.md"
            doc.write_text("Read `00_总控台/missing.md`.", encoding="utf-8")
            checker = WorkspaceCheck(root)
            checker.code_links(doc, doc.read_text(encoding="utf-8"), "fixture")
            self.assertTrue(any("missing inline-code path" in item["message"] for item in checker.errors))

    def test_absent_local_mount_warns_but_broken_child_fails(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = root / "AGENTS.md"
            content = "Read `01_产品资产/01_原始数据包/sample.jpg`."
            checker = WorkspaceCheck(root)
            checker.code_links(doc, content, "fixture")
            self.assertEqual(checker.errors, [])
            self.assertTrue(any("local ignored entry unavailable" in item["message"] for item in checker.warnings))
            (root / "01_产品资产").mkdir()
            checker = WorkspaceCheck(root)
            checker.code_links(doc, content, "fixture")
            self.assertEqual(checker.errors, [])
            (root / "01_产品资产/01_原始数据包").mkdir()
            checker = WorkspaceCheck(root)
            checker.code_links(doc, content, "fixture")
            self.assertTrue(any("missing inline-code path" in item["message"] for item in checker.errors))

    def test_catalog_link_is_relative_to_catalog(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = root / ".agents/skills/demo/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("---\nname: demo\ndescription: fixture\n---\n# Demo\n", encoding="utf-8")
            catalog = root / "07_知识库与Skills/03_Skills清单.md"
            catalog.parent.mkdir(parents=True)
            catalog.write_text("[demo](../.agents/skills/demo/SKILL.md)", encoding="utf-8")
            checker = WorkspaceCheck(root)
            checker.skills()
            self.assertEqual(checker.errors, [])
            catalog.write_text("[demo](./.agents/skills/demo/SKILL.md)", encoding="utf-8")
            checker = WorkspaceCheck(root)
            checker.skills()
            self.assertTrue(any("missing local link" in item["message"] for item in checker.errors))


if __name__ == "__main__":
    unittest.main()
