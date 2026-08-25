# Accio / Workctl 发品实测（证据记录）

> 本文件是工具能力证据，不是发品 SOP。发品决策和门禁以 `02_Alibaba运营/00_运营SOP/国际站商品全生命周期SOP.md` 为唯一来源。

## Workctl

- 已安装并认证：`workctl v0.1.43`，账号 `accio_id 200689478`。
- 2026-08-25 已验证 Accio Desktop `0.30.2` 的本地 gateway 正常监听 `127.0.0.1:4097`；普通 Codex 子进程仍不会自动继承 gateway 环境。
- 已增加本地适配器 `run_workctl_with_accio_env.py`：只在本机内存中继承正在运行的 Accio 子进程环境并启动 `workctl`，不打印、不落盘、不提交 gateway token。使用方式：`python run_workctl_with_accio_env.py <workctl 参数>`。
- 适配器仅是 Windows x64 本地恢复措施；Accio 未运行、进程环境结构变化或 gateway 端口关闭时必须停止，不可猜 token、不可绕过登录。
- 通过适配器已成功读取实时动态 schema，并实测 `icbu.other.update-upgrade`、`product-edit-draft-detail`、`submit-draft`、`list-information`、`batch call` 与 `artifact get/stat`。
- 公网 npm 包 `workctl@0.2.1` 与当前 Work Agent CLI 不是同一产品，不得用 `npm install -g workctl` 升级本 CLI。官方恢复命令仍以安装 Skill 中的 `@ali/work-agent-cli` 说明为准。

## Accio 侧栏实测

- 侧栏可见能力包括智能发品、标题优化、扩充关键词、文本翻译、SKU 换色、合成场景图、营销视频和视频翻译。
- Accio 自述可做商品查询、草稿编辑、图片银行上传、SKU 图绑定、详情编辑、预检和提交，但它无法展示底层工具的准确名称、参数、返回结构或 dry-run 语义，不能据此直接调用。
- 对在线商品 BQ041 的只读查询可返回标题、商品 ID、状态、审核、价格、MOQ 和部分属性；不能可靠返回 6 张主图 URL、SKU ID/图绑定、详情类型、产品/公司图计数、包装和公开页。
- Accio 把 `31 天`交期错误解析成无单位的 `31342313`，因此交易字段必须由编辑器或其他权威接口回读。
- 对草稿 ID `10000047166193` 的只读查询明确返回“未查询到商品”；说明当前商品查询不能覆盖未发布草稿。不能让 Accio按 ID 安全接管半成品草稿。

## 当前工具分工

- Excel 批量发品：新品批处理的主路径。
- Accio / Workctl：存量旧 HTML 升级、结构化详情精确编辑、提交、copy/trunk 回读和多商品并行检查。
- 浏览器：登录、图片银行、Excel 检测/导入以及公开买家页最终验收；不再承担可批量结构化完成的重复点击。
- 所有 Workctl 命令每次执行前读取当前 schema 和 `--help`；不复用旧命令参数。

## 旧 HTML 详情实测 SOP（2026-08-25）

1. `list-information` 回读 trunk；`productDescType=5` 表示旧 HTML，不能直接调用 `product-edit-draft-detail`。
2. 调用 `update-upgrade`，每个商品传 `detailType=STRUCT_DETAIL`。接口会返回 `taskId`，随后用 `draftFirst` 回读；成功标志是 `productDescType=4` 且出现结构化详情字段。
3. 升级会带入旧共享模板文案，必须扫描 `Flyknit / refund / deduct / wide toe`；只修改已冻结的公司介绍与 FAQ，不改主图、详情图、SKU、价格、MOQ、交期或包装。
4. 提交前回读标题、Model Number、6 张主图、SKU 数、价格梯度、MOQ、交期、包装、详情/公司图数量和风险词。
5. 调用 `submit-draft` 后先检查 copy，再检查 trunk。`copy auditStatus=-2` 且 trunk 未变化表示平台审核/同步中，不得重复提交，也不得标记完成；稳定在线商品实测为 `auditStatus=1`。
6. copy、trunk、公开买家页三层一致后，才把该款标为完全正确。

### 2026-08-26 批次 3 新增实测

- Workctl 批次汇总的 `succeeded` 只说明工具调用完成，仍要逐项检查 `output.data`。业务正文为“不支持编辑结构化详情字段”或“Please check the number of custom attributes”时均视为失败。
- 旧详情先 `update-upgrade`，再以 `draftFirst` 确认 `productDescType=4`；随后图库按“DELETE 当前图 + ADD 正式 sc04 图”替换，FAQ 按 `sortOrder + operationType=EDIT` 更新。
- 系统 Model Number 修改必须带 `operationType=EDIT, attrNameId=3, attrValueId=-3`。遗漏 ID 会追加同名自定义属性；修复方法是删除无 ID 重复项并回读确认只剩一条系统属性。
- 已增加 `build_structured_detail_batch.ps1`，从批次计划和实时草稿回读生成可复用的详情替换批次；生成结果不写图片说明文本，避免卖家编辑页出现图集说明清理提示。

## 复用提示词

Accio 只读核对必须显式限定：

`只做只读查询，不得修改、保存、提交或发布。查询商品 ID <id>，读取不到的字段逐项写“无法读取”，不要猜测。`

任何写操作都必须冻结 productId、允许修改字段、禁止修改字段和“不提交”边界；随后仍由浏览器或权威接口回读。
