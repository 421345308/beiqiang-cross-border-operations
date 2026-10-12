# MiniCPM-o API与本地客户端

优先通过官方MiniCPM-o公开演示API审阅完整MP4或16kHz单声道WAV/FLAC，本机只解码、检查和保存证据，不承担模型推理。这个入口使用服务端计算；匿名演示不等于承诺长期服务或生产SLA。未使用API密钥、未触发视频生成，也不自动改用付费入口。

官方契约与来源：[Realtime概览](https://github.com/OpenBMB/MiniCPM-o-Demo/blob/main/docs-app/content/docs/en/realtime-api/overview.md)、[Chat契约](https://github.com/OpenBMB/MiniCPM-o-Demo/blob/main/docs-app/content/docs/en/realtime-api/chat.md)、[视频音频转换实现](https://github.com/OpenBMB/MiniCPM-o-Demo/blob/main/apps/server/core/processors/base.py)。部署版本可能与master不同，因此保存实际返回的backend和session信息，不能仅由源码断言服务端内部实现完全相同。

## API调用

依赖Python、FFmpeg/ffprobe、numpy、soundfile、websocket-client；客户端不安装依赖或下载权重。

```powershell
python minicpm_api_review.py '<完整MP4或16kHz单声道音轨>' --output '<独立尝试目录>' --prompt-file '<审片原文>' --authorized-upload
```

`--authorized-upload`只表示调用方已有该文件、平台和用途的授权，不代替取得授权。`--direct`仅在环境代理已经确认失效时使用，忽略当前进程的代理变量，TLS校验仍开启。完整MP4按原字节发送，音轨按全样本float32发送；视频不是图片序列配转写。`--stack-frames 1`是服务端标准采样，5为官方高刷新选项；均不能声称看尽所有源帧。

已有manifest的目录拒绝重用，无自动重试。网络错误与模型错误分别保留；明确网络连接失败后人工决定新目录重试，不覆盖失败。`--audio-only`要求已解码WAV/FLAC，不会从MP4静默抽取音轨。非零音轨起点要求另做时钟映射。

精确零样本静音默认在本地确认后跳过API，manifest为`skipped_exact_silence`，不产生冒充模型的回答。仅做模型对照时传`--control-test`，允许把全零静音提交并检查误报。低音量或背景噪声不按静音处理。

保存manifest、请求元数据、原始事件与未改写response.txt；base64输入不抄入请求日志。`answered_unverified`仅代表接口返回。服务端生成文字仍可能误认歌词、编造声源、错误计算事件数或把跳切说成连续动作，不能作自动商业审美验收。

## 本地备用

`minicpm_cpp_review.py`通过loopback调用已经部署的llama.cpp-omni；客户端不下载权重或启动服务器。同步传入源时钟的音频块和对应视觉帧，保存完整采样和回执。具体调用见其`--help`；运行环境、模型hash、卸载层数与峰值内存必须由本次部署另存。

8GB显存可通过部分CPU卸载加载Q4模型，加载成功不保证速度与正确性。发现资源或语义问题时停止该运行，不因已下载权重继续无效长测。公开API也需要独立验收，远端计算不是准确性保证。

## 必须保留的语义对照

在使用某入口自动评价成片前，先测已知短语、无音频内容的零样本、次数与时刻已知的声音，以及同画面更换音轨。全程音频接入、输出文字、输入token计量与语义正确性是不同状态；任何关键对照失败都要保留，不以后处理规则声称原模型通过。声音判别还需对照画面边界帧、身份和完整动作，文字模型建议不能代替连续观看。
