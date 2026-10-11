# Hypit 工具入口

当前固定版本：`@hypit/hypit@0.1.8`。

接入状态：已作为实验性可选后端接入；本地 `check`、`plan`、Runtime、Build、导出与代表帧视觉 QA 均已通过。验证 Build：`bld_20260915T130035090Z_DDFAC8EA3F`。

## 定位

Hypit 是贝强视频工具链中的可选语义编排、批量变体与可编辑合成后端。目前不替代 LibTV、Seedance/H3、video-use、OpenCut，也不自动选择或登录任何托管 Provider。

## 目录

- `distribution/`：固定版本的 Hypit 可执行 Distribution；`node_modules/` 不进入 Git。
- `Invoke-Hypit.ps1`：统一启动入口，优先使用满足版本要求的 Node，并将其目录前置到当前进程 `PATH`，确保 Hypit 的安装与渲染子进程使用同一版本；同时加入项目内 FFmpeg。
- `Initialize-HypitDistribution.ps1`：为 Hypit `0.1.8` 发布包内已附带、但未建立 Node 解析入口的内部包，以及它固定安装的 HyperFrames Engine/Producer 创建本地 Junction；只补缺失入口，不覆盖现有依赖。
- `Hypit接入评估_2026-09-15.md`：接入边界、风险和三阶段试点方案。

兼容性说明：Hypit `0.1.8` 的 `packages install` 能将 Inter 字体标记为机器级 Ready，但当前 Source 编译未能从该 store 解析字体。隔离 Distribution 因此同时固定本地依赖 `@fontsource-variable/inter@5.3.0`。此外，该版本发布包附带内部 workspace 源码，却没有为 Build 子进程建立包解析入口；启动脚本会自动补齐本地 Junction。两项兼容处理都没有修改 Hypit 上游源码。

本地 smoke test 位于 `99_临时区/Hypit_POC/`；成片为 `output/hypit-ready.mp4`。

## 使用

从具体 Hypit 视频项目根目录调用：

```powershell
& 'C:\Users\spq\Desktop\贝强\08_工具链\02_视频工具\Hypit\Invoke-Hypit.ps1' --version
& 'C:\Users\spq\Desktop\贝强\08_工具链\02_视频工具\Hypit\Invoke-Hypit.ps1' paths
& 'C:\Users\spq\Desktop\贝强\08_工具链\02_视频工具\Hypit\Invoke-Hypit.ps1' check .\authors\main.svml
```

## 与 video-use 配合

用户指定 Hypit 或任务需要参考改编、语义编排时，读取已安装 Hypit Skill；不要因命令未加入全局 PATH 而判定未安装，统一使用本目录启动器。Hypit 不会自动让 video-use 调用它，二者通过同一项目素材、时间基准与证据关联。

1. video-use 获取公开参考并核对作品 ID、时长、尺寸与主体，原件只保存一份；下载失败时使用有支持证据的站点导出或浏览器媒体下载，不把相邻自动播放视频当目标。
2. Hypit `media probe/tile/frames` 检查同一文件，以整体取样和关键事件密集序列解释构图、接触、变化与落点。连续播放、听审和转录是否完成分别记录；序列图不能认证声音、全部连续动作或主观体感。
3. 先形成有具体视觉事件的创意，再选合成后端。适合 Hypit 的项目用其组件、Timeline、Runtime；已有 Remotion 工程且行为合适时可以继续使用，不为接工具重建两套时间线。Hypit 的导演方法可以使用，生成与 Build 不必强行使用。
4. 共享原件路径、source_id、取样时刻及已验证的转录时钟；避免重复下载、转录或付费生成。生成模型与授权按项目另核，不从 Hypit Provider 的可用性推断可免费调用。
5. 输出重新交给 video-use 做技术检查、原尺寸疑点检查及独立创意复核。Build 成功、无重复帧、外部模型赞同均不能单独证明成片质量。

声音不能从图片取样中自动获得。本地音轨、语言与声学时间检查可复用[声音入口](../audio_review/README.md)，不自动登录Hosted转录或上传素材；已核时钟的转写可作为语义分析输入。音乐和听感需要真正接收音频的审片路线，不能用ASR或波形代替。

2026-10-11 已实测固定版 `media probe` 与 `media tile`；本地 FFmpeg 子进程在受限环境可能报 `spawn EPERM`，按正常审批执行同一命令可通过。`probe` 的时长显示可能取三位小数，末段 `tile --end` 需使用 CLI 接受的边界；不据此改变原片身份或声画时钟。此次仅验证参考检查，未生成品牌成片。

## 执行边界

- `check`、`plan`、`paths` 和本地诊断可以直接使用。
- 不默认执行 `hypit auth login`，不把密钥写入项目文件。
- `build` 前先检查 Run 的 Needs；包含托管转录、图像、视频、语音或云 GPU 的 Build，仍需负责人按当前任务明确授权费用和范围。
- HypiHub 会接收其 Provider 所需的素材；贝强 SKU 原件、客户素材和未公开品牌文件不默认上传。
- H3 生成必须继续通过贝强中央 Prompt、官方工作流和校验器；未建设贝强自有 Provider 前，不用 Hypit 绕过该流程。
