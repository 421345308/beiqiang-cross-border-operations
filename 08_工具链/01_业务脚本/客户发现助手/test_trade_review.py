"""Anonymous checks of evidence gates and existing stop-state preservation."""
import copy
import tempfile
import unittest
from pathlib import Path

from app import Store
from trade_review import WEIGHTS, build, private_path, validate


def fixture():
    url = "https://research.example/about"
    return {"checked_at": "2026-10-26", "leads": [{"company": "Synthetic Research", "website": "https://research.example/", "website_verified": True, "website_source_url": url, "country": "待核", "verification_status": "待核", "next_action": "核采购角色", "sources": [{"url": url, "checked_at": "2026-10-26", "access_level": "public_page", "evidence": "Anonymous test only"}], "score": {key: {"points": 0, "reason": "无证据", "source_urls": []} for key in WEIGHTS}}]}


class Reader:
    def check(self, candidate):
        return {"local_stop": candidate["review"]["state"] == "停止联系"}


class TradeReviewTests(unittest.TestCase):
    def test_positive_score_needs_listed_evidence(self):
        payload = fixture()
        payload["leads"][0]["score"]["product"]["points"] = 10
        with self.assertRaises(ValueError):
            validate(payload)
        payload["leads"][0]["score"]["product"]["source_urls"] = ["https://unlisted.example/"]
        with self.assertRaises(ValueError):
            validate(payload)
        payload["leads"][0]["score"]["product"]["source_urls"] = ["https://research.example/about"]
        self.assertEqual(validate(payload), payload)

    def test_no_invented_website_or_crm_match(self):
        payload = fixture()
        payload["leads"][0]["website"] = ""
        payload["leads"][0]["website_verified"] = False
        reviewed, seeds = build(payload, Reader())
        self.assertEqual(seeds["candidates"], [])
        self.assertEqual(reviewed["leads"][0]["crm"]["match_status"], "缺已核官网未作精确匹配")

    def test_index_only_website_not_imported(self):
        payload = fixture()
        payload["leads"][0]["website_verified"] = False
        reviewed, seeds = build(payload, Reader())
        self.assertFalse(seeds["candidates"])
        payload["leads"][0]["website_verified"] = True
        payload["leads"][0]["sources"][0]["access_level"] = "search_index"
        with self.assertRaises(ValueError):
            build(payload, Reader())
        payload["leads"][0]["sources"][0]["access_level"] = "public_page"
        payload["leads"][0]["website_source_url"] = "https://directory.example/"
        with self.assertRaises(ValueError):
            build(payload, Reader())

    def test_stop_and_evidence_survive_duplicate_import(self):
        payload = fixture()
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory))
            _, seeds = build(payload, Reader())
            self.assertEqual(store.add(seeds["candidates"]), 1)
            candidate_id = store.read()[0]["id"]
            store.review(candidate_id, "停止联系", "Synthetic opt out")
            old = copy.deepcopy(store.read())
            reviewed, seeds = build(payload, Reader(), old)
            self.assertTrue(reviewed["leads"][0]["crm"]["local_stop"])
            self.assertEqual(store.add(seeds["candidates"]), 0)
            self.assertEqual(store.read(), old)

    def test_no_public_output_path(self):
        with self.assertRaises(ValueError):
            private_path(Path(__file__).resolve().parent / "public-leads.json")

    def test_reject_overweight_and_bad_date(self):
        payload = fixture()
        payload["leads"][0]["score"]["bulk"]["points"] = 26
        with self.assertRaises(ValueError):
            validate(payload)
        payload = fixture()
        payload["leads"][0]["sources"][0]["checked_at"] = "unknown"
        with self.assertRaises(ValueError):
            validate(payload)


if __name__ == "__main__":
    unittest.main()
