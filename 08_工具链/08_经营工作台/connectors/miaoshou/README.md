# 妙手只读连接器

复用原 `../../../01_业务脚本/抖店妙手/miaoshou_http.mjs`，不修改该客户端、不登录、不扫描会话目录、不执行平台写入。当前交付为可运行模块与JSON CLI，尚未接后台持久采集或进行真实联网验收。

在工作台仓库根目录运行（Node 18+，无额外依赖）：

```powershell
node "08_工具链/08_经营工作台/connectors/miaoshou/cli.mjs" capabilities
node "08_工具链/08_经营工作台/connectors/miaoshou/cli.mjs" connection-check --session-path "C:\绝对私有路径\session.json" --expected-shop-id "123"
node "08_工具链/08_经营工作台/connectors/miaoshou/cli.mjs" products --session-path "C:\绝对私有路径\session.json" --expected-shop-id "123" --page 1 --page-size 20 --is-draft false
node "08_工具链/08_经营工作台/connectors/miaoshou/cli.mjs" product --session-path "C:\绝对私有路径\session.json" --expected-shop-id "123" --product-id "456"
node --test "08_工具链/08_经营工作台/connectors/miaoshou/index.test.mjs"
```

示例路径/ID均为占位；由受控后端配置选择真实私有会话，不把会话文件、店铺精确ID或真实原始采集输出写进公开Git。`capabilities`无须会话，其余操作缺少显式绝对路径或数字字符串店铺ID即拒绝。每次操作先验证服务端身份；多请求读取在各阶段和返回前再核身份，串店不返回商品。独立店铺使用独立配置，不用默认旧店会话。

模块导出 `MiaoshouConnector` 和静态 `capabilities`。实例参数为 `{sessionPath, expectedShopId, clientFactory?, now?}`；调用 `await connector.execute(operation, input)`。`clientFactory(options)`是离线测试注入点，生产默认使用 `MiaoshouHttp.fromSavedSession`；不允许通过CLI注入任意模块。`products`一次读取一页，输入 `{page,pageSize,isDraft}`，默认1/100/平台默认范围；按返回 `pagination.nextPage`由调用者继续，不能将一页条数当目录总数。分页期间目录可能变化，调用方全量采集应核各页总数及ID去重。

结果包含 `ok`、`operation`、`connector`、`collectedAt`、`attemptedAt`；仅真实读取成功填写 `collectedAt`，失败及静态能力查询保持null；`attemptedAt`在加载指定会话前填写，参数拒绝与静态能力查询保持null。成功有 `data`，列表另有 `pagination`（total/returned/hasMore/nextPage/scope），失败只有固定安全错误，不附原始异常、路径、回执或部分商品。CLI每次输出一行JSON，失败退出码1。连接过期与网络/会话/平台错误显示 `connectionIssue: true`，不得将其转为零商品；上次成功与过期标记由后台持久层管理。SKU身份统一输出字符串 `skuId`，优先取精确 `skuIdStr`；数字仅在安全整数范围内转字符串，不安全数值拒绝整次结果。

输出严格投影：店铺仅ID；商品仅精确字符串ID、名称/标题、状态/类目；SKU仅ID、商家编码、原接口价格/库存/启停及销售规格；审核仅发布时间、状态和标题。不输出cookie、shopToken、账户名称、手机号、地址、原始审核原因或未知字段；不返回原始详情对象/图片/履约字段。SKU价格按既有 `specPricesV2/specPrices` 元口径，库存为平台填报。标题和规格是业务文本，仍应按私有业务数据保存，不公开真实采集输出。审核记录不等于当前正式字段或买家体验验收。

静态能力列出未来可接图片上传、商品创建/编辑、尺码组件创建及上下架，全部 `enabled:false`。本版无写路由，不能把底层客户端具有写方法当作本连接器已开放写入。未来接写必须另按店铺身份、授权对象/字段、原档案双改、独立证据及正式回读验收。

离线测试使用fake客户端，覆盖目标缺失、串店、读取期间串店、分页、详情/SKU/审核、会话过期、异常脱敏及不安全数值ID；不读取实际凭证、不发网络请求。
