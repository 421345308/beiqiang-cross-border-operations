# MiniMax H3 技术入口

本目录维护本工作区可验证的 MiniMax H3 技术事实、官方工作流和中央执行工具。项目创意与项目复盘不放在这里；经验如何沉淀由 `ai-video-learning-system` Skill 管理。

每次生成前按以下顺序执行：

1. 读取 `C:\Users\spq\.codex\skills\h3-prompt-writing\SKILL.md`。
2. 根据任务模式继续读取 Skill 中的 `references/base-en.txt` 或 `references/ref-en.txt`。
3. 读取本目录的 `MiniMax-H3本地生成规范.md`。
4. 从 `官方工作流/` 选择 T2VA、I2VA/FL2VA 或 Ref2VA 官方 JSON。
5. 先计算合法帧数和实际时长，可以避免 Prompt 时间线与 latent 长度不一致。
6. 使用 `validate_h3_prompt.ps1` 校验 Prompt 字段、首行、合法帧数与实际时长。
7. 校验通过后，再核对模式、权重、LoRA、步数、scheduler、参考素材路由和输出画幅。

需要建立一个用户可在生成前检查和修改的候选时，使用 `New-H3GenerationPackage.ps1`。它会从中央官方画布建立审阅快照、完整 Prompt 和运行清单；用户修改后运行 `Update-H3GenerationPackageHashes.ps1` 同步证据；提交前再用 `Test-H3GenerationPackage.ps1 -RequireReady` 核对实际 API 图。完整说明见 `生产母版V1.md`。

示例：

```powershell
& .\validate_h3_prompt.ps1 -Mode FL2VA -PromptPath '完整提示词路径' -Frames 124
```

## 权威文件

- `MiniMax-H3本地生成规范.md`：官方能力边界、模式选择、参数配对、推荐路径与审核。
- `官方工作流/video_minimax_h3_t2v.json`：官方 T2VA 工作流。
- `官方工作流/video_minimax_h3_i2v.json`：官方 I2VA / FL2VA 工作流。
- `官方工作流/video_minimax_h3_r2v.json`：官方 Ref2VA 工作流。
- `run_i2va_official.py`：由官方 I2V 节点图逐项映射的中央 I2VA / FL2VA 提交器；仅传 `--first-frame` 时为 I2VA，同时传 `--first-frame` 与 `--last-frame` 时把两图分别接入官方节点的首、尾帧输入；固定 FL2VA 权重、8-step Turbo LoRA（strength 1.0）、`res_multistep + simple`，避免历史项目参数悄然进入新任务。
  - `audio_vae` 的官方连接目标是 `VAEDecodeAudio`；传入 `MiniMaxH3ImageToVideo` 会触发节点输入错误。I2V 节点输入为 `clip`、视频 `vae`、prompt、尺寸、帧数及可选首/尾帧。

## 技术来源边界

- 历史项目 Prompt、Manifest、Gradio 参数槽脚本和运行日志属于项目输出，适合复盘具体结果，不适合直接定义新任务的模型连接方式。
- LoRA 降权、关闭 LoRA、自由文本 Prompt 或附加参考槽等经验先进入外部经验候选池；经过官方工作流对照验证后，再决定是否影响共享指南。
- 从旧成片反推的参数组合缺少完整运行上下文，复用前从当前官方节点图重新核对更可靠。

这样分层后，官方资料回答“模型怎样运行”，共享经验回答“什么情况下哪种选择更可能有效”，项目档案回答“这支片实际发生了什么”。
