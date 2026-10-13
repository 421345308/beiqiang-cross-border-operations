# Erduo：可选 B-roll 制作与独立审片路线

已按负责人要求接入。它增加字幕/简报驱动的动效镜头、分镜交接、独立审片和局部重渲染能力，不负责抓取社交平台、自动换商品或预测成交；鞋与脚的真实感仍由实物证据、生成素材及逐时审片承担。

## 安装与固定版本

- [上游](https://github.com/erduo1998-cell/erduo-broll-loop-engineering)固定在 `741583ed973f9a431fcb262396556eae7fd13f15`，`RELEASE_VERSION` 为 1.1.1；根 package.json 的 1.1.0 不作为实际安装身份。
- 主 Skill 已用 skill-installer 安装到个人 Codex skills 的 `erduo-broll-loop-engineering/`，包含引用、脚本及 13 个旧阶段 Skill。新一轮可发现；按实际路线读取，不全部加载。
- 运行源码在本目录 `upstream/`，HyperFrames 固定 **0.7.104**。doctor 提示新版不等于应升级。
- 8 个官方核心 Skill 用同一安装器固定到 `official-skills/`；[来源](https://github.com/heygen-com/hyperframes)提交 `c96b30c7174984e684620556ce871a285381ec60`。仅按需读，未覆盖其他全局 Skill。
- 使用已有 Node 24.19.0、FFmpeg、FFprobe 和 Chrome Headless。依赖与上游嵌套仓库留本地，不进项目 Git；恢复安装以本页版本和 [安装清单](INSTALLATION.json)为准。

## 与现有视频能力的分工

1. **video-use** 获取参考、核对作品身份、抽帧和独立检查；**audio_review** 复用缓存 ASR 与音轨时间证据；**Hypit** 按需辅助参考理解与语义编排。
2. 选用 **Erduo** 新项目主链时：完整原始 SRT/design → 新上下文导演 → 连续章节创作者 → 父任务统一渲染 → 新上下文审片者 → 原作者局部返修。审片者看实际画面及原意，不看作者解释、耗时或成本。
3. 主链用 HyperFrames；显式 Remotion 或已有旧项目走上游 legacy 路线。当前贝强项目不自动迁移、不并行维护两条成片时间线。
4. 产品画面来自核过的贝强素材或生成结果，代码负责可编辑的排版、文字、转场及合成。技法卡是方法参考，不是鞋类视频素材库。

新上下文交接只在实际选用这条制作路线时执行。任务准备器生成 TASK.md，并不自动启动角色或隔离上下文。主 Skill 的代码为 MIT；作者另外的 Agent Motion 非商业许可不随本次接入获得商业授权。

## Windows 入口

从工作区运行，下例目录只是两秒技术验证：

```powershell
& '08_工具链/02_视频工具/Erduo/Invoke-Erduo.ps1' -Mode runtime --version
& '08_工具链/02_视频工具/Erduo/Invoke-Erduo.ps1' -Mode plan --project 'C:/Users/spq/Desktop/贝强/99_临时区/Erduo_POC'
& '08_工具链/02_视频工具/Erduo/Invoke-Erduo.ps1' -Mode task --project 'C:/Users/spq/Desktop/贝强/99_临时区/Erduo_POC' --role director --srt input/original.srt --design input/design.md
& '08_工具链/02_视频工具/Erduo/Invoke-Erduo.ps1' -Mode render --project 'C:/Users/spq/Desktop/贝强/99_临时区/Erduo_POC' --quality final
```

入口修复两项已复现的 Windows 兼容问题：`.mjs` 用所选 Node 显式启动；环境里的 PATH/Path 仅在值完全一致时合并，再交给上游 safe-spawn。值不同仍拒绝，其他同名冲突仍拒绝；PEXELS_API_KEY 清除与 HYPERFRAMES_NO_TELEMETRY=1 保留。未修改上游、关闭 TLS、扩大网络权限或输出环境值。

本地渲染需启动浏览器/FFmpeg 子进程；受限执行中曾返回 spawn EPERM，正常提权运行成功。这是运行环境边界，与用户是否授权制作不同。

## 实测范围（2026-10-11）

两秒单镜技术样例：中文文字、有限 GSAP 位移、本地字体和脚本 → MP4 **1080×1920、30fps、H.264、60帧、无声**；完整解码通过，抽样图中移动与落点成立。首次渲染约20秒，再跑仅复用缓存约0.8秒，未重做镜头。版本查询、计划检查、导演任务准备及 Windows 渲染入口均成功。

证据在工作区 `99_临时区/Erduo_POC/lean-renders/final/index.json` 与 checks/S01.png，摘要哈希见安装清单。它不是商业片、鞋类生成测试、带声连看或独立审美验收。上游支持矩阵仍将 Windows 标为 unverified；本地这项有限验证不改写其状态。可选 Whisper.cpp/Kokoro/MusicGen 缺失不阻断已验证的无声渲染；已有音频工具可用，无需盲装。

是否采用，以具体画面任务决定。安装解决工具与交接，最终审美、动作有效性和付费素材利用率仍要对真实成片验证。
