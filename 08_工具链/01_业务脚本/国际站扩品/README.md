# 国际站扩品工具

用途：把搜鞋网贝强工厂店公开商品目录同步为本地清单，下载候选素材，并生成视觉审计联系表。

## 官方 Excel 模板保真写入

`build_alibaba_openxml.py` 用于把已通过事实、图片和去重闸门的商品行写入国际站当前类目官方模板。它保留隐藏表、批注、drawing/VML、关系文件和数据验证，只改写 `Template` 数据行；不得用普通 Excel 库重新导出后替代它。

输入 `rows.json` 是数组，每个元素代表一个颜色×尺码组合，以 Excel 列名为键。当前模板阶梯价按两列一组填写：`CM=2`、`CN=9.49`、`CO=50`、`CP=9.19`、`CQ=100`、`CR=9.09`；使用该模式时不要填写 `CI` 的 SKU 单件价格。生成后仍须执行本地三层校验、平台“检查文件”、单批不超过 15 款试发和全门禁回读。

生成器已经内置强制预检；任一关键字段不合格就停止输出 Excel。也可单独执行：

```powershell
python .\validate_alibaba_batch.py --rows <rows.json> --xlsx <批量发品.xlsx> --report <校验报告.json>
```

硬校验包括：型号/标题/SKU 唯一、同款产品级字段一致、6 张主图、4 张产品详情图、5 张公司图、颜色图不复用主图/详情图、全部图片为 `sc04` 正式地址、`CI` 为空、三档价格、单档 `100/31` 交期、真实包装和禁用宣称/临时 URL 扫描。表格未通过时只修 `rows.json` 或生成配置并重新生成，禁止转入浏览器逐项补字段。

格式校验之前必须先过“来源身份闸门”。`sooxie_prelisting_profiles_2026-08-14.json` 中标记为 `BLOCK_DUPLICATE` 或 `HOLD_*` 的款式，两个生成器都会直接报错停止；不得因为平台 Excel 显示“可发布”而绕过。平台预检只校验字段和格式，不证明与现有在线链接结构独立。

默认采用“一批一表、多款连续写入”的方式：先为每款生成全部颜色×尺码行，再把多款行合并进同一份官方模板。每款必须有唯一标题、型号和 SKU 前缀；产品级字段在该款所有 SKU 行中保持一致。完整单款试点通过后，先扩到 3–5 款，再扩到每批 10–15 款。浏览器仅用于整批图片入库、上传一份 Excel、平台检查/导入、异常回读和上线抽检，不作为常规逐款录入或补图工具。

图片银行批次约束：每批最多 10 张，文件名连扩展名不超过 30 个字符，建议用 `q53m1.jpg`、`q53d1.jpg`、`q53c1.jpg` 这种短编号。页面出现 `sc01` 只代表预览上传完成，必须点“确认上传”后使用图片银行返回或确认过的 `sc04` 正式地址；检测报告提示“图片需要来自图片银行”时，只修图片确认状态、URL 映射和 `rows.json`，随后重生成整批 Excel，不得转为逐款网页编辑。

真实图片局部去标支持：`build_sooxie_prelisting_batch.py` 的图片规格可使用 `{"path": "工作区相对路径"}` 引用已验收处理图。只允许在负责人确认可供无标版本时使用；处理图必须保存在 `01_产品资产/02_处理后商品资产/<BQ编码_货号>/00_去标原图/`，原图不得覆盖。处理后先比较鞋型、鞋底、配色、角度和纹理，再生成 6 主图/详情/颜色图；出现结构漂移即剔除该图或整款暂缓。

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
