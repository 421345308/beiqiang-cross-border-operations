# 贝强独立站项目入口

网站源码使用独立 Git 仓库；经营仓库只维护运营 SOP、开发记录和导航。继续开发前先核对源码工作区与最新发布记录。

**持续推进：国际站与独立站产品对齐（2026-11-11）。** 主办：独立站增长会话；负责独立站产品与链接投影、只读差异核对和本地同步工具。EdgeOne 生产部署于 10:51 UTC 成功，正式域名回读 `2026-11-11.11`：网站与既有五语下载产品册均为 162 款。按 2026-11-10 15:46 UTC 的国际站完整快照，同口径 247 个产品身份中还有 85 个未进入网站；这是历史快照差异，不代表实时在售或库存。继续逐款核对既有来源、版本与素材，并复用产品中心和工作台映射；产品中心、国际站档案和工作台的并行修改由所属会话维护。

### 本轮产品对账与同步切片

**2026-11-11 负责人明确更正：**“搜鞋网上的商品都是可以直接发上去的，不用授权连接”，所问用途为贝强独立站。搜鞋网商品图不再以缺单独授权链接作为官网上新前置；继续核准实际商品身份、颜色、普通／加绒等版本、清晰度、明显第三方标识及个人信息，不能混用其他商品图。此前本页以未找到单独供图许可暂停官网草稿的判断已被此确认取代。该说明没有扩大为独立分发产品册或其他渠道的授权；独立产品册用途单独处理，不阻塞官网商品页。

**2026-11-11 新增两款正式上线：**[BQ-LQ021](https://www.beiqiang.online/products/bq-lq021/) 和 [BQ-LQ052](https://www.beiqiang.online/products/bq-lq052/) 分别对应产品中心 `LQ-021`、`LQ-052` 及国际站 `1601974859471`、`1601975454376`。07:59 UTC 官方回读均 `approved/Y`，前者为蓝、浅灰、黑及 EU 39–48，后者为米、黑及 **EU 39、42–48**；40、41 不在后者本次平台配置中，网站筛选保持缺口。色码配置不等于实时库存，宽鞋头分类复用既有负责人确认。原图和来源逐图留[追溯记录](02_开发记录/验收证据/20261110_产品对齐/lq021-lq052-source-image-lineage.json)。

本次网站提交 `8a30c38`、EdgeOne 部署 `dpr0311edric` 为 `Success`。正式域名已验两款 10 个五语详情页、8 张网页图、5 个产品册页、5 个询价页及 5 份下载 PDF；五份 PDF 各有 156 个不重复身份，型号链接指向对应语言详情页，中英各 34 页、德法西各 41 页，新增页面图片与版式已核。正式浏览器检查选色与询价清单，且确认 BQ-LQ052 的 EU 39、42、48 可筛出、40、41 不会误筛出；未发送真实询价。两款工作台实时投影已匹配现行款号、国际站 ID 和网站链接。隔离构建测试 565 项通过、8 项跳过，lint 0 错误、9 条既有图片警告。[完整验收](02_开发记录/验收证据/20261110_产品对齐/next-two-20261111-production-verification.json)；VPS 私有 API 是否更新及真实询盘投递未由本次验证证明。

**BQ-LQ052 选样提示已修复：**后续正式页复核发现 `2026-11-11.6` 英／中文选样提示错误套用了模压洞洞鞋模板，把实际系带称作仿鞋带装饰。网站提交 `9a24449` 已改为系带提示并补单元及实际渲染回归；隔离构建 565 项通过、8 项跳过，lint 0 错误、9 条既有图片警告。EdgeOne 部署 `dprx0822uwtu` 于 09:03 UTC 成功，正式站 `2026-11-11.7` 的 BQ-LQ052 中英提示、原模压款 BQ1048 中英提示，以及五语产品册页面和下载文件均回读通过。[修复回读](02_开发记录/验收证据/20261110_产品对齐/lq052-guidance-production-verification.json) 后续 `2026-11-11.8` 的 BQ-LQ052 中英文页面仍已回读为正确系带提示。

**2026-11-11 新增两款正式上线：**[BQ1013](https://www.beiqiang.online/products/bq1013/) 和 [BQ-LQ2588-1](https://www.beiqiang.online/products/bq-lq2588-1/) 复用产品中心 `HR013`、`BQ-LQ2588-1` 的已采用来源和既有国际站映射。BQ1013 对应 `1601943542214`、`1601943514448`、`1601943543192` 三条链接，仍是一款；11-10 全量快照三条均 `approved/Y`，11-11 03:57 UTC 对首条的回读仍 `approved/Y`，沙、酒红、黑各为供方尺码标签 36–48，未擅自称为欧码。BQ-LQ2588-1 的 `1601973772709` 于 03:49 UTC 回读 `approved/Y`，白、黑白、全黑各 EU 39–47；宽鞋头沿用负责人对来源分类的既有确认。平台色码配置不等于实时库存。八张原图按字节复用，逐图来源、颜色及哈希见[图片追溯](02_开发记录/验收证据/20261110_产品对齐/bq1013-lq2588-1-source-image-lineage.json)。

网站提交 `c8ebf73`、EdgeOne 部署 `dpgllgdxend4` 成功，正式站 `2026-11-11.11` 已回读两款 10 个五语商品页、8 张网页图、5 个产品册页、5 个询价页及 5 份网站下载 PDF；五份 PDF 各含 162 个不重复身份和对应语种商品链接，中英各 35 页、德法西各 43 页。BQ1013 的五语产品册卡片明确标注供方尺码标签，样品和码制需进一步确认；两款五语新增卡片已逐页目视检查。正式浏览器逐色核验两款询价清单、五语闭合及尺码筛选，未发送真实询盘；工作台已匹配两款及 BQ1013 的三条链接。隔离构建测试 574 项通过、8 项跳过，lint 0 错误、9 条既有图片警告。[正式验收](02_开发记录/验收证据/20261110_产品对齐/bq1013-lq2588-1-production-verification.json)

**选款助手后端范围：**BQ-LQ2588-1 可进入男鞋选款结果。本地按旧后端款号白名单进行条件模拟：普通询价的款号与商品条目可保留，但若私有 API 白名单尚未纳入新款，结构化选款简报可能过滤该款；人工选款路径也需核对。私有 API 当前版本及真实询盘投递本轮未验证，未重启服务；后续应在允许的部署流程中同步白名单并分别验证单款、新旧混选和人工选款。

**新增三款正式上线：**[BQ1021](https://www.beiqiang.online/products/bq1021/) / `HR021`、[BQ-LQ2633](https://www.beiqiang.online/products/bq-lq2633/) 和 [BQ-LQ2598](https://www.beiqiang.online/products/bq-lq2598/) 已进入正式站 `2026-11-11.9`。BQ1021 的三条国际站链接 `1601943593293`、`1601943584343`、`1601943577329` 于 08:13 UTC 均回读 `approved/Y`，分别为 `BQ1021-A/B/C`，归一个产品身份；米／黑各 EU 36–42。2633 于 03:57 UTC、2598 于 03:49 UTC 官方回读各自链接均 `approved/Y`，各三色、EU 39–48；平台配置不等于现货。两款路崎鞋的宽鞋头依据是负责人已确认的来源分类，非图片推断。12 张图片及 BQ1021 既有裁切与原片关系见[来源和哈希](02_开发记录/验收证据/20261110_产品对齐/three-products-source-image-lineage.json)。

已新增玛丽珍鞋五语分类，以及目录中的魔术贴与抽绳扣两种闭合方式和可分享筛选；2598 保持普通系带。玛丽珍分类询价按钮直接进入询价页，不伪造当前后端尚不支持的分类来源。网站提交 `9778cb4`、EdgeOne 部署 `dpiu1xkfardz` 为 `Success`。正式站已回读 15 个五语商品页、12 张网页图、5 个分类页、5 个产品册页、5 个询价页和 5 份下载文件；五份 PDF 均含 160 个不重复身份及对应语种链接，中英各 34 页、德法西各 42 页。正式浏览器核验 8 个色图、三款询价清单和 10 个五语闭合筛选，未发送真实询盘；工作台已匹配三款及 BQ1021 的三条链接。隔离构建 572 项通过、8 项跳过，lint 0 错误、9 条既有图片警告。[正式验收](02_开发记录/验收证据/20261110_产品对齐/three-products-20261111-production-verification.json)

**选款助手男鞋筛选已修复：**正式回读发现英文匹配曾把 `Women's` 中的 `men's` 误判为男鞋，BQ1021 会进入男鞋推荐；修复前已在正式站英、中两语复现。网站提交 `1fe6da9` 使用词边界识别男鞋，EdgeOne 部署 `dpglkcu29v56` 成功，正式版本 `2026-11-11.10` 在英、中、德、法、西五语实际操作男鞋筛选均未再出现该款。五语产品册页面和下载文件回读通过，下载文件哈希与已验的 160 款产品册一致；未发送真实询盘。隔离构建测试 573 项通过、8 项跳过，lint 0 错误、9 条既有图片警告。[筛选修复及正式回读](02_开发记录/验收证据/20261110_产品对齐/finder-gender-20261111-production-verification.json)。魔术贴与抽绳扣暂不作为选款助手提交给私有后端的新偏好；私有 API 版本和真实询盘投递未由本次验证证明。

**BQ1003 / HR003 已正式上线。** 已采用[泰豪 K0099 来源](https://taihao.sooxie.com/detail/2496569)，三条历史链接仍归一个身份；2026-11-11 03:57 UTC 首条 `1601943312845` 官方回读 `approved/Y`，黑、灰、蓝、红各 EU 38–50 共 52 个色码组合。来源脚长表仅至 46，官网五语详情页和五语下载产品册均提示 47–50 需确认样品尺寸；色码组合不是实时库存。四张原图按字节复制并保留原有 XMP，来源及哈希见[图片追溯](02_开发记录/验收证据/20261110_产品对齐/bq1003-source-image-lineage.json)。

网站提交 `0932308` 对应 EdgeOne 生产部署 `dp0nimj8wpgt`，正式站 `2026-11-11.8` 已回读 [BQ1003](https://www.beiqiang.online/products/bq1003/) 的 5 个五语详情页、4 张网页图、5 个产品册页、5 个询价页和 5 份版本化下载；工作台已匹配 HR003、三条国际站链接和网站投影。正式浏览器逐色检查图片，并将红色款加入本地询价清单，未发送真实询价。五份 PDF 各有 157 个不重复身份与对应语种产品链接，中英各 34 页、德法西各 42 页；新增款五语版面经目视检查，785 条本地静态产品路由核对通过。隔离构建测试 566 项通过、8 项跳过，lint 0 错误、9 条既有图片警告。[正式验收](02_开发记录/验收证据/20261110_产品对齐/bq1003-20261111-production-verification.json)

**2026-11-11 正式上线及验收：** BQ-LQ02507、BQ-LQ02508、BQ-LQ2559、BQ-LQ061、BQ-W5998 已进入正式站 `2026-11-11.4`，网站共 154 款。逐项回读五款 25 个英／中／德／法／西页面、20 张网页图、5 份现有产品册和 5 条本地工作台身份／国际站 ID／网站投影，均通过；英中页面链接至各自国际站商品，德法西页面链接至相应语言询价页。隔离浏览器在正式站逐款选择实际颜色，确认主图和询价清单均保留对应款号、颜色与图片；未发送真实询价。首次回读中网络超时的 3 个页面和 3 份产品册已单独复查通过。[正式验收回执](02_开发记录/验收证据/20261110_产品对齐/five-products-production-verification.json)

**EdgeOne 构建恢复：**此前 GitHub 自动构建确已触发，最新失败记录 `dph703bb11mt` 对应网站提交 `f362dc4`，日志显示复制静态产物时磁盘空间不足（`ENOSPC`），后续云函数文件写入随之失败。网站提交 `4fa10ed` 将同一项目内的静态目录复制改为移动，避免多占一份约 332 MiB 的产物；隔离构建中的 4,135 个文件在移动前后总哈希一致，相关 20 项测试通过。自动生产部署 `dpen3d1dum3c` 于 06:55 UTC 返回 `Success`，正式域名及 EdgeOne 默认域名最终均回读 `2026-11-11.4`；没有重启服务或更改账户和安全配置。

**154 款阶段的产品册验收：**官网既有英／中／德／法／西下载产品册曾从 149 款更新至 154 款，包含 BQ-LQ02507、BQ-LQ02508、BQ-LQ2559、BQ-LQ061、BQ-W5998；该阶段中英各 33 页，德法西各 41 页。每本按 PDF 实际文本核对 154 个身份各出现一次、每个型号链接到对应语言详情页；五款 25 个语言卡片的文案、颜色、尺码及嵌入图片经逐项比对和 10 页目视检查，询价链接和 770 条本地静态商品路由亦核对。官网 5 个产品册页、5 个询价页及 5 份版本化下载均正式回读通过，PDF 哈希与已验文件一致。[正式回读证据](02_开发记录/验收证据/20261110_产品对齐/catalogue-154-production-verification.json) 网站提交 `1d80e74`，EdgeOne 部署 `dpea78rh8vwk` 为 `Success`；隔离构建测试 564 项通过、8 项跳过，lint 0 错误、9 条既有图片警告。现行数量见上方更新。

上述更新仅覆盖网站既有下载功能；负责人确认搜鞋网图片用于独立站，不自动扩展到邮件外发、第三方平台或其他独立分发。下载产品册选款与单款／比较页打印照片选款已拆开：本批五款的既有打印表现不变。生成过程未修改 BQ-LQ1026 原图及署名元数据，原文件 SHA256 保持 `453884a6aa8c21c694018afb552ae1504f6c803b54af8c13775b28e93ffd69a6`。

本批复用产品中心和国际站对应关系。2026-11-11 04:42 UTC 官方回读 02507、02508、2559 三条商品均 `approved/Y`；前两款为棕／蓝，2559 为黑／卡其，各 20 个色码组合，均不代表实时库存。02507/02508 生成公开副本时仅去掉包含定位／设备标识的 EXIF，保留 XMP、IPTC、ICC，并确认像素及尺寸不变；2559 所选图保持原件，[素材来源与哈希](02_开发记录/验收证据/20261110_产品对齐/lq-0250x-2559-source-image-lineage.json)留档。LQ061、W5998 的 8 张图片按来源逐字节复制，[来源与哈希](02_开发记录/验收证据/20261110_产品对齐/lq061-w5998-source-image-lineage.json)留档。

按 2026-11-10 15:46 UTC 国际站完整快照与 154 款阶段网站对账：482 条展示链接对应 247 个产品身份，当时 154 个身份已进入网站、93 个待处理；现行差额见上方，不因快照未检出而自动下架。2026-11-11 04:37 UTC 官方回读 BQ-LQ061、BQ-W5998 均为 `approved/Y`，分别为 3 色 / 39 组及 2 色 / 22 组，平台色码不代表现货；前者原记录 EU 36–48，后者色码字段虽名 EUR Size，值是 `Size 35` 等原始标签，不能擅自称已核欧码。

**BQ-LQ1026 公开图片元数据专项，仅只读：**正式页面和 JSON-LD 引用的 `/catalog/bq-lq1026/01_main.jpg` 含摄影署名与版权联系线索，联系方式存在于 EXIF、IPTC、XMP 的版权字段；没有证据证明它是供应商联系方式或直接暴露供货关系。六张原 JPEG、六张网页 WebP、六张小图 WebP 和一张缩略图均返回 200；其余五张 JPEG 未检出同一联系值及上述版权／署名值，13 张 WebP 未检出该联系值或版权／署名字段。本专项没有修改图片、剥除元数据、擦除署名或下架；如需改变版权标识，应先弄清其归属和处理依据。

**原 8 款五语草稿：BQ1013 已上线，其余 7 款待处理。** BQ1005、BQ1011、BQ1013、BQ1017 分别复用产品中心 HR005、HR011、HR013、HR017 原身份；每款有三条国际站链接，不能拆成三款。另有 BQ-LQ2667、BQ-MJ9968、BQ-NS003、BQ042 各一条。2026-11-11 03:57 UTC 对各款下表首条 ID 的官方 `product.get` 回读均为 `approved/Y`，合计 233 个色码组合；四个 HR 身份的其余八条链接状态依据 2026-11-10 全量快照，不将该快照误作本次字段回读。这八款当时本地工作台已回读原身份、现行型号及对应 ID，网站状态为 `not_in_subset`；BQ1013 现已上线，其余款继续按具体资料推进。

| 现行型号 / 主库身份 | 原国际站 ID（首条为本次回读） | 已回读色码与对应依据 |
| --- | --- | --- |
| BQ1005 / HR005 | `1601943335751`、`1601943353831`、`1601943444273` | 黑、棕，各 EU 38–46；已采用[丰收 627](https://fsxy.sooxie.com/detail/2496290)，不得混用旧款图文。 |
| BQ1011 / HR011 | `1601943501378`、`1601943406882`、`1601943513336` | 白、米黄，各供方尺码标签 39–44；已采用[卡特 2081](https://kate.sooxie.com/detail/2582530)。 |
| BQ1013 / HR013（已上线） | `1601943542214`、`1601943514448`、`1601943543192` | 沙、酒红、黑，各供方尺码标签 36–48；已采用[仁里 2269](https://renli.sooxie.com/detail/2547894)。 |
| BQ1017 / HR017 | `1601943484872`、`1601943583193`、`1601943459958` | 黑、黄、卡其、酒红，各尺码标签 38–44；已采用[宇泰 A1003](https://yut.sooxie.com/detail/2470645)。本次正式值是数字标签，暂不改写成已核欧码。 |
| BQ-LQ2667 | `1601973009551` | 黑，EU 39–48；已采用[路崎 2667](https://luqi.sooxie.com/detail/2561050)。来源另列黑色加绒，正式 SKU 不区分，不能判定其内里版本。 |
| BQ-MJ9968 | `1601969788941` | 灰、绿、蓝，各尺码标签 35–40；已有已采用来源，正式鞋面字段仅为 Synthetic。 |
| BQ-NS003 | `1601970690721` | 黑白、灰、全黑、绿、玫红、卡其各尺码标签 35–45，紫色 35–43；已有已采用来源。 |
| BQ042 / 206 | `10000047166193` | 黑白、全黑、米色，各 EU 35–45；主库仅 `MAPPED`、未记录已采用来源，现有历史来源不等于已核当前供货。 |

<details>
<summary>八款五语标题及颜色草稿（未上线）</summary>

| 型号 | 中文 | English | Deutsch | Français | Español |
| --- | --- | --- | --- | --- | --- |
| BQ1005 | 男士包头流苏穆勒鞋 | Men's Closed-Toe Tassel Mules | Herren-Mules mit geschlossener Spitze und Quasten | Mules pour homme à bout fermé et à glands | Mules de hombre con puntera cerrada y borlas |
| BQ1011 | 厚底低帮系带休闲鞋 | Chunky-Sole Low-Top Lace-Up Shoes | Niedrige Schnürschuhe mit markanter Sohle | Chaussures basses à lacets et semelle épaisse | Calzado bajo de cordones con suela gruesa |
| BQ1013 | 单扣套脚休闲鞋，鞋底缝线设计 | Slip-On Casual Shoes with Buckle and Sole Stitching | Slipper mit Schnalle und Sohlennaht | Chaussures à enfiler avec boucle et couture de semelle | Calzado sin cordones con hebilla y costura en la suela |
| BQ1017 | 铆钉宽带夹趾拖鞋 | Wide-Strap Thong Sandals with Rivet Detail | Zehentrenner mit breitem Riemen und Nietendetails | Sandales à entre-doigts avec bride large et rivets | Sandalias de dedo con tira ancha y remaches |
| BQ-LQ2667 | 男士低帮系带休闲步行鞋 | Men's Low-Top Lace-Up Casual Walking Shoes | Herren-Schnürschuhe für Alltag und Spaziergänge | Chaussures basses à lacets pour homme, pour la marche au quotidien | Zapatillas bajas con cordones para hombre, para caminar a diario |
| BQ-MJ9968 | 拼色搭扣玛丽珍平底鞋 | Colorblock Mary Jane Flats with Hook-and-Loop Strap | Flache Mary-Jane-Schuhe mit Klettverschluss und Farbeinsätzen | Babies plates à bride auto-agrippante et empiècements contrastés | Zapatos planos Mary Jane con tira autoadherente y paneles de contraste |
| BQ-NS003 | 针织套脚休闲鞋 | Knit Slip-On Casual Shoes | Legere Schlupfschuhe aus Strick | Chaussures décontractées à enfiler en maille | Zapatos casuales de punto sin cordones |
| BQ042 | 系带针织低帮休闲鞋 | Knit Lace-Up Low-Top Shoes | Niedrige Schnürschuhe mit Strick-Obermaterial | Chaussures basses à lacets en maille | Zapatillas bajas de punto con cordones |

| 型号 | 中文颜色 | English | Deutsch | Français | Español |
| --- | --- | --- | --- | --- | --- |
| BQ1005 | 黑、棕 | Black, Brown | Schwarz, Braun | Noir, marron | Negro, marrón |
| BQ1011 | 白、米黄 | White, Beige | Weiß, Beige | Blanc, beige | Blanco, beige |
| BQ1013 | 沙、酒红、黑 | Sand, Wine Red, Black | Sand, Weinrot, Schwarz | Sable, bordeaux, noir | Arena, burdeos, negro |
| BQ1017 | 黑、黄、卡其、酒红 | Black, Yellow, Khaki, Wine Red | Schwarz, Gelb, Khaki, Weinrot | Noir, jaune, kaki, bordeaux | Negro, amarillo, caqui, burdeos |
| BQ-LQ2667 | 黑 | Black | Schwarz | Noir | Negro |
| BQ-MJ9968 | 灰、绿、蓝 | Grey, Green, Blue | Grau, Grün, Blau | Gris, vert, bleu | Gris, verde, azul |
| BQ-NS003 | 黑白、灰、全黑、绿、玫红、紫、卡其 | Black/White, Grey, All Black, Green, Rose Red, Purple, Khaki | Schwarz/Weiß, Grau, ganz Schwarz, Grün, Rosenrot, Violett, Khaki | Noir/blanc, gris, noir intégral, vert, rose vif, violet, kaki | Negro/blanco, gris, negro integral, verde, rosa intenso, morado, caqui |
| BQ042 | 黑白、全黑、米色 | Black/White, All Black, Beige | Schwarz/Weiß, ganz Schwarz, Beige | Noir/blanc, noir intégral, beige | Negro/blanco, negro integral, beige |

尺码见上表；标签不自动换算成欧码。色码为平台商品配置，不代表现货或承诺供货，订单与合脚需另核。

</details>

该批十条完整正式回执（含现已上线的 BQ1003 和 BQ-LQ2633）留本机 `02_开发记录/验收证据/.local/20261111_待补图正式回读/`，文件以商品 ID 和 `20261111T0357…Z` 时间命名。已按每个 SKU 而非仅 SKU 数量检查色码组合、原身份和本地渠道映射；原始回执不推送公开仓库。

<details>
<summary>八款逐图和版本问题</summary>

负责人已确认搜鞋网商品图片可用于贝强独立站；下列原图仍须核对具体款式、配色、版本和可见标识。来源记录与哈希用于追溯，独立分发产品册的使用范围不在本次明确用途内：

- BQ1005 可复用 `02_Alibaba运营/05_扩品工程/执行记录/HR实源替换/HR005/.local/搜鞋替代候选/627_来源图/` 的 `main_02.jpg` 黑、`main_03.jpg`／`main_04.jpg` 棕；本地 `main_05.jpg` 较小，同一图片 ID 的[公开高清原图](https://images.xiecdn.com/FSXY/sz9bug0iqhos0e6kjh1p1smik2go2her.jpg!bac)只读回读为 800×800、SHA256 `05048839697c2e49e3dc30661371d686617c317b246f41a3b5f294c0b3cc330c`，尚未保存。`main_01.jpg` 含设备序列号；不能混入旧款蓝／卡其配色。
- BQ1011 原图在 `01_产品资产/01_原始素材/2081_卡特_2026-11-03/`，白 `00.jpg`、米 `18.jpg`；鞋舌有文字，归属未核。BQ1013 的同款图可从 `02_Alibaba运营/05_扩品工程/执行记录/HR实源替换/HR013/.local/搜鞋替代候选/2269/` 复用 `11.jpg` 沙、`13.jpg` 酒红、`18.jpg`／`19.jpg` 黑；四图未发现人脸、明显第三方标识或设备序列号／GPS／联系方式字段。同目录 `23–28.jpg` 有 GPS、机主及设备序列号字段，避免直接公开；平台 `Label n (supplier size)` 不能自动换算成 EU。BQ1017 原图在 `01_产品资产/01_原始素材/A1003_宇泰_2026-11-04/`，黑 `16.jpg`、黄 `20.jpg`、卡其 `03.jpg`、酒红 `24.jpg`；部分详情仅 480px。
- BQ-LQ2667 的无人主图原件虽保存在 `图片/2588-1/04.jpg`，其 URL 与 2667 供方主图一致，但仍需核对应版本；来源另列普通及加绒内里，不能据平台单一黑色 SKU 推定具体版本。
- BQ-MJ9968 三色同框原图为 `%USERPROFILE%/Documents/Codex/2026-10-02/task-7/MaryJane_selection/9968/published/03.jpg`；各色独图含人物腿部。BQ-NS003 的 Green、Rose Red、Purple 正式色图绑定历史 `05_AI候选` 处理稿，不能称作原拍；Pink 不能借用 Purple 图，需补各色可用原片。来源“飞织鞋面、MD 大底”与平台把 `Knitted textile (fiber unspecified)` 写在中底字段的记录不同，不由此推定中底材料。
- BQ042 历史色图存在浅色原图“白色”与平台 Beige 的名称差异；旧修复记录显示黑白色处理图曾定点清除后跟星形标记，不能据此认定原鞋无标识，需核未改标识原片和当前来源。

用于独立站时按负责人确认继续逐色、版本及可见标识核对；如需独立分发产品册，另处理其用途范围，不将该事项作为官网页面前置。

</details>

本次权限依据检索覆盖 BQ032、BQ034、BQ035、BQ039，HR001–010 中尚未上站的九款，HR011–021、025–028、033、034、042、044、054，路崎 061、2588-1、2598、2633、2667，ABH219、D805、MJ9968、WBF2888、NS003，以及部分 BQ042–061；查阅了对应产品中心、来源包、图片索引、相关渠道资料及可定位的业务文档。这段是负责人确认官网用途之前的检索记录；现在不再以缺单独授权链接阻塞搜鞋网图片用于官网。继续按剩余身份核真实图款和销售版本，独立分发产品册用途另处理。

BQ032 / ZX2212 是一个产品身份，对应 `10000046653813`、`1601939722196`、`1601939751023`、`1601939651515` 四条历史链接；其中 Black／All Black 是同图的名称差异。2026-10-20 来源记 EVA 外底，2026-11-02 四条平台字段均记 Rubber 外底，主链接中底 EVA、其余三条中底 Rubber；材料和图片版本继续核，不把链接拆为四款或据旧字段覆盖现状。

**原四款草稿：BQ-LQ2588-1 已上线，BQ034、BQ035、BQ039 待处理。** 三款 BQ 复用负责人 2026-11-02 确认的本厂商品身份；路崎款复用已采用的 [2588-1 来源](https://luqi.sooxie.com/detail/2412409)。2026-11-11 03:49 UTC 官方 `product.get` 四条均为 `approved/Y`，色码分别为 33、18、22、27 个组合；这是当时平台配置，不等于现货承诺。工作台当时已回读原产品和对应 ID，网站投影均为 `not_in_subset`；现 BQ-LQ2588-1 已上线，其余三款继续核对。路崎款的宽鞋头分类有[负责人分类事实确认](../02_Alibaba运营/05_扩品工程/执行记录/路崎宽头户外_2026-10-08/负责人分类事实确认.json)，并非从照片推断宽楦；合脚仍由样品确认。

| 产品及国际站 ID | 正式色码 | 资料边界 |
| --- | --- | --- |
| BQ034 / T5505 · `11000037600317` | 黑、灰、棕，各尺码标签 35–45 | 平台外底 EVA；平台内里 Mesh 与 2026-10-20 来源“无内里”不同，草稿不定论内里。 |
| BQ035 / A001 · `10000046705043` | 灰、深蓝，各尺码标签 37–45 | 负责人于 2026-10-21 针对 A001 拖鞋类目确认鞋底 EVA；本次国际站中底、外底为 Rubber，原包曾记橡塑。保留两边记录，草稿暂不合并成唯一材料结论。 |
| BQ039 / 155 · `1601924755368` | 黑、红，各尺码标签 35–45 | 负责人 2026-10-21 按实物确认鞋底 EVA、鞋面及靴筒无内里；平台写分段发泡外底和 Textile Lining。发泡与 EVA 不必然冲突，内里记录需区分；155 不与 A155 合款。 |
| BQ-LQ2588-1（已上线） · `1601973772709` | White、BlackWhite、AllBlack，各 EU 39–47 | 平台材料未指定；三色合图与单色图须逐色对应，不从照片猜材料。 |

<details>
<summary>四款五语标题与色码草稿（未上线）</summary>

| 型号 | 中文 | English | Deutsch | Français | Español |
| --- | --- | --- | --- | --- | --- |
| BQ034 | 针织套脚步行鞋，EVA 鞋底 | Knit Slip-On Walking Shoes with EVA Sole | Strick-Slipper mit EVA-Sohle | Chaussures en maille à enfiler, semelle EVA | Calzado de punto sin cordones con suela de EVA |
| BQ035 | 针织包头半拖鞋 | Knit Closed-Toe Backless Mules | Geschlossene Mules aus Strick | Mules en maille à bout fermé | Mules de punto con puntera cerrada |
| BQ039 | 弹力针织高帮套脚鞋，EVA 鞋底 | Stretch-Knit High-Top Slip-On Shoes with EVA Sole | Hohe Schlupfschuhe aus elastischem Strick mit EVA-Sohle | Chaussures montantes en maille extensible à enfiler, semelle EVA | Calzado alto de punto elástico sin cordones con suela de EVA |
| BQ-LQ2588-1 | 宽鞋头厚底系带休闲鞋 | Wide-Toe Chunky-Sole Lace-Up Shoes | Schnürschuhe mit weiter Zehenbox und markanter Sohle | Chaussures à lacets, bout large et semelle épaisse | Calzado con cordones, puntera ancha y suela gruesa |

| 型号 | 中文色码 | English | Deutsch | Français | Español |
| --- | --- | --- | --- | --- | --- |
| BQ034 | 黑、灰、棕；尺码标签 35–45。 | Black, Grey, Brown; size labels 35–45. | Schwarz, Grau, Braun; Größenetiketten 35–45. | Noir, gris, marron ; pointures indiquées 35–45. | Negro, gris, marrón; tallas indicadas 35–45. |
| BQ035 | 灰、深蓝；尺码 37–45。 | Grey, Deep Blue; size labels 37–45. | Grau, Dunkelblau; Größenetiketten 37–45. | Gris, bleu foncé ; pointures indiquées 37–45. | Gris, azul oscuro; tallas indicadas 37–45. |
| BQ039 | 黑、红；尺码 35–45。 | Black, Red; size labels 35–45. | Schwarz, Rot; Größenetiketten 35–45. | Noir, rouge ; pointures indiquées 35–45. | Negro, rojo; tallas indicadas 35–45. |
| BQ-LQ2588-1 | 白、黑白、全黑；EU 39–47。 | White, Black/White, All Black; EU 39–47. | Weiß, Schwarz/Weiß, ganz Schwarz; EU 39–47. | Blanc, noir/blanc, noir intégral ; EU 39–47. | Blanco, negro/blanco, negro integral; EU 39–47. |

正式色名 `BlackWhite`、`AllBlack` 仅为阅读增加分隔，不把颜色或链接拆为新款。以上为编辑稿，供货、尺码及合脚按订单和样品确认。

</details>

原五款正式回执（含现已上线的 BQ-LQ2598 和 BQ-LQ2588-1）保存在本地 `02_开发记录/验收证据/.local/20261111_待补图正式回读/`。按原顺序 BQ034、BQ035、BQ039、BQ-LQ2598、BQ-LQ2588-1 的 SHA256 分别为 `f12efdf48a99ac78d33f3dc6399890f1d8684586b16eb97bdffa356edf0a6bf4`、`c4cf475aaed984700537d19c54b28d29b3a60985fc5ea022296d8ddbe4345f4d`、`d609ec2d9ff6bfe23a19bb9a0e4a30cc1d173642866255df44d1c81dd4b5ea6f`、`3664350f80e7afa27cb577e0a9ef6b5c2bfb9f6b5482d30411e0c5071af24cfe`、`cba99738baa498eae0c71f2bd87bc59ad87893cdd5d743e4016c0914161857ff`。

<details>
<summary>四款候选图片及下一步确认范围</summary>

已核对下列 11 张图片字节与既有来源记录；负责人现已确认搜鞋网商品图可用于独立站，继续逐图核款式、颜色和版本。独立分发产品册及其他用途不由此次说明自动覆盖；有更清晰的同款原片可按实际版本替换候选。

- BQ034：离线归档 `E:/贝强离线归档/产品旧档/历史制作资料/00_最终上传/BQ034_T5505/03_颜色图/` 的 `01_black.jpg`、`02_grey.jpg`、`03_brown.jpg`。
- BQ035：同一离线归档下 `BQ035_A001/03_颜色图/` 的 `01_grey.jpg`、`02_deep_blue.jpg`。
- BQ039：[成品素材目录](../01_产品资产/02_成品素材/BQ039/)的 `BQ039_474bb642b7e46370.png`、`BQ039_cd6faacd2805d240.png`。这两张为国内渠道既有裁切稿，来源是历史 155 原图 `18.webp`、`19.webp`，原图带宣传文字；不得把裁切或文字消失当作权属证明。
- BQ-LQ2588-1：[原图目录](../02_Alibaba运营/05_扩品工程/执行记录/路崎宽头户外_2026-10-08/图片/2588-1/)可复用 `15.jpg`／`21.jpg` 黑白、`22.jpg` 白、`24.jpg` 全黑；四图未发现人脸、明显第三方标识或设备序列号／GPS／联系方式。`01.jpg` 含设备序列号，`02–06.jpg` 为其他款推荐，`26.jpg`／`27.jpg` 为多色拼图，不能当作单色图。

</details>

**149 款版本时的历史对账；现行覆盖见文首。** 国际站会话于 2026-11-10 15:46 UTC 取回完整官方目录：490 个唯一商品 ID，其中 482 条 `approved/Y`、6 条 `approved/N`、2 条 `tbd/N`；另有 29 条本地历史 ID 本次未检出，不能据此认定已下架。[原始目录及状态对比](../02_Alibaba运营/01_店铺与全店诊断/经营诊断证据/20261110_商品状态只读/catalog_escalated/status_snapshot.json)保留时间及取数边界。按产品中心明确身份归并，482 条展示链接属于 247 个产品身份；网站 149 款覆盖其中 149 个身份，另有 **98 个身份 / 153 条展示链接**尚未进入网站投影，其中 68 个身份对应一条、30 个对应多条链接。此差异按当次平台状态与本地身份计算，不是 98 款已完成选款、可直接发布的结论。使用同一完整 `catalog.json` 和现行主档复跑只读对账，得到相同 98 身份：本次十五款草稿涉及其中 15 个身份 / 25 条链接；此前五款草稿涉及 5 个身份 / 5 条链接。除这二十款外，该快照还有 78 个身份 / 123 条链接未纳入上述草稿，不能据此推定它们的图片权利或实际供货状态。

**原备网站草稿：BQ-LQ02507、BQ-LQ02508（现已完成正式部署）。** 两款分别复用产品中心原身份，使用国际站链接 `1601973978339`、`1601973995230`，不是新建商品或同款多链接。2026-11-11 02:38 UTC 两条 `product.get` 正式回读均为 `approved/Y`，各有棕色、蓝色各 EU 39–48 共 20 个 SKU；中底、外底、内里均未指定，网站草稿不猜材料或实时库存。02507 是侧拉链加系带，02508 为系带无侧拉链；供货依据分别回[02507 商品档案](../02_Alibaba运营/02_单品优化记录/商品档案/BQ-LQ02507/README.md)与[02508 商品档案](../02_Alibaba运营/02_单品优化记录/商品档案/BQ-LQ02508/README.md)。两条完整正式回执保存在本机 `02_开发记录/验收证据/.local/20261111_待补图正式回读/`，SHA256 分别为 `742cb2301d90a8776f78f801fc904f81728759236b25a5d33678fe17d51c3ed5`、`214e89bfd8d9d1eb04c38e106da6dc751cbc2390804015ea85b208d381d06e64`。

02507 拟选原图 `19.jpg`（棕）、`24.jpg`（蓝），02508 拟选原图 `18.jpg`（棕）、`22.jpg`（蓝），均在[路崎原图目录](../02_Alibaba运营/05_扩品工程/执行记录/路崎宽头户外_2026-10-08/图片/)对应款号内；四图原尺寸已查看，本机 SHA256 与各自[02507 正式图片银行映射](../02_Alibaba运营/05_扩品工程/执行记录/路崎宽头户外_2026-10-08/02507准备/正式图片银行映射.json)和[02508 正式图片银行映射](../02_Alibaba运营/05_扩品工程/执行记录/路崎宽头户外_2026-10-08/02508准备/正式图片银行映射.json)一致。四图无人物、未观察到可识别第三方字标；02507 五金局部太小，不能判断看不清的细节。负责人已确认搜鞋网商品图可用于独立站；独立分发产品册用途另行处理。原图 02–06 是其他推荐款，不混用。以下是准备时的编辑草稿；目前正式站与工作台投影已更新，五语网站下载产品册已纳入这两款。

| 语言 | BQ-LQ02507 文案草稿 | BQ-LQ02508 文案草稿 |
| --- | --- | --- |
| 中文 | 侧拉链系带低帮休闲鞋。棕色或蓝色，EU 39–48；请结合样品及订单确认合脚和供货。 | 拼片系带低帮休闲鞋。棕色或蓝色，EU 39–48；请结合样品及订单确认合脚和供货。 |
| English | Side-Zip Lace-Up Low-Top Shoes. Brown or Blue, EU 39–48; confirm sample fit and order availability. | Panelled Lace-Up Low-Top Shoes. Brown or Blue, EU 39–48; confirm sample fit and order availability. |
| Deutsch | Niedrige Schnürschuhe mit seitlichem Reißverschluss. Braun oder Blau, EU 39–48; Passform am Muster und Verfügbarkeit zur Bestellung bestätigen. | Niedrige Schnürschuhe mit mehrteiligen Einsätzen. Braun oder Blau, EU 39–48; Passform am Muster und Verfügbarkeit zur Bestellung bestätigen. |
| Français | Chaussures basses à lacets et zip latéral. Marron ou bleu, EU 39–48 ; confirmer le chaussant sur échantillon et la disponibilité pour la commande. | Chaussures basses à lacets et empiècements. Marron ou bleu, EU 39–48 ; confirmer le chaussant sur échantillon et la disponibilité pour la commande. |
| Español | Calzado bajo de cordones con cremallera lateral. Marrón o azul, EU 39–48; confirme el ajuste con una muestra y la disponibilidad para el pedido. | Calzado bajo de cordones con paneles. Marrón o azul, EU 39–48; confirme el ajuste con una muestra y la disponibilidad para el pedido. |

**另备 BQ033、BQ037、BQ038 五语文案，仍未发布。** 产品中心记录负责人确认三款为本厂产品，拟分别指向国际站 `1601924345456`、`1601924347721`、`1601924732369`。2026-11-11 02:42–02:43 UTC 三款官方只读回读均为 `approved/Y`；运行中的本地工作台已匹配各自身份和上述 ID，网站仍为 `not_in_subset`。完整回执在本机 `02_开发记录/验收证据/.local/20261111_待补图正式回读/`，SHA256 依次为 `58928f0d0a4b2566dff3dc6ffa01cc3a23e21871c1e67c75d3747876fcfdcf01`、`1c8a0e5efe4a20bd43141a72001d827f68234e5018d2f0f66e657d894bd3a745`、`70d7fc39d5ff3c31417f32a65f99a63deaacd7002235b1f02112c18b3abb0364`。尺码保留正式属性中的原始数字标签，不擅自换算；三款共 44、72、55 个颜色尺码组合，不把颜色或加绒版本算成独立款。

历史颜色图包可在 `E:/贝强离线归档/产品旧档/历史制作资料/00_最终上传/` 的 `BQ033_T5503`、`BQ037_H7116`、`BQ038_M889` 中按对应款查到。BQ033 黑、米白、粉三色归档图与正式色图哈希一致，灰色归档图与正式色图不同，待按版本单独核；BQ037 黑白普通与加绒、BQ038 的黑白普通与加绒及全黑普通与加绒分别共用同一图片字节，不能将外观图写成加绒内里实拍。负责人已确认搜鞋网商品图可用于独立站；逐色及普通／加绒版本复核后进入网站投影。独立分发产品册用途不由此次确认自动覆盖。

逐款补证位置：BQ033 的历史灰图 `02_grey.jpg` SHA256 为 `f7cd80c8e0406d6b16f075af71d965d33b015a3e80021c975bfdd067e2c2d95a`，正式灰图索引为 `449c211751fe71080efae1e0348d87b4cd1c716c7c232c740f3d9d5b3a972b51`，已查本地 72 张相关图仍未找到同哈希文件，不据此回改平台。BQ037 各色成品中黑白鞋头、白色鞋底有截断，完整六色来源图为 `E:/贝强离线归档/产品旧档/历史输入/待审_搜鞋网_2026-08-14/H7116/原图/12.webp`，SHA256 `25e1bcf5372f48ec4523c3139df48df957f9d387c15f88ffd8c650f554071430`；BQ038 的白色成品有截断，完整三色来源图为同一历史输入目录的 `M889/原图/11.webp`，SHA256 `e343af232299f50151dc2eb4a2b5396febc4b1c85df586deeaa2682aeeecaf57`。负责人已确认搜鞋网商品图可用于独立站；产品册独立分发用途另处理。

另核 BQ040 / 1689（`1601924792152`）和 BQ041 / 202（`10000047127570`）：历史资料对应贝强搜鞋店商品，两款当前产品中心仍为 `MAPPED`，未记录已采用来源 ID，不能据旧店页面断定当前供货。2026-10-21 正式字段记录 BQ040 三色尺码 39–45、BQ041 三色尺码 31–40；尚未以本次接口重读。BQ041 三色原图及处理图在上述离线归档的 `历史输入/待审_搜鞋网_2026-08-14/202/原图` 与 `历史制作资料/00_最终上传/BQ041_202/03_颜色图` 中；色图无人物，当前来源和对应销售版本仍需确认。BQ040 的部分色图包含人物、文案或图形，旧主图历史加工方式记录有歧义，暂不直接复用。两款均未进入网站草稿或正式目录。

<details>
<summary>BQ033、BQ037、BQ038 五语标题及色码草稿（未上线）</summary>

| 款号 | 中文 | English | Deutsch | Français | Español |
| --- | --- | --- | --- | --- | --- |
| BQ033 | 针织系带鞋，发泡鞋底 | Knit Lace-Up Shoes with Foamed Sole | Strick-Schnürschuhe mit Schaumsohle | Chaussures en maille à lacets et semelle mousse | Calzado de punto con cordones y suela de espuma |
| BQ037 | 针织系带鞋，撞色鞋头 | Knit Lace-Up Shoes with Contrast Toe | Strick-Schnürschuhe mit Kontrastkappe | Chaussures en maille à lacets et bout contrasté | Calzado de punto con cordones y puntera en contraste |
| BQ038 | 针织系带鞋，EVA 鞋底 | Knit Lace-Up Shoes with EVA Sole | Strick-Schnürschuhe mit EVA-Sohle | Chaussures en maille à lacets et semelle EVA | Calzado de punto con cordones y suela de EVA |

| 语言 | BQ033 色码 | BQ037 色码 | BQ038 色码 |
| --- | --- | --- | --- |
| 中文 | 黑、粉、米白、灰；尺码标签 35–45。 | 黑白、灰、白、蓝、绿及黑白加绒：尺码标签 35–45；紫色：35–40。 | 黑白、白、全黑；黑白及全黑另有加绒，尺码标签 35–45。 |
| English | Black, Pink, Off White and Grey; size labels 35–45. | Black/White, Grey, White, Blue, Green and Black/White Fleece: size labels 35–45; Purple: 35–40. | Black/White, White and All Black; Black/White and All Black are also offered with fleece lining; size labels 35–45. |
| Deutsch | Schwarz, Rosa, gebrochenes Weiß und Grau; Größenetiketten 35–45. | Schwarz/Weiß, Grau, Weiß, Blau, Grün und Schwarz/Weiß mit Fleecefutter: Größenetiketten 35–45; Violett: 35–40. | Schwarz/Weiß, Weiß und ganz Schwarz; Schwarz/Weiß und ganz Schwarz auch mit Fleecefutter; Größenetiketten 35–45. |
| Français | Noir, rose, blanc cassé et gris ; pointures indiquées 35–45. | Noir/blanc, gris, blanc, bleu, vert et noir/blanc fourré : pointures indiquées 35–45 ; violet : 35–40. | Noir/blanc, blanc et noir intégral ; noir/blanc et noir intégral aussi fourrés ; pointures indiquées 35–45. |
| Español | Negro, rosa, blanco roto y gris; tallas indicadas 35–45. | Negro/blanco, gris, blanco, azul, verde y negro/blanco con forro abrigado: tallas indicadas 35–45; morado: 35–40. | Negro/blanco, blanco y negro integral; negro/blanco y negro integral también con forro abrigado; tallas indicadas 35–45. |

</details>

本批 BQ-LQ018、BQ-LQ2572、BQ-LQ2578 分别对应既有身份 LQ-018、LQ-2572、LQ-2578，以及国际站 `1601974978404`、`1601974755167`、`1601974917344`；2026-11-11 逐款官方只读回读均为 `approved/Y`。018 四色 EU 37–48，仅采用有依据的橡胶外底；2572 米色和黑色 EU 39–46，宽鞋头、网面与 PU 外底有来源，合脚以样品确认；2578 三色 EU 39–46，贾卡织物鞋面、MD 中底和橡塑外底依正式字段记录。2572 的旧宣传图曾写 39–48，本次按当前来源和正式 SKU 展示 39–46。12 张原图按 [来源和 SHA256](02_开发记录/验收证据/20261110_产品对齐/lq-20261111-source-image-lineage.json) 留证，所选图未观察到明显第三方鞋标；部分 018、2578 图片有不含可识别人脸的手或腿部，摄影或模特使用许可未在现有材料中单独证明，未断言统一授权。2578 另有两张未选照片存在角度或版本疑问，本批未采用。

本地工作台只读接口已按三条原身份回读到对应网站投影及国际站 ID。完整构建及 558 项测试中 551 项通过、7 项数据库测试因未配置跳过；类型检查通过，lint 无错误、9 项既有图片警告；五语产品册已渲染检查。[正式回读](02_开发记录/验收证据/20261110_产品对齐/lq-20261111-production-verification.json)通过 15 个五语商品页面、12 张网页图、5 份产品册及 3 条本地映射核对；中英文页指向相应国际站商品，德法西语页保留各自语言询价入口。正式页实测 018 黑卡其、2572 黑色和 2578 浅灰色，均联动对应图片与询价颜色；工厂视频及中英文字幕版本一致性通过，未提交真实询盘。其他候选的具体图像、既有经营决定和版本疑问记录在 [逐款筛查证据](02_开发记录/验收证据/20261110_产品对齐/lq-20261111-screening-evidence.json)，只就有关图片和产品判断，不将个别疑点扩大为全部商品阻塞。

上一批新增 BQ-L3522 和 BQ-CS929 两个不同身份，对应国际站 `1601969920294`、`1601970118386`，在当次完整目录均为 `approved/Y`；2026-10-19 正式字段与来源分别支持牛反绒套脚鞋及网面系带鞋。各款均按三色、原始尺码标签 39–46 / 39–47 展示，提醒确认码制与样品测量；未将标签擅自换算成 EU。八张选用图未见明显第三方标识、无人物，分别按原 URL 和 SHA256 留下[L3522 图片来源](02_开发记录/验收证据/20261110_产品对齐/l3522-source-image-lineage.json)与[CS929 图片来源](02_开发记录/验收证据/20261110_产品对齐/cs929-source-image-lineage.json)。CS929 银色图保留原有 `MORE SHOW` 排版；原图已按字节纳入网站源码，原摄影权利与独立图片许可未在已审资料中单独证明。两款本地工作台已匹配网站投影及相应国际站 ID；五语产品册逐页检查，完整构建及 552 项测试中 545 项通过、7 项数据库测试因未配置跳过，lint 无错误、9 项既有图片警告。[正式回读](02_开发记录/验收证据/20261110_产品对齐/batch3-production-verification.json)通过两款共 10 个语言页面、八张网页图和五语 PDF 的核对；英中页的国际站商品直达链接正确，德法西页沿用本国语言询价入口。正式页分别选米色和银色后展示对应照片和询价颜色；工厂视频和中英文字幕版本一致，未提交真实询盘。

上一批另核 17 款，标识、图片使用或版本有明确疑点的款暂挂；图组不足者暂不纳入该批。逐款原图或记录、SHA256、判断边界见[筛查证据](02_开发记录/验收证据/20261110_产品对齐/batch3-screening-evidence.json)。其中 BQ-LQ1680（`1601980486423`）经国际站会话 2026-11-10 19:40 UTC 只读复核，买家页详情图仍将灰色写为 EU 33–48，正式 SKU 和买家选码面板为 EU 39–48；该差异尚未修复，由国际站会话按[原商品档案](../02_Alibaba运营/02_单品优化记录/商品档案/LQ-1680/README.md)继续处理。

BQ036 是负责人于 2026-11-02 明确确认的本厂款，产品中心将 HR039 与 BQ1039 历史别名合并为同一身份，四条国际站链接分别保留；网站选用 `1601924292931`。当前两色 EU 35–45、针织鞋面和 EVA 鞋底对应正式字段，六张选用图片均按原有店铺商品图库逐张核对并保留 SHA256；图片来源、对应历史商品及历史网站图片哈希见[BQ036 素材记录](02_开发记录/验收证据/20261110_产品对齐/bq036-source-image-lineage.json)。该记录能追溯店铺现用图，但未独立证明原摄影著作权，不能作为普遍图片权利结论；所选图中未观察到明显第三方标识。工作台本地已匹配 BQ036 并保留四个渠道 ID；五语目录已渲染核对，完整构建与 548 项测试中 541 项通过、7 项数据库测试因未配置跳过，lint 无错误、9 项既有图片警告。[正式验收](02_开发记录/验收证据/20261110_产品对齐/bq036-production-verification.json)回读五语商品页，并核对六张网页图及五语目录的哈希。英文、中文页的国际站商品链接指向选定 ID；德语、法语和西班牙语页沿用各自语言的询价入口，其目标均返回 200，但目前未设国际站商品直达链接。正式页选全黑后正确显示两张全黑图片，工厂视频和英中字幕的版本一致性检查通过，未提交真实询盘。

历史筛选中，BQ-LQ2559 的[供应商主图](../01_产品资产/01_原始素材/BQ-LQ2559/BQ-LQ2559_e25a0a844e78cb2c.jpg)含笔记本苹果标识，BQ-LQ2550 的[来源图](../01_产品资产/01_原始素材/BQ-LQ2550/BQ-LQ2550_f0efed461e8dfe73.jpg)含 `CAMEL OUTDOOR` 字样；BQ-LQ2417 的[来源图](../01_产品资产/01_原始素材/BQ-LQ2417/BQ-LQ2417_55a2795eaa6ede48.jpg)含 `TINGGUA` 小字，含义与权属不明；DZ14546082-A 的[来源图](../01_产品资产/01_原始素材/DZ14546082-A/DZ14546082-A_KB11/01.jpg)有星形旋钮图案，归属不明。BQ-LQ2550、BQ-LQ2417 和 DZ14546082-A 暂按各自标识及销售版本继续核对；BQ-LQ2559 已选另外四张同款图并完成正式上线验收；不凭外观认定侵权或授权，不擦除标识。BQ-LQ2593 已记录来源，仍需核对具体图款和销售版本，不据此推定可替代其他款。

按此前 149 款版本统计的 98 个待处理身份中，75 个状态为 `ADOPTED`、23 个为 `MAPPED`；27 个有可访问原包，96 个在素材索引中至少有四个可访问文件。文件可能含共用图和平台合成图，仍须逐张检查是否适合网站与对应颜色；BQ-FY3300、BQ-RF1105A 暂无索引素材，且本地旧状态为 `new/N` 与本次列表 `approved/Y` 不一致，需按精确 ID 核正式字段及素材。BQ1044 已换为新款但公开验收未完；BQ-LQ2583-1 的低清颜色图仍须核实。未进入网站的身份均需要创建和核对五语产品资料，不把索引文件数当作图片、语言或供货验收。

上一批新增 BQ-LQ02505、BQ-LQ2509、BQ-LQ029、BQ-LQ1026 和 BQ-LQ9705：分别对应五个已有产品身份、已采用供货来源及 `approved/Y` 国际站商品；28 张图片按[来源索引和 SHA256](02_开发记录/验收证据/20261110_产品对齐/lq-source-image-lineage.json)对应原图，未把颜色或不同链接算成新款。1026、9705 的黑色 EU 36–48、灰色 EU 39–48、酒红 EU 36–41 在五语页面按颜色说明；029 的网布或加绒是内里版本，按选定配置确认。运行中的本地工作台已通过只读接口回读五个原产品身份，均匹配对应网站投影；完整构建和 544 项测试中 537 项通过、7 项数据库测试因未配置跳过，lint 无错误、9 项既有图片警告。本地已实测颜色、图库和询价清单联动，并检查五语产品册；正式站 25 个语言页面已回读对应型号与尺码范围，五个国际站链接正确，28 张网页图片及五语 PDF 与发布文件的哈希一致；代表款的选色与图片联动正常。[正式回读证据](02_开发记录/验收证据/20261110_产品对齐/lq-production-verification.json)保留具体结果；未提交真实询盘。

新四款 BQ-LQ015、BQ-LQ2560、BQ-LQ2580、BQ-LQ2416 分别对应四个产品中心身份、已采用来源和快照中 `approved/Y` 的国际站商品，16 张原图的来源、SHA256、颜色及对应商品见[逐款记录](02_开发记录/验收证据/20261110_产品对齐/lq-batch2-source-image-lineage.json)。所选图片中未观察到明显第三方标识，但检查的记录没有找到独立图片使用授权，不能据此宣称权利已确认。2580 宽鞋头有来源文字依据，合脚程度仍以样品确认；2560 材料未明、2416 鞋面材料来源记录有冲突，均未填猜测值。五语产品册、颜色映射和本地工作台四款投影已核；重复同步无额外修改。完整构建与 546 项测试中 539 项通过、7 项数据库测试因未配置跳过，lint 无错误、9 项既有图片警告。正式站 20 个语言页面、16 张网页图及五语 PDF 与发布文件核对通过，本地工作台四款映射已回读；2580 选黑色后显示对应黑色图片。[验收记录](02_开发记录/验收证据/20261110_产品对齐/lq-batch2-production-verification.json)保留哈希及目录超时后的重试结果。正式站既有工厂视频与英中字幕的版本一致性检查通过；未提交真实询盘。

1026 来源图保留鞋侧实际小字、鞋底 `OUTDOOR` 及旋钮小图案；2026-10-15 的来源记录和 2026-11-10 国际站快照支持当时有该带标款及展示链接，不证明现货、接单、标识权属、图片使用授权或无标版本。02505、2509 的原图也有旋钮小图案，9705 有 `FASHION`、`OUTDOOR` 和旋钮图案；029 所选照片未观察到明显第三方标识。五款逐图检查范围和未查到的授权证据已写回[原图片来源记录](02_开发记录/验收证据/20261110_产品对齐/lq-source-image-lineage.json)，未擦除标识，也未推定侵权或授权；涉及销售版本、标识和图片使用时向供方确认。

BQ-9002 普通版已上线：复用产品中心现有身份与来源，保持它与 9002-1 加绒版分开；采用该款四张来源原图、两色、EU 38–47 及五语文案，完整目录生成并维护原始素材 SHA256。修正 BQ006 失效旧链接、BQ015 指向 BQ020 的错链，并补 BQ014、BQ020 及 BQ-9002 的指定链接；五个 ID 在当日完整目录均为 `approved/Y`。BQ014 曾因历史映射冲突使用店铺回退，本次以正式型号、平台图库 URL 与本地对应图片核对身份，不用标题相似替代款式核对。本地网站完整构建及测试 541 项中 534 项通过、7 项因未配置真实数据库跳过；五语 PDF、浏览器产品页及颜色加入询价流程已在本地抽查，未发送实际询盘。

上一正式版本已只读核验 BQ-9002 五语页面、五个国际站链接、四张网页图片及五语 PDF；图片和 PDF 均与源码文件 SHA256 一致。既有正式站版本及工厂视频、英中字幕的 `verify-deployment-parity` 检查通过；[逐项回读证据](02_开发记录/验收证据/20261110_产品对齐/release-verification.json)记录实际地址、产品 ID 和资产哈希。部署控制台未登录，未读取平台构建日志，发布状态以正式域名实际回读为依据。

BQ015 旧的“网布内里由阿里正本确认”来自曾被误认作该款的旧 ID，其现行图片和型号对应 BQ020；网站移除这条特定证据归属并保留所选内里材料的确认项。网站当前只展示三种有对应图片的配色，国际站该款已核六色；其余颜色实图、原记录中的弹力材料、EVA 和加绒版本仍需按 R1811 原件及当前订单适用范围复核，不能把一款旧 ID 的属性直接转给另一款。

只读对账及显式链接计划工具为 [sync_website_links.py](../08_工具链/06_工作区维护/sync_website_links.py)，方法见[网站运营与发布SOP](01_运营SOP/网站运营与发布SOP.md)。工具复用现有产品与渠道数据，不自动改商品事实；会在来源、网站文件或计划版本变化时拒绝覆盖，重复规划同一结果不产生修改。可重建的逐条差异和图片/PDF核验放在 `99_临时区/独立站产品对齐/`，不作为新的主库或实时状态。云端 Agent 目前未接入此对账或自动发布。

| 项目 | 入口或规则 |
| --- | --- |
| 本地源码 | [03_网站源码/](03_网站源码/)；独立管理提交、分支、测试和回滚 |
| GitHub | [beiqiang-footwear-site](https://github.com/421345308/beiqiang-footwear-site) |
| 生产分支 | `main` |
| 自动发布 | GitHub `main` 推送触发 EdgeOne 构建和发布；推送成功不等于部署已生效 |
| 正式域名 | [www.beiqiang.online](https://www.beiqiang.online/) |
| 网络可达性 | 不申请 ICP 备案；Pages 加速区域为「全球可用区（不含中国大陆）」；故障按目标地区、正式域名和当前部署核验 |

继续开发时在源码仓库核对当前分支、未提交改动和最新部署；入口不保存某次整理时的文件数量。

采购前台现提供中文、英文、德语、法语和西班牙语。新增语种覆盖首页、选款、产品详情、比较、询价、PDF目录及首次询价邮件回执；部分资源、工厂视频字幕及高级项目流程仍按中英文提供，入口须明确标注。覆盖范围、产品体验回改与正式域名验收见[产品与架构设计](02_开发记录/独立站产品与架构设计.md)。

### 访问与部署判断

负责人2026-10-18决定不做ICP备案，继续服务海外买家并维持不含中国大陆的加速区域。大陆访问异常不直接等同代码故障；排查仍按目标地区、实际域名/CDN及当前部署取证。历史IP和某次连接失败不保存为永久技术结论。

## 按任务读取

| 要解决的问题 | 权威记录 |
| --- | --- |
| 整站改版、专业文案、多语言与架构 | [独立站产品与架构设计](02_开发记录/独立站产品与架构设计.md)：2026-10-25现状审查、产品结构、语言方案、SEO/GEO与验收；设计与实施状态分开 |
| 当前搜索、渠道接入与下一动作 | [全渠道增长总控](../00_总控台/全渠道增长总控.md)、[独立站任务路由](AGENTS.md) |
| 搜索收录、SEO与AI可发现性方法 | [搜索运营SOP](01_运营SOP/搜索与AI可发现性运营.md)；当前数据与原始证据放 `03_搜索与渠道数据/`，增长总控只协调下一步 |
| 历史采购路径改版与发布验收 | [2026-09-08 初始化阶段采购路径优化](02_开发记录/2026-09-08_初始化阶段采购路径优化.md)：含 `2026-09-08.2` 和当时验证范围；当前上线版本须核最新远端与正式域名 |
| 商品公开范围与原始包对应 | [2026-09-08 网站货源核对](02_开发记录/2026-09-08_网站货源核对.md)：货源证据不能替代库存、规格、样品及交期确认 |
| 历史功能决策与阶段验收 | [历史发布与验收记录](02_开发记录/历史发布与验收记录.md)：按需查章节；其中款数、能力和验证范围是当时快照，商品范围以产品中心与实际网站字段为准 |
| 买家与业务员操作、历史阶段能力 | [功能总盘点与操作手册](02_开发记录/独立站商业化功能总盘点与操作手册_2026-08-23.md) |
| 当前流程、权限和异常处理 | [网站运营与发布SOP](01_运营SOP/网站运营与发布SOP.md)；历史证据单独查发布与验收记录 |
| 当前采购内容承接、开发与发布验收 | [采购内容承接与搜索改进](02_开发记录/采购内容承接与搜索改进.md)；旧执行计划保留当时研究证据 |

历史文档保留原确认时间和验收范围；功能存在、正式发布、真实询盘及商业结果分别判断。查找某项能力时搜索对应章节，不预读全部阶段历史。

## 开发与落盘

1. 在源码独立仓库的唯一 `main` 分支继续开发，保护已有未提交内容，不另建任务分支或工作树。
2. 按改动运行网站自身的必要测试与构建，再在该仓库独立提交和推送。
3. 发布后核验正式域名及受影响页面、询盘、通知或后台链路，记录实际通过范围。
4. 将开发结论、发布回执和运营结果写回 `02_开发记录/`；日常流程更新 `01_运营SOP/`。根经营仓库不收录网站源码、依赖或构建产物。
