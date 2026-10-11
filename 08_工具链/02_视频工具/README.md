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
| `Erduo/` | 已安装 erduo-broll-loop-engineering 固定版及 HyperFrames 0.7.104；Windows 两秒竖屏渲染、交接准备和缓存复用已验证。可选独立导演/章节创作/审片与局部返修；分工与边界见[入口](Erduo/README.md)，不代替鞋类素材与成片验收 |
| `opencut-classic/` | OpenCut 第三方编辑器实体目录 |
| `Blender人体白模/` | Blender 人体白模相关工具和说明 |
| `ffmpeg/` | FFmpeg 本地运行文件 |
| `audio_review/` | 已验证的本地音轨提取、缓存中文ASR与声学时间证据；复用现有Whisper/GPU/librosa，无自动下载或上传。声音语义与听感须另核，见[入口](audio_review/README.md) |
| `tokenhub_video_review.py` | 腾讯云Kimi原生视频辅助审片；仅用已启用FREE且后付费关闭、余量≥200000的接入点，每次发送前核验，无自动重试。清单可设reasoning_effort=low/medium/high、max_completion_tokens=500–9000；默认medium/3500控制审片时长和输出量，不改变免费守卫。原生取样不替代局部原尺寸时序检查与创意判断 |
| `.libtv/` | LibTV 本地运行状态，不作为项目档案 |
| `LibTV/` | 官方CLI回读的模型规格与成本比较；Seedance2.5默认720P已核，精确积分价仍待核，不默认1080P，见[入口](LibTV/README.md) |

具体 AI 视频项目统一从 `../../05_内容与视频/03_通用AI视频实验/README.md` 进入。项目目录保存创作目标、素材、提示词、运行清单、候选输出和验收；本目录保存可复用工具。
