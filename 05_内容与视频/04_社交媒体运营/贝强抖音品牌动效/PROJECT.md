# 贝强抖音品牌动效

## 当前状态

2026-10-10：完成三张生成概念画面和18秒Remotion风格比较小样，等待负责人审美反馈；没有发布。不是正式品牌定稿。

## 本次目标与授权

负责人要求不用真实工厂照片，不以获客为本片目标；希望画面精美、可以抽象，让观看者对贝强有品牌印象。负责人要求参考Remotion skill及优秀案例，并明确说“可以试着做一些”。本次制作生成图片与本地Remotion动效，不调用付费AI视频生成模型。

生成鞋形只作视觉概念，没有映射到真实SKU。画面不证明贝强的材料、工厂设备、产能、测试或其他供应能力。品牌名采用文字排版；不是经确认的正式Logo。收尾“步履之间，自有风格。”为候选文案。

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

媒体及依赖仅在本地保存，不进入普通Git。依赖锁定Remotion 4.0.534；本机渲染浏览器为`C:/Program Files/Google/Chrome/Application/chrome.exe`。执行`npm install`、`node sound-design.mjs`后，运行`npm run render -- --browser-executable="C:/Program Files/Google/Chrome/Application/chrome.exe"`。生成图需要另行备份，Git不能重建原始像素。

## 创作判断与边界

本片用三个方向作比较，不代表正式成片需要混用三套风格。暖白更柔和，深色偏冷硬，彩色更醒目。这些是本轮审美判断，不是播放或品牌记忆效果证据。

当前动画包含镜头缩放与位移、逐字入场、曲线描绘、纵向遮罩转场及品牌收尾。鞋与织物仍是同一张图，不包含真实织物运动、独立鞋形转动或连续生产镜头。下一轮应先选定视觉方向，再拆分主体与背景、建立贯穿全片的动作；仅增加转场不会自动提升为成熟广告。

## 参考及采用的方法

- [Remotion官方AI Skills](https://www.remotion.dev/docs/ai/skills)：按画面、时间轴、排版、渲染拆分制作。
- [claude-motion作者工程](https://github.com/whaleyxbt/claude-motion)：借鉴分镜、时间轴、预览、回看与声音的制作流程，不以一次提示词生成作为质量证明。
- [Collectors Film作者复盘](https://github.com/sub-level/marketing-videos/blob/main/docs/case-studies/collectors-film.md)：借鉴字体比例、停留时间、连续视觉元素及独立竖屏排版。
- [BUCK / Nike White Hot](https://buck.co/work/nike-white-hot)、[ManvsMachine / Flyknit](https://mvsm.com/project/flyknit)：借鉴材质特写、光影揭示和抽象形状到鞋形的视觉关系。这些是专业CG参考，不能称为Remotion成片案例。
- [Jitter Opus 5.5介绍](https://jitter.video/changelog/2026-10-01-jitter-ai-opus-5-5)：可验证作者对运动与序列能力的描述；不据此断言模型做过专门的视频后训练。

## 验证

- TypeScript检查通过；依赖安装审计0已知漏洞。
- Remotion导出成功。视频H.264、1080×1920、30fps，540帧/18秒；AAC立体声48kHz，容器18.005秒，约16.3MB。
- 已查看暖白排版原始帧；本地浏览器完整播放到结束，readyState=4，视频尺寸与时长正确；抽查深色、彩色及收尾。排版无明显遮挡，主鞋形轮廓清楚。
- 音轨存在，解码正常，峰值约−17.7dB，无数值削波。浏览器播放完成不等同于负责人审美验收或抖音实际发布测试。
