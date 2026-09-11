# Skills 清单与任务路由

核对日期：2026-09-11。先按任务选择一个主 Skill，只读相关参考。项目业务知识在 Git 内维护；通用个人工具与插件保留原安装，不重复复制进项目。

## 项目维护的 21 个入口

以下文件均在 `.agents/skills/`。16 个贝强专用个人 Skills 已整包迁入，迁移前后 50 个文件、130,809 字节的 SHA-256 全部一致，原全局入口已移除；下列目录是后续维护位置。

| 任务 | 项目入口 | 使用边界 |
| --- | --- | --- |
| 买家定位与声明 | [beiqiang-positioning](../.agents/skills/beiqiang-positioning/SKILL.md) | 单款证据优先，宽楦不是全店默认 |
| 发品、发布与修复规则 | [alibaba-international-operations](../.agents/skills/alibaba-international-operations/SKILL.md) | 唯一 SOP 负责规则，入口只按任务路由 |
| API 执行与回读 | [alibaba-openapi-operator](../.agents/skills/alibaba-openapi-operator/SKILL.md) | 凭证在 Git 外，按已授权目标执行 |
| 当前全店审查 | [alibaba-30-products-audit](../.agents/skills/alibaba-30-products-audit/SKILL.md) | 覆盖当前全量，不限 30 款 |
| 单款优化 | [alibaba-product-optimizer](../.agents/skills/alibaba-product-optimizer/SKILL.md) | 小修改只交付相关字段 |
| 主图转化审查 | [image-conversion-review](../.agents/skills/image-conversion-review/SKILL.md) | 先审查问题再决定是否重做 |
| 图片简报与提示词 | [image-brief-generator](../.agents/skills/image-brief-generator/SKILL.md) | 真实商品证据约束生成 |
| 竞品研究 | [competitor-research-firecrawl](../.agents/skills/competitor-research-firecrawl/SKILL.md) | 外部观察不替代贝强事实 |
| 市场需求与方向 | [market-demand-research](../.agents/skills/market-demand-research/SKILL.md) | 区分后台数据、公开观察与假设 |
| P4P 测试 | [p4p-keyword-testing](../.agents/skills/p4p-keyword-testing/SKILL.md) | 测试方案与真实广告变更分开授权 |
| 周复盘 | [weekly-data-review](../.agents/skills/weekly-data-review/SKILL.md) | 用实际指标确定下一步 |
| 开店或重启首周 | [launch-week-operation](../.agents/skills/launch-week-operation/SKILL.md) | 非日常任务默认流程 |
| RFQ 报价 | [rfq-quote-assistant](../.agents/skills/rfq-quote-assistant/SKILL.md) | 技术开发买家先读技术型询盘 SOP |
| 询盘跟进 | [inquiry-follow-up](../.agents/skills/inquiry-follow-up/SKILL.md) | 起草与对外发送分开，发送须已授权 |
| 物流与贸易条款 | [shipping-trade-terms](../.agents/skills/shipping-trade-terms/SKILL.md) | 不虚构运费、时效和清关条件 |
| TikTok B2B 脚本 | [tiktok-b2b-content](../.agents/skills/tiktok-b2b-content/SKILL.md) | 产品/工厂证据与买家意图一致 |
| Seedance 鞋款视频 | [beiqiang-seedance-video](../.agents/skills/beiqiang-seedance-video/SKILL.md) | 生成工具与模型验证，剪辑交给 video-use |
| 项目记忆读取 | [beiqiang-memory-recall](../.agents/skills/beiqiang-memory-recall/SKILL.md) | 只读相关有效记忆 |
| 项目记忆维护 | [beiqiang-memory-curator](../.agents/skills/beiqiang-memory-curator/SKILL.md) | 维护以用户授权范围为准 |
| CompShare GPU | [compshare-cli](../.agents/skills/compshare-cli/SKILL.md) | 小入口加按需操作参考，以当前帮助为准 |
| Remotion 视频 | [remotion-best-practices](../.agents/skills/remotion-best-practices/SKILL.md) | 一个入口、11 个模式参考，避免再读插件同套流程 |

## 通用安装与其他维护源

按当前会话提供的 Skill 路径调用，不硬编码插件缓存版本。以下能力没有迁入项目：

| 能力 | 安装或维护方式 |
| --- | --- |
| H3 提示词 | 个人 `h3-prompt-writing`；先读项目 MiniMax-H3 中央规范与官方工作流 |
| LibTV 画布 | 个人 `libtv-cli` |
| 视频剪辑、QA、Manim | 个人 `video-use`，其下 `manim-video` |
| 视频通用经验 | `ai-video-learning-system`；[工作区维护源](04_AI视频知识体系/ai-video-learning-system/SKILL.md) 与个人安装按授权同步 |
| Work Agent | 优先 `~/.agents/skills/workctl/` 中的 `workctl` 和 `workctl-operator` |
| 文档、PDF、表格、演示、图像、网站、浏览器等 | 使用当前会话已安装的对应通用 Skill 或插件 |

## 维护规则

- [国际站商品全生命周期 SOP](../02_Alibaba运营/00_运营SOP/国际站商品全生命周期SOP.md) 是发布规则唯一来源；Skill 不再保存一套商业默认值。用户只改一个字段时，不强制展开整份运营模板。
- 贝强专用 Skill 直接改项目副本并随 Git 提交。迁入后不要重新建立同名全局副本；通用工具或插件的安装、升级与卸载按实际任务范围处理。
- Remotion 项目参考来自 4.0.522，2026-09-11 检查的插件内参考为 4.0.506。本地较新知识已保留，11 个重复项目入口与包内重复地图文本已移除；升级后检查是否重建重复入口，验证所有参考链接。
- Workctl 两个个人安装根的 16 个文件于 2026-09-11 比较一致。本项目只读取优先入口；其他任务兼容性未评估，不在本次卸载通用安装。
- `skills-lock.json` 保留 CompShare 上游安装来源；本地整理改动由 Git 跟踪，不伪造来源哈希。
