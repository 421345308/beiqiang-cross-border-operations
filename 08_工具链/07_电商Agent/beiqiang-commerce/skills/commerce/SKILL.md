---
name: commerce
description: Handle Beiqiang product listing preparation, ecommerce images/video, comparable operating data and buyer follow-up through one local workflow. Use for those tasks or a combined commerce task; use the relevant existing business skill for external execution. Not a general creative or unrelated coding agent.
---

# 贝强电商经营 Agent

首版依赖当前宿主模型进行理解、创意、分析和专业判断；MCP程序只承担数据读取、任务与证据管理、结构检查和已实现的官方只读查询。不能声称程序能自动判断实物、审美或增长成因。

## 接收和接续

1. 从当前用户请求确定目标和范围。复用已有明确选择，不为每次小修改补问全部字段。只改标题选 `title`；上架审核包选 `listing`；独立商品视频选 `video`；经营数据选 `operations`；跟进草稿选 `customer`；明确要求合并闭环且输入齐备才选 `commerce`。单项工作不得扩大成整店或全平台任务。
2. 先用 `commerce_tasks` 找本任务已有记录，用 `commerce_task` 核真实断点。新任务先 `commerce_plan`，再用稳定的 `idempotency_key` 调 `commerce_create`；重复请求沿用同一key，不按时间每次重建。已存在的业务项目先读其唯一入口。
3. 请求JSON必填 `workflow/goal/channel/language`。除纯数据分析外填 `sku`，涉及某个线上链接填 `listing_id`，多个ID不能任意代选。视频有现有项目填 `project_path`；运营/组合任务填 `metrics_path`；客户/组合任务填明确的 `customer_context_path`。路径均为工作区相对文件路径。
4. 用户只给自然语言时，由你把已有上下文整理成这些字段；字段无法推断才询问。缺经营数据或买家信息时继续独立的商品/内容工作，不编造数据或客户，也不把整个经营闭环记为完成。

## 执行与专业判断

用 `commerce_context` 取对应步骤的资料引用和已有产物，然后读取相关原文。入口的SHA只是版本记录；目录名、结构通过或平台成功都不是商品证据。SKU别名统一到 `canonical_sku`，同款多链接分别验收。源字段冲突原样揭示并按SOP解释，不能自动补自产、库存、宽楦、材料或商用承诺。

`identity/metrics` 由 `commerce_run` 执行。其它步骤由你调用对应已有Skills完成真实专业工作，再用 `commerce_submit_artifact` 保存结构化成果；已有成果可用 `commerce_complete` 登记文件。写入传刚读取的 `expected_revision`。版本冲突先重新读取；来源或产物变更，用 `commerce_refresh` 写明原因后重新检查，不能直接绕过检查标完成。刷新保留事件引用，但不自动重复外部动作。

- **商品**：按当前商品SOP和本款事实写标题、字段、素材角色、采购意图及未确认项。标题范围只交付标题及依据；完整上架包才覆盖全部内容。读取API成功能力和当前Schema后才判断支持字段，不从历史脚本继承默认值。
- **内容**：使用项目受众/渠道/语言/模型。先明确观众为何看、人物为何行动、商品如何影响行动，再写口语对白、镜头和提示；提示词是导演方案的执行形式。生活信息通过具体处境和动作表达，短视频按事件压缩节奏，避免小说式说明。痛感用行为变化与机位表达；走路核步态/接地/相对速度；开盒核盒身刚性、支撑和手部接触。三项来自BQ028一次用户反馈，原因未独立验证，不能作为全模型保证。动物保留自然动作；需要内心声时不要生成说话口型。具体场数/对白/笑点遵从该项目，不固化为通用模板。
- **运营**：复用 `commerce_metrics` 的可比口径计算。把观察、原因假设、下一测试和数据缺口分开；播放/点击不是订单，也不能用未知归因计算商机转化。
- **客户**：读取明确选定客户记录，核需求、商业条件和停止联系状态；引用现有CRM，不另建客户主库。首版产物是草稿，`sent:false`。真正发送只在用户明确授权的范围调用已有工具，并在原客户业务源留真实证据。

## 成果和边界

产物结构见 [artifact-contracts.md](references/artifact-contracts.md)。最终 `review` 要给逐项证据或不适用理由；`reviewer:agent` 仅代表你的审核，不能伪造用户批准。运行时仅验证必填字段、时间线、身份、依赖和版本，不认证内容事实或美学。

`package_ready` 只表示已完成本任务审核包。对用户交付可读的实际成果、变化原因、验证和待核项。正式业务写回原有商品档案、PROJECT、CRM或经营入口，运行库只是任务索引与本地草稿，不作为新事实主库。客户/回执/凭证不公开同步。

`commerce_platform_read` 仅支持官方Alibaba `product.get`和LibTV `node`读取，不更改原台账，也不能把查询结果记为公开页面或完整视频验收。发布、上传、广告、消息和生成继续使用相应现有官方Skills与当次适用授权，执行证据回原业务对象；本插件v0.1不提交这些操作。不要因为同意开发，就推导为具体商品发布或本批付费生成授权。

## MCP不可用时

可通过插件内 `server.py --tool <commerce_*工具> --args-file <JSON文件>` 使用同一后端，不需要新模型API。完整安装、CLI用法和当前开发状态见工作区 `08_工具链/07_电商Agent/README.md`。当前官方平台命令仍以各工具 `--help` 与现行规范为准。
