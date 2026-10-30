# 国际站只读适配器

供受控后端/执行器调用的Python标准库CLI，复用仓库 `.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py` 的加载、签名及HTTP实现。没有导入时取数、后台循环、自动刷新token或平台写入。

从本目录执行：

```text
python adapter.py capabilities
python adapter.py connection-check
python adapter.py products --page 1 --page-size 50
python adapter.py product --product-id 123456789
python adapter.py --config C:/external/config.json products --page 2 --page-size 20
python -m unittest discover -s . -p test_adapter.py
```

`capabilities` 完全离线；其他三个命令显式发起一次平台只读请求。分页必须由调用者按 `pagination.nextPage` 再调用，不隐式抓全店。`page-size` 允许1–50，以平台返回的有效page_size计算下一页。列表参数固定 `language=ENGLISH,current_page,page_size`；详情固定 `language=ENGLISH,product_id`，无任意method/参数透传。详情ID使用原 `product.get` 所接受的平台ID，不负责不同编码转换。

stdout一行JSON；成功退出0，业务/客户端失败退出1。无效CLI语法由argparse返回2及stderr说明。统一字段：`ok,operation,data,error,source,pagination`。`data` 为商品数组、单个商品对象、连接探测结果或能力说明；失败时为null，不能把它计为0件商品。`source.collectedAt` 只有有效业务响应才填写UTC时间；`attemptedAt` 是请求尝试时间。账号仅为固定连接别名 `beiqiang-alibaba-primary`，`identityVerified=false`，不宣称API验证了店铺身份。`pagination` 包含 `page,pageSize,total,returned,hasMore,nextPage`。连接探测只证明商品列表读取成功，不证明写权限、其他API权限或云端可达。

商品只输出已核摘要字段 `id,product_id,subject,status,display,red_model,group_name,category_id,language,pc_detail_url,main_image.images`，未知字段不透传；详情暂不输出SKU、价格或完整详情结构。非末页短页及页内重复ID返回失败。详情须由原始数字 `id` 匹配请求；未返回数字id时按既有验收规则核 `https://www.alibaba.com/product-detail/..._{请求ID}.html`，不把可能加密的 `product_id` 当作数字ID。商品读取成功仅代表平台字段，并不证明实物、自产或库存。

Python集成可调用 `execute(command,client=...,page=...,page_size=...,product_id=...)`。注入客户端实现 `call(method,params)`；生产默认使用 `ExistingClient`，读取现有外部配置，不复制凭证。输出过滤敏感字段、已加载密钥原文及带签名URL；异常和平台原始错误文字不出边界，仅返回稳定错误码。生产应通过私有诊断流程使用原客户端定位，不将其原始stdout/stderr透传给网页。

当前仅完成本地代码及离线注入测试，没有实际联网或云端部署验收。原客户端与外部凭证须存在于执行环境；服务器授权、受控调用入口、私有存储、上次成功/过期记录、调度与UI由主系统接入。不得将 `cloudReady=false` 或本地能力描述显示为云端已运行。

写能力待接入：后续必须按具体操作建立类型化差异、对象范围/授权、请求回执、正式回读及本地档案双改流程；现适配器不提供发布、更新、库存、发信或任意API通道。自然曝光、点击、询盘等数据管家指标不属于本适配器，原应用权限也未证明已接入，不能以商品数替代。
