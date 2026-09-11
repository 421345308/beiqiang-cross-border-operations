---
name: market-demand-research
description: Research Beiqiang walking shoe market demand and product direction priority using Alibaba backend exports, Firecrawl public competitor research, optional Apify/social signals, TikTok Creative Center observations, and keyword evidence. Use when deciding which product directions are worth promoting, developing, P4P testing, or making content for.
---

# Market Demand Research

Use this skill to judge what Beiqiang should push next with evidence from multiple data sources. Separate B2B supplier signals from retail demand language.

## 适用场景

- Decide which Beiqiang product directions are worth focus after launch.
- Compare wide toe box walking shoes, comfort walking shoes, standing-all-day shoes, nurse shoes, slip-on shoes, lightweight shoes, orthopedic-style shoes, custom logo shoes, senior comfort shoes, and travel walking shoes.
- Turn Alibaba backend data plus public competitor observations into next product, keyword, image, and detail-page actions.

## 输入要求

Use any available data:

- Alibaba backend export: exposure, clicks, CTR, visitors, inquiries, inquiry rate, P4P spend, keyword rows, RFQ demand.
- Firecrawl research: Alibaba public competitor pages, brand sites, wholesale sites, review articles, public search results.
- Optional Apify output: Amazon/TikTok/public e-commerce trend rows when available and allowed.
- TikTok Creative Center or manual observation notes: hooks, scenes, claims, buyer questions.

When a source is missing, mark it as missing. Do not pretend the model is data-backed.

## 判断模型

Rate each direction by:

- Demand signal: search/result density, backend exposure/click/inquiry signal, RFQ signal, retail/social attention.
- Competition strength: supplier count, title similarity, price pressure, content saturation.
- Beiqiang fit: factory supply ability, product evidence, image readiness, FOB 8-12 USD/pair fit, OEM/ODM angle.
- Conversion path: whether the direction can produce a clear Alibaba title, main image, detail proof, and inquiry hook.

## 输出格式

Return:

```text
Research scope:
Sources used:
Missing sources:
Hot direction table:
Priority conclusion:
Product actions:
Keyword actions:
Image/detail-page actions:
P4P implications:
RFQ implications:
ChatGPT handoff:
```

Hot direction table fields:

```text
产品方向 | 数据来源 | 需求信号 | 竞争强度 | 贝强是否适合做 | 推荐优先级 | 推荐标题方向 | 推荐主图卖点 | 推荐详情页卖点
```

## 贝强业务规则

- Treat Alibaba supplier pages as B2B supply evidence.
- Treat Amazon, Walmart, TikTok, and review articles as demand language, not as Beiqiang proof.
- Favor directions that support Beiqiang's wide toe box comfort walking shoe supplier positioning.
- Turn findings into operational choices: improve current products first, then decide whether new products are needed.

## 禁止事项

- Do not claim a direction is hot without at least one named data source or explicit missing-data note.
- Do not copy competitor wording into Beiqiang listings.
- Do not use unsupported medical, orthopedic, waterproof, safety, or compliance claims.
- Do not recommend high ad spend before title/image/detail quality and duplicate risk are checked.
