# 云端执行接入与备用CLI执行器

2026-10-29：已准备可运行的 Python 标准库队列客户端，**未部署到云、未调用模型、未购买资源**。配套云接口由网站工作台后端维护，本目录不保存第二份任务状态或业务资料。

## 当前首选：OpenAI托管Codex Cloud

2026-10-30负责人指出应复用OpenAI提供的云环境，故撤销“必须先提供Linux云主机”的判断。官方支持在网页/桌面创建并发布环境，从手机接续；任务可在本机休眠后运行。[官方云环境文档](https://learn.chatgpt.com/docs/environments/cloud-environments)。不需要先购买服务器，也不需要在托管任务里再嵌套一层Codex CLI登录。

本账户实查：桌面“设置 → Codex云端 → 环境”显示暂无已保存环境；创建向导已识别GitHub连接，但显示“此连接没有可用的代码仓库”。进一步从向导“配置访问权限”进入官方ChatGPT Codex Connector安装授权页，已选择且仅选择`421345308/beiqiang-cross-border-operations`和`421345308/beiqiang-footwear-site`，未点击Install & Authorize。该连接器要求读取checks/commit statuses/metadata，读写actions/code/issues/pull requests/workflows，以及读取账号邮箱；已集中请求负责人确认新增访问。普通连接设置页加载失败，向导提供的GitHub官方安装页可用。环境计划Only me；尚未创建、发布或执行云任务。授权页面截图保存在本地`99_临时区/工作台应用验收/Codex云端仓库授权.png`，不进公开Git。

接入验收分两步：先验证发布环境能用Sol读项目、完成一项任务并取得结果，再验证官网工作台能否通过官方方式提交和回收任务。[CLI参考](https://learn.chatgpt.com/docs/cli/reference)提供实验性`codex cloud exec/list/status/diff`能力，本机已有相关命令且只读list成功；仍需核新托管环境兼容性。CLI功能存在不等于已有供网站直接调用的个人套餐REST接口，当前未证实这一接口。Legacy Cloud与新Cloud不可混同，不能把Legacy环境选择器为空解释为账户无云能力。

网站私有后台、任务队列与资料快照继续复用；本目录`runner.py`是自托管备选，不是OpenAI托管环境的必装程序。只有托管路线实际不满足需求且负责人选定替代方案时，再考虑下述部署。

## 已有网站与备用部署条件

- 已有正式网站：EdgeOne Makers `beiqiang-footwear` / `makers-zsvtdpeh3qf1`，静态前端、Cloud Functions与Blob；源码独立仓库 `03_独立站/03_网站源码/`。目前没有可核的本项目常驻CPU云主机或已部署Agent执行器证据；本机没有可直接用于盘点CVM的 `tccli`，不能据此断言云账号没有实例。
- 本机已安装EdgeOne CLI：`08_工具链/03_网站发布运行时/edgeone-cli-runtime/node_modules/.bin/edgeone.cmd`，已只读验证 `--help` / `makers --help`。网站 `.edgeone/project.json`确认上面的项目身份；未读取auth文件或`.env`。
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

此包用于首次导入，未携带expected_version即按云版本0处理。已有快照后再次导入需核真实云版本并显式准备对应expected_version；不可把首次包作为覆盖更新。白名单或七项任务范围变化时脚本要求先复核范围。
