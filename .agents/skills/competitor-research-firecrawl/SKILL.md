---
name: competitor-research-firecrawl
description: Firecrawl-based competitor research workflow for Beiqiang cross-border shoe operations. Use when researching Alibaba.com, Amazon, TikTok Shop, wholesale, brand, or marketplace competitors; extracting product titles, prices, MOQ, selling points, materials, image angles, keywords, buyer positioning, and gaps; or producing structured competitor tables for Beiqiang wide toe box comfort walking shoes and related casual footwear.
---

# Competitor Research Firecrawl

Use this skill to turn competitor pages into structured sourcing intelligence for Beiqiang. The goal is not to copy competitors; it is to identify buyer intent, keyword clusters, proof points, image roles, and gaps Beiqiang can answer credibly.

## Required References

- Read `references/firecrawl-workflow.md` before using Firecrawl or designing a competitor research run.
- Read `references/competitor-output-template.md` before returning research results.
- Use `beiqiang-positioning` to filter recommendations through Beiqiang's B2B factory positioning.

## Tool Selection

When Firecrawl MCP is available:

- Use `firecrawl_search` or `firecrawl_agent` when exact competitor URLs are unknown.
- Use `firecrawl_map` when exploring one competitor site or storefront.
- Use `firecrawl_scrape` for one known page.
- Use `firecrawl_batch_scrape` when known URLs are ready.
- Use `firecrawl_extract` with the schema in `references/firecrawl-workflow.md` when the task needs product titles, prices, MOQ, materials, selling points, and page structure as JSON.

When Firecrawl MCP is not available, state that limitation briefly, use available browsing/search tools if permitted, and keep the same extraction schema manually.

## Research Standard

Prefer 5-12 relevant competitor products per task. Separate Alibaba supplier competitors from retail marketplace signals because Alibaba pages reveal B2B supply expectations while Amazon/TikTok pages reveal end-customer demand language.

Always return:

- Competitor product table.
- Keyword and title patterns.
- Image/detail-page observations.
- Buyer pain points and proof gaps.
- Beiqiang action recommendations for Alibaba listing, RFQ, or content.

Do not copy competitor wording verbatim into Beiqiang buyer-facing copy.

## 适用场景

- Competitor research for Alibaba.com, Amazon, TikTok Shop, wholesale sites, brand sites, and public marketplace pages.
- Structured extraction of competitor title keywords, price/MOQ text, materials, selling points, image roles, detail-page modules, and buyer positioning.
- Keyword planning, product-page optimization, RFQ angle discovery, TikTok B2B content angle discovery, and weekly market review.

## 贝强业务规则

- Use competitor data as market evidence, not as copy to paste.
- Separate Alibaba B2B supplier signals from retail demand signals.
- Filter every recommendation through Beiqiang's wide toe box comfort walking shoe factory positioning.
- Only research public pages. Do not access login-only, CAPTCHA, private, or paywalled pages.

## 输出格式

Return:

```text
Research target:
Sources used:
Competitor table:
Keyword findings:
Image/detail-page findings:
Buyer pain points:
Beiqiang differentiation:
Alibaba actions:
RFQ actions:
TikTok content actions:
Evidence boundary:
```

## 禁止事项

- Do not scrape too many pages at once or high-frequency crawl.
- Do not collect private personal data.
- Do not bypass login, CAPTCHA, robots-style restrictions, or paywalls.
- Do not present competitor claims as Beiqiang facts.
