"""Read normalized multi-channel observations without pooling incompatible outcomes."""
from datetime import date
from decimal import Decimal, InvalidOperation

from .strategy import platform_id, PLATFORMS

def snapshot(ws, metrics_path=None):
    from .runtime import fail
    if not metrics_path:
        return dict(slices=[], figures={"impressions": None, "clicks": None, "qualified_inquiries": None, "orders": None, "spend": None, "revenue": None},
                    limitations=["No actual operating-data source selected; unknown figures are null", "No cross-platform total or ROI inferred"], source=None)
    data = ws.json(metrics_path)
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("slices"), list):
        fail("INVALID_METRICS", "normalized JSON needs schema_version:1 and slices[]")
    result, seen = [], set()
    for row in data["slices"]:
        if not isinstance(row, dict):
            fail("INVALID_METRICS", "slice must be an object")
        required = {"id", "platform", "placement", "entity_id", "business_model", "period_start", "period_end", "timezone", "currency", "attribution", "metrics"}
        if set(row) != required or any(not isinstance(row[k], str) or not row[k].strip() for k in required - {"metrics"}):
            fail("INVALID_METRICS", "slice dimensions and metric fields must be explicit")
        platform = platform_id(row["platform"])
        if not platform or row["placement"] not in PLATFORMS[platform]["placements"] or row["business_model"] not in PLATFORMS[platform]["business_models"]:
            fail("INVALID_METRICS", "unknown platform/placement/business model")
        try:
            if date.fromisoformat(row["period_start"]) > date.fromisoformat(row["period_end"]):
                raise ValueError("reversed window")
        except ValueError:
            fail("INVALID_METRICS", "invalid measurement period")
        identity = (platform, row["placement"], row["entity_id"], row["business_model"], row["period_start"], row["period_end"], row["timezone"], row["currency"])
        if identity in seen or any(s["id"] == row["id"] for s in result):
            fail("OVERLAPPING_METRICS", "duplicate slice/row; cannot prove disjoint measurements")
        seen.add(identity)
        if not isinstance(row["metrics"], dict):
            fail("INVALID_METRICS", "metrics must be an object of observed values or null")
        metrics = {}
        for key, value in row["metrics"].items():
            if value is None:
                metrics[key] = None
                continue
            if type(value) not in (int, float, str):
                fail("INVALID_METRICS", "metric values must be numbers or null")
            try:
                number = Decimal(str(value))
                if not number.is_finite() or number < 0:
                    raise ValueError("invalid metric")
            except (InvalidOperation, ValueError):
                fail("INVALID_METRICS", "non-finite/negative metric")
            metrics[key] = str(number)
        def ratio(n, d):
            num, den = metrics.get(n), metrics.get(d)
            return str((Decimal(num) / Decimal(den)).quantize(Decimal("0.0001"))) if num is not None and den is not None and Decimal(den) > 0 else None
        linked = row["attribution"] == "click_linked"
        derived = {"ctr": ratio("clicks", "impressions")}
        if row["business_model"] == "b2b":
            derived.update(click_to_qualified_rate=ratio("qualified_inquiries", "clicks") if linked else None,
                           cost_per_qualified=ratio("spend", "qualified_inquiries") if linked else None)
        elif row["business_model"] == "retail":
            derived.update(click_to_order_rate=ratio("orders", "clicks") if linked else None,
                           cost_per_order=ratio("spend", "orders") if linked else None)
        result.append({**row, "platform": platform, "metrics": metrics, "derived": derived,
                       "interpretation": "Imported observations; source authenticity and causal conclusions are not established by parsing"})
    return dict(slices=result, source=ws.reference(metrics_path), pooled_totals=None,
                limitations=["Cross-platform/surface/period/currency/entity outcomes remain separate", "Unknown attribution yields null conversion/cost ratios"],
                next_actions=[dict(slice_id=r["id"], evidence_gap="Define missing metrics and qualified outcomes", hypothesis="Select one factor using the channel/creative plan; do not infer a cause from this snapshot") for r in result])
