---
name: p4p-keyword-testing
description: Build small-budget Alibaba.com P4P keyword testing plans for Beiqiang products. Use when selecting test products, keyword groups, daily budgets, bid logic, negative/pause rules, metric tracking, and post-test actions for wide toe box comfort walking shoes and related casual footwear.
---

# P4P Keyword Testing

Use this skill to create controlled P4P tests that identify useful keywords without wasting budget on weak listings.

## 适用场景

- Plan the first small-budget Alibaba P4P test after store launch.
- Select 3-5 products and keyword clusters for testing.
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
- Good first candidates should fit Beiqiang's wide toe box, comfort walking, slip-on, breathable knit, lightweight, or OEM/ODM positioning.
- Ask for or mark missing MOQ, price range, sample, lead time, and packing data before pushing aggressive conversion language.

## 禁止事项

- Do not run P4P on pages with poor main image, missing detail page, unresolved duplicate risk, or misleading title.
- Do not promise final FOB price from the ad test.
- Do not continue spending on high-impression/no-click or click/no-inquiry keywords without a fix.
- Do not use medical/orthopedic terms unless the product and platform rules support them.
