#!/usr/bin/env python3
"""Read-only aggregation of one comparable funnel slice. Input is dated CSV, never platform writes.

Required columns: row_id, period_start, period_end, timezone, currency, channel,
plan_mode, scope_id, impressions, clicks, spend, qualified_inquiries, attribution.
qualified_inquiries may be blank when the buyer-level deduplicated count is unavailable.
attribution is click_linked or unknown. Callers must filter to one comparable slice;
this tool refuses cross-channel/currency/timezone/plan/scope/period addition.
"""

import argparse
import csv
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

FIELDS = (
    "row_id", "period_start", "period_end", "timezone", "currency", "channel",
    "plan_mode", "scope_id", "impressions", "clicks", "spend", "qualified_inquiries", "attribution",
)
DIMENSIONS = ("period_start", "period_end", "timezone", "currency", "channel", "plan_mode", "scope_id")


def aggregate(rows: list[dict[str, str]]) -> dict[str, str | int | None]:
    if not rows:
        raise ValueError("no rows")
    seen: set[str] = set()
    baseline: tuple[str, ...] | None = None
    totals = {"impressions": 0, "clicks": 0, "spend": Decimal(0), "qualified_inquiries": 0}
    inquiry_known = True
    attribution_known = True
    for row in rows:
        missing = [field for field in FIELDS if field not in row]
        if missing:
            raise ValueError(f"missing fields: {', '.join(missing)}")
        if not row["row_id"].strip() or row["row_id"] in seen:
            raise ValueError("blank or duplicate row_id; cannot prove disjoint rows")
        seen.add(row["row_id"])
        dims = tuple(row[field].strip() for field in DIMENSIONS)
        if not all(dims):
            raise ValueError("blank period/timezone/currency/channel/plan/scope")
        if baseline is None:
            baseline = dims
        elif dims != baseline:
            raise ValueError("incompatible period/timezone/currency/channel/plan/scope")
        try:
            impressions = int(row["impressions"])
            clicks = int(row["clicks"])
            spend = Decimal(row["spend"])
            inquiries = int(row["qualified_inquiries"]) if row["qualified_inquiries"].strip() else None
        except (ValueError, InvalidOperation) as error:
            raise ValueError("invalid or missing metric") from error
        if min(impressions, clicks, spend) < 0 or clicks > impressions or (inquiries is not None and inquiries < 0):
            raise ValueError("negative metric or clicks exceed impressions")
        totals["impressions"] += impressions
        totals["clicks"] += clicks
        totals["spend"] += spend
        if inquiries is None:
            inquiry_known = False
        else:
            totals["qualified_inquiries"] += inquiries
        if row["attribution"] != "click_linked":
            attribution_known = False
    clicks = totals["clicks"]
    inquiries = totals["qualified_inquiries"] if inquiry_known else None
    linked = attribution_known and inquiries is not None
    ratio = lambda num, den: str((num / den).quantize(Decimal("0.0001"))) if den else None
    return {
        **dict(zip(DIMENSIONS, baseline)), "rows": len(rows),
        "impressions": totals["impressions"], "clicks": clicks, "spend": str(totals["spend"]),
        "qualified_inquiries": inquiries, "ctr": ratio(Decimal(clicks), totals["impressions"]),
        "average_cpc": ratio(totals["spend"], clicks),
        "click_to_qualified_rate": ratio(Decimal(inquiries), clicks) if linked else None,
        "cost_per_qualified": ratio(totals["spend"], inquiries) if linked else None,
        "attribution_status": "click_linked" if linked else "not_comparable",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path)
    args = parser.parse_args()
    with args.csv_file.open(encoding="utf-8-sig", newline="") as stream:
        result = aggregate(list(csv.DictReader(stream)))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
