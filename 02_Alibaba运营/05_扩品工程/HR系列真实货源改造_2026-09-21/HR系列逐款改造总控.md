# HR 系列逐款改造总控

建立日期：2026-09-21  
更新时间：2026-09-24
范围：HR001–HR067，共 67 个产品家族、201 条 A/B/C 链接。  
当前目标：保留已有链接，逐条改造成有真实生产或可执行供货渠道、价格安全、图片与详情适合 B2B 采购的商品。

## 完成定义

单条链接只有同时满足以下条件才记为 `PUBLIC_QA_PASS`：

1. 已映射贝强原始数据包，或记录了可执行的外部货源链接与真实来源；
2. 标题、型号、属性、颜色、尺码、SKU 与真实货源一致；
3. 最低销售价不低于核验进货价加价 30%，运费另计；
4. 六张主图分别回答不同采购问题，M1 产品优先，其余覆盖选择、结构、定制/打样、工厂/履约、包装或询价输入，不用同一角度与信息反复占位；
5. 至少四张产品专属详情图和五张已验收公司图；
6. 视频为当前商品专属视频或经全片接触表验收的通用工厂视频；
7. 平台提交成功，完成 API 回读、图片/SKU/价格核验和买家公开页验收。
8. 已记录需求证据：优先使用国际站选词参谋/产品参谋、Alibaba 公开销量商品卡及其它跨境平台的近期销售或搜索信号；热销只决定选品和词序优先级，不能替代货源、材料、功能或自有工厂证据。

## 执行原则

- 编号口径：`HRxxx` 是产品/型号家族，后缀 `-A/-B/-C` 是同一产品的不同存量链接，不代表不同鞋款。
- 先按 67 个家族核验货源，再逐条处理 201 个链接；同一家族 A/B/C 必须统一真实货号、鞋型、颜色、尺码、SKU、来源和价格底线。链接之间只允许使用真实的搜索意图、首图构图、图片信息角色和文案侧重点差异，不得换款、扩色或伪造产品差异；同时保留平台重复铺货风险记录，不再新增同款链接。
- 旧 HR 概念图、已上线状态、质量分和视频绑定不证明供货。未建立真实映射的链接一律 `HOLD_SOURCE`。
- 有流量的链接保留 Product ID，不删除；无流量链接也优先改造，只有明确重复且无经营价值时才另行提请负责人决定。
- 外部货源仍标真实来源，不自动写成贝强自有工厂货；下单前复核当天价格、可供色码与数量、包装和交期。公开页面库存数字不是选品或上架的精确库存门槛。完成真实换款后的有效 SKU 统一填 `999` 作可询货标记，不是物理库存，也不能对买家承诺 999 双现货。
- 改造选品采用“需求信号 + 可执行货源 + 单款事实”三重门：先找国际站或其它跨境平台已有需求的产品方向，再确认搜鞋网可采购的真实鞋。旧 HR 是概念图时不强求完全同款，可以选择相似方向的真实款作**整家族替换**；不再因与旧概念图不完全相同而停工。差异必须反映在同一家族 A/B/C 的型号、色码、鞋型、图片、文案和价格中，不把旧图作为新货。**不以页面即时库存或逐码精确数量淘汰候选/拖延改造；页面写 0 时核对渠道是否仍接单/可预订，或找同货号渠道，不能直接推断“无实际货源”。**有可执行采购入口且完成页面换款后，新 SKU 后台统一用 `999` 作可询货标记，不代表实际有 999 双；接单再核实。没有可用采购入口仍为 `HOLD_SOURCE`。其它平台热词、销量与价格只作需求参考，不复制品牌、医疗、宽楦、防滑等级等无证据表述。
- 标题由“当前选词参谋词簇 + 真实产品身份/结构 + B2B采购角色”组成，核心品类和结构词前置，Wholesale/OEM/ODM 等采购词按自然语义加入；不堆词，不把单个竞品标题当作选词证据。A/B/C 可以承接不同真实人群或采购意图，但必须保持同款事实一致。
- 通用工厂视频无需为每款制作不同内容；达到平台 20 条关联上限时才建立同内容容量分片，并控制每个分片约 15–18 条。

## 当前队列

| 顺序 | 链接 | Product ID | 真实映射 | 页面角色 | 当前状态 | 下一步 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | HR039-A | `1601943650395` | 搜鞋网贝强工厂店 `8025` | 混色批发/进口商入口 | `PUBLIC_QA_PASS` | OpenAPI 为 `approved/Y + Solid`，公开标题、价格、SKU、型号和纯色属性均终验通过；进入数据观察 |
| 2 | HR039-B | `1601943670292` | 与 HR039-A 同一真实货号 `8025` | `Men's + Knit Slip-On + Walking + Daily Wear` 搜索入口 | `PUBLIC_QA_PASS` | OpenAPI `approved/Y`，旧 Fit Type 已删除；公开标题、纯色、型号、两色、EU35–45 和价格终验通过，进入数据观察 |
| 3 | HR039-C | `1601943583746` | 与 HR039-A 同一真实货号 `8025` | `Unisex + Knit Sock Sneakers + Slip-On + OEM` 搜索入口 | `PUBLIC_QA_PASS` | OpenAPI `approved/Y`，型号与 Solid 正确且旧 Fit Type 已删除；公开标题、两色、EU35–45、价格和详情终验通过，进入数据观察 |
| 4 | HR001-A | `1601943321794` | 搜鞋网贝强工厂店 `9002` | `Men's + Knit Slip-On + Walking + Importers` | `PUBLIC_PAGE_QA_PASS / STOCK_999_VERIFIED / MATERIAL_LAYER_EVIDENCE_PENDING` | 页面图文已验收。2026-09-24 第一次仅提交 SKU Schema 库存虽获受理，审核通过后仍 20/20 为 0，已记录[无效提交回执](./HR001-A_9002_999可询货标记_提交回执_2026-09-24.json)；随后用库存专用 API `plus` 修复，[正式回执](./HR001-A_9002_999库存专用接口回执_2026-09-24.json)及独立回读确认 `approved/Y`、20/20 SKU 为 `999` 可询货标记，request_id `21546a1d17901844715034557`。来源详情卡仅证明“鞋底材质 EVA”，独立中底与里衬材质仍待核。 |
| 5 | HR001-B | `1601943493004` | 与 HR001-A 同一真实货号 `9002` | `Wholesale + Men's Knit Slip-On + Walking + OEM Supplier` | `PUBLIC_PAGE_QA_PASS / STOCK_999_VERIFIED / MATERIAL_LAYER_EVIDENCE_PENDING` | 20/20 新 SKU `999` 仅作可询货标记；页面图文验收通过。与 A 一样，独立中底与里衬材质仍缺单款证据。 |
| 6 | HR001-C | `1601943474137` | 与 HR001-A 同一真实货号 `9002` | `Private Label + Men's Textile Slip-On + Walking` | `PUBLIC_PAGE_QA_PASS / STOCK_999_VERIFIED / MATERIAL_LAYER_EVIDENCE_PENDING` | 20/20 新 SKU `999` 仅作可询货标记；页面图文验收通过。与 A 一样，独立中底与里衬材质仍缺单款证据。 |
| 7 | HR002-A | `1601943305914` | 整组改造目标 [路崎 `2618`](./HR002_2618_相似实款与图库预检_2026-09-24.md) | `Men's + Lace-Up + Casual/Walking`，待当期选词核对 | `BUYER_COPY_SOURCE_LEAK / modified/N / STOCK_999 / COMPANY_V3_PENDING / NOT_PUBLIC_QA` | [正式接口回读](./HR002-A_2618_提交后OpenAPI核验.json)：标题/型号、Black/Khaki/Dark Brown × 自定义 EU39–48 的 30 SKU、六主图、正确 D1–D4 商品详情和 USD16.90/16.40/15.90 已提交；30/30 有效 SKU 用库存专用接口设 999 并回读，非实物库存。负责人 09-24 明确买家页不能擅写外采身份；当前公司介绍、FAQ 和接口 `textDesc` 含采购身份，审核中卖家页禁止重提，恢复后首要清除；旧版公司图、公开验收待处理。 |
| 8 | HR002-B | `1601943393550` | 与 HR002-A 同一目标货号 `2618` | 黑色系带低帮休闲/步行，同鞋第二搜索入口 | `API_2618_SUBMITTED / modified/N / STOCK_0 / OLD_DETAIL_PENDING / BUYER_COPY_SOURCE_LEAK` | [接口提交回执](./HR002-B_2618_API字段提交回执.json)：新标题/型号、三色 EU39–48 共 30 SKU、黑色 M1+独立 M2–M6、USD16.90/16.40/15.90 已进入审核版；接口 `textDesc` 误含外采身份，审核恢复后优先清除。库存 30/30 仍 0，审核后写 999，旧结构化详情仍待换。 |
| 9 | HR002-C | `1601943419438` | 与 HR002-A 同一目标货号 `2618` | 同鞋第三真实搜索入口，待选词核对 | `API_2618_SUBMITTED / modified/N / STOCK_0 / OLD_DETAIL_PENDING / BUYER_COPY_SOURCE_LEAK` | [接口提交回执](./HR002-C_2618_API字段提交回执.json)：深棕真实穿着首图、独立 M2–M6、三色 EU39–48 共 30 SKU 和 USD16.90/16.40/15.90 已进入审核版；接口 `textDesc` 误含外采身份，审核恢复后优先清除。库存专用接口再设 999、替旧详情并公开验收。 |
| 10 | HR003-A | `1601943312845` | 搜鞋网吕尚鞋业 `9922` | `Men's + Chunky Mesh + Lace-Up + Casual` | `LOCAL_GALLERY_READY / SKU_AXIS_PASS / MATERIAL_PREFLIGHT_PENDING / NOT_LIVE` | 22 张详情实拍、A 白色首图、6 主图与 4 产品详情图已完成；Black/White、EU39–44 系统代码可用。米色不进首批 SKU。取消等待 HR002；独立核必填材料与 9922 单款证据，缺项可整家族转相似可采购实款，不因库存数字停工 |
| 11 | HR003-B | `1601943335928` | 与 HR003-A 同一真实货号 `9922` | 黑色 Chunky Dad Shoes 搜索入口 | `M1_LOCAL_READY / WAIT_HR003_A_PUBLIC_QA` | 黑色真实首图已完成；与 A 共用产品图、详情、公司图、SKU 和价格事实，A 未闭环前不提交 |
| 12 | HR003-C | `1601943467198` | 与 HR003-A 同一真实货号 `9922` | Wholesale Thick Sole Mesh 搜索入口 | `M1_LOCAL_READY / WAIT_HR003_A_PUBLIC_QA` | 黑白分屏真实首图已完成；与 A/B 同款，只改变标题搜索意图和图序，A、B 依次闭环后推进 |
| 13 | HR004-A | `1601943397351` | 搜鞋网新干线 `731` | `Men's + Lightweight Mesh + Lace-Up + Walking` | `LOCAL_GALLERY_READY / SKU_AXIS_PASS / MATERIAL_PREFLIGHT_PENDING / NOT_LIVE` | 来源页 CNY38、Grey/Black、EU39–47 已核验；A/B/C 首图、6 主图、4 详情图、2 SKU 图与 17 角色上传计划完成，计划最低 USD7.90 高于 30% 底线。取消等待 HR003；独立核类目必填材质与单款证据，缺项可转相似可采购实款 |
| 14 | HR004-B | `1601943405519` | 与 HR004-A 同一真实货号 `731` | 黑色轻量网面步行鞋搜索入口 | `WAIT_HR004_A_PUBLIC_QA` | 与 A 共用 731 事实、18 SKU、来源与价格底线；只改变黑色首图、词序和图序 |
| 15 | HR004-C | `1601943421458` | 与 HR004-A 同一真实货号 `731` | 灰黑两色批发休闲鞋搜索入口 | `WAIT_HR004_A_PUBLIC_QA` | 与 A/B 同款；使用灰黑总览首图，不建立新产品或扩色 |
| 16 | HR005-A | `1601943335751` | 搜鞋网 QQ龙鞋业 `1882` | `Men's + Mesh Mule + Backless + Slip-On` | `SOURCE_ROUTE_FOUND / LOCAL_GALLERY_READY / SKU_AXIS_PASS / MATERIAL_PREFLIGHT_PENDING / NOT_LIVE` | CNY27、Grey/Black、EU39–44 的系统码已确认；计划最低 USD5.90，高于30%底线；17角色上传计划为12上传+5复用。取消等待 HR004；页面“是否库存：否”不单独淘汰，独立核材料必填与单款证据，缺项可转相似可采购实款 |
| 17 | HR005-B | `1601943353831` | 与 HR005-A 同一真实货号 `1882` | 黑色网面后空穆勒鞋入口 | `WAIT_HR005_A_PUBLIC_QA` | 与 A 共用 1882 来源、12 SKU 和价格底线；只改变黑色首图、词序和图序 |
| 18 | HR005-C | `1601943444273` | 与 HR005-A 同一真实货号 `1882` | 灰黑两色批发网面半拖入口 | `WAIT_HR005_A_PUBLIC_QA` | 与 A/B 同款；使用灰黑总览首图，不建立新产品或蓝色 SKU |
| 19 | HR006-A | `1601943439124` | 搜鞋网飞云鞋业 `5838`；潮足与华福交叉核验 | `Men's + Knit Mesh + Rotary Dial + Casual Sneakers` | `SOURCE_SELECTED / MULTI_SUPPLIER_EVIDENCE / HOLD_IP / HOLD_ASSETS / SCHEMA_PREFLIGHT_PASS / WAIT_HR005_PUBLIC_QA` | 主来源 CNY55、Beige/Ice Blue/Black、EU39–44；18 SKU 系统码已通过 OpenAPI 预检；最低计划 USD10.90，高于30%底线；三家实拍均见 `PaulQiyu` 和带标旋钮，未取得无标版本，不上传、不抹标 |
| 20 | HR006-B | `1601943450234` | 与 HR006-A 同款 `5838` | 黑色旋转扣织物休闲运动鞋入口 | `HOLD_IP / HOLD_ASSETS / WAIT_HR006_A_PUBLIC_QA` | 与 A 共用 5838 来源、颜色尺码与价格底线；只改变黑色首图、词序和图序；随 A 等待无标证据 |
| 21 | HR006-C | `1601943364813` | 与 HR006-A 同款 `5838` | 米色/冰蓝/黑色批发旋转扣运动鞋入口 | `HOLD_IP / HOLD_ASSETS / WAIT_HR006_A_PUBLIC_QA` | 与 A/B 同款；三色总览首图，不建立新产品；随 A 等待无标证据 |
| 22 | HR007-A | `1601943463020` | 主候选涌哥网批 `G225`；安全备选牧诚 `Z212` | `Men's + Suede-Look + Low Top + Thick Sole + Lace Up` | `SOURCE_CANDIDATE_SELECTED / HOT_SIGNAL_PASS / HOLD_IP / HOLD_ASSETS / SCHEMA_PREFLIGHT_PASS / PREP_ONLY` | G225 CNY39、人气1184、退货率5.24%、Black/Yellow/Grey、EU39–44；18 SKU 系统码已通过 OpenAPI 预检；最低候选 USD8.10 高于30%底线；矩形标识和素材不足待解除 |
| 23 | HR007-B | `1601943408495` | 与 HR007-A 同款候选 `G225` | 黑色绒感低帮厚底系带休闲鞋入口 | `HOLD_IP / HOLD_ASSETS / PREP_ONLY` | 与 A 共用来源、事实和价格底线；只改变黑色首图、词序和图序 |
| 24 | HR007-C | `1601943332965` | 与 HR007-A 同款候选 `G225` | 黑/黄/灰三色批发低帮休闲鞋入口 | `HOLD_IP / HOLD_ASSETS / PREP_ONLY` | 与 A/B 同款；三色总览首图，不建立新产品 |
| 25 | HR008-A | `1601943348656` | 鞋型优先候选叁叁（33）鞋贸 `LT115`；履约备选有间鞋坊 `25273` | `White + Low Top + Lace Up + Casual Cupsole` | `SOURCE_CANDIDATE_SELECTED / SHAPE_MATCH_PASS / HOLD_SUPPLIER_QUALITY / HOLD_ASSETS / SCHEMA_PREFLIGHT_PASS / PREP_ONLY` | LT115 CNY36、White/Black/Brown、EU36–45；30 SKU 系统码已通过 OpenAPI 预检；最低候选 USD7.50 高于30%底线；退货率31.03%，需二供或样品质量核验 |
| 26 | HR008-B | `1601943422371` | 与 HR008-A 同款候选 `LT115` | 黑色低帮系带休闲板鞋入口 | `HOLD_SUPPLIER_QUALITY / HOLD_ASSETS / PREP_ONLY` | 与 A 共用来源、事实和价格底线；只改变黑色首图、词序和图序 |
| 27 | HR008-C | `1601943451227` | 与 HR008-A 同款候选 `LT115` | 白/黑/棕三色批发低帮休闲鞋入口 | `HOLD_SUPPLIER_QUALITY / HOLD_ASSETS / PREP_ONLY` | 与 A/B 同款；三色总览首图，不建立新产品 |
| 28 | HR009-A | `1601943434630` | 候选 `A2510W`；千品鞋业 + 领投鞋业同货号二供 | `Men's + Mesh-Look + Lace Up + Walking/Casual` | `SOURCE_CANDIDATE_SELECTED / CROSS_BORDER_SIGNAL / MULTI_SUPPLIER_EVIDENCE / HOLD_IP / HOLD_ASSETS / HOLD_CUSTOM_COLOR_MAPPING / SCHEMA_PARTIAL_PASS / PREP_ONLY` | 两家均CNY41、Black/White-Green/White-Blue、EU36–45；最低候选USD8.50高于30%底线；实拍 `AIR`、鞋舌和后跟标识待解除，组合色待自定义Schema预检 |
| 29 | HR009-B | `1601943411769` | 与 HR009-A 同款候选 `A2510W` | 黑色网面视觉低帮系带鞋入口 | `HOLD_IP / HOLD_ASSETS / HOLD_CUSTOM_COLOR_MAPPING / PREP_ONLY` | 与 A 共用来源、事实和价格底线；只改变黑色首图、词序和图序 |
| 30 | HR009-C | `1601943520149` | 与 HR009-A 同款候选 `A2510W` | 白蓝/白绿/黑三色批发休闲运动鞋入口 | `HOLD_IP / HOLD_ASSETS / HOLD_CUSTOM_COLOR_MAPPING / PREP_ONLY` | 与 A/B 同款；三色总览首图，不建立新产品 |
| 31 | HR010-A | `1601943501309` | 候选快乐鞋行 `086` | `Wholesale + Unisex + Black White + Chunky Dad Sneakers` | `SOURCE_CANDIDATE_SELECTED / CROSS_BORDER_SIGNAL / HOLD_IP / HOLD_ASSETS / HOLD_CUSTOM_COLOR_MAPPING / SCHEMA_PARTIAL_PASS / PREP_ONLY` | CNY48、单一黑白组合色、EU36–45；候选最低USD9.50高于30%底线；鞋舌/后跟标识、高清素材及组合色Schema待解除 |
| 32 | HR010-B | `1601943527175` | 与 HR010-A 同款候选 `086` | 黑白厚底系带休闲老爹鞋入口 | `HOLD_IP / HOLD_ASSETS / HOLD_CUSTOM_COLOR_MAPPING / PREP_ONLY` | 与 A 共用来源、10 SKU 和价格底线；只改搜索词序、首图构图和图序 |
| 33 | HR010-C | `1601943479449` | 与 HR010-A 同款候选 `086` | 批发/转售商黑白厚底休闲鞋入口 | `HOLD_IP / HOLD_ASSETS / HOLD_CUSTOM_COLOR_MAPPING / PREP_ONLY` | 与 A/B 同款；不换鞋、不扩色，使用不同真实角度首图 |
| 34 | HR011-A | `1601943501378` | [凌子鞋业 NK25](https://lingzi.sooxie.com/detail/1994564)仍有 ¥41、一件代发入口；俊杰同货号页仅作已下架历史证据 | `Wholesale + Unisex + Knit Slip On + Sock Sneakers` | `SOURCE_ROUTE_ACTIVE / LOCAL_GALLERY_READY / SKU_AXIS_PASS / MATERIAL_LAYER_EVIDENCE_PENDING / NOT_LIVE` | 首批 Black/Grey、EU36–45 的 20 SKU 色码轴可表达，最低候选 USD8.50 高于 ¥41×1.30；[9月24日复核](./HR011_NK25_货源候选与改造门禁_2026-09-22.md)发现来源未给大底/中底/里衬，旧概念鞋材料不能继承。取消“等 HR002”串行安排，独立找同款材料卡或资料完整的相似实款，先过字段门禁再上传提交；不因库存数字停工 |
| 35 | HR011-B | `1601943406882` | 与 HR011-A 同款候选 `NK25` | 黑色针织袜套套脚休闲鞋入口 | `LOCAL_GALLERY_READY / MATERIAL_LAYER_EVIDENCE_PENDING / NOT_LIVE` | 与 A 共用来源、20 SKU、价格和材料门禁；黑色首图及角度图已本地准备，定款后同货号推进，不保留旧 Lace Up |
| 36 | HR011-C | `1601943513336` | 与 HR011-A 同款候选 `NK25` | 灰色批发/转售商针织套脚鞋入口 | `LOCAL_GALLERY_READY / MATERIAL_LAYER_EVIDENCE_PENDING / NOT_LIVE` | 与 A/B 共用来源、20 SKU、价格和材料门禁；灰色角度图与批发语义已本地准备，不建立新产品或扩色 |
| 37 | HR012-A | `1601943445780` | 候选 `DL20` | 男式复古厚底系带休闲鞋进口商入口 | `HOLD_IP / HOLD_ASSETS / SCHEMA_PREFLIGHT_PASS / PREP_ONLY` | CNY49、三种组合色、EU39–44；33 图审查发现鞋舌字母标及素材真实性风险，禁止抹标；Schema 已确认自定义组合色 + 6码可建18 SKU，继续找无标实物证据或替代来源 |
| 38 | HR012-B | `1601943531277` | 与 HR012-A 同款候选 `DL20` | Layered upper / chunky sole 批发入口 | `HOLD_IP / HOLD_ASSETS / SCHEMA_PREFLIGHT_PASS / PREP_ONLY` | 与A共用同一货源、三色、EU39–44、价格底线及图片/IP阻断；不线上写入 |
| 39 | HR012-C | `1601943484576` | 与 HR012-A 同款候选 `DL20` | Retro dad style 三色批发入口 | `HOLD_IP / HOLD_ASSETS / SCHEMA_PREFLIGHT_PASS / PREP_ONLY` | 与A/B同款；不沿用旧AI页三色、EU36–45或无证据材料功能；不线上写入 |
| 40 | HR013-A | `1601943542214` | [路崎鞋业 777](https://luqi.sooxie.com/detail/2185764)，页面有一件代发、联系及拿货入口，黑/浅灰 EU39–48、¥25 | 网面套脚步行休闲鞋 | `SOURCE_ROUTE_FOUND / IMAGE_LOCAL_CANDIDATE / MATERIAL_MIDSOLE_PENDING / PREP_ONLY` | [19 图与材料实审](./HR013_777_全图与材料预检_2026-09-23.md)；[B2B 图稿审查](./HR013_777_B2B图稿审查_2026-09-23.md)：A/B/C 首图、M2–M6、D1–D4、双色 SKU 图已本地生成并逐张检查，尚未入库或上线。[官方 Schema 与替代货源复查](./HR013_777_类目Schema与替代货源复查_2026-09-23.md)证实 MD 大底及布内里可用自定义字段准确表达，唯独独立中底无证据；996/958 已下架，不换到失效货号。旧页仍概念图，不因库存字样停工，也不填旧材料提交。 |
| 41 | HR013-B | `1601943514448` | 与 A 共用 777 候选 | 同款黑色搜索入口待确定 | `SOURCE_CANDIDATE / PREP_ONLY` | 不换款，等待 A 定款与闭环 |
| 42 | HR013-C | `1601943543192` | 与 A 共用 777 候选 | 同款浅灰色搜索入口待确定 | `SOURCE_CANDIDATE / PREP_ONLY` | 不换款，等待 A/B 定款与闭环 |
| 43–45 | HR014-A/B/C | `1601943417982 / 1601943481648 / 1601943574061`，2026-09-23 OpenAPI 均回读 `approved/Y` | 网面系带男鞋方向；彩踏 `5566-1` 为同一家族优先候选，领鑫同款公版为第二公开采购入口候选，尚未定款 | `SOURCE_ROUTE_FOUND / HOLD_IP_ASSETS / MATERIAL_PREFLIGHT_PENDING / PREP_ONLY` | [货源与 Schema 纠错](./HR014_网面厚底鞋初筛_2026-09-23.md)：两店均标 CNY23，彩踏 4色 EU36–46，领鑫公版仅 EU39–44，双店共用黑白/黑色×6码＝12 SKU 预案；原 22 SKU 预案作废。当前类目 API Schema 必填大底/中底/里衬，来源未给齐；源图有无依据性能文案、领鑫混卖带字标变体，须完成材料/IP/图库审查。库存数字不是阻断；[旧页正式快照](./HR014_OpenAPI只读回读.json)仍为旧三色×10码，不改线上 |
| 46–48 | HR015-A/B/C | `1601943502604 / 1601943542329 / 1601943517454`，2026-09-23 OpenAPI 均回读 `approved/Y` | 旧页为白/黑/棕厚底冲孔系带运动休闲鞋；尚无可采用的新货号 | 同鞋型三链接的搜索入口待定 | `HOLD_SOURCE / PREP_ONLY` | [初筛记录](./HR015_冲孔休闲鞋初筛_2026-09-23.md)与[正式快照](./HR015_OpenAPI只读回读.json)：3 个搜鞋网公开候选经实图对照不合适，未改线上；继续寻找无标识争议、可供且素材完整的同方向款，或三链接同步换成经核实的新款 |
| 49–51 | HR016-A/B/C | `1601943514625 / 1601943535517 / 1601943523535`；三条官方均 `approved/Y`，公开关键项及视频通过 | 三链接统一采用[路崎 031](https://luqi.sooxie.com/detail/2454935)，男式中帮系带鞋，黑/卡其/土黄 EU39–48、页面 CNY98 | 同一真实货号；A/B/C 使用不同真实照片和信息角色 | `ABC_APPROVED_PUBLIC_KEY_QA_VIDEO_PASS / C_SCORE_5_STOCK_999` | 有代发/拿货入口，网纱里料、橡胶外底、EVA 中底有来源；30% 底线 CNY127.40/双。[A 公开页与视频验收](./HR016-A_031_公开验收与工厂视频回执_2026-09-24.md)、[B 正式与公开回执](./HR016-B_031_六主图四详情正式提交回执_2026-09-24.md)及[C 正式回读与公开关键项验收](./HR016-C_031_真实换款提交与回读_2026-09-24.md)均确认按同款 031 上线；C 六主图、四详情、五公司图、30 个唯一 SKU/30 个 `999`，正式质量分 5.00，工厂通用视频关联后公开播放。最低 USD21.90；`999` 只表示可询货，不是精确库存；接单核当天供应。 |
| 52–54 | HR017-A/B/C | `1601943484872 / 1601943583193 / 1601943459958`，2026-09-24 官方 `product.get` 均 `approved/Y` | 旧深蓝/奶油米/酒红复古网面鞋为概念资产；2026-09-24 选定[启越 Y1125](https://qiyue.sooxie.com/detail/2533841)作为整组相似实款采购路线，沙/灰 EU39–44、CNY83 | 三链接共用 Y1125，不保留旧鞋色码/图文，区别仅为真实搜索意图与不重复图片角色 | `SOURCE_ROUTE_FOUND / MATERIAL_EVIDENCE_PENDING / HOLD_ASSETS_IP / NOT_LIVE` | [公开货源初筛与 09-24 重判](./HR017_复古网面鞋初筛_2026-09-23.md)：采购页仍有代发/拿货入口，30% 最低销售等值 CNY107.90/双；“非完全同款”和逐码库存数字不再是选品阻断。首图其他字样与里料/中底、全图 IP 未过门禁，A/B/C 未线上换款，不按旧图发 Y1125。 |
| 55–57 | HR018-A/B/C | 原 ID `1601943561380 / 1601943555428 / 1601943607120` 均保留；A/B/C 均已提交改造 | 旧鞋为概念图；共用[路崎 036](https://luqi.sooxie.com/detail/2439422)整家族替换 | 同一货号，三条只区分真实搜索意图和首图角度；其余鞋款事实一致 | `ABC_APPROVED_Y / QUALITY_5_EACH / STOCK_999_EACH / PUBLIC_IMAGE_DETAIL_QA_PASS / FACTORY_VIDEO_API_BOUND / VIDEO_PUBLIC_QA_PASS / DUPLICATE_RISK` | [A 修正回读](./HR018-A_036_正式提交与接口回读_2026-09-24.md)、[B 回读](./HR018-B_036_正式提交与接口回读_2026-09-24.md)、[C 回读](./HR018-C_036_正式提交与接口回读_2026-09-24.md)：官方状态均 `approved/Y`，正式质量分各 5.00；各六主图、四详情、五公司图、黑/米自定义 EU39–48 共 20 SKU，20/20=`999` 可询货标记；最低 USD14.90 高于 ¥72 ×1.30。[三条公开九图终验](./HR018_036_公开九图与重复展示终验_2026-09-24.md)通过。[工厂通用主视频](./HR018_036_工厂主视频绑定与反向回读_2026-09-24.md)三条 API 反向回读和公开播放器均通过。M2–M6 与 D1–D4 完全共用，有重复展示风险，保留现有流量链接并继续治理。 |
| 58–60 | HR019-A/B/C | 历史 ID `1601943493822 / 1601943546524 / 1601943635041`，本轮未实时 OpenAPI 回读 | 旧女式针织套脚楔底鞋仅概念资产；F011/8037 仍为待核验线索 | 三链接共用一个新货号 | `HOLD_SOURCE / PREP_ONLY / DEDUP_8008_REJECTED` | [公开货源初筛与实拍去重](./HR019_女式针织套脚鞋货源初筛_2026-09-23.md)：8008 已用于 `BQ043`，避免重复；F011/8037 与旧图不同并非淘汰原因，可整家族换款，8037 店铺退货率 23.68% 需核。A32/AK10/V83 库存数字不单独判无货源，核实采购入口；15701 已下架。未改线上。 |
| 61–63 | HR020-A/B/C | `1601943497861 / 1601943530673 / 1601943558469`，2026-09-23 官方接口均回读 `approved/Y` | 旧棕/黑/暖棕打孔侧松紧厚白底鞋为概念资产；尚无选定新货号 | 三链接共用一个新货号，搜索意图待定 | `HOLD_SOURCE / PREP_ONLY` | [搜鞋网公开初筛与实拍比对](./HR020_打孔套脚鞋货源初筛_2026-09-23.md)：A5809、9805、K819、8971-1 与旧鞋不同不构成停工理由，可在核采购入口/IP/素材后选相似款整组替换；89631 已下架。B 旧标题的 Mesh/Light Weight 未核实，旧图文不得混用。 |
| 64–66 | HR021-A/B/C | `1601943593293 / 1601943584343 / 1601943577329`，2026-09-23 OpenAPI 均回读 `approved/Y` | 旧单搭带网面厚底鞋是概念资产，尚无选定新货号 | 待定款 | `HOLD_SOURCE / PREP_ONLY` | [五款搜鞋网候选初筛](./HR021_女式搭带网面鞋货源初筛_2026-09-23.md)：SK18/5965A/D666 与旧鞋不同可作为整组换款候选重新评估，重点核采购入口、素材和 IP；2929/699 的原供货问题另核。A/B/C 不拆款；B 旧标题型号同步修正，未改线上。 |
| 67–69 | HR022-A/B/C | API 回读 ID `1601943496879 / 1601943496880 / 1601943578396` 均 `approved/Y`、各 30 SKU | 旧抽绳扣网面鞋是概念资产；[81888、3783、QAS03 初筛](./HR022_男式免手穿网面鞋货源初筛_2026-09-23.md)与旧图不同，但可重新评估为整组相似实款；旧 `999` 已归零并回读 | 同一真实货号待定 | `HOLD_SOURCE / PREP_ONLY / OLD_STOCK_0` | 不按旧图采购；核候选的采购入口、IP 与素材，选定同一货号后重建三条图文色码和价格。真实换款后有效 SKU 统一 `999`，不核逐码现货数字 |
| 70–72 | HR023-A/B/C | API 回读 ID `1601943614240 / 1601943629102 / 1601943547591` 均 `approved/Y`、各 30 SKU | 旧女式复古拼接板鞋是概念资产；[四款公开货源初筛](./HR023_女式复古拼接板鞋货源初筛_2026-09-23.md)与旧鞋型/色码不同不再否决，需逐款重核采购入口、IP 和素材；旧 `999` 已各 30/30 归零并回读 | 同一真实货号待定 | `HOLD_SOURCE / PREP_ONLY / OLD_STOCK_0` | 不按旧图发货；定同一真实货号后重建三条型号、色码、图文、价格并公开验收。真实换款后有效 SKU 统一 `999`，接单再核供应 |
| 73–75 | HR024-A/B/C | ID `1601943553670 / 1601943527861 / 1601943622296` 均 `approved/Y`，各 30 旧 SKU | 旧中帮网面鞋是概念资产；[一鸿 3316 真实采购入口及实拍](./HR024_网面鞋替换货源_2026-09-23.md)为优先整组换款，沙/黑 EU39–44、低帮松紧系带，与 HR014 的 5566-1 不重复 | A/B/C 共用一鸿 `3316`，链接搜索侧重点可不同 | `SOURCE_ROUTE_FOUND / REPLACEMENT_PREP / NOT_LIVE` | 先按 3316 重做 12 SKU、六主图、四产品详情、标题/型号、价格≥实采价×1.30；A 旧 30 SKU 已归零并回读，B/C 未改。完成 A 全门禁后继续 B/C；不得把旧中帮图文直接对应 3316 出货 |
| 76–201 | HR025–HR038、HR040–HR067 其余链接 | 见历史全链路回读 | 待逐家族核验 | 待确定 | `HOLD_SOURCE` | 按真实供给、链接流量和改造成本排序推进 |

## 状态词

- `HOLD_SOURCE`：没有真实生产或采购映射，禁止承诺供货。
- `SOURCE_CONFIRMED_PLAN_READY`：同一 HR 型号家族的真实来源已确认，差异化链接方案待执行。
- `PREFLIGHT_PASS_WAIT_PREVIOUS_PUBLIC_QA`：当前链接完整提交包已通过只读预检，但按逐条闭环原则等待前一链接公开验收；尚未写平台。
- `PREFLIGHT_PASS_READY_TO_SUBMIT`：完整提交包已通过只读预检，前一链接也已闭环，可以执行本链接提交。
- `DRAFT_VALIDATION_BLOCKED_CUSTOM_ATTRIBUTE`：目标图文、型号、SKU 与交易字段已保存在唯一草稿，但平台预检要求删除当前类目不支持的自定义属性；尚未公开提交。
- `DRAFT_SAVED_NEW_IMAGES`：卖家草稿已保存并刷新回读目标图组，买家页尚未更新。
- `SUBMITTED`：已提交，等待平台审核或传播。
- `API_SUBMITTED_REVIEW`：OpenAPI 写入已被平台接受，当前处于审核态；审核期间只读状态，不重复提交，审核恢复后继续剩余字段和公开验收。
- `UI_FIX_READY`：OpenAPI 已形成字段 no-op 证据，卖家后台已定位唯一剩余修复项；只允许修改已记录字段，提交后仍须 OpenAPI 和买家页终验。
- `UI_STAGED_WAIT_CONFIRM`：历史状态名，仅表示后台有暂存但尚未提交；不得把页面暂存计为线上完成。HR 系列既定改造目标内的普通业务判断与平台操作连续推进，不再设置内部“负责人再确认”停点；遇到平台或执行环境强制的即时安全确认时，按强制机制处理，不把它写成业务审批。
- `SUBMITTED_DETAIL_FIT_REPAIR`：产品详情替换与旧自定义属性清理已提交并进入 `modified/N`；审核期间只读回查、不重复写入，恢复后核验正式字段和买家公开页。
- `SUBMITTED_PATTERN_REPAIR`：已提交事实属性修复，审核期间不重提；审核后重新做 API 与公开页验收。
- `SUBMITTED_TITLE_ATTR_REPAIR`：标题传播、系统属性或自定义属性清理已提交；审核期间不重提，审核后逐项回读。
- `SUBMITTED_MODEL_FIX_WAIT_REVIEW`：主体迁移已提交，但门禁发现型号输入值仍需单字段修正；平台审核期间禁止重提，审核恢复后修正再验收。
- `SUBMITTED_MODEL_FIX`：型号单字段修正已提交并进入审核；即时正式版可能仍显示审核前值，禁止重复提交，待恢复后确认。
- `SUBMITTED_MODEL_FULL_SCHEMA_FIX`：裸型号字段更新被证明无效后，已在目标商品自身完整 Schema 内修改型号输入值；即时回读正确，等待审核与公开终验。
- `SUBMITTED_MODEL_FIX_FIT_TYPE_PENDING`：型号完整 Schema 修正已正确进入审核，但回读又发现旧链接自定义 Fit Type 残留；审核恢复后只删除该项再终验。
- `PUBLIC_QA_FAIL_TITLE_ATTR`：接口审核通过，但买家公开标题或属性仍与目标事实不一致，不得记为闭环。
- `PUBLIC_QA_PASS`：公开页及所有关键字段验收通过。
- `BLOCKED`：存在明确平台或证据阻断，必须写明阻断原因。

## 权威入口

- [货源、发货与图片总表](./HR系列货源发货与图片总表.md)
- [执行记录](./HR系列真实货源改造执行记录_2026-09-21.md)
- [HR039-B/C 当前字段只读回读与候选撤回记录](./HR039-BC_货源与字段预检_2026-09-21.md)
- [热销选品与标题优化规则](./HR系列热销选品与标题优化规则_2026-09-22.md)
- [HR002 → 2618 当前相似实款与图库预检](./HR002_2618_相似实款与图库预检_2026-09-24.md)；[S6077 历史草稿与失败回执](./HR002_S6077_货源选择与改造门禁_2026-09-22.md)
- [HR003 → 9922 货源选择与改造门禁](./HR003_9922_货源选择与改造门禁_2026-09-22.md)
- [历史201条全链路回读](../热榜持续扩品_2026-09-05/HR001-HR067_201条最终全链路回读.json)
