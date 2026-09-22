---
name: alibaba-30-products-audit
description: Audit Beiqiang Alibaba.com products before further listing or promotion. Use when reviewing the current full catalog (including 30, 40, or more products), validating product identity, main images, SKU bindings, detail pages, URLs and live state, scoring conversion quality, or deciding which products should be promoted, paused, merged, or fixed.
---

# Alibaba Full Catalog Audit

## Beiqiang product provenance gate (2026-09-08)

负责人于2026-09-08确认：只有原始数据包中的商品属于贝强自有工厂货。阿里巴巴国际站扩品可能没有实际存在的商品；已上线、API回读、图片、生成素材、热榜或竞品记录均不能证明产品实物存在、自有工厂生产或可供货。必须逐款关联原始数据包；没有匹配证据的扩品标记为 HOLD_SOURCE（实物与货源待核验），不得称为自有工厂货、计入已确认供给或承诺样品/库存/交期。外部商品经后续核实可以记录真实来源，但不自动成为自有工厂货；归属变化须由负责人明确确认。


Use this skill for Beiqiang's pre-launch or pre-promotion Alibaba.com product audit. Treat the audit as an operating decision tool, not a generic listing review.

Before publishing additional products, run a blocking integrity audit of every current live product. A catalog with unresolved identity, image, SKU, detail-page, or URL errors is not ready for expansion.

## 适用场景

- Review all current Beiqiang Alibaba.com products before official store launch.
- Score product pages, local upload folders, exported backend rows, or product URLs.
- Identify main products, potential products, supplemental products, duplicate-risk products, and products not suitable for promotion.
- Decide first-week optimization, P4P testing candidates, and products needing merge or pause.

## 输入要求

Prefer these inputs:

- Product code/model, product URL, title, category, product group, attributes, keywords, selling points.
- Main image files or screenshots, first 5 gallery images, detail page screenshots or local detail images.
- Video availability, SKU/color images, MOQ/sample/lead-time/packing fields when available.
- Alibaba backend data when available: impressions, clicks, CTR, visitors, inquiries, inquiry rate, P4P spend, keyword rows, RFQ leads.
- Live readback where available: productId, title, Model Number, main-image count, SKU/color-image bindings, product detail count, company-image count, productDescType, URL scan, copy, trunk, and public page.

If backend data is missing, label the result as `本地资料预审`, not final performance audit.

## 发布完整性门槛

For every live item, block further publishing until these pass:

- Title and Model Number match the current SKU and source model.
- Six main images belong to the same product and contain no Chinese promotion, domestic watermark, third-party mark, or AI-altered shoe structure.
- SKU color count, size count, total combinations, and color-image bindings are internally consistent.
- Use the workspace's sole authoritative SOP, `02_Alibaba运营/00_运营SOP/国际站商品全生命周期SOP.md`, for live publishing thresholds. The current structured-detail baseline is at least 4 product images that clearly cover the product, plus 5 audited company images; do not retain duplicate or irrelevant images merely to reach 6. For `productDescType=5`, verify AI/HTML page content or the public buyer page instead of treating empty structured arrays as missing.
- No `skill.accio.com`, local path, expiring OSS URL, nested URL, or malformed non-Alibaba image address.
- Copy, trunk, and public page agree. Copy correct plus trunk old is pending, not complete.

Quality score alone cannot pass this gate.

## 同货号多链接审计

Do not count links as independent products merely because their titles, M1 colors or image order differ. Group the catalog first by verified factory article number and physical shoe structure, then compare sibling links on:

- M1 color and composition.
- Exact and near-duplicate overlap in M2-M6.
- Product-detail image overlap.
- SKU color/size matrix, attributes and commercial fields.
- Whether each page answers a genuinely different procurement need with different evidenced content.

Use these decisions:

- `OPTIMIZE_CANONICAL`: retain the strongest existing link and improve its M1 color plus full six-image sequence.
- `KEEP_DISTINCT`: retain siblings only when real product facts and page content support distinct buyer needs.
- `MERGE_REVIEW`: same product facts with mainly title/color/image presentation differences; compare performance before consolidation.
- `PAUSE_REVIEW`: redundant weak sibling with no independent traffic or conversion evidence.

Flag `5/6 shared main images + all product-detail images shared` as high-confidence presentation-only expansion even when titles and keywords are unique. Do not automatically remove or hide products during an audit; provide the family evidence and recommended action first.

## 评分表

Score each product out of 100:

- Title quality: 10
- Category and attributes: 10
- First image click potential: 15
- First 5 gallery image system: 15
- Video and dynamic proof: 10
- Detail page conversion: 15
- Keyword coverage: 10
- Duplicate listing risk: 10
- Inquiry guidance: 5

Use evidence in the product folder, screenshots, or backend export. Do not invent a score for unavailable evidence; mark it as pending or give a conservative low score.

## 产品分层

- A 主推款: clear verified differentiation, strong images, complete live integrity, and suitability for P4P test. Wide-toe positioning is optional and SKU-specific.
- B 潜力款: product is useful but title/images/detail page need optimization.
- C 补充款: can enrich the shop but should not receive ad budget now.
- D 重复风险款: too similar to other products; merge, adjust, or weaken.
- E 暂不推广款: weak positioning, weak assets, poor conversion value, or missing key evidence.

## 输出格式

Return:

```text
Audit scope:
Evidence used:
Product score table:
Product tier table:
Main promote candidates:
Pause or merge candidates:
P4P test candidates:
Top duplicate risks:
High-priority fixes:
Missing data:
Today action list:
ChatGPT handoff:
```

For each product row include: product code, model, group, score, tier, biggest problem, priority action, P4P suitability, duplicate risk, missing confirmations.

## 贝强业务规则

- Keep Beiqiang positioned as a Quanzhou footwear factory supplier for US/EU importers, wholesalers, Amazon/TikTok sellers, sourcing agents, and brand/private-label buyers.
- Prefer real product differences: shoe type, outsole, upper, toe width, closure, buyer scenario, season, size range, OEM/ODM service.
- Prioritize exposure, click-through, inquiry conversion, and repeatable buyer trust.
- Use FOB 8-12 USD/pair only as target commercial logic, subject to style, quantity, material, size ratio, packing, and order requirements.

## 禁止事项

- Do not suggest blind mass listing or duplicate listing just to increase product count.
- Do not treat color-only or title-only variants as strong separate products.
- Do not invent price, MOQ, material, outsole, lining, certificates, lead time, capacity, or medical claims.
- Do not mark a product as P4P-ready if first image, title, detail page, or duplicate risk is unresolved.
