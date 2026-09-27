# 数据管家流量导出 · 方法与数据字典（2026-09-27）

> 本目录是**数据管家（阿里国际站卖家后台）官方数据的首次导出留档**，含导出通道的完整复现方法。
> 目的：让后续分析（含 AI 辅助）能直接基于**平台原始数据**工作，而不是基于页面截取或第三方推测。

---

## 一、本目录内容

| 路径 | 内容 | 规模 |
|---|---|---|
| `流量与关键词诊断_2026-09-27.md` | 基于本批数据的诊断报告 | — |
| `BQ标题改造方案_2026-09-27.md` | BQ 系列 46 款标题方案（HR 已排除） | — |
| `数据/Products-2026-09-19.csv` | 逐款绩效，**365 款 × 29 指标** | 70 KB |
| `数据/getKeywords-2026-09-19.csv` | 关键词绩效，**500 词 × 11 指标** | 26 KB |
| `数据/BQ标题改造方案.csv` | 46 款标题新旧对照 + 主攻词 + 依据 | — |
| `数据/BQ目标_真实属性.csv` | 46 款的系统属性原始值（标题事实依据） | — |

**原始 `.xls` 未入库**，符合本仓库 `.gitignore` 既有约定（第 80–81 行 `*.xlsx` / `*.xls`，注释：*Heavy binary deliverables stay local and are represented by text indexes*）。平台的原始导出文件保存在工作区 `beiqiang_体检/exports/`，`数据/` 下的 CSV 是由其**逐格转换**而来（行数已校验：365 / 500 数据行），可作保真核对。

**数据周期**：2026-09-13 ~ 2026-09-19（PST）
**店铺**：`cn1576227362luzl`
**导出时间**：2026-09-27

---

## 二、两条通道（关键：流量数据必须走第二条）

数据管家的数据分两类，**获取通道完全不同**：

| 数据 | 通道 | 说明 |
|---|---|---|
| 商品侧（标题/属性/质量分/库存/分组/图片） | ✅ **开放平台 API** | 已有权限，可自动化 |
| 流量侧（曝光/点击/访客/询盘/**词来源**） | ⚠️ **浏览器导出** | API **拿不到**，见下 |

### 为什么流量数据不能用 API

官方权限矩阵（`https://open.alibaba.com/doc/doc.htm?docId=107343&docType=1#/?docId=44`，文档中心 → 开发者指南 → API权限申请）：

| 开发者身份 | API权限组 | 获取方式 |
|---|---|---|
| **服务商** | 含 **国际站数据管家基础权限包** | 通过 `fuwu.alibaba.com` 应用工具类目服务商申请通过后可申请 |
| **商家** | 国际站订单管理权限包 / 国际站基础权限包 / ICBU-物流-快递 | **默认获取（无申请入口）** |
| 买家/分销 | 国际站海外分销 | 按解决方案申请 |

**我方应用是「商家」身份**（`SELF_APP2218064103529` / AppKey `513180`），默认权限中**不含**数据管家，且文档未给商家申请路径。

实测验证（排除法）：`alibaba.mydata.self.product.get` 在**未补齐参数**时返回 `MissingParameter`，**补齐必填参数后**立即变为 `InsufficientPermission` —— **说明权限校验在参数校验之后**，参数不全会掩盖真实权限状态。

> 结论：`alibaba.mydata.*`（曝光/点击/访客/询盘/来源关键词）与 `alibaba.scbp.ad.report.*`（直通车报表）**当前无法通过 API 获取**。
> ⚠️ 该结论基于 2024-06 更新的文档，**建议向阿里客户经理确认自研型开发者能否申请数据管家权限包**（两年前的政策可能已变）。

---

## 三、通道一：开放平台 API（商品侧）

### 凭据
- 客户端：`.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py`（**仅用标准库**，无需 requests）
- 凭据路径：`~/.config/beiqiang/alibaba-openapi.json`（权限 600，**仓外**，`.gitignore` 已覆盖）
- **凭证一律不写入 Git 或报告**（遵循 `02_Alibaba运营/AGENTS.md`）

### 已验证的接口与参数

| 接口 | 正确参数 | 返回 |
|---|---|---|
| `alibaba.icbu.product.list` | `language=ENGLISH`, `current_page`, `page_size` | 商品清单（**共 382 款**） |
| `alibaba.icbu.product.get` | `product_id`（加密 ID 或数字 ID 均可）, `language=ENGLISH` | 单个商品**完整数据**（22.8 KB：attributes / product_sku / sourcing_trade / struct_detail） |
| `alibaba.icbu.product.score.get` | `product_id`=**加密 ID** | `final_score` / `boutique_tag` / `problem_map` |
| `alibaba.icbu.product.sku.inventory.get` | `product_id`=**数字 ID** | `data_list[].inventory` |
| `alibaba.icbu.product.schema.render` | — | ⚠️ 返回空壳，**不可用**，用 `product.get` 代替 |

### 踩坑（重要）
1. **分页参数是 `current_page` / `page_size`**，不是 `pageNo`/`pageSize`（后者被静默忽略并**反复返回第 1 页**）
2. **接口把 `page_size=50` 截断为 30/页** → **不能用「本页不足 page_size」判断结束**，必须用 `total_item` 判定
3. `product.list` 返回的 `id` 是**数字**、`product_id` 是**加密字符串**，不同接口要的不一样（见上表）
4. **`keywords` 字段 382/382 全为空** —— 待确认是新版已弃用还是确实没填

### 复现
```bash
cd beiqiang_体检
python fetch_details.py      # 382 款全量（6 线程并发 + 断点续跑，约 100 秒）
python fetch_target_attrs.py # 指定目标集的完整属性
```

---

## 四、通道二：数据管家浏览器导出（流量侧）★ 核心

### 为什么需要浏览器
数据有页面、有「导出数据」按钮，但**没有 API**。所以用真实浏览器打开页面、**点它自带的导出按钮**（而不是绕开导出直接打内部接口）。

### 真实域名（易错，务必记对）

| 用途 | 域名 |
|---|---|
| **数据管家** | `https://hz-mydata.alibaba.com/`（登录后 302 → `data.alibaba.com`） |
| **卖家后台 My Alibaba** | `https://hzmy.alibaba.com/` |
| **产品参谋**（逐款 29 指标，带导出） | `https://data.alibaba.com/product/overview` |
| **选词参谋**（关键词，带导出） | `https://data.alibaba.com/traffic/keyword` |
| 店铺分析 | `https://data.alibaba.com/traffic/overview` |
| 员工分析 | `https://data.alibaba.com/account/account` |

> ⚠️ **`data.alibaba.com/home` 在未登录时是「数据参谋」的营销销售页**（满页"立即申请""商家案例"），很容易误判成"这里没有后台功能"。登录后根路径才是数据概览。

### 完整步骤

**① 启动真实 Chrome（独立 profile + 调试端口）**

```bash
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE="$HOME/.config/beiqiang/chrome-profile"

"$CHROME" \
  --user-data-dir="$PROFILE" \
  --remote-debugging-port=9333 \
  --no-sandbox --disable-gpu \
  --crash-dumps-dir="$HOME/.config/beiqiang/chrome-profile-crashes" \
  --no-first-run --no-default-browser-check \
  https://hz-mydata.alibaba.com/
```

**四个必须理解的参数：**

| 参数 | 为什么必须 |
|---|---|
| `--user-data-dir=<非默认目录>` | Chrome 136+ **禁止**默认配置目录开远程调试，报错原文：`DevTools remote debugging requires a non-default data directory.` ⇒ 拿不到用户现有 Chrome 的登录态，需在新 profile 登录一次（之后持久保存） |
| 用**真实 Chrome 二进制** | 不要用 `Google Chrome for Testing` —— 那是另一个构建，指纹异常，国内平台登录/风控易失败 |
| `--no-sandbox --disable-gpu` | 若在受限执行环境内启动，Chrome 自身沙箱会初始化失败：`sandbox initialization failed: Operation not permitted` → GPU 进程 `exit_code=6` → `FATAL: GPU process isn't usable. Goodbye.`（CDP 端口会短暂 LISTEN 然后浏览器就退出）。这两个开关只影响本地进程，网页 JS 探测不到 |
| 后台任务方式运行（非 `nohup &`） | `nohup ... &` 起的进程活不过一轮工具调用，会被回收 |

**② 用户在窗口里登录一次**（账号密码 + 可能短信验证码，无法替代）。会话持久保存在该 profile 里，**之后不用再登录**。

**③ 用 CDP 连接并把下载重定向到工作区**

```js
const browser = await chromium.connectOverCDP("http://127.0.0.1:9333");
const ctx = browser.contexts()[0];
const page = ctx.pages().at(-1);

const cdp = await ctx.newCDPSession(page);
await cdp.send("Browser.setDownloadBehavior", {
  behavior: "allow",
  downloadPath: EXPORT_DIR,      // 明确指定，否则落到浏览器默认下载目录
  eventsEnabled: true,
});
cdp.on("Browser.downloadWillBegin", e => console.log(e.suggestedFilename));
```

**④ 导航到目标页 → 点「导出数据」→ 等文件落盘**

- 产品参谋的导出按钮选择器：**`a.product-effective-download`**（文案「导出数据」）
- 判断完成：先记录 `EXPORT_DIR` 原有文件集合，轮询出现新文件即为完成（`.crdownload` 是未完成临时文件）
- 导出文件名自带日期，如 `Products-2026-09-19.xls`、`getKeywords-2026-09-19.xls`

**⑤ 附带的页面结构读取**（不需要导出时也能取数）

```js
// 判断当前在哪一页不要用 document.title —— 该后台大量页面 title 都是
// "Alibaba Manufacturer Directory - ..." 这个通用标题，必须用 URL + 正文
const links = [...document.querySelectorAll("a")].map(a => [a.innerText, a.getAttribute("href")]);
```

### 复现脚本
```
beiqiang_体检/启动数据管家浏览器.sh   # 启动器
beiqiang_体检/cdp_export.js           # 在当前页点导出并捕获下载
beiqiang_体检/cdp_export2.js          # 导航到指定 URL 后点导出（可指定按钮文案）
beiqiang_体检/cdp_goto.js             # 导航并 dump 页面结构（菜单/按钮/表头）
beiqiang_体检/cdp_dump.js             # dump 当前页
```

### 解析导出的 .xls
平台导出的是**真 BIFF8**（`file` 报 `CDFV2 Microsoft Excel`，由 Java Excel API 生成），不是 HTML 伪装。用 `xlrd`：

```bash
python -m venv <venv> && <venv>/bin/pip install xlrd
python beiqiang_体检/parse_export.py "原始导出/Products-2026-09-19.xls"
```

⚠️ **表头不在第 0 行**：前 5 行是标题 + 空行，**实际列名在 row index 5**；第 0 行第 0 格是「表名,时间周期YYYY-MM-DD~YYYY-MM-DD」。稳妥做法是扫描前 15 行、取非空单元格最多的那行当表头。

### 已知坑
- 点标签页（如「关键词指数」）时，按文案匹配会同时命中父级容器 → 用 `querySelectorAll` 取**最后一个（最内层）**再 click；且**即使 click 返回 true 也要校验切换后列名是否真的变了**（否则可能导出的还是原标签页数据 —— 本次「关键词指数」导出即复现了该问题，重复得到「引流关键词」数据集）
- 平台对导出有配额：页面文案提示「**单日导出上限20次**」

---

## 五、数据字典

### `Products-2026-09-19.csv`（365 款 × 29 列）

| 列 | 含义 |
|---|---|
| 产品ID | 数字 ID（可与 `product.list` 的 `id` 及 `product.get` 互通） |
| 产品名称 | 商品标题 |
| 是否橱窗 / 是否顶展 / 是否P4P | 营销位标记 |
| **搜索曝光次数 / 搜索点击次数 / 搜索点击率** | 自然搜索表现 |
| 访问人数 | 商品页访问人数 |
| **询盘个数 / 询盘人数 / 询盘率** | 商机转化 |
| 近90天商机人数 | |
| 收藏人数 / 分享人数 / 对比人数 | 互动 |
| TM咨询人数 | TradeManager 咨询 |
| 提交订单个数 | |
| 产品负责人 | 子账号 |
| RTS线上买家数 / RTS线上实收GMV | RTS（现货）表现 |
| 全店曝光次数 / 全店点击次数 | 该商品贡献的全店口径 |
| 营销曝光/点击次数 | |
| 标准推广曝光/点击次数 | 直通车-标准推广 |
| 全站推广曝光/点击次数 | 直通车-全站推广 |

### `getKeywords-2026-09-19.csv`（500 词 × 11 列）

| 列 | 含义 |
|---|---|
| 词 | 关键词（**含多语种**：英语 / 法语 / 西语 / 葡语 / 意语） |
| 曝光量 / 点击量 / 点击率 | 我方该词表现 |
| 外贸直通车曝光 / 点击 / 推广时长 | P4P 表现 |
| **Top10平均曝光 / Top10平均点击** | **同行 Top10 基准 ← 差距分析的锚** |
| **关键词指数** | 搜索热度代理指标（越大越热） |
| **卖家规模指数** | 竞争度代理指标（越小竞争越小） |

> **机会词识别公式**：`关键词指数 ≥ 200 且 卖家规模指数 ≤ 10`（本次筛出 12 个）

### `BQ目标_真实属性.csv`（46 款）

每列的 `_属性` 段来自 `product.get` 的 `attributes` 原始值，是标题方案的**唯一事实来源**，可逐条复查。

---

## 六、给后续分析者的硬约束

### 1. 品牌词硬性排除
选词参谋页面平台原文警示：

> 「关键词指数是买家访问的客观呈现。使用词前请根据平台规则**自助查询①是否为品牌词，避免受罚**；②是否涉嫌违反《阿里巴巴国际站禁限售商品目录》的信息，以避免受罚。」

**本批数据中出现过**：`nike shoes`（词指数 259 / 我方曝光 289）、`adidas`（321 / 23）、`jordan shoes`（259 / 31）。
⇒ 这些词**一律不得写入商品标题、关键词或直通车词库**。

### 2. 不编造产品事实
标题与描述只能基于两类事实：
- **A. 系统属性** `attributes`
- **B. 作者已在旧标题断言的事实**（Thick Sole / Chunky / Anti-Slip / Mesh 等）

`Wide Toe Box` **不从外观推断**，只在该属性确有标注时才能写（本批 5 款）。
⚠️ 多值属性**不能按 `" / "` 截断** —— `Outsole Material = "Rubber / Plastic"` 若截成 `Rubber` 即篡改事实。

### 3. 标题长度上限 **128 字符**（本批 365 款实测：78–128，无一条超标）

### 4. 其他已实测口径
- 全店单日（2026-09-26）基准：曝光 9,247 / 点击 174 / 访问 117 / 询盘 1 / TM 咨询 9 / 搜索曝光 5,754 / 搜索点击 224
- 全店商品数：**382 款**（API），其中 BQ 181 / HR 197
- 系列流量结构（09-13~09-19）：**BQ 61.0% / HR 22.3% / 其它 16.7%**；全店 CTR 1.16%
- ⚠️ kaisuntd 多个商品销量同为 `300 sold` 且 MOQ 多为 300 pairs，**疑为平台展示规则，不可当真实成交**

---

## 七、下一批可拉取（通道已打通，无需重新登录）

| 目标 | 路径 |
|---|---|
| 流量参谋（流量来源/去向） | `data.alibaba.com/traffic/overview` |
| 访客详情 | 数据参谋 → 店铺 → 访客详情（⚠️ **不能导出**，且**只保留最近 31 天**，建议每月 2 号前处理） |
| 直通车效果 | 数据参谋 → 营销 → 直通车效果 |
| 关键词指数（全行业词库） | `data.alibaba.com/traffic/keyword` → 「关键词指数」标签页（本次未成功切换，需修正 tab 点击逻辑） |
| 商品细节（详情图/FAQ/公司图） | `alibaba.icbu.product.get` 的 `struct_detail` 字段 |

---

## 八、待确认

1. **数据管家权限包能否申请** —— 向阿里客户经理确认自研型开发者（商家身份）是否有路径（文档更新于 2024-06，可能已变）
2. **`keywords` 字段 382/382 全空** —— 新版是否已弃用该字段
3. **小语种流量来源** —— 无任何标题含法语词，却获得 1,325 次法语曝光（高于 `shoes` 的 1,089），**推断来自平台对英文标题的自动翻译**（非明文结论，需确认）。若成立，提升小语种曝光的正确做法是**把英文核心品类词写扎实**，而不是往标题塞外语词
