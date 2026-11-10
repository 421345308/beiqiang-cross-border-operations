# 贝强本地工作台

入口：[打开工作台](http://127.0.0.1:8766/)。未启动时双击[启动工作台.cmd](启动工作台.cmd)。2026-11-01核对本机只在8766端口运行工作台；旧的8765地址请改用当前入口。

## 云端询盘与服务器（2026-11-10）

网站 [经营后台](https://www.beiqiang.online/admin/) 已发布统一入口；登录现有私有工作台后，经营总览展示网站业务询盘数、待处理数和通知状态，并可进入既有询盘处理页。正式后台接口无登录时返回 401。只读核对正式 API 与服务器 PostgreSQL 均有 6 条询盘，5 条为内部测试、1 条为业务询盘；该条网站原始状态为 `new`，邮件服务曾接受通知，是否送达收件箱与实际客户跟进另行核对。当前计数是 2026-11-10 的观察，不是实时指标。

本轮网站提交 `601d0ee`、`4df40ed`：收窄测试数据识别、完整分页读取；生产自建后端先提交询盘再尝试邮件，并以对象锁合并通知状态，避免覆盖并发人工备注。网站静态发布标识 `2026-11-10.1` 已在线；新加坡 API release `20261110T020912Z` 已切换，旧 release 保留。隔离 PostgreSQL 测试验证保存先于模拟发信及并发备注保留；网站全套 520 项测试中 515 通过、5 项默认跳过。浏览器使用隔离示例验证总览、打开详情及连接失败提示；正式后台登录页已打开，登录后页面仍待验收。实际生产未新造客户询盘或发送测试邮件。

该服务器 2 核、2 GB 内存、40 GB 磁盘；检查时可用内存约 1.4 GiB、磁盘可用约 31 GB。原代理、私有 API、独立网关与数据库运行正常；云 runner 已安装但未启动，Codex 设备登录尚未完成，任务仍为人工 Cloud 模式。现有网站及其数据库部署在独立服务器，可不依赖本地电脑运行，尚未做关机实测；本地素材、浏览器、SQLite 任务和自主 Agent 执行尚不能。密码登录、长期会话、云本地任务领取与恢复、及时提醒完整验收及公开采购顾问仍待实现或验证。SMTP 接受不等于实际收件，未知通知结果先核对再重发。

电脑控制已于本次恢复：窗口清单与腾讯云控制台实际操作成功。以下旧故障记录保留为历史，不能再作为当前控制不可用的结论。

## 批次研究进度与中断接续（2026-11-08）

客户批次的每次并行研究现保存为一个不执行的分组及逐客户 Agent 工作；原客户资料和草稿仍是成果来源。打开“本批研究进度与接续”可按客户查看状态和上次阻断原因，刷新后仍能读取；中途中断时明确点击“继续尚未启动的客户研究”，服务再次检查客户仍在批次且没有已知停止或重复阻断，只启动从未执行的子工作。实际启动认领时同一 SQLite 事务再次检查成员和共享抑制；未建立全部客户工作不会显示整个分组已完成。已有工作不会自动重跑，失败或结果不明仍须在原客户任务中核对成果后按现有方式接续。初次请求使用去重键，同一个请求返回原有任务；取消分组不会终止已运行子任务，也不会允许启动其余计划。

`agent_jobs.py` 和 `job_dependencies.py` 在原 SQLite 任务记录上增加分组、父子关系、前置依赖与按任务认领；旧记录无需迁移。`batch_research.py` 连接原批次、任务和页面；`server.py` 暴露任务图及显式计划、依赖和启动接口。依赖完成不会自动启动后续工作，动态分组不作为依赖，任务关系也未绑定业务输入版本；这不是通用自动调度器。`today.py` 不再让尚未执行的计划或分组遮住同对象真实失败任务。

本轮还修复两处检查：CRM 操作记录中“未发现退信、未退订”等明确否定不再误判为停止联系；实际退信、退订及历史触达仍阻断。只读核对实际 CRM 未发现现有同类误判，不能据此宣称某客户可发送。客户资料写入在失败前文件根本未变化时不再无谓替换原文件；真正需要恢复且恢复失败仍报结果不明。

**验证：** 下方客户、Gmail、任务、并发及工作台 Python 回归 507 项，503 项通过、4 项默认跳过真实浏览器/模型；前端 111 项通过。额外启用真实 Chrome 隔离验收，验证双客户切换、单客修改和研究接续，未发送；另从实际批次入口在隔离客户上启动两个真实 Codex 研究子任务，70.030 秒完成，分别保存客户资料和中英文草稿，父分组汇总两个完成，轨迹中未见联网搜索或命令执行，也未发送。隔离测试不使用真实客户或邮箱。原真实三客户批次、附件和此前准备的草稿继续留本机；未替负责人通过审核或发送。实际本机服务及无界面 Chrome 只读加载原批次，看到三张客户卡与新的研究进度入口。

```powershell
python -X utf8 -m unittest tests_agent_job_concurrency tests_job_dependencies tests_batch_research tests_customer_batches tests_customer_batch_http tests_batch_sending tests_outreach_checks tests_outreach_mcp tests_gmail_bounce_check tests_gmail_draft_concurrency tests_gmail_observations tests_gmail_event_reconcile tests_single_send_guard tests_customer_commercial tests_customer_concurrency tests_customer_revision_concurrency tests_customer_revision_race tests_customer_outcome_unknown tests_customer_analysis tests_customer_workspace tests_customer_workflow tests_customer_conversation tests_customer_http tests_customer_revision_http tests_customer_mcp_revision tests_business_context tests_desk_http tests_gmail_drafts tests_gmail_send_authorization tests_gmail_event_safety tests_gmail_sync tests_gmail_job_integration tests_gmail_mailbox tests_gmail_filter tests_gmail_translation tests_agent_jobs tests_job_recovery tests_runtime_backend tests_mcp_dossier tests_today tests_customer_batch_browser tests_outreach_live_codex
node --test --test-reporter=dot tests_desk_frontend.mjs
$env:BEIQIANG_RUN_BROWSER_TEST='1'; python -X utf8 -m unittest tests_customer_batch_browser -v
$env:BEIQIANG_LIVE_CODEX='1'; python -X utf8 -m unittest tests_outreach_live_codex.OutreachLiveCodexTests.test_two_research_agents_prepare_separate_synthetic_customers -v
```

**桌面控制排障：** 负责人确认 Any App 已开启；个人 `node_repl` 配置及应用内置 `cua_repl` 清单均曾指向升级后被移除的旧运行时，现已备份并将版本路径改到本机现有组件，控制权限及通信端点未改变。官方插件重装未生成运行配置，已还原受影响的生成文件；新的只读 Codex 会话实际加载 `node_repl`，`sky.list_windows` 仍因原生管道不存在报 `os error 2`，无法确认桌面控制恢复。当前应用 26.1029.9216.0，官方诊断及系统包管理器均显示有 26.1103.4239.0 更新；包管理器下载长时间无进展，另一次官方地址读取被 Cloudflare 返回 403/1010，已停止并清理空分段，没有绕过拒绝或安装更新。后续可由负责人使用应用自带的正常更新入口，再复测窗口；更新是否解决问题尚未知。备份仅留本机。隔离 Chrome 测试不代表桌面控制恢复。

## 客户开发批次（2026-11-06）

进入“客户开发 → 开发批次”。可以新建批次，按客户或候选、发现渠道和关键词筛选现有对象并批量加入；同一对象不会重复加入，误选或重复对象可仅从批次移除，不删除原客户或草稿。列表集中显示客户背景、来源、审核状态和草稿情况；打开一位后可查看来源及观察时间、产品匹配、原客户往来、中英文邮件和实际附件。每次最多选择 8 位客户并行研究；单客修改要求只交给绑定该客户和批次的 Agent Job，完成后在没有未保存输入时自动重新读取当前客户。研究及草稿保存在原对象及本地邮件草稿中，不建立第二套 CRM。Agent 没有发信工具，结果仍须重新阅读和审核。

先逐封核对收件人、主题、完整英文及中文对照和实际附件，再标记该版本通过；修改客户资料、草稿、附件或相关邮箱观察后，旧审核会失效。对 CRM 已完整读取但未匹配的客户，可以明确记录实际查过的别名、独立发送记录、停止联系记录及结果；该记录绑定来源、账号、收件人和 CRM 指纹，不改变原 CRM 的未知状态。明确退订、拒绝、退信、重复以及邮箱或退信覆盖不完整，不能通过该记录豁免。

选中已审核邮件后执行本次只读检查，全部通过才出现列明收件人、主题及数量的批次确认。逐封邮件也须先检查，预览通过后才显示最后确认。客户或准确邮箱被标为“不联系”后，其他批次及逐封发送都受到共享抑制。跨批次首次邮件按发件账号和准确收件地址认领；已有客户的最新入站邮件经线程、Message-ID、主题和地址核实后，逐封回复按该入站邮件另行认领。发送只记录 Gmail 实际回执；结果不明、中断及已使用计划不得自动重发，继续使用邮件页面的对账和人工确认未发送后的恢复入口。五分钟确认计划只对当时显示和检查的版本有效。

退信检查使用 Gmail 官方只读批量接口读取候选系统通知，同一账号且官方邮箱水位未变化时在进程内复用候选，逐个地址重新解析；缓存不落盘。检查最多覆盖 3 页、75 封候选，单封超过 12 MiB、批量响应过大、读取失败或内容无法判断时均为未知，不能当作通过。该检查不证明地址可送达、不覆盖其他邮箱及未知别名。[Gmail 批量请求文档](https://developers.google.com/workspace/gmail/api/guides/batch)。

**真实资料验收：** 已在本机私有状态建立一个包含 3 家北美鞋类候选的批次，研究来源、观察日期、产品匹配、个性化英文和完整中文对照及各自实际 PDF 附件均回原对象。1 家待负责人审阅；1 家公开地址只用于特定支持事项、1 家已有历史触达，均暂缓，不当成可立即首封。使用真实工作台 Agent Job 指定修改其中一家邮件的中英文问句，回读确认只有指定问句变化、收件人主题附件和另外两家草稿不变，该客户回原批次待审核。真实工作台的无界面 Chrome 实际加载了三家批次列表。真实 Gmail 对首个候选做过只读检查：当前账号查询覆盖 47 封系统通知，未发现该精确地址的退信；首次读取 43.0 秒、同水位缓存复用 12.1 秒。该结果不是其他邮箱或其他渠道的完整停止联系证明。没有替负责人通过邮件审核，没有发送邮件；客户资料、原始邮件、附件及批次状态留本机，不提交公开仓库。

**多窗口和邮箱：** 不同客户的批次审核按单客快照比较，其他客户更新不应导致本客户输入被覆盖。共享邮箱观察按账号、精确地址范围及 Gmail 官方 `historyId` 持久化元数据，完整观察前后水位一致时才更新；失败、不完整或 IMAP 无可比水位时保持未知，不存正文。Gmail 区的“邮件事件与任务核对”可查看实际事件、任务 ID 及状态；需用户选择并写明依据才关联已有任务，不启动或重播。历史任务没有明确事件来源时不得自动猜配，新 Gmail Job 记录准确事件来源。

同一个 SQLite 数据库内，Agent 对同一对象的创建和续接由短事务原子认领；另一个实例不会把仍存活的拥有者任务误标中断。拥有者及已记录子进程均已退出时才按实际状态标中断，不自动重跑。历史活动任务缺拥有者，或服务在启动子进程后、登记 PID 前崩溃时，可在任务区明确填写原服务 PID 和核验依据；系统确认已记录进程退出后只标记可恢复，仍须先核对可能未登记的子进程及成果，再显式续接。无法确认的状态不会自行释放。

实现及接口分别见 `customer_batches.py`、`outreach_checks.py`、`batch_sending.py`、`single_send_guard.py`、`gmail_bounce_check.py`、`gmail_observations.py`、`gmail_event_reconcile.py`、`desk_mcp.py` 与 `web/desk.js`。工作台、SQLite 和上述保护以同一台本机及同一个数据库为范围；其他邮箱、独立数据库、直接绕过服务的脚本或已在途外发不受同一事务保护。批次研究现有持久分组和显式接续；通用事件 Router、Watchdog 及最小跨业务一句话入口仍未接入，见 [ARCHITECTURE.md](ARCHITECTURE.md)。

**本轮验证：** 下列完整 Python 回归 466 项，462 项通过、4 项按默认设置跳过真实浏览器或真实模型；前端 110 项通过。显式启用后，隔离 Chrome 的双客户切换及局部修改 1 项通过；两个隔离客户的真实 Codex 研究任务同时运行并各自保存资料和草稿，1 项通过（54.740 秒）；另有单客草稿修改的真实 Codex 测试通过。真实模型测试消耗模型调用，使用合成客户、不连接真实邮箱、不发送。真实工作台也经无界面 Chrome 加载实际三客户批次，三个实际 PDF 附件均经 HTTP 下载回读、SHA 一致且各 22 页。负责人反馈已重启后复验：电脑控制插件在配置中已启用、组件可加载，但未发现原生通信管道；重置 JavaScript 会话后读取窗口仍报系统找不到指定文件（os error 2）。工作台服务本身正常，无界面 Chrome 验收不代表桌面控制已恢复；不要把再次重启当作已验证的解决办法。

```powershell
python -X utf8 -m unittest tests_agent_job_concurrency tests_customer_batches tests_customer_batch_http tests_batch_sending tests_outreach_checks tests_outreach_mcp tests_gmail_bounce_check tests_gmail_draft_concurrency tests_gmail_observations tests_gmail_event_reconcile tests_single_send_guard tests_customer_commercial tests_customer_concurrency tests_customer_revision_concurrency tests_customer_revision_race tests_customer_outcome_unknown tests_customer_analysis tests_customer_workspace tests_customer_workflow tests_customer_conversation tests_customer_http tests_customer_revision_http tests_customer_mcp_revision tests_business_context tests_desk_http tests_gmail_drafts tests_gmail_send_authorization tests_gmail_event_safety tests_gmail_sync tests_gmail_job_integration tests_gmail_mailbox tests_gmail_filter tests_gmail_translation tests_agent_jobs tests_job_recovery tests_runtime_backend tests_mcp_dossier tests_customer_batch_browser tests_outreach_live_codex
node --test tests_desk_frontend.mjs
$env:BEIQIANG_RUN_BROWSER_TEST='1'
python -X utf8 -m unittest tests_customer_batch_browser -v
$env:BEIQIANG_LIVE_CODEX='1'
python -X utf8 -m unittest tests_outreach_live_codex -v
```

## 客户分析与推进安排的版本保护（2026-11-06）

客户分析和推进安排的读取与保存由 `customer_workspace.py` 统一处理。页面保存必须带实际读取的 revision；分析还须带原来源 `source_hash`。同一数据库中的受支持写入在短事务内核对版本：缺版本返回 HTTP 400，旧版本返回 409；页面保留未保存输入，不自动重试。客户分析 Agent 启动及续接时记录输入版本，人工或其他入口修改相关上下文后，旧成果转为 `needs_input`，不会覆盖。旧任务没有记录版本时也不盲目保存。已确认发送后的客户状态更新携带流程版本，更新冲突不会重发邮件。

`desk_mcp.py` 提供 `get_customer_profile` / `save_customer_profile` 与 `get_customer_workflow` / `save_customer_workflow`，只对当前绑定客户工作，保存必须使用此前读取的版本；只读模式禁止保存。`desk_cli.py capabilities list --query customer_` 可发现这些定义，但 CLI 尚无对应的独立客户读写命令。版本字段从现有资料计算，不需要 SQLite 迁移；调用旧接口的外部客户端需先更新并读取版本。

已用两个独立进程竞争相同分析和流程快照，各有一方成功、另一方冲突；双连接还验证提交后插入人工修改时，后续自动步骤沿用自己的旧版本而冲突。真实本机 HTTP 与 MCP 交叉写入也验证旧版本被拒绝。隔离数据下实际启动全新的无界面 Chrome，加载工作台页面，分析和流程两处均验证冲突提示、输入保留及另一方新值保留；用户可先复制输入，再明确放弃本次修改并读取新值。后台刷新失败及主动重读失败也不会清空正在编辑的内容。测试不是已登录桌面浏览器验收。未读取真实邮箱、未发送邮件、未修改真实客户。

**真实 Agent 验收：** 事务快照修复前后分别在临时工作区对合成客户启动一次现有 `AgentJobs` draft；修复后的 Codex CLI / `gpt-6.1-sol` 任务以 attempt 1 完成并保存会话，耗时 83.526 秒。CLI 记录显示调用 `get_business_context`、上述四个客户工具并重新读取两项结果，均成功。服务回读确认分析摘要和下一动作均为测试标记，原始需求未改变。随后补强原来源发生变化时的冲突分类，以合成数据竞争测试验证。轨迹未出现联网搜索或命令执行；draft 后端仍允许网络，不声称本次处于网络硬隔离。只含合成数据与工具名称的本地验收结果留在 `99_临时区/客户MCP真实Codex验收/`，私有运行日志不入公开仓库。可用 `BEIQIANG_LIVE_CODEX=1` 显式运行 `python -X utf8 -m unittest tests_customer_live_codex -v` 重现，默认跳过且会消耗一次模型调用。

**本轮回归（2026-11-06）：** 在本目录执行下列命令，共 264 项，其中 261 项通过、3 项为默认跳过的真实浏览器及两项真实 Codex 集成；另执行前端模拟 DOM 测试 101 项全部通过。将 `BEIQIANG_RUN_BROWSER_TEST=1` 后单独执行 `python -X utf8 -m unittest tests_customer_browser -v`，真实 Chrome 1 项通过；可通过 `BEIQIANG_TEST_CHROME` 指定浏览器路径。测试使用临时工作区和合成客户，真实浏览器不使用现有用户配置。

```powershell
python -X utf8 -m unittest tests_customer_commercial tests_customer_concurrency tests_customer_revision_concurrency tests_customer_revision_race tests_customer_outcome_unknown tests_customer_analysis tests_customer_workspace tests_customer_workflow tests_customer_conversation tests_customer_http tests_customer_revision_http tests_customer_mcp_revision tests_customer_browser tests_customer_live_codex tests_business_context tests_desk_http tests_gmail_drafts tests_gmail_send_authorization tests_gmail_event_safety tests_gmail_sync tests_gmail_job_integration tests_gmail_mailbox tests_gmail_filter tests_gmail_translation tests_agent_jobs tests_job_recovery tests_runtime_backend tests_mcp_dossier
node --test tests_desk_frontend.mjs
```

仍有限制：跨数据库、绕开服务的手工文件修改、未纳入版本的外部来源竞争，以及文件和 SQLite 之间的崩溃原子性没有解决。冲突后页面没有并排合并界面，须保留输入、重新读取并人工核对。共享邮箱观察、事件与 Job 对账及基础任务关系已按上文继续实现；其覆盖范围有限，也没有通用 Router 或 Watchdog。

## Gmail 事件与 Agent 任务关联（2026-11-05）

现有 Gmail 新回复事件使用 `gmail_reply_events` 去重，旧表增量迁移 `job_id`、`updated_at`、`last_error`。满足现有筛选条件的回复先原子认领事件，再发布缓存并在锁外调用现有 Agent Job；成功时持久化实际 Job ID。已确认邮件不会被认领；若确认发生在认领之后，不会撤销已开始的回调。仅能证明尚未创建任务的同客户忙碌情况使用 `deferred` 并按间隔重试；回调异常、无 Job ID、旧 `failed` 或中断的 `dispatching` 均须核对，不自动重播。

远端改造提交：[2c90e22](https://github.com/421345308/beiqiang-cross-border-operations/commit/2c90e22fac86184ff1ad81773f09ec448538e6db)、[4c699b0](https://github.com/421345308/beiqiang-cross-border-operations/commit/4c699b0468d6caa276a4d28bdcc518efc7f842b5)、[6eb8fda](https://github.com/421345308/beiqiang-cross-border-operations/commit/6eb8fdaa7355d0cbec02e6a3e2a37380b2549b6a)。本机进一步补齐双连接认领、结果不明、确认交错、旧表及并发迁移测试。事件认领与任务创建不是同一事务；中途崩溃需要人工对账。较新回复到来时现有逻辑选最新回复，早先 `deferred` 可能留存且不自动关联新任务。此切片不是通用事件总线、Router 或 Watchdog。

## 客户商机写入冲突修复（2026-11-05）

MCP 客户商机写入要求先调用 `get_customer_commercial` 读取 revision，再传给 `save_customer_commercial`；版本不一致时重新读取合并。revision 覆盖商机、已保存 workflow、原来源 hash、已持久 Gmail 事件及确认标识；不依赖各进程私有邮件缓存。客户分析、工作流和商机的受支持写入口用同一 SQLite 短事务串行化派生 JSON 读改写；其他数据库及绕开服务的直接文件写入不受保护。

远端改造提交：[0c16d6f](https://github.com/421345308/beiqiang-cross-border-operations/commit/0c16d6f5c21762b51b3338ba59409c05bf4a4e6b)、[51ee035](https://github.com/421345308/beiqiang-cross-border-operations/commit/51ee0357c60c6109048f7e0b77d9be0f8f09f5ff)、[ae1585b](https://github.com/421345308/beiqiang-cross-border-operations/commit/ae1585b399cccf53aa0be6a3dae0e012fff4210f)。本机回归覆盖 Agent 旧 revision、下一步变化、双进程不同字段及同 revision 竞争。文件和 SQLite 不能保证断电原子；写入结果不明时 HTTP/MCP及客户分析任务提示先核对，不能盲目重试。2026-11-05 留下的分析和工作流客户端版本缺口，已按上节继续修复。

**本机迁移与端到端验收：** [本轮修复及测试提交 `c81a104d86434f0233da9b1c640b1a2fe830bce7`](https://github.com/421345308/beiqiang-cross-border-operations/commit/c81a104d86434f0233da9b1c640b1a2fe830bce7)。加载前真实 SQLite 事件表为三列、4条记录；使用 SQLite 在线备份并核完整性后重启，迁移后三个新列出现，原4条及其状态均保留。`tests_gmail_job_integration.py` 用合成来信与临时数据库，贯通 Gmail 过滤与事件持久化、`Workbench._gmail_reply`、真实 `AgentJobs`、事件回写 Job ID 与状态查询；另以显式启用的测试调用真实 Codex 完成隔离的模拟回复任务，未连接真实邮箱、未发信。常规测试默认跳过这项真实模型调用。

**回归命令与结果（本机 2026-11-05）：** 在本目录执行以下命令，共 208 项，其中 207 项通过、1 项为上述真实模型可选测试的默认跳过；另设环境变量 `BEIQIANG_RUN_LIVE_CODEX_TEST=1` 单独运行 `tests_gmail_job_integration.GmailJobIntegrationTests.test_synthetic_reply_runs_real_codex_without_real_mail_or_send`，1 项通过。测试的邮件、客户和 Job 使用临时数据；不会证明真实 Gmail 送达、人工审核或经营效果。

```powershell
python -X utf8 -m unittest tests_customer_commercial tests_customer_concurrency tests_customer_outcome_unknown tests_customer_analysis tests_customer_workspace tests_customer_workflow tests_business_context tests_desk_http tests_gmail_event_safety tests_gmail_sync tests_gmail_job_integration tests_gmail_mailbox tests_gmail_filter tests_agent_jobs tests_job_recovery tests_runtime_backend
```

**2026-11-05 接续候选：** 分析和工作流的页面、MCP 与 Agent 版本保护，以及共享邮箱观察和事件与 Job 的可查询对账、人工关联已按上节继续实现。持久父子任务、依赖、Worker Session、Fast/Slow Path 和 Watchdog 并未因批次并行工作而实现。

## Agent Runtime 代码审计与接续（2026-11-05）

审计基线：GitHub `main` 与本地 HEAD 均为 `8233301b7133b475867a069c3f937d0ce2d9c2f6`，另有不属于本任务的未提交文件；以下按实际代码而非设计目标分类。目标边界及决策见 [ARCHITECTURE.md](ARCHITECTURE.md)，产品体验见 [PRODUCT.md](PRODUCT.md)。

| 能力 | 当前判断与代码依据 |
| --- | --- |
| 自主执行和连续工具调用 | **部分实现**：`agent_jobs.py` 启动持久 Codex 会话，`desk_mcp.py` 提供业务工具，Agent 可连续调用；业务提示、业务成果与状态仍耦合在执行器中。正常任务和邮件提取使用不同权限配置。 |
| 动态规划与多 Agent | **部分实现**：普通 Codex 任务可使用现有多 Agent 功能，不同业务对象任务可并行；没有工作台可查的父子任务、依赖、委派范围或汇总协议。单服务内同对象和旧进程检查不是跨进程协调。 |
| 状态和恢复 | **部分实现**：SQLite `agent_jobs(id,data)` 存任务状态、事件、尝试与 session；服务启动将活动任务标失败，需核旧进程/成果后手动继续会话。此前真实验证取消并继续；服务崩溃仅用真实 PID 模拟，未实现步骤检查点、局部重试或外部恰好一次。旧 `server.py` 的 `runs` 为另一条兼容路径。 |
| 上下文和成果 | **部分实现**：`business.py`、`business_context.py` 和 `desk_mcp.py` 读取原对象及资料；`business_artifacts` 只存索引，成果正文留原对象 `.local`。创作项目上下文仍有专门分支；不是统一的跨任务共享上下文或事实库。 |
| 能力发现和共用服务 | **部分实现**：`desk_mcp.py` 的静态工具定义及 `desk_cli.py capabilities list` 支持基础发现，当前数量和具体定义以代码为准；未按对象/实际连接状态完整筛选，UI 另有静态清单。画布和商品素材的 UI/MCP/CLI 共用 `creation_canvas.py`、`product_creation.py`；国际站商品修改和 LibTV 等并非都已暴露给 MCP/CLI。 |
| 多模型、外部任务与费用 | **未完整实现**：当前真实执行后端是 Codex CLI；外部平台任务和本地任务没有统一状态同步。业务日志是受控本地诊断，并非统一可追踪的跨服务账本；未知耗费与账单不能据此推算。 |

**仍需处理：** 分析与工作流的客户端派生版本已按上节接通；未满足 Gmail 派发条件的缓存变化仍不保证跨进程可见。下一轮优先处理持久邮箱观察、事件与任务对账及人工接续，再逐步建立父子任务与 Worker/Watchdog；具体取舍按实际业务瓶颈决定。

**本轮改造：** [代码与架构审计提交 `84cec8164f148f573152a2f67815607982ad0c9b`](https://github.com/421345308/beiqiang-cross-border-operations/commit/84cec8164f148f573152a2f67815607982ad0c9b)。`codex_backend.py` 提取 Codex 命令、进程创建与输出事件转换；`agent_jobs.py` 仍负责任务状态、业务上下文、进程管理、取消及成果写入，并接受可信 Python 调用方注入符合当前契约的后端。默认模型和普通任务、邮件整理、客户分析的权限与命令保留；`tests_runtime_backend.py` 验证注入、事件与用量边界，既有执行器及恢复测试保护兼容性。该接口仍依赖本地子进程、PID、标准流和最终文件，**不是**多提供商或远端执行器已接通。

每次尝试的 `attempt_usage` 保存实际观察到的每个完成事件中的已知非负 token 字段；未报告是 `null`，没有完成事件是空列表，费用是 `null`。取消后观察到的缓冲事件可记录用量，但不改变取消状态或发布成果；无法观察的耗费仍未知。缓存输入、推理输出等字段可能包含于其他字段，不直接相加；这里不是账单。原始诊断按既有上限留本地，不写入公开仓库。

**自动验证：** 在工作台目录运行 `python -X utf8 -m unittest tests_runtime_backend tests_agent_jobs tests_job_recovery tests_customer_analysis tests_gmail_translation tests_desk_http tests_canvas_agent tests_canvas_concurrency tests_product_creation tests_mcp_dossier`，本轮 90 项通过。独立复核了普通、邮件和客户分析三模式的新建与恢复命令；替身后端验证接口只证明本地适配契约。真实任务及运行回读见下方验收记录，商业或平台效果不由代码测试推断。

**真实执行验收：** 重启加载后，用 `product:BQ009` 发起只读内部选款审阅，任务 `87a5be1c640f4a7bbdbd91e1f490bd13` 经实际 Codex 完成、保留 session 并保存原对象成果 `79bac9a226394990b679b007401a2db2`；读取审计有11条，其中9次成功读取来源。SQLite 回读本次一条完成事件的 input 566,960、cached input 484,736、output 5,696、reasoning output 2,797 tokens，cost 为未知；字段可能包含关系，不相加，数字只说明该次实际回报，不代表效率提升或账单。原文及诊断留本地对应任务，不向公开仓库提交。成果是内部审阅，未实时查询或修改平台，也未发送客户。

2026-11-05 按 [Agent增量架构](ARCHITECTURE.md)接续：内部 Agent 可读取并保存当前创作项目画布，也可查询已索引商品素材并将其引用到当前项目；与页面共用业务服务及版本。CLI 用 `capabilities list --query canvas` 查询现有 MCP 工具定义，`product-creation options <商品ID>` 查素材和项目，`product-creation add` 复用素材；工具定义中的连接、权限和费用不能当作已验证状态。独立数据库连接同时写同一画布时由 SQLite 原子检查版本，冲突须重新读取合并；这不覆盖手动文件编辑或其他服务，也不是跨进程任务锁。

真实对象验证：BQ009 经商品服务查得40项本机可用素材；ZX9507 原创作画布保留原节点，新增工厂侧面原图引用和可编辑R03方案，Agent服务保存后由本机工作台接口回读，旧版本保存返回冲突。两款未被错误关联；ZX9507 共用商品身份仍待核。2026-11-05续验：项目页面已列出原10秒成片，在页面播放并观察进度从0秒到3秒；R03节点经页面编辑、保存、刷新及Agent工具回读，内容一致。成片索引只复用受控媒体根，不代表作品审美或发布验收。画布保存在本机数据库，跨机器共享未验证。

任务恢复续验：BQ009和ZX9507两项真实对象工作曾同时运行；BQ009在会话建立后取消，原进程退出后以同一会话接续并完成，ZX9507内容审阅也完成。当时对同对象历史任务残留进程、状态不明或线程收尾进行检查；不同对象可并行。那次实际验证的是取消后的接续；重启残留进程保护用本机真实PID模拟，不等于真实崩溃恢复。此后已按客户批次章节扩展为同数据库跨实例原子认领；手动CLI、其他数据库和外部提交仍不受此保护，通用步骤检查点尚未实现。

BQ009真实任务首次接续发现，产品记录已指定唯一当前档案，但该档案未进入Agent来源清单。现按该明确标记、精确型号及档案标题识别原档，并沿用路径安全校验；同一任务再次接续，实际分四段读完53,286字并保存复核成果。历史渠道状态按原日期使用，本次没有实时复核平台。任务及读取证据留本机 `.local/agent-jobs/`，不替代商品原档。

工作台目前提供中文工作区、客户发现与研究、独立站询盘处理和创作入口。长期路线及后续范围见[PRODUCT.md](PRODUCT.md)。完整渠道修改、创作及经营反馈仍待贯通。

2026-11-04 品牌店续查：负责人登录后，妙手网页核实品牌店名称及56条商品，正常导出的全店SPU文件读回56行。抖店页“查看品牌店商品快照”显示18:49的来源、标题和数量；原文件仅有商品ID及标题，不表示实时状态、库存或价格。自动审核因凭据泄露风险拒绝了浏览器会话向本地客户端交接，未读取或保存该凭据；工作台独立HTTP会话仍过期，旧店仍需独立续登并核目标。快照在本机受忽略目录，不会自动刷新。

抖店现已接入统一 Agent 对象与妙手只读浏览器连接代码，可在配对指定品牌店后查询身份及分页商品；当前组件未安装、未配对，真实接口和店铺读取尚未验收。负责人已同意安装及配对；浏览器工具拒绝打开扩展管理内部页面，原因是该工具的网址策略只允许 HTTP(S)。不复制浏览器凭据或绕过该限制。连接组件完成合法安装并配对后，先验证身份、登录状态、商品分页及实际 Agent 调用，再按结果扩展经营能力；旧店继续单独绑定和核验。

2026-11-04 继续推进：BQ018 的 R1、W1 两条在18:16正式回读均为审核通过、展示状态 Y、评分5.00；买家页本次跳转登录，公开呈现仍待验收。国际站渠道页保留13:48–14:06历史质量扫描，并在相关链接旁单独显示商品档案里的官方复核评分，不把旧扫描总数当成当前低分数量。抖店页新增手动“检查两店连接”；实际页面检查显示旧店会话过期且目标未绑定，品牌店会话过期，均未取得商品。未绑定旧店只在主动检查时核会话，不读取商品或自动绑定；现有工具没有网页登录会话导入机制。商品素材加入画布前可查看选中图片及放大预览，选择真实项目后才执行；客户商机按已登记产品 ID 或明确现行型号精确关联，冲突标歧义，不靠别名猜配。

2026-11-04 搜索连接续接：负责人同意并接受 Google API 条款后，已在现有授权所属项目启用 Search Console API；工作台选中 `https://www.beiqiang.online/`，首次真实读取成功，页面和接口均已核验。2026-10-05 至 11-01（太平洋时间，最终数据，网页搜索）展示 1205、点击 3，读取时间 11-04 16:14（北京时间）。这是 Google 自然搜索表现，不等于网站总访问、询盘或订单；搜索词等明细可能不完整。

2026-11-04全渠道改造：总览并列进入外贸客户、国际站、抖店和内容创作，并可进入商品及独立站。商品详情读取原档明确身份对应的抖店历史记录与独立站源码关联；抖店按原档区分店铺、版本和日期。重启后已在实际页面核对 BQ031 的三条抖店历史对应。网站关联已扩展为源码生成的商品目录，与当前网站源码的133条编号和地址核对一致，按产品中心明确的产品 ID 或现行型号匹配，本机现有资料中133条精确对应产品中心，身份重复时标记歧义；重启后 BQ009 和 BQ1049 已在页面显示对应网址，未匹配不代表未上架，源码对应不代表公开页面验收。

本轮实际连接：先前受限执行环境的代理连接失败；正常宿主网络下，官方客户端成功完整读取 488 条商品目录，2026-11-04 13:48 字段组合为 approved/Y 480、approved/N 6、tbd/N 2；不等于买家页验收。工作台页面也于13:47读到 BQ031 指定链接的平台图文。逐商品质量分已只读采集：2026-11-04 13:48–14:06 共尝试488条，482条取得分数（477条5.0、5条低于5.0），6条平台返回通用验证失败，不能记为达标；工作台显示采集时间、覆盖、失败和平台原文，不当作实时流量或询盘。BQ-9002 补图和 BQ018 后续变更的最新状态以各单款正式回读为准，采集结果不会自动更新。Search Console 已选择贝强网站并完成首次真实读取，详见上方连接续接记录。抖店两家保存的妙手会话均过期，旧店还缺目标绑定；现有工具不能自动从网页登录取得会话，两店均未取回商品。历史数据继续标注统计期，不能代替当前表现。

商品素材可选择后引用到指定的现有创作项目画布，不复制或覆盖原文件；后端核对商品素材归属、文件、项目和画布版本，并防止重复添加。重启后 BQ009 页面已实际加载素材与项目选择，测试环境完成保存、回读及冲突验收；尚未向真实项目写入，素材引用仅由用户选择项目和素材后执行。客户 Agent 在读取原报价、样品、订单记录时按明确款号精确查找产品中心商品，保留记录状态，未匹配和歧义不猜配，该能力通过自动测试。

渠道页的“商品经营分析”读取国际站已有逐链接经营复核，展示2026-10-11至17日的历史曝光、点击、访客、询盘与当时建议，可按行动筛选并进入对应商品查看平台链接。匹配使用平台链接ID；换款或该历史期间之后的变化需结合当前商品判断。当前不自动更新这些经营指标，也不会根据历史数据自动修改商品。

2026-11-03新增：从渠道分析进入商品时直达对应国际站链接；商品详情可调整六张主图顺序、选择该商品已有本地图片替换主图，也可调整详情图组的顺序或替换固定位置图片，查看前后方案后提交及回读。详情替换保留原位置角色、文字及分组，暂不增加图片数量或新组。准备时按当前平台商品与图片银行关联，首次可能需要几分钟；BQ009已完成真实只读结构核对，上传、提交和回读流程使用模拟平台验收，未对真实商品执行本次改动。客户详情可记录报价、样品和订单的当前情况与下一步，保存在原客户档案；这是内部记录，不会自动报价、发信或创建订单。

工作台Agent的 `get_business_context` 现场读取负责人规则、当前目标和重点、当前商品或客户原档、客户报价/样品/订单进展、对应渠道状态和已有下一动作；`list_artifacts`、`read_artifact` 读取当前对象既有成果，优先复用并按需核对原件，不新增独立事实库；`save_customer_commercial` 可按委托把草稿和实际进展写回当前客户。BQ009与已有客户已做真实只读验收；仍需按具体任务读取相关往来和原件。

2026-11-04针对自主经营改造：普通对象任务以项目根目录为工作区，保留用户配置、项目文档、可用插件和持久会话，并启用多 Agent 选项；按本次委托及既有授权执行本地研究、资料与代码修改、测试和适用的 GitHub 同步。同对象任务现在按同数据库短事务在不同服务实例间认领，不同对象可并行；涉及共享文件时仍须按总控工作流协调主办和串行 Git 操作，该机制不是通用文件锁。对象页可新建、取消或按原会话继续工作；失败或重启后先核已有文件和进程，不自动重跑。旧 `--ephemeral` 工作没有可恢复的会话。

限制审查：原执行器显式设置了 `read-only`、`--ephemeral`、`--ignore-user-config`、禁用多 Agent/插件和 `project_doc_max_bytes=0`，这些是项目配置而非已证明的平台强制限制；原用途是把对象任务限制为读取与草稿。它们不再用于普通经营任务。客户来信自动触发的草稿和结构化翻译仍使用只读、隔离插件的专用模式；MCP 对该模式也拒绝业务写入。邮件翻译器、停用的旧云 runner 及旧兼容运行接口各自职责不同，本次没有把它们当成普通经营执行器统一放开。

客户开发邮件及跟进继续由负责人审核具体收件人、主题、正文和实际附件；付款、生产承诺及未授权敏感动作须先确认。普通 Agent 遵循这些项目指令，工作台 Gmail 界面保留逐封审核发送；继承的其他插件、命令和外部服务不受工作台邮件界面的技术门禁统一约束，不能把提示词当成跨工具的强制权限系统。GitHub 同步由 Agent 在经过验证后按项目现行授权执行，并报告失败；目前没有独立的自动发布器或可证明覆盖所有阶段成果的强制同步机制。

真实本机 CLI 已完成工作区写入、同一会话续接和 `git ls-remote` 读取远端测试；具体插件、多 Agent 分工、跨机器恢复和实际经营效果仍需按真实任务分别验收。两处既有 GitHub 仓库均为公开仓库，客户原件、联系方式、订单隐私和凭证不得同步到其中；私有跨机方案与当前连接状态见 [Muse–Codex 协作](../04_MCP与Workctl/Muse-Codex协作.md)。

2026-11-04真实客户验收：候选、选款、双语审核稿和附件回到同一客户对象；实际复核纠正了人工对商品链接的误判，首轮约7分钟。新增成果读取工具后，同一任务按原会话续接，3次业务工具调用、约76秒完成当前稿复核；两轮工作量不同，不能据此计算性能提升。负责人尚未审核，也没有客户外发或反馈，经营效果尚不能判断。

“渠道 → 独立站 → Google 搜索表现”支持单独授权 Search Console、选择已有站点，读取搜索词、页面、国家及展示点击；授权后工作台运行时按上次成功时间自动更新，也可手动刷新。2026-11-03代码及模拟接口测试通过；此前首次授权后站点列表返回403；现已启用项目 API、选择站点并完成真实读取，见上方连接续接记录。本机关机时不更新。复用现有Google桌面客户端，搜索读取权限需单独授予。

## 现在怎样使用

1. 从商品或客户进入（重复的资料导航已移除），搜索款号、公司或需求；查看原资料、关联素材及已有成果。
2. 商品或客户对象页可在“交给 Agent 执行”中说明目标，继续已有工作；也可在当前 Codex 对话交办。商品页逐条检查国际站标题、主图和详情图。
3. 在客户页面查看往来、编辑草稿并审核发送；已有成果仍可查看和编辑。跨对象任务的进展与成果保留在各业务对象。

总览按需要决定、待处理、等待与进行中展示客户回复和实际工作；状态已推进的旧失败不再重复提醒。客户开发可新增和编辑公司、联系方式、业务摘要及下一步，并按类型和联系状态筛选；创作画布可添加带时长、画面、文案及素材的镜头，保存或导出分镜简报。

商品按已登记鞋型分类和筛选；商品详情把供货入口与国际站链接放在一起，并逐链接读取正式标题、主图、详情图和公司图，与本地记录比较。标题显示英文原文及自动生成的中文译文；平台读取时间与本地记录分开，平台暂不可读时不把旧记录当成实时数据。一个款号有多条链接时可切换检查；标题草稿仍可查看和审核。客户接入本地CRM/项目对象及网站原询盘；网站在页面打开时按120秒缓存期限后台更新，也可手动刷新。

### 客户开发与询盘处理

- **同行找客户**按公开资料中的中文公司登记全称展示，并附已有统一社会信用代码、来源和国际站店铺入口；可按公司、代码或鞋类搜索，复制当前筛选的公司全称及代码，或只复制公司名。未找到中文公司全称的店铺单独折叠，不混入海关查询名单；缺代码时明确显示未查到。资料依据及范围见[出口商反查](../../06_市场研究/01_竞品/出口商反查/README.md)。已关联的买家可直接打开；同名客户提示先查看原记录。海关数据中的出口方和买家仍以具体记录为准，工作台未接入海关数据库。
- **客户工作区**首屏把目标客户和当前询盘放在同一张工作列表，按“待我处理、等待客户、待开发”分组筛选；每行显示客户情况、下一步和状态，新回复排在前面。买家类型、关键词及已结束状态仍可筛选。客户详情可直接读 Gmail 中文译文、起草回复并审核发送；未发送的中英成果可带入邮件草稿。视觉和任务组织参考 [frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design) 与 [Linear 的收件分流](https://linear.app/docs/triage)。
- **客户资料包**用于整理准备发给买家的材料：从客户详情进入后可查看该客户关联材料和通用资料，也可按资料名称或款号查找已有文件和商品图片，编辑名称和关联客户、搜索或移除登记；一份资料可以关联多个客户，移除登记保留原件。这里不替代商品、客户档案，也不自动发送。
- **客户开发**读取原候选池，也可通过 Firecrawl 公开搜索鞋类买家线索，核对公司名称与来源后加入目标客户；客户详情可继续查找官网并交给 Agent 研究。搜索摘要不是海关进口记录，不代表当前采购意向。搜索由已随工作台同步的 `buyer_discovery.py` 实现，不再依赖另一任务的 `discover.py`；依赖运行环境已有 `FIRECRAWL_API_KEY` 和额度，未配置时显示实际状态。原 ImportYeti 网页抓取实验按[该站条款](https://www.importyeti.com/policies/terms)及客户发现助手现行决定不运行。
- **开发信审核**：2026-11-01负责人要求，每封客户开发信和开发跟进先审核具体客户、收件地址、主题、英文与中文对照及实际产品PDF，明确同意后才能发送；已发送对象不自动补发或追发。草稿需有真实客户业务研究、贝强工厂介绍及相关多款产品；具体标准见[外发素材SOP](../../04_客户开发/03_邮件与多渠道模板/潜在客户多渠道开发与外发素材SOP_2026-08-26.md)。邮箱权限不是信件审核；Agent只准备草稿，实际发送由负责人操作。
- **询盘处理**以独立站询盘和往来为当前接入重点；历史复盘与已结束对象分开，订单买家另列。按负责人2026-11-01要求，暂停国际站询盘及聊天接入，不再以手工粘贴作为工作流；既有记录继续可查。既有RFQ暂停状态不变。
- **推进状态**为待处理、准备回复、等客户、内部评估、报价沟通、样品推进，以及成交/停止/归档；按当前阶段提供下一状态，已结束可以重开。网站站内或已连接 Gmail 的客户有新回复时，当前队列分别提示；连接后客户及候选买家的新邮件自动交给 Agent 准备中文分析与中英回复草稿，已标记等待的客户从等待时点起计算，人工决定是否发送。没有客户时限就不填。状态和下一动作保存在客户原分析文件，邮件原件仍以 Gmail 为准。2026-11-02一封真实来信已识别并出现在首页；原自动整理曾因找不到 Codex 而失败，修复执行路径后手动接续并生成了草稿。后续新邮件的自动执行仍需继续观察；任务失败会在首页提示接续。
- **Gmail连接与自动处理**：在客户详情的“Gmail邮件往来”优先使用 Google 账号授权，只请求 `gmail.readonly` 权限。首次需在自己的 Google Cloud 项目启用 Gmail API、配置 Google 身份验证平台、创建“桌面应用”OAuth 客户端并选择下载的 JSON，之后在 Google 授权；页面内提供步骤和入口。授权及客户端资料由 Windows 凭据管理器保存，账号地址和连接时间保存在本机 `.local/gmail.json`，邮箱原文留 Gmail。负责人已确认当前 Google 项目为“测试”状态，授权自每次同意起 7 天后到期；工作台显示预计时间，到期可直接重新授权，不必重新选择客户端文件。负责人要求暂时保持测试状态。本机账号创建应用专用密码时提示不可用，原因未确定；该方式留作备选。工作台运行期间按客户邮箱匹配并定期读取；关机或工作台未启动时不运行。邮件可标记处理，后续新邮件再提醒；读取失败显示真实连接状态。新电脑首次运行本功能时，在工作台目录执行 `python -m pip install -r requirements-gmail.txt` 安装依赖。2026-11-02已实际读到客户新回复、在首页提醒，并在修复执行路径后接续生成草稿。
- **消息时效与审核发送**：Gmail 在工作台进程运行时约每 2 分钟轮询，可在客户详情手动更新；网站询盘在页面使用时约每 2 分钟刷新。两者不是实时推送，本机关闭后停止检查，但邮箱和独立站仍能收消息。Gmail 草稿保存在工作台本地；客户页面可编辑英文正文和中文对照、上传文件或选取资料包附件，审核收件人、主题、正文和实际附件后由负责人点击发送。中文对照不发送。发送成功记入客户并立即回读；客户后来回复继续同步和提醒。沿原邮件线程回复时使用来信的 Reply-To，修改主题则作为新邮件。Google 接受发送不等于客户已读或进箱。
- **Gmail发送授权**：发送权限与原有只读授权分开，Google离线授权保存在Windows凭据管理器；工作台使用 [Gmail API](https://developers.google.com/workspace/gmail/api/guides/threads) 处理线程和发送。Agent不会自动发送或追发。若发送结果不明确，先核对 Gmail 已发送邮件，系统不自动重发；只有负责人确认未发送后才能恢复草稿。Google项目仍是负责人之前选择的测试状态，该状态下Gmail刷新授权有7天期限；到期可在邮件草稿的“Gmail 发信授权”中重新授权同一账号，长期使用需要按Google正式项目及适用验证要求处理。
- **Gmail邮件筛选**：既有客户按联系邮箱匹配；同一邮件线程的其他发件人还需与客户同一企业域名或明确回复对应发出邮件，避免把同主题群发中的不同客户合并。推广邮件不进入客户往来，休假及工单等自动回复单独标注、不触发客户回复草稿。对于未登记发件人，客户开发页筛选近 90 天最多最近 30 封含鞋类关键词的收件箱邮件，展示有采购意向的候选；用户可查看 Gmail 原文、加入客户或忽略，历史来信与新来信分开。此筛选依赖邮件内容和关键词，不代表已覆盖所有潜在询盘；原邮件始终留在 Gmail。
- **邮件中文阅读**：客户邮件默认显示主题和正文的中文译文；原文通过每封邮件的 Gmail 链接查看。工作台运行时自动翻译已识别的新客户回复，打开客户详情时补译其既有收发邮件；复用本机 Codex，译文保存在本地数据库以便再次查看，Gmail 仍是原邮件来源。翻译进行中会显示进度，失败可在页面重试。
- **秘书式简报**先显示核心意图、我们如何承接、此刻最多三个问题及建议回复，再看原文中文对照和联系方式。Agent读取现有公司能力资料，复用已确认工厂身份和合作条件；判断正文与表单冲突，结合当前对象的负责人说明选择采用信息，不逐字段机械求核。原件保留，处理说明和分析单独保存；具体开发性能仍按项目评估，不能以已知工厂身份代替所有技术承诺。
- **网站往来与回复**：网站客户详情可查看私信原文；已有成果以“英文正文”或“英文回复草稿”独立章节保存时，可带入回复框再由用户检查、发送。网站保存与邮件提醒结果分别显示。模拟接口测试已通过，尚未对真实客户发送实测。国际站询盘和聊天接入暂停。
- 2026-11-01核查：负责人查看当前应用权限列表，未看到询盘或买家消息接口。阿里[国际站消息接入文档](https://open.fliggy.com/docs/doc.htm?articleId=118890&docType=1&treeId=456)示例是订单变更通知，不是询盘或聊天。当前暂停国际站询盘和聊天接入。
- **客服知识与往来**：询盘Agent可读取当前网站客户完整往来并区分新需求及已答事项；逐条中文译文按消息关联保存，详情自动刷新；
- **客服知识**沿用产品矩阵、公司资料、客户SOP与逐款原档，询盘Agent通过业务工具读取，不再建立第二份事实库；现在是原资料读取与草稿能力，尚非完整自动客服。
- 页面不显示整包JSON。旧草稿和处理记录折叠保留；分析建议可转为关联研究任务。英文外发草稿要求完整中文对照，中文摘要不能代替逐段翻译。
- 网站记录来自原站后端，未标测试不证明访客身份或自然获客。当前记录登记页为`/sourcing-review/`，时间为2026年10月28日22:48（北京时间），来源网址及推广参数为空。具体来源核验与证据在该客户私有分析中，公开入口不复制客户原文。

### 渠道与创作

- **渠道**显示独立站询盘读取状态及国际站带统计期的历史指标；商品详情可读取国际站指定链接正式标题并准备修改草稿。BQ009一条标题草稿因忽略2026-10-31已确认的定位被负责人否决并撤回，未提交；应以[最新商品档案](../../02_Alibaba运营/02_单品优化记录/商品档案/BQ009/README.md)为准。抖店工作台接入暂缓，不影响已有经营工具。
- **创作**沿原内容入口索引项目及关联素材；本地画布可编辑镜头及素材关系。LibTV区域通过官方CLI读取根目录画布、查看节点、创建画布和新增文字节点；现有节点编辑、素材生成及发布尚未接入。创建动作在用户点击后执行，不自动生成媒体或扣费。

## 验收与实际边界

- 已实际运行商品资料任务、网站询盘回复草稿任务，核对业务工具的原件读取记录、成果文件及对象归属。
- 第二包实际跑通网站原文→完整中文翻译与分析、候选官网→中文研究成果，以及页面创建关联研究任务→读回原询盘→中英改进稿。商品既有选款稿补齐中文对照；询盘已结合负责人解释排除必填数量对订单判断的影响，重写中英合作回复，不再追问已解释的表单数字。
- 询盘分流改造曾通过134项Python回归（含1项Windows链接测试跳过）、19项前端回归；本轮全量结果见下方验证命令及当前验收。本轮覆盖状态推进与重开、历史隔离、显式时限排序、经营状态与分析互不覆盖、负责人说明传递，以及真实模型读取公司能力后重做简报。平台询盘消息与外发尚不在已验收范围。
- 已于2026-11-01读取BQ009目标链接标题，但生成草稿误用旧判断、忽略较新的负责人决定，已撤回且未提交。重新处理应先查该款最新档案及对应平台现状。先前全量Python 172项通过（1项跳过），前端与妙手测试25项、画布模型2项通过。
- 已在真实页面审阅修改商品成果，保存、刷新并回读；询盘下一动作也已通过页面保存并回读。发现旧尺码计划与最新正式档案冲突后已纠正该草稿。工具默认优先当前档案，历史证据按需搜索；AI成果仍需要内容审阅。
- 已验证HTTP与文件回写、失败/取消/重启中断、网站测试记录排除，以及前端异步导航、保存和编辑不被轮询覆盖。早期未读到依据的草稿保留并标为待补依据，不算成功交付。
- 普通Agent现可在授权范围内执行项目工作；网站私信和 Gmail 按现行审核规则由负责人操作。Gmail真实账号授权与客户来信读取已验证，发信链路以模拟邮箱测试，不向客户发送测试邮件；实际发送以Gmail回执为准。渠道修改、完整创作工作区、报价订单与自动经营反馈仍须按具体能力验收。
- 资料随商品、客户等对象呈现，不单独建立重复入口；搜索不是全电脑文件搜索。既有桌面聊天不会自动全部出现在本地任务列表。

## 唯一来源与运行

产品JSON、供应来源、媒体原件、CRM和项目文档仍在原处。网站询盘通过原后端只读接口访问，仅内存缓存，未再落一套询盘快照。成果正文位于原业务的私有`.local/成果/`或`.local/网站询盘/`，SQLite只存索引、任务和关联；编辑直接更新同一份成果。

客户中文译文和分析写入`04_客户开发/.local/`，带原件标识；原文变化会标示需要重核。人工录入原件单独保留并按渠道及内容去重。候选池保持原位只读，研究任务及补充信息位于`04_客户开发/02_目标名单/.local/工作台研究/`。国际站接口回读及订单投影缓存在私有目录，不能提交公开仓库。

本地服务在127.0.0.1:8766，状态库为`.local/runs.sqlite3`。Gmail Google OAuth 客户端资料与授权令牌保存在系统凭据管理器，应用专用密码方式留作备选；普通任务继承用户环境和可用工具权限，不能将其视为与本机凭证完全隔离。Codex子进程使用当前已有系统代理，不修改全局网络配置。新加坡网站后端及原VPS代理继续运行；本机关机时本地任务停止，官网继续收询盘。当前无需新增付费服务。

## Agent接续与代码入口

桌面Agent可通过`python -X utf8 desk_cli.py objects list --kind product --query BQ008`查询同一业务对象，`objects get product:BQ008`取详情；`artifacts list --object-id product:BQ008`取成果，`artifacts save product:BQ008 --title 标题 --content-file 文件`保存。命令在本目录运行；正文留业务目录，不能另建一份客户事实库。

桌面Agent可用 `desk_cli.py materials list <客户ID>` 找到客户专属及通用资料，用 `materials read <客户ID> <资料ID>` 读取 PDF 或文本（PDF 读取依赖 `pypdf`，每次最多前30页；图片返回原位置）；客户任务中的 Sol 可以使用 `list_customer_materials`、`read_customer_material` 读取同一资料包，不复制原件。

客户任务可调用 `get_customer_gmail` 只读该客户已连接的邮箱往来；未连接或读取失败时返回实际状态。授权令牌、客户端密钥及应用专用密码不写入业务对象、模型提示、项目文件或Git。

| 文件 | 职责 |
| --- | --- |
| `business.py` | 产品/客户源读取、对象关联和成果保存 |
| `today.py`、`product_gaps.py` | 首页按实际状态汇总待办；检查商品已登记的图片和链接 |
| `website_inquiries.py` | 原网站询盘、私信和读取状态 |
| `customer_workspace.py`、`customer_analysis.py` | 客户原文与中文分析、研究任务、候选补充及结构化模型回写 |
| `creation.py`、`channel_overview.py`、`douyin_overview.mjs` | 创作原项目、渠道概览及抖店只读商品入口 |
| `customer_workflow.py` | 当前/历史/结束分流、阶段推进、明确优先级和实际时限排序 |
| `inquiry_intake.py`、`connectors/alibaba/customer_source.py` | 历史记录归档与国际站订单买家读取；不作为当前询盘接入方式 |
| `prospect_research.py` | 复用客户发现助手，实际读取绑定候选公司的公开官网 |
| `company_lookup.py` | 从公开搜索查找公司官网候选；选择后回原客户，研究沿用 `prospect_research.py` |
| `resource_library.py`、`web/library.js` | 对客资料的原文件引用、客户关联与管理 |
| `gmail_oauth.py`、`gmail_mailbox.py`、`gmail_sync.py`、`gmail_translation.py`、`gmail_drafts.py` | Gmail 授权、往来读取、中文翻译、客户邮件草稿、人工审核发送及后台同步 |
| `agent_jobs.py` | 对象任务、会话接续、同对象并发保护、取消和成果保存 |
| `desk_mcp.py` | 现有业务对象和关联资料读取、客户商机记录；自动邮件/翻译模式只读 |
| `desk_cli.py` | 桌面Agent与页面复用同一业务访问、成果和画布实现 |
| `server.py` | 本地HTTP、共用对象/任务/成果接口；旧运行接口保留历史兼容 |
| `web/index.html`、`desk.js`、`desk.css` | 新默认界面；旧app/workspace文件不再加载 |
| `media_assets.py`、`connectors/`、`product_changes.py` | 复用媒体预览及已有平台能力，后续接入对象内流程 |
| `cloud-runner/` | 既有云端执行代码，当前不启用 |

验证：本目录运行`python -X utf8 -m unittest discover -p 'tests*.py'`及`node --test tests_desk_frontend.mjs tests_library_frontend.mjs`。真实任务日志、读取依据与成果索引在被忽略的`.local/`，不进入公开Git。新会话先看PRODUCT确定下一包，再看本页确认实际能力。

画布依赖与构建：在 `creation-canvas/` 执行 `npm ci` 和 `npm run build`；依赖和构建产物留本机，源码与锁定版本随项目同步。运行时不连接npm。画布是本地布局，不会自动同步到LibTV；LibTV入口读取官方画布，两个视图分别表示各自数据。

桌面Agent在本目录执行 `python -X utf8 desk_cli.py canvas get <项目ID>` 读取画布；保存使用 `canvas save <项目ID> --content-file <JSON>`，先取当前version。内部普通任务可用 `get_creation_canvas` 和 `save_creation_canvas` 读写同一画布，自动邮件整理等只读模式不能写入。
