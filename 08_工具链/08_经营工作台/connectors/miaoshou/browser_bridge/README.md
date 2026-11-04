# 妙手店铺只读浏览器桥接（待审查原型）

本目录是未安装、未授予权限、未连接真实店铺的原型。支持用户在妙手正常登录后，由工作台对**指定店铺**读取身份及商品分页，供现有 Agent 调用；不支持任何业务写入。浏览器以自身登录态向妙手发送固定请求，不读取、复制或输出浏览器凭据。扩展不使用 cookies、webRequest、debugger 权限；服务端不接收原始妙手响应、请求头或凭据。返回只包含商品 ID、名称、标题、状态、类目和分页字段；错误只用固定代码。商品与店铺 ID 是内部业务信息，不应进入公开仓库或普通请求日志。

店铺身份必须来自现有私有配置，绝不由 Agent 临时猜测。工作台生成 5 分钟有效的一次性配对码，用户在当前目标店登录页的扩展弹窗中输入；服务端核对扩展来源和店铺 ID，生成仅保存在服务端内存及扩展 `storage.session` 的配对令牌。每次查询前、后由扩展读取并核对目标店，服务端还会再次核对，失败不返回商品数据。令牌需要妥善保管，不能写入日志、Git 或浏览器页面。刷新/关闭配对页会使连接离线；扩展或服务端重启后应重新配对。配对不是平台官方开放接口授权，网页登录可能过期，页面接口也可能变化。

## 服务端集成契约

`miaoshou_bridge.MiaoshouBridge` 为线程安全内存对象，不绑定 HTTP。仅工作台本机 UI 的既有同源端点调用 `issue_pairing(expected_shop_id)`；返回的配对码仅显示给操作者。其余三个桥接端点使用下表（所有请求 JSON，固定本机地址 `127.0.0.1:8766`）：

| 路径后缀 | 输入 | 返回 |
| --- | --- | --- |
| `pair` | `{code,shop_id}` | `pair(code, Origin, shop_id)` 返回 `{token}` |
| `poll` | `{}`，Bearer 令牌 | `{task: poll(Origin, token)}` |
| `complete` | `{task_id,payload}`，Bearer 令牌 | `complete(Origin, token, task_id, payload)` 的返回值 |

三个端点完整前缀均为 `/api/desk/miaoshou-bridge/`。服务端必须仅对这些端点允许符合 `chrome-extension://[a-p]{32}` 的 Origin；除首次以一次性码配对外，始终验证配对时绑定的确切 Origin 和令牌。其余原有 API、签发配对码端点继续使用现有本机 Host、Origin 校验。提供必要的 OPTIONS 预检时，同样限定路由、Origin、`POST` 与必要请求头，不使用 `*`、不允许凭据跨源；拒绝非预期 Host。限制请求体大小，不在访问日志或异常日志记录 body、令牌、配对码或原始请求头。浏览器扩展 Origin 是额外绑定，不替代高熵一次性码和令牌，因为本机非浏览器进程可以伪造 Origin。

Agent 在现有执行器调用 `submit('connection-check', {})` 或 `submit('products', {page, pageSize, isDraft?})`，再用 `get_result(task_id)` 读取完成状态；`status()` 返回在线情况。任务 60 秒未完成返回 `bridge_disconnected`。只接受固定操作和参数，不接受 URL、脚本或请求方法。

本目录已接入工作台的受限路由和抖店 Agent 读取工具。Chrome 是否实际安装、MV3 加载、扩展到本机的 CORS/Private Network Access 预检行为和具体妙手页面返回格式尚未实机验证；视浏览器版本可能需要受限的预检响应或浏览器侧用户许可。不可为了通过验证而放宽全局来源或转发凭据。安装和站点权限须在审阅后取得用户明确确认。

## 隔离测试

在工作台目录执行 `python -m unittest tests_miaoshou_bridge.py -v`；在本目录执行 `node test_browser_bridge.mjs`。测试使用伪造响应，不访问店铺网络，不证明真实登录、数据权限或 Chrome 加载成功。
