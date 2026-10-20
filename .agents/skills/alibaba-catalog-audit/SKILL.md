---
name: alibaba-catalog-audit
description: Audit Beiqiang Alibaba.com product identity, images, SKU bindings, detail pages, URLs and conversion issues for the requested current catalog scope. A full-store audit covers the current catalog rather than a historical product count; it does not automatically block unrelated work.
---

# Alibaba Catalog Audit

## Required reads

- Read the [Alibaba entry](../../../02_Alibaba运营/AGENTS.md), exact product/source evidence and applicable [lifecycle SOP](../../../02_Alibaba运营/00_运营SOP/国际站商品全生命周期SOP.md) gates. Reuse unchanged context already read. Current identity and supplier relationships come from the product center, not historical audit counts.

## Scope and evidence

Establish whether the user requested a full store, one family, a batch, one field or a promotion-readiness review. A full-store audit first obtains the complete current catalog and reconciles IDs; a narrow task stays narrow. Missing evidence is unknown rather than a low invented score.

Keep source identity, local drafts, official fields/review, buyer-visible content and business results separate. Label offline reviews as local preparation. For performance data retain the reporting window, timezone, currency, channel, unit, buyer deduplication and attribution; do not combine incompatible organic/ad/RFQ slices.

## Review

- Resolve physical product, source article/version, current Beiqiang model and each platform ID before evaluating presentation. A/B/C and historical aliases do not create new physical products.
- Check requested content and its actual dependencies: title/category/attributes; image identity, roles and readability; SKU color/size bindings; details/video; commercial fields; buyer contact path. Current thresholds and single-product exceptions live only in the SOP.
- For HTML/AI detail types inspect actual rendered content or the buyer page; empty structured image arrays alone do not establish missing details. Distinguish officially stored content from delayed or failed public rendering.
- Compare siblings using source identity, original IDs, actual product/variant facts, buyer intent, image overlap and performance. A changed title/color/order alone is weak differentiation. Recommend canonical optimization, evidence-supported distinct pages, merge review or pause review; an audit does not itself authorize hiding/deleting products.
- For each material issue state the observation, competing explanation, next discriminating check and smallest useful correction. Actual scores aid diagnosis; scores and page completeness do not prove supply, demand or purchase progress.

## Risk scope and output

Apply lifecycle SOP §9 to the affected object, linked fields, shared assets or genuinely shop-wide risk. Do not make one unresolved product a blanket gate on every authorized task. Explain the actual propagation path when broader work must stop.

Report scope/coverage, evidence dates, material findings, recommended action and unresolved facts. A full audit may use a product/family table and promotion tiers; a single-field check needs only its finding. Use an optional scoring rubric only when useful to compare adequately observed products, identify it as an internal heuristic, and do not substitute it for official requirements or buyer results. Prices, MOQ, sample and lead-time conditions come from current SKU evidence and SOP, not a second commercial-default table here.
