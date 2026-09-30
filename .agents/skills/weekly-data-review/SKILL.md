---
name: weekly-data-review
description: Turn dated Alibaba.com and B2B channel metrics into Beiqiang's next weekly actions. Use for exposure, clicks, inquiries, buyer quality, RFQ and content results; keep unsupported SKU claims out of recommendations.
---

# Weekly Data Review

Use this skill to convert weekly operation data into next actions. The review should be operational, specific, and tied to Beiqiang's B2B buyer positioning.

## Required References

- Read `references/review-template.md` for a complete weekly scorecard; a single metric or narrow diagnosis needs only its source rows.
- Load a narrower skill only when the review actually includes that action: product editing, competitor verification, RFQ wording or TikTok content. Keep the default review focused on the supplied metrics and source dates.

## Review Logic

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
