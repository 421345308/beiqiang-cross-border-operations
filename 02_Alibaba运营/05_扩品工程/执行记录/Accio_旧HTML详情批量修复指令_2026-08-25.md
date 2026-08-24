# Accio 旧 HTML 详情批量修复指令

> 状态：已准备，尚未向 Accio 提交线上写操作。
> 用法：每次只执行一个批次，每批 10 款；批次 1 验收通过后再执行批次 2、3。

## 固定执行要求

调用“国际站商品信息优化”的存量治理能力，并在最终发布阶段调用“商品发布（编辑模式）”。只修改指定 `productId` 的四处共享文案，不是重做详情页，也不是创建新商品。

必须保留标题、型号、6 张主图、SKU/颜色图绑定、产品级卖点、产品图、公司图、价格、MOQ、交期、包装和其他交易字段。不得改变任何图片或未点名字段。

替换内容：

- 公司介绍：`Quanzhou Beiqiang Footwear & Apparel Co., Ltd. is a footwear factory located in Quanzhou, Fujian, China. We supply casual walking shoes and related footwear for overseas B2B buyers. Product materials, colors, size ratios, packing and customization requirements are confirmed according to the current style and order details.`
- 工厂问答：`We are a footwear factory located in Quanzhou, Fujian, China. We supply casual walking shoes and related footwear for overseas B2B buyers. Product details and order requirements are confirmed according to the current style.`
- 样品问答：`Yes. Samples can be arranged for quality checking. The sample fee, courier cost, development time and any bulk-order policy will be confirmed for the current style before payment.`
- 选择工厂问答：`We provide factory support for product confirmation, sample checking, mixed size and color discussion, packing requirements and OEM/ODM cooperation. Final specifications are confirmed according to the current style and order details.`

风险规则：不得新增 `Flyknit`、医疗功效、固定退还/抵扣样品费或全店宽楦承诺。BQ001、BQ002、BQ031 可保留已有、产品级且有证据的宽楦卖点；其他款不得新增宽楦描述。

发布前必须输出预览并逐款核对 `productId + title + model number`。发布后逐款回读 copy、trunk、公开页，确认图片和交易字段未变化、风险词为 0，并返回每款成功/失败状态及公开链接。

## 批次 1

`BQ001/10000042821848, BQ002/10000042896165, BQ004/10000043201799, BQ005/1601815020244, BQ006/1601814931739, BQ007/1601825070472, BQ008/1601825021825, BQ009/1601825074604, BQ011/10000043725883, BQ012/10000043744505`

## 批次 2

`BQ013/10000043763325, BQ014/10000043732626, BQ015/10000043734620, BQ016/10000044021584, BQ017/10000044034049, BQ018/10000044007878, BQ019/10000044041008, BQ020/1601839073314, BQ021/1601838963947, BQ022/10000043991998`

## 批次 3

`BQ023/10000044004948, BQ024/10000044041031, BQ025/10000044024484, BQ026/10000044011929, BQ027/10000044028277, BQ028/1601839105416, BQ029/1601839062659, BQ030/1601839050756, BQ031/10000046439033, BQ032/10000046653813`
