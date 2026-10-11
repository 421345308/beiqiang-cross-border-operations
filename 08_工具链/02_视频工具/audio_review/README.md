# 本地视频声音分析

作用：从已核身份的视频原件提取音轨，恢复口播的词级时间、响度能量包络、声音变化与节拍候选，供镜头分析和剪辑使用。没有上传、模型下载、付费API或审美评分；原件只读，证据保存到具体项目。

## 当前选择与GitHub研究

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
