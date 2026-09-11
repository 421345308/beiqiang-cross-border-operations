# Firecrawl Competitor Research Workflow

Use Firecrawl to collect structured market evidence before optimizing Beiqiang listings, keywords, RFQ angles, or TikTok B2B content.

## MCP Setup Assumption

Firecrawl MCP is expected to expose tools such as:

- `firecrawl_search`
- `firecrawl_scrape`
- `firecrawl_batch_scrape`
- `firecrawl_map`
- `firecrawl_extract`
- `firecrawl_agent`
- status-check tools for async batch or agent jobs

If the tools are not available in the current Codex session, keep the same schema and use available search/browsing tools manually. State that Firecrawl MCP is not active.

## Research Inputs

Ask for or infer:

- Product type: wide toe box walking shoes, knit slip-on shoes, winter walking shoes, canvas casual shoes, etc.
- Target market: US, Europe, or both.
- Buyer type: importer, wholesaler, Amazon/TikTok seller, brand buyer.
- Platform scope: Alibaba only, retail marketplaces, brand sites, TikTok/Amazon signals, or mixed.
- Evidence goal: keywords, titles, price/MOQ, image strategy, selling points, detail-page modules, content angles.

## Search Query Seeds

Use combinations such as:

```text
wide toe box walking shoes wholesale supplier
wide toe box walking shoes Alibaba manufacturer
breathable knit slip on walking shoes OEM
comfort walking shoes EVA sole wholesale
lightweight slip on walking shoes factory
wide toe box shoes Amazon comfort walking
TikTok wide toe box walking shoes comfort
```

Add product-specific terms such as `winter`, `fleece lined`, `canvas`, `mesh`, `men`, `women`, `EU 36-46`, or `private label` only when relevant.

## Tool Flow

1. Use `firecrawl_search` for broad discovery when URLs are unknown.
2. Use `firecrawl_map` for one supplier site, Alibaba storefront, or brand site when many product URLs may exist.
3. Use `firecrawl_scrape` for a single page when exact URL is known.
4. Use `firecrawl_batch_scrape` for 5-12 known product URLs.
5. Use `firecrawl_extract` when structured JSON is needed from product pages.
6. Use `firecrawl_agent` for open-ended research across multiple sources, then poll its status tool until complete.

## Extraction Schema

Use this schema or a task-specific subset with `firecrawl_extract`.

```json
{
  "type": "object",
  "properties": {
    "research_scope": {
      "type": "object",
      "properties": {
        "platform": { "type": "string" },
        "keyword": { "type": "string" },
        "target_market": { "type": "string" },
        "buyer_type": { "type": "string" }
      }
    },
    "products": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "source_url": { "type": "string" },
          "platform": { "type": "string" },
          "supplier_or_brand": { "type": "string" },
          "product_title": { "type": "string" },
          "price_text": { "type": "string" },
          "moq_text": { "type": "string" },
          "target_buyer_signal": { "type": "string" },
          "core_keywords": {
            "type": "array",
            "items": { "type": "string" }
          },
          "materials": {
            "type": "object",
            "properties": {
              "upper": { "type": "string" },
              "outsole": { "type": "string" },
              "lining": { "type": "string" }
            }
          },
          "features": {
            "type": "array",
            "items": { "type": "string" }
          },
          "wide_toe_box_signal": { "type": "string" },
          "image_strategy": {
            "type": "array",
            "items": { "type": "string" }
          },
          "detail_page_modules": {
            "type": "array",
            "items": { "type": "string" }
          },
          "customization_signals": {
            "type": "array",
            "items": { "type": "string" }
          },
          "buyer_questions_answered": {
            "type": "array",
            "items": { "type": "string" }
          },
          "gaps_or_risks": {
            "type": "array",
            "items": { "type": "string" }
          }
        },
        "required": ["source_url", "product_title"]
      }
    }
  },
  "required": ["products"]
}
```

## Extract Prompt

Use a prompt like:

```text
Extract B2B product research data for walking shoe supplier comparison. Focus on product title, price text, MOQ, buyer positioning, materials, wide toe box or comfort signals, features, image strategy, detail-page modules, customization claims, and gaps. Do not rewrite marketing copy. Return only structured data matching the schema.
```

## Analysis Rules

- Separate verified page facts from inference.
- Treat retail price and retail review language as demand signals, not Alibaba quote guidance.
- Mark unsupported competitor claims instead of repeating them.
- Convert findings into Beiqiang actions: title terms, image roles, detail modules, RFQ proof, TikTok hooks, or weekly optimization tasks.
