---
name: market-demand-research
description: Research Beiqiang walking shoe market demand and product direction priority using Alibaba backend exports, Firecrawl public competitor research, optional Apify/social signals, TikTok Creative Center observations, and keyword evidence. Use when deciding which product directions are worth promoting, developing, P4P testing, or making content for.
---

# Market Demand Research

## Required reads

- Read [current status](../../../00_总控台/当前状态.md), [product master](../../../00_总控台/产品经营主表.md), and dated evidence for the specific direction.

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

For a full direction study, return the following; a narrow question needs only the relevant conclusion, sources and limits:

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
```

Hot direction table fields:

```text
产品方向 | 数据来源 | 需求信号 | 竞争强度 | 贝强是否适合做 | 推荐优先级 | 推荐标题方向 | 推荐主图卖点 | 推荐详情页卖点
```

## 贝强业务规则

- Treat Alibaba supplier pages as B2B supply evidence.
- Treat Amazon, Walmart, TikTok, and review articles as demand language, not as Beiqiang proof.
- Favor directions supported by a real, verified supply route and B2B buyer demand. Wide-toe is one possible evidenced direction, not a store-wide positioning.
- Turn findings into operational choices: improve current products first, then decide whether new products are needed.

## 禁止事项

- Do not claim a direction is hot without at least one named data source or explicit missing-data note.
- Do not copy competitor wording into Beiqiang listings.
- Do not use unsupported medical, orthopedic, waterproof, safety, or compliance claims.
- Do not recommend high ad spend before title/image/detail quality and duplicate risk are checked.

## 完整任务记录入口

完整单款选品把需求源、观察日期、信号类型、与实款的异同和未知项写入现有采集模板 B；零售购买提示只证明原页面与观察期，评论数/品牌榜单是代理信号，不能迁移成本款销量。成熟证据复用并记录适用性，只补决策缺口；没有搜索量/竞争数据的蓝海记为试验假设。入口：[现有单款采集模板](../../../02_Alibaba运营/05_扩品工程/工厂店外新款数据采集模板.md)；详细规则只读生命周期 SOP，窄范围请求不扩展为整套工作。

品牌与拟售路线按生命周期 SOP §3；完整图数默认及2627BSK例外按 §4，不在本 Skill复制规则全文。
