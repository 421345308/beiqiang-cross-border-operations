# Seedance 商品视频工具

## 使用边界

本页只说明本地脚本的调用方式，不决定当前默认视频模型。每次按项目要求、已安装的相关 Skill、当前服务端模型列表和费用核对模型 ID；付费生成遵守根 `AGENTS.md` 的当次授权。下方模型 ID 是历史命令示例，不证明今天仍可用。

`prompts/BQ001_*` 是 BQ001 早期生成任务的原始提示词证据；[逐次复盘](../../../05_内容与视频/01_贝强商品视频/seedance/reviews/BQ001.md)按原路径引用。它们不作新任务模板，也不因版本号较高而自动成为最佳方案。新项目提示词与结果写回对应项目，工具目录仅保留可复用示例和脚本。

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
- 真实素材与 AI 镜头的比例由当前项目目的和逐镜验收决定，不套固定百分比。
- 字幕、价格、MOQ、Logo 和 CTA 建议后期添加，不让视频模型直接生成文字。
- TikTok 发布现实感 AI 视频时，启用平台的 AI-generated 内容标记。
