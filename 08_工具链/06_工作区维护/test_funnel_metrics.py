"""Synthetic fixtures only; these numbers are not Beiqiang operating data."""

import unittest
from funnel_metrics import aggregate


def row(**changes):
    result = dict(row_id="synthetic-1", period_start="2026-09-01", period_end="2026-09-07",
                  timezone="PST", currency="CNY", channel="ads", plan_mode="smart",
                  scope_id="synthetic-plan", impressions="100", clicks="4", spend="8.00",
                  qualified_inquiries="0", attribution="click_linked")
    result.update(changes)
    return result


class FunnelFixture(unittest.TestCase):
    def test_weighted_rates_and_zero_denominator(self):
        result = aggregate([row(), row(row_id="synthetic-2", impressions="10", clicks="1", spend="2.00", qualified_inquiries="1")])
        self.assertEqual(result["ctr"], "0.0455")
        self.assertEqual(result["average_cpc"], "2.0000")
        self.assertEqual(result["click_to_qualified_rate"], "0.2000")
        self.assertEqual(result["cost_per_qualified"], "10.0000")
        zero = aggregate([row(impressions="0", clicks="0", spend="0", qualified_inquiries="0")])
        self.assertIsNone(zero["ctr"])
        self.assertIsNone(zero["cost_per_qualified"])
        spent_without_inquiry = aggregate([row(spend="8.00", qualified_inquiries="0")])
        self.assertEqual(spent_without_inquiry["spend"], "8.00")
        self.assertIsNone(spent_without_inquiry["cost_per_qualified"])

    def test_missing_and_unattributed_inquiries_are_not_zero(self):
        self.assertIsNone(aggregate([row(qualified_inquiries="")])["qualified_inquiries"])
        self.assertIsNone(aggregate([row(attribution="unknown", qualified_inquiries="1")])["cost_per_qualified"])

    def test_incompatible_dimensions_duplicates_and_fields(self):
        for change in ({"currency": "USD"}, {"timezone": "UTC"}, {"channel": "organic"},
                       {"plan_mode": "keyword"}, {"scope_id": "other"}, {"period_end": "2026-09-08"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                aggregate([row(), row(row_id="synthetic-2", **change)])
        with self.assertRaises(ValueError):
            aggregate([row(), row()])
        with self.assertRaises(ValueError):
            aggregate([{"row_id": "synthetic-1"}])


if __name__ == "__main__":
    unittest.main()
