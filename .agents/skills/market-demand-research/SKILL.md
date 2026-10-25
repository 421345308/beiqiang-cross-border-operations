---
name: market-demand-research
description: Research footwear demand and product priorities for Beiqiang using Google Trends, search queries, scoped sales evidence, channel results and verified supply. Use for product selection, website catalog expansion, search-content planning or deciding which directions merit promotion; distinguish search interest from sales and channel-specific buying intent.
---

# Market Demand Research

## Required reads

- Read the relevant sections of [demand evidence and expansion method](../../../06_市场研究/需求证据与扩品方法.md), then dated evidence for the specific decision.
- For SKU selection, consult the existing product-center identities and source records. Read global current status only when prioritizing across businesses; a narrow keyword question does not require a workspace-wide review.

Use this skill to judge what Beiqiang should push next with evidence from multiple data sources. Separate B2B supplier signals from retail demand language.

## 适用场景

- Decide which Beiqiang product directions are worth focus after launch.
- Compare relevant evidenced product directions without imposing a permanent comfort, wide-toe or medical positioning.
- Turn demand and supply findings into actions for the requested website, marketplace or social channel.

## 输入要求

Use any available data:

- Google Trends: dated queries/topics, market, period, category, search type, normalization and related queries. Zero is not zero demand; independently normalized charts cannot establish relative market size.
- Search Console: this site's visibility and queries, not total market demand. Keyword tools: estimates with source, location and date, not observed sales.
- Retailer sales reports or disclosed transactions: exact market, period, product/brand scope and denominator. Brand revenue, merchandising lists and reviews are different evidence types.
- Alibaba backend export: exposure, clicks, CTR, visitors, inquiries, inquiry rate, P4P spend, keyword rows, RFQ demand.
- Firecrawl research: Alibaba public competitor pages, brand sites, wholesale sites, review articles, public search results.
- Optional Apify output: Amazon/TikTok/public e-commerce trend rows when available and allowed.
- TikTok Creative Center or manual observation notes: hooks, scenes, claims, buyer questions.

When a source is missing, mark it as missing. Do not pretend the model is data-backed.

## 判断模型

Rate each direction by:

- Demand evidence: comparable search-interest trends, scoped sales observations, backend exposure/click/inquiry and RFQ signals. Keep retail/social attention separate from purchase evidence. Search-result density, supplier counts and Sooxie popularity are not demand volume or sales.
- Competition strength: supplier count, title similarity, price pressure, content saturation.
- Beiqiang fit: verified supply route, exact product evidence, media readiness, applicable commercial conditions and confirmed customization scope. External supply is valid when supported; it does not become own-factory manufacturing.
- Conversion path: the requested channel's buyer journey, exact product/page and meaningful next action. Do not require an Alibaba CTA for website or social work.
- Explain the basis for priority; do not invent numerical scores or causal explanations from proxy metrics.

## 输出格式

For a full direction study, return the following; a narrow question needs only the relevant conclusion, sources and limits:

```text
Research scope:
Sources used:
Missing sources:
Evidence and opportunity table:
Priority conclusion:
Product actions:
Keyword actions:
Image/detail-page actions:
Requested-channel actions:
```

Evidence table fields:

```text
产品方向 | 来源与统计范围 | 直接观察 | 推断及替代解释 | 对应产品与供货 | 缺口 | 下一动作
```

## 贝强业务规则

- Treat Alibaba supplier pages as B2B supply evidence.
- Treat Amazon, Walmart, TikTok, and review articles as demand language, not as Beiqiang proof.
- Favor directions supported by a real, verified supply route and B2B buyer demand. Wide-toe is one possible evidenced direction, not a store-wide positioning.
- Turn findings into operational choices: improve current products first, then decide whether new products are needed.
- For website expansion, reconcile existing product IDs, live catalog and excluded drafts before searching for more shoes. Re-evaluate historical holds against current evidence; neither an old hold nor an Alibaba listing is a permanent publication verdict. Do not add an unrequested physical-sample or exact-stock gate to otherwise evidenced sourcing.

## 禁止事项

- Do not call a direction a bestseller or market-wide trend unless the source supports that exact claim. A missing-data disclaimer does not license an unsupported conclusion.
- Do not copy competitor wording into Beiqiang listings.
- Do not use unsupported medical, orthopedic, waterproof, safety, or compliance claims.
- Do not recommend high ad spend before title/image/detail quality and duplicate risk are checked.

## 完整任务记录入口

研究结果写回现有主题或产品对象，保留需求源、观察日期、信号类型、与实款的异同和未知项。成熟证据复用并记录适用性，只补决策缺口；没有搜索量/竞争数据的机会记为假设。若进入Alibaba完整单款执行，再使用[该渠道采集模板](../../../02_Alibaba运营/05_扩品工程/工厂店外新款数据采集模板.md)的B/G字段；网站和社媒无需为此另建Alibaba任务包。

Alibaba拟售路线和完整任务包按其生命周期SOP；网站选款和搜索内容按网站SOP。不要把某渠道图数、报价或发布规则复制成跨渠道门槛。研究本身不授权采购、外发或付费投放；已有用户授权按原对象和范围继续有效。
