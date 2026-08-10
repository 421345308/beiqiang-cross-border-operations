# Firecrawl MCP Setup For Codex

This file is an integration note. Do not store a Firecrawl API key in the project.

## What This MCP Is For

Use Firecrawl MCP for public competitor research:

- Search public web pages.
- Scrape public product pages.
- Extract structured product data with a JSON schema.
- Compare Alibaba, brand, wholesale, Amazon, or TikTok Shop public signals.

Do not use it for login-only, CAPTCHA, paywalled, private, or high-frequency crawling.

## Environment Variable

Set the API key in the local user environment:

```powershell
[Environment]::SetEnvironmentVariable("FIRECRAWL_API_KEY", "your_api_key_here", "User")
```

Restart Codex after setting it.

## Codex Config Location

Use the user-level Codex config:

```text
C:\Users\spq\.codex\config.toml
```

Add this block:

```toml
[mcp_servers.firecrawl]
command = "npx"
args = ["-y", "firecrawl-mcp"]
startup_timeout_sec = 60
tool_timeout_sec = 120
env_vars = ["FIRECRAWL_API_KEY"]
```

This forwards the local environment variable without writing the API key into the config file.

## Verification

1. Restart Codex.
2. Start a new Codex thread in the Beiqiang workspace.
3. Ask: `List available MCP tools for Firecrawl`.
4. Expected result: tools such as `firecrawl_search`, `firecrawl_scrape`, `firecrawl_batch_scrape`, `firecrawl_extract`, or `firecrawl_agent` should be available.
5. Run a small public-page test before a real research batch.

## Beiqiang Competitor Research Test

Use `competitor-research-firecrawl` with this task:

```text
Use Firecrawl to research public competitor pages for "Wide Toe Box Walking Shoes" targeting US/EU B2B buyers. Extract URL, brand/company, product positioning, title keywords, core selling points, price/MOQ text, target customer, image/detail-page angle, and Beiqiang differentiation suggestions. Use only public pages, limit to 5-8 relevant results, and do not copy competitor wording.
```
