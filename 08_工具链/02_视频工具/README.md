# 视频工具目录

这里只放可复用的视频生成、剪辑、检查工具和运行环境，不放具体项目的素材与成片。

| 目录或文件 | 用途 |
| --- | --- |
| `MiniMax-H3/` | H3 中央规范、官方工作流与校验工具 |
| `seedance_video/` | Seedance 相关脚本与接口工具 |
| `video_use/` | 视频下载、抽帧、检查和剪辑能力 |
| `remotion/` | 当前 Remotion 工程与可视化视频制作 |
| `awesome-seedance/` | **工作区级通用视频模板库**（第三方，上游每日同步，本地保留不进 Git）。25 个分类模板 / 463 案例 / 12 个可选 Skill；来源 `LearnPrompt/awesome-seedance`，许可为代码 MIT + 策展 CC BY 4.0 + 提示词归原作者。索引见 [模板索引](../../07_知识库与Skills/04_AI视频知识体系/awesome-seedance-模板索引.md) |
| `Hypit/` | 已安装固定版 0.1.8，作为实验性可选编排与合成后端；本地参考抽帧、原型 Build/导出已验证。与 video-use 的分工见 [工具入口](Hypit/README.md)，不代表商业成片已验收 |
| `reference_remake/` | 完整参考视频＋真实同SKU图片→LibTV整片草稿的准备与CLI接线工具；不调用生成、不安装模型或剪辑器。来源、职责和测试边界见[入口](reference_remake/README.md) |
| `Erduo/` | 已安装 erduo-broll-loop-engineering 固定版及 HyperFrames 0.7.104；Windows 两秒竖屏渲染、交接准备和缓存复用已验证。可选独立导演/章节创作/审片与局部返修；分工与边界见[入口](Erduo/README.md)，不代替鞋类素材与成片验收 |
| `opencut-classic/` | OpenCut 原始代码实体目录，README已标明归档且不再维护；不当作新版MCP/批量渲染已接通 |
| `Blender人体白模/` | Blender 人体白模相关工具和说明 |
| `ffmpeg/` | FFmpeg 本地运行文件 |
| `audio_review/` | 音轨解码/信号证据及云端原生音视频客户端。MiMo和MiniCPM官方API已测试但存在确定语义误报；方舟豆包API返回ModelNotOpen后暂停。按负责人要求删除MiniCPM权重/Comni、MNN运行库与本地推理客户端，不部署本地模型，见[入口](audio_review/README.md) |
| `tokenhub_video_review.py` | 腾讯云Kimi原生视频辅助审片；仅用已启用FREE且后付费关闭、余量≥200000的接入点，每次发送前核验，无自动重试。清单可设reasoning_effort=low/medium/high、max_completion_tokens=500–9000；默认medium/3500控制审片时长和输出量，不改变免费守卫。原生取样不替代局部原尺寸时序检查与创意判断 |
| `.libtv/` | LibTV 本地运行状态，不作为项目档案 |
| `LibTV/` | 官方CLI回读的模型规格与成本比较；28秒图片参考含声720P=1288/1080P=3080积分；同次完整视频参考报价720P=1288/1080P=6160积分。最终商品绑定与提示词改变后须正常核最终报价，不换算未知积分人民币成本，见[入口](LibTV/README.md) |

具体 AI 视频项目统一从 `../../05_内容与视频/03_通用AI视频实验/README.md` 进入。项目目录保存创作目标、素材、提示词、运行清单、候选输出和验收；本目录保存可复用工具。

## 剪辑项目核对与选择（2026-10-12）

未核实一个名为Origin Cut的高关注剪辑仓库，最接近负责人描述的是OpenCut；未把相似名称当同一项目。以下star为当天官方仓库显示约数，不能当可用性或审美验收。

| 项目 | 约star / 现状 | 对当前整条AI复刻的帮助与决定 |
| --- | --- | --- |
| [OpenCut](https://github.com/OpenCut-app/OpenCut) | 93.7k；官方仍标明重写，Editor API/MCP/无头模式属建设内容 | 可关注未来可编程编辑器；本地classic已归档，不启动整套数据库、Redis和开发服务来替换现有链路 |
| [OpenChatCut](https://github.com/0xsline/OpenChatCut) | 2.3k；独立AGPL项目，与商业ChatCut无隶属；Windows早期安装包，已提供本地MCP和多轨时间轴 | 最符合可检查/可撤销/保留完整原素材的剪辑目标，支持FCPXML和硬件H264导出；值得后续单项目导入—编辑—导出验证。未安装或宣称实测通过 |
| [商业ChatCut](https://chatcut.io/) | 官方商业产品，不以GitHub star衡量 | 现有Hosted MCP已配置并启用，但本会话没有工具；尚未验证登录或项目调用。按插件接入说明先恢复既有连接，不重复注册或以插件缺工具为由安装桌面版。生成仍走用户选定LibTV |
| [LosslessCut](https://github.com/mifi/lossless-cut) | 44.5k；FFmpeg无损剪切/重排/合并 | 适合检查与保存完整素材或快速裁切，不承担创意审片/商品替换；基础能力本机FFmpeg已有，不重复装应用 |
| [auto-editor](https://github.com/WyattBlue/auto-editor) | 5.5k；音量/运动阈值决定保留与切除，可导出编辑工程 | 对口播粗剪有帮助，但不将静音/低运动等同商品无信息；当前音乐驱动鞋片不默认启用自动删静音或删静止 |

制作链保持原视频直接提供参考条件、真实商品图锁身份、整条28秒输出；编辑器负责可控文字、混音、必要修整和导出，不靠自动大量删除来掩盖生成失败。重点借鉴可撤销编辑、素材来源关联、单个导出队列与完整时间轴，项目原件保留不覆盖。新工具需验证完整原片导入、声轨接入、转脚/抬跟保留、完整长度导出与资源回收，不能仅用成功启动页面验收。

## 运行收尾与资源边界

每次生成/审片/渲染记录自己启动的进程PID、父进程、命令职责、端口与退出状态，任务结束在finally或显式关闭时回收。只关闭已核本任务的闲置服务；不按python/node名称批量结束，不终止Codex界面、其他任务MCP或用户应用。本地语义推理已退出；导出一次一个，不另留预览网站或并行GPU作业。

2026-10-12负责人报告卡顿后已实际查进程、三秒CPU增量、RAM/GPU及旧预览端口：未发现MiniCPM/Comni/FFmpeg/Remotion作业，3417/3418无监听；Python任务为Blender MCP服务，不能冒充视频推理残留。内存31.69GB，可用约10.7GB，Codex界面ChatGPT子进程初次合计约6.9GB；这只是资源占用，不证明唯一根因。已结束本轮浏览器/桌面工具JS会话并确认诊断终端退出，复测CPU活动显著降低、可用约10.8GB、磁盘队列0；显存约1.5—1.7GB，无模型占满。负责人随后明确反馈“明显改善”；说明回收本轮会话有实际帮助，不据此证明唯一根因。未强关应用；若再持续卡顿，需将界面重启与相同任务下的前后指标对应，不能先乱杀后台。
