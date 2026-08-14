# 阿里国际站产品上新 SOP

> 2026-08-14 安全更新：本文件保留历史上新操作经验，但其中出现的材料、价格、MOQ、重量、尺寸、交期、清关和通用卖点都不是新款默认值。扩品与多链接项目必须先执行《国际站合规扩品与多链接工程 SOP》，完成实质去重、IP 检查和产品事实卡后才能引用本文件。禁止把 BQ030/BQ031 或任一旧款字段整页复制到新款。

适用场景：贝强鞋类数据包上架到阿里巴巴国际站，尤其是宽鞋头、飞织/网布、一脚蹬、休闲步行鞋类产品。

## 1. 开始前确认

每次开始一个新数据包，先确认以下信息：

- 数据包名称：例如 `5.13贝强1数据包`、`5.13贝强2数据包`
- 商品类目：鞋靴及配饰 > 男鞋 > 休闲运动潮鞋 > 慢走风休闲鞋
- 是否沿用现有产品组：通常用 `Wide Toe Box Walking Shoes`
- 是否有真实尺码范围、价格、MOQ、库存、包装尺寸、毛重
- 是否有货代或报关行提供的 HS 编码

需要及时向商家确认的高风险项：

- 成交价、申报价值、MOQ、交期
- 真实尺码范围和尺码表
- 包装尺寸、单双毛重、箱规
- 美国 HS 编码、中国出口 HS 编码、清关申报价值
- 是否支持 OEM/ODM、Logo、包装、吊牌定制

## 2. 读取数据包

优先查看这些内容：

- `001.jpg`：整张详情长图，用来提取核心卖点、重量、材质、颜色、功能。
- `750天猫`：用于结构化商详图片上传，通常已经切成 24 张详情图。
- `800X800主图`：用于主图、颜色图、规格图。
- `透明图`：用于生成尺寸图、主图衍生图、干净背景图。

检查图片要求：

- 主图：建议 800x800 或更高，大小不超过平台限制。
- 详情图：平台要求 600x600 以上，大小不超过 5M。
- 不要优先使用网上图片，除非数据包缺关键素材。
- 生成图必须基于自有产品图，避免和实物不一致。

## 3. 商品标题

标题结构建议：

`核心材质/功能 + 穿着方式 + 使用场景 + 鞋类词 + 核心差异点 + 适用人群`

常用标题模板：

```text
Breathable Mesh Slip-On Walking Shoes Lightweight Wide Toe Box Casual Sneakers for Men Women
```

更偏成熟卖家风格：

```text
Breathable Mesh Slip-On Casual Walking Shoes Lightweight Wide Toe Box Sneakers for Men Women Outdoor Daily Wear
```

标题注意：

- 不堆太多重复词。
- 不写产品没有的功能，例如 Waterproof、Steel Toe、Leather。
- 如果是男鞋类目但实际可男女穿，可以标题末尾写 `for Men Women`。
- 长度控制在平台限制内，优先保留 `Breathable`、`Mesh`、`Slip-On`、`Walking Shoes`、`Wide Toe Box`、`Lightweight`。

## 4. 商品分组

推荐产品组：

```text
Wide Toe Box Walking Shoes
```

如需细分，可以增加：

```text
Outdoor Casual Walking Shoes
Breathable Slip-On Sneakers
```

原则：

- 每个商品只能进一个产品组。
- 同类宽鞋头休闲鞋先放同一组，方便买家集中浏览。
- 等产品数量多了，再按场景、鞋底、季节拆组。

## 5. 基础属性

慢走风休闲鞋常用属性：

| 字段 | 推荐值 |
|---|---|
| 大底材质 | Rubber |
| 鞋面材质 | Mesh |
| 原产地 | China |
| 中底材质 | EVA |
| 里衬材质 | Mesh |
| 产品特性 | Breathable, Anti-Slip, Lightweight, Comfortable |
| 品牌 | Beiqiang |
| 型号 | BQ-001 / BQ-002 / 按商品递增 |
| 季节 | Spring, Summer, Autumn |
| 款式 | Walking Shoes |
| 图案类型 | Solid |
| 鞋头风格 | Round Toe |
| 闭合方式 | Slip-On |
| 图案 | Solid |
| 鞋面材质 | Mesh |

通常不强填：

- 真皮类型：产品不是皮鞋时不填。
- 图标工艺：没有 Logo/印花时不填。
- 位置：不是定制 Logo 位置时不填。
- 开口类型：平台无合适选项时不填。

## 6. 颜色规格

颜色命名要用清晰英文，不要只写中文或模糊编号。

数据包1可用：

```text
White
Black White Sole
All Black
```

数据包2可用：

```text
Grey White Sole
Grey Khaki Sole
Grey Black Sole
```

规格图建议：

- 每个颜色上传对应 800x800 清晰产品图。
- 图上不要有过多中文文案。
- 保持白底或浅背景优先。

## 7. 详情图片整理

页面结构化商详一般有四组：

- 尺寸图 Product dimensions
- 场景图 Scene image
- 细节图 Detail shot
- 其他商品图片 Other product images

整理文件夹命名建议：

```text
推荐上传-商品详情图
推荐上传-商品详情图-数据包2
```

子文件夹：

```text
1-尺寸图
2-场景图
3-细节图
4-其他商品图片
```

图片分配逻辑：

- 尺寸图：生成英文尺寸参考图，优先用透明图里的产品图。
- 场景图：详情图中的首屏图、穿着/户外/生活方式图。
- 细节图：宽鞋头、透气鞋面、缓震、鞋垫、防滑大底、轻量。
- 其他商品图片：不同角度、不同颜色、套图。

尺寸图规范：

- 生成 1200x1200。
- 标题用 `PRODUCT DIMENSIONS`。
- 加 `SIZE REFERENCE` 表。
- 标注 `Reference only`，避免数据包无真实尺码时造成承诺风险。
- 如果商家提供真实尺码表，必须替换参考尺码。

## 8. 商品卖点

可直接使用的通用英文卖点模板：

```text
Breathable Mesh Upper: Soft knitted mesh fabric improves airflow and helps keep feet fresh and comfortable during daily walking.

Wide Toe Box Design: Roomy forefoot space allows toes to spread naturally, reducing pressure for long-time wear.

Lightweight Comfort: Lightweight construction makes the shoes easy to wear for commuting, travel, walking and light outdoor activities.

Slip-On Closure: No-lace design makes the shoes easy to put on and take off, suitable for quick everyday use.

Cushioned EVA Midsole: Soft and flexible midsole helps absorb impact and provides comfortable support with every step.

Anti-Slip Rubber Outsole: Textured rubber sole offers stable grip and wear resistance for indoor and outdoor surfaces.

Casual Versatile Style: Simple solid color design pairs easily with sportswear, casual pants and daily outfits.
```

如详情图写明重量：

- 数据包1：约 `267g per shoe`
- 数据包2：约 `253g per shoe`

可替换到 `Lightweight Comfort` 中。

## 9. 交易信息

常用初始填写，后续需商家确认：

- 销售方式：按件卖或按双卖，鞋类建议 `Pair/Pairs`
- MOQ：新店可先低门槛，例如 `1`、`2`、`10`，以实际策略为准
- 库存：按颜色分别填写，例如每色 `1000`
- 商品编码：例如 `BQ-001`、`BQ-002`
- 发货期：例如 `1-50 pairs: 30 days`，更大数量需协商

需要确认：

- 真实库存是否足够。
- 是否支持一件代发。
- 是否做阶梯价。
- FOB/EXW/DDP 等贸易条款是否要展示。

## 10. 物流信息

若无真实包装资料，可先用保守估算，提交前建议确认。

鞋类单双参考：

- 毛重：`0.5 KG/Pair` 左右
- 长：`34 CM/Pair`
- 宽：`23 CM/Pair`
- 高：`13 CM/Pair`
- 物流属性：普货

注意：

- 包装尺寸会影响运费，不要长期使用估算值。
- 如果有鞋盒尺寸，优先按鞋盒实测填写。

## 11. 海关清关属性

以数据包2当前页面实际下拉为例：

| 字段 | 推荐选择/填写 |
|---|---|
| 清关标准名称 | 男式休闲鞋 (Men's casual shoes) |
| 鞋子外底材料 Outsole material | rubber |
| 风格 Style | not covering the ankle |
| 鞋面材料 Upper material | textile materials |
| 补充风格 Style | soles are affixed to the upper exclusively with an adhesive |
| 产品类型/类别 Type | slip-on type |
| 补充鞋面材料 Upper material | textile material |
| vallue($) | 优先按实际申报价值；平台下拉有 `6.5` 时可先选 `6.5` |
| 材质 Material | Mesh upper, EVA midsole, rubber outsole |
| 用途 Use | Daily walking and casual wear |
| 美国清关英文品名 | Men's casual shoes |
| 中国出口中文品名 | 男式休闲鞋 |

HS 编码原则：

- 优先让平台根据清关属性自动推断。
- 不盲填完整美国 HS 编码。
- 中国出口 HS 编码、美国 HS 编码最终建议由货代/报关行复核。
- 任何涉及税率、清关异常风险的字段，都要向商家确认。

## 12. 公司信息与 FAQ

如果暂无公司资料，可先不强填公司图。文字可准备通用版，但提交前需要确认真实性。

FAQ 建议：

```text
Q: Can I customize the logo or packaging?
A: Yes, OEM and packaging customization can be discussed based on order quantity.

Q: What is the sample lead time?
A: Sample lead time is usually 7-15 days, depending on stock and customization requirements.

Q: What materials are used for this shoe?
A: The shoe uses a breathable mesh upper, EVA midsole and rubber outsole.

Q: Is this shoe suitable for daily walking?
A: Yes, it is designed for daily walking, commuting, travel and light outdoor activities.
```

需要确认：

- 是否真的支持 Logo。
- 起订量是多少。
- 样品是否收费。
- 打样周期是否准确。

## 13. 发布前复核清单

提交前逐项检查：

- 商品标题是否包含核心关键词且无虚假功能。
- 分组是否正确。
- 必填属性是否 `5/5`。
- 图片是否清晰、尺寸合规、没有错款。
- 详情图四个图集是否每组至少一张。
- 商品卖点是否与图片和属性一致。
- 颜色规格是否和主图一致。
- 价格、MOQ、库存、发货期是否合理。
- 物流重量和尺寸是否填写完整。
- HS 编码和清关属性是否需要商家/货代复核。
- 没有把数据包1和数据包2的图片混用。

## 14. 后续工作方式

每次新数据包按这个流程执行：

1. 读取数据包文件结构和长图。
2. 提取商品差异点。
3. 给出标题、分组、属性、颜色、卖点。
4. 整理详情图四个上传文件夹。
5. 缺尺寸图时生成英文尺寸图。
6. 协助填写发布页。
7. 遇到价格、尺码、清关、包装等高风险信息时暂停确认。

## 15. 浏览器实操门禁（2026-08-15）

在国际站后台完成一款商品时，必须按以下顺序执行：

1. 本地上传图片全部加 SKU 前缀，图片银行按 SKU 文件名与画面内容双重核对。
2. 标题、型号、属性、颜色和 SKU 图填写后先保存，再重载回读；颜色下拉必须按 Enter 确认。
3. 若按钮可见却无响应，先检查右侧 AI 抽屉或客服浮窗是否覆盖目标区域。
4. 滚动到“商品详情信息”触发懒加载，再检查详情；禁止只凭空容器判断详情缺失。
5. 复制旧款后进入 AI 详情编辑器，替换全部产品文字与产品图片，删除没有新款素材的旧场景模块。
6. 在详情文字中搜索旧 SKU、旧尺码、旧颜色、旧材料和不适用卖点；命中数必须为 0。
7. 详情编辑器执行 `保存 → 编辑完成 → 同步 App`，回到主发布页再保存并重载。
8. 复核主图顺序、型号、颜色、规格图、尺码、价格、MOQ、交期、包装和详情图片数量。
9. 运行商品质量检测；质量分达到 5.0、各区块无问题后再提交。
10. 从成功页记录 `primaryId` 和“审核中”状态，并立即写回扩品台账。

本流程已由 BQ032（`10000046653813`）与 BQ033（`11000037600317`）实测验证。
