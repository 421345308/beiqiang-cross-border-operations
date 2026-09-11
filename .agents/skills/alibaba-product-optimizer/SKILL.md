---
name: alibaba-product-optimizer
description: Optimize a single Beiqiang Alibaba.com product listing for B2B search traffic, click-through, and inquiry conversion. Use when improving product titles, keywords, product groups, attributes, selling points, main images, detail-page modules, SKU/color images, inquiry hooks, and post-publish actions for wide toe box comfort walking shoes and related casual footwear.
---

# Alibaba Product Optimizer

## Beiqiang product provenance gate (2026-09-08)

负责人于2026-09-08确认：只有原始数据包中的商品属于贝强自有工厂货。阿里巴巴国际站扩品可能没有实际存在的商品；已上线、API回读、图片、生成素材、热榜或竞品记录均不能证明产品实物存在、自有工厂生产或可供货。必须逐款关联原始数据包；没有匹配证据的扩品标记为 HOLD_SOURCE（实物与货源待核验），不得称为自有工厂货、计入已确认供给或承诺样品/库存/交期。外部商品经后续核实可以记录真实来源，但不自动成为自有工厂货；归属变化须由负责人明确确认。


Use this skill when the task is one Beiqiang Alibaba product page or one product package. It wraps Beiqiang positioning, competitor signals, and the existing Alibaba International Operations workflow into a focused optimization pass.

## Required References

- Read `references/optimization-checklist.md` for the single-page optimization workflow.
- Use `beiqiang-positioning` before writing buyer-facing copy.
- Use `alibaba-international-operations` for Alibaba page rules, image rules, attribute patterns, and the existing Beiqiang product package knowledge.
- Use `competitor-research-firecrawl` first when the product type, keywords, image plan, or differentiation is uncertain.

## Output Contract

For a complete single-product optimization, return content in a form the operator can paste into Alibaba.com. For a narrow revision, return only the changed fields and relevant evidence or confirmations:

- Product group and duplicate-risk note.
- 3 title options with buyer intent notes.
- 3-5 keyword phrases.
- Required, optional, and custom attributes.
- 4-6 selling points.
- Main image roles, including first-image click-through logic.
- Detail-page module order.
- RFQ/inquiry hook for the page.
- Pending confirmations for price, MOQ, material, lining, outsole, size range, packing, certificates, or lead time.

## Quality Gate

Approve the page only if the title, attributes, images, details and inquiry hook agree on the verified product, actual source and confirmed order support for overseas B2B buyers. Wide toe room, own-factory supply and material claims require the exact SKU's evidence; they are not default quality criteria.

## 适用场景

- Optimize one Beiqiang Alibaba.com product listing or one product package.
- Generate or revise title, keywords, attributes, selling points, main image plan, detail-page plan, SKU/color plan, inquiry hook, and post-publish action.

## 贝强业务规则

- Start from Beiqiang positioning and real product evidence.
- Keep the page B2B: importer, wholesaler, Amazon/TikTok seller, brand buyer.
- Highlight wide toe box, comfort walking, knit/textile upper, EVA sole, lightweight, slip-on, sample, OEM/ODM, mixed sizes/colors only when true or supported.
- Treat price, MOQ, material, lining, outsole, size range, packing, and lead time as confirmation items when missing.

## 输出格式

Use this checklist for a complete optimization package; do not append unrelated sections to a small edit:

```text
Product:
Buyer intent:
Title options:
Keywords:
Attributes:
Selling points:
Main image plan:
First 5 image plan:
Detail page structure:
MOQ/sample/lead time:
Shipping note:
Inquiry hook:
Pending confirmations:
```

## 禁止事项

- Do not create duplicate-looking listings without a clear product role.
- Do not stuff titles with repeated terms.
- Do not use unsupported medical, waterproof, leather, certification, or brand claims.
- Do not let images contradict attributes or title.
