# awesome-seedance 模板索引（工作区级）

本页是**工作区级通用 AI 视频能力**，服务所有视频项目，**不限于鞋类经营**。

| 项目 | 内容 |
| --- | --- |
| 来源 | https://github.com/LearnPrompt/awesome-seedance |
| 本地位置 | `08_工具链/02_视频工具/awesome-seedance/`（不进 Git，见下方说明） |
| 入库日期 | 2026-09-22（`--depth 1` 克隆，153 文件 / 11.01 MB） |
| 内容规模 | 25 个分类模板、463 个案例（`data/cases.json`）、264 次跨模型复测、12 个可安装 Skill |
| 许可 | **代码 MIT**；策展编排 CC BY 4.0；**提示词与媒体归原作者**。三套并存，对外再分发前须逐项确认 |
| 更新 | 上游每日同步；需要新版时在本地目录执行 `git pull`，然后核对本索引的模板数是否仍为 25 |

## 为什么本地保留但不进 Git

上游每日自动同步，若纳入项目 Git 会产生持续的大量 diff 噪声；且它是第三方策展内容，按项目规则「第三方工程保持本地」。因此加入 `.gitignore`，只把**本索引**和鞋业场景约束入库。

## 怎么用

1. 先读本页，按**用途**而不是按行业选模板。
2. 再读模板正文：`08_工具链/02_视频工具/awesome-seedance/docs/templates/zh/<slug>.md`（中文）或 `.../en/<slug>.md`（英文原文）。
3. 需要机器可读版本时读 `data/templates-local.json`（含 `useWhen`、`structure`、`pitfalls`、`exampleCases`、`copyPrompt` 字段）。
4. 模板给出的是**镜头语言和结构方法**，不是贝强的事实来源。产品事实、客户事实、工厂事实仍回到项目自己的原始证据。

## 25 个模板

### 结构基础（3）—— 所有片型都可用

| 模板 | slug | 用途 |
| --- | --- | --- |
| 逐秒时间轴脚本 | `timeline-shot-script` | 把创意拆成逐秒镜头表，任何片型的前置工作 |
| 参考图身份锁 | `character-reference-lock` | 用参考图锁定主体特征不漂移，可套用到人物、产品、道具 |
| 分镜网格转视频 | `storyboard-grid-to-video` | 先出分镜网格再转视频，长片分段制作的基础 |

### 写实与 UGC（4）

| 模板 | slug | 用途 |
| --- | --- | --- |
| 手持 UGC vlog | `handheld-ugc-vlog` | 原生手机感、日常随拍质感 |
| 第一人称长镜头 | `pov-continuous-take` | 主观视角一镜到底 |
| 早年 DV 家庭录像 | `retro-found-footage` | 2000 年代家用 DV 质感、伪纪实 |
| 宠物动物当主角 | `pet-animal` | 宠物题材、动物拟人化 |

### 商业与产品（4）

| 模板 | slug | 用途 |
| --- | --- | --- |
| UGC 创作者评测 | `ugc-creator-review` | 口播评测体（虚构创作合法，见下方场景约束） |
| 产品广告镜头表 | `product-commercial-shotlist` | 商业广告的分镜与镜头清单 |
| 过程与转化蒙太奇 | `process-transformation-montage` | 制作过程、前后转化、工艺展示 |
| 时尚 lookbook 与人像 | `fashion-lookbook` | 服饰鞋包的造型展示与人像写真片 |

### 叙事与表演（5）

| 模板 | slug | 用途 |
| --- | --- | --- |
| 对白与表演节拍 | `dialogue-performance-beats` | 有人物对白的表演调度 |
| 电影感叙事短片 | `cinematic-narrative-short` | 有起承转合的短叙事 |
| 电影感旅行漫游 | `travel-city-walk` | 城市漫游、旅行蒙太奇 |
| 反转结尾搞笑短片 | `meme-comedy` | 梗文化、反转喜剧 |
| 恐怖悬疑 | `horror-suspense` | 恐怖、惊悚、悬疑氛围 |

### 风格化动画（3）

| 模板 | slug | 用途 |
| --- | --- | --- |
| 动漫风格锁 | `anime-style-lock` | 二次元/动画风格一致性 |
| 定格动画节奏 | `stop-motion-cadence` | 定格动画的低帧率手工质感 |
| 3D 卡通角色短片 | `3d-cartoon` | 3D 卡通角色与场景 |

### 动作、舞蹈与特效（6）

| 模板 | slug | 用途 |
| --- | --- | --- |
| 打斗编排 | `combat-choreography` | 动作戏的招式与节奏设计 |
| 节拍同步 MV | `music-beat-sync-mv` | 音乐卡点剪辑 |
| 时间冻结与倒放 | `time-freeze-rewind` | 时间暂停、倒放、速度特效 |
| 汽车与载具 | `car-vehicle` | 车辆、速度感镜头 |
| 奇幻科幻大场面 | `epic-fantasy-scifi` | 世界观、大场景特效 |
| 体育与极限运动 | `sports-extreme` | 运动动作与极限场景 |

合计 3 + 4 + 4 + 5 + 3 + 6 = **25**。

## 使用边界：约束属于场景，不属于模板

模板本身没有对错。**限制来自具体使用场景**，这一点必须分清：

| 场景 | 可以怎么做 |
| --- | --- |
| 通用 AI 视频实验 / 个人项目 | 25 个模板**全部可用**。虚构角色评测、恐怖、打斗、宠物、奇幻都是正当创作题材，不受经营场景的约束 |
| 贝强对外商品视频 | 只取与采购证据相关的子集，并遵守单款事实与不得编造的红线。见 [beiqiang-seedance-video 模板映射](../../../.agents/skills/beiqiang-seedance-video/references/template-mapping.md) |

换句话说：`ugc-creator-review` 用在**虚构创作**里完全合法；用在**贝强商品视频**里假装是真实买家评测，才构成编造客户评价。**不要因为经营场景的限制，就把整个模板库判为不可用。**

## 与其他视频知识的关系

- 本页是**模板来源索引**，不是规则权威。
- 分层记忆与经验晋级规则仍看 [ai-video-learning-system](ai-video-learning-system/SKILL.md)。
- 贝强商品视频的生成、验收与红线仍看 `.agents/skills/beiqiang-seedance-video/`。
- 模型参数与接口回到各模型的中央规范与当前工具帮助。
