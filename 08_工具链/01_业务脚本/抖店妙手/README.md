# 国内抖店妙手 HTTP 接入

核验：2026-10-18。使用已授权国内妙手的本机登录会话，不需要购买跨境套餐。这是网页业务接口接入，不是对外开放平台SDK；按当前前端验证参数。

2026-10-18连接更新：旧店默认保存会话此前返回50001登录过期；新店的正常授权配置已由负责人完成，并另存独立会话。新店身份、商品/草稿、类目品牌规则、运费、图片上传及推荐类目已通过独立HTTP读取或操作。旧店四款新图文仍未正式提交，不能把新店连接成功当旧店恢复。

业务入口：[抖店经营与棉鞋上品](../../../09_国内电商/抖店/README.md)。调用器：[miaoshou_http.mjs](miaoshou_http.mjs)。通过 `await MiaoshouHttp.fromSavedSession()` 加载会话，业务请求独立运行，不经过浏览器渲染或Computer Use。

2026-10-18多店保护已实现并测试：新店会话使用 `.local/shops/brand/session.json`，保存明确目标身份；原 `.local/session.json` 保持原样。新增 `getShopIdentity()`，每次图片上传、商品/尺码/状态写入前都读取服务端身份并核对目标ID。缺目标、会话串店或保存配置目标冲突会在写入前失败；自动测试覆盖串店拦截和目标正确的提交记录。旧会话的只读方法仍可用，旧写入须先经真实身份核对并补齐该会话自己的目标信息，不能填新店目标迁就旧脚本。

## 实测能力

| 方法 | 业务能力 |
| --- | --- |
| `getShopIdentity()` | 当前服务端店铺ID/名称；不向业务调用方返回shopToken等无关鉴权字段 |
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

负责人已明确授权本机持久化，旧默认配置在 `.local/session.json`，新店在 `.local/shops/brand/session.json`，均由.gitignore排除；不另加密，不打印或推送。通过 `fromSavedSession({sessionPath})` 明确选择配置；其中expectedShopId为写入前匹配目标，不能用当前网页名称代替服务端核验。过期后正常续登再保存。使用Node内置HTTPS与正常TLS校验，不使用失效的本机7892代理。网络分流按负责人2026-10-15明确要求另行调整，业务调用器不自行改系统代理。

## 新品牌店首发准备

`brand_candidate_content.mjs`为继续扩品准备A116、K6116、A212，只写品牌首发档案的`expansion_candidates`及独立处理素材，不重建现有商品。先用`sooxie_source_read.mjs`更新`.local/品牌新店/来源/下一批候选.json`；逐款购买理由、推荐假设、标题、主图、版本和缺口共用该当前档案。渲染后回写真实视觉哈希及详情清单，已提交候选禁止重建。`brand_expand_apply.mjs`支持该三款，要求当款价格已确认、本地视觉哈希一致、最新完整目录与SKU查重齐全；现有4款路径保持不变。候选价格为null时拒绝准备与发布，不把提案当作已批准价格。

2026-10-20这三款已获94减5价格确认并正式创建，审核、双接口回读、39张平台图片逐张像素/顺序/颜色绑定及3款H5通过；原券已保存扩至9款，原7款保护核验通过。当前完整目录10款、草稿0，品牌档案9款182个加绒SKU。候选正文已归入`models`当前记录，`expansion_candidates`只留完成状态和引用，不重复维护正文。不得再运行创建。`verify_brand_media.py`支持发布前候选或当前models；国内CDN使用已授权直连且保留正常TLS校验，避免读取已失效系统代理。手机App选码与实际核销仍待验。

`build_focus_content.mjs --brand-launch` 只生成新店A1689和ZX9002加绒版，各5张主图与8屏详情；使用独立的 `抖店品牌首发/` 素材目录与 `数据/品牌首发商品.json`，不覆盖旧店四款素材、发布状态或视觉验收。A1689仅使用对应加绒实图，不把常规版鞋口图当加绒；ZX9002缺真实绒里近照，当前明确外观展示，不合成绒里证明。

`build_focus_factory_packet.mjs --brand-launch`现转交`render_brand_factory_packet.mjs`，只渲染当前6款63行实测与12条脚本，保留工厂已填写记录，不再清空重建；`build_brand_review.mjs` 生成品牌文字头像、店招、两张广告草案及接触表，并汇入新店图文审核HTML。品牌文字在画面外，实鞋与通用鞋盒不改绘Logo；店招画布尺寸仍是设计稿，正式装修需核槽位。重新渲染后须按新文件哈希重做视觉验收，不能沿旧验收上传。

`brand_launch_http.mjs inspect|prepare` 显式使用新店配置。inspect完整分页核商品与草稿并读运费，精确ID取productIdStr；prepare仅适用未创建阶段，要求当前全套素材视觉哈希匹配，按新店/文件SHA复用上传并取推荐类目，校验新店品牌与必填属性。首发prepare仅适用最初空店；当前已有6款，不重复prepare或创建。

`brand_launch_apply.mjs sizes|prepare-product|publish|verify <A1689|ZX9002>`要求私有履约授权、准备文件和新店配置的目标身份一致；独立尺码组件、94元/100件/次日发/服务和实际运费均按本轮确认设置，查重后仅一次创建。两款已有真实创建回执、审核通过与主字段/SKU回读；后续不要再执行sizes/publish来重建对象。首发当时商品2、草稿0；2026-10-19扩品后完整目录6、草稿0。商品券由官方后台正常创建并重新打开核范围，实际94减5预计89；精确对象、券期限和截图仅留业务.local。

`brand_listing_content.mjs build|prepare|apply|verify <款式>`用于这两条已有商品的60字符标题和实物主图修订，只写title/mainImg，保护详情、品牌、颜色图、现存SKU身份/价格/库存/编码、尺码模板及履约。build遇已提交或已验收修订拒绝重建，审核页用`build_cotton_content.mjs <内容JSON> <审核HTML> --review-only`刷新。一次正式提交失败后，只有独立保存的明确ddApiLocalQpsLimit拒绝、当前标题尚未写入且保护字段未变，才允许显式`--retry-qps`另留尝试；未知结果仍只读核实。

`verify_brand_media.py`读取已通过正式回读的修订，从实际平台CDN取回主图、详情及逐色图片，逐张比较尺寸、RGB像素和顺序/绑定。当前6款77张均与本地原图像素完全一致；6款H5标题、3张主图、8屏详情、94/97减5及次日发已核。手机App选码、订单实际核销仍待办，中通共享已生效、首次正常打印待核；不把H5或API成功当全部经营闭环完成。

`getFreightTemplates({refresh:true})`为已观察到的妙手原生刷新参数；新店模板创建后优先刷新再取列表，不能因缓存滞后重复创建。正式商品freightId独立回读，不将模板管理异步绑定计数当作唯一证据。

新店精确身份、推荐凭据、上传URL及回执只留 `09_国内电商/抖店/.local/品牌新店/`，不混用旧店缓存、模板ID或券ID。源站普通/加绒参数可能沿旧描述；本轮加绒SKU按实际加绒页面颜色尺码及原图判断，不照搬“网纱内里”。

Chrome连接现已恢复，官方优惠查询及原券编辑已完成；商品批量操作仍使用独立HTTP。实际买家商品页渲染另行验收，不能因后台或本地预览通过而自动标通过。


`brand_expand_content.mjs`只初始化明确新增4款的独立加绒内容，已有款拒绝覆盖；`build_cotton_content.mjs`按`detail_output_dir`导出新店详情，避免覆盖旧店。已提交素材只用`--review-only`刷新审核HTML，不能无故重渲染让验收哈希失效。

`brand_expand_apply.mjs prepare|publish|verify <M889|H7212|ZX2116|ZX9507>`按当前新店身份、已批准分档、全套图像哈希及真实加绒范围执行。上传按SHA复用，独立尺码组件与当前类目/品牌规则取回；一次创建请求和正式主字段/SKU/审核分别留证。4款均已创建，不能再次publish。`protect-existing`只读比较扩品前原2款主字段与SKU基线。`verify_brand_media.py [明确款式...]`可只验本次新款；H5对象顺序、券范围与App实际核销仍分别取证。各次写plan的步骤串行执行。

2026-10-19续登由负责人在正常妙手授权页面完成，新店持久会话已续期，HTTP完整目录6/草稿0；不因此声称旧店默认会话恢复。当前原公开5元券已在官方页面加4款并重新打开核6款，原2款价格保留；中通共享页面读到已生效，不能仅看自有网点数量推断无面单。

## 来源与图片准备

`sooxie_source_read.mjs` 只读贝强工厂店公开详情，按页面当前nonce及实际前端参数请求搜鞋网Detail/index，不使用账户Cookie，不输出nonce。示例：`node sooxie_source_read.mjs 2555441 --output source.json`。

2026-10-20修正图库读取：接口alt图只是子集，现按已观察到的`photoBig`首图、`Lazyload/data-url`详情图及接口补充图去重，不读取关联推荐卡片。已读全目录79条中的74条完整详情图URL，4条详情读取失败、1条完整图库读取失败，分别保留原因；403或重定向不通过绕过访问限制补取。**源页自身也可能混放不同鞋型**（如部分旧加绒页），这些图仍需逐款筛选，不能因解析到就用于本款主图。

全目录新增候选保存在当前品牌商品档案的`expansion_candidates`，验收后进入`models`，不同时维护两份当前记录。`brand_expand_apply.mjs`已扩候选白名单；未确认价格时在读取会话及任何外部调用前停止。常规版的季节、内里、功能和鞋面沿单款字段，尺码组件名称及SKU编码R/F区分版本；动态类目、品牌、必填字段和独立尺码在正式prepare时取当前值。2026-10-20负责人统一同档94减5后，11款308SKU已正式新建并审核、主字段/SKU、149张媒体、原券20款范围及H5通过；原10款保护通过，App闭环仍待验。L0017已获负责人单款109减5、券后104确认，价格守卫仅对L0017开放109档。2026-10-21已再备ZX2212/8008/K6689三款常规版图文，白名单加入该三款；其当前图文与价格均已核，尚未正式prepare/create。新店会话50001已在2026-10-21按负责人当次确认正常续登恢复。L0017/8008/ZX2212/K6689已各创建一次并审核、规格/价格/履约回读、59张媒体、原券24款全范围及H5验收通过；完整目录25款/草稿0，原21款保护通过。所有4款已归入models，不得重新prepare/create。ZX2212长配色图H5三段裁切坐标连续覆盖原2438像素高度，逻辑图序按完整覆盖验收，不把重复整图静默折叠。所有已创建款不得重发。

`build_cotton_content.mjs`默认保持加绒布局；明确`fleece:false`才输出常规版讲解、颜色和参数，可用`upper_feature`传本款真实鞋面描述。未知内里不补人造绒，参数长值自适应字号/换行。已实际渲染并查看6款常规版48屏详情；已发布图片只用`--review-only`刷新审核页，不能随生成器升级批量重绘线上素材。

平台图片只读下载遇到短读或临时TLS/网络失败时，`verify_brand_media.py`对同一URL最多尝试3次，保持TLS校验；403等非临时拒绝不重试。完整下载且图像可解码后原子落盘，再作像素比对，不将半截文件当缓存；不重传商品或改用别款图片。

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
