# 私有 Sol 后台执行器部署包

> 2026-10-31当前决策：负责人否决默认付费托管组合，优先验证现有机器上的开源自建。本页保留此前已验证的Docker包和Render可选步骤，不代表已选用Render，也不构成开户或购买要求。最新取舍见[架构方案](../../PRODUCT.md#运行条件与已核边界)。


准备于2026-10-30。复用上级 `runner.py` 的单实例循环，没有增加第二个派发器、监督器、队列或模型API。此目录只是可审阅部署包；未开通Render、未付费、未在Render登录或实际运行模型。启动预检通过也不证明套餐剩余、模型可用或真实任务完成。

## 选定的运行方式与价格

Render **Background Worker，Singapore，单实例，1GB Persistent Disk**。后台worker持续运行且无公开入站端口，支持Dashboard Shell及SSH；硬盘只给同一服务单实例使用，部署会短暂停旧实例，不能横向扩容、不能在build/pre-deploy/one-off job读取该盘。不使用Cron job，它不能挂此持久盘。[后台worker](https://render.com/docs/background-workers)、[地域](https://render.com/docs/regions)、[硬盘限制](https://render.com/docs/disks)、[Shell支持](https://render.com/docs/ssh)

官方当前最低worker为 `0.5c-512mb`：计算约US$7/月，1GB盘US$0.25/月，合计约 **US$7.25/月**。512MB是否满足本项目须按真实Sol任务测量；若发生OOM再由负责人决定 `1c-2g`，计算约US$25/月，连1GB盘约US$25.25/月。另计税、超额出口及任何选择的附加服务，不自动升配，也不把免费web plan当免费后台worker。[价格](https://render.com/pricing)、[当前plan ID](https://render.com/docs/compute-plans)

2026-10-30通过官方npm包注册表实查 `@openai/codex@0.166.0` 可取得，默认固定该稳定版本；本机 `0.166.0-alpha.5.1` 也可取得，但没有据此自动替换。Docker build参数 `CODEX_VERSION` 可由负责人明确指定其他准确版本；重新构建后 `WORKBENCH_CODEX_VERSION` 与实际CLI版本须一致。禁止 `latest`，禁止启动时自动升级。实际模型固定为现有runner中的 `gpt-6.1-sol`。

## 部署前集中决定

仅将来明确重选Render时，才核实当时费用并办理账户/付款资料。当前没有本项目Render账号资源的可核证据，不能声称已有免费额度。不要把服务器费与现有ChatGPT套餐额度混为一笔。

这是一台无公开入口的可信私有worker，不是在公开GitHub仓库启用带账号凭证的CI。代码可从现有main或审核后的镜像取得；保持自动部署关闭，禁止PR预览、公共触发器或第三方任意代码进入运行环境。不要把 `auth.json` 放进源码、镜像、build args、Render环境变量、GitHub Actions或日志。官方支持保存CLI认证并用于可信私有自动化；公开仓库CI不适用其账号认证维护方案。[非交互认证](https://learn.chatgpt.com/docs/non-interactive-mode)、[私有认证维护边界](https://learn.chatgpt.com/docs/auth/ci-cd-auth)

## 首次部署和普通登录

1. 在Render从当前根仓库main创建Docker Background Worker。可选择本目录 `render.yaml` 作为Blueprint路径；配置的Docker build context仅为 `08_工具链/08_经营工作台/cloud-runner`，只复制 `runner.py`、`preflight.py`、entrypoint，不复制业务原件或凭证。`autoDeployTrigger` 为 `off`；仅人工审阅后部署，不随任意提交自动升级程序。[Blueprint字段](https://render.com/docs/blueprint-spec)
2. 建1GB盘挂 `/var/data`，保持 `RUNNER_ENABLED=false`。在Render私有设置填写当前机器用 `WORKBENCH_RUNNER_SECRET`，它不能出现在文档或命令行。地址必须精确为 `https://www.beiqiang.online/api/workbench-runner`。首次启动只初始化固定两目录并以非root用户 `node` 空闲等待，无heartbeat、claim或模型调用。
3. 打开该worker的Dashboard Shell。容器入口短暂以root初始化 `/var/data/codex`、`/var/data/runner` 的目录归属和0700权限，拒绝符号链接、非目录及非挂载盘；不递归chown，不改已有认证文件。随后执行进程降为 `node`。Shell可能以镜像声明的root进入，**所有Codex操作使用下列同一用户**：

```sh
gosu node codex login --device-auth
gosu node codex login status
```

由负责人在自己的浏览器完成该次正常ChatGPT授权；不要复制本机auth文件。CLI和runner共享 `CODEX_HOME=/var/data/codex`，认证只保存在私有盘；自动续期由官方CLI完成，不自写刷新协议。若设备登录被账户设置禁用，负责人只需按官方登录提示启用或正常完成另一登录方式。后台任务不自动切API计费。[官方登录与缓存](https://learn.chatgpt.com/docs/auth)

Render Docker Shell要求运行用户有Shell、正确 `.ssh` 权限、root账号如被指定须可解锁；镜像按官方说明准备。盘不挂用户HOME，避免Render SSH不支持该布局。没有运行自建SSH服务器或开放端口22。[Docker Shell要求](https://render.com/docs/ssh#docker-specific-configuration)

4. 在同一Shell以node运行预检：

```sh
gosu node python3 /opt/worker/preflight.py
```

结果只有布尔、固定错误码、CLI版本和时间，无认证原文、真实文件路径或密钥。只有所有检查通过才把Render的 `RUNNER_ENABLED` 设为 `true` 并重新启动同一服务。不要新建第二实例。后端必须已允许该机器以 `self_hosted` 模式领取；worker登录成功本身不改变服务器模式或业务授权。

## 启动检查与主程序接口

`preflight.py` 默认只运行 `codex --version` 和强制ChatGPT方式的 `codex login status`，不调用模型、队列或平台。检查精确正式地址、机器密钥已配置、PATH中CLI存在且版本匹配、无API/provider覆盖、Linux非root运行、CODEX_HOME和STATE为持久挂载盘下独立私有可写目录。不会读取或打印auth.json。`eligible_to_start=true` 仅代表可开始；`model_access_verified`、队列连通及跨重启持久化验证始终不由这次预检伪造为true。

供现有runner集成：

```python
from preflight import preflight
startup = preflight()
if not startup['ok']:
    # 输出安全预检结果后退出；不得先发送ready心跳或领取任务。
    raise SystemExit(1)
capabilities = {'ready': True, 'auth': 'chatgpt', 'model': startup['model']}
# 沿原runner循环 heartbeat(capabilities=capabilities)，不新建派发层。
```

后端caps协议的ready含义为“通过启动检查”，不是“已完成真实模型任务”。CLI实际执行或认证失败后，以 `ready:false,auth:'unknown',model:'gpt-6.1-sol'` 报告需复核并停止，未知结果先回读，不自动重放。平台发布、客户外发及采纳仍按原业务规则。

Render会管理失败实例并可能重启进程，所以仅 `raise/exit` 不代表永久暂停。runner执行失败在私有STATE写 `blocked.json`，预检只看此标记是否存在、不读取内容；存在即拒绝启动，不因服务重启重新领取下一张业务任务。[实例生命周期](https://render.com/docs/troubleshooting-deploys)

恢复须先关闭 `RUNNER_ENABLED`，核服务器原run的状态及正式回执、实际登录和失败原因；未知提交结果先回读，不重放任务。修复依赖后，由负责人或其明确授权的操作者在同一私有Shell执行恢复操作：将 `/var/data/runner/blocked.json` 移到同目录一个未存在的私有归档名，或在已有失败记录可追溯的情况下明确清除该标记；不批量删STATE、认证文件或原任务证据。然后以node重跑预检，再开启worker。程序、部署脚本与自动重启都不会自动移走/清除标记。

导出函数：`preflight(env=None, expected_version=None, run_command=None, find_executable=None, require_non_root=True, require_mount=True)`（后六项为关键字参数）。生产保持host检查开启。单测注入假CLI/临时目录，不使用实际登录或模型；版本参数允许显式准确版本，默认锁0.166.0。若升级选择其他版本，先用同一任务验收再改配置。

## 必须实际验收的证据

- Shell正常登录后，预检为eligible；网站收到真实启动检查caps，禁用状态无假在线。
- 只选一张标识测试任务，真实Sol完成领取、续租、结果回传及原对象审阅；不能用固定假内容冒充模型结果。
- 关闭本机和浏览器后，同一worker能继续有界任务；重启后官方CLI认证仍可用，持久盘保存同一身份。不输出凭证证明。
- 终止/取消旧任务后旧租约不能提交；部署期间按原租约中断规则处理，失败不自动重放。带盘部署不承诺零停机。
- 预检只能确认CLI报告有ChatGPT登录，不单独证明服务器接受会话或指定模型可用；后两项以真实运行回执为准。

本包不采购资源、不创建账号、不发送消息、不改平台。停止领取先关闭服务器执行开关并核活动任务，再将worker `RUNNER_ENABLED=false`；停用环境变量仍保留盘及认证，不因停用自动删资料。认证失效由负责人在同一私有Shell正常续登。

`RUNNER_ENABLED=false` 只停止任务处理，容器仍在运行，不代表停止Render资源计费；停费与磁盘保留条件须按实际控制台账单另核。

## 本机已验收范围（2026-10-31）

Docker Engine 27.5.1真实构建成功，固定CLI回读为 `codex-cli 0.166.0`。首次BuildKit用时1511.046秒，主要等待官方镜像和npm原生包；最新源码命中缓存重建0.442秒（命令墙钟5.033秒）。最终镜像为 `sha256:82d5200208ea64fbdd07081bf7cd9b6179bf83991a24da27f6058f975cd3bc6d`，镜像内runner、preflight和entrypoint均已与当前源文件SHA256核对一致。entrypoint实际LF、无CRLF；Ubuntu13项预检测试与Shell语法检查通过，Render官方Blueprint JSON Schema校验通过。

全程 `--network none`、全新空卷的Docker smoke用时8.531秒：验证非root UID1000、两个0700私有目录及真实挂载盘、bootstrap无领取、固定CLI版本、无登录时预检拒ready、故障闸跨容器重启保存，以及启用后在首个队列请求前拒绝不合格启动。本次标识容器和卷已清理，其他镜像/卷保留；没有复制账号认证、调用模型/网站或创建云服务。详细无密钥证据在受忽略的 `99_临时区/工作台应用验收/worker-deploy-smoke.json`。这些结果证明本机部署包和失败保护可用，Render实际部署、本人正常登录、真实Sol与关机后执行仍未验收。
