# 云端执行接入与备用CLI执行器

2026-10-30：原生Sol Cloud经标准客户端完成正式网站指定任务回传，实际配对已验收；自托管CLI执行器仍为备用，未部署或购买资源。配套云接口由网站工作台后端维护，本目录不保存第二份任务状态或业务资料。

## 当前首选：OpenAI托管Codex Cloud

2026-10-30负责人指出应复用OpenAI提供的云环境，故撤销“必须先提供Linux云主机”的判断。官方支持在网页/桌面创建并发布环境，从手机接续；任务可在本机休眠后运行。[官方云环境文档](https://learn.chatgpt.com/docs/environments/cloud-environments)。不需要先购买服务器，也不需要在托管任务里再嵌套一层Codex CLI登录。

2026-10-30已完成：负责人授权并安装官方ChatGPT Codex Connector，已回读确认仅选择`421345308/beiqiang-cross-border-operations`与`421345308/beiqiang-footwear-site`。基于两个仓库main创建的**贝强经营工作台**环境已发布，环境列表显示私有，配置为Only me。初始化使用GPT-6.1 Sol，运行于OpenAI托管环境，无需购置主机。

云端实测：网站构建、396项测试和lint通过，英文首页、目录与中文首页请求正常；经营工作台11项后端测试及6项备用执行器离线测试通过，实际读取7张任务。Node 24.19、Python 3.12；两个仓库无源码或锁文件改动。已保存安装脚本与启动说明；仅在被忽略位置补齐测试PDF副本和本地Node兼容配置。发布完成后UI确认已加载最新发布版本的草稿；尚未另起独立业务任务验证恢复。发布与授权截图、回读保存在`99_临时区/工作台应用验收/`，不进公开Git。

当前使用：在官方ChatGPT/Codex的“设置 → Codex云端”找到已发布环境。官网手动Cloud模式允许复制含指定run_id的执行指令。负责人已保存专用网络密钥，2026-10-30已发布包含该密钥的Only me环境；实际运行结果见下方验收，不再等待负责人重复填写。

2026-10-30复查：官方环境列表与编辑配置已恢复，两个已授权仓库、安装脚本和启动技能均可见。负责人完成网络密钥保存后，发布UI确认已加载最新发布版本草稿。当前配置及原生Sol验证会话为`01a18bc8-b6c4-7241-bd42-4104547c4025`；本轮未扩大仓库或使用者权限。

从官方Cloud启动Sol有界任务，使用本目录`cloud-task.py`领取指定任务并回报进展、续租和结果；不在托管任务中嵌套Codex CLI或另调用API模型。网络密钥名称为`WORKBENCH_RUNNER_SECRET`，作用域仅当前Only me环境，允许域名仅`www.beiqiang.online`。值留本机被忽略的`.local/cloud-pairing-secret.txt`，不进Git或聊天；按照电脑操作工具的凭证规则，由负责人在官方表单完成填写和保存。保存后发布环境，再以新Cloud任务验证恢复和实际回传。

```text
python3 cloud-task.py claim --run-id <指定ID>
python3 cloud-task.py event --run-id <指定ID> --message "实际进展"
python3 cloud-task.py heartbeat --run-id <指定ID>
python3 cloud-task.py complete --run-id <指定ID> --result <私有JSON文件>
python3 cloud-task.py status --run-id <指定ID>
```

失败时用`fail --run-id <指定ID> --message "实际原因"`。结果文件在Linux使用0600权限；客户端私有状态保存在被忽略的`.local/cloud-task/`，不输出密钥或租约。保留官方代理及证书配置，网络密钥可为官方代理占位值，不要求原始密钥出现在进程中。手动模式必须指定任务，不抢其他排队任务；已领取任务按真实租约展示，不显示常驻在线。网站仍为snapshot_review，结果只进入待审，源文件采纳尚未接通。

验收：网站399项测试、类型检查、构建和lint通过（9项既有图片提示）；客户端及备用执行器合计25项Linux测试通过。正式域名与部署预览版本、视频及字幕一致。本机对正式网站完成指定领取、进度、续租、结果回传，私有回读为awaiting_review；首次紧接完成的事件列表未满足回读断言，随后只读复核确认原进度事件和结果均已保存，没有重新执行任务。证据为`99_临时区/工作台应用验收/manual-cloud-protocol-readback.json`。此项是本机协议验收，model=protocol-test、无源文件修改；当时尚未验证实际OpenAI Cloud到官网执行，后续实际验收见下节。私有队列另留一张连接验收任务，不改原七项经营任务。

当前客户端的实验性`codex cloud`选择器尚未显示该新版环境，未提交CLI云任务；这不是永久能力判断。面向个人套餐、供自建网站直接创建新版Cloud任务的公开REST接口尚未核实。网站自行唤醒、持续守护及源文件采纳均未实现。正式Agents API需要独立Platform身份与计费，不与个人套餐Cloud混用。[Agents API快速入门](https://developers.openai.com/api/docs/guides/agents-api/quickstart)。

### 原生Sol实际回传验收（2026-10-30）

负责人保存网络密钥后，已发布配置并从同一官方配置会话运行原生GPT-6.1 Sol。首次验收运行`7e9a0f5c15d3b8280ba6262edc967e80`完成领取和两条进度上报，但临时传输进程JSON解析错误后退出，内存租约未保存；统筹核实后取消该运行，保留原进度与错误，不补造完成。

随后明确使用已提交`cloud-task.py`创建新验收运行`55ebc551e7f6fb9a45377f4a5cfda059`，完成指定领取、持久保存租约、实际进度、续租及中文结果提交。官网私有存储独立回读确认`awaiting_review`、model=`gpt-6.1-sol`、真实会话标识、中文能力审查、`changes=[]`和下一步均已保存，无error。证据：`99_临时区/工作台应用验收/native-cloud-client-readback.json`；原失败记录保留在私有运行历史。

本次仅验证官方配置会话中的原生模型到官网完整回传，不是独立新会话恢复、常驻执行、自动唤醒、平台发布、客户外发或源文件采纳。后续人工启动必须沿标准客户端保存运行状态，不能临时改用仅内存持有租约的传输程序。任务结论经统筹审阅用于明确三类业务依赖，未启动该提案中的业务执行包。

网站私有后台、任务队列与资料快照继续复用；本目录`runner.py`是自托管备选，不是OpenAI托管环境的必装程序。只有托管路线实际不满足需求且负责人选定替代方案时，再考虑下述部署。

## 云端提案经本地审阅回写

官网“导出提案，交项目对话审阅回写”导出v1 JSON，保留服务器的`source/source_hash/source_version`、运行编号和实际修改，不包含执行凭证或完整私有日志。没有来源或没有修改项的结果仅供阅读；旧导出包缺少原文依据时不能直接应用。

在经营仓库根目录，由原业务主办或统筹读取完整提案并核事实，再预览具体差异：

```text
python -X utf8 "08_工具链/08_经营工作台/cloud-runner/review-proposal.py" "提案文件.json"
python -X utf8 "08_工具链/08_经营工作台/cloud-runner/review-proposal.py" "提案文件.json" --apply
```

默认只预览；`--apply`仅在实际审阅通过后执行。工具以当前本地原文字节计算规范化SHA256，须与提案原文一致，再整体核验唯一片段、同一文件及现有四份白名单后精确写入，保留未修改内容和换行。来源版本作为追溯字段，离线工具不声称查询了最新云版本。文件已被其他对话修改时停止应用，沿新原文形成新提案；不能改hash让旧提案强行通过。

最小应用回执位于`.local/proposal-review/<run_id>.json`，不进Git。该目录的互斥只协调本工具，其他对话仍遵守单文件单主办；写前重新核原字节，不宣称对任意外部编辑器提供跨进程事务。原文已写但回执保存失败会明确报出，先检查原文，不盲目重复应用。

回写后运行`prepare-import.py`生成当前本地资料包，在官网选择该文件。页面会一次读取已登录管理员可见的快照/任务版本，展示新增或更新，确认后提交；已有显式版本不匹配会报冲突，提交前云版本变化也会停止，不自动重读重试。无需手填版本号，导入仍限原四份文档和任务。

刷新快照后点“确认已在项目回写”。服务端将原历史快照应用提案，并与新导入快照逐项核对；一致才记录`accepted / review_origin=local`及原/新hash和版本。此操作是管理员确认及快照比对，不直接读取或修改本地磁盘，也不等于后台自动同步。确认完成后再继续其他独立修改；若新快照含额外改动，先查差异，不伪造匹配回执。

该路径不自动提交Git、外发邮件或改平台。项目接手者从原业务文件、提交记录和私有应用回执接续，官网运行记录用于定位原提案。

2026-10-30真实验收：原生Sol运行`78a2d80b3dfe1caa0dd3c2aa007b714e`以《当前状态》云快照版本9生成一个具体新增段落，统筹核对经营方向后，用上述工具预览并回写本地原文。刷新为版本10后，经既有部署管理员身份调用同一服务端确认函数，独立回读为`accepted / review_origin=local`，原/新hash与本地回执一致；只增加经营验收方向，没有伪造客户或订单结果。随后本页任务摘要等独立更新另行同步，不改写原提案回执。证据为`99_临时区/工作台应用验收/source-review-cloud-readback.json`、`source-writeback-accepted-readback.json`及受忽略的`.local/proposal-review/`；本地工具13项测试在Ubuntu全部通过。

## 已有网站与备用部署条件

- 已有正式网站：EdgeOne Makers `beiqiang-footwear` / `makers-zsvtdpeh3qf1`，静态前端、Cloud Functions与Blob；源码独立仓库 `03_独立站/03_网站源码/`。目前没有可核的本项目常驻CPU云主机或已部署Agent执行器证据；本机没有可直接用于盘点CVM的 `tccli`，不能据此断言云账号没有实例。
- 本机已安装EdgeOne CLI：`08_工具链/03_网站发布运行时/edgeone-cli-runtime/node_modules/.bin/edgeone.cmd`，已只读验证 `--help` / `makers --help`。网站 `.edgeone/project.json`确认上面的项目身份；本轮使用既有部署身份配置网站队列并验收私有存储，凭证只在进程内使用。
- GitHub型项目继续由main推送触发部署，不用上传型项目绕过现有发布。部署适配器 `edgeone-deploy/export-static.mjs`、静态构建 `scripts/export-edgeone-static.mjs`；正式发布核验 `npm run verify:deployments`（`scripts/verify-deployment-parity.mjs`）。配置以网站README的Production Deployment段为准：root `edgeone-deploy`、install `npm ci --prefix ..`、build `npm run build`、output `dist`。
- 官方现提供同项目 `agents/` 运行时：单次默认5分钟、可设60分钟，空闲5分钟回收，会话最长6小时。它不是永久后台进程；需要持久任务和真实触发。普通Cloud Functions单次默认30秒、最大120秒，不宜承载不确定时长的CLI任务。[Agents文档](https://pages.edgeone.ai/document/agents)、[Cloud Functions限制](https://pages.edgeone.ai/document/cloud-functions)。本账号是否可用、部署根与Agents打包是否匹配，仍须实际预览验收。

备用路线是可信CPU云主机运行Codex CLI，通过正常device-auth登录现有ChatGPT套餐承接网站私有队列。此处`runner.py`仅服务该路线；不是已配置的OpenAI Cloud或EdgeOne Agent。EdgeOne Agent加官方API也是备选，不默认切到API付费。

## 备用Runner的身份与费用条件

网站本人登录、机器队列身份、模型调用身份是三件事。Runner需要：

1. 已部署的HTTPS队列端点和独立 `WORKBENCH_RUNNER_SECRET`，由部署环境注入，不在网页中提供机器密钥。
2. 一处能运行Python 3.10+和Codex CLI的执行环境。无已确认现有实例，因此目前无主机报价，不自行购买或启动GPU实例。
3. 在该执行环境、同一个非root用户下运行 `codex login --device-auth`，由负责人在自己的浏览器完成ChatGPT授权，然后运行 `codex login status`确认使用ChatGPT登录。若安全设置尚未允许设备登录，按官方设置启用。本路线使用现有套餐的Codex额度与限制，不自动切换API、不承诺无限或零额外费用。**不复制本机ChatGPT auth文件去云**。[官方鉴权文档](https://learn.chatgpt.com/docs/auth)。

本目录未验证云主机登录后的套餐余量或Sol实际访问。API Key只作为负责人明确选择后的可选身份，按API计费。符合条件的ChatGPT订阅者确有API赠金，但官方明确排除Codex API-key usage，不能把赠金当成这条执行路线的额度。[官方赠金范围](https://developers.openai.com/api/docs/guides/chatgpt-api-credits)。

## Runner使用

在选定执行主机完成Codex安装和正常登录后，在部署环境设置 `WORKBENCH_RUNNER_URL=https://<正式主机>/api/workbench-runner` 和 `WORKBENCH_RUNNER_SECRET`。不要把实际密钥放进命令历史、Git或README。

服务与手动device-auth必须使用同一Linux用户、HOME，以及同一个`CODEX_HOME`（若设置）。Runner保留正常登录身份；`--ignore-user-config`仅隔离用户配置，不绕过规则或跳过认证。开始前确认该用户没有意外的`OPENAI_API_KEY`、自定义API base URL或API-key登录；若发现，先由负责人正常切回ChatGPT登录，不让runner自动改认证。

```text
python runner.py --once
python runner.py
```

`--once`只领取一次；无参数每10秒检查一次。只要主进程运行就继续；不会自行安装系统服务、创建任务计划或配置开机启动。`WORKBENCH_RUNNER_STATE`可指定私有运行目录，默认复用上级被忽略的`.local/cloud-runner`。部署环境需保留适当权限并为CLI会话记录配置自己的私有保留策略。

采用网站后端约定的 `POST /api/workbench-runner`，Bearer机器密钥；action为 `heartbeat/claim/event/complete/fail`。claim返回 `job`（空则无任务），包含id、source、instruction、lease_token、lease_expires_at、document `{path,content,hash,version}`。任务文档是明确导入云端的快照，不根据source读本地路径。全局heartbeat记录在线，执行时每30秒带run_id和lease_token续10分钟租约；服务端拒绝续租即停止本次CLI。任务过期后端应标interrupted，不能自动重领重跑。

只将选中文本通过stdin送入独立临时目录中的只读CLI，禁用连接器、插件、shell、浏览器和图片生成等能力；不执行队列下发的命令。机器密钥不进入子进程环境。CLI生成的事件回传为私有日志，结构化提案须满足快照hash、单文件和精确唯一片段校验。最终只提交待审提案；网站后端当前为snapshot_review，尚不允许采纳原文改动，后续须接通原业务源同步再开放回写。

网络/租约/执行或上报失败会停止runner，不自动重新执行，也不把发送成功当作业务操作完成。重启应先核云端原记录状态。当前无CLI resume请求入口；session_id只作真实执行追溯，不承诺跨主机恢复。

## Linux用户服务模板（仅准备）

`beiqiang-workbench-runner.service.example`是最小systemd用户服务模板，未安装或启动。需先替换执行器目录、Python绝对路径与Codex所在bin目录，再放入该Linux用户的`~/.config/systemd/user/`。环境文件占位为`~/.config/beiqiang-workbench/runner.env`，仅由该用户可读，使用systemd的`KEY=value`格式设置队列URL、独立机器密钥及私有state路径；这里不提供实际秘密。不要将本机Windows路径复制为Linux执行路径。

服务继承该用户正常Codex登录，默认不注入API Key。模板`Restart=no`，失败保留真实中断状态，需核原运行后手动恢复；停止时systemd终止本服务cgroup中的子进程。模板未配置开机启动或linger。未来实际启用时须核用户服务是否在退出SSH后持续运行；需要长期运行时由已授权部署步骤明确配置，不把模板存在当成持续运行证据。日志进入该用户的journal，按私有运行日志管理。

## 验证范围

Windows与WSL Ubuntu 22.04均通过6项离线测试及帮助入口：Linux独立进程会话参数、保留规则/只读CLI参数、快照hash冲突、跨文件拒绝、无source任务限制、HTTPS凭证URL拒绝和服务不自动重试。可在本目录运行 `python3 -m unittest -v test_runner.py`。这些测试未发送队列请求、未启动真实模型、未安装systemd服务；Linux语法和契约通过不等于云端登录、端到端或部署验收。电脑关闭后能否继续执行取决于此程序是否实际运行在独立云环境；本机WSL运行不满足该目标。

## 准备首次私有资料导入

在贝强工作区根目录运行：

```powershell
python -X utf8 '08_工具链/08_经营工作台/cloud-runner/prepare-import.py'
```

输出为 `08_工具链/08_经营工作台/.local/cloud-import.json`（已被上级`.gitignore`忽略），仅包含 `documents/tasks/goals`，由登录后的界面确认时加入 `action: import` 后提交。文件是**私有资料快照**，不放入公开网站资产或Git；本地原业务文档仍然权威，导出与导入均不代表源同步接通。

脚本复用现有server读取及任务生成器，严格只读后端明确白名单的四份文档和原七张任务卡，不展开引用、不读取本地执行日志、CRM附件或凭证。移除本地16位任务id及无需导入的evidence，由云端按source/title生成32位id。当前导出75,526字节，低于UI的340,000字节与后端350,000字节限制；超限会拒绝，不截断业务原文。命令只显示数量、字节数和输出路径，不打印正文。

此包不携带版本。官网选择文件时会读取一次当前版本并准备导入预览，再由确认按钮提交；直接调用后端则仍须显式提供核实后的expected_version，不能把无版本包当作覆盖更新。白名单或七项任务范围变化时脚本要求先复核范围。
