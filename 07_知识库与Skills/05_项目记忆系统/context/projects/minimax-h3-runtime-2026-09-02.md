---
type: Context
title: H3 最近确认实例与启动核验
description: 仅在已选 H3 后定位 CompShare 实例并控制空转成本；使用前查实时状态。
status: active
privacy: internal
tags: [MiniMax H3, CompShare, GPU实例]
timestamp: 2026-09-02
---

# H3 最近确认实例与启动核验

负责人于 2026-09-02 确认默认实例为 `pipa-h3-50g-wlcb`，ID `uhost-1upsea5q4e1r`，当时硬件标识 `4090_48G`。同日完成 HR001 I2VA 验证并停止实例；该记录不证明实例今天仍存在或正在停止。

先查实时实例列表；启动前满足付费授权，启动后检查模型、编码器、VAE、匹配 LoRA 与节点。预检失败立即停止，不盲目下载大模型或提交。生成、下载及必要验证结束后关闭本次 GPU，避免空转。

规范入口：`08_工具链/02_视频工具/MiniMax-H3/MiniMax-H3本地生成规范.md`、`h3-prompt-writing` 和当前 `compshare-cli` Skill。此实例不决定其他视频任务使用哪个模型。
