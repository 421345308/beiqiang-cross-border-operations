# 9968 经营任务包（既有回执填表示例）

本例按[现有采集模板](../../工厂店外新款数据采集模板.md)填写，整合日期2026-10-02；只读既有执行证据，无平台写入。历史快照不能覆盖新的时间明确回执。

## A. 身份与事实

- 角色：NEW（方向需求代理支持）；执行写入者沿用原任务授权角色，本整合不是写入者。
- 内部货号9968，公开型号BQ-MJ9968，categoryId=201152005，productId=1601969788941。
- 实款采购入口：https://qdnx.sooxie.com/detail/2532759；成本60 CNY，来源采集与材料证据见[facts_and_copy.json](facts_and_copy.json)。有效入口说明内部可询货能力，不证明贝强自产或当前现货。
- SKU：Grey / Green / Blue；35–40，3×6=18；不额外换算US/脚长。材料/结构：鞋面/里衬Synthetic leather，外底Rubber，鞋垫PU；中底Not specified；单条hook-and-loop搭带、包后跟。
- 质量边界：已有原始照片/加工清单/视觉回执支撑可见结构；没有本整合取得的实物抽检或性能实验。平台5分与实物质量分开。
- 原批报价：数量2/50/100，USD/pair 13.44 / 12.54 / 11.65；FX=6.6987、加价1.5/1.4/1.3向上取分，MOQ2，仅本批冻结口径，不是永久报价。包装适用店铺商业基线、不是单款实测。
- 实际可选库存字段省略/未写，不继承事实草稿中的999计划；接单核价、色码、数量与交期。Schema与载荷见[prepared_listing.json](prepared_listing.json)、[intended_payload.xml](intended_payload.xml)。
- 去重范围与相近ID见[dedup_gate.json](dedup_gate.json)，不把部分查询扩大成全店结论；相近款不是已授权旧品替换对象。

## B. 需求与实款匹配

Mary Jane平底需求方向有零售近期购买/评价代理；9968单条宽搭带与拼色不是原零售样本同款。 需求与词证来源日期2026-10-02，参见[共享证据](../../../../06_市场研究/海外鞋类需求与词证_2026-10-02.md)。原零售信号只归原商品；本款销量、点击、询盘、搜索量及低竞争均未由这些页面验证。

## C. 词证与标题决策

- 候选词群：Mary Jane flats / colorblock / hook-and-loop strap / single strap / synthetic leather；均为公开语言候选，市场与URL见共享证据，搜索量未知、未冒充后台买家词。
- 已发布/当前载荷标题：`Women's Colorblock Mary Jane Flats with Hook-and-Loop Strap`。保留核心品类及来源支持结构；本例不提交新标题。
- 弃词：无证宽楦/医疗/防水/认证/性能、竞品品牌；不凭宽搭带写wide fit；不把synthetic leather写genuine leather。
- 关键词持久化单独验收：正式字段回读优先于facts拟稿；空值标待补，不由质量分代替。

## D. 图片分工（原清单角色，不新造验收）

| 图 | 买家问题 | 原清单证据与边界 |
| --- | --- | --- |
| M1 | 能否认清具体实鞋？ | Actual Grey shoe photograph; complete native scene；实际图像与有效像素仍以原清单/视觉回执为准 |
| M2 | 有哪些真实款型/颜色选择？ | Three source-mapped Grey Green Blue shoes；实际图像与有效像素仍以原清单/视觉回执为准 |
| M3 | 鞋口/后跟与穿着结构如何？ | Actual on-foot opening and closed heel；实际图像与有效像素仍以原清单/视觉回执为准 |
| M4 | 局部结构实际如何？ | True strap and stitched panel construction; native detail crop；实际图像与有效像素仍以原清单/视觉回执为准 |
| M5 | 怎样选择色码与询价输入？ | Size labels and buying inputs with complete Green shoes；实际图像与有效像素仍以原清单/视觉回执为准 |
| M6 | 如何联系采购并核对供应商身份？ | Product-led supplier identity, no claim this style is own-factory made；实际图像与有效像素仍以原清单/视觉回执为准 |
| D1 | 已知规格材料与未知项是什么？ | Confirmed source materials; no guessed midsole or leather grade；实际图像与有效像素仍以原清单/视觉回执为准 |
| D2 | 结构与细节如何？ | Actual opening, heel and strap structure, no performance promise；实际图像与有效像素仍以原清单/视觉回执为准 |
| D3 | 真实色码怎么选？ | Assortment and exact source label matrix; no measured conversions；实际图像与有效像素仍以原清单/视觉回执为准 |
| D4 | 询价需提供哪些订单要求？ | Practical procurement inputs with actual Blue shoes; no price card；实际图像与有效像素仍以原清单/视觉回执为准 |

清单来源：[asset_manifest.json](asset_manifest.json)。公司图沿用[company_v3_manifest.json](company_v3_manifest.json)五张及原视觉验收；不是本款自产证明。逐色SKU图取来源对应单色，不改色。无价格图、不靠纯文字占位；图组具体像素、CDN及视觉结论查原证据，不能由此表替代逐张看图。

## E. 当前验收状态

当前存档内容/审核/真实评分/公开QA通过。actual_score=5.00，2026-10-02T14:29:22.302306+00:00，request_id=0b80d2d617909513672208861。正式keywords实际为[""]，关键词持久化待补；旧品目标已在本例F/G增量预留，未执行下架。

正式验收：[formal_checks.json](formal_checks.json)；公开依据：[parent_public_final_acceptance.json](parent_public_final_acceptance.json)；评分与时间查[score_timestamp.json](score_timestamp.json)及原评分回执（若字段更晚，以更晚实证为准）。本例不声称重新进行平台查询或独立浏览器QA。

## F. 旧新映射与普通旧品收尾

当前待替换目标：HR052-A / 1601943742273 → 1601969788941。旧女鞋通用占位HOLD_SOURCE，9968提供明确女式单搭带拼色平底实款；保留HR040询盘价值与HR021已有货源，不抢最近款。 classification=普通品，观察2026-10-02 00:48:31 UTC；protected=false，仅该ID可候选，同族其他ID保持原状。reservation=PREOFF_CHECK_PASSED_AWAITING_PARENT_AUTHORIZED_OFF；old_action=NOT_SENT；whole_family_complete=false。具体分层证据、保留兄弟ID与工程交接字段见[现有队列映射](../../HR系列真实货源改造_2026-09-21/HR普通品一对一待替换映射_2026-10-02.json)。owner先确认未被占用、最新单目标分类与关联价值；新款适用验收通过后交父任务授权收尾，不重复新建或自行下架。

历史生产包续用缺口：publish_manifest未绑定source_identity/search_intent/hero_review、differentiation_review及其sha256；独立dedup_gate文件不自动接入新工程。现有新品真实5分和公开PASS成果保留，这不是发布失败或重新创建理由。工程writer须用原证据补绑定并静态验证；本任务不改原manifest，不重发。

## G. 唯一下一动作与复盘

由原owner补关键词持久化并回读；按当前已预留旧HR目标完成关联核实与授权收尾。

后续按适用窗口观察真实曝光、点击、询盘；没有转化数据只复用本次内容/工具能力的已验证范围，不宣称商业热卖。供应商可选问答不追加成硬阻断。

首三款只读核验通过并交父任务off owner；当前旧ID approved/Y、今日普通、限定本地未见冲突占用、11单加密ID对账无匹配。询盘/推广未知；关键词专项不阻塞此次已批准收尾。[确切交接](../HR首三款普通旧品收尾_2026-10-02/README.md)。本任务未下架，待单次off回执+同ID下架回读更新最终状态。
