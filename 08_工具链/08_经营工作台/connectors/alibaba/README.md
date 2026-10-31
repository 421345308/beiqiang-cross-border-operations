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

`capabilities` 完全离线；其他命令显式发起一次平台只读请求。分页必须由调用者按 `pagination.nextPage` 再调用，不隐式抓全店。`page-size` 允许1–50，以平台返回的有效page_size计算下一页。列表参数固定 `language=ENGLISH,current_page,page_size`；详情固定 `language=ENGLISH,product_id`，无任意method/参数透传。详情仅接受数字平台ID；原加密 `product_id` 保留作平台原字段，不用作详情路由。

stdout一行JSON；成功退出0，业务/客户端失败退出1。无效CLI语法由argparse返回2及stderr说明。统一字段：`ok,operation,data,error,source,pagination`。`data` 为商品数组、单个商品对象、连接探测结果或能力说明；失败时为null，不能把它计为0件商品。`source.collectedAt` 只有有效业务响应才填写UTC时间；`attemptedAt` 是请求尝试时间。账号仅为固定连接别名 `beiqiang-alibaba-primary`，`identityVerified=false`，不宣称API验证了店铺身份。`pagination` 包含 `page,pageSize,total,returned,hasMore,nextPage`。连接探测只证明商品列表读取成功，不证明写权限、其他API权限或云端可达。

商品只输出已核摘要字段 `id,product_id,subject,status,display,red_model,group_name,category_id,language,pc_detail_url,main_image.images`，未知字段不透传；详情暂不输出SKU、价格或完整详情结构。非末页短页及页内重复ID返回失败。详情须由原始数字 `id` 匹配请求；未返回数字id时按既有验收规则核 `https://www.alibaba.com/product-detail/..._{请求ID}.html`，不把可能加密的 `product_id` 当作数字ID。商品读取成功仅代表平台字段，并不证明实物、自产或库存。

Python集成可调用 `execute(command,client=...,page=...,page_size=...,product_id=...)`。注入客户端实现 `call(method,params)`；生产默认使用 `ExistingClient`，读取现有外部配置，不复制凭证。输出过滤敏感字段、已加载密钥原文及带签名URL；异常和平台原始错误文字不出边界，仅返回稳定错误码。生产应通过私有诊断流程使用原客户端定位，不将其原始stdout/stderr透传给网页。

2026-10-31已通过当前原客户端实际只读验收：connection-check、商品第一页2件（总487）、该页返回数字ID对应详情、订单第一页2条（总30）及该页首条订单详情均成功。13项离线测试通过。脱敏回执位于工作台 `.local/alibaba/`（Git忽略），保留各自真实UTC采集时间与request/trace ID；没有批量抓取、刷新token或平台写入。尚未云端部署验收。原客户端与外部凭证须存在于执行环境；服务器授权、受控调用入口、私有存储、上次成功/过期记录、调度与UI由主系统接入。不得将 `cloudReady=false` 或本地能力描述显示为云端已运行。

写能力待接入：后续必须按具体操作建立类型化差异、对象范围/授权、请求回执、正式回读及本地档案双改流程；现适配器不提供发布、更新、库存、发信或任意API通道。自然曝光、点击、询盘等数据管家指标不属于本适配器，原应用权限也未证明已接入，不能以商品数替代。


## 查询合同（本地界面）

Python `execute("orders",page=1,page_size=20)` / `execute("order",order_id="列表返回id")`；CLI `orders --page 1 --page-size 20` / `order --order-id ...`。上限50，显式逐页，不自动跟页。订单list使用官方 `param_trade_ecology_order_list_query={role:seller,start_page:page-1,page_size}`，get使用 `e_trade_id,language=en_US`。官方文档：[list](https://developer.alibaba.com/docs/api.htm?apiId=41047)、[get](https://developer.alibaba.com/doc2/apiDetail.htm?apiId=41148)。get文档标聚石塔内调用，不能由权限清单推定任意环境可用；本次本机原客户端实测成功不等于未来环境承诺。

商品列表 `data` 为数组、详情为对象，保留已列白名单字段，增加 `id:string`（原始数字ID或已核正式URL尾部数字）、`platformUrl=pc_detail_url`。标题 `subject`、图片 `main_image.images`、审核状态 `status`、显示状态 `display` 都保留真实原文；实测approved/Y不翻译成其他业务状态。数字id用于详情路由，加密product_id不能替代。采集日期在 `source.collectedAt`，不是商品创建/修改日期。

订单列表与详情仅投影 `{id:string,trade_id:string,create_date?:{timestamp,format_date},modify_date?:{timestamp,format_date},status?:string,trade_status?:string}`。日期为平台原始时间戳及格式化PDT/PST原文，不擅改时区或时间单位。实测列表只返回订单号及日期，不返回状态或金额，界面应显示未提供；不补0、不补成交结论。详情不输出buyer/seller姓名、email、地址、电话、备注、银行或合同。失败 `data=null,collectedAt=null`，通用稳定error.code；平台顶层安全错误码可保留error.platformCode，原文异常/消息不外泄。账号仍为配置别名且identityVerified=false，读取成功没有验证店铺身份。

能力矩阵 `capabilities.data.business` 包含 products/orders/inquiries/quotations/metrics/images/videos/showcase，各值 `{status,reason,methods:[],entry}`。只有 `data.read` 是已接入执行操作；authorized-not-integrated表示既有权限清单（2026-09复核）记录该读API，但本适配器未接入、本轮未实测，不展示执行按钮。询盘status为not-verified：既有权限清单未记录询盘/报价可用接口，本轮未实测，不据此判定当前未授权或平台不存在；客户及RFQ仍回原项目。自然指标数据管家需另授权及聚石塔，历史已实际返回InsufficientPermission，P4P不能代替自然指标；本地历史来源为 `02_Alibaba运营/04_周报与数据/` 与 `02_Alibaba运营/01_店铺与全店诊断/数据管家导出_2026-09-27/数据/Products-2026-09-19.csv`，只作带原日期历史，不伪称今日实测。图片库、视频查询/关联、橱窗读API在既有权限清单（2026-09复核）有记录，尚未本适配器接通、本轮未实测；该历史清单未记录video.upload权限。这不是本日全量鉴权结果；商品及订单列表、详情的本次实际成功读取另有上述回执。

## 最小商品操作提案（本轮未实现写入）

建议先做“单商品标题修改”：负责人选商品及优先字段后，读取该ID当前product.get及schema.render，生成仅productTitle差异，显示旧值/拟值及事实依据供审阅；复用 `08_工具链/01_业务脚本/国际站扩品/repair_hr_changed_title.py` 的values_only、正式基线比较、请求摘要和一次执行回执模式，以及现原客户端top_call/schema.update，不复制旧脚本硬编码商品/标题或既有HR授权。`update_hr001_title.py`也有已验最小productTitle Schema，但自身顶层会写，不直接import/执行该历史脚本。确认后才类型化具名执行，回读biz_success、正式product.get标题/审核状态，区分提交与生效/公开呈现；同步 `02_Alibaba运营/05_扩品工程/数据/国际站商品.json` 对应对象和既有商品档案。未正式生效保留待验收，不提前改成成功。结果未知先读回，不自动重放。图文修改以后沿同一Schema成功能力索引及图片库链路逐字段接入；本适配器没有任意method透传或写通道。
