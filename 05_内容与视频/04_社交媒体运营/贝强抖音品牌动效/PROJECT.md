# 贝强抖音品牌动效

## 当前状态

2026-10-10：第一版为三张风格图和18秒比较小样。负责人要求“请继续下一步”后，本轮完成暖白方向20秒分层品牌片，已导出、检查关键画面与转场，并交付本地视频，等待负责人观看反馈。采用暖白是本轮执行判断，并非负责人正式定版。没有发布。

## 本次目标与授权

负责人要求不用真实工厂照片，不以获客为本片目标；希望画面精美、可以抽象，让观看者对贝强有品牌印象。负责人要求参考Remotion skill及优秀案例，并明确说“可以试着做一些”。本次制作生成图片与本地Remotion动效，不调用付费AI视频生成模型。

生成鞋形只作视觉概念，没有映射到真实SKU。画面不证明贝强的材料、工厂设备、产能、测试或其他供应能力。品牌名采用文字排版；不是经确认的正式Logo。收尾“步履之间，自有风格。”为候选文案。

本轮仍使用builtin image_gen制作分层图片及本地Remotion动画；不调用付费AI视频生成模型。

## 文件与复现

| 内容 | 文件 |
| --- | --- |
| 暖白、深色、彩色原始生成画面 | `public/warm.png`、`public/dark.png`、`public/color.png` |
| 生成工具及完整提示词 | `prompts.json`，builtin image_gen，2026-10-10 |
| Remotion工程 | `src/Root.tsx`、`src/index.ts`、`package.json`、`package-lock.json` |
| 本地原创合成声音 | `sound-design.mjs` → `public/sound.wav`，无外部采样 |
| 动效小样 | `out/贝强_三种风格动效试稿.mp4` |
| 排版检查 | `out/暖白排版.png`、`out/深色排版.png` |
| 比较预览 | `preview.html`；运行`node preview-server.mjs`，地址`http://127.0.0.1:3417` |
| 第二版鞋形、背景、织带 | `public/shoe-v2.png`、`public/space-v2.png`、`public/ribbon-v2.png` |
| 第二版生成提示词与原始参考 | `prompts-v2.json`；参考为`public/warm.png` |
| 第二版分层动画 | `src/WarmFilm.tsx`，composition `WarmBrandFilm` |
| 第二版声音 | `node sound-design.mjs --v2` → `public/sound-v2.wav` |
| 第二版20秒品牌片 | `out/贝强_暖白织带品牌片_v2.mp4` |
| 第二版排版检查 | `out/v2_开场.png`、`out/v2_主视觉.png`、`out/v2_细节.png`、`out/v2_收尾.png` |
| 第二版导出视频抽样检查 | `out/v2_QA_逐秒画面.jpg`、`out/v2_QA_收尾转场.jpg` |

媒体及依赖仅在本地保存，不进入普通Git。依赖锁定Remotion 4.0.534；本机渲染浏览器为`C:/Program Files/Google/Chrome/Application/chrome.exe`。执行`npm install`、`node sound-design.mjs`后，运行`npm run render -- --browser-executable="C:/Program Files/Google/Chrome/Application/chrome.exe"`。生成图需要另行备份，Git不能重建原始像素。

第二版复现：先运行`node sound-design.mjs --v2`，再运行`npm run render:warm -- --pixel-format=yuv420p --color-space=bt709 --browser-executable="C:/Program Files/Google/Chrome/Application/chrome.exe"`。预览页默认第二版，同时保留第一版回看。

## 创作判断与边界

本片用三个方向作比较，不代表正式成片需要混用三套风格。暖白更柔和，深色偏冷硬，彩色更醒目。这些是本轮审美判断，不是播放或品牌记忆效果证据。

第一版包含镜头缩放与位移、逐字入场、曲线描绘、纵向遮罩转场及品牌收尾，鞋与织物是同一张图。

第二版围绕同一暖白织物展开：0–4秒纤维开场与鞋形揭示；4–10秒鞋与织带分层悬浮；10–14秒连续推进到鞋面特写；14–17秒织带掠过、纹理进入贝强字样；17–20秒品牌停留。鞋、背景、前后织带独立位移与缩放；织带增加轻微二维形变；品牌文字经历纹理填充到实色的过渡。没有真实3D鞋形旋转或布料物理模拟，也没有生产过程镜头。

相较第一版，第二版统一了材质和动作线索，但视觉仍偏柔和，文案与字样辨识尚未通过观众反馈验证。正式片应由负责人观看后决定是否保留此方向。

## 参考及采用的方法

- [Remotion官方AI Skills](https://www.remotion.dev/docs/ai/skills)：按画面、时间轴、排版、渲染拆分制作。
- [claude-motion作者工程](https://github.com/whaleyxbt/claude-motion)：借鉴分镜、时间轴、预览、回看与声音的制作流程，不以一次提示词生成作为质量证明。
- [Collectors Film作者复盘](https://github.com/sub-level/marketing-videos/blob/main/docs/case-studies/collectors-film.md)：借鉴字体比例、停留时间、连续视觉元素及独立竖屏排版。
- [BUCK / Nike White Hot](https://buck.co/work/nike-white-hot)、[ManvsMachine / Flyknit](https://mvsm.com/project/flyknit)：借鉴材质特写、光影揭示和抽象形状到鞋形的视觉关系。这些是专业CG参考，不能称为Remotion成片案例。
- [Jitter Opus 5.5介绍](https://jitter.video/changelog/2026-10-01-jitter-ai-opus-5-5)：可验证作者对运动与序列能力的描述；不据此断言模型做过专门的视频后训练。

## 验证

### 第二版

- TypeScript检查通过。鞋与织带PNG为RGBA，alpha范围0–254；背景无鞋，为独立RGB画面。
- 已检查四张关键画面：开场、主视觉、鞋面特写、品牌收尾。主鞋形完整可读，特写裁切是镜头设计；文字与主体未互相遮挡。
- 导出成功：H.264、1080×1920、30fps、600帧；yuv420p / BT.709；AAC立体声48kHz。视频20秒，容器20.011秒，文件20,571,726字节。
- 抽查导出视频的逐秒画面，并以每秒4帧检查13.5–17秒的品牌转场；鞋形与织带运动连续，品牌纹理过渡到实色，未见明显缺图或文字裁切。
- 全片音轨解码正常，平均−24.0dB，峰值−8.4dB，无数值削波；这不是音乐审美或用户试听验收。
- 现有浏览器预览页之一停在错误页，浏览器工具因协议策略拒绝绑定该页；未绕过该拒绝。本轮采用本地媒体交付，浏览器完整播放验收未完成，等待负责人实际观看。

### 第一版

- TypeScript检查通过；依赖安装审计0已知漏洞。
- Remotion导出成功。视频H.264、1080×1920、30fps，540帧/18秒；AAC立体声48kHz，容器18.005秒，约16.3MB。
- 已查看暖白排版原始帧；本地浏览器完整播放到结束，readyState=4，视频尺寸与时长正确；抽查深色、彩色及收尾。排版无明显遮挡，主鞋形轮廓清楚。
- 音轨存在，解码正常，峰值约−17.7dB，无数值削波。浏览器播放完成不等同于负责人审美验收或抖音实际发布测试。
