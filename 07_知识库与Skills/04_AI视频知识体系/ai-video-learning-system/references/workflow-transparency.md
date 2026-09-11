# AI 视频工作流透明与可复现规范

## 目标

让用户在生成前就能理解和修改工作流，而不是只在看到结果后反推问题。节点画布负责暴露技术变量；项目档案负责解释创作意图；运行清单把两者与最终候选绑定。

## 三层内容

### 1. 中央工作流

中央工作流保存模型节点、连接关系、兼容参数和可复用 Subgraph。它回答“系统怎样运行”。同一模型只维护一个当前权威入口；项目目录不复制中央工作流并把副本当成新规范。

需要区分两种 JSON：

- **可视化画布 JSON**：供用户在 ComfyUI 中打开、查看节点和修改暴露参数，是中央权威工作流；
- **实际提交 API JSON**：由本次 Prompt、素材和参数解析出的完整执行图，是该候选的复现证据，不反向成为新规范。

中央画布优先把这些参数暴露到顶层：

- Prompt；
- 参考图片、视频、音频；
- seed；
- 模式、模型、LoRA、strength、步数；
- sampler、scheduler；
- 宽高、画幅、帧数和实际时长；
- 参考素材读取精度；
- 输出前缀。

不常改且存在明确兼容关系的内部连接留在 Subgraph 内，避免项目操作时误接。

### 2. 项目镜头定义

项目的单一 `PROJECT.md` 解释“为什么这样生成”，包括镜头叙事作用、主体与环境冻结项、参考素材职责、单一主要动作、验收重点和与前后镜头的关系。

完整 Prompt 保存在独立纯文本文件中，便于用户在提交前直接修改。项目档案只链接 Prompt，不保存互相漂移的副本。

### 3. 候选运行清单

每次候选对应一个不可覆盖的运行清单。使用 [generation-run-manifest.template.json](generation-run-manifest.template.json) 建立新清单，至少记录：

```json
{
  "candidate_id": "S01_v01",
  "shot_id": "S01",
  "prompt_path": "prompts/S01_v01.txt",
  "prompt_sha256": "",
  "canonical_canvas_path": "中央可视化画布路径",
  "canonical_canvas_sha256": "",
  "review_canvas_path": "本候选可打开和讨论的画布快照",
  "review_canvas_sha256": "",
  "resolved_api_workflow_path": "本候选实际提交节点图路径",
  "resolved_api_workflow_sha256": "",
  "mode": "",
  "references": [
    {"path": "", "sha256": "", "role": "identity|costume|scene|motion|camera|audio|keyframe"}
  ],
  "parameters": {
    "seed": 0,
    "width": 0,
    "height": 0,
    "frames": 0,
    "effective_duration_seconds": 0,
    "model": "",
    "lora": "",
    "lora_strength": 0,
    "steps": 0,
    "sampler": "",
    "scheduler": ""
  },
  "changed_variable": "",
  "frozen_properties": [],
  "expected_output": "",
  "status": "ready|submitted|generated|accepted|rejected"
}
```

运行清单中的哈希在提交前计算。实际提交内容必须由该 Prompt 和中央工作流解析得到，不能在远端临时改完却不回写。若执行器直接组装 API 图，也必须先把解析后的 JSON 保存到清单所指路径，再提交完全相同的内容。

## 生成前检查

付费或长时生成提交前，用户和执行者都应能看到：

1. 这一镜头要表达什么；
2. 每个参考素材负责什么；
3. 模型将收到的完整 Prompt；
4. 采用哪张中央节点图；
5. 哪些参数可改、当前值是什么；
6. 本轮唯一改动和冻结项；
7. 生成后按什么标准判定。

若只有自然语言聊天摘要或最终视频，而没有上述文件，结果不能作为可复现基线。

## 节点画布的推荐分层

```text
参考素材路由
    ↓
模型官方核心 Subgraph
    ↓
候选参数与单变量分支
    ↓
预览 / 正式输出
    ↓
运行清单与项目验收
```

ComfyUI 的节点缓存、部分执行和 Subgraph 可以减少重复计算并提高复用，但不会消除生成模型的随机性。固定 seed 和其他变量后只改变一个因素，能把抽卡变成可解释的对照实验。

## 结果回写

生成结束后只在项目档案追加：可观察结果、保留优点、回归问题、接受或淘汰结论、下一步。Prompt、工作流和运行清单继续作为证据保留；淘汰候选的媒体可在结论记录后清理，但不要删除唯一的复现依据。
