"""Cost and credential boundary tests; no network requests."""
import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import tokenhub_video_review as review


class ReviewBoundaryTests(unittest.TestCase):
    def endpoint(self, **changes):
        e = dict(EndpointId="kimi-k3", Status="ACTIVE", ChargeType="FREE", PaymentEnabled=False,
                 ChargeDetail=json.dumps({"FreeQuota": {"TotalQuota": 1000000, "UsedQuota": 300000}}))
        e.update(changes)
        return SimpleNamespace(returncode=0, stdout=json.dumps({"ModelEndpointSet": [e], "RequestId": "test"}))

    def check(self, **changes):
        with patch.dict(os.environ, {"APPDATA": "C:/test"}), patch.object(review.subprocess, "run", return_value=self.endpoint(**changes)):
            return review.free_preflight("kimi-k3", True)

    def test_verified_free_endpoint(self):
        self.assertEqual(self.check()["free_remaining_before"], 700000)

    def test_postpaid_enabled_stops(self):
        with self.assertRaises(RuntimeError): self.check(PaymentEnabled=True)

    def test_unknown_payment_status_stops(self):
        with self.assertRaises(RuntimeError): self.check(PaymentEnabled=None)

    def test_paid_endpoint_stops(self):
        with self.assertRaises(RuntimeError): self.check(ChargeType="POSTPAID")

    def test_low_quota_stops(self):
        with self.assertRaises(RuntimeError):
            self.check(ChargeDetail=json.dumps({"FreeQuota": {"TotalQuota": 1000000, "UsedQuota": 900000}}))

    def test_invalid_review_budget_is_rejected(self):
        for value in (True, 3500.5, 0, 10000, "3500"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                review.review_budget({"max_completion_tokens": value})
        with self.assertRaises(ValueError):
            review.review_budget({"reasoning_effort": "unsupported"})

    def test_aborted_or_truncated_answer_is_not_a_review(self):
        for finish in ("abort", "length", "content_filter", None):
            with self.subTest(finish=finish):
                self.assertFalse(review.review_completed("Only an opening paragraph", finish))
        self.assertFalse(review.review_completed("   ", "stop"))
        self.assertTrue(review.review_completed("Finished critique", "stop"))

    def test_reflected_key_and_video_scrubbed(self):
        fake = "test-credential"
        result = review.scrub({"error": fake + " sk-dummy1234567890 data:video/mp4;base64,ABCDEF"}, fake)
        self.assertNotIn(fake, result["error"])
        self.assertNotIn("ABCDEF", result["error"])
        self.assertNotIn("sk-dummy", result["error"])


if __name__ == "__main__": unittest.main()
