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

## 执行边界

- `check`、`plan`、`paths` 和本地诊断可以直接使用。
- 不默认执行 `hypit auth login`，不把密钥写入项目文件。
- `build` 前先检查 Run 的 Needs；包含托管转录、图像、视频、语音或云 GPU 的 Build，仍需负责人按当前任务明确授权费用和范围。
- HypiHub 会接收其 Provider 所需的素材；贝强 SKU 原件、客户素材和未公开品牌文件不默认上传。
- H3 生成必须继续通过贝强中央 Prompt、官方工作流和校验器；未建设贝强自有 Provider 前，不用 Hypit 绕过该流程。
