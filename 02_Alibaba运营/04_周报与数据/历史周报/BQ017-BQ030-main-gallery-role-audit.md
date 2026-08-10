# BQ017-BQ030 主图角色审计

审计日期：2026-06-21

## 审计结论

- 检查产品：14 个
- FAIL：0 个
- WEAK：0 个
- PASS：14 个

结论：当前 BQ017-BQ030 的主图组已通过角色差异审计。`02_upper.jpg`、`03_fit.jpg`、`04_sole.jpg`、`06_scene.jpg` 的中心画面已经不再是同图换标题，图组可以分别承担鞋面、穿脱/结构、鞋底/支撑、颜色和使用/采购决策等角色。

## 审计标准

- `01_main.jpg`：搜索点击图，干净白底或浅底，产品完整清晰。
- `02_upper.jpg`：核心差异点或鞋面/材料证据。
- `03_fit.jpg`：闭合方式、穿脱方式、鞋口/脚感结构。
- `04_sole.jpg`：鞋底、缓震、纹理、弯折或结构证据。
- `05_colors.jpg`：真实颜色/SKU 选项，标签必须和图片一致。
- `06_scene.jpg`：使用场景或 B2B 采购决策支持，如样品、尺码、订单支持。不要做重复填充图。

## 逐款结果

| 产品 | 分组 | 状态 | 源图数量 | 主要问题 | 建议重做方向 |
|---|---|---:|---:|---|---|
| BQ017_A008 | Quilted Casual Walking Shoes | PASS | 18 | 图组角色基本有差异 | 2 quilted upper close-up; 3 lace-up fit/detail; 4 sole/cushion proof; 5 real colors; 6 commuting/daily use |
| BQ018_A116 | Lightweight Knit Walking Shoes | PASS | 18 | 图组角色基本有差异 | 2 knit upper; 3 lace-up fit; 4 walking sole/side support; 5 colors; 6 travel/commuting scene |
| BQ019_A206 | Breathable Knit Casual Shoes | PASS | 18 | 图组角色基本有差异 | 2 breathable knit texture; 3 men/women couple style or lace-up detail; 4 outsole/sole profile; 5 colors; 6 daily walking scene |
| BQ020_A218 | Summer Breathable Walking Shoes | PASS | 18 | 图组角色基本有差异 | 2 hollow knit airflow proof; 3 lace-up stability; 4 sole/cushion; 5 colors; 6 summer walking/use scene |
| BQ021_K6212 | Winter Slip-On Walking Shoes | PASS | 18 | 图组角色基本有差异 | 2 stretch textile upper; 3 slip-on opening; 4 sole/tread; 5 colors; 6 winter/fleece only if confirmed, otherwise daily use |
| BQ022_A2208 | Striped Knit Slip-On Shoes | PASS | 18 | 图组角色基本有差异 | 2 striped knit upper; 3 sock-like slip-on opening; 4 side/sole structure; 5 colors; 6 travel/commuting scene |
| BQ023_A505 | Soft Slip-On Walking Shoes | PASS | 18 | 图组角色基本有差异 | 2 soft knit upper; 3 low-cut slip-on fit; 4 sole profile; 5 black/grey/brown colors; 6 daily walking scene |
| BQ024_A830 | Men Slip-On Walking Shoes | PASS | 18 | 图组角色基本有差异 | 2 men soft knit upper; 3 slip-on fit; 4 sole/yellow-sole variant proof if available; 5 colors; 6 men commuting/daily use |
| BQ025_A1689 | Low Cut Slip-On Walking Shoes | PASS | 18 | 图组角色基本有差异 | 2 low-cut opening; 3 slip-on fit/top view; 4 outsole/side sole; 5 colors; 6 couple/daily walking scene |
| BQ026_T5828 | Lightweight Knit Walking Shoes | PASS | 18 | 图组角色基本有差异 | 2 breathable knit/mesh; 3 lace-up lightweight fit; 4 177g evidence only if source image is used; 5 colors; 6 women's daily walking scene |
| BQ027_K6116 | Knit Casual Walking Shoes | PASS | 18 | 图组角色基本有差异 | 2 knit upper; 3 lace-up fit; 4 chunky sole proof; 5 colors; 6 casual walking scene |
| BQ028_BISCUIT | Winter Slip-On Walking Shoes | PASS | 18 | 图组角色基本有差异 | 2 biscuit sole texture; 3 slip-on opening; 4 autumn/winter or fleece only if confirmed; 5 colors; 6 daily use/order support |
| BQ029_A025 | High Top Sock Walking Shoes | PASS | 18 | 图组角色基本有差异 | 2 high-top sock upper; 3 ankle opening; 4 wave pattern sole/upper; 5 black variants; 6 autumn/winter casual use |
| BQ030_A811 | Kids Walking Shoes | PASS | 18 | 图组角色基本有差异 | 2 breathable mesh upper; 3 kids lace-up fit; 4 cushion sole; 5 child color options; 6 school/daily walking scene |

## 优先级建议

1. 先修 `BQ017-BQ020`：这几款是常规透气/针织/夏季款，最适合建立一套可复用的主图角色模板。
2. 再修 `BQ021-BQ028`：这里有冬季、套脚、饼干底、低帮等差异，需要按产品特征分模板处理。
3. 最后修 `BQ029-BQ030`：高帮袜鞋和儿童鞋应分别做季节/鞋口/颜色/学校场景图，不能套用成人慢走鞋模板。

## 操作原则

- 不直接上传国内中文详情图；只能截取真实产品画面并重排英文 B2B 版式。
- 不使用未确认的 `orthopedic`、`waterproof`、证书、销量、工厂产能等表述。
- `EVA`、加绒、重量等信息只有在源图或供应商确认支持时才可放到图上；不确定时放到待确认清单。
- 每款至少保留 4 张强图；6 张弱图不如 4 张强图。

## QA 文件

- 当前主图组总览：`C:\Users\spq\Desktop\贝强\02_可上传素材\99_归档\BQ017_BQ030_gallery_role_audit_20260621\current_gallery_audit.jpg`
- 源图预览总览：`C:\Users\spq\Desktop\贝强\02_可上传素材\99_归档\BQ017_BQ030_gallery_role_audit_20260621\source_contact_overview.jpg`
- 结构化 CSV：`C:\Users\spq\Desktop\贝强\02_可上传素材\99_归档\BQ017_BQ030_gallery_role_audit_20260621\gallery_role_audit.csv`
