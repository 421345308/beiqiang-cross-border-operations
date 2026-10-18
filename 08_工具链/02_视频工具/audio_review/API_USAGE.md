# 云端原生音视频客户端

所有语义模型推理走云端，本机只解码、检查和保存证据。当前制作采用原视频直接作为生成模型参考条件；理解模型辅助商品差异与提示词适配，不以文字报告重建原片。客户端返回答复不等于语义或商业成片验收通过。

## 方舟豆包：完整视频与提示词适配

`ark_video_adapt.py`按官方Chat接口发送完整带声音MP4，要求现有`ARK_API_KEY`，不安装模型、不自动开通资源、不生成视频、不自动重试。模型固定为文档中支持内嵌音轨的`doubao-seed-2-1-lite-260915`；账号未开通则保留ModelNotOpen错误，不能声称审片成功。官方契约见[音频理解](https://docs.volcengine.com/docs/ark/audio-understanding?lang=zh)和[视频理解](https://docs.volcengine.com/docs/ark/video-understanding?lang=zh)。

```powershell
python ark_video_adapt.py '<完整带声MP4>' --prompt-file '<适配要求>' --output '<独立尝试目录>' --authorized-upload --authorized-call
```

理解请求可能计量收费，两个授权标记分别对应文件上传与本次理解调用；不代替实际授权。`--prepare-only`只检查输入并保存元数据，不联系API。限30秒、25MB，原生完整文件输入、服务器2fps采样，不能声称看尽全部帧。usage中的audio_tokens只证明音轨输入计量，语义正确性仍独立检验。

密钥只在进程中读取，禁止写入参数、清单或Git。`--direct`用于已证实失效的环境代理，TLS仍开启，固定官方域名且禁止重定向；已有manifest目录拒绝重用。保留源hash、请求元数据、原始回执、耗时和usage，不保存base64文件副本。

## MiniCPM-o公开演示：研究对照入口

可通过官方公开演示API发送完整MP4或16kHz单声道WAV/FLAC；匿名演示不等于生产SLA。客户端不使用API密钥、不触发视频生成。该入口仍须通过语义对照后才可采用，不因模型在云端而认定准确。

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

## 计算边界

本地量化推理路线已退出；不下载权重、不部署推理服务器，也不自动退回CPU。本地历史试验记录只用于查证，不是部署入口。

## 必须保留的语义对照

在使用某入口自动评价成片前，先测已知短语、无音频内容的零样本、次数与时刻已知的声音，以及同画面更换音轨。全程音频接入、输出文字、输入token计量与语义正确性是不同状态；任何关键对照失败都要保留，不以后处理规则声称原模型通过。声音判别还需对照画面边界帧、身份和完整动作，文字模型建议不能代替连续观看。
