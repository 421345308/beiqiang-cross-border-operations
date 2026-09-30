---
name: weekly-data-review
description: Turn dated Alibaba.com and B2B channel metrics into Beiqiang's next weekly actions. Use for exposure, clicks, inquiries, buyer quality, RFQ and content results; keep unsupported SKU claims out of recommendations.
---

# Weekly Data Review

## Required reads

- Read dated metric sources and the [current status](../../../00_总控台/当前状态.md). Full-scorecard references below are conditional.

Use this skill to convert weekly operation data into next actions. The review should be operational, specific, and tied to Beiqiang's B2B buyer positioning.

## Required References

- Read `references/review-template.md` for a complete weekly scorecard; a single metric or narrow diagnosis needs only its source rows.
- Load a narrower skill only when the review actually includes that action: product editing, competitor verification, RFQ wording or TikTok content. Keep the default review focused on the supplied metrics and source dates.

## Review Logic

Before diagnosing, state coverage dates, report timezone, currency, product/family/link ID, channel, metric unit, deduplication and attribution. Missing is not zero. Do not add organic, recommendation, ads, RFQ and visitor marketing rows or different product/search-term dimensions without a common definition. The read-only [funnel aggregator](../../../08_工具链/06_工作区维护/funnel_metrics.py) rejects incompatible slices and calculates weighted CTR/CPC; valid-inquiry rates require buyer-level deduplication and click attribution.

Write each finding as observation → competing explanations → best-supported cause → discriminating check → smallest correction → expected direction and failure signal. Zero exposure requires checking time, publish/review state, visibility, category, duplicate/compliance risk, matching demand and plan state before changing a title. Low CTR needs intent/placement/device/region and visible offer review; low inquiry needs traffic quality, product proof, terms and contact path. Small samples and zero inquiries support risk control, not a claim that the page lost a test. Record what is missing separately from evidence against a hypothesis.

Diagnose in this order:

1. Exposure: keyword coverage, product count, duplicate risk, ranking, and platform quality.
2. Clicks and CTR: first image, title relevance, price band, product type match.
3. Inquiries: detail-page proof, MOQ/sample clarity, buyer trust, RFQ reply speed.
4. Inquiry quality: buyer type, market, quantity, repeat questions, price mismatch.
5. Follow-up: quote completeness, second-touch timing, sample conversion.

## 适用场景

- Weekly Alibaba.com operation review, product-page performance review, keyword review, inquiry quality review, RFQ follow-up review, TikTok content review, and next-week action planning.

## 贝强业务规则

- Diagnose data through Beiqiang's B2B buyer funnel: exposure, click, inquiry, quote, sample, bulk-order discussion.
- Prioritize verified product positioning, Alibaba product quality, inquiry conversion and buyer trust. Wide-toe positioning applies only to evidenced SKUs.
- Tie every recommendation to a measurable next action.

## 输出格式

For a complete weekly review, use the following fields and give next-week actions an owner, due date and expected metric impact. A single-metric question or narrow update needs only the relevant analysis:

```text
Week:
Scorecard:
Top wins:
Top problems:
Product actions:
Keyword actions:
RFQ/follow-up actions:
TikTok actions:
Competitor checks:
Next-week task table:
Facts to confirm:
```

## 禁止事项

- Do not give vague advice without product, keyword, buyer, or metric linkage.
- Do not optimize only for exposure while ignoring inquiry quality.
- Do not assume P4P spending is the fix before checking titles, images, detail pages, and RFQ replies.
