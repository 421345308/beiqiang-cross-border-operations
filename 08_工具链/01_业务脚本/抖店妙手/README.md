# 国内抖店妙手 HTTP 接入

核验：2026-10-15。使用已授权国内妙手的本机登录会话，不需要购买跨境套餐。这是网页业务接口接入，不是对外开放平台SDK；按当前前端验证参数。

业务入口：[抖店经营与棉鞋上品](../../../09_国内电商/抖店/README.md)。调用器：[miaoshou_http.mjs](miaoshou_http.mjs)。通过 `await MiaoshouHttp.fromSavedSession()` 加载会话，业务请求独立运行，不经过浏览器渲染或Computer Use。

## 实测能力

| 方法 | 业务能力 |
| --- | --- |
| `listImportFiles()` | 导入任务查询，已测页大小10 |
| `getCategories()` / `getCategoryInfo(cateId)` | 类目树、动态属性、SKU与服务规则 |
| `getFreightTemplates()` | 原店运费模板查询，不改模板 |
| `listProducts({page,pageSize,isDraft})` | 完整分页读取商品、草稿；还需逐商品SKU查重 |
| `getProductBase(id)` / `getProductSku(id)` | 正式字段与SKU回读，精确商品ID取字符串productIdStr |
| `getProductAudit(id)` | 审核记录：-1等图片审核，0审核中，1通过，2不通过 |
| `uploadImage(path)` | JPEG/PNG上传，返回临时图片地址 |
| `recommendCategory({name,mainImgUrls})` | 真实标题与主图的官方推荐类目及凭据 |
| `getSizeTemplateInit(cateId)` / `saveSizeTemplate(payload,{evidenceDir})` | 规则查询、新建独立尺码组件 |
| `createProduct(payload,{evidenceDir})` | 已取得真实商品ID，回读价格、SKU、图片、履约 |
| `saveProduct(payload,{evidenceDir})` | 已验证补46/47码，回读原图、价格与服务 |
| `setProductStatus(ids,status,{evidenceDir})` | 固定上/下架操作，0上架、1仓库；转仓库接口已有成功回执 |

正式请求、回执和回读只存于 `09_国内电商/抖店/.local/evidence/`。提交、审核、买家页面检查分开记状态。

## 字段与执行约定

- 创建实际路径 `POST /api/v2/product/create_product/createProduct`，正式提交commit=1、status=0；仓库status=1，草稿commit=0、status=2。草稿也是写入。
- 普通表单使用括号索引编码嵌套对象、数组，不是整体JSON。编辑接口 `saveEditProductInfo` 的表单字段productInfo才是商品对象JSON字符串。
- specPricesV2.price单位为元，71.50元传71.5；其他只读价格字段可能为分。创建包含stockNum，编辑保留既有skuId、原价和原库存参照，不反复重置现存SKU。
- 推荐mainImgUrls为字符串数组；创建使用原样categoryRecommendId、categoryRecommendCheckStr，并核所选类目在推荐及账号权限范围内。
- 上传字段uploadWarePreviewImg、uploadType=localImg、enableUploadMultiple=false。主图及颜色规格图必须原生1:1且尺寸达到当前规则；最短边600不代表比例合格，详情图另按规则检查。
- 已测颜色图绑定使用specPic。单SKU的skuPictureUrl还有独立素材中心约束，临时地址曾被拒绝，调用器暂不开放该未完成验证的字段。
- 尺码组件和销售规格必须完全一致。过滤共享旧表后，先创建独立组件，再使用实际ID；只传前端JSON不够，不覆盖原共享模板。
- 创建三包字段为afterSaleServiceV2.three_guarantees.service_type/duration，回读为threeGuarantees.serviceType/duration，时长以单款授权为准。
- 编辑异步落地，成功后立即读取可能仍是旧SKU；稍后只读核对，不能直接再写一次。图片CDN的p3/p9域名可能变化，按图片对象路径比较内容。

查重必须核SKU颜色、编码及图片。旧889/8811链接可能混放别的货号，单看标题和主货号会漏。普通版与加绒版分别判断，不能把普通SKU的全局属性改成加绒。

写入方法要求新的私有evidenceDir，独占保存request.json、attempt.json后发送，结果写response.json，失败写failure.json。同目录阻止再次写入，没有自动重试。网络超时先回读；只有明确失败、修正并核准后才能开始独立的下一次尝试。图片审核排队应正常等待并复用已上传地址，不反复上传同图。

## 会话与正常连接

负责人已明确授权本机持久化，保存在 `.local/session.json` 并由.gitignore排除；不另加密，不打印或推送。过期后正常续登再保存。使用Node内置HTTPS与正常TLS校验，不使用失效的本机7892代理，不更改系统代理。

Chrome桥接曾因插件缺少browser-service.mjs而不可用，属于组件故障；已测独立HTTP可继续执行，买家可视化检查仍单独待验。

## 来源与图片准备

`sooxie_source_read.mjs` 只读贝强工厂店公开详情，按页面当前nonce及实际前端参数请求搜鞋网Detail/index，不使用账户Cookie，不输出nonce。示例：`node sooxie_source_read.mjs 2555441 --output source.json`。

来源普通/加绒旧参数可能混用，读取成功不等于材料全部核准；“是否库存”不是数量。`build_cotton_preview.py` 从当前准备包重建本地含图审核页，无外部写入。

契约取自当前entry-c0a63a8f.js引用的创建、编辑、属性、图片及尺码模块。链接搬家、分片导入和跨境开放平台仍未验证。[官方帮助](https://v1o7zyazq9.feishu.cn/wiki/OpquwOPHeiAeAFkPFcCcqHoonYc)。
