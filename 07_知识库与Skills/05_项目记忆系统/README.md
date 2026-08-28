# 贝强项目记忆系统

更新时间：2026-08-27
来源方法：用户提供的《个人记忆系统》原文与截图，并结合贝强现有经营目录落地。

## 目标

让不同 AI 工具快速知道：贝强是谁、如何判断、怎样协作、当前在做什么、过去沉淀了什么。记忆文件属于本项目并由用户管理，不绑定任何单一 AI 工具。

## 五类记忆

| 一级目录 | 回答的问题 | 稳定性 |
| --- | --- | --- |
| `identity/` | 贝强是谁、长期角色与方向是什么 | 稳定层 |
| `principles/` | 做决策和经营时必须如何判断 | 稳定层 |
| `preferences/` | 希望 AI 如何沟通、协作和交付 | 动态层 |
| `context/` | 当前阶段、项目、关系和阻断是什么 | 动态层，必须注意时效 |
| `knowledge/` | 有哪些技能、经历、复盘和外部学习 | 动态层，经验不能直接当规则 |

## 权重与冲突裁决

| 等级 | 默认位置 | 使用方式 |
| --- | --- | --- |
| 身份基线 | `identity/` | 提供长期背景；事实冲突时回到证据核验，不作为行为禁令 |
| L1 | `principles/behavioral-rules/`、`principles/business-boundaries/` | 默认必须遵守；冲突时明确提醒用户 |
| L2 | `principles/decision-making/`、`knowledge/skills/` | 与任务相关时优先使用 |
| L3 | `preferences/` | 影响形式和协作方式，不覆盖事实 |
| L4 | `context/` | 影响当前决策；使用前核验时间和状态 |
| L5 | `knowledge/experiences/`、`knowledge/learnings/` | 用于类比和启发，不直接套用 |

高等级优先于低等级，但用户始终拥有最终决策权。AI 发现冲突时应说明冲突和风险，不替用户做最终选择。

## 目录硬约束

- 记忆目录有且只有两级：`一级目录/二级目录/文件.md`。
- 二级目录下只放文件，禁止创建三级目录。
- 内容增多时使用文件名前缀或拆成多个文件，不再加深目录。
- 每个一级、二级目录都有 `README.md`，说明“放什么/不放什么”。
- 每条正式记忆必须包含七字段 YAML frontmatter。
- `INDEX.md` 是总地图；新增、更新、归档记忆时必须同步。

## 七字段元数据

```yaml
---
type: Identity | Principle | Preference | Context | Skill | Experience | Learning
title: 一句话标题
description: 是什么，以及什么任务需要调用
status: active | archived
privacy: internal | public
tags: [主题一, 主题二]
timestamp: YYYY-MM-DD
---
```

`timestamp` 是内容最近一次沉淀或验证日期。涉及客户、账号、联系方式和内部经营数据时使用 `privacy: internal`。

## 调用判据

| 任务信号 | 优先加载 |
| --- | --- |
| 公司介绍、定位、长期目标 | `identity/` |
| 发布、报价、合规、承诺边界 | L1 principles，再读相关 L2 skill |
| 写文案、报告、沟通或交付 | 相关 principles + preferences |
| 继续当前项目、排优先级、判断阻断 | context；先核验 `timestamp` |
| 复盘、方案选择、技能复用 | knowledge/skills，再参考 experiences/learnings |
| 对外输出 | 跳过与任务无关的 `privacy: internal` 内容，不泄露内部数据 |

## 使用与维护闭环

### 读取

1. 先读本文件和 `INDEX.md`。
2. 按任务信号筛选 title + description，不全量阅读。
3. 先加载相关身份基线，再按 L1→L5 加载相关正文。
4. 说明本次使用了哪些关键记忆，以及如何影响决策。

### 写入

1. 从对话或项目结果中提取候选记忆；AI 输出本身不自动成为记忆。
2. 给出本质、来源、稳定性、目录、权重、隐私和排除理由。
3. 必须先让用户确认候选和归类。
4. 确认后写入或更新正文，并同步 `INDEX.md`。
5. 经验反复出现后可建议“经验→技能”；外部学习被内化后可建议“学习→技能”。未经确认不自动晋级。

## 与现有业务文件的关系

记忆库是“索引和提炼层”，不是第二套业务真相库：产品事实仍以 `01_产品资产/` 为准；Alibaba 发布以唯一权威 SOP 和最新回读为准；客户互动以 CRM/客户项目为准；视频参数以模型中央规范为准。记忆正文引用权威文件，不复制整份数据。
