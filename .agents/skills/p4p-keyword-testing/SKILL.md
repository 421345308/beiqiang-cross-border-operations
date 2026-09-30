---
name: p4p-keyword-testing
description: Plan and review small-budget Alibaba.com P4P keyword tests for verified Beiqiang products. Use for test-product selection, intent groups, budgets, pause rules, metrics and post-test actions.
---

# P4P Keyword Testing

## Required reads

- Read [workspace boundaries](../../../AGENTS.md), [Alibaba entry](../../../02_Alibaba运营/AGENTS.md), and dated account-mode/report evidence for the target plan.

Use this skill to create controlled P4P tests that identify useful keywords without wasting budget on weak listings.

## 适用场景

- Plan the first small-budget Alibaba P4P test after store launch.
- Select a test size the budget and listing quality can support; do not impose a fixed product count.
- Diagnose P4P results by impressions, clicks, CTR, inquiries, spend, and inquiry quality.
- Decide which keywords to pause, keep, increase, or move into organic title/detail optimization.

## 输入要求

Required:

- Product code, product title, product group, current first image, detail-page status.
- Candidate keywords and product direction.
- Daily/weekly budget range and target market if known.

Recommended after launch:

- Keyword impressions, clicks, CTR, average CPC, spend, inquiries, inquiry rate, RFQ/inquiry quality, buyer countries.

## 测试原则

- Test only products that are not obvious duplicate-risk pages.
- Prioritize products with complete title, first image, attributes, detail page, and inquiry CTA.
- Group keywords by intent: core product terms, long-tail scenario terms, and B2B/OEM terms.
- Start with small daily budgets and short cycles, then optimize from data.
- Identify whether the target is standard keyword advertising, full-site smart promotion or another mode. Check actual controls, report grain, attribution, currency/timezone and any active contract or lock before proposing a keyword, time or geography change. The 2026-09-15 historical smart-plan case is not a current control map.
- Distinguish bid keywords from buyer search terms. Candidate terms need source/date/market, exact SKU relevance, buyer intent and validation status. Long-tail cost or conversion advantage is a hypothesis, not a guarantee; there is no universal Top5/50% split or fixed click threshold.
- Draft budget, bid, pause and scale changes with a risk cap and review condition; do not execute them without task authorization. Correct confirmed wrong category or misleading claims immediately; compare reasonable alternatives only when a controlled test can separate them.

## 输出格式

Return:

```text
P4P test goal:
Products selected:
Products excluded:
Keyword groups:
Budget and schedule:
Bid logic:
Pause rules:
Scale rules:
Tracking table:
After-test actions:
Risk notes:
ChatGPT handoff:
```

Tracking table fields:

```text
Date | Product | Keyword | Match type | Impressions | Clicks | CTR | Avg CPC | Spend | Inquiries | Inquiry rate | Buyer quality | Action
```

## 贝强业务规则

- P4P should validate buyer intent and keyword quality, not cover up weak product pages.
- Select product and keyword claims supported by each SKU's evidence and sourcing status; do not treat wide-toe, knit, EVA or OEM/ODM as default product attributes.
- Ask for or mark missing MOQ, price range, sample, lead time, and packing data before pushing aggressive conversion language.

## 禁止事项

- Do not run P4P on pages with poor main image, missing detail page, unresolved duplicate risk, or misleading title.
- Do not promise final FOB price from the ad test.
- Do not continue spending on high-impression/no-click or click/no-inquiry keywords without a fix.
- Do not use medical/orthopedic terms unless the product and platform rules support them.
