# 国内抖店妙手 HTTP 接入

核验：2026-10-15。只服务已授权的国内抖店妙手账户，不使用跨境妙手 AppKey。

## 已验证

- 从已登录网页采样，再以独立 Node HTTPS 客户端请求；业务请求不经过浏览器渲染或 Computer Use。
- `POST /api/v2/move/import/getImportFileList`，表单 `pageNo=1&pageSize=10`。匿名 HTTP 返回 `result=fail, code=50001`；当前授权会话的独立 HTTP 返回 `result=success, data={importTaskList:[], importTaskTotal:0}`，与网页一致。
- `GET /api/v2/product/batch/getProductCateTree` 无请求体。当前会话独立 HTTP 成功，返回按类目 ID 索引的对象 `productCateTree` 及数组 `recentCategoryList`。
- 独立 HTTP 的上述查询未携带网页 `bx-v`、`deviceId`、`page-url` 等头，未关闭 TLS 校验，未重试或规避平台检查。这仅证明两项已测查询，不外推所有接口。
- 会话采用网页当前已有认证 Cookie。负责人于2026-10-15明确要求本机持久化，现保存在本目录 `.local/session.json`，由目录内 `.gitignore` 排除。它是本机 JSON 会话文件，不作额外加密，不打印或推送；会话过期须正常续登并重新保存，遇平台拒绝停止，不自动重放写请求。

调用器：[miaoshou_http.mjs](miaoshou_http.mjs)。后续使用 `await MiaoshouHttp.fromSavedSession()` 加载本机已保存会话，再调用 `listImportFiles()` 或 `getCategories()`，无需每轮打开浏览器。更新会话后调用 `saveSession()`；`clearSession()` 仅清除实例引用，不删除已保存文件。该模块只允许两项已测查询，没有通用 URL 透传或商品写入方法。

## 从实际页面代码学到、尚未执行的写入结构

证据来源是当前网页实际加载的公开模块，不是猜测路径：

- `product_quick_edit-2d86c738.js` 定义 `/product/create_product` 前缀及 `createProduct`、`getCreateBaseInfoByCateId`、`getRecommendCategory`、`uploadDescImgByZip` 包装。
- `index.vue_vue_type_script_setup_true_lang-96fd7eec.js` 定义创建表单及提交转换。预期完整路径为 `POST /api/v2/product/create_product/createProduct`；仅静态识别，未提交、未取得成功回执。
- 核心载荷包括 `cateId`、`title`、`standardBrandId`、`attrValues`、`categoryPropertyPics`、`pics`、`mainImageThreeToFour`、`description`、`whiteBgImgUrl`、`qualityList`、`assocIds`、`specValues`、`specPricesV2`、`specPic`，以及按类目取得的服务、尺码、履约等字段。`specPricesV2` 转换中包含 `stockNum`。价格单位、完整 SKU 结构、图片存储及字段合法值仍须单独核验。
- 保存草稿走相同创建接口；转换器对草稿设 `commit=0,status=2`，正式提交通常设 `commit=1`，实际还受当前 `status` 影响。草稿同样是平台写入，不作为只读验证。
- 标题及主图会用于类目推荐；接口返回的 `categoryRecommendId`、`categoryRecommendCheckStr` 被加入创建载荷。不能编造或跳过该前置验证。
- `/api/v2/move/batch/importProductUrls` 使用文件上传包装，字段 `productUrlsFile`，并附加 `conditions`；完整内容尚未上传验证。
- 搬家任务代码还存在 `moveTaskMultiPartUploadSave`/`moveTaskMultiPartUploadSaveBySts`，涉及素材/数据分片上传及任务提交，不能当作一个简单商品 JSON 接口。

以上静态识别不等于发布已成功，接口契约可能随页面版本改变；写入前须用实际商品、类目及当前表单参数核准，建立失败回读和重复提交保护。

## 上货模板已核事实

网页“导入复制”下载的 CSV 仅有：`链接地址（必填）,商品标题（选填）,售卖价（选填）,货号（选填）`。这是来源链接导入，不能直接代替完整的本地商品资料包。

## 正常连接问题

本机曾有指向 `127.0.0.1:7892` 的失效代理配置；直接 HTTPS 可达。调用器用 Node 内置 HTTPS，不读取这项代理，也不修改系统代理设置。

官方帮助入口：https://v1o7zyazq9.feishu.cn/wiki/OpquwOPHeiAeAFkPFcCcqHoonYc
