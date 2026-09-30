---
name: alibaba-product-optimizer
description: Analyze or revise requested fields on one Beiqiang Alibaba.com product. Use for a title-only draft, keywords, attributes, images, details or a complete page review; preserve the requested scope. Publishing and API changes belong to separate execution skills.
---

# Alibaba Product Optimizer

货源身份、外采可供能力和 `HOLD_SOURCE` 的现行判断只读根 `AGENTS.md` 与单款证据；本 Skill 不维护第二份货源规则。

Use this skill for one SKU or existing product link. A title-only draft is not a full-page rebuild, catalog audit, competitor study or publishing operation. Other skill links below are conditional routes, not automatic calls or authorization.

## Inputs and stop conditions

Identify the exact SKU/product ID, requested fields, existing value when editing a live link, current SKU evidence and any relevant user choice. For a title, inspect the present title and the product facts the new wording would claim; check current attributes/main image only where needed to avoid contradiction. If the real shoe/source or a proposed high-impact claim lacks evidence, stop that claim and report the missing fact. Do not turn a draft into a published change.

## Adaptive optimization rule

Separate `HARD_CONSTRAINT` from `DEFAULT_HEURISTIC`. Source identity, SKU facts, compliance and publish/readback gates remain fixed. Title formulas, keyword placement, image order, module count beyond platform requirements, visual style and historical conversion advice are hypotheses. If fresh keyword data, current buyer intent, current platform behavior or a protected-link pilot supports a better approach, use it and record why. Read the adaptive-learning reference in `alibaba-international-operations` when a conflict is material.

## Required reads

- Apply the already loaded [workspace boundaries](../../../AGENTS.md) and [Alibaba entry](../../../02_Alibaba运营/AGENTS.md); reuse unchanged material from this task.
- Locate the applicable parts of the [product lifecycle SOP](../../../02_Alibaba运营/00_运营SOP/国际站商品全生命周期SOP.md). For a title draft, its fact priority and title/claim rules in sections 1 and 3 suffice; live publishing and full-page work require their own gates.
- Read the exact SKU's source evidence and, for an existing link, the current field value. The product master routes to evidence; it does not prove current stock or platform state.

## Conditional reads

- For a complete page pass, use the [optimization checklist](references/optimization-checklist.md); select only its title section for title uncertainty.
- For an unresolved buyer promise or positioning choice, use the [positioning card](../beiqiang-positioning/references/positioning-card.md). Reading a rule does not restart a full positioning workflow.
- For material keyword uncertainty that current SKU/platform data cannot settle, consider [competitor research](../competitor-research-firecrawl/SKILL.md). External wording never supplies Beiqiang product facts.
- For coordinated listing preparation or repair, use [Alibaba operations](../alibaba-international-operations/SKILL.md). For an authorized API write/readback, use [OpenAPI operator](../alibaba-openapi-operator/SKILL.md).

## Method

1. Freeze the requested scope and target link. Classify proposed claims as verified SKU fact, confirmed commercial condition or drafting hypothesis.
2. For a title, choose a recognizable product/category term and only supported differentiators. Current keyword evidence and buyer clarity decide wording; fixed formulas and character targets are heuristics. Avoid stuffing and unsupported medical, waterproof, leather, certification or brand terms.
3. For HR replacement titles, apply lifecycle SOP §3's current batch exception and fact boundaries; do not infer its details for another batch. Keep internal supplier and procurement paths out of buyer-facing copy.
4. Check the changed field against relevant existing product facts. A full page task additionally aligns attributes, gallery, details and inquiry content, then uses the checklist. Do not create another listing without a supported product role and duplicate-risk review.
5. For keyword work, separate ad targeting terms, observed buyer queries and research candidates. Record each candidate's source/date/market, intent, exact SKU support and validation state; do not invent volume or infer that long-tail always wins. Match the proposed title to the page's actual ability to answer that query.

## Output and completion

For a title-only task, return the proposed title and brief evidence for its product terms, plus only blocking or material pending confirmations. Offer alternatives only when they represent useful buyer-intent choices. Do not append an image plan, full attributes, FAQ, quotation or publication receipt.

For a complete optimization, return the requested page package and its evidence gaps. Claims about wide toe room, own-factory supply, material, sample, MOQ, packing and lead time need the exact SKU's evidence or confirmation. Completion means the draft matches the verified SKU and requested scope; it does not imply platform submission, approval, inventory accuracy or public-page acceptance.
