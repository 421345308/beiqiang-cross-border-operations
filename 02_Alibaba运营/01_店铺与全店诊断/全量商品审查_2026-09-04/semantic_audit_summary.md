# 151 款语义只读审计摘要

基线：既有 `api_product_get_details.json` 与 `full_product_audit.csv`；未调用写 API，未修改线上商品。`attribute_semantic_audit.csv` 将机器候选与确认错误分列。

## 汇总

- 覆盖 151 款。
- 标题/型号不一致：25 款，标为 `confirmed_error_candidate`。其中 `DZ14546082-A` 标题未出现货号；另有旧型号字段形如 `BQ-001`、`BQ-016` 而标题使用商品款号的记录，仍需人工确认型号字段是否应改为商品款号，故 CSV 中是候选确认错误，不等同于已确认平台错误。
- 属性语义候选：32 款。主要命中 `Flexible Cushion`、`Chunky Cushion`、`Cushion`、`Soft/Stretch Textile Upper`、`Foamed Cushion Sole` 等描述性或字段错位值；这些是机械候选，须对照实物/原始资料确认后再改。
- BQ032 及以后标题或属性命中 `Wide Toe Box`：0 款机器命中。本次未发现 BQ032+ 的 Wide Toe Box 文字风险；这不构成对鞋楦证据的正向确认。
- 标题机械重复候选：37 款，主要是模板词或重复结构；需与同货号 W/R/O 家族区分。关键词过短/缺少核心鞋类词：0 款。

## 判定边界

### 机器候选

标题重复短语、模型 token 缺失、属性值含 Cushion/Flexible/Soft Textile 等描述性词、标题/属性出现 BQ032+ Wide Toe Box，均先列候选。机器无法判断照片是否真实、属性是否有供应商证据、旧型号是否为合法展示型号，也无法替代视觉审查。

### 确认错误

只有存在直接证据时才升级：标题明确缺少应展示的制造商货号；属性字段与实物/已确认资料明确冲突；出现未经 SKU 证据支持的 Wide Toe Box；或页面把描述性营销词填入不匹配的标准材料字段。当前 CSV 保守地将 25 个标题/型号不一致记录标为 `confirmed_error_candidate`，避免把机械结果误报为最终确认错误。

## 买家可读性候选

标题应让进口商/批发商能快速识别产品类型、结构/材质、使用场景、B2B 意图和制造商货号。当前标题普遍覆盖 shoe/walking/casual 及 wholesale/OEM/factory 等词，但存在大量模板化同质标题；建议后续按同货号家族核验差异化卖点，避免仅替换 W1/R1/O1 角色词。

## 优先人工队列

1. 先核对 25 个型号不一致记录，区分“标题漏货号”与“modelNumber 历史字段”。
2. 核对 32 个属性候选的标准字段、实物材料和供应商确认；尤其 BQ013、BQ014、BQ015、BQ032 以及含 Foamed/Chunky Cushion 的款。
3. 继续维持 BQ032+ Wide Toe Box 证据门槛；本轮无命中，不得反向推断为宽楦。
4. 对 37 个标题重复候选做同鞋型/同首图/详情语义复核，机器聚类不直接判重复。

明细：[attribute_semantic_audit.csv](./attribute_semantic_audit.csv)。
