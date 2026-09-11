# 内容与视频工作位置

先读本目录 `README.md`，再进对应项目 `PROJECT.md`；缺档时先查现有源记录并建立最小项目档案，不能把目录名或渲染文件推定为验收。贝强 SKU 视频、TikTok 和通用 AI 实验分别管理，素材与产物不散落根目录。

- 使用相关视频记忆与 `ai-video-learning-system`；普通创作不加载 Alibaba、报价或无关经营记忆。模型按用户选择和已确认工具偏好路由。
- 消耗点数、额度或费用的 AI 视频生成须有负责人当次明确确认；范围改变时重新核对授权，不从旧任务推定。
- 按 `03_通用AI视频实验/README.md` 的在制、已完成、暂停、参考研究、历史待补档案分类。状态以 `PROJECT.md` 和验收证据为准，已有渲染不等于用户验收。
- 原始参考、生成结果、剪辑工程、成片与 QA 保持同项目关联。失败素材仅在有具体复盘/恢复用途时保留；可重建缓存无需长期保存。
- 审美经验保留适用范围和置信度，不把一次结果升级为模型规则。贝强商品视频要追溯真实 SKU，生成图不证明实物、产能或性能。

## MiniMax H3 专项

任何 H3 提示词/参数/工作流/生成任务，先读已安装 `h3-prompt-writing` 和 `08_工具链/02_视频工具/MiniMax-H3/MiniMax-H3本地生成规范.md`，只使用中央 `官方工作流/` JSON。

- T2VA/I2VA/FL2VA/L2VA：适用时先写官方关键帧对齐行，随后依次 `integrated_multimodal_description`、`overall_soundscape`、`non_diegetic_music`。
- Ref2VA：依次 `subject_definitions`、`summary`、`retention_analysis`、`detailed_description`、`overall_soundscape`、`non_diegetic_music`，统一参考标签。
- 先算合法 `17k + 5` 帧数，按有效时长 `frames / 24` 写提示词。FL2VA、Ref2VA 权重及 LoRA 分开；4-step 配 4 步、8-step 配 8 步，官方默认强度 1.0，除非新的官方依据更新中央规范。
- 提交前以模式、Prompt 文件和帧数调用中央 `validate_h3_prompt.ps1`；失败不生成。历史工程的工作流、manifest、Gradio slot 脚本和参数不复用为规范。
