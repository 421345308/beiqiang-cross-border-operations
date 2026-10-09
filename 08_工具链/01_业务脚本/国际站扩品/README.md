# 国际站扩品工具

## 有效品牌原ID修复

`repair_brand_text.py` 用于已授权商品的有效品牌文本修复。本批执行范围见路崎执行记录的`质量复核_2026-10-09/有效品牌与MD标签核验.json`；该初始清单冻结，当前结果另见`有效品牌与MD标签当前核验.json`，不得把待审核当作已上线。

按 `prepare / submit / verify --manifest <初始清单绝对路径>` 分阶段执行。准备与验收各最多4个独立只读请求，写入逐款串行且每ID只尝试一次。当前原商品及其Schema是唯一载荷来源；只提交品牌所属`icbuCatProp`，其它属性逐节点保全，所有未提交商品字段正式回读比对。有效品牌须实际回读`Beiqiang`，不能因自定义负数标记存在而判通过。已有更新账本只能回读，禁止重放。平台审核通过后另验当前Schema和实际评分；该工具不产生浏览器验收结论，也不改变来源或单款自产事实。

> 旧文中的 Workctl 命令及为评分刷新库存示例仅作历史追溯，不作为现行执行入口；接续优先读文末“2026-10-02 工程交接与接续入口”和唯一生命周期 SOP。

> 当前真实写入入口须使用下文“2026-10-02 执行路径保护修正”的显式清单；旧批量脚本参数不可作为新建或更新的当前数据源。


用途：把搜鞋网贝强工厂店公开商品目录同步为本地清单，下载候选素材，并生成视觉审计联系表。

## 官方 Excel 模板保真写入

`build_alibaba_openxml.py` 用于把已通过事实、图片和去重闸门的商品行写入国际站当前类目官方模板。它保留隐藏表、批注、drawing/VML、关系文件和数据验证，只改写 `Template` 数据行；不得用普通 Excel 库重新导出后替代它。

输入 `rows.json` 是数组，每个元素代表一个颜色×尺码组合，以 Excel 列名为键。鞋类 `CL` 必须为 `Pair/Pairs`；`Piece/Pieces` 属于阻断错误。当前模板阶梯价按两列一组填写：`CM=2`、`CN=9.49`、`CO=50`、`CP=9.19`、`CQ=100`、`CR=9.09`；使用该模式时不要填写 `CI` 的 SKU 单件价格。生成后仍须执行本地三层校验、平台“检查文件”、单批不超过 15 款试发和全门禁回读。

生成器已经内置强制预检；任一关键字段不合格就停止输出 Excel。也可单独执行：

```powershell
python .\validate_alibaba_batch.py --rows <rows.json> --xlsx <批量发品.xlsx> --report <校验报告.json>
```

硬校验包括：型号/标题/SKU 唯一、同款产品级字段一致、6 张主图、4 张产品详情图、5 张公司图、颜色图不复用主图/详情图、全部图片为 `sc04` 正式地址、`CI` 为空、三档价格、单档 `100/31` 交期、真实包装和禁用宣称/临时 URL 扫描。表格未通过时只修 `rows.json` 或生成配置并重新生成，禁止转入浏览器逐项补字段。

格式校验之前必须先过“来源身份闸门”。`sooxie_prelisting_profiles_2026-08-14.json` 中标记为 `BLOCK_DUPLICATE` 或 `HOLD_*` 的款式，两个生成器都会直接报错停止；不得因为平台 Excel 显示“可发布”而绕过。平台预检只校验字段和格式，不证明与现有在线链接结构独立。

默认采用“一批一表、多款连续写入”的方式：先为每款生成全部颜色×尺码行，再把多款行合并进同一份官方模板。每款必须有唯一标题、型号和 SKU 前缀；产品级字段在该款所有 SKU 行中保持一致。完整单款试点通过后，先扩到 3–5 款，再扩到每批 10–15 款。浏览器仅用于整批图片入库、上传一份 Excel、平台检查/导入、异常回读和上线抽检，不作为常规逐款录入或补图工具。

图片银行批次约束：每批最多 10 张，文件名连扩展名不超过 30 个字符，建议用 `q53m1.jpg`、`q53d1.jpg`、`q53c1.jpg` 这种短编号。页面出现 `sc01` 只代表预览上传完成，必须点“确认上传”后使用图片银行返回或确认过的 `sc04` 正式地址；检测报告提示“图片需要来自图片银行”时，只修图片确认状态、URL 映射和 `rows.json`，随后重生成整批 Excel，不得转为逐款网页编辑。

真实图片局部去标支持：`build_sooxie_prelisting_batch.py` 的图片规格可使用 `{"path": "工作区相对路径"}` 引用已验收处理图。只允许在负责人确认可供无标版本时使用；处理图必须保存在 `01_产品资产/04_去标与处理后素材/<BQ编码_货号>/00_去标原图/`，原图不得覆盖。处理后先比较鞋型、鞋底、配色、角度和纹理，再生成 6 主图/详情/颜色图；出现结构漂移即剔除该图或整款暂缓。

## 目录同步

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\sync_sooxie_catalog.ps1 -Mode Inventory
```

输出：

- `02_Alibaba运营/05_扩品工程/数据/搜鞋网贝强工厂店在线商品_2026-08-14.csv`
- `02_Alibaba运营/05_扩品工程/数据/搜鞋网待去重候选_2026-08-14.csv`

## 下载候选主图

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\sync_sooxie_catalog.ps1 -Mode CandidateCovers
```

候选主图用于视觉去重，不代表可上架。

## 下载选定数据包

```powershell
& .\sync_sooxie_catalog.ps1 -Mode SelectedPackages -SelectedArtno @('ZX2212','T5503')
```

特点：

- 图片最多 4 路并发。
- 已存在文件自动跳过，可中断续跑。
- CDN 返回 WebP 时按真实格式保存。
- 每款保留 `source.json` 和原图文件夹。

大批量续跑经验：一次下载 48 包可能超出单次命令时限，应按 5-8 款小批运行。脚本会跳过已存在文件，不会重新下载完成包。Xiecdn 图片 URL 必须去掉 `!` 后的转码后缀，并携带来源 Referer；当前脚本已内置主/备 URL 和 3 次重试。

搜鞋网官方“数据下载”按钮需要登录。当前脚本从公开详情页重建标题、颜色、尺码、上架时间和完整详情图，不读取账号凭证。

## 生成联系表

`make_candidate_contact_sheets.ps1` 读取 JPG/PNG 审计预览并生成每页 12 张联系表。WebP 原图先转为 JPG 预览，原图不改。

## 生成预上架包

先完成重复/IP/产品事实审计，然后编辑配置正本：

```text
sooxie_prelisting_profiles_2026-08-14.json
```

执行：

```powershell
python .\build_sooxie_prelisting_batch.py --workspace C:\Users\spq\Desktop\贝强
```

新增单款或小批次时，避免重写已经人工修复过的其他商品素材目录：

```powershell
python .\build_sooxie_prelisting_batch.py --workspace C:\Users\spq\Desktop\贝强 --codes BQ052 --no-index
```

`--codes` 只选择指定编码，`--no-index` 只生成对应素材文件夹，不覆盖共享总表、验收文件和历史批次预览。完成视觉验收后，再通过台账合并新增商品状态。

脚本会：

- 从每款 `source.json` 直接读取尺码。
- 按配置生成 6 张主图、至少 4 张信息完整的英文详情图和逐颜色 SKU 图；默认不再为凑数补第 5、6 张详情图。
- 校验公开标题/关键词禁用宣称、图片数量、像素尺寸和颜色映射。
- 写出总表、单品填写表和主图/详情/颜色总览，用于人工视觉验收。

生成程序不调用生成式 AI，不改变鞋型、配色和结构。源图存在中文或第三方标识时，必须通过选图/合规裁切或转入隔离，不使用 AI 抹除风险元素。

## 每次运行后

1. 更新 `国际站合规扩品工程总控.md`。
2. 更新 `扩品批次台账.csv` 的唯一下一动作。
3. 不把“货号缺口”直接当成“可建链接数量”。
4. 不自动发布；草稿创建、提交和上线都要分别记录。

## 批量公开详情验收

`audit_alibaba_public_batch.ps1` 用于在提交审核前后读取同一批商品的实时公开 `descComponentData.bodyLayout`，生成紧凑对比报告。它会记录在线/审核状态、pageId、详情长度、产品/公司图库标记，以及 `Flyknit`、退款抵扣、无依据宽楦、Accio 临时地址和嵌套 Alibaba URL 风险数量。公开风险未归零的商品不能计入“完全正确”。

输入使用 Workctl `batch call` 的只读 JSON 规范，每个步骤调用当前实时 schema 中的 `icbu.other.list-id`；命令若变更，应先按 `workctl schema` 修正规范，不复制旧命令。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\audit_alibaba_public_batch.ps1 `
  -BatchSpec <批次只读查询.json> `
  -RawOutput <原始回读.json> `
  -Report <紧凑验收报告.json>
```

同一批同步前后必须保留两份紧凑报告。只有状态、结构化字段、公开 `bodyLayout`、真实图片像素、SKU 绑定和买家公开页全部通过，才可把商品标记为完成；本脚本不替代图片视觉验收。

`stage_alibaba_public_images.ps1` 可从同一份 `batch call` 原始回读中下载每款公开主图、详情图、公司图和去重后的 SKU 颜色图，并生成 URL/本地文件清单。下载后可对每个 SKU 目录运行 `make_candidate_contact_sheets.ps1`，逐张核对货号身份、第三方标识、中文/国内营销风格、颜色绑定和图集角色。公开 URL 回读与像素验收必须使用同一批原始数据，避免只看本地预上架包。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\stage_alibaba_public_images.ps1 `
  -RawBatchOutput <原始回读.json> `
  -OutputDirectory <公开图片验收目录>
```

## API 发品后的 3.9 分修复门禁

Schema 提交成功不等于库存已经对 30 个颜色×尺码 SKU 生效。若质量分为 `3.90`，先读取 `alibaba.icbu.product.score.get` 的 `extendProblemMap`；当只有 `inventory=true` 时，不得误改标题或图片，应通过 `alibaba.icbu.product.sku.inventory.get` 读取真实 SKU，再用 `alibaba.icbu.product.inventory.update` 把每个 SKU 同步到计划库存。`product.get` 可能不返回 Schema 商品的 `sku_infos`，此时库存接口是 SKU 绑定与库存验收的权威回读。

库存接口已经正确但质量分仍显示旧的 `3.90` 时，对同一 SKU 执行一次可逆的减一/加一刷新，等待平台重算后再次调用质量分接口。完成标准不是“已发出更新请求”，而是同一商品同时满足：审核通过、前台展示、30 个 SKU 库存正确、6 主图/4 产品详情图/5 公司图结构通过、质量分 `5.00` 且问题项全部为 `false`。

本批 HR001–HR067 的最终合并验证由 `consolidate_hr_audit.py` 生成。它还会核对 201 条发布回执中的首图 B2B 标识版本、官方图片银行 URL、主图/详情图互斥、标题唯一性和关键词唯一性，避免只依据平台分数判断内容质量。

## Schema 成功能力检索（必须先查）

在判断“API 不支持”或改走浏览器前，先运行唯一离线证据入口：

```powershell
python 08_工具链/01_业务脚本/国际站扩品/schema_publish_contract.py --operation create --detail-type 4 --category-id 201334413
```

注册表 `schema_capabilities.json` 是代码可读的证据索引，包含操作、详情类型、类目、日期、商品类型、ID 和原始回执/XML 路径；不要在 SOP/Skill 另建能力表。返回 `historically_verified` 仅说明该范围历史业务提交成功，必须重新获取当前类目 Schema、规则和权限；其他组合返回 `unverified`，不能解释为不支持。草稿、正式新建和更新分别查询（`createDraft/create/update`），详情类型 2/4/5 不互相推导。

正式 type4 新建复用 `publish_hot_rank_hr_a_batch.py` 的 `set_gallery` 嵌套图库构造及共享 `schema_publish_contract.values_only` 清理，不重写一套接口/载荷；旧脚本整批参数只属于历史任务，不可直接重跑或复制商业默认值。将当前 Schema 和核实后的目标数据传入已有构造函数；当前 Schema 的必填依赖和 FAQ 约束必须另行校验，保留实际条数，不硬编码四条。更新必须显式选择目标字段及当前 Schema 依赖，并保留当前 SKU ID；不要以新建清理器或旧整批源 XML 替代增量更新。

结果分为 `business_rejected`、`unverified_business_result`、`draft_created_needs_readback`、`submitted_needs_readback`；外层 success 或 ID 单独不够。草稿正文空、type2 的 DESCRIPTION_REQUIRED 都不能否定 type4 正式新建历史。提交后仍须独立核对正式字段、审核和公开页，不能由回执解除货源阻断。当前废弃的 Workctl/Work Agent 路线不作执行入口，旧记录只用于历史追溯。

离线回归（不读取凭证、不导入 API 客户端、不请求平台）：

```powershell
python -m unittest discover -s 08_工具链/01_业务脚本/国际站扩品 -p test_schema_publish_contract.py -v
```

字段级查询追加 `--field companyFaqDesc` 等参数：`reported_verified` 表示统筹报告已确认但本工程未摘录原始回执，`observed_noop` 只描述已记录尝试，`observed_empty` 表示正式字段为空；`unverified` 表示没有收集到匹配证据。各状态不能互相替换。`verify_content` 必须传入独立正式回读，回执成功不会自动转成内容成功。

FAQ 最新统筹报告是最多 8 条，question/answers 必填；这是当前目标 Schema 的观察，不作跨类目常量。`faq_constraints` 读取当次 Schema 原始规则；150/500 的 `maxInputNumRule` 没有单位时不得硬编码为字符数。实际提交前仍需核对当前规则和平台验证。新链接关键词仍空及库存全 0 由业务统筹处理，本工程未作平台写入或库存语义裁定。

## 2026-10-02 执行路径保护修正

写入接口 `api_submit` 直接调用客户端一次，不使用 `top_retry`。超时/断连返回 `write_outcome_unknown`，必须停止并核对创建/目标状态后再决定下一步；不得自动重发。失败字段递归检查且失败优先，矛盾或模糊响应不能算业务成功。

真实 CLI 的 draft/publish/update 统一要求 `--input-manifest` 和 `--receipt`，绕过旧批量构造器；旧批量参数不能进入这些写入模式。直接 API 也只接受 `prepare_scoped_listing` 准备的当前 Schema 载荷。update 只带显式 `field_ids` 和从当前目标拷贝的 `dependency_ids`；SKU 更新须保留当前 ID，拒绝历史整包、无关字段和目标 ID 错配。

输入清单格式（示意；占位值须换成当次事实与回读）：

```json
{
  "operation": "update",
  "product_id": "目标商品ID",
  "category_id": "目标叶子类目ID",
  "facts_reviewed": true,
  "source_evidence": ["当次单款事实审查的文件路径"],
  "current_schema": "target-current-schema.xml",
  "current_schema_sha256": "该文件实际SHA256",
  "schema_request_id": "当次回读request_id",
  "schema_acquired_at": "含时区的ISO时间",
  "payload_xml": "intended-fields-only.xml",
  "field_ids": ["productTitle"],
  "dependency_ids": []
}
```

`current_schema` 必须是目标当次回读或新建目标类目的当次 Schema；此入口接受 24 小时内快照，这只是本地防陈旧门禁，不保证平台期间不变。载荷 XML 必须仅包含 `field_ids` 对应字段；依赖从当前 Schema 拷贝。Schema hash、request_id、时间、目标、类目和事实审查在读取凭证前校验；不能用填写清单替代真实事实审查及已有写入授权。

```powershell
python 08_工具链/01_业务脚本/国际站扩品/publish_hot_rank_hr_a_batch.py --mode update --product-id <目标ID> --input-manifest <审查后清单.json> --receipt <新回执.json>
```

回执同时记录 `status` 和 `content_status`。正式业务成功仍为 `pending_readback`，退出码 2 表示待验收，不表示可以重发。verify_content 已接入实际 api_submit；独立正式回读不一致会返回 `content_mismatch_or_noop`。`--mode verify` 不调用客户端，读取独立正式回读证据 JSON（product_id、request_id、acquired_at、schema_file、schema_sha256），验证目标、hash 和晚于提交的时间，然后比较已保存回执的目标值：

```powershell
python 08_工具链/01_业务脚本/国际站扩品/publish_hot_rank_hr_a_batch.py --mode verify --product-id <目标ID> --receipt <提交回执.json> --formal-readback <独立正式回读证据.json>
```

verify 现在同时返回目标正式字段与发布后整体验收状态；缺评分或其它内容证据时退出码 2，不能报告整体完成。写入结果不明不得套用 verify 绕过创建排重，应先核对当次目标/新增状态。

最新 266 原件证明目标类目是 **32211**，不能沿用热榜历史的 201334413：注册表已纠正范围。正式 type4 新建回执和已审核四条 FAQ 快照可查归档原件。单次 FAQ 4→6 更新回执及 get 实际六条已证、其它字段未变，但 modified/N，公开最终未证；公司图库更新仍未验证。两项最新回执及前后计数的白名单 fixture 为 `schema_contract_fixtures/266_verified_receipts.json`，保留原件来源。新证据不扩大其它图库更新能力。

全部回归：`python -B -m unittest discover -s 08_工具链/01_业务脚本/国际站扩品 -p "test_schema*.py" -v`。真实路径测试只替换客户端传输为内存客户端，不替换 top_retry/api_submit/载荷构造；覆盖超时单次调用、外目录隔离导入、CLI 更新字段保护、深层失败和序列化回执正式 no-op 验证。

当前载荷准备器实际执行 FAQ 的动态 `maxItemsRule/minItemsRule` 与子字段 `requiredRule` 检查；无单位的 `maxInputNumRule` 只保留原始规则，不推定字符计数。写入 CLI 在请求前以独占方式保留回执账本；已有账本会在加载客户端前阻止再次请求，不能通过重复同一命令覆盖超时证据。

最新追加核验：FAQ6 的 get/render 原件及 `266_FAQ6_final_formal_checks.json` 已证明 exact、protected_fields_changed=[]、approved/Y，登记 `formal_fields_verified_approved`。统筹最新报告公开六条也已验收；当前已收原始 final checks 仍注明 PUBLIC_PENDING，故公开层单独记 `reported_verified`，不凭报告升级为原件验证。

## 发布后评分完成门

本批改造 `target_score=5.0`，达到平台分数仅是一项发布后完成条件，不限制首次发布。共享 `post_publish_acceptance` 输出实际分数、观察时间、来源和诊断状态：未出分 `PENDING_SCORE`；低于5.0 `PENDING_OPTIMIZATION`，按实际扣分项优化；5.0但时间/来源缺失 `PENDING_SCORE_EVIDENCE`；其它内容未验 `PENDING_CONTENT`；诊断未清 `PENDING_DIAGNOSTICS`。只有评分与全部既有内容门同时通过才为整体 `PASS`。平台分数不证明实物质量/真实性，源事实仍需独立证据。

实际提交回执已附此后验记录，分数默认 null。266 的能力注册记录也附 target_score=5.0、actual_score/observed_at/score_source=null、diagnostics.status=not_read、overall_status=PENDING_SCORE；这是待业务负责人读分的工程验收记录，不改商品业务状态表。

离线 `--mode verify` 的独立回读证据 JSON 可附以下字段；不可预填5.0或用示例替代真实回读：

```json
{
  "content_checks": {
    "review_approved": null,
    "public_page": null,
    "sku_binding": null,
    "media_review": null,
    "source_truth": null,
    "keyword_persistence": null
  },
  "post_publish_score": {
    "actual_score": null,
    "observed_at": null,
    "score_source": null,
    "diagnostics": {"status": "not_read"}
  }
}
```

`formal_fields` 由真实字段比较计算，不能手填绕过；其它检查只在对应证据通过后填 true。score_source 保留原始回读文件或 method/request_id，observed_at 为含时区的实际观察时间，正式验收要求评分回读晚于当次提交。diagnostics 保留实际诊断详情；已核无未解决项才标 clear，低分仍需按扣分项优化后重新读分。分数未读不会阻断第一次调用，提交后始终独立判断整体完成。

## 产品型号与图库格式回归

新建/草稿清单必须给 `expected_model`，且显式包含 `icbuCatProp`；入口调用共享 `serialize_product_attribute/serialize_product_model`，从当前 Schema 的 Model Number 定义定位字段，不固定猜 p-3。按当前已保存值或有来源的已验证字段格式保留负数 marker 和 inputValue，执行当次 byte 长度规则；SKU outerId 不能代替产品属性。找不到唯一型号字段或值格式时明确报 unsupported，停止在读取凭证前。型号更新同样可给 expected_model，由最小属性载荷序列化，保留其它目标字段。

格式 fixture 仅据936/K858已存型号原件；5998所摘录的旧NOT_SENT修正文件仅为准备态格式样本；统筹已确认后续真实型号修正提交成功，不得用旧样本降级当前业务状态。平台会把 -3 marker 规范成 -2，正式比较核对真实 inputValue，不能仅因负数标记变化误报 no-op。请求仍保留来源格式，不把 marker 硬编码成 -3。图库 fixture 保留266/936的真实嵌套、URL、role值及全部值属性，回归保证清理器不丢失；displayName 仅为观察到的来源属性，不声明所有类目通用必填或漏图的唯一因果。

## 询盘新建的可选库存省略

创建/草稿侧保持原始 SKU 库存字段省略，不默认999、不从Schema默认值补库存；新建依赖字段也必须显式提供已核事实值，不能借dependency_ids拷贝Schema默认商业数据。当前Schema明确requiredRule=true而省略/空置库存时停止，请取得已验证输入，不自动填值。准备结果和回执的inventory_input记录SKU数量、每行是否省略及完整原始已提供库存字段/XML和值属性；省略、空字段和999只是请求形态，不证明库存、供货或删除语义。更新侧不引入任何猜测清空规则。

真实fixture记录5998省略库存→正式stock空列表、score5；936/266显式999→正式stock0记录、score3.9及inventory问题。原始请求、get和score路径/request_id均保留；不同类目与内容存在混杂，因果未证，不能推广为通过省略/清空消分的方法，更不能假填999。

## 新建 SKU 正式回读语义

共享 `verify_content_details(..., operation="create")` 按稳定 skuOuterId 对齐行，逐项严格核对实际提交的 props（含颜色/尺码属性）及全部已提交字段；不要求请求/回读的行序或完整树相同。正式回读必须为每行给出唯一非空非0 skuId；首次独立回读建立稳定代码→平台ID映射，返回 sku_verification.bindings，后续带该映射时拒绝ID换绑。首读无法证明一个此前未知ID的历史归属，不作这种推断。

未提交 price/skuStock/outerSupplyId 等只进入 unsubmitted_observations，不填充请求、不判删除、不作为真实库存。update 保持完整严格比较及已有skuId保护。真实verify CLI读取回执operation（或正式method映射），调用共享比较并返回映射；新建SKU结构/ID绑定由代码校验，媒体像素、审核、货源、公开页等仍须各自证据。

`5998_create_sku_readback.json` 摘录指定原件SKU子树及hash/request_id，不含响应外壳/凭证。旧5998型号与266 M5/P4的NOT_SENT样本仅说明当时文件阶段；统筹确认两者后续已提交成功，本地样本不能降级实际业务状态。本回归不重做业务提交。

### verify 回执落盘与连续验收

verify 原子保存独立回执，默认 `<原提交回执文件名>.verification.json`，也可用 `--verification-receipt <固定验收回执.json>` 明确指定。后续使用同一原提交回执和同一验收路径时自动读取首次已验证的 SKU ID 绑定；即使上一轮失败，首次绑定仍保留。不要为每轮更换验收路径来重建绑定。

原提交回执始终保持原字节；验收回执记录其路径/hash及正式回读来源。换用/修改原提交回执会被拒绝；验收输出不得指向提交回执或原回读证据。验收过程对路径加独占锁，并在同目录临时文件 flush/fsync 后 os.replace 原子提交；失败不截断旧验收回执。崩溃残留锁须核对后处理，不自动抢锁。stdout 仍输出同份验收结果，不能代替落盘。

## 写入异常的安全取证

api_submit 异常回执新增 failure_evidence：脱敏message、明确或unknown的transport_phase、request_sent（三态）、curl_exit_code、http_status、业务request/trace引用、白名单响应摘要及stderr_excerpt。只保存已经捕获的信息；不保存请求URL、argv、headers、完整响应或凭证，不用curl错误码推断请求未发出。原response仍为null，状态仍write_outcome_unknown，禁止自动重试。

SDK ClientError 的 transport_evidence 仅在内存携带原响应；发布器 safe_exception_evidence 统一脱敏、白名单摘录后落盘。已有本地curl包装器复用SDK native_http_json，保留验证TLS、原签名和单次调用，增加HTTP状态捕获。新增包装器须复用该函数，不能再丢弃stdout/stderr而仅抛类名；旧无遥测异常只能保存现有脱敏文字/显式码，其余为未知。

69002 forensic_resolution.json 记录的原异常message/HTTP体/退出码已丢失，本修补不恢复、不猜测、不改其业务状态或重发授权。后续异常回执中的request_id只支持追查，不等于业务提交成功或未提交。

异常脱敏追加回归：Authorization按整行值遮蔽（包括Basic/base64），自由文本只要出现command/cmd/argv、curl或请求数据参数就整段省略，覆盖message、stderr、非JSON摘要；不只依赖异常是否有cmd属性。结构化HTTP/退出码/request_id仍可保留。

## 发布前本地差异化检查

真实新建/草稿载荷带scImages时，现有入口要求差异化PASS，否则在加载客户端/写入前停止，返回冲突产品ID/字段或UNVERIFIED缺证项；不修改载荷、不自动下架、不调用全店API。prepare_scoped_listing接收differentiation_context；api_submit再次绑定实际型号/首图/标题，不能换载荷绕过。

清单可附differentiation_review（JSON路径）及其sha256。该临时审查JSON含candidate的source/search_intent/hero_review，source_records按既有产品ID选择来源登记/图审投影，evidence_files列现有catalog_snapshot/source_register/visual_review文件及sha256。加载器从保存的products/get读真实ID、red_model/Model Number、首图；来源投影不能覆盖这些字段。现有13页本地快照可复用（分页报告总数363/364，保存363条；加载器记录条数/唯一ID/报告总数差异，不冒称完整覆盖），未知来源只列未关联ID，不宣称全店已去重；新建仍须其它既有身份/全店审计门禁。元数据必须来自真实来源/图审，不从标题猜搜索意图或用不同URL/hash假证图像差异。

同采购页的不同实款须有关键结构差异、独立型号、搜索意图和经图审的首图差异；已存在HR ABC可保留链接表达差异，update检查排除目标自身。新建同实款不因ABC后缀、标题换词或换URL获得豁免；不得复活旧多发同款试验。首图可见型号若与明确预期不符单独阻断；没有可见标签记not_present，没看图记缺证，不猜OCR。图库/型号规范仍以唯一SOP为准。

真实回归fixture只摘录同日全店快照中的新266、262、旧266及现有1688来源登记/实际M1图审：266/262为不同款，同源不是重复；旧/新266为同款，报告1601969526580、model_number/source_identity/hero_image等冲突。历史状态不用于自动处置现在商品。

差异化审查JSON的最小结构（值必须取当次既有登记/图审，不是生成的产品事实）：

```json
{
  "candidate": {"source": {"reference": "采购入口", "style": "实款货号", "critical_facts": {"profile": "已证结构"}, "evidence": ["来源登记"]}, "search_intent": {"key": "已审采购意图", "evidence": ["定位记录"]}, "hero_review": {"url": "实际首图URL", "content_key": "图审内容标识", "label_status": "not_present", "evidence": ["实际图审"]}},
  "source_records": {"既有产品ID": {"source": {}, "search_intent": {}, "hero_review": {}}},
  "evidence_files": [{"path": "现有保存列表.json", "sha256": "文件hash", "kind": "catalog_snapshot"}, {"path": "现有来源登记.md", "sha256": "文件hash", "kind": "source_register"}],
  "coverage_limit": "本地证据范围与缺口"
}
```

首图不同构图须有真实图审content_key/evidence；SHA只用于识别明确相同的文件，不把不等的SHA或URL当视觉差异。catalog数据读实际product_id/id、red_model/Model Number及首图；source_records只是选中来源记录的临时投影，不建立新的货源权威表。PASS仅为本地已关联范围差异化通过，不解除原有全店审计、来源和其它门禁。

### 显式 replacement 过渡

已授权库存省略重建，清单须显式给replacement_source_product_id，且差异化审查JSON的replacement同ID。evidence_files增加一个replacement_accepted_payload（完整已验收XML）及replacement_acceptance_record（旧ID验收原件），都校验hash；replacement包含authorization_evidence与acceptance_map：product_id、accepted_payload_sha256、accepted_field_ids、verified_field_ids、evidence。字段映射必须完整，原件必须识别旧ID。准备后的实际载荷仅允许省略库存/去除旧平台skuId，其余全部已验收值严格一致；型号不改名伪装，库存字段连空节点也不带。

过渡只匹配指定旧ID，且相同来源实款/型号/意图/已审首图；其它重复ID继续阻断，缺证仍未验证。回执保留replacement_transition.status=AUTHORIZED_TRANSITION_OLD_RETAINED、old_product_disposition=NOT_OFFLINED_PENDING_NEW_ACCEPTANCE；它是工程待收尾记录，不声称旧品已下架。新链接达到5.0、完整内容和公开QA后，旧品下架仍由有明确授权的业务执行者单独执行，本代码不发布/下架、不会按分数自动处置商品。

## 2026-10-02 工程交接与接续入口

本节是工具交接，业务规则仍只读唯一生命周期 SOP 和 `02_Alibaba运营/05_扩品工程/工厂店外新款数据采集模板.md`。当前模板 SHA256 为 `63c5329767c7512348255c9bdfc54d3ffd3f700a430d54128f87d607d35a8466`；变更后应重新审查投影，不自动刷新 hash 绕过保护。本文较早段落中的 Workctl 命令和为评分减一/加一库存路线仅作历史追溯，不能作为现行执行授权或复活入口；当前商业/库存依据以唯一 SOP、单款事实和当次授权为准。

下次 agent 先查 `schema_publish_contract.py` / `schema_capabilities.json`，再用既有 publisher 的 manifest 路由；不要另造签名、载荷或能力表。`historically_verified` 只在登记的日期、操作、类目、商品类型和详情形式成立；其它能力记 `unverified`，草稿失败和外层 success 均不能推导正式业务结论。FAQ 从当前 Schema 读取，不固定四条。

### 实际文件清单

以下路径相对本 README，SDK 路径相对项目根；它们是本次工程交付，不代表目录里所有历史脚本都适合重跑。

| 文件 | 用途 |
| --- | --- |
| `schema_publish_contract.py` | 共享能力检索、值载荷清理、动态字段约束、结果分类、正式回读、SKU/媒体/评分和差异化门 |
| `schema_capabilities.json` | 范围化历史成功证据唯一代码索引；回执与原件路径可追溯 |
| `publish_hot_rank_hr_a_batch.py` | 已有唯一 Schema 构造与显式 manifest 路由；单次写、独占回执、独立 verify、只读 inspect-existing、任务包桥接 |
| `.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py` | 现有 SDK 的安全异常取证与已存在 native TLS 传输抽取；不改授权、网关或自动重试 |
| `test_schema_publish_contract.py`、`test_schema_revision_paths.py` | 业务结果分类、草稿/正式分离、未知写入、实际路由与最小更新保护 |
| `test_schema_model_gallery.py`、`test_schema_create_inventory.py`、`test_schema_create_sku.py` | 当前型号与嵌套图库、可选库存省略、正式稳定 SKU/平台 ID 核验 |
| `test_schema_verify_persistence.py`、`test_schema_score_gate.py` | 原提交不变、原子独立验收及连续 SKU 绑定；真实5分与完整内容分开 |
| `test_schema_failure_evidence.py` | message/stderr/命令/Auth 安全脱敏与结构化传输证据 |
| `test_schema_differentiation.py`、`test_schema_replacement.py` | 真实来源/采购意图/图审差异、限定旧 ID 清洁库存重建与真实验收原件绑定 |
| `test_schema_keywords.py`、`test_schema_task_pack.py` | 当前关键词动态规则与 get/render 分类；A–G 显式投影、战略一对一映射、已建 ID 禁重发、OFF 计划禁进 create |
| `schema_contract_fixtures/README.md`、`formal_receipts.json`、`type4_detail.xml` | 去敏的历史正式成功与嵌套值结构，回执原件可追溯 |
| `schema_contract_fixtures/266_verified_receipts.json`、`gallery_success_shapes.json` | 266 范围内实证与嵌套图库格式；不泛化图库更新能力 |
| `schema_contract_fixtures/model_number_cases.json`、`model_number_formats.json` | 型号属性字段/marker/inputValue 的真实格式观察 |
| `schema_contract_fixtures/create_inventory_omission_cases.json`、`5998_create_sku_readback.json` | 实际新建库存请求与正式 SKU 回读摘录；不推广库存因果 |
| `schema_contract_fixtures/266_262_differentiation.json`、`keyword_current_cases.json` | 266/262 差异与重复实证；当前关键词 Schema、非空/空正式读值 |
| `schema_contract_fixtures/9968_existing_binding/inspect_manifest.json`、`taskpack_projection.json`、`differentiation_review.json`、`M1_label_observation.json` | 真实9968原提交、来源、采购意图、M1与本地目录的只读绑定 |
| 同目录 `mapping_snapshot.json`、`taskpack_document_snapshot.md`、`snapshot_provenance.json` | 注明来源/hash/时间的历史 fixture，隔离可变业务映射与经营文档；不是当前 OFF 权威 |
| 本 `README.md` | 调用方式、交付清单、已知缺口；不另建第二份业务 SOP |

### 只读验证与调用

2026-10-02 17:19 UTC 已验证 **93 tests PASS**；9968历史fixture和最新业务原件重新hash绑定两条只读路径都成功。在项目根运行完整离线回归（内存客户端/假的配置参数；不读取真实凭证，不创建/更新/下架商品）：

```powershell
python -B -m unittest discover -s 08_工具链/01_业务脚本/国际站扩品 -p "test_schema*.py"
python -B 08_工具链/01_业务脚本/国际站扩品/publish_hot_rank_hr_a_batch.py --mode inspect-existing --input-manifest 08_工具链/01_业务脚本/国际站扩品/schema_contract_fixtures/9968_existing_binding/inspect_manifest.json --product-id 1601969788941
```

9968 预期返回 `EXISTING_EVIDENCE_BOUND_NEW_CREATION_DISABLED`、`create_allowed=false`、`platform_calls=0`，绑定原 manifest SHA256 `9cd1eaeca3ca2549f8f47d2ac19aef9506af7816adfbeb8283b140f29cf7f133`；旧目标限定 HR052-A / `1601943742273`。fixture 中 `old_action` 是摘录时间的值，不能当当前平台状态。真实续用需用最新原件审查后建立新的 hash 绑定，原提交回执/manifest 保持不变。任何已分配 productId 的任务包或映射均拒绝 create/createDraft；创建未知先对账，不重发。

任务包接入需在现有 manifest 增加 `task_pack`（显式 JSON 投影路径）和 `task_pack_sha256`；投影绑定唯一模板、单款 A–G 原文和适用的一对一映射，明确 `task_id/role/phase/writer/next_action/public_model/category_id/product_id/source_identity/search_intent/hero_review`。A/C/D 映射到真实候选审查，B/E/G 引用原证据，F 只保留限定目标和待收尾计划。业务表不能自动变成执行请求；`operation` 必须与显式调用一致。战略不同实款 REPLACE 不得到同鞋重复豁免，也不会自动 OFF。既有同 SKU 清洁库存重建是另一份严格契约，不能混用。

2627BSK 最新原owner存档（2026-10-02 17:23:52 UTC）已创建 `1601969885846`，publish_receipt.status=submitted_needs_readback，正式及公开验收待完成；较早D3未知/未创建阶段已被新回执取代，不能拿旧断点重试创建。其历史 publish_manifest.operation=create、回执task_pack=null，不能伪称已完成A–G桥接接入；原manifest/回执保留原字节，由原owner用已有ID做只读续验，后续桥接须另建显式绑定的inspect-existing wrapper，禁止重放历史create。NEW/REPLACE路径已用实际loader/api_submit和内存客户端回归，不代替本款独立验收。本工程没有对该款上传、重试或创建。

### 已知缺口与接续边界

- 9968、3522 等正式关键词空值问题未由本工程解决。`serialize_product_keywords` 按当前实际子字段、输入数量、字节/正则规则构造；实际 SDK list→JSON→表单离线序列化未发现值丢失。已绑定 get 空值为 `keyword_not_persisted`；审核中 `pending_review`；无目标绑定/缺字段 `unverified_keyword_readback`；Schema 只有字段定义不是实际空值证据。3522 单次字段更新曾 SSL EOF，结果未知，不自动重发，由原 owner 用已认可传输做只读对账。各款更新后的结果以最新独立原件为准，不能由旧 fixture 降级。
- `batch.update.display` 的三份历史请求都为 `MissingParameter product_id_list`。三个实际参数摆放路径的离线解码均保留顶层 CSV，curl stdin 字节不丢失；没有可信修正。旧 TOP 官方契约与当前迁移网关是不同协议族，不能猜着换网关、session、签名或加版本再试写。等待当前迁移契约/平台 request-ID 追踪/匹配协议的成功原件。已确认浏览器 OFF 的目标保留该成果，不再重放旧目标，不从历史 Y 回读推断现在状态。
- 本地目录快照保存363条、原报告363/364；PASS 只覆盖关联证据，不宣称全店实时去重。旧品保护、订单/询盘/推广价值和 owner 占用由唯一业务执行者按当次授权查确切 ID，不扩大到家族。
- 工程验收与业务授权分开。关键词专项未完成仍如实记录；已另获明确授权的普通旧品收尾按其精确范围执行，工程没有平台 OFF 入口，也不覆写已确认授权。
- 未提交/超时结果、真实评分、媒体/公开页和转化效果分别保留未知，禁止阶段 PASS 代替全链完成；本工程没有平台写入、商品状态表改动或 Git push。

本轮增量 diff、机器可读交付清单及 OFF 离线复现位于 `C:/Users/spq/Documents/Codex/2026-10-02/task-5/`：`engineering_closeout.diff`、`engineering_closeout_evidence.json`、`delivery_manifest.json`、`task_pack_manifest_bridge.diff`、`keyword_contract_minimal.diff`、`replacement_acceptance_hardening.diff`、`off_protocol_offline_diagnostic.py`、`off_protocol_offline_evidence.json`。这些是审查材料；工作目录中的 install/apply/freeze 脚本是当次迁移工具，接续时不要重复运行或用它们覆盖生产代码。

硬停止时间为 **2026-10-02 18:00 UTC（北京次日02:00）**；届时停止新任务/修改/发布，只安全收敛在途结果并保存检查点，等待用户重新分配，不自动恢复，不推断额度已重置。

知识最终交接重绑：2026-10-02 17:26 UTC，按 task3/business_evidence_hashes_for_engineer.json 核实6份业务原件hash后更新上述模板绑定；历史9968 manifest与提交回执保持原字节。历史映射fixture仍是注明来源的快照，最新业务映射只在独立只读wrapper重新绑定，不冒称实时OFF状态。

## 2026-10-03补充：已验证首图精准更新与旧标签兼容

F2888 / 1601970034464 / category201339011 / type4，经当前目标Schema提交仅scImages首图替换；正式approved/Y、实际5.00，其他五主图、24SKU、属性、价格和结构化文字保持；详情图片集合与角色保持，平台返回顺序有变化。真实回执去敏fixture为`schema_contract_fixtures/F2888_verified_hero_update.json`，通过`schema_publish_contract.py capability`指定operation=update、field=scImages检索。仅此类目/日期/字段案例，不推断detailImage/companyImage更新、关键词或其他类目永久支持；公开完整QA未完成。

任务包读取器兼容既有同义标签`STRATEGIC_RETIRE_NOT_IDENTICAL_SHOE`，与长标签同属不同鞋款经营替换。精确旧ID、来源、保护、普通分层、已有新ID和去重检查保留；不修改业务表、不授予重复豁免或OFF权限。929准备包与5项离线兼容回归在`C:/Users/spq/Documents/Codex/2026-10-02/task-5/single_agent_resume_2310/929_publish/`；创建被平台自动审批拒绝，命令未启动，禁止改路重试。审批不是API能力证据。

### HR021：评分达标与字段保留必须分别验收

2026-10-03，category201152005 的 HR021 A/B/C 首图增量更新均获正式受理、approved/Y；02:29 UTC A实际5.0，B/C当时3.9。三款其他五主图、各12SKU、属性、价格及结构化详情保持，但原非空关键词均正式回读为空，即使B/C请求包含原关键词也未保留。去敏实际fixture为`schema_contract_fixtures/HR021_keyword_preservation_failure.json`，离线回归`test_hr021_keyword_preservation.py`确保5.0不能覆盖`keyword_not_persisted`。这是限定目标的副作用证据，不是通用删除契约、关键词永久不支持或完整更新能力认证。关键词恢复请求被自动审批阻止，命令未启动；不得改路重试，待可信直接授权。

## 2026-10-03：SKU 属性对发送前校验

`schema_publish_contract.py` 在 create/createDraft 发送前检查 SKU props 的 `propName=p-<propId>` 和文本 `propId:propValueId`，使用真实929成功格式和M001业务拒绝的去敏fixture回归。本检查只证明序列化格式，不扩张类目支持。A6607本次正式请求因店铺儿童鞋经营类目限制被明确拒绝；它不是type4能力不支持的证据。两款各一次正式尝试均无新ID，历史授权拒绝已被后续直接用户授权取代，不能继续作为当前阻塞。

离线9968检查fixture的模板哈希已按当前已审规范准确重绑，仍引用唯一权威模板，原业务manifest与正式回执保持不动。业务当前结果以总控台和单写入执行记录为准；本README前面的日期记录是历史证据，不继承旧报价、库存或退役命令。


### 关键词增量结果诊断（离线）

`diagnose_keyword_attempt(current_schema, payload, before_get, after_get, receipt, expected_product_id=...)` 复用 `compare_keyword_readback`，区分 accepted_keyword_noop、unexpected_keyword_loss、pending_review、retired_interface_rejected 与 unknown_write_outcome_stop；已存在的正确值不证明本次写成功。真实 fixture 和8项回归见 `schema_contract_fixtures/HR021_keyword_diagnosis_case.json`、`test_keyword_attempt_diagnosis.py`。六款当前字段存在不等于持久化已验证；同类失败不重放，Workctl 不恢复。下一项单款验证与精确旧HR边界见[当前诊断包](../../../02_Alibaba运营/05_扩品工程/执行记录/HR进度核查_2026-10-03_task5/关键词与旧HR诊断/最小修复方案.md)。


### M001 正常编辑页关键词迁移观察（2026-10-03）

正常页明确提示副标题/关键词合并至商品卖点；M001已有660字卖点，单字段关键词UI验证零输入/零保存/零提交，正式前后无差异。当前能力仍未证实，不得改卖点冒充关键词恢复、扩写其余五款或复活Workctl。实际页面、正式回读及六旧HR只读证据见[本轮结果](../../../02_Alibaba运营/05_扩品工程/执行记录/HR进度核查_2026-10-03_task5/关键词与旧HR诊断/M001关键词UI验证/结果.md)。


### 当前编辑版本的内容验收（2026-10-03）

现有验证CLI可读取正式证据的`content_version`，哈希绑定`formal_get_file/public_text_file`、精确`category_id/editor_observation_id`，调用`evaluate_versioned_content`后替换旧`keyword_persistence`硬门槛为当前卖点一致验收。2026-10-03 六款当前编辑版本正文已逐款核验完成（M001、2627BSK、805、H219、F2888、936），证据按精确商品/类目/观察ID/日期绑定；旧2627提示-only记录仍待验，未知或后续版本不得自动继承。旧关键词观测仍保留，不推断关键词写入或旧品下架完成。历史keyword字段诊断仍保留，单字段关键词请求仍需原字段持久化。唯一业务规则见[生命周期SOP §8.1](../../../02_Alibaba运营/00_运营SOP/国际站商品全生命周期SOP.md#81-按当前编辑版本选择关键词或商品卖点验收)；实际证据、计数及回归见[工程交付](../../../02_Alibaba运营/05_扩品工程/执行记录/HR进度核查_2026-10-03_task5/关键词迁移验收修正/工程交付.md)。

本轮新增五款去敏原文 fixture：`schema_contract_fixtures/current_content_six_20261003.json`；纯离线回归：`test_six_current_content_acceptance.py`。当前证据清单与45项测试见[六款续验交付](../../../02_Alibaba运营/05_扩品工程/执行记录/HR进度核查_2026-10-03_task5/关键词迁移验收修正/六款续验_2026-10-03/交付.md)。


### 2026-10-04：真实完整FAQ创建与回读归一化

唯一能力入口继续使用 `schema_publish_contract.py --operation create --detail-type 4 --category-id 201336512 --product-id 1601970628659`。既有 `schema_capabilities.json` 已登记989／1601970628659及725／1601970622736的精确正式创建、当前编辑版本和字段证据，含源款直链、自身型号、日期、类目与去敏fixture；再次准备同源商品先查现有ID，不能重发。它们分别为类目201336512／201334413，不能外推更新、草稿、HTML或永久全类目支持。

FAQ创建需按当前Schema写全父／子字段type，数量上限动态读取；725的实际31002拒绝fixture为 `schema_contract_fixtures/725_faq_type_rejection_20261004.json`。`created_field_equivalent` 只在创建回读中识别已观察到的字段排序、数值格式、定制值标记及sc04同资产链接；保留主图槽位、图库数量／分组、颜色与SKU身份，update仍严格比较。真实正负回归为 `test_created_readback_normalization.py`、`test_faq_create_type_guard.py`，本次56项离线测试通过，测试不写平台。

业务规则唯一权威仍为[全生命周期SOP](../../../02_Alibaba运营/00_运营SOP/国际站商品全生命周期SOP.md)。具体回执、当前版本证据、diff和验收以[2026-10-04交付](../../../02_Alibaba运营/05_扩品工程/执行记录/989与725正式新建_2026-10-04_task5/最终交付.md)为准；旧关键词空值不伪装为恢复，旧品不因新ID成功而自动下架，Workctl不复活。
