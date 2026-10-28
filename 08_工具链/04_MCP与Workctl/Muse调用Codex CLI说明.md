# Muse 调用 Codex CLI 说明

核对日期：2026-10-28。适用对象：在本机运行、能够启动子进程的 Muse 或其他可信自动化程序。本页只维护调用技术；分工与会话索引见[Muse–Codex协作](Muse-Codex协作.md)，工作目标与接续方式以本地项目入口为准。

Codex 提供官方命令行工具 `codex`。Muse 可以通过 `codex exec` 提交任务，读取过程事件和最终答复，也可以保存会话 ID 后继续同一项工作。此方式会运行 Codex agent，能够按实际权限读取文件、修改代码、执行命令和使用已配置的工具。

新建 CLI 任务不会自动获得当前桌面聊天的全部上下文。Muse 应显式提供任务、工作目录、输入文件、允许修改的范围和验收条件。桌面聊天中的连接器、浏览器状态、附件和专用工具，也不能假定在 CLI 中全部可用。

## 本机入口

| 项目 | 当前结果 |
| --- | --- |
| 命令 | `codex` |
| 版本 | `codex-cli 0.164.0-alpha.11.1` |
| 当前可执行文件 | `C:\Users\spq\AppData\Local\OpenAI\Codex\bin\2993767bd1dfb009\codex.exe` |
| 登录检查 | `codex login status` 返回 `Logged in using ChatGPT` |
| 贝强工作目录 | `C:\Users\spq\Desktop\贝强` |

优先从 Muse 自己的运行环境解析 `codex`。上表中的版本目录可能在升级后变化，不应作为长期固定路径。

在 Muse 所用的 Windows 用户和进程环境中运行：

```powershell
Get-Command codex
codex --version
codex login status
codex exec --help
```

如果 Muse 找不到命令，先刷新或重启 Muse 进程以获取更新后的 PATH；也可以把已确认的 `codex.exe` 路径配置为 Muse 的可执行文件。Muse 在远程机器、容器、WSL 或不同 Windows 用户下运行时，需要在对应环境另行确认安装、路径和登录。

当前本机可复用现有登录，无需把凭证交给 Muse。其他环境通过 `codex login` 正常登录；API key 是另一种认证方式，费用和权限按该方式另算。不要把认证文件、令牌写入提示词或仓库。参见[官方认证说明](https://learn.chatgpt.com/docs/auth)。

## 最小调用

以下 PowerShell 命令只要求输出固定文本，不使用工具：

```powershell
'Do not call any tools. Reply with exactly CODEX_CLI_OK.' |
  codex -a never exec -C 'C:\Users\spq\Desktop\贝强' -s read-only --ephemeral --json --color never -
```

本机已运行这个测试：退出码为 `0`，收到 `agent_message` 内容 `CODEX_CLI_OK` 和 `turn.completed`。这证明当前 CLI 的认证和基本模型调用能够完成；具体业务工具仍需逐项确认。

该测试用了 `--ephemeral`，不会保存可供后续续接的会话记录。正式任务需要续接时，去掉此参数。

## Muse 调用约定

Muse 应直接启动可执行文件并传入参数数组，通过标准输入传送 UTF-8 提示词，不把用户内容拼接成一整条 shell 命令。这样可以保留中文、多行文本和引号，也避免 shell 将提示词内容当成命令执行。

建议的首次接入参数：

```text
可执行文件：解析得到的 codex.exe
参数数组：
  -a
  never
  exec
  -C
  C:\Users\spq\Desktop\贝强
  -s
  read-only
  --json
  --color
  never
  -
标准输入：任务提示词，UTF-8 编码，写完后关闭标准输入
```

| 参数 | 用途 |
| --- | --- |
| `exec` | 执行一次非交互任务，适合由 Muse 调用 |
| `-C <目录>` | 明确工作目录，避免任务在 Muse 安装目录运行 |
| `-s read-only` | 约束模型生成的 shell 操作，适合分析和接入测试 |
| `-s workspace-write` | 任务需要修改工作区文件时使用 |
| `-a never` | 不等待终端交互审批；受限操作会返回失败，不代表授予所有权限 |
| `--json` | 标准输出为逐行 JSON 事件流 |
| `--color never` | 禁用颜色控制符 |
| `-` | 从标准输入读取提示词 |
| `-o <文件>` | 另存最终答复；使用本次任务独有的绝对路径 |
| `--output-schema <文件>` | 按 JSON Schema 约束最终答复形状 |
| `-m <模型>` | 可选，显式选用已确认有权访问的模型 |

不指定 `-m` 时使用实际生效配置；桌面聊天中选定的模型不能据此推断为 CLI 模型。本版本不支持旧教程中的 `--full-auto`，需要写文件时使用 `-s workspace-write`。参见[官方非交互说明](https://learn.chatgpt.com/docs/non-interactive-mode)。

shell 的读写约束不能替代外部工具自身的授权控制。例如调用有写权限的经营接口，仍可能产生外部变更；仅做分析时，应在任务中明确禁止外部写入，并使用合适的工具配置。

### 提示词应包含的内容

```text
任务：分析指定文件并给出修改建议。
工作目录：C:\Users\spq\Desktop\贝强。
输入：列明文件绝对路径及必要背景。
授权范围：只读；不修改文件，不调用外部写入接口。
规则：遵循工作区 AGENTS.md 和本任务适用的下级说明。
验收：输出问题、证据位置、建议和未完成项。
缺少必需输入时：说明缺少什么，不自行编造事实。
```

允许修改时，把授权范围换成具体文件和动作，并写明验收方式。任务领取、并行写入与授权统一按[根AGENTS](../../AGENTS.md)及[总控工作流](../../00_总控台/AGENTS.md)执行；传入业务源路径，完成后直接回写该处。

## 读取结果

启用 `--json` 后，按行解析标准输出；每行是独立 JSON 对象，不要把整个输出当成一个 JSON。标准错误应单独保存为诊断日志，不能与 JSON 流合并。

常见事件示例：

```jsonl
{"type":"thread.started","thread_id":"实际会话ID"}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"最终答复"}}
{"type":"turn.completed","usage":{"input_tokens":100,"output_tokens":20}}
```

Muse 应保存 `thread.started.thread_id`，展示 `agent_message`，并处理 `turn.failed`、顶层 `error` 和进程异常退出。未知事件可保留原文，避免依赖固定事件数量或固定 `item` 编号。完整事件说明见[官方非交互输出](https://learn.chatgpt.com/docs/non-interactive-mode)。

完成判断应同时检查进程退出码、回合结束事件和任务验收条件。退出码为 `0` 并不证明商品已发布、文件正确或业务目标已完成；需要核验最终答复和对应产物。`item` 内的配置诊断也应保留并评估，不能仅因为含有 `error` 字样就认定整个任务失败。

### Python 调用示例

下面是可供 Muse 适配的标准库示例。它等待完成后统一处理输出；需要即时进度时，改为 `Popen` 并同时持续读取 stdout、stderr。使用较长任务超时，避免把启动工具所需时间误判为卡死。

```python
import json
import shutil
import subprocess

exe = shutil.which("codex.exe") or shutil.which("codex")
if not exe:
    raise RuntimeError("Muse 的运行环境找不到 Codex CLI")

workspace = r"C:\Users\spq\Desktop\贝强"
prompt = "不要调用任何工具。请只回复：Muse 接入成功。"
args = [
    exe, "-a", "never", "exec",
    "-C", workspace, "-s", "read-only",
    "--json", "--color", "never", "-",
]

try:
    result = subprocess.run(
        args,
        input=prompt,
        cwd=workspace,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        shell=False,
        timeout=600,
    )
except subprocess.TimeoutExpired as exc:
    # 超时不能证明先前动作没有执行，不能直接重派写入任务。
    raise RuntimeError("调用超时，需要核对已有进度和产物") from exc

events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
thread_id = next(
    (e["thread_id"] for e in events if e.get("type") == "thread.started"), None
)
messages = [
    e["item"]["text"] for e in events
    if e.get("type") == "item.completed"
    and e.get("item", {}).get("type") == "agent_message"
]
failed = any(e.get("type") in {"turn.failed", "error"} for e in events)
completed = any(e.get("type") == "turn.completed" for e in events)

print(json.dumps({
    "process_ok": result.returncode == 0 and completed and not failed,
    "thread_id": thread_id,
    "messages": messages,
    "diagnostics": result.stderr,
    "events": events,
}, ensure_ascii=False))
```

示例返回的是调用层结果。Muse 仍应根据本次任务检查产物，保留 `events` 中的诊断；日志按任务受控保存，不把其中的业务数据自动公开。

## 继续同一项任务

保存首次运行收到的会话 ID，然后明确指定 ID：

```powershell
'请基于上一轮结果继续，先说明尚未完成的部分。' |
  codex -a never exec -C 'C:\Users\spq\Desktop\贝强' -s read-only resume --json '实际会话ID' -
```

Muse 应维护自己的任务 ID 与 Codex 会话 ID 对应关系。多任务环境避免使用 `--last`，它可能命中其他任务。续接前确认原任务已结束，并核对授权范围。此示例将目录和权限参数放在 `resume` 前，符合本机 `codex exec --help` 与 `codex exec resume --help` 的参数结构。

本机已核对 `codex resume --all --include-non-interactive` 可用于列出非交互会话；正式会话记录位于 `E:\C盘迁移\Codex\.codex\sessions`。官方App Server列表接口默认筛选交互来源，但桌面App实际筛选尚未独立确认，因此侧栏不显示不能据此判断记录丢失。[官方会话列表](https://learn.chatgpt.com/docs/app-server)

`codex exec resume` 用于接续已保存且当前客户端可访问的会话。若 Muse 的目标是给当前桌面聊天发消息，应先核对聊天 ID 和共享服务的实际能力。本机另有 `codex queue --thread <ID> --message <文本>` 命令，但本次只核对了帮助，未验证投递与答复回收；不能把“已排队”当成“任务已完成”。

## 需要持续连接时

第一阶段用 `codex exec` 即可。若 Muse 需要持续对话、增量文本、运行中打断和审批交互，可接入 `codex app-server`：默认通过标准输入输出传输逐行 JSON 消息，客户端先完成 `initialize` 和 `initialized` 握手，再使用 `thread/start`、`thread/resume`、`turn/start` 和 `turn/interrupt` 等方法。具体协议以[官方 App Server 文档](https://learn.chatgpt.com/docs/app-server)及本机生成的 schema 为准。

```powershell
codex app-server --help
codex app-server generate-json-schema --help
```

自行启动一个 app-server 进程，不代表它已经连接到桌面应用当前服务或能操作当前聊天。共享桌面服务需要单独核实连接方式；不要直接读取或修改会话数据库来注入消息。

## 当前告警与故障处理

本机最小测试在出现下列告警后仍成功完成：模型列表刷新超时、部分 Skill 图标路径告警、PowerShell shell snapshot 不支持、`beiqiang-commerce` MCP 初始化失败，以及一个旧配置键被忽略。基本文本调用成功不代表故障 MCP 可用；需要该工具的任务应先修复并核验对应能力。

| 现象 | Muse 应如何处理 |
| --- | --- |
| 找不到 `codex` | 在 Muse 所在进程核 PATH、用户身份与可执行文件路径 |
| 未登录或认证失败 | 运行 `codex login status`，按正常流程登录；不复制他人凭证 |
| 模型不可用 | 核实际模型配置和账户权限；不擅自替换用户明确指定的模型 |
| 启动有告警 | 保留 stderr 和诊断事件，再核回合完成与任务所需工具 |
| 工作区外无法运行 | 先确认工作目录；仅在明确的非 Git 任务中按帮助考虑 `--skip-git-repo-check` |
| 文件写入受限 | 核任务是否已授权写入，再选择 `workspace-write`；不自动扩大到全盘权限 |
| 超时或进程中断 | 先核会话状态和已有产物，写入任务不得直接重复执行 |
| 只收到 `thread.started` | 只说明会话已创建，继续等待回合结束或失败事件 |

2026-10-28补核：Muse第2、3轮事件日志使用同一UUID，均有 `turn.completed`；Sol 6.1测试日志返回 `SOL61_OK`及完成事件。另一个 `sol` 测试返回该ID不受当前登录方式支持；不能据此推断 `gpt-6-sol` 的结果。原始日志与定位见[协作入口](Muse-Codex协作.md)。这些记录证明对应调用与续接，桌面消息投递及具体外部工具按实际接入另行验收。
