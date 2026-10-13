# 腾讯云 TokenHub CLI

## 当前状态

2026-10-10，按负责人提供的官方安装指南完成本机安装：

- Node.js v20.14.0、npm 10.7.0；CLI `tencent-tokenhub-cli` 1.0.1，`thcli --version` 通过。
- npm 全局目录：`C:/Users/spq/AppData/Roaming/npm`；上游仓库为 TencentCloud/THCLI。
- 官方 Skills v1.0.0，12个；`thcli +connect status` 回读为最新。Codex安装目录为 `C:/Users/spq/.agents/skills/thcli-*`，同时按安装器默认发现规则注入Claude Code、CodeBuddy、Cursor和Trae。
- 当前 profile=default、site=cn、area=gz，负责人已完成浏览器授权；`auth status` 返回成功，脱敏default alias配置存在，现有Key启用且绑定全部接入点。
- 现有可灵V3、MiniMax H3/H3 Max接入点回读为ACTIVE；本次未开通模型、创建Key或修改云配置。负责人选择可灵V3并明确确认两段各5秒、1080P、无声，预计合计8元；两次提交均成功，输出已保存品牌片项目。没有额外付费重试。

## 依据与执行入口

- [用户指定安装指南](https://gz-thcli-skills-1258344699.cos.ap-guangzhou.myqcloud.com/tokenhub-cli-skills/install.md)
- [上游](https://github.com/TencentCloud/THCLI)
- 执行时读取本机 `thcli-overview`、`thcli-shared` 及实际资源域 Skill；当前参数以 `thcli <command> --help` 为准。
- 文档第一次经网页工具不可访问、默认环境请求连接失败；在已授权本机正常网络中重新读取成功。安装、npm包信息及Skills下载随后成功，不归因为负责人未授权。

## 登录故障与恢复结论

安装指南针对Codex的无浏览器登录要求用户自行在终端运行：

```powershell
thcli auth login --browser no
```

用户在浏览器完成腾讯云授权，将页面凭据粘贴回自己的终端；不发送聊天，不写入项目。用户完成后，依次验证 `thcli auth status` 与 `thcli chat-config get`；脱敏default alias存在即通过，不因星号重复建Key。未设置时依官方流程处理，绝不读取或记录密钥明文。

负责人随后明确要求“你执行终端，我会进行登陆”。首次回调后 `get_temp_cred` 的 Node fetch 失败，进程自行退出。第二次官方登录保持原进程、原state，负责人完成授权后返回成功，凭证由CLI管理，不写项目。

已确认CLI 1.0.1的Windows自动开页存在URL截断：通过shell执行未完整引用的`start`命令，URL中的`&`被解释为命令分隔。使用不含凭证的模拟URL复现。随后以PowerShell `Start-Process -FilePath`打开同一完整登录地址，保留OAuth原state与回调；授权成功。没有更改官方CLI、关闭校验或修改全局代理。此前fetch失败的底层根因仍未证实。

已完成的网络诊断：Node环境无HTTP_PROXY/HTTPS_PROXY/ALL_PROXY覆盖；当前无凭证POST `/cli/get_temp_cred` 收到HTTP400和“AccessToken is required”，说明该次探测能到交换接口，不代表登录成功。显式绕过HTTP代理与经系统代理127.0.0.1:7892的两条测试均收到同类HTTP400。系统同时有hongmo TUN网卡198.18.0.1，目标域名解析为198.18.1.71；所以“不使用HTTP代理参数”不能称完全绕过代理软件。此前失败的底层错误码未知，尚未证明代理是根因。没有关闭TUN、修改全局代理、改DNS或降低TLS校验。

`fetch-diagnostics.cjs` 是可选Node preload，仅在fetch失败时打印异常name/code/syscall链；不打印URL、请求、响应或凭证，不修改官方CLI。语法检查通过。用于收集下一次失败的底层网络原因，实际登录仍由官方CLI管理。

只读查询可查模型/比价、Key用量和诊断；`+chat` 是模型对话能力，会消耗token。云端Key创建/修改/删除/明文、模型开通、接入点变更和套餐购买等，在官方Skills默认流程中由用户自行执行。凭证由CLI管理，不进Git。

## 视频执行入口

当前CLI没有独立视频生成命令；模型、价格、接入点与Key通过官方CLI只读查询。可灵V3生成使用腾讯云[官方异步接口](https://cloud.tencent.com/document/product/1823/135742)。`validate-video-trial.mjs`先离线检查两段授权配方、尺寸与提示词；`tokenhub-kling-video.mjs`只支持已明确批准的可灵V3配方，提交前落账、已有账本禁止再次提交，轮询保存脱敏回执与本地视频。API Key仅从CLI现有配置读入内存，不输出、不保存、不修改凭证文件。

本次配方与回执：`05_内容与视频/04_社交媒体运营/贝强抖音品牌动效/tokenhub-trial.json`及同项目`edit/generation/tokenhub-kling-v3/`。估计8元不视为账单验收；两次成功回读各400000用量单位，最终费用以平台账单为准。生成成功与动作质量验收分别记录在项目入口。

负责人随后认可改宽构图、重做完整迈步并扩完整内容的建议。本轮沿用可灵V3，单次5秒1080P无声，预计新增4元；`tokenhub-step-v2.json`保存完整首尾图提示词、生成提示词与范围，任务`step-v2`回读succeeded、400000用量单位。新版落地留在画内，素材已进入18.5秒完整候选；没有额外自动付费重试。离线校验器已支持费用范围一致的1–2个独立任务，原两段配方仍校验通过。实际费用仍以平台账单为准。
