# Seedance 商品视频工具

## 推荐用法

本工作区默认使用已开通的完整版 `Seedance 2.0`。只有明确传入其他模型 ID 时，才会调用 Mini 或 Fast。`Seedance 1.5 Pro` 已被官方模型列表标记为即将下线，不建议新流程继续绑定。

不要把 API Key 写入脚本或提示词。PowerShell 当前窗口中设置：

```powershell
$env:ARK_API_KEY="你的火山方舟 API Key"
python -m pip install "volcengine-python-sdk[ark]"
```

## 生成 TikTok 试片

媒体素材必须是火山方舟可下载的公网 URL 或已授权的 `asset://` 素材 ID。
本地图片也可通过 `--image-file` 传入，脚本会自动转换为 Base64 数据。

```powershell
python .\08_工具链\02_视频工具\seedance_video\seedance_generate.py create `
  --prompt-file .\08_工具链\02_视频工具\seedance_video\prompts\01_tiktok_product_proof_en.txt `
  --image-url "https://你的素材地址/鞋子主图.jpg" `
  --model "doubao-seedance-2-0-260128" `
  --ratio "9:16" `
  --resolution "720p" `
  --duration 8
```

本地图片示例：

```powershell
python .\08_工具链\02_视频工具\seedance_video\seedance_generate.py create `
  --prompt-file .\08_工具链\02_视频工具\seedance_video\prompts\01_tiktok_product_proof_en.txt `
  --image-file ".\01_产品资产\02_可发布素材\00_最终上传\BQ017_A008\01_主图\01_main.jpg" `
  --resolution "480p" `
  --duration 8 `
  --no-generate-audio
```

结果 JSON 和视频会保存到 `05_内容与视频/01_贝强商品视频/seedance`。火山方舟返回的视频链接有效期有限，脚本成功后会立即下载。

## 生成 Alibaba.com 横版

```powershell
python .\08_工具链\02_视频工具\seedance_video\seedance_generate.py create `
  --prompt-file .\08_工具链\02_视频工具\seedance_video\prompts\03_alibaba_b2b_showcase_en.txt `
  --image-url "https://你的素材地址/鞋子主图.jpg" `
  --image-url "https://你的素材地址/鞋子侧面.jpg" `
  --model "doubao-seedance-2-0-fast-260128" `
  --ratio "16:9" `
  --resolution "720p" `
  --duration 12
```

## 查询已有任务

```powershell
python .\08_工具链\02_视频工具\seedance_video\seedance_generate.py get "任务ID" --download
```

## 内容边界

- AI 适合：商品转台、材质微距、上脚氛围、视觉转场、背景和镜头运动。
- 必须真实：工厂、工人、质检、装箱、仓库、产能、证书、测试数据和客户评价。
- 最佳成片通常是混剪：真实商品/工厂素材占 60%-80%，AI 镜头占 20%-40%。
- 字幕、价格、MOQ、Logo 和 CTA 建议后期添加，不让视频模型直接生成文字。
- TikTok 发布现实感 AI 视频时，启用平台的 AI-generated 内容标记。
