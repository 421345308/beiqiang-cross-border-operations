import unittest
from pathlib import Path

from audit_workspace_structure import is_wire_record, local_destination


class EvidenceBoundaryTest(unittest.TestCase):
    def test_complete_platform_envelopes_are_local(self):
        for value in (
            {"alibaba_product_get_response": {}},
            {"response": {"alibaba_product_edit_response": {}}},
            {"trace_id": "fixture", "biz_success": True},
            {"param_product_top_schema": "fixture"},
            {"observed_at": "fixture", "response": {}},
        ):
            with self.subTest(value=value):
                self.assertTrue(is_wire_record(value))

    def test_business_summaries_are_not_protocol_records(self):
        for value in (
            {"products": [], "sources": []},
            {"product_id": "fixture", "verification": {"passed": True}},
            {"source_url": "https://example.com", "observed_at": "fixture"},
            [], None,
        ):
            self.assertFalse(is_wire_record(value))

    def test_links_preserve_document_and_workspace_scope(self):
        root = Path.cwd()
        document = root / "domain" / "README.md"
        self.assertEqual(local_destination(document, "../AGENTS.md#scope", root), document.parent / "../AGENTS.md")
        self.assertEqual(local_destination(document, "/AGENTS.md", root), root / "AGENTS.md")
        self.assertIsNone(local_destination(document, "https://example.com/a", root))
        self.assertIsNone(local_destination(document, "#scope", root))


if __name__ == "__main__":
    unittest.main()
