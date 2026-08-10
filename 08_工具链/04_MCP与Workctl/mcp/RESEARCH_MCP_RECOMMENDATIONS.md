# Research MCP Recommendations

Use this note to choose web-research MCP tools for Beiqiang operations. Do not store API keys in this file.

## Recommended Stack

### 1. Firecrawl MCP

Primary use: public competitor page scraping, crawling, structured extraction, and page-to-markdown conversion.

Best for Beiqiang:

- Alibaba/brand/wholesale product page extraction.
- Product title, price/MOQ text, materials, selling points, image angles, and detail-page modules.
- Turning known URLs into structured competitor tables.

Keep as the default first choice for product-page research.

### 2. Exa MCP

Primary use: AI-native web search and semantic discovery.

Best for Beiqiang:

- Finding relevant competitor pages when exact URLs are unknown.
- Discovering niche product angles such as wide toe box walking shoes, comfort shoes, barefoot-style walking shoes, and Amazon/TikTok seller trends.
- Company or brand research before deeper extraction.

Use with Firecrawl: Exa finds good URLs; Firecrawl extracts structured page data.

### 3. Tavily MCP

Primary use: general AI-agent search, extraction, crawl, and research workflows.

Best for Beiqiang:

- Fast broad research across many public sources.
- Getting concise source-backed market summaries.
- Comparing market trend signals before selecting pages for Firecrawl extraction.

Use when the question is broader than one product page.

### 4. Brave Search MCP

Primary use: independent web search, news/images/video/local search, and source discovery.

Best for Beiqiang:

- Fresh public web search.
- Finding additional sources outside normal SEO-heavy results.
- Cross-checking search results from another provider.

Use with Firecrawl: Brave finds sources; Firecrawl extracts product-page details.

### 5. Apify MCP

Primary use: running ready-made scraping actors for specialized platforms.

Best for Beiqiang:

- Marketplace or social/public data workflows that need a maintained actor.
- Structured e-commerce scraping when a suitable public actor exists.
- Larger-scale workflows after the operating process is stable.

Use carefully. Follow each target site's terms and avoid login-only, CAPTCHA, paywalled, or private data.

## Practical Recommendation For Beiqiang

Start with Firecrawl only. Add Exa or Tavily later if discovery quality is weak. Add Brave Search for independent search coverage. Add Apify only when a specific marketplace or social data workflow needs a dedicated actor.

## Safe Research Rule

Only research public pages, keep batches small, and do not copy competitor wording directly into Beiqiang buyer-facing copy.
