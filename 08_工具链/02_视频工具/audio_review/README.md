# 视频声音与云端音视频理解

作用：从已核身份的视频原件提取音轨，恢复口播的词级时间、响度能量包络、声音变化与节拍候选，供镜头分析和剪辑使用。原有audio_review.py只做本地提取/ASR/信号分析，无上传、模型下载或付费API。新增原生音视频请求入口另需明确上传范围；原件只读，证据保存到具体项目。

## 既有工具与GitHub研究（历史核验）

2026-10-11查询官方仓库页面显示的约数；star会变，代表关注度，不是本任务效果排名。

| 官方项目 | 当前约star | 能解决什么 | 本项目取舍 |
| --- | --- | --- | --- |
| [openai/whisper](https://github.com/openai/whisper) | 110.3k | 多语言语音识别 | 本机已安装、有中文small权重和可用GPU，本轮直接复用，无需下载 |
| [ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp) | 54.3k | C/C++本地ASR，支持Windows、CPU及多种加速 | 合理的便携替代，但不会新增声音审美理解，本轮不重复安装 |
| [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) | 25.8k | CTranslate2优化ASR及量化 | 已装1.2.1，仅其tiny.en转换权重有缓存；不能用英文模型处理本参考中文。要使用需中文转换权重及兼容CUDA/cuDNN，当前不为重复能力下载 |
| [librosa/librosa](https://github.com/librosa/librosa) | 8.7k | 音频/音乐信号分析，节拍与起音候选 | 已装0.11.0，本轮实测；人声可能污染节拍估计，不能等同音乐BPM或脚步事件 |
| [QwenLM/Qwen2.5-Omni](https://github.com/QwenLM/Qwen2.5-Omni) | 4.1k | 联合理解音频、视频与文字 | 可作声画语义模型路线。官方标准BF16/Transformers示例中3B处理30秒视频最低约22.43GB，当前8GB GPU不能直接照搬；量化/其他运行方式需另行测试，不为一次参考盲装大模型 |

四种能力分开：音轨存在/解码、语言恢复、声学时间定位、听感与声画意义判断。前三项工具成功不能证明第四项完成。通过播放器让用户能听到，与当前助手实际获得音频理解输入也不同。

## 已验证的本地链路

本机FFmpeg、Python、Whisper20250625、PyTorch2.2.1、librosa0.11.0、NumPy1.26.4与soundfile0.14.0已成功处理19.73秒公开参考。RTX4060 Laptop 8GB可用，读取已有small.pt，不网络下载；模型加载及转写约7.72秒，进度显示实际解码约5.81秒。Windows没有Triton快速对齐内核时自动用较慢的词时间实现，不能把词时刻当精确人工标注。

结果包含中文口播和词时间，但口语存在明显误识；只是研究证据，不是可直接发布的字幕或已人工听核的逐字稿。文字与画面联合分析可重新解释参考开场用途；音乐风格、脚步来源、听感仍需真正的音频理解输入或人工听审。

## 调用

```powershell
$taskModelPath = Join-Path $env:USERPROFILE '.cache/whisper/small.pt'
python -X utf8 -u '08_工具链/02_视频工具/audio_review/audio_review.py' '<已核本地视频>' --output '<该项目/edit/音频证据目录>' --model-file $taskModelPath --language zh --device cuda
```

不传`--model-file`时只提取与分析声学特征，适用于无口播的产品片，避免把音乐转成幻觉字幕。权重必须已存在，不自动下载；CUDA不可用时直接报错，不暗中切CPU。无音轨时直接报错，不虚构静音/口播。非零音轨起始时间需要明确时钟映射，当前工具拒绝静默偏移。

输出：`audio.wav`、`audio_streams.json`、`signal_features.json`、`audio_timeline.png`、可选`transcript.json/txt`及`manifest.json`。相同源SHA256、参数、模型SHA256的完成结果缓存复用，不重复转写；不同源/参数要求新证据目录。所有时刻共享源时钟；RMS是能量度量，不是LUFS响度认证，起音/节拍是候选而非声源识别，0dBFS峰值不单独证明削波。

## 与Hypit、video-use和外部审片配合

获取、身份、画面序列仍走video-use/Hypit；声音证据与同一原件关联。在关键字词、音频空隙或动作时刻有具体问题时再生成声画局部视图，不把整段音轨反复转写。ASR错误保留并标注，不根据先前模型回答偷偷改“原始转写”。

需要对音乐、音色、音效与画面关系作语义判断时，选择确实接受音频/带音轨视频的模型或人工听审，记录实际输入、是否接受、采样范围及证据，不把只有图片的模型称作听过视频。外部音轨上传和付费调用按当次授权、工具审核执行；不因参考是公开的便绕过明确的上传拒绝。

## 原生音视频理解：当前实测与自主维护

2026-10-12新增两个可复用入口。它们不同于音轨提取、波形或ASR，不以文字转写替代听感。

- `omni_review.py`：完整本地MP4/音轨上传Qwen官方免费HF演示，支持Qwen2.5和Qwen3；必传`--authorized-upload`，保存输入hash/时长/提示词/响应，已有尝试目录不重新提交。失败返回非零退出码，超时取消本次job，无自动重试。依赖gradio_client隔离安装在99_临时区/音视频审片/deps，未改全局Python。Qwen3请求关闭输出语音，仅审片。
- `tokenhub_omni_review.py`：MiMo V2.6 Flash经腾讯云原生video_url或input_audio输入；保留整个音轨，不上传转写/波形替代它。复用免费预检：ACTIVE、FREE、后付费关闭、余量≥200000，不开通资源、不切付费。客户端发送完整文件；模型内部2fps取样不等于逐帧看尽，快切/接地仍需局部检查。记录usage.audio_tokens：缺失/零记为unconfirmed，有数值仅证明计量声轨输入，不证明回答正确。完成答复与独立核验分开。

厂商原始规范：[MiMo视频](https://mimo.mi.com/docs/en-US/quick-start/usage-guide/multimodal-understanding/video-understanding)、[MiMo音频](https://mimo.mi.com/docs/en-US/quick-start/usage-guide/multimodal-understanding/audio-understanding)。腾讯云是否支持同一原生契约必须实际调用；不能由模型目录的“多模态”标签直接认定音轨接入通过。

```powershell
python '08_工具链/02_视频工具/audio_review/tokenhub_omni_review.py' '<完整MP4>' --output '<项目/本次对象审片目录>' --prompt-file '<独立审片提示词>' --authorized-upload --direct
```

`--direct`仅忽略本机已证实失效的环境代理，保留TLS验证、官方固定域名与禁止重定向。密钥仅在进程内读取本机thcli配置，未进入命令参数、清单或输出。模型调用前需免费额度生效。常规thcli技能流程不代跑`models free`；2026-10-12负责人直接明确要求执行该命令后，按用户指令领取MiMo免费额度成功。未开后付费、未执行生成，不把CLI错误视为授权缺失。

### 同一回力28.47秒参考的结果

| 入口与实际输入 | 结果 | 能采用什么 |
| --- | --- | --- |
| Qwen2.5官方免费演示；原HEVC整片、H264全时长兼容片分别一次 | 两次上游AppError，没有答复 | 失败证据；不算听过或模型能力否定 |
| Qwen3官方免费演示；H264完整视频、完整音轨诊断分别一次 | 两次上游AppError，没有答复 | 入口故障证据；无声音结论 |
| 已登录豆包网页；完整H264 MP4 | 明确“不支持 review-h264.mp4 文件类型” | 该网页输入限制；不推广至所有豆包/API模型 |
| 腾讯云MiMo V2.6 Flash | 完整视频、独立同源音轨、静音对照均返回；audio_tokens177/178/178，总12,741免费token | 原生请求接入通过；时间/动作描述错误，静音误报嗡声，不能自动放行 |

音轨原生接入已解决，可靠性缺口仍未解决。两次模型观察一致只算候选；静音对照所有PCM=0却报嗡声，有确定反证。歌词/卡点不得冻结。参考页面音乐标记与约121BPM信号候选不能充当听审结论。回读归项目对象`douyin-7611509086996231539/av-review/`，不把别的19.73秒参考转写搬过来。

### 当前计算路线：云端推理

2026-10-12负责人明确停止本地模型运行。MiniCPM GGUF权重、Comni推理程序/缓存、MNN隔离运行库和本地推理客户端均已删除；不再研究本机量化/CPU部署，不下载新权重。既有失败证据保留以追溯实际结果。

当前轻量入口为`ark_video_adapt.py`：完整MP4经官方方舟接口交给Doubao Seed 2.1 Lite理解并直接返回Seedance差异提示词。第一次调用已认证但返回ModelNotOpen，没有答复；不得宣称已审片。调用方法、密钥边界与无请求的prepare-only见[API用法](API_USAGE.md)。现有音轨提取/信号工具不承担模型推理；历史Whisper配置不作为本轮执行路线。

原视频直接进入Seedance控制动作、镜头顺序和节奏，真实商品图控制商品身份；理解模型用于辅助适配和查错，文字报告不替代原视频。外部官方Kickart结构复刻与LAS对象替换可研究，但尚未执行，不能写成已验证本鞋效果。

## 2026-10-12 GitHub能力筛选

官方仓库页面显示约数，不按star自动验收；MiniCPM-o本地和API测试见下；本地推理已退出，其余新权重未部署。

| 项目 | 约star | 实际作用与本机取舍 |
| --- | ---: | --- |
| [OpenBMB MiniCPM-V/o](https://github.com/OpenBMB/MiniCPM-V) | 26.5k | 选MiniCPM-o4.5的同步音视频输入，不误用仅视觉的V4.6。官方9B/int4测试约11GB显存，8GB机器需检验CPU/GGUF或卸载，并核全部音视频能力保留。已测试失败并退出本地部署 |
| [Qwen3-Omni](https://github.com/QwenLM/Qwen3-Omni) | 4k | 原生音视频、use_audio_in_video=True；常规30秒BF16示例Instruct约88.52GB，Thinking约77.79GB，不能直接本机运行。云端/另经验证量化作交叉核验；HF演示故障不是模型否定 |
| [VideoLLaMA2](https://github.com/DAMO-NLP-SG/VideoLLaMA2) | 1.3k | 必须AV checkpoint（2.1-7B-AV），默认视觉checkpoint不能听。8/16帧路线不适合本片精确快切终审，备用研究 |
| [ComfyUI](https://github.com/Comfy-Org/ComfyUI) | 137k | 参考条件、遮罩、合成、插帧/超分与视频工作流；是执行框架，不能自己理解审美或保障鞋纹身份 |
| [Wan2.2](https://github.com/Wan-Video/Wan2.2) | 17.9k | Animate接参考视频+人物图，动作迁移/人物替换。不是已验证的商品替换。本片只有小腿和鞋，姿态/遮罩/细鞋纹需专项验证；不声称现有8GB可运行官方配置 |

[MiniCPM官方同步输入示例](https://github.com/OpenBMB/MiniCPM-o-Demo)将16kHz音频与视频帧按同一时间输入；原生AV并不意味着模型看每一帧，也不免除误报测试。[Wan官方预处理](https://github.com/Wan-Video/Wan2.2/blob/main/wan/modules/animate/preprocess/UserGuider.md)强调姿态和遮罩、比例差异；[Comfy官方替换模板](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/template_purz_wan22_animate_auto_character_replace.json)更适合清楚人物，推荐77—150帧并中心裁切。长片需连续段策略，不把短模板直接当28秒商品复刻。

云端候选的最小验收：静音不得虚构声源；已知短语/音效可正确识别；同画面换音轨后声音描述必须相应变化；原片4.367秒跳切、14.933—17.233经过镜头和固定相机判断可与原尺寸证据核对。先完成这些，再评估声画节奏建议；模型答复、技术导入及star均不能自动放行商业成片。

## MiniCPM-o实测与当前计算路线（2026-10-12）

负责人要求优先API后，本机模型推理已停止。保留[minicpm_api_review.py](minicpm_api_review.py)发送完整原生音视频到MiniCPM-o官方公开Realtime接口，backend实际返回pytorch；本机只解码和存证。本地GGUF备用客户端及运行环境随后按负责人要求删除。云端调用、授权、静音守卫与输入范围见[API使用说明](API_USAGE.md)。

本地Q4_K_M+16层GPU/其余CPU确实完成12秒音频推理，耗时297.563秒；全零静音被虚构为讨论风景电影。本地不再默认启用。官方API完整28.47秒原片耗时38.406秒、原音轨15.891秒，恢复已知短语主体但误认专名；全零静音虚构讲解，同画面静音虚构摩擦，三提示音错数为五。所有失败和首次网络超时保留；连接失败后只明确重连一次，不覆写错误。两种路线均未通过可靠自动审片；计算速度提升不等于语义或审美能力通过。

同画面换音三条全帧解码hash一致，全部28.466667秒，完整音轨未截短。原音输入与MiMo共同支持英文演唱电子节奏的大类观察，仍不确认歌词/具体卡点；模型“连续穿袜/穿鞋”描述已被源边界帧否定。实际结果归具体项目同一参考的av-review，不在本工具入口重复客户或账号证据。没有租云、使用付费密钥或执行付费视频生成。

精确静音业务输入现在由本地零样本检查跳过API；明确模型控制测试才允许强制提交。这是确定性输入验证，不能当作模型测试通过。后续API选择仍优先原生声画、留存整个输入与测试失败，不把图片抽帧配ASR升级为完整声音理解，也不把模型输出长度当能力证据。
