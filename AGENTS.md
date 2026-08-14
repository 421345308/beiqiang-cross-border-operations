# Beiqiang Cross-Border Operations System

This workspace is the operating system for Quanzhou Beiqiang Footwear & Apparel Co., Ltd. Use it for Alibaba.com product operations, competitor research, RFQ conversion, TikTok B2B content, and weekly review.

## Business Positioning

- Company: footwear factory supplier in Quanzhou, Fujian, China.
- Core products: wide toe box comfort walking shoes, casual walking shoes, lightweight slip-on shoes, breathable knit/textile shoes, related casual footwear.
- Business model: OEM/ODM and wholesale supply.
- Target buyers: importers, wholesalers, Amazon/TikTok sellers, sourcing agents, and brand/private-label buyers.
- Target markets: United States and Europe.
- Price logic: FOB `8-12 USD/pair` is the target commercial band, but final quote depends on style, quantity, material, size ratio, packing, and order requirements.

All outputs must be B2B-facing. Avoid retail-consumer copy, unsupported medical claims, fake certificates, invented factory capacity, or unconfirmed price promises.

## Skill Map

Use these Skills as a layered system:

1. `beiqiang-positioning`
   - Purpose: positioning guardrail for every Beiqiang task.
   - Use before writing listings, RFQ replies, TikTok scripts, competitor conclusions, or weekly actions.

2. `competitor-research-firecrawl`
   - Purpose: structured competitor research with Firecrawl MCP.
   - Use for extracting competitor titles, price/MOQ text, selling points, materials, image angles, detail-page modules, and market gaps.

3. `alibaba-product-optimizer`
   - Purpose: optimize one Alibaba.com product page.
   - Use for titles, keywords, product groups, attributes, main images, detail pages, selling points, and inquiry hooks.
   - Pair with existing `alibaba-international-operations` for Alibaba platform rules and existing Beiqiang product-package knowledge.

4. `rfq-quote-assistant`
   - Purpose: Alibaba RFQ quote and buyer follow-up.
   - Use for FOB range replies, sample discussion, MOQ questions, OEM/ODM messages, and follow-up sequences.

5. `inquiry-follow-up`
   - Purpose: inquiry and WhatsApp follow-up.
   - Use for sample-order pushes, no-reply buyer follow-ups, quotation reminders, and next-step buyer qualification.

6. `image-brief-generator`
   - Purpose: Alibaba image brief and AI prompt generation.
   - Use for main images, detail images, shipping images, OEM/ODM images, factory images, quality-check images, and wide toe box comparison visuals.

7. `shipping-trade-terms`
   - Purpose: trade terms and logistics copy.
   - Use for EXW, FOB, FCA, DDP, air, sea, express, Amazon FBA, sample shipping, and buyer-safe logistics explanations.

8. `tiktok-b2b-content`
   - Purpose: short-video scripts for sourcing buyers.
   - Use for factory proof, product proof, wide toe box demos, packing/checking content, and Alibaba inquiry CTAs.

9. `weekly-data-review`
   - Purpose: turn weekly data into specific next actions.
   - Use for exposure/click/CTR/inquiry diagnosis, RFQ performance, product-page priorities, keyword actions, and content planning.

Existing Skill:

- `alibaba-international-operations`
  - Current role: mature Alibaba.com listing workflow and Beiqiang product package knowledge.
  - Keep using it for Alibaba product upload SOP, image/detail-page rules, platform traffic logic, field filling, customs cautions, and post-publish optimization.

## Default Workflow

For a new product:

1. Use `beiqiang-positioning`.
2. Inspect the raw product package and existing Beiqiang facts.
3. Use `competitor-research-firecrawl` if buyer intent, title terms, image strategy, or differentiation is unclear.
4. Use `alibaba-product-optimizer` plus `alibaba-international-operations` to produce title, keywords, attributes, image plan, detail-page plan, and confirmations.
5. Use `rfq-quote-assistant` to prepare inquiry reply language.
6. Use `inquiry-follow-up` for no-reply buyers, sample pushes, WhatsApp follow-up, and quote reminders.
7. Use `image-brief-generator` when images need a clear design brief or AI prompt.
8. Use `shipping-trade-terms` for EXW/FOB/DDP/FBA logistics wording.
9. Use `tiktok-b2b-content` to turn the product angle into B2B factory content.
10. Use `weekly-data-review` after publishing to decide the next optimization.

## Firecrawl MCP Integration

Firecrawl MCP is used only for competitor and market research, not for inventing Beiqiang facts.

Recommended local MCP config example:

- `08_工具链/04_MCP与Workctl/mcp/firecrawl-mcp.example.json`
- `08_工具链/04_MCP与Workctl/mcp/firecrawl-codex-config.example.toml`
- `08_工具链/04_MCP与Workctl/mcp/FIRECRAWL_MCP_SETUP.md`

Expected Firecrawl tools:

- Search: find competitor pages when URLs are unknown.
- Map: discover URLs from one site or storefront.
- Scrape: read one known page.
- Batch scrape: read multiple known product URLs.
- Extract: return structured JSON for product title, price, MOQ, features, materials, image strategy, and gaps.
- Agent: handle broader research when exact URLs are unknown.

When Firecrawl is unavailable in the current Codex session, say so, then use available browsing/search tools if allowed and keep the same structured output schema from `competitor-research-firecrawl`.

## Output Standards

Alibaba-ready outputs must include:

- B2B buyer intent.
- Keyword cluster.
- Title options.
- Attributes and selling points.
- Main image roles.
- Detail-page modules.
- Inquiry or RFQ hook.
- Pending confirmations.

RFQ outputs must include:

- Buyer intent summary.
- English reply.
- Follow-up.
- Missing quote data.
- Internal risk note.

Weekly review outputs must include:

- Scorecard.
- Top wins and problems.
- Product-page actions.
- Keyword/content actions.
- RFQ actions.
- Next-week task list with expected metric impact.

## Evidence Rules

Use real product photos, Beiqiang references, user confirmations, or competitor observations as evidence. Mark uncertain facts clearly. Ask for confirmation before finalizing high-impact details such as material, outsole, lining, size range, price, MOQ, packing, certificates, and lead time.

## Technical Development Inquiry Gate

When a buyer asks for controlled hardness, foam density, rebound, compression set, stack height, drop, last dimensions, new tooling, outsole formulation, laboratory tests, NDA, or a confidential tech pack, classify the inquiry as `Technical Development Buyer` and use `07_知识库与Skills/01_运营SOP/技术型品牌买家询盘评估SOP.md` before quoting.

Always separate:

- `Buyer Target`: what the buyer wants; never present it as an existing Beiqiang capability.
- `Confirmed Capability`: supported by a physical sample, document, or supplier confirmation.
- `Fixed / Not Adjustable`: existing mold, structure, formulation, or hardness that cannot be changed.
- `Actual Result After Sampling`: data that only exists after a finished sample is produced; do not guarantee it will match the buyer target.

Reference images, components, complete physical samples, internal measurements, and formal test reports are different readiness levels. Never describe a reference sole or concept as a tested finished shoe. Do not create a Trade Assurance sample order until the sample purpose, deliverables, acceptance criteria, and exclusions are written clearly.
