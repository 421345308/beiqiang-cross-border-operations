# Firecrawl MCP Setup For Codex

This file is an integration note. Do not store a Firecrawl API key in the project.

## Verified local route (2026-10-28)

The current Codex configuration does not load a Firecrawl MCP server, and the app plugin inventory reports Firecrawl as not installed. The existing local `FIRECRAWL_API_KEY` is nevertheless valid: the official credit-usage endpoint returned HTTP 200, and public Alibaba, trade-record and buyer pages were successfully scraped through the official API. Missing session tools do not mean missing credits or an unavailable account.

For this environment, use the existing key directly with the [official API](https://docs.firecrawl.dev/api-reference/endpoint/scrape): `GET https://api.firecrawl.dev/v2/team/credit-usage` checks the account; `POST https://api.firecrawl.dev/v2/scrape` accepts a public URL and `formats: ["markdown"]`. Pass the key only in the Authorization header from the environment. Keep TLS verification enabled and save source URL, collection time and response status with the business evidence. Do not send customer emails or private CRM data as scrape inputs.

Do not install another integration or restart active sessions just to use this working route. The optional MCP setup below applies when persistent MCP tools are wanted; quota resets do not install or reload an MCP server. A successful request also does not prove every target page is accessible or every source claim is true.

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
