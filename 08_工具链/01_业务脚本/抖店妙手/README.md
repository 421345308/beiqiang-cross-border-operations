# 国内抖店妙手 HTTP 接入

核验：2026-10-15。使用已授权国内妙手的本机登录会话，不需要购买跨境套餐。这是网页业务接口接入，不是对外开放平台SDK；按当前前端验证参数。

2026-10-18连接更新：已有HTTP成功证据持续有效，但当前保存会话返回50001登录过期；正常续登页停在平台授权协议确认。不是商品编辑授权失效，也不能用旧回读冒充今日数据；负责人完成页面协议确认后再保存已授权会话。当前四款新图文尚未正式提交。

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
| `getSizeTemplateInfo(sizeInfoTemplateId)` | 回读实际选定尺码及配置，已验证当前前端参数 |
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

负责人已明确授权本机持久化，保存在 `.local/session.json` 并由.gitignore排除；不另加密，不打印或推送。过期后正常续登再保存。使用Node内置HTTPS与正常TLS校验，不使用失效的本机7892代理。网络分流按负责人2026-10-15明确要求另行调整，业务调用器不自行改系统代理。

Chrome连接现已恢复，官方优惠查询及原券编辑已完成；商品批量操作仍使用独立HTTP。实际买家商品页渲染另行验收，不能因后台或本地预览通过而自动标通过。

## 来源与图片准备

`sooxie_source_read.mjs` 只读贝强工厂店公开详情，按页面当前nonce及实际前端参数请求搜鞋网Detail/index，不使用账户Cookie，不输出nonce。示例：`node sooxie_source_read.mjs 2555441 --output source.json`。

来源普通/加绒旧参数可能混用，读取成功不等于材料全部核准；“是否库存”不是数量。`build_cotton_preview.py` 从当前准备包重建本地含图审核页，无外部写入。

契约取自当前entry-c0a63a8f.js引用的创建、编辑、属性、图片及尺码模块。链接搬家、分片导入和跨境开放平台仍未验证。[官方帮助](https://v1o7zyazq9.feishu.cn/wiki/OpquwOPHeiAeAFkPFcCcqHoonYc)。

## 已有棉鞋内容优化

`build_cotton_content.mjs` 读取渠道内 `数据/棉鞋内容优化.json`，将真实产品照片及明确标识的穿搭示意嵌入可编辑SVG，按场景与利益、结构讲解、加绒日常、外底轮廓、配色、参数、选码、服务渲染8屏详情与本地审核页。需要Node、`@resvg/resvg-js`及微软雅黑字体；渲染依赖留临时运行目录，或用 `BEIQIANG_RESVG_MODULE` 指定已安装模块。处理图、SVG、PNG与依赖不入普通Git。原图不覆盖，图像生成只作有留证的局部清理，不用生成角度证明实物。

`optimize_cotton_existing.mjs <款号> prepare|apply|verify` 只针对已确认的4条在售棉鞋。可在操作后加可读修订标识（如`benefit-scenes`），独立保存本次正式请求及前后回读，复用此前已上传的相同素材；不覆盖上一轮正式回执。prepare保存当前字段、按文件SHA缓存上传并核推荐类目，apply只编辑base/mainImg/descImg，不传SKU写入组，verify回读标题、独立详情、SKU身份价格、履约与本次标题审核。素材须先视觉验收；限流正常等候，已上传素材复用。未知写入结果只读核实，明确失败后另留独立尝试证据。

## 现存款式拆分与消费者内容

`retail_family_content.mjs upload|apply|verify|activate|repair-brand <明确款号...>`读取当前两份渠道内容档案及仅本地保存的对象映射。按图片SHA复用上传；apply必须新留正式请求，保存当前价格、库存、商家编码与规格身份作为基线；旧混款仅关闭非本款SKU。已执行对象不重复apply。repair-brand仅为已核无标识实物的L0017纠正历史误填品牌，不可用作去除实物品牌。

颜色规格改名即使传原SKU编号也可能导致平台重新编号，本轮M889发生55个编号迁移；其正式验证保持oldIdsKept=false和verified=false，另记内容价格通过及逐码映射，不降低身份检查来冒充全通过。其他现存规格名称保留。尺码组件ID改变时，以`getSizeTemplateInfo`回读的已选尺码和配置比较，保留正式等价证据，不直接断言ID未变。

上下架响应的result=success不代表全部对象成功，必须检查successCount、failCount和逐商品原因，再回读status；本轮3条明确QPS失败另留一次重试证据后已核在售。未知结果只读查询，不自动重复写入。

`build_cotton_content.mjs <内容JSON> <审核HTML> [款号|--review-only]`可渲染任一当前档案；`--review-only`只重建审核页，复用已发布文件，不重绘或重置发布状态。当前15款共51张主图及120屏独立详情；文件哈希、平台媒体内容与颜色绑定逐张验收。主图用真实产品，AI穿搭仅标示意详情。

优惠管理未暴露为本地HTTP写方法。本轮按明确授权在抖店原50元券增加H7212，编辑后重新打开读取原商品、金额、期限、数量和预计价；不从商品标价推测优惠，也不擅自复制新券。具体私有ID、截图和回读留业务.local。

## 重点款与经营回收（2026-10-18）

`build_focus_content.mjs`从现有渠道档案与真实来源照片重建四款20张主图、32屏详情；原生SVG嵌入照片，原件不重画。源区域独立裁切，防止嵌套SVG留白处漏出促销贴纸。重建会重置发布/视觉状态，正式发布后不要用它覆盖当前结果；先核修订范围。候选标题当前不自动应用。

`build_focus_factory_packet.mjs`生成四款76条实测空表和8条逐镜头脚本，以及可填写/打印/保存的工厂页面。实际测量、拍摄和上传分开；空表不能标实测完成。

`focus_media_update.mjs prepare|apply|verify <款式>`仅适用于该审核包；精确对象映射在业务.local/evidence/focus-content/targets.json。prepare要求全套素材SHA对应的视觉验收，读取正式主字段和SKU双基线后按SHA复用上传；apply只发送mainImg/descImg组，保留原颜色图绑定，不连带改标题、规格名、SKU/价格/库存、服务或品牌。线上变化先停止，已有attempt不重发；verify仍留下平台媒体像素、当前审核、买家页及优惠资格待验。**已通过本地字段/图片绑定保护测试；续登未完成，尚无本次正式写入成功证据**，不能称新链路已线上验收。

`compass_review.mjs <精确私有取数目录>`完全离线，不访问网络或读取凭证。capture-manifest.json声明窗口、预期总数和分页文件；JSON按单位换算、DOM按字段读取，分页去重、关键词齐全、支付与支付时间退款对平后生成当前私有经营诊断。费用“-”保留null，不混算不同截止日，不把全店收入和店铺被投消耗伪装成广告ROI。取数不完整就失败，不静默用旧缓存补齐。

罗盘正常登录可读，独立HTTP试读返回“当前环境存在风险”后已停止，不改签名、伪装环境或绕过检查。当前用正常页面请求采样/导出与离线分析；仍需浏览器会话，不能称罗盘完全脱离Computer Use。优先复用原始响应，避免逐格抄数。商品批量业务继续用已有妙手HTTP；登录/平台检查和必要买家端呈现保留浏览器或人工入口。

通用电商Agent的`operations.metrics`当前仍按CSV漏斗读取，直接传本轮零售JSON会拒绝。本次使用上述独立分析及`commerce_business_snapshot`读取两个独立窗口，保留未知归因、不合并总额；不要把订单填成B2B询盘或伪装文件格式。本地通用任务保留待适配，不冒称全流程完成。

## 国内经营网站直连

2026-10-15按负责人明确要求，已在Clash Verge当前配置的持久规则及DNS合并项中设置抖店、妙手、搜鞋网等17个国内业务/图片资源域名优先DIRECT，使用国内DNS；原国外代理规则和TUN设置保留。实时连接回读已确认抖店、妙手、抖音及相关资源走DIRECT。仅关闭这些域名遗留的海外代理连接让其重建，未清空全部连接。

同机单次首页测试：抖店调整前20秒仍未结束，调整后0.84秒；妙手2.06秒降至0.31秒。妙手登录后的商品上货页面已正常加载。测速仅代表该次请求，业务页耗时还受服务器与页面处理影响。完整配置、回滚原件、私有管道鉴权及实时验收仅保存在业务.local/network，不进入公开仓库。

## 已验证价格与券承接

`coupon_price_transition.mjs prepare|apply|verify [私有计划JSON]`按已确认券后目标调整现存可售SKU标价，保留停售价、现存SKU编号、库存、编码、颜色尺码、图文及履约；原价参照不虚构修改。支持明确逐SKU标价映射，必须先记录已生效券及精确商品范围。仅价格操作，不创建/修改券。券由官方后台正常操作并重新打开读取范围、规则与预计价。

当前前端会拒绝历史规格备注的首尾空格；只有明确失败后，才可留独立attempt_label并针对已确认备注空格清理重试，颜色/尺码名称不改。验收包含允许的空格清理，保持此前失败凭据，不能忽略其他身份变化。单品直降与券可叠加，转券必须先确认原活动已失效；表格刚操作后可能仍显示旧状态或旧价格，下一次实际回读确认后再进行依赖动作。
