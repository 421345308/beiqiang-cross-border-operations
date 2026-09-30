# Alibaba工具与代理协作

更新：2026-09-29。

- [贝强代理上下文入口](贝强代理上下文入口.md)：WorkBuddy、Accio、Codex共用的公司背景、目标、证据路由和质量要求；每次派发再附指定任务与冻结计划。
- [代理共用工作区与接入状态](代理共用工作区与接入状态.md)：实际工作目录、已通过的小任务、Accio固定会话与当前限制。
- `run_workbuddy_task.mjs`：通过WorkBuddy桌面官方认证通道派发限定Read/Write任务；默认从贝强目录启动。

- [WorkBuddy HR执行指南](WorkBuddy_HR执行指南.md)：精简委派、图片/标题质量、回执、故障与额度边界。
- [Codex独立能力与Accio依赖](Codex独立能力与Accio依赖.md)：优先独立API，只把已证明可迁移的能力算作脱离Accio。
- `run_workctl_with_accio_env.py`：当前Workctl网关适配；仍依赖正在运行且具有有效网关环境的Accio，不能把它叫作独立接口。

账号与凭证不写到本目录或代理提示词。商品业务规则取唯一SOP，具体事实取当次证据。命令参数和模型选择先查当前help/schema。
