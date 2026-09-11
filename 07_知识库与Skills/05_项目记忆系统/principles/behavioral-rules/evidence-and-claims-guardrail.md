---
type: Principle
title: 对外事实与承诺底线
description: 对外宣称货源、宽楦、材料、商务条件或技术能力前调用。
status: active
privacy: internal
tags: [货源证据, HOLD_SOURCE, B2B, 技术开发]
timestamp: 2026-09-08
---

# 对外事实与承诺底线

负责人 2026-09-08 确认：只有原始数据包商品属于贝强自有工厂货。扩品必须逐款关联原包；未匹配的标为 `HOLD_SOURCE`，不得称为自有货、计入确认供给或承诺样品/库存/交期。已核实的外部来源不自动变为自有货，归属变化由负责人确认。

上线、API 回读、生成图、热榜和竞品记录不能证明实物存在或可供货；后台回读只能证明其对应线上状态。

- 鞋类经营文案面向 B2B 采购；不编造认证、产能、材料、尺码、库存、医疗功效或商务承诺。
- FOB 8–12 USD/pair 是目标商业带；实际报价依款式、数量、材料、尺码配比、包装和要求确认。
- Wide Toe Box 是 SKU 级声明；BQ032 及之后默认 regular fit，除非 SKU 证据或用户确认宽楦。
- 技术开发必须分开 Buyer Target、Confirmed Capability、Fixed / Not Adjustable、Actual Result After Sampling；参考组件不能冒充测试完成的成鞋。

权威来源：根 `AGENTS.md`；技术开发执行 `07_知识库与Skills/01_运营SOP/技术型品牌买家询盘评估SOP.md`。发布、商务字段及验收条件直接读商品全生命周期 SOP，不沿用记忆中的旧默认。
