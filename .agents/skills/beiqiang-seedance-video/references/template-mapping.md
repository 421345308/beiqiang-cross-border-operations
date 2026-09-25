# awesome-seedance 模板映射（贝强商品视频场景）

本页只回答一件事：**在「贝强对外商品视频」这个场景里，怎么用那个模板库。**

它不是对模板库的价值判断 —— 模板库是工作区级通用能力，25 个模板对通用创作全部可用。本页的取舍只在这个场景内成立。

- 模板库总索引：[awesome-seedance 模板索引](../../../../07_知识库与Skills/04_AI视频知识体系/awesome-seedance-模板索引.md)
- 模板正文：`08_工具链/02_视频工具/awesome-seedance/docs/templates/zh/<slug>.md`

## 直接采用（3）

| 模板 | 怎么用 |
| --- | --- |
| `timeline-shot-script` | 与本 Skill 现有第 4 条「Time-coded shot plan」同源，但细化到逐秒。新提示词一律按它写时间轴 |
| `storyboard-grid-to-video` | Alibaba 12–30 秒横版需要 2–3 段拼接时，先出分镜网格再逐段生成，避免整片结构失控 |
| `product-commercial-shotlist` | 16:9 横版与目录像的镜头清单来源 |

## 改造后采用（7）

**改造原则：迁移方法论，不迁移对象。** 这些模板的对象多是「人物/剧情」，要把它落到「鞋款 + 采购证据」上。

| 模板 | 改造方向 |
| --- | --- |
| `character-reference-lock` | 对象从「人物角色」换成「SKU 鞋款」。取其「可测参数 + 排除列表」写法，升级本 Skill 的 Product Identity Lock：颜色、针织纹理、鞋带走向、鞋口与拉环、外底色纹与轮廓、Logo 位置逐项写明，再列出「不得流入的相邻样式」 |
| `handheld-ugc-vlog` | 只取「原生手机感、自然光、低机位」的**镜头质感**，用于上脚与走动氛围镜头 |
| `pov-continuous-take` | 只取主观视角，用于「买家视角拿起鞋、翻看鞋底、按压前掌」 |
| `process-transformation-montage` | 只取蒙太奇结构，**素材限真实生产、质检、装箱、仓库**，AI 仅做转场 |
| `fashion-lookbook` | 用于多配色排列与鞋款造型展示；避开奢侈品调性，不做以真人身材为主体的时尚片 |
| `music-beat-sync-mv` | 只取节拍同步剪辑手法，并入本 Skill 的 Music 节（BPM、卡点、动作同步） |
| `time-freeze-rewind` | 可选。用于鞋底弯折、前掌宽度的慢动作停顿展示；不得暗示性能或缓震测试 |

## 本场景禁止（2）

| 模板 | 原因 |
| --- | --- |
| `ugc-creator-review` | 会生成「买家/创作者评测」体。用在贝强对外商品视频里等于**合成客户评价**，违反「不得编造客户评价」红线。同一模板用在虚构创作中不受此限 |
| `horror-suspense` | 与采购场景气质冲突，有品牌风险 |

## 本场景不使用（13）

`retro-found-footage`、`pet-animal`、`dialogue-performance-beats`、`cinematic-narrative-short`、`travel-city-walk`、`meme-comedy`、`anime-style-lock`、`stop-motion-cadence`、`3d-cartoon`、`combat-choreography`、`car-vehicle`、`epic-fantasy-scifi`、`sports-extreme`

**「不使用」不是「不可用」**：它们在通用 AI 视频实验里照常可用。若某个贝强项目出现合理场景（例如企业宣传需要叙事短片），可按具体任务重新评估，不必受本表束缚。

## 三条不可放松的约束

无论用哪个模板，以下三条优先于模板本身：

1. **单款事实**：鞋型、颜色、材料、认证、产能、交期只来自该 SKU 的原始证据。
2. **不得编造**：不生成虚假工厂、工人、测试、证书、价格、MOQ、客户评价。
3. **付费与授权**：付费生成须负责人当次确认；生成、剪辑、验收、发布分别取证。

## 已知踩坑（沿用现有经验）

- 即使写了 `no text`，模型仍可能在结尾英雄帧补出伪文字 → 明确要求全空背景、无任何标识与符号。
- 单角度参考不足以锁住针织纹理与雕塑外底 → 用同色干净的正、侧、三视角与外底参考。
- 「脚入鞋」动作易使鞋口与脚部变形 → 优先用穿着状态，套脚演示改用真实素材。
- 招牌断言只放在纯产品实拍镜头上，生活化生成镜头只作短插入。
- 生成后必须核对返回的 model ID，不能只信请求参数。
